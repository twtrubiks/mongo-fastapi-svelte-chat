"""基礎測試"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
@pytest.mark.unit
async def test_health_check():
    """測試健康檢查端點"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "chatroom-api"
        assert data["version"] == "1.0.0"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_root_endpoint():
    """測試根端點"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "即時聊天室 API"
        assert data["status"] == "running"
