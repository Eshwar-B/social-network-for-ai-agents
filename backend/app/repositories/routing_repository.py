"""Repository for routing logs and webhook delivery records."""

from typing import List, Optional
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models.delivery import WebhookDelivery
from app.database.models.routing_log import RoutingLog


class RoutingRepository:
    """Handles database persistence and retrieval for routing decisions and delivery attempts."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def save_routing_logs(self, logs: List[RoutingLog]) -> List[RoutingLog]:
        """Save a batch of routing log records."""
        self.db.add_all(logs)
        self.db.commit()
        return logs

    def delete_logs_for_post(self, post_id: uuid.UUID) -> None:
        """Delete existing routing logs for a post to ensure idempotent execution."""
        self.db.execute(delete(RoutingLog).where(RoutingLog.post_id == post_id))
        self.db.commit()

    def get_logs_for_post(self, post_id: uuid.UUID) -> List[RoutingLog]:
        """Retrieve all routing decisions for a specific post."""
        return list(
            self.db.execute(
                select(RoutingLog).where(RoutingLog.post_id == post_id)
            ).scalars().all()
        )

    def get_qualified_logs_for_post(self, post_id: uuid.UUID) -> List[RoutingLog]:
        """Retrieve only qualified recipient logs for a specific post."""
        return list(
            self.db.execute(
                select(RoutingLog).where(
                    RoutingLog.post_id == post_id,
                    RoutingLog.status == "QUALIFIED",
                )
            ).scalars().all()
        )

    def get_logs_for_agent(
        self,
        agent_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> List[RoutingLog]:
        """Retrieve routing evaluations where this agent was targeted."""
        return list(
            self.db.execute(
                select(RoutingLog)
                .where(RoutingLog.target_agent_id == agent_id)
                .order_by(RoutingLog.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).scalars().all()
        )

    def create_delivery(self, delivery: WebhookDelivery) -> WebhookDelivery:
        """Record an initial webhook delivery attempt."""
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        return delivery

    def update_delivery(self, delivery: WebhookDelivery, updates: dict) -> WebhookDelivery:
        """Update status, attempts, or response code for a delivery record."""
        for key, value in updates.items():
            setattr(delivery, key, value)
        self.db.commit()
        self.db.refresh(delivery)
        return delivery

    def get_deliveries_for_post(self, post_id: uuid.UUID) -> List[WebhookDelivery]:
        """Retrieve all webhook deliveries for a post."""
        return list(
            self.db.execute(
                select(WebhookDelivery).where(WebhookDelivery.post_id == post_id)
            ).scalars().all()
        )

    def get_deliveries_for_agent(self, agent_id: uuid.UUID) -> List[WebhookDelivery]:
        """Retrieve all webhook delivery attempts for an agent."""
        return list(
            self.db.execute(
                select(WebhookDelivery).where(WebhookDelivery.target_agent_id == agent_id)
            ).scalars().all()
        )
