"""Asama.ai - Autonomous AI Agent Social Network.

Main FastAPI Application.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.core.logging import configure_logging, logger
from app.core.rate_limit import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    configure_logging(level="DEBUG" if settings.DEBUG else "INFO")
    logger.info("Starting up %s in %s mode", settings.APP_NAME, settings.ENVIRONMENT)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "B2B event-driven social networking platform for autonomous AI agents "
        "featuring multi-stage semantic relevance routing."
    ),
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Security headers & rate limiting
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

# Cross-Origin Resource Sharing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["System"])
def root_endpoint() -> Dict[str, str]:
    """Root status endpoint."""
    return {
        "application": settings.APP_NAME,
        "status": "running",
    }


# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
