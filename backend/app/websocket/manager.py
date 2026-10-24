"""WebSocket 連線管理器"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import WebSocket

from app.utils.json_encoder import safe_json_dumps

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 連線管理器"""

    def __init__(self):
        # 儲存所有活躍的 WebSocket 連線
        # 格式: {user_id: {room_id: websocket}}
        self.active_connections: dict[str, dict[str, WebSocket]] = {}

        # 儲存房間中的使用者
        # 格式: {room_id: {user_id}}
        self.room_users: dict[str, set[str]] = {}

        # 儲存使用者資訊
        # 格式: {user_id: user_info}
        self.user_info: dict[str, dict] = {}

        # 全局在線使用者集合
        self.global_online_users: set[str] = set()

        # 待執行的離線 task（debounce）
        # 格式: {user_id: asyncio.Task}
        self._pending_offline: dict[str, asyncio.Task] = {}

        # debounce 秒數
        self._disconnect_debounce_seconds: float = 3.0

        # 待執行的房間離開 task（per-room debounce）
        # 格式: {(user_id, room_id): asyncio.Task}
        self._pending_room_leave: dict[tuple[str, str], asyncio.Task] = {}

        # 房間重新連線 debounce 秒數
        self._room_rejoin_debounce_seconds: float = 5.0

        # 連線鎖，確保線程安全
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        room_id: str,
        user_info: dict,
        still_member: Callable[[], Awaitable[bool]] | None = None,
    ) -> bool:
        """
        建立 WebSocket 連線

        Args:
            websocket: WebSocket 連線物件
            user_id: 使用者 ID
            room_id: 房間 ID
            user_info: 使用者資訊
            still_member: 登記連線後再確認一次成員資格。連線前雖已驗證過，但撤銷
                （force_disconnect）只斷得到已登記的連線，驗證之後、登記之前被移出，
                這條連線就會留下來繼續收房間廣播。先登記再確認：撤銷不是在這裡被發現，
                就是斷得到這條連線。確認通過前不加入房間名單、不宣告加入

        Returns:
            bool: 是否建立連線
        """
        # 在測試環境中，WebSocket 可能還未被接受
        # 在生產環境中，WebSocket 已經在 handlers.py 中被接受
        # 我們需要處理這兩種情況
        try:
            # 嘗試接受連接（用於測試環境）
            await websocket.accept()
        except Exception:  # intentional: 連線可能已被上層 accept，忽略重複 accept 錯誤
            pass

        # 取消該使用者的 pending offline task（如有）
        pending_task = self._pending_offline.pop(user_id, None)
        if pending_task and not pending_task.done():
            pending_task.cancel()

        async with self._lock:
            room_key = (user_id, room_id)
            pending_room_task = self._pending_room_leave.pop(room_key, None)
            is_room_rejoin = False
            if pending_room_task and not pending_room_task.done():
                pending_room_task.cancel()
                is_room_rejoin = True
                logger.info(
                    f"User {user_id} rejoined room {room_id} within debounce window"
                )

            # 儲存連線（登記後 force_disconnect 才找得到這條連線），
            # 同一使用者在同一房間的舊連線一併從登記移除
            user_rooms = self.active_connections.setdefault(user_id, {})
            replaced = user_rooms.get(room_id)
            user_rooms[room_id] = websocket

        # 鎖外關閉舊連線：對端不回關閉握手時 close 會等到逾時，持鎖等會卡住所有人
        # 的連線與斷線。舊連線已不在登記中，它的 disconnect 會因 identity 不符略過
        if replaced is not None:
            try:
                await replaced.close()
            except Exception as e:  # intentional catch-all
                logger.error(f"Error closing old connection for user {user_id}: {e}")

        # 鎖外確認：查資料庫期間撤銷的 force_disconnect 才拿得到鎖
        if still_member is not None and not await still_member():
            # 與連線前驗證失敗相同：撤回登記並以 4001 關閉
            await self.force_disconnect(
                user_id,
                room_id,
                reason="Authentication failed",
                code=4001,
                websocket=websocket,
            )
            return False

        async with self._lock:
            # 確認期間這條連線可能已被撤銷，或被同一使用者的新連線取代
            if self.active_connections.get(user_id, {}).get(room_id) is not websocket:
                return False

            # 初始化房間使用者集合
            if room_id not in self.room_users:
                self.room_users[room_id] = set()

            # 添加使用者到房間
            self.room_users[room_id].add(user_id)

            # 儲存使用者資訊
            self.user_info[user_id] = user_info

            # 將使用者加入全局在線集合
            self.global_online_users.add(user_id)

            logger.info(f"User {user_id} connected to room {room_id}")

            # 向房間廣播使用者上線訊息（僅在非快速重連時）
            if not is_room_rejoin:
                await self.broadcast_to_room(
                    room_id,
                    {
                        "type": "user_joined",
                        "user": user_info,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "room_id": room_id,
                    },
                    exclude_user=user_id,
                )

            # 向當前使用者發送房間使用者列表（只包含當前在線的用戶）
            # 前端會將這個列表與已經從 API 載入的完整成員列表合併
            online_users = []
            for uid in self.room_users[room_id]:
                if uid in self.user_info:
                    user_data = self.user_info[uid].copy()
                    user_data["is_active"] = True  # 明確標記為在線
                    online_users.append(user_data)

            await self.send_personal_message(
                user_id,
                room_id,
                {
                    "type": "room_users",
                    "users": online_users,
                    "global_online_user_ids": list(self.global_online_users),
                    "timestamp": datetime.now(UTC).isoformat(),
                    "room_id": room_id,
                    "online_only": True,  # 標記這只是在線用戶列表
                },
            )

        await self._broadcast_user_status(
            user_id, user_info, True, exclude_room=room_id
        )
        return True

    async def disconnect(
        self, user_id: str, room_id: str, websocket: WebSocket | None = None
    ):
        """
        斷開 WebSocket 連線

        Args:
            user_id: 使用者 ID
            room_id: 房間 ID
            websocket: 要斷開的連線物件。提供時會比對 identity，
                僅當儲存的連線正是這條 websocket 才清理；
                若已被新連線取代（同 user 同房重連），則為 stale 清理直接略過，
                避免舊連線的 finally 誤刪新連線。None 時維持無條件清理（舊語意）。
        """
        async with self._lock:
            # identity 比對：連線已被新連線取代時，這是舊連線的延遲清理，
            # 不可動到新連線的任何狀態（連線、room_users、room-leave 排程）
            if websocket is not None:
                current = self.active_connections.get(user_id, {}).get(room_id)
                if current is not websocket:
                    logger.info(
                        f"Stale disconnect ignored for user {user_id} room {room_id}"
                    )
                    return

            # 移除連線
            if user_id in self.active_connections:
                if room_id in self.active_connections[user_id]:
                    del self.active_connections[user_id][room_id]

                # 如果使用者沒有其他房間連線，排程 debounce 離線
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    self._schedule_offline(user_id)

            if room_id in self.room_users and user_id in self.room_users[room_id]:
                self._schedule_room_leave(user_id, room_id)

            logger.info(f"User {user_id} disconnected from room {room_id}")

    async def force_disconnect(
        self,
        user_id: str,
        room_id: str,
        reason: str = "已離開房間",
        code: int = 4003,
        websocket: WebSocket | None = None,
        notice: dict | None = None,
    ):
        """
        強制斷開使用者在指定房間的 WS 連線（成員資格撤銷，非暫時斷線）

        與 disconnect() 的差異：
        - 立即從 room_users 移除（不走 rejoin debounce）——撤銷是確定事件，
          否則離開者會殘留在廣播名單與在線列表中繼續收到房間訊息
        - 主動關閉 socket（close code 4003，前端視為禁止訪問、不重連）

        用於離開房間／刪除房間等需要撤銷讀取權的場景。

        Args:
            user_id: 使用者 ID
            room_id: 房間 ID
            reason: 關閉原因（帶入 WS close frame）
            code: 關閉代碼（撤銷用 4003）
            websocket: 提供時比對 identity，登記的已不是這條連線（已被撤銷或被新連線
                取代）就不動任何狀態，比照 disconnect()
            notice: 關閉前送給被斷開者的最後一則訊息（如 user_left，前端據此離開房間）
        """
        closing = None
        async with self._lock:
            user_rooms = self.active_connections.get(user_id)
            if (
                websocket is not None
                and (user_rooms or {}).get(room_id) is not websocket
            ):
                return
            if user_rooms:
                closing = user_rooms.pop(room_id, None)
                # 使用者沒有其他房間連線時，比照 disconnect() 排程 debounce 離線
                if not user_rooms:
                    del self.active_connections[user_id]
                    self._schedule_offline(user_id)

            # 立即清理 room_users 與 pending room-leave task
            room_key = (user_id, room_id)
            pending_task = self._pending_room_leave.pop(room_key, None)
            if pending_task and not pending_task.done():
                pending_task.cancel()
            if room_id in self.room_users:
                self.room_users[room_id].discard(user_id)
                if not self.room_users[room_id]:
                    del self.room_users[room_id]

        # 鎖外關閉 socket（close 可能阻塞或拋錯，不可持鎖執行）
        if closing is not None:
            if notice is not None:
                try:
                    await closing.send_text(safe_json_dumps(notice))
                except Exception:  # intentional: 連線可能已由對端關閉，照常關閉
                    pass
            try:
                await closing.close(code=code, reason=reason)
            except Exception:  # intentional: 連線可能已由對端關閉
                pass
            logger.info(f"Force disconnected user {user_id} from room {room_id}")

    async def force_disconnect_room(self, room_id: str, reason: str = "房間已刪除"):
        """
        強制斷開房間內所有 WS 連線（房間刪除時撤銷所有讀取權）

        Args:
            room_id: 房間 ID
            reason: 關閉原因（帶入 WS close frame）
        """
        async with self._lock:
            # 已登記、還在確認成員資格的連線不在 room_users，一併斷開
            user_ids = self.room_users.get(room_id, set()) | {
                user_id
                for user_id, rooms in self.active_connections.items()
                if room_id in rooms
            }
        for user_id in user_ids:
            await self.force_disconnect(user_id, room_id, reason=reason)

    async def _broadcast_user_left(self, room_id: str, user_info: dict):
        """廣播 user_left 事件給房間內剩餘使用者"""
        await self.broadcast_to_room(
            room_id,
            {
                "type": "user_left",
                "user": user_info,
                "timestamp": datetime.now(UTC).isoformat(),
                "room_id": room_id,
            },
        )

    async def _broadcast_user_status(
        self,
        user_id: str,
        user_info: dict,
        is_online: bool,
        exclude_room: str | None = None,
    ):
        """廣播使用者在線狀態變更到所有有活躍連線的房間"""
        for rid in list(self.room_users.keys()):
            if rid == exclude_room:
                continue
            await self.broadcast_to_room(
                rid,
                {
                    "type": "user_status_changed",
                    "user_id": user_id,
                    "user": user_info,
                    "is_online": is_online,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

    def _schedule_offline(self, user_id: str):
        """排程 debounce 離線。注意：必須在持有 self._lock 時呼叫。"""
        # 取消舊的 pending task（如有）
        old_task = self._pending_offline.pop(user_id, None)
        if old_task and not old_task.done():
            old_task.cancel()

        task = asyncio.create_task(self._execute_offline(user_id))
        self._pending_offline[user_id] = task

    async def _execute_offline(self, user_id: str):
        """等待 debounce 時間後執行真正的離線處理"""
        await asyncio.sleep(self._disconnect_debounce_seconds)

        left_room_ids: list[str] = []

        async with self._lock:
            # 再次檢查：使用者可能已重新連線
            if user_id in self.active_connections and self.active_connections[user_id]:
                self._pending_offline.pop(user_id, None)
                return

            saved_user_info = self.user_info.get(user_id, {}).copy()

            self.global_online_users.discard(user_id)
            self.active_connections.pop(user_id, None)
            self.user_info.pop(user_id, None)
            self._pending_offline.pop(user_id, None)

            # 一併處理該使用者所有 pending room-leave tasks，
            # 避免 room debounce 比 offline debounce 長時留下殘留
            for key in [k for k in self._pending_room_leave if k[0] == user_id]:
                task = self._pending_room_leave.pop(key, None)
                if task and not task.done():
                    task.cancel()
                # 直接清理 room_users
                rid = key[1]
                if rid in self.room_users:
                    self.room_users[rid].discard(user_id)
                    left_room_ids.append(rid)
                    if not self.room_users[rid]:
                        del self.room_users[rid]

        if saved_user_info:
            for rid in left_room_ids:
                await self._broadcast_user_left(rid, saved_user_info)
            await self._broadcast_user_status(user_id, saved_user_info, False)

    def _schedule_room_leave(self, user_id: str, room_id: str):
        """排程延遲的房間離開。必須在持有 self._lock 時呼叫。"""
        room_key = (user_id, room_id)
        old_task = self._pending_room_leave.pop(room_key, None)
        if old_task and not old_task.done():
            old_task.cancel()

        task = asyncio.create_task(self._execute_room_leave(user_id, room_id))
        self._pending_room_leave[room_key] = task

    async def _execute_room_leave(self, user_id: str, room_id: str):
        """等待 debounce 時間後執行真正的房間離開處理"""
        room_key = (user_id, room_id)
        try:
            await asyncio.sleep(self._room_rejoin_debounce_seconds)

            async with self._lock:
                # 使用者可能已重新連線到此房間
                if (
                    user_id in self.active_connections
                    and room_id in self.active_connections[user_id]
                ):
                    return

                if room_id in self.room_users:
                    self.room_users[room_id].discard(user_id)
                    if not self.room_users[room_id]:
                        del self.room_users[room_id]

                logger.info(
                    f"User {user_id} room leave from {room_id} finalized after debounce"
                )

            # 不廣播 user_left：使用者只是切換房間，仍在線上
            # 真正離線時由 _execute_offline 的 user_status_changed 通知所有房間
        finally:
            # 被取消時同一個 key 可能已排入新的計時器，只移除自己的表項
            if self._pending_room_leave.get(room_key) is asyncio.current_task():
                del self._pending_room_leave[room_key]

    def get_global_online_user_ids(self) -> list[str]:
        """回傳所有全局在線的使用者 ID 列表"""
        return list(self.global_online_users)

    async def send_personal_message(self, user_id: str, room_id: str, message: dict):
        """
        發送私人訊息給特定使用者

        Args:
            user_id: 使用者 ID
            room_id: 房間 ID
            message: 訊息內容
        """
        if (
            user_id in self.active_connections
            and room_id in self.active_connections[user_id]
        ):
            websocket = self.active_connections[user_id][room_id]
            try:
                await websocket.send_text(safe_json_dumps(message))
            except Exception as e:  # intentional catch-all: 發送失敗延遲清理連線
                logger.error(f"Error sending message to {user_id}: {e}")
                # 延遲清理，避免在持有 _lock 時呼叫 disconnect 造成死鎖
                # 帶上 websocket 比對 identity，避免誤刪已取代的新連線
                asyncio.create_task(self.disconnect(user_id, room_id, websocket))

    async def broadcast_to_room(
        self, room_id: str, message: dict, exclude_user: str | None = None
    ):
        """
        向房間內所有使用者廣播訊息

        Args:
            room_id: 房間 ID
            message: 訊息內容
            exclude_user: 排除的使用者 ID
        """
        if room_id not in self.room_users:
            return

        # 複製使用者列表以避免在迭代時修改
        users_to_notify = list(self.room_users[room_id])

        for user_id in users_to_notify:
            if exclude_user and user_id == exclude_user:
                continue

            if (
                user_id in self.active_connections
                and room_id in self.active_connections[user_id]
            ):
                websocket = self.active_connections[user_id][room_id]
                try:
                    await websocket.send_text(safe_json_dumps(message))
                except Exception as e:  # intentional catch-all: 廣播失敗延遲清理連線
                    logger.error(f"Error broadcasting to {user_id}: {e}")
                    # 延遲清理，避免在持有 _lock 時呼叫 disconnect 造成死鎖
                    # 帶上 websocket 比對 identity，避免誤刪已取代的新連線
                    asyncio.create_task(self.disconnect(user_id, room_id, websocket))

    async def broadcast_message(
        self, room_id: str, message: dict, sender_id: str | None
    ):
        """
        廣播聊天訊息

        Args:
            room_id: 房間 ID
            message: 訊息內容
            sender_id: 發送者 ID，如果為 None 則不排除任何用戶
        """
        # 添加訊息元數據
        message_data = {
            "type": "message",
            "payload": message,
            "sender": self.user_info.get(sender_id, {}) if sender_id else {},
            "timestamp": datetime.now(UTC).isoformat(),
            "room_id": room_id,
        }

        await self.broadcast_to_room(room_id, message_data, exclude_user=sender_id)

    def get_room_users(self, room_id: str) -> list[dict]:
        """
        獲取房間內的使用者列表

        Args:
            room_id: 房間 ID

        Returns:
            List[Dict]: 使用者資訊列表
        """
        if room_id not in self.room_users:
            return []

        return [
            self.user_info[user_id]
            for user_id in self.room_users[room_id]
            if user_id in self.user_info
        ]

    async def handle_ping(self, user_id: str, room_id: str):
        """
        處理 ping 訊息

        Args:
            user_id: 使用者 ID
            room_id: 房間 ID
        """
        await self.send_personal_message(
            user_id,
            room_id,
            {"type": "pong", "timestamp": datetime.now(UTC).isoformat()},
        )

    async def send_event(self, user_id: str, event_data: dict):
        """
        發送通用事件給指定使用者（不需要 title/message 欄位）

        Args:
            user_id: 使用者 ID
            event_data: 事件資料（必須包含 type 欄位）
        """
        if user_id not in self.active_connections:
            return

        room_ids = list(self.active_connections[user_id].keys())
        if not room_ids:
            return

        # 發送到任意一個房間即可（避免重複）
        room_id = room_ids[0]
        try:
            await self.send_personal_message(user_id, room_id, event_data)
        except Exception as e:  # intentional catch-all: 事件發送失敗嘗試備援房間
            logger.error(f"Error sending event to {user_id} in room {room_id}: {e}")
            # 嘗試其他房間
            for fallback_room_id in room_ids[1:]:
                try:
                    await self.send_personal_message(
                        user_id, fallback_room_id, event_data
                    )
                    break
                except Exception:  # intentional: 備援房間發送失敗繼續嘗試下一個
                    continue

    async def send_notification(self, user_id: str, notification_data: dict):
        """
        發送通知給指定使用者（驗證後委派給 send_event）

        Args:
            user_id: 使用者 ID
            notification_data: 通知資料
        """
        if not notification_data:
            logger.warning(f"Empty notification data for user {user_id}")
            return

        if not notification_data.get("title") or not notification_data.get("message"):
            logger.warning(
                f"Notification missing title or message for user {user_id}: {notification_data}"
            )
            return

        notification_message = {
            "type": "notification",
            "data": notification_data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self.send_event(user_id, notification_message)


# 全域連線管理器實例
connection_manager = ConnectionManager()
