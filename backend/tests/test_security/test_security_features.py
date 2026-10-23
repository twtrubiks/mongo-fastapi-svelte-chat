"""真實 app 的安全行為測試（經由 HTTP 走完整的 middleware 堆疊）"""

import base64
import json
from datetime import timedelta

import jwt
import pytest

from app.auth.jwt_handler import create_access_token
from app.config import settings

SENSITIVE_KEYS = {"password", "hashed_password"}


def _all_keys(value) -> set[str]:
    """遞迴收集 JSON 結構中所有的 key"""
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys |= _all_keys(item)
        return keys
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value)) if value else set()
    return set()


def _b64(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


async def _register_and_login(client, user: dict) -> dict:
    register = await client.post("/api/auth/register", json=user)
    assert register.status_code == 201
    login = await client.post(
        "/api/auth/login",
        data={"username": user["username"], "password": user["password"]},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    tokens = login.json()
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    return {"register": register, "login": login, "me": me, **tokens}


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
@pytest.mark.integration
class TestSecurityFeatures:
    """測試 app 實際的安全行為"""

    async def test_password_never_exposed_and_stored_as_bcrypt(
        self, async_client, isolated_db_manager, test_user
    ):
        session = await _register_and_login(async_client, test_user)
        profile = await async_client.get(
            "/api/auth/profile", headers=_bearer(session["access_token"])
        )

        for response in (session["register"], session["login"], session["me"], profile):
            assert not SENSITIVE_KEYS & _all_keys(response.json())

        db = await isolated_db_manager.get_database()
        stored = await db["users"].find_one({"username": test_user["username"]})
        assert "password" not in stored
        assert stored["hashed_password"].startswith("$2b$")
        assert test_user["password"] not in stored["hashed_password"]

    async def test_refresh_token_cannot_be_used_as_access_token(
        self, async_client, isolated_db_manager, test_user
    ):
        session = await _register_and_login(async_client, test_user)

        response = await async_client.get(
            "/api/auth/me", headers=_bearer(session["refresh_token"])
        )

        assert response.status_code == 401

    @pytest.mark.parametrize(
        "forge",
        [
            pytest.param(
                lambda claims: jwt.encode(
                    {**claims, "exp": 9999999999},
                    "attacker-controlled-secret-key-32-bytes!",
                    algorithm="HS256",
                ),
                id="wrong-secret",
            ),
            pytest.param(
                lambda claims: f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(claims)}.",
                id="alg-none",
            ),
            pytest.param(
                lambda claims: create_access_token(
                    claims, expires_delta=timedelta(seconds=-1)
                ),
                id="expired",
            ),
            pytest.param(
                lambda claims: create_access_token({"sub": claims["sub"]}),
                id="missing-user-id",
            ),
            pytest.param(
                lambda claims: create_access_token({"user_id": claims["user_id"]}),
                id="missing-sub",
            ),
        ],
    )
    async def test_forged_or_incomplete_tokens_rejected(
        self, async_client, isolated_db_manager, test_user, forge
    ):
        session = await _register_and_login(async_client, test_user)
        claims = {"sub": test_user["username"], "user_id": session["me"].json()["id"]}

        response = await async_client.get(
            "/api/auth/me", headers=_bearer(forge(claims))
        )

        assert response.status_code == 401

    async def test_valid_token_with_same_claims_is_accepted(
        self, async_client, isolated_db_manager, test_user
    ):
        """對照組：同樣的 claims 用正確的金鑰簽發時可以通過"""
        session = await _register_and_login(async_client, test_user)
        claims = {"sub": test_user["username"], "user_id": session["me"].json()["id"]}
        token = jwt.encode(
            {**claims, "exp": 9999999999},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )

        response = await async_client.get("/api/auth/me", headers=_bearer(token))

        assert response.status_code == 200

    async def test_security_headers_on_responses(self, async_client):
        response = await async_client.get("/")

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        # 非 HTTPS 不送 HSTS
        assert "Strict-Transport-Security" not in response.headers

    async def test_hsts_sent_behind_https_proxy(self, async_client):
        response = await async_client.get("/", headers={"X-Forwarded-Proto": "https"})

        assert response.headers["Strict-Transport-Security"].startswith(
            "max-age=31536000"
        )

    async def test_room_search_keyword_is_regex_escaped(
        self, async_client, isolated_db_manager, auth_headers
    ):
        for name in ("abc room", "a.c room"):
            created = await async_client.post(
                "/api/rooms/", json={"name": name}, headers=auth_headers
            )
            assert created.status_code == 201

        dot = await async_client.get(
            "/api/rooms", params={"search": "a.c"}, headers=auth_headers
        )
        assert dot.status_code == 200
        assert [room["name"] for room in dot.json()] == ["a.c room"]

        paren = await async_client.get(
            "/api/rooms", params={"search": "(("}, headers=auth_headers
        )
        assert paren.status_code == 200
        assert paren.json() == []
