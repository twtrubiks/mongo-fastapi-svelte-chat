"""基礎 Repository 抽象類"""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from app.database.improved_transaction import (
    ImprovedTransactionMixin as TransactionMixin,
)

logger = logging.getLogger(__name__)


class BaseRepository[T](ABC, TransactionMixin):
    """基礎資料存取抽象類"""

    def __init__(self, database: AsyncDatabase, collection_name: str):
        """
        初始化 Repository

        Args:
            database: MongoDB 資料庫連線
            collection_name: 集合名稱
        """
        self.db = database
        self.collection: AsyncCollection = database[collection_name]
        self.collection_name = collection_name

    def _get_session_kwargs(self) -> dict[str, Any]:
        """
        獲取 session 相關的參數

        Returns:
            Dict[str, Any]: session 參數字典
        """
        # 目前不使用事務，返回空字典
        return {}

    async def find_by_id(self, id: str | ObjectId) -> dict[str, Any] | None:
        """
        根據 ID 查找文檔

        Args:
            id: 文檔 ID

        Returns:
            Optional[Dict[str, Any]]: 找到的文檔，如果不存在則返回 None
        """
        if isinstance(id, str):
            if not ObjectId.is_valid(id):
                return None
            id = ObjectId(id)

        try:
            document = await self.collection.find_one(
                {"_id": id}, **self._get_session_kwargs()
            )
            if document:
                document["_id"] = str(document["_id"])
            return document
        except Exception as e:
            logger.error(f"Error finding document by ID {id}: {e}")
            return None

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        """
        查找單個文檔

        Args:
            query: 查詢條件

        Returns:
            Optional[Dict[str, Any]]: 找到的文檔，如果不存在則返回 None
        """
        try:
            document = await self.collection.find_one(
                query, **self._get_session_kwargs()
            )
            if document:
                document["_id"] = str(document["_id"])
            return document
        except Exception as e:
            logger.error(f"Error finding document with query {query}: {e}")
            return None

    async def find_many(
        self,
        query: dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        sort: list[tuple] | None = None,
    ) -> list[dict[str, Any]]:
        """
        查找多個文檔

        Args:
            query: 查詢條件
            skip: 跳過的文檔數
            limit: 返回的文檔數限制
            sort: 排序條件

        Returns:
            List[Dict[str, Any]]: 找到的文檔列表
        """
        try:
            cursor = (
                self.collection.find(query, **self._get_session_kwargs())
                .skip(skip)
                .limit(limit)
            )
            if sort:
                cursor = cursor.sort(sort)

            documents = await cursor.to_list(length=limit)

            # 轉換 ObjectId 為字符串
            for doc in documents:
                doc["_id"] = str(doc["_id"])

            return documents
        except Exception as e:
            logger.error(f"Error finding documents with query {query}: {e}")
            return []

    async def count_documents(self, query: dict[str, Any]) -> int:
        """
        計算符合條件的文檔數量

        Args:
            query: 查詢條件

        Returns:
            int: 文檔數量
        """
        try:
            return await self.collection.count_documents(
                query, **self._get_session_kwargs()
            )
        except Exception as e:
            logger.error(f"Error counting documents with query {query}: {e}")
            return 0

    async def insert_one(self, document: dict[str, Any]) -> str | None:
        """
        插入單個文檔

        Args:
            document: 要插入的文檔

        Returns:
            Optional[str]: 插入文檔的 ID，如果失敗則返回 None
        """
        try:
            # 添加時間戳
            document["created_at"] = datetime.now(UTC)
            document["updated_at"] = datetime.now(UTC)

            result = await self.collection.insert_one(
                document, **self._get_session_kwargs()
            )
            logger.info(
                f"Document inserted in {self.collection_name}: {result.inserted_id}"
            )
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error inserting document: {e}")
            return None

    async def insert_many(self, documents: list[dict[str, Any]]) -> list[str]:
        """
        插入多個文檔

        Args:
            documents: 要插入的文檔列表

        Returns:
            List[str]: 插入文檔的 ID 列表
        """
        try:
            # 添加時間戳
            now = datetime.now(UTC)
            for doc in documents:
                doc["created_at"] = now
                doc["updated_at"] = now

            result = await self.collection.insert_many(
                documents, **self._get_session_kwargs()
            )
            logger.info(
                f"Documents inserted in {self.collection_name}: {len(result.inserted_ids)}"
            )
            return [str(id) for id in result.inserted_ids]
        except Exception as e:
            logger.error(f"Error inserting documents: {e}")
            return []

    async def update_one(
        self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False
    ) -> bool:
        """
        更新單個文檔

        Args:
            query: 查詢條件
            update: 更新內容
            upsert: 如果不存在是否創建

        Returns:
            bool: 是否更新成功
        """
        try:
            # 添加更新時間戳
            if "$set" in update:
                update["$set"]["updated_at"] = datetime.now(UTC)
            else:
                update["$set"] = {"updated_at": datetime.now(UTC)}

            result = await self.collection.update_one(
                query, update, upsert=upsert, **self._get_session_kwargs()
            )

            if result.modified_count > 0:
                logger.info(f"Document updated in {self.collection_name}")
                return True
            elif result.upserted_id and upsert:
                logger.info(
                    f"Document upserted in {self.collection_name}: {result.upserted_id}"
                )
                return True

            return False
        except Exception as e:
            logger.error(f"Error updating document: {e}")
            return False

    async def update_many(self, query: dict[str, Any], update: dict[str, Any]) -> int:
        """
        更新多個文檔

        Args:
            query: 查詢條件
            update: 更新內容

        Returns:
            int: 更新的文檔數量
        """
        try:
            # 添加更新時間戳
            if "$set" in update:
                update["$set"]["updated_at"] = datetime.now(UTC)
            else:
                update["$set"] = {"updated_at": datetime.now(UTC)}

            result = await self.collection.update_many(
                query, update, **self._get_session_kwargs()
            )
            logger.info(
                f"Documents updated in {self.collection_name}: {result.modified_count}"
            )
            return result.modified_count
        except Exception as e:
            logger.error(f"Error updating documents: {e}")
            return 0

    async def delete_one(self, query: dict[str, Any]) -> bool:
        """
        刪除單個文檔

        Args:
            query: 查詢條件

        Returns:
            bool: 是否刪除成功
        """
        try:
            result = await self.collection.delete_one(
                query, **self._get_session_kwargs()
            )
            if result.deleted_count > 0:
                logger.info(f"Document deleted from {self.collection_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False

    async def delete_many(self, query: dict[str, Any]) -> int:
        """
        刪除多個文檔

        Args:
            query: 查詢條件

        Returns:
            int: 刪除的文檔數量
        """
        try:
            result = await self.collection.delete_many(
                query, **self._get_session_kwargs()
            )
            logger.info(
                f"Documents deleted from {self.collection_name}: {result.deleted_count}"
            )
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            return 0

    async def exists(self, query: dict[str, Any]) -> bool:
        """
        檢查文檔是否存在

        Args:
            query: 查詢條件

        Returns:
            bool: 文檔是否存在
        """
        try:
            count = await self.collection.count_documents(
                query, limit=1, **self._get_session_kwargs()
            )
            return count > 0
        except Exception as e:
            logger.error(f"Error checking document existence: {e}")
            return False

    async def aggregate(self, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        執行聚合查詢

        Args:
            pipeline: 聚合管道

        Returns:
            List[Dict[str, Any]]: 聚合結果
        """
        try:
            # PyMongo 的 AsyncCollection.aggregate() 是一個協程函數
            # 需要 await 來獲取 AsyncCommandCursor
            cursor = await self.collection.aggregate(
                pipeline, **self._get_session_kwargs()
            )

            # 使用異步迭代器收集結果
            results = []
            async for document in cursor:
                # 轉換 ObjectId 為字符串
                if "_id" in document and isinstance(document["_id"], ObjectId):
                    document["_id"] = str(document["_id"])
                results.append(document)

            return results
        except Exception as e:
            logger.error(f"Error executing aggregation: {e}")
            return []

    async def create_index(self, index_spec: str | list[tuple], **kwargs) -> str:
        """
        創建索引

        Args:
            index_spec: 索引規格
            **kwargs: 其他索引選項

        Returns:
            str: 索引名稱
        """
        try:
            index_name = await self.collection.create_index(index_spec, **kwargs)
            logger.info(f"Index created in {self.collection_name}: {index_name}")
            return index_name
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            return ""

    async def drop_index(self, index_name: str) -> bool:
        """
        刪除索引

        Args:
            index_name: 索引名稱

        Returns:
            bool: 是否刪除成功
        """
        try:
            await self.collection.drop_index(index_name)
            logger.info(f"Index dropped in {self.collection_name}: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Error dropping index: {e}")
            return False

    @abstractmethod
    async def get_by_id(self, id: str) -> T | None:
        """
        根據 ID 獲取實體物件

        Args:
            id: 實體 ID

        Returns:
            Optional[T]: 實體物件，如果不存在則返回 None
        """
        pass

    @abstractmethod
    async def create(self, entity: T) -> T | None:
        """
        創建新實體

        Args:
            entity: 實體物件

        Returns:
            Optional[T]: 創建後的實體物件，如果失敗則返回 None
        """
        pass

    @abstractmethod
    async def update(self, id: str, entity: T) -> T | None:
        """
        更新實體

        Args:
            id: 實體 ID
            entity: 更新後的實體物件

        Returns:
            Optional[T]: 更新後的實體物件，如果失敗則返回 None
        """
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """
        刪除實體

        Args:
            id: 實體 ID

        Returns:
            bool: 是否刪除成功
        """
        pass
