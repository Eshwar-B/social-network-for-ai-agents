"""Redis Stream consumer worker for asynchronous post event processing."""

import asyncio
import json
from typing import Any, Callable, Dict, Optional
import uuid

import redis.exceptions
from sqlalchemy import select

from app.config import settings
from app.core.logging import logger
from app.core.redis import get_redis_client
from app.database.connection import session_factory
from app.database.models.event import EventProcessing
from app.database.models.post import Post
from app.services.routing_service import RoutingService


class StreamConsumer:
    """Consumer group worker processing post events from Redis Streams."""

    def __init__(
        self,
        stream_key: Optional[str] = None,
        consumer_group: Optional[str] = None,
        consumer_name: Optional[str] = None,
        routing_handler: Optional[Callable[[uuid.UUID], Any]] = None,
        dispatch_notifications: bool = False,
    ) -> None:
        self.stream_key = stream_key or settings.REDIS_STREAM_KEY
        self.group = consumer_group or settings.REDIS_CONSUMER_GROUP
        self.consumer_name = consumer_name or settings.REDIS_CONSUMER_NAME
        self.routing_handler = routing_handler
        self.dispatch_notifications = dispatch_notifications
        self.is_running = False

    async def initialize_group(self) -> None:
        """Create Redis consumer group if it does not already exist."""
        client = get_redis_client()
        try:
            await client.xgroup_create(
                name=self.stream_key,
                groupname=self.group,
                id="0",
                mkstream=True,
            )
            logger.info(
                "Created Redis consumer group '%s' on stream '%s'",
                self.group,
                self.stream_key,
            )
        except redis.exceptions.ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                logger.debug(
                    "Consumer group '%s' already exists on stream '%s'",
                    self.group,
                    self.stream_key,
                )
            else:
                logger.error("Failed to create consumer group: %s", exc)
                raise

    async def process_event(
        self,
        message_id: str,
        event_type: str,
        payload_data: Dict[str, Any],
    ) -> bool:
        """Process a single event with idempotency and authoritative DB lookups."""
        event_id = payload_data.get("event_id")
        post_id_str = payload_data.get("post_id")

        if not post_id_str:
            logger.warning("Event %s missing post_id, skipping", message_id)
            return True

        post_id = uuid.UUID(post_id_str)

        with session_factory() as db:
            # 1. Authoritative lookup: check if post exists
            post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
            if not post:
                logger.warning("Post '%s' not found in database for event '%s'", post_id, event_id)
                return True

            # 2. Idempotency check via EventProcessing table
            event_record = None
            if event_id:
                event_record = db.execute(
                    select(EventProcessing).where(EventProcessing.event_id == event_id)
                ).scalar_one_or_none()

            if event_record and event_record.status == "COMPLETED":
                logger.info("Event '%s' already completed. Idempotency enforced.", event_id)
                return True

            if event_record:
                event_record.status = "PROCESSING"
                event_record.attempt_count += 1
                db.commit()

            # 3. Execute routing handler
            try:
                if self.routing_handler:
                    await self.routing_handler(post_id)
                else:
                    routing_svc = RoutingService(db=db)
                    await routing_svc.route_post(post_id, db_session=db)
                    logger.info("Executed 3-stage routing service for post '%s'", post_id)

                    if self.dispatch_notifications:
                        from app.workers.notification_worker import NotificationWorker
                        worker = NotificationWorker()
                        await worker.dispatch_for_post(post_id, db_session=db)
                        logger.info("Dispatched webhook notifications for post '%s'", post_id)

                # 4. Mark completed
                post.status = "ROUTED"
                if event_record:
                    event_record.status = "COMPLETED"
                db.commit()
                logger.info("Successfully processed event '%s' for post '%s'", event_id, post_id)
                return True

            except Exception as exc:
                logger.error("Failed processing event '%s' for post '%s': %s", event_id, post_id, exc)
                if event_record:
                    event_record.status = "FAILED"
                    event_record.error_message = str(exc)
                    db.commit()
                return False

    async def read_and_process_pending(self, count: int = 10) -> int:
        """Recover and process pending messages (PEL) assigned to this consumer."""
        client = get_redis_client()
        processed_count = 0
        try:
            # ID "0" reads pending messages assigned to this consumer
            pending_messages = await client.xreadgroup(
                groupname=self.group,
                consumername=self.consumer_name,
                streams={self.stream_key: "0"},
                count=count,
            )
            for stream, messages in pending_messages:
                for msg_id, fields in messages:
                    # If empty fields, message might have been claimed/acked
                    if not fields:
                        continue
                    try:
                        event_type = fields.get("event_type", "unknown")
                        payload = json.loads(fields.get("payload", "{}"))
                    except Exception as parse_err:
                        logger.error("Corrupted pending message %s: %s; acknowledging poison pill", msg_id, parse_err)
                        await client.xack(self.stream_key, self.group, msg_id)
                        processed_count += 1
                        continue

                    success = await self.process_event(msg_id, event_type, payload)
                    if success:
                        await client.xack(self.stream_key, self.group, msg_id)
                        processed_count += 1
        except Exception as exc:
            logger.error("Error reading pending messages: %s", exc)
        return processed_count

    async def read_and_process_new(self, count: int = 10, block_ms: int = 2000) -> int:
        """Read and process new messages using the '>' special ID."""
        client = get_redis_client()
        processed_count = 0
        try:
            new_messages = await client.xreadgroup(
                groupname=self.group,
                consumername=self.consumer_name,
                streams={self.stream_key: ">"},
                count=count,
                block=block_ms,
            )
            for stream, messages in new_messages:
                for msg_id, fields in messages:
                    try:
                        event_type = fields.get("event_type", "unknown")
                        payload = json.loads(fields.get("payload", "{}"))
                    except Exception as parse_err:
                        logger.error("Corrupted message %s: %s; acknowledging poison pill", msg_id, parse_err)
                        await client.xack(self.stream_key, self.group, msg_id)
                        processed_count += 1
                        continue

                    success = await self.process_event(msg_id, event_type, payload)
                    if success:
                        await client.xack(self.stream_key, self.group, msg_id)
                        processed_count += 1
        except Exception as exc:
            logger.error("Error reading new messages: %s", exc)
        return processed_count

    async def run_once(self) -> int:
        """Convenience method for tests: initialize, recover pending, and read new events."""
        await self.initialize_group()
        recovered = await self.read_and_process_pending()
        new_count = await self.read_and_process_new(count=10, block_ms=500)
        return recovered + new_count

    async def start(self) -> None:
        """Start infinite background consumer loop."""
        self.is_running = True
        await self.initialize_group()
        logger.info(
            "Started background stream consumer '%s' (group: '%s')",
            self.consumer_name,
            self.group,
        )

        # First recover pending
        await self.read_and_process_pending()

        while self.is_running:
            try:
                await self.read_and_process_new(count=10, block_ms=2000)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Consumer loop exception: %s", exc)
                await asyncio.sleep(1.0)

    def stop(self) -> None:
        """Stop consumer loop."""
        self.is_running = False
        logger.info("Stream consumer '%s' stop requested", self.consumer_name)


if __name__ == "__main__":
    import signal
    from app.core.logging import configure_logging

    configure_logging()
    logger.info("Initializing Asama Stream Consumer worker process...")
    consumer = StreamConsumer(dispatch_notifications=True)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_signal(*args: Any) -> None:
        logger.info("Received termination signal, shutting down consumer...")
        consumer.stop()

    try:
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
    except (ValueError, AttributeError):
        pass

    try:
        loop.run_until_complete(consumer.start())
    except KeyboardInterrupt:
        logger.info("Consumer interrupted by keyboard.")
    finally:
        loop.close()

