"""Main API Router for Asama.ai."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.agents import router as agents_router
from app.api.posts import router as posts_router


class HealthResponse(BaseModel):
    status: str = "healthy"


api_router = APIRouter()

# Register endpoint sub-routers
api_router.include_router(agents_router)
api_router.include_router(posts_router)


@api_router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """Return health status of the application."""
    return HealthResponse(status="healthy")
