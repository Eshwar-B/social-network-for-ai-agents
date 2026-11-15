"""Redis connection pool and client lifecycle management."""

import asyncio
from typing import Optional
import redis.asyncio as aioredis

from app.config import settings
from app.core.logging import logger

_redis_client: Optional[aioredis.Redis] = None
_client_loop: Optional[asyncio.AbstractEventLoop] = None


def get_redis_client() -> aioredis.Redis:
    """Return asynchronous Redis client bound to the current running event loop."""
    global _redis_client, _client_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _redis_client is None or _client_loop != current_loop:
        _client_loop = current_loop
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def close_redis_client() -> None:
    """Close active Redis client connection pool."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Closed Redis connection pool.")


async def check_redis_connection() -> bool:
    """Check connectivity to Redis server."""
    try:
        client = get_redis_client()
        pong = await client.ping()
        logger.info("Redis health check: status=%s", "healthy" if pong else "unhealthy")
        return bool(pong)
    except Exception as exc:
        logger.error("Redis connection check failed: %s", exc)
        return False
