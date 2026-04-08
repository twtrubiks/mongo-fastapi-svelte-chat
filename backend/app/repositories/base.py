"""基礎 Repository 抽象類"""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger(__name__)


class BaseRepository[T](ABC):
    """基礎資料存取抽象類"""

    def __init__(self, database: AsyncDatabase, collection_name: str):
        self.db = database
        self.collection: AsyncCollection = database[collection_name]
        self.collection_name = collection_name

    @staticmethod
    def _normalize_id(document: dict[str, Any]) -> dict[str, Any]:
        """將 MongoDB _id 轉換為 id 欄位（統一所有 repo 的映射邏輯）"""
        if "_id" in document:
            document["_id"] = str(document["_id"])
            if "id" not in document:
                document["id"] = document["_id"]
        return document

    @abstractmethod
    def _to_model(self, document: dict[str, Any]) -> T:
        """將 MongoDB 文檔轉換為領域模型（子類必須實作）"""
        ...

    async def find_by_id(self, id: str | ObjectId) -> dict[str, Any] | None:
        if isinstance(id, str):
            if not ObjectId.is_valid(id):
                return None
            id = ObjectId(id)

        document = await self.collection.find_one({"_id": id})
        if document:
            self._normalize_id(document)
        return document

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        document = await self.collection.find_one(query)
        if document:
            self._normalize_id(document)
        return document

    async def find_many(
        self,
        query: dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        sort: list[tuple] | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self.collection.find(query).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)

        documents = await cursor.to_list(length=limit)

        for doc in documents:
            self._normalize_id(doc)

        return documents

    async def count_documents(self, query: dict[str, Any]) -> int:
        """計算符合條件的文檔數量"""
        return await self.collection.count_documents(query)

    async def insert_one(self, document: dict[str, Any]) -> str:
        """插入單個文檔，回傳插入文檔的 ID"""
        # 添加時間戳（截斷至毫秒，與 MongoDB 儲存精度一致）
        _now = datetime.now(UTC)
        now = _now.replace(microsecond=_now.microsecond // 1000 * 1000)
        document["created_at"] = now
        document["updated_at"] = now

        result = await self.collection.insert_one(document)
        logger.info(
            f"Document inserted in {self.collection_name}: {result.inserted_id}"
        )
        return str(result.inserted_id)

    async def update_one(
        self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False
    ) -> bool:
        """更新單個文檔，回傳是否有文檔被更新"""
        # 添加更新時間戳（截斷至毫秒，與 MongoDB 儲存精度一致）
        _now = datetime.now(UTC)
        now = _now.replace(microsecond=_now.microsecond // 1000 * 1000)
        if "$set" in update:
            update["$set"]["updated_at"] = now
        else:
            update["$set"] = {"updated_at": now}

        result = await self.collection.update_one(query, update, upsert=upsert)

        if result.modified_count > 0:
            logger.info(f"Document updated in {self.collection_name}")
            return True
        elif result.upserted_id and upsert:
            logger.info(
                f"Document upserted in {self.collection_name}: {result.upserted_id}"
            )
            return True

        return False

    async def update_many(self, query: dict[str, Any], update: dict[str, Any]) -> int:
        """更新多個文檔，回傳更新的文檔數量"""
        # 添加更新時間戳（截斷至毫秒，與 MongoDB 儲存精度一致）
        _now = datetime.now(UTC)
        now = _now.replace(microsecond=_now.microsecond // 1000 * 1000)
        if "$set" in update:
            update["$set"]["updated_at"] = now
        else:
            update["$set"] = {"updated_at": now}

        result = await self.collection.update_many(query, update)
        logger.info(
            f"Documents updated in {self.collection_name}: {result.modified_count}"
        )
        return result.modified_count

    async def delete_one(self, query: dict[str, Any]) -> bool:
        """刪除單個文檔，回傳是否有文檔被刪除"""
        result = await self.collection.delete_one(query)
        if result.deleted_count > 0:
            logger.info(f"Document deleted from {self.collection_name}")
            return True
        return False

    async def delete_many(self, query: dict[str, Any]) -> int:
        """刪除多個文檔，回傳刪除的文檔數量"""
        result = await self.collection.delete_many(query)
        logger.info(
            f"Documents deleted from {self.collection_name}: {result.deleted_count}"
        )
        return result.deleted_count

    async def get_by_id(self, id: str) -> T | None:
        """根據 ID 獲取實體（子類可覆寫以加入額外邏輯）"""
        document = await self.find_by_id(id)
        if document:
            return self._to_model(document)
        return None

    async def create(self, entity: T) -> T:
        """建立實體，直接從已知資料組裝回傳（避免 re-fetch）"""
        entity_dict = entity.model_dump(exclude={"id"})
        await self.insert_one(entity_dict)
        # pymongo insert_one 會在 dict 上注入 _id (ObjectId)，需 normalize
        self._normalize_id(entity_dict)
        # insert_one 設的 datetime 帶 tzinfo，但 MongoDB 回傳 naive UTC，
        # 去除 tzinfo 以保持一致
        for key, val in entity_dict.items():
            if isinstance(val, datetime):
                entity_dict[key] = val.replace(tzinfo=None)
        return self._to_model(entity_dict)

    async def delete(self, id: str) -> bool:
        return await self.delete_one({"_id": ObjectId(id)})
