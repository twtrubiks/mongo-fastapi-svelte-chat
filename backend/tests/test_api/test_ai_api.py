"""AI 助理狀態 API 測試（經由完整路由、依賴注入與 middleware）"""

import pytest

from app.config import settings
from app.core.bot import BOT_USERNAME

FORM = {"Content-Type": "application/x-www-form-urlencoded"}


@pytest.fixture
async def auth_headers(async_client, isolated_db_manager) -> dict:
    password = "password123"
    register = await async_client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": password},
    )
    assert register.status_code == 201
    login = await async_client.post(
        "/api/auth/login",
        data={"username": "alice", "password": password},
        headers=FORM,
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
@pytest.mark.integration
class TestAIStatus:
    @pytest.mark.parametrize(
        ("provider", "nvidia_key", "google_key", "enabled"),
        [
            ("nvidia", "nv-key", None, True),
            ("nvidia", None, "g-key", False),
            ("gemini", None, "g-key", True),
            ("gemini", "nv-key", None, False),
        ],
    )
    async def test_enabled_when_current_provider_has_key(
        self,
        async_client,
        auth_headers,
        monkeypatch,
        provider,
        nvidia_key,
        google_key,
        enabled,
    ):
        monkeypatch.setattr(settings, "AI_PROVIDER", provider)
        monkeypatch.setattr(settings, "NVIDIA_API_KEY", nvidia_key)
        monkeypatch.setattr(settings, "GOOGLE_API_KEY", google_key)

        response = await async_client.get("/api/ai/status", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == {"enabled": enabled, "bot_username": BOT_USERNAME}

    async def test_requires_login(self, async_client):
        response = await async_client.get("/api/ai/status")

        assert response.status_code == 401
