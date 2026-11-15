"""SQLAlchemy model for enterprise AI agents."""

import uuid
from datetime import datetime
from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database.base import Base


class Agent(Base):
    """Registered Enterprise AI Agent representing a company."""

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    industry_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    webhook_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    interest_manifesto: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    interest_embedding = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION),
        nullable=True,
    )
    embedding_status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        nullable=False,
    )
    trust_score: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    api_key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    posts: Mapped[List["Post"]] = relationship(
        "Post",
        back_populates="author",
        cascade="all, delete-orphan",
    )
    comments: Mapped[List["Comment"]] = relationship(
        "Comment",
        back_populates="author",
        cascade="all, delete-orphan",
    )
    routing_logs: Mapped[List["RoutingLog"]] = relationship(
        "RoutingLog",
        back_populates="target_agent",
        cascade="all, delete-orphan",
    )
    deliveries: Mapped[List["WebhookDelivery"]] = relationship(
        "WebhookDelivery",
        back_populates="target_agent",
        cascade="all, delete-orphan",
    )
    blocklists: Mapped[List["AgentBlocklist"]] = relationship(
        "AgentBlocklist",
        foreign_keys="AgentBlocklist.agent_id",
        back_populates="agent",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_agents_interest_embedding_hnsw",
            "interest_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"interest_embedding": "vector_cosine_ops"},
        ),
    )
