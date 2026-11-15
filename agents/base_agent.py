"""Base autonomous company agent class."""

import json
from typing import Any, Dict, List, Optional
import uuid
import httpx

from agents.decision_engine import AgentDecision, DecisionEngine, DecisionOutcome
from app.utils.hmac_utils import verify_webhook_signature


class BaseAgent:
    """Base class defining standard capabilities and autonomous behaviors for an enterprise AI agent."""

    def __init__(
        self,
        company_name: str,
        industry_category: str,
        interest_manifesto: str,
        capabilities: Optional[List[str]] = None,
        agent_id: Optional[uuid.UUID] = None,
        api_key: Optional[str] = None,
        api_key_hash: Optional[str] = None,
        webhook_url: Optional[str] = None,
        decision_engine: Optional[DecisionEngine] = None,
    ) -> None:
        self.agent_id = agent_id or uuid.uuid4()
        self.company_name = company_name
        self.industry_category = industry_category
        self.interest_manifesto = interest_manifesto
        self.capabilities = capabilities or []
        self.api_key = api_key
        self.api_key_hash = api_key_hash
        self.webhook_url = webhook_url or f"https://{company_name.lower().replace(' ', '')}.example/webhook"
        self.decision_engine = decision_engine or DecisionEngine()

    def verify_incoming_webhook(self, payload_bytes: bytes, signature_header: str) -> bool:
        """Verify HMAC signature for incoming notification."""
        secret = self.api_key_hash or "test_secret"
        return verify_webhook_signature(
            payload_bytes=payload_bytes,
            signature_header=signature_header,
            secret=secret,
        )

    def analyze_announcement(self, webhook_payload: Dict[str, Any]) -> AgentDecision:
        """Analyze incoming post and generate an autonomous structured decision."""
        post_data = webhook_payload.get("post", {})
        author_data = post_data.get("author", {})

        return self.decision_engine.evaluate_opportunity(
            company_name=self.company_name,
            industry_category=self.industry_category,
            interest_manifesto=self.interest_manifesto,
            capabilities=self.capabilities,
            post_title=post_data.get("title", ""),
            post_content=post_data.get("content", ""),
            author_company=author_data.get("company_name", "Unknown"),
            author_industry=author_data.get("industry_category", "Unknown"),
        )

    async def submit_comment_response(
        self,
        post_id: str,
        decision: AgentDecision,
        base_url: str = "http://test",
        custom_client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[dict]:
        """Submit an autonomous response as a comment under the original post."""
        if decision.decision not in (DecisionOutcome.INTERESTED, DecisionOutcome.NEEDS_MORE_INFORMATION):
            # Only post comments if interested or asking for details
            return None

        client = custom_client or httpx.AsyncClient(base_url=base_url)
        close_client = custom_client is None
        headers = {}
        if self.api_key:
            headers["X-Agent-API-Key"] = self.api_key

        payload = {
            "content": decision.comment_text,
            "proposed_terms": decision.proposed_terms,
        }

        try:
            resp = await client.post(
                f"/api/v1/posts/{post_id}/comments",
                json=payload,
                headers=headers,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return None
        except Exception as exc:
            from app.core.logging import logger
            logger.warning("Agent '%s' failed to submit comment response: %s", self.company_name, exc)
            return None
        finally:
            if close_client:
                await client.aclose()

    async def execute_autonomous_cycle(
        self,
        raw_payload_bytes: bytes,
        signature_header: str,
        base_url: str = "http://test",
        client: Optional[httpx.AsyncClient] = None,
    ) -> AgentDecision:
        """Run the full autonomous lifecycle: verify webhook -> analyze -> decide -> submit comment."""
        # 1. Verify signature
        if not self.verify_incoming_webhook(raw_payload_bytes, signature_header):
            raise ValueError(f"Webhook signature verification failed for agent '{self.company_name}'")

        # 2. Parse payload
        payload = json.loads(raw_payload_bytes.decode("utf-8"))

        # 3. Analyze post & make decision
        decision = self.analyze_announcement(payload)

        # 4. If interested, submit comment back to platform
        post_id = payload.get("post_id")
        if post_id and decision.decision in (DecisionOutcome.INTERESTED, DecisionOutcome.NEEDS_MORE_INFORMATION):
            await self.submit_comment_response(post_id, decision, base_url=base_url, custom_client=client)

        return decision
