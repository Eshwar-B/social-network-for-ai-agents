"""Background worker for dispatching webhook notifications to qualified agents."""

import asyncio
from typing import List, Optional
import uuid
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.delivery import WebhookDelivery
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog
from app.services.notification_service import NotificationService


class NotificationWorker:
    """Dispatches webhook notifications asynchronously to selected agents."""

    def __init__(
        self,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self.service = notification_service or NotificationService()

    async def dispatch_for_post(
        self,
        post_id: uuid.UUID,
        db_session: Optional[Session] = None,
        custom_client: Optional[httpx.AsyncClient] = None,
    ) -> List[WebhookDelivery]:
        """Fetch all qualified recipients for a post and deliver signed webhooks."""
        db = db_session
        if not db:
            with session_factory() as local_db:
                return await self._execute_dispatch(post_id, local_db, custom_client)
        return await self._execute_dispatch(post_id, db, custom_client)

    async def _execute_dispatch(
        self,
        post_id: uuid.UUID,
        db: Session,
        custom_client: Optional[httpx.AsyncClient] = None,
    ) -> List[WebhookDelivery]:
        post = db.get(Post, post_id)
        if not post:
            logger.error("Post %s not found for notification dispatch", post_id)
            return []

        qualified_logs = list(
            db.execute(
                select(RoutingLog).where(
                    RoutingLog.post_id == post_id,
                    RoutingLog.status == "QUALIFIED",
                )
            ).scalars().all()
        )

        logger.info(
            "Dispatching notifications for post %s to %d qualified agents",
            post_id,
            len(qualified_logs),
        )

        deliveries: List[WebhookDelivery] = []
        for log in qualified_logs:
            agent = db.get(Agent, log.target_agent_id)
            if not agent:
                continue

            delivery = await self.service.deliver_webhook(
                target_agent=agent,
                post=post,
                vector_score=float(log.vector_score or 0.0),
                rerank_score=float(log.rerank_score or 0.0),
                final_score=float(log.final_score or 0.0),
                db_session=db,
                custom_client=custom_client,
            )
            deliveries.append(delivery)

        return deliveries
