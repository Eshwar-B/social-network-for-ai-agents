"""Rate limiting middleware and dependency using sliding window counters."""

import time
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import logger


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter tracking request timestamps."""

    def __init__(self, requests_per_minute: int = 120) -> None:
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60.0
        self._requests: Dict[str, List[float]] = {}

    def is_allowed(self, client_key: str) -> Tuple[bool, int, float]:
        """Check if request from client_key is allowed.

        Returns:
            Tuple of (is_allowed, remaining_requests, reset_after_seconds)
        """
        now = time.time()
        window_start = now - self.window_seconds

        timestamps = self._requests.get(client_key, [])
        # Evict timestamps outside sliding window
        valid_timestamps = [t for t in timestamps if t > window_start]

        if len(valid_timestamps) >= self.requests_per_minute:
            oldest_ts = valid_timestamps[0]
            reset_after = max(1.0, (oldest_ts + self.window_seconds) - now)
            self._requests[client_key] = valid_timestamps
            return False, 0, reset_after

        valid_timestamps.append(now)
        self._requests[client_key] = valid_timestamps
        remaining = self.requests_per_minute - len(valid_timestamps)
        return True, remaining, self.window_seconds

    def reset(self) -> None:
        """Clear all rate limit buckets (useful for tests)."""
        self._requests.clear()


_rate_limiter = SlidingWindowRateLimiter(requests_per_minute=120)


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Return shared sliding window rate limiter instance."""
    return _rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware enforcing request rate limits per client."""

    def __init__(self, app, limiter: Optional[SlidingWindowRateLimiter] = None) -> None:
        super().__init__(app)
        self.limiter = limiter or _rate_limiter

    async def dispatch(self, request: Request, call_next):
        # Exclude root docs and health checks from aggressive rate limiting
        if request.url.path in ("/", "/docs", "/openapi.json", "/api/v1/health"):
            return await call_next(request)

        # Identify client by API Key header if present, otherwise by IP
        client_key = (
            request.headers.get("X-Agent-API-Key")
            or request.headers.get("Authorization")
            or request.client.host if request.client else "unknown_client"
        )

        allowed, remaining, reset_after = self.limiter.is_allowed(client_key)
        if not allowed:
            logger.warning("Rate limit exceeded for client %s on %s", client_key, request.url.path)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down your requests.",
                headers={"Retry-After": str(int(reset_after))},
            )

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_after))
        return response
