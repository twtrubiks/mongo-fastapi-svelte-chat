"""MongoDB 索引定義與建立模組

應用程式啟動時自動建立索引，確保查詢效能與資料唯一性約束。
create_index 是冪等操作，索引已存在時會跳過。
"""

import logging

from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger(__name__)


async def ensure_indexes(db: AsyncDatabase) -> None:
    """建立所有 collection 的索引"""

    # ── users ──
    users = db["users"]
    # 唯一索引：防止重複用戶名與 email
    await users.create_index([("username", ASCENDING)], unique=True)
    await users.create_index([("email", ASCENDING)], unique=True)

    # ── messages ──
    messages = db["messages"]
    # 複合索引：進入聊天室載入訊息（最高頻查詢）
    await messages.create_index([("room_id", ASCENDING), ("created_at", DESCENDING)])

    # ── rooms ──
    rooms = db["rooms"]
    # 多鍵索引：查詢「我的房間」列表（members 是陣列，MongoDB 自動建 multikey index）
    await rooms.create_index([("members", ASCENDING)])
    # 複合索引：探索頁面查詢公開房間 + 按建立時間排序
    await rooms.create_index([("is_public", ASCENDING), ("created_at", DESCENDING)])

    # ── notifications ──
    notifications = db["notifications"]
    # 複合索引：查詢使用者通知列表 + 未讀計數
    await notifications.create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)]
    )

    # ── room_invitations ──
    invitations = db["room_invitations"]
    # 唯一索引：防止重複邀請碼
    await invitations.create_index([("invite_code", ASCENDING)], unique=True)

    logger.info("MongoDB 索引建立完成")
