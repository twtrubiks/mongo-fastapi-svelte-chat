"""為既有訊息補上 per-room seq 並校正 counters（一次性遷移，冪等可重跑）

使用方式（建議在後端服務停止時執行，避免與新訊息取號競爭）：

    cd backend && python -m scripts.backfill_message_seq

行為：
- 找出仍有訊息缺少 seq 的房間
- 將該房間「全部」訊息按 (created_at, _id) 重新編號 1..N
  （混合狀態下無法只補舊訊息——舊訊息比新訊息早，插不進已占用的小序號）
- 將 counters 的 room_seq 設為 N
"""

import asyncio

from pymongo import AsyncMongoClient, UpdateOne

from app.config import settings


async def backfill() -> None:
    client = AsyncMongoClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DATABASE]

    # 找出仍有訊息缺 seq 的房間
    room_ids = await db["messages"].distinct(
        "room_id", {"$or": [{"seq": None}, {"seq": {"$exists": False}}]}
    )

    if not room_ids:
        print("所有訊息皆已有 seq，無需遷移")
        await client.close()
        return

    for room_id in room_ids:
        cursor = (
            db["messages"]
            .find({"room_id": room_id}, {"_id": 1})
            .sort([("created_at", 1), ("_id", 1)])
        )

        operations = []
        seq = 0
        async for doc in cursor:
            seq += 1
            operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"seq": seq}}))

        if operations:
            await db["messages"].bulk_write(operations)

        # 校正 counter：下一則訊息從 N+1 開始
        await db["counters"].update_one(
            {"_id": f"room_seq:{room_id}"},
            {"$set": {"seq": seq}},
            upsert=True,
        )
        print(f"房間 {room_id}：重新編號 {seq} 則訊息，counter 設為 {seq}")

    print(f"\n完成：共處理 {len(room_ids)} 個房間")
    await client.close()


if __name__ == "__main__":
    asyncio.run(backfill())
