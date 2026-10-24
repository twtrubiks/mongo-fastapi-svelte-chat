"""ConnectionManager 測試用的成員資格查詢（取代 RoomService，不連資料庫）"""

from collections.abc import Awaitable, Callable


class FakeMembership:
    """房間成員表：房間 ID → 成員 ID"""

    def __init__(self, rooms: dict[str, set[str]] | None = None):
        self.rooms = rooms if rooms is not None else {}

    async def get_member_ids(self, room_id: str) -> list[str]:
        return sorted(self.rooms.get(room_id, set()))

    async def get_member_room_ids(self, user_id: str, room_ids: list[str]) -> list[str]:
        return [rid for rid in room_ids if user_id in self.rooms.get(rid, set())]

    def factory(self) -> Callable[[], Awaitable["FakeMembership"]]:
        """給 ConnectionManager(membership=...) 的工廠"""

        async def create() -> FakeMembership:
            return self

        return create
