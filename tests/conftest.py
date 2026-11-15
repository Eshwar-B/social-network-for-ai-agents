"""Pytest configuration, shared fixtures, and lifecycle teardown."""

from typing import AsyncGenerator, Generator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from app.core.redis import close_redis_client
from app.database.connection import session_factory
from app.main import app


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session for tests."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP async test client for FastAPI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest.fixture(autouse=True)
async def cleanup_redis_connections():
    """Ensure Redis client connections are closed cleanly after each async test."""
    yield
    try:
        await close_redis_client()
    except Exception:
        pass
