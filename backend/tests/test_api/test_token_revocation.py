"""Token 撤銷端到端測試

改密碼後 token_version +1，既有 access / refresh token 必須立即失效；
一般資料更新不影響既有 token；刪除帳號後既有 token 不可再使用。
每個情境都先以舊 token 打一次 API 讓使用者快取生效，確認撤銷不會被快取遮蔽。
"""

import pytest

from app.utils.user_cache import get_cached_user

FORM = {"Content-Type": "application/x-www-form-urlencoded"}


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
        headers=FORM,
    )


@pytest.fixture
async def session(async_client, isolated_db_manager):
    """註冊並登入，回傳 token 與使用者 ID；並確認使用者快取已被寫入"""
    user = {
        "username": "revokeuser",
        "email": "revoke@example.com",
        "password": "oldpass123",
    }
    await async_client.post("/api/auth/register", json=user)
    tokens = (await _login(async_client, user["username"], user["password"])).json()

    me = await async_client.get("/api/auth/me", headers=_bearer(tokens["access_token"]))
    assert me.status_code == 200
    user_id = me.json()["id"]
    assert await get_cached_user(user_id) is not None, "Redis 使用者快取未生效"

    return {**user, **tokens, "user_id": user_id}


@pytest.mark.asyncio
@pytest.mark.integration
class TestTokenRevocation:
    async def test_change_password_revokes_existing_tokens(self, async_client, session):
        response = await async_client.put(
            "/api/auth/change-password",
            json={"current_password": "oldpass123", "new_password": "newpass123"},
            headers=_bearer(session["access_token"]),
        )
        assert response.status_code == 200

        old_access = await async_client.get(
            "/api/auth/me", headers=_bearer(session["access_token"])
        )
        assert old_access.status_code == 401

        old_refresh = await async_client.post(
            "/api/auth/refresh", json={"refresh_token": session["refresh_token"]}
        )
        assert old_refresh.status_code == 401

    async def test_new_login_after_password_change_works(self, async_client, session):
        """改過密碼的使用者重新登入後，新 token 與換發的 token 都可正常使用"""
        await async_client.put(
            "/api/auth/change-password",
            json={"current_password": "oldpass123", "new_password": "newpass123"},
            headers=_bearer(session["access_token"]),
        )

        assert (
            await _login(async_client, "revokeuser", "oldpass123")
        ).status_code == 401
        login = await _login(async_client, "revokeuser", "newpass123")
        assert login.status_code == 200
        tokens = login.json()

        me = await async_client.get(
            "/api/auth/me", headers=_bearer(tokens["access_token"])
        )
        assert me.status_code == 200

        refreshed = await async_client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert refreshed.status_code == 200
        me_again = await async_client.get(
            "/api/auth/me", headers=_bearer(refreshed.json()["access_token"])
        )
        assert me_again.status_code == 200

    async def test_failed_password_change_keeps_tokens(self, async_client, session):
        response = await async_client.put(
            "/api/auth/change-password",
            json={"current_password": "wrongpass", "new_password": "newpass123"},
            headers=_bearer(session["access_token"]),
        )
        assert response.status_code == 400

        me = await async_client.get(
            "/api/auth/me", headers=_bearer(session["access_token"])
        )
        assert me.status_code == 200

    async def test_profile_update_does_not_revoke_tokens(self, async_client, session):
        response = await async_client.put(
            "/api/auth/profile",
            json={"full_name": "Renamed", "email": "revoke@example.com"},
            headers=_bearer(session["access_token"]),
        )
        assert response.status_code == 200

        # 快取已清除，回傳的是更新後的資料
        me = await async_client.get(
            "/api/auth/me", headers=_bearer(session["access_token"])
        )
        assert me.status_code == 200
        assert me.json()["full_name"] == "Renamed"

        refreshed = await async_client.post(
            "/api/auth/refresh", json={"refresh_token": session["refresh_token"]}
        )
        assert refreshed.status_code == 200

    async def test_deleted_account_tokens_rejected(self, async_client, session):
        response = await async_client.delete(
            "/api/auth/profile", headers=_bearer(session["access_token"])
        )
        assert response.status_code == 200

        me = await async_client.get(
            "/api/auth/me", headers=_bearer(session["access_token"])
        )
        assert me.status_code == 400

        refreshed = await async_client.post(
            "/api/auth/refresh", json={"refresh_token": session["refresh_token"]}
        )
        assert refreshed.status_code == 401
