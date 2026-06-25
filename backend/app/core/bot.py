"""聊天室 AI Bot 身分與觸發判斷

Bot 是一個真實的 MongoDB 使用者（擁有固定 user_id），讓 bot 訊息能正常
渲染頭像／暱稱並走正規訊息流。啟動時由 lifespan 呼叫 ensure_bot_user 種子化，
並將 user_id 快取於模組層供 WebSocket handler 取用。
"""

import logging
import secrets
import unicodedata
from datetime import UTC, datetime, timedelta

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.auth.password import get_password_hash
from app.models.message import MessageInDB, MessageType
from app.models.user import UserInDB
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

# Bot 身分（種子化用）
BOT_USERNAME = "AI 助理"
BOT_EMAIL = "bot@chatroom.app"
BOT_FULL_NAME = "聊天室 AI 助理"

# 觸發前綴：使用者輸入以此開頭即呼叫 bot（大小寫不敏感）
BOT_TRIGGER = "@bot"

# 對話摘要指令（大小寫不敏感，完整比對）
SUMMARY_TRIGGER = "/summary"

# 啟動時快取 bot 的 user_id（ObjectId 字串）
_bot_user_id: str | None = None


async def ensure_bot_user(db: AsyncDatabase) -> str | None:
    """種子化 bot 使用者（冪等）並快取其 user_id。

    啟動時呼叫一次。bot 帳號使用隨機密碼雜湊，無法被密碼登入。

    Returns:
        str | None: bot 的 user_id；種子化失敗時為 None
    """
    global _bot_user_id

    user_repo = UserRepository(db)
    existing = await user_repo.get_by_username(BOT_USERNAME)
    if existing:
        _bot_user_id = existing.id
        logger.info(f"Bot user already exists: {existing.id}")
        return existing.id

    # 不可登入的隨機密碼（bot 永不透過密碼登入）
    bot_doc = UserInDB(
        username=BOT_USERNAME,
        email=BOT_EMAIL,
        full_name=BOT_FULL_NAME,
        hashed_password=await get_password_hash(secrets.token_urlsafe(32)),
        is_active=True,
    )
    try:
        created = await user_repo.create(bot_doc)
        _bot_user_id = created.id
        logger.info(f"Bot user seeded: {created.id}")
    except DuplicateKeyError:
        # 多 worker 併發種子化撞唯一索引：改抓既有帳號（冪等契約的預期結果）
        existing = await user_repo.get_by_username(BOT_USERNAME)
        _bot_user_id = existing.id if existing else None

    return _bot_user_id


def get_bot_user_id() -> str | None:
    """取得已快取的 bot user_id（啟動 ensure_bot_user 後可用）。"""
    return _bot_user_id


def is_bot_trigger(content: str) -> str | None:
    """判斷訊息是否呼叫 bot。

    僅當 @bot 後接空白或為字串結尾才算觸發（避免「@bother」之類誤判）。
    先做 NFKC 正規化，讓中文輸入法常打出的全形「＠bot」也能觸發；
    全形→半形為 1:1 對應，故前綴長度與原字串索引對齊，問題內容仍取原文。

    Returns:
        str | None: 觸發時回傳去除前綴後的問題（可能為空字串），否則 None
    """
    stripped = content.strip()
    normalized = unicodedata.normalize("NFKC", stripped).lower()
    if normalized == BOT_TRIGGER:
        return ""
    if normalized.startswith(BOT_TRIGGER) and normalized[len(BOT_TRIGGER)].isspace():
        return stripped[len(BOT_TRIGGER) :].strip()
    return None


def is_summary_command(content: str) -> bool:
    """判斷訊息是否為 /summary 指令（大小寫不敏感，允許前後空白）。

    先做 NFKC 正規化，讓全形「／summary」等中文輸入法輸入也能觸發。
    """
    normalized = unicodedata.normalize("NFKC", content.strip()).lower()
    return normalized == SUMMARY_TRIGGER


# @bot 多輪對話歷史參數（整房共享：只取「使用者 @bot 提問 → bot 回答」往返，
# 略過一般閒聊；套時間窗與則數上限避免翻舊帳、控制 token）
BOT_HISTORY_MAX_PAIRS = 6  # 最多帶入最近幾組往返
BOT_HISTORY_WINDOW_MINUTES = 10  # 超過此分鐘數的往返視為舊對話，不帶入
BOT_HISTORY_MAX_ANSWER_CHARS = 200  # 單則 bot 歷史回答截斷上限（控制 token）


def _as_utc(dt: datetime) -> datetime:
    """無 tzinfo 的時間視為 UTC（PyMongo 預設回傳 naive UTC），統一成 aware 以利比較。"""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def build_bot_history(
    messages: list[MessageInDB],
    bot_user_id: str,
    now: datetime | None = None,
) -> str:
    """從近期房間訊息組出 @bot 對話歷史段落（整房共享，供多輪記憶）。

    只取「使用者 @bot 提問 → 緊接的 bot 回答」配對，略過一般閒聊；當前這次尚未
    回答的提問（最後一個未配對者）自然不入歷史。套用時間窗與則數上限控制長度。

    Args:
        messages: get_room_messages_for_context 回傳的訊息（最舊→最新排序）
        bot_user_id: bot 的 user_id（用於辨識 bot 回答）
        now: 時間窗基準（預設現在；測試可注入）

    Returns:
        str: 格式化對話歷史（最舊→最新）；無可用往返時回空字串
    """
    if now is None:
        now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=BOT_HISTORY_WINDOW_MINUTES)

    pairs: list[tuple[str, str, str]] = []  # (提問者, 問題, bot 回答)
    pending: tuple[str, str] | None = None  # 最近一個未回答的 @bot 提問

    for msg in messages:
        if msg.message_type != MessageType.TEXT:
            continue
        if msg.user_id == bot_user_id:
            # bot 回答：與最近未回答的提問配對（須落在時間窗內）
            if pending is not None and _as_utc(msg.created_at) >= cutoff:
                pairs.append((pending[0], pending[1], msg.content))
            pending = None
            continue
        # 使用者訊息：是 @bot 提問才暫存待配對（空問題與閒聊略過）
        question = is_bot_trigger(msg.content)
        if question:
            pending = (msg.username, question)

    if not pairs:
        return ""

    lines: list[str] = []
    for username, question, answer in pairs[-BOT_HISTORY_MAX_PAIRS:]:
        lines.append(f"{username}: {question}")
        lines.append(f"{BOT_USERNAME}: {answer[:BOT_HISTORY_MAX_ANSWER_CHARS]}")
    return "\n".join(lines)
