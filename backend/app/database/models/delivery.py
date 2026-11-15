"""SQLAlchemy model for webhook notification delivery attempts and audit logs."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.agent import Agent
    from app.database.models.post import Post


class WebhookDelivery(Base):
    """Record of webhook notification delivery attempts to selected agents."""

    __tablename__ = "webhook_deliveries"

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
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        nullable=False,
        index=True,
    )
    http_response_code: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    error_details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    payload = mapped_column(
        JSONB,
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

    @property
    def response_status_code(self) -> Optional[int]:
        """Convenience alias for http_response_code."""
        return self.http_response_code

    @response_status_code.setter
    def response_status_code(self, val: Optional[int]) -> None:
        self.http_response_code = val

    @property
    def error_message(self) -> Optional[str]:
        """Convenience alias for error_details."""
        return self.error_details

    @error_message.setter
    def error_message(self, val: Optional[str]) -> None:
        self.error_details = val

    # Relationships
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="deliveries",
    )
    target_agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="deliveries",
    )

    __table_args__ = (
        Index("ix_deliveries_post_target", "post_id", "target_agent_id"),
    )
