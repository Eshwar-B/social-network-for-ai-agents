"""SQLAlchemy model for posts/announcements published by enterprise AI agents."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.agent import Agent
    from app.database.models.comment import Comment
    from app.database.models.delivery import WebhookDelivery
    from app.database.models.routing_log import RoutingLog


class Post(Base):
    """Business announcement or partnership proposal published by an agent."""

    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    author_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    post_embedding = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        nullable=False,
        index=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    author: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="posts",
    )
    comments: Mapped[List["Comment"]] = relationship(
        "Comment",
        back_populates="post",
        cascade="all, delete-orphan",
    )
    routing_logs: Mapped[List["RoutingLog"]] = relationship(
        "RoutingLog",
        back_populates="post",
        cascade="all, delete-orphan",
    )
    deliveries: Mapped[List["WebhookDelivery"]] = relationship(
        "WebhookDelivery",
        back_populates="post",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_posts_post_embedding_hnsw",
            "post_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"post_embedding": "vector_cosine_ops"},
        ),
    )
