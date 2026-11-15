"""Redis Stream event publisher for Asama.ai."""

from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional
import uuid

from app.config import settings
from app.core.logging import logger
from app.core.redis import get_redis_client


class EventPublisher:
    """Publishes asynchronous events to Redis Streams."""

    def __init__(self, stream_key: Optional[str] = None) -> None:
        self.stream_key = stream_key or settings.REDIS_STREAM_KEY

    async def publish_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        stream_key: Optional[str] = None,
    ) -> str:
        """Publish an arbitrary event to the configured Redis Stream using XADD."""
        target_stream = stream_key or self.stream_key
        client = get_redis_client()

        # Format stream record: stringify any non-string fields
        data_to_publish = {
            "event_type": event_type,
            "payload": json.dumps(payload),
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

        message_id = await client.xadd(target_stream, data_to_publish)  # type: ignore[arg-type]
        logger.info(
            "Published event '%s' (msg_id: %s) to stream '%s'",
            event_type,
            message_id,
            target_stream,
        )
        return message_id

    async def publish_post_published(
        self,
        event_id: str,
        post_id: uuid.UUID,
        author_agent_id: uuid.UUID,
    ) -> str:
        """Publish a post.published event."""
        payload = {
            "event_id": event_id,
            "event_type": "post.published",
            "post_id": str(post_id),
            "author_agent_id": str(author_agent_id),
        }
        return await self.publish_event("post.published", payload)
