"""SQLAlchemy model for routing decisions and audit logs."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class RoutingLog(Base):
    """Audit log of routing evaluations, scores, and recipient selection decisions."""

    __tablename__ = "routing_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vector_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    rerank_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    final_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    decision_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="routing_logs",
    )
    target_agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="routing_logs",
    )

    __table_args__ = (
        Index("ix_routing_logs_post_target", "post_id", "target_agent_id"),
    )
