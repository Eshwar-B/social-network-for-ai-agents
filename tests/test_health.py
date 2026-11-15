"""Tests for application health and root endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify that root endpoint returns application name and running status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "Asama.ai"
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify that /api/v1/health endpoint returns healthy status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_settings_load():
    """Verify configuration settings are properly initialized."""
    assert settings.APP_NAME == "Asama.ai"
    assert settings.RELEVANCE_THRESHOLD == 0.75
    assert settings.MAX_RECIPIENTS == 5
    assert settings.EMBEDDING_DIMENSION == 1536
