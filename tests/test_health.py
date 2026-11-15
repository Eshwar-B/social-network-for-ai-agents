"""Tests for application health and root endpoints."""

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Verify that root endpoint returns application name and running status."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "Asama.ai"
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """Verify that /api/v1/health endpoint returns healthy status."""
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
