"""Repository for Agent database operations."""

from typing import List, Optional, Tuple
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.agent import Agent


class AgentRepository:
    """Encapsulates data access operations for Agent entities."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, agent: Agent) -> Agent:
        """Persist a new Agent."""
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_by_id(self, agent_id: uuid.UUID) -> Optional[Agent]:
        """Retrieve an agent by primary UUID."""
        return self.db.execute(
            select(Agent).where(Agent.id == agent_id)
        ).scalar_one_or_none()

    def get_by_company_name(self, company_name: str) -> Optional[Agent]:
        """Retrieve an agent by unique company name (case-insensitive)."""
        return self.db.execute(
            select(Agent).where(func.lower(Agent.company_name) == company_name.strip().lower())
        ).scalar_one_or_none()

    def get_by_api_key_hash(self, key_hash: str) -> Optional[Agent]:
        """Retrieve an agent by hashed API key."""
        return self.db.execute(
            select(Agent).where(Agent.api_key_hash == key_hash)
        ).scalar_one_or_none()

    def list(
        self,
        offset: int = 0,
        limit: int = 50,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[Agent], int]:
        """List agents with pagination and optional active filter."""
        query = select(Agent)
        count_query = select(func.count(Agent.id))

        if is_active is not None:
            query = query.where(Agent.is_active == is_active)
            count_query = count_query.where(Agent.is_active == is_active)

        total = self.db.execute(count_query).scalar() or 0
        agents = (
            self.db.execute(
                query.order_by(Agent.created_at.desc()).offset(offset).limit(limit)
            )
            .scalars()
            .all()
        )
        return list(agents), total

    def update(self, agent: Agent, update_dict: dict) -> Agent:
        """Update agent fields and persist changes."""
        for field, value in update_dict.items():
            if value is not None and hasattr(agent, field):
                setattr(agent, field, value)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def set_active_status(self, agent: Agent, is_active: bool) -> Agent:
        """Set agent active or inactive status."""
        agent.is_active = is_active
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def update_embedding(
        self,
        agent: Agent,
        embedding: List[float],
        status: str = "COMPLETED",
    ) -> Agent:
        """Save regenerated vector embedding and status."""
        agent.interest_embedding = embedding
        agent.embedding_status = status
        self.db.commit()
        self.db.refresh(agent)
        return agent
