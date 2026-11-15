"""Service layer handling Agent business rules and workflows."""

from typing import List, Optional, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.security import generate_agent_api_key, hash_api_key
from app.database.models.agent import Agent
from app.repositories.agent_repository import AgentRepository
from app.schemas.agent import AgentCreate, AgentUpdate


class AgentService:
    """Manages agent registration, profile management, and state transitions."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AgentRepository(db)

    def register_agent(self, data: AgentCreate) -> Tuple[Agent, str]:
        """Register a new enterprise company agent."""
        existing = self.repo.get_by_company_name(data.company_name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An agent for company '{data.company_name}' is already registered.",
            )

        plain_api_key = generate_agent_api_key()
        key_hash = hash_api_key(plain_api_key)

        agent = Agent(
            company_name=data.company_name.strip(),
            industry_category=data.industry_category.strip(),
            webhook_url=data.webhook_url.strip(),
            interest_manifesto=data.interest_manifesto.strip(),
            embedding_status="PENDING",
            trust_score=1.0,
            is_active=True,
            api_key_hash=key_hash,
        )
        created_agent = self.repo.create(agent)
        logger.info(
            "Registered new agent for company '%s' (ID: %s)",
            created_agent.company_name,
            created_agent.id,
        )
        return created_agent, plain_api_key

    def get_agent(self, agent_id: uuid.UUID) -> Agent:
        """Retrieve agent by UUID, raising 404 if not found."""
        agent = self.repo.get_by_id(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent with ID '{agent_id}' was not found.",
            )
        return agent

    def list_agents(
        self,
        offset: int = 0,
        limit: int = 50,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[Agent], int]:
        """List registered agents with pagination."""
        return self.repo.list(offset=offset, limit=limit, is_active=is_active)

    def update_agent(
        self,
        agent_id: uuid.UUID,
        data: AgentUpdate,
        current_agent: Agent,
    ) -> Agent:
        """Update an agent profile, ensuring authenticated ownership."""
        if current_agent.id != agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update another agent's profile.",
            )

        agent = self.get_agent(agent_id)
        update_dict = data.model_dump(exclude_unset=True)

        # If manifesto changed, mark embedding status as pending regeneration
        if "interest_manifesto" in update_dict and update_dict["interest_manifesto"]:
            update_dict["embedding_status"] = "PENDING"

        updated = self.repo.update(agent, update_dict)
        logger.info("Updated profile for agent '%s' (ID: %s)", updated.company_name, updated.id)
        return updated

    def activate_agent(self, agent_id: uuid.UUID, current_agent: Agent) -> Agent:
        """Activate an agent account."""
        if current_agent.id != agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to activate another agent's profile.",
            )
        agent = self.get_agent(agent_id)
        return self.repo.set_active_status(agent, is_active=True)

    def deactivate_agent(self, agent_id: uuid.UUID, current_agent: Agent) -> Agent:
        """Deactivate an agent account."""
        if current_agent.id != agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to deactivate another agent's profile.",
            )
        agent = self.get_agent(agent_id)
        return self.repo.set_active_status(agent, is_active=False)
