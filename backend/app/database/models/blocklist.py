"""SQLAlchemy model for agent exclusions, domain blocks, and industry restrictions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.agent import Agent


class AgentBlocklist(Base):
    """Configuration table for agent blocklists and excluded industry categories."""

    __tablename__ = "agent_blocklists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    blocked_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    blocked_industry: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
        back_populates="blocklists",
    )
    blocked_agent: Mapped[Optional["Agent"]] = relationship(
        "Agent",
        foreign_keys=[blocked_agent_id],
    )

    __table_args__ = (
        Index("ix_blocklist_agent_blocked", "agent_id", "blocked_agent_id"),
        Index("ix_blocklist_agent_industry", "agent_id", "blocked_industry"),
    )
