"""Agent registration and management API router."""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_agent
from app.database.connection import get_db
from app.database.models.agent import Agent
from app.schemas.agent import (
    AgentCreate,
    AgentListResponse,
    AgentRegistrationResponse,
    AgentResponse,
    AgentUpdate,
)
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["Agents"])


def _to_agent_response(agent: Agent) -> AgentResponse:
    """Helper to convert Agent ORM entity to AgentResponse schema."""
    return AgentResponse(
        id=agent.id,
        company_name=agent.company_name,
        industry_category=agent.industry_category,
        webhook_url=agent.webhook_url,
        interest_manifesto=agent.interest_manifesto,
        embedding_status=agent.embedding_status,
        has_embedding=agent.interest_embedding is not None,
        trust_score=agent.trust_score,
        is_active=agent.is_active,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.post(
    "/register",
    response_model=AgentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new company AI agent",
)
def register_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db),
) -> AgentRegistrationResponse:
    """Register a new enterprise company agent.

    Returns the registered agent profile and an API key for authentication.
    The API key is returned ONLY once at registration.
    """
    service = AgentService(db)
    agent, plain_api_key = service.register_agent(payload)
    return AgentRegistrationResponse(
        agent=_to_agent_response(agent),
        api_key=plain_api_key,
        message="Agent registered successfully. Store your API key securely.",
    )


@router.get(
    "",
    response_model=AgentListResponse,
    summary="List registered enterprise AI agents",
)
def list_agents(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
) -> AgentListResponse:
    """Retrieve paginated list of registered agents."""
    service = AgentService(db)
    agents, total = service.list_agents(offset=offset, limit=limit, is_active=is_active)
    return AgentListResponse(
        agents=[_to_agent_response(a) for a in agents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Retrieve an agent by ID",
)
def get_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AgentResponse:
    """Retrieve detailed agent profile by UUID."""
    service = AgentService(db)
    agent = service.get_agent(agent_id)
    return _to_agent_response(agent)


@router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Update agent profile",
)
def update_agent(
    agent_id: uuid.UUID,
    payload: AgentUpdate,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """Update agent industry, webhook URL, or interest manifesto.

    Requires authentication as the agent being updated.
    """
    service = AgentService(db)
    updated = service.update_agent(agent_id, payload, current_agent)
    return _to_agent_response(updated)


@router.post(
    "/{agent_id}/activate",
    response_model=AgentResponse,
    summary="Activate agent account",
)
def activate_agent(
    agent_id: uuid.UUID,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """Activate an agent. Requires authenticated ownership."""
    service = AgentService(db)
    activated = service.activate_agent(agent_id, current_agent)
    return _to_agent_response(activated)


@router.post(
    "/{agent_id}/deactivate",
    response_model=AgentResponse,
    summary="Deactivate agent account",
)
def deactivate_agent(
    agent_id: uuid.UUID,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """Deactivate an agent. Requires authenticated ownership."""
    service = AgentService(db)
    deactivated = service.deactivate_agent(agent_id, current_agent)
    return _to_agent_response(deactivated)
