"""Notification service for dispatching signed webhook events with retry and circuit breaker."""

import asyncio
import json
import time
from typing import Dict, List, Optional
import uuid
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import logger
from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.delivery import WebhookDelivery
from app.database.models.post import Post
from app.repositories.routing_repository import RoutingRepository
from app.utils.hmac_utils import format_signature_header, generate_webhook_signature, is_safe_webhook_url


class CircuitBreaker:
    """In-memory circuit breaker preventing calls to persistently failing endpoints."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout_sec: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failure_counts: Dict[str, int] = {}
        self.tripped_at: Dict[str, float] = {}

    def is_available(self, endpoint_key: str) -> bool:
        """Check if circuit is open (blocked) or closed (available)."""
        now = time.time()
        if endpoint_key in self.tripped_at:
            if now - self.tripped_at[endpoint_key] > self.recovery_timeout_sec:
                # Half-open: recovery timeout elapsed, permit trial attempt
                del self.tripped_at[endpoint_key]
                self.failure_counts[endpoint_key] = 0
                return True
            return False
        return True

    def record_success(self, endpoint_key: str) -> None:
        """Reset consecutive failures on success."""
        self.failure_counts.pop(endpoint_key, None)
        self.tripped_at.pop(endpoint_key, None)

    def record_failure(self, endpoint_key: str) -> bool:
        """Record a failure; returns True if breaker just tripped."""
        count = self.failure_counts.get(endpoint_key, 0) + 1
        self.failure_counts[endpoint_key] = count
        if count >= self.failure_threshold:
            self.tripped_at[endpoint_key] = time.time()
            logger.warning(
                "Circuit breaker tripped for endpoint '%s' after %d consecutive failures",
                endpoint_key,
                count,
            )
            return True
        return False


_global_circuit_breaker = CircuitBreaker()


class NotificationService:
    """Orchestrates secure webhook delivery to qualified agents."""

    def __init__(
        self,
        db: Optional[Session] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        max_attempts: int = 3,
        initial_backoff_sec: float = 0.1,
    ) -> None:
        self._db = db
        self.breaker = circuit_breaker or _global_circuit_breaker
        self.max_attempts = max_attempts
        self.initial_backoff_sec = initial_backoff_sec

    def build_webhook_payload(
        self,
        post: Post,
        recipient: Agent,
        vector_score: float,
        rerank_score: float,
        final_score: float,
    ) -> dict:
        """Construct standard Asama.ai webhook payload."""
        author_data = {
            "id": str(post.author.id) if post.author else str(post.author_agent_id),
            "company_name": post.author.company_name if post.author else "Unknown",
            "industry_category": post.author.industry_category if post.author else "Unknown",
        }
        return {
            "event": "post.matched",
            "post_id": str(post.id),
            "post": {
                "id": str(post.id),
                "title": post.title,
                "content": post.content,
                "status": post.status,
                "author": author_data,
                "created_at": post.created_at.isoformat() if post.created_at else None,
            },
            "recipient": {
                "id": str(recipient.id),
                "company_name": recipient.company_name,
                "industry_category": recipient.industry_category,
            },
            "relevance": {
                "vector_score": round(vector_score, 4),
                "rerank_score": round(rerank_score, 4),
                "final_score": round(final_score, 4),
            },
            "timestamp": int(time.time()),
        }

    async def deliver_webhook(
        self,
        target_agent: Agent,
        post: Post,
        vector_score: float,
        rerank_score: float,
        final_score: float,
        db_session: Optional[Session] = None,
        custom_client: Optional[httpx.AsyncClient] = None,
    ) -> WebhookDelivery:
        """Deliver a signed webhook with retry and SSRF protection."""
        db = db_session or self._db
        if not db:
            with session_factory() as local_db:
                return await self._execute_delivery(
                    target_agent, post, vector_score, rerank_score, final_score, local_db, custom_client
                )
        return await self._execute_delivery(
            target_agent, post, vector_score, rerank_score, final_score, db, custom_client
        )

    async def _execute_delivery(
        self,
        target_agent: Agent,
        post: Post,
        vector_score: float,
        rerank_score: float,
        final_score: float,
        db: Session,
        custom_client: Optional[httpx.AsyncClient] = None,
    ) -> WebhookDelivery:
        repo = RoutingRepository(db)
        webhook_url = target_agent.webhook_url
        endpoint_key = webhook_url

        # 1. Create delivery record in database
        delivery = WebhookDelivery(
            post_id=post.id,
            target_agent_id=target_agent.id,
            attempt_number=0,
            status="PENDING",
        )
        delivery = repo.create_delivery(delivery)

        # 2. SSRF check
        if not is_safe_webhook_url(webhook_url, allow_localhost=True):
            logger.warning("Blocked unsafe webhook destination: %s", webhook_url)
            repo.update_delivery(
                delivery,
                {
                    "status": "FAILED",
                    "error_message": "Blocked unsafe destination (SSRF protection)",
                    "attempt_number": 1,
                },
            )
            return delivery

        # 3. Circuit breaker check
        if not self.breaker.is_available(endpoint_key):
            logger.warning("Circuit open for %s; aborting delivery", endpoint_key)
            repo.update_delivery(
                delivery,
                {
                    "status": "CIRCUIT_OPEN",
                    "error_message": "Circuit breaker open for endpoint",
                    "attempt_number": 1,
                },
            )
            return delivery

        # 4. Construct payload and sign with HMAC
        payload_data = self.build_webhook_payload(
            post=post,
            recipient=target_agent,
            vector_score=vector_score,
            rerank_score=rerank_score,
            final_score=final_score,
        )
        payload_bytes = json.dumps(payload_data).encode("utf-8")
        secret = target_agent.api_key_hash or settings.HMAC_SECRET_KEY
        sig_hex, timestamp = generate_webhook_signature(payload_bytes, secret)
        sig_header = format_signature_header(sig_hex, timestamp)

        headers = {
            "Content-Type": "application/json",
            "X-Asama-Signature": sig_header,
            "X-Asama-Event": "post.matched",
            "X-Asama-Delivery-Id": str(delivery.id),
        }

        # 5. Delivery attempt loop with exponential backoff
        client = custom_client or httpx.AsyncClient(timeout=10.0)
        close_client = custom_client is None
        backoff = self.initial_backoff_sec
        success = False
        last_error = ""
        status_code = None

        try:
            for attempt in range(1, self.max_attempts + 1):
                delivery.attempt_number = attempt
                try:
                    resp = await client.post(webhook_url, content=payload_bytes, headers=headers)
                    status_code = resp.status_code
                    delivery.response_status_code = status_code
                    if 200 <= status_code < 300:
                        success = True
                        delivery.status = "SUCCESS"
                        delivery.error_message = None
                        self.breaker.record_success(endpoint_key)
                        logger.info(
                            "Delivered notification for post %s to agent %s (%s) on attempt %d",
                            post.id,
                            target_agent.company_name,
                            webhook_url,
                            attempt,
                        )
                        break
                    else:
                        last_error = f"HTTP status {status_code}"
                        self.breaker.record_failure(endpoint_key)
                except Exception as exc:
                    last_error = str(exc)
                    self.breaker.record_failure(endpoint_key)

                if attempt < self.max_attempts:
                    await asyncio.sleep(backoff)
                    backoff *= 2.0

            if not success:
                delivery.status = "FAILED"
                delivery.error_message = last_error
                logger.warning(
                    "Failed delivery to agent %s (%s) after %d attempts: %s",
                    target_agent.company_name,
                    webhook_url,
                    self.max_attempts,
                    last_error,
                )

            repo.update_delivery(
                delivery,
                {
                    "status": delivery.status,
                    "attempt_number": delivery.attempt_number,
                    "response_status_code": delivery.response_status_code,
                    "error_message": delivery.error_message,
                },
            )
            return delivery
        finally:
            if close_client:
                await client.aclose()
