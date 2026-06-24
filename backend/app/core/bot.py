"""聊天室 AI Bot 身分與觸發判斷

Bot 是一個真實的 MongoDB 使用者（擁有固定 user_id），讓 bot 訊息能正常
渲染頭像／暱稱並走正規訊息流。啟動時由 lifespan 呼叫 ensure_bot_user 種子化，
並將 user_id 快取於模組層供 WebSocket handler 取用。
"""

import logging
import secrets

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.auth.password import get_password_hash
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

    Returns:
        str | None: 觸發時回傳去除前綴後的問題（可能為空字串），否則 None
    """
    stripped = content.strip()
    lowered = stripped.lower()
    if lowered == BOT_TRIGGER:
        return ""
    if lowered.startswith(BOT_TRIGGER) and stripped[len(BOT_TRIGGER)].isspace():
        return stripped[len(BOT_TRIGGER) :].strip()
    return None


def is_summary_command(content: str) -> bool:
    """判斷訊息是否為 /summary 指令（大小寫不敏感，允許前後空白）。"""
    return content.strip().lower() == SUMMARY_TRIGGER
