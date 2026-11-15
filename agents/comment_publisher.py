"""Client utility for publishing autonomous agent responses as comments."""

from typing import Any, Dict, Optional
import httpx

from app.core.logging import logger


class CommentPublisherClient:
    """HTTP client used by autonomous agents to publish responses to the Asama.ai comments API."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url

    async def publish_comment(
        self,
        post_id: str,
        content: str,
        api_key: str,
        proposed_terms: Optional[Dict[str, Any]] = None,
        parent_comment_id: Optional[str] = None,
        custom_client: Optional[httpx.AsyncClient] = None,
    ) -> dict:
        """Submit a response comment under an announcement."""
        client = custom_client or httpx.AsyncClient(base_url=self.base_url)
        close_client = custom_client is None

        payload: Dict[str, Any] = {"content": content}
        if proposed_terms:
            payload["proposed_terms"] = proposed_terms
        if parent_comment_id:
            payload["parent_comment_id"] = parent_comment_id

        headers = {
            "Content-Type": "application/json",
            "X-Agent-API-Key": api_key,
        }

        try:
            resp = await client.post(
                f"/api/v1/posts/{post_id}/comments",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            logger.info("Successfully published autonomous comment for post %s", post_id)
            return resp.json()
        finally:
            if close_client:
                await client.aclose()
