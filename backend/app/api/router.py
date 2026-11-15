"""Main API Router for Asama.ai."""

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "healthy"


api_router = APIRouter()


@api_router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """Return health status of the application."""
    return HealthResponse(status="healthy")
