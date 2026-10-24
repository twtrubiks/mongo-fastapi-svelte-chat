"""已設密碼、加入方式卻仍是直接加入的公開房，改為密碼加入（一次性遷移，冪等可重跑）

修正前，在房間設定替直接加入的公開房設定密碼，只會存下密碼雜湊，join_policy
仍是 direct，加入時不檢查密碼：房主以為房間已上鎖，任何人仍可直接加入。
之後的建立與更新已會改成 password；這支腳本修正修正前存下的房間。

使用方式：

    cd backend && python -m scripts.fix_password_join_policy
"""

import asyncio

from pymongo import AsyncMongoClient

from app.config import settings

# 公開、直接加入，但有密碼雜湊
UNLOCKED_PASSWORD_ROOMS = {
    "room_type": "public",
    "join_policy": "direct",
    "password_hash": {"$type": "string", "$ne": ""},
}


async def migrate() -> None:
    client = AsyncMongoClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DATABASE]

    result = await db["rooms"].update_many(
        UNLOCKED_PASSWORD_ROOMS, {"$set": {"join_policy": "password"}}
    )
    print(f"完成：{result.modified_count} 個房間改為密碼加入")
    await client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
