"""加入申請資料存取層"""

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.models.enums import JoinRequestStatus
from app.models.invitation import JoinRequest
from app.repositories.base import BaseRepository


class JoinRequestRepository(BaseRepository[JoinRequest]):
    def __init__(self, database: AsyncDatabase):
        super().__init__(database, "join_requests")

    def _to_model(self, document: dict[str, Any]) -> JoinRequest:
        return JoinRequest(**document)

    async def find_pending_by_id(self, request_id: str) -> JoinRequest | None:
        document = await self.find_one(
            {"_id": ObjectId(request_id), "status": JoinRequestStatus.PENDING.value}
        )
        if document:
            return self._to_model(document)
        return None

    async def find_pending_by_room_and_user(
        self, room_id: str, requester_id: str
    ) -> JoinRequest | None:
        document = await self.find_one(
            {
                "room_id": room_id,
                "requester_id": requester_id,
                "status": JoinRequestStatus.PENDING.value,
            }
        )
        if document:
            return self._to_model(document)
        return None

    async def update_review(
        self,
        request_id: str,
        status: JoinRequestStatus,
        reviewed_by: str,
        reviewed_at: datetime,
        review_comment: str | None,
    ) -> bool:
        return await self.update_one(
            {"_id": ObjectId(request_id)},
            {
                "$set": {
                    "status": status.value,
                    "reviewed_by": reviewed_by,
                    "reviewed_at": reviewed_at,
                    "review_comment": review_comment,
                }
            },
        )

    async def find_by_room(
        self, room_id: str, status: JoinRequestStatus | None = None, limit: int = 100
    ) -> list[JoinRequest]:
        query: dict[str, Any] = {"room_id": room_id}
        if status:
            query["status"] = status.value

        documents = await self.find_many(query, sort=[("created_at", -1)], limit=limit)
        return [self._to_model(doc) for doc in documents]

    async def find_by_user(
        self, user_id: str, status: JoinRequestStatus | None = None, limit: int = 100
    ) -> list[JoinRequest]:
        query: dict[str, Any] = {"requester_id": user_id}
        if status:
            query["status"] = status.value

        documents = await self.find_many(query, sort=[("created_at", -1)], limit=limit)
        return [self._to_model(doc) for doc in documents]
