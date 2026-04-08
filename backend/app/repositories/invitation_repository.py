"""邀請資料存取層"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.models.enums import InvitationStatus
from app.models.invitation import RoomInvitation
from app.repositories.base import BaseRepository


class InvitationRepository(BaseRepository[RoomInvitation]):
    def __init__(self, database: AsyncDatabase):
        super().__init__(database, "room_invitations")

    def _to_model(self, document: dict[str, Any]) -> RoomInvitation:
        return RoomInvitation(**document)

    async def find_pending_by_code(self, invite_code: str) -> RoomInvitation | None:
        document = await self.find_one(
            {"invite_code": invite_code, "status": InvitationStatus.PENDING.value}
        )
        if document:
            return self._to_model(document)
        return None

    async def find_by_code(self, invite_code: str) -> RoomInvitation | None:
        document = await self.find_one({"invite_code": invite_code})
        if document:
            return self._to_model(document)
        return None

    async def update_status(self, invitation_id: str, status: InvitationStatus) -> bool:
        return await self.update_one(
            {"_id": ObjectId(invitation_id)},
            {"$set": {"status": status.value}},
        )

    async def find_by_room(
        self, room_id: str, active_only: bool = False, limit: int = 100
    ) -> list[RoomInvitation]:
        query: dict[str, Any] = {"room_id": room_id}
        if active_only:
            query["status"] = InvitationStatus.PENDING.value
            query["expires_at"] = {"$gt": datetime.now(UTC)}

        documents = await self.find_many(query, sort=[("created_at", -1)], limit=limit)
        return [self._to_model(doc) for doc in documents]
