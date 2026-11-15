"""Webhook receiver and router for autonomous enterprise agents."""

import json
from typing import Optional
import httpx

from agents.agent_registry import AgentRegistry, create_default_registry
from agents.decision_engine import AgentDecision
from app.core.logging import logger


class WebhookReceiver:
    """Receives platform webhook notifications, verifies authenticity, and routes to recipient agents."""

    def __init__(self, registry: Optional[AgentRegistry] = None) -> None:
        self.registry = registry or create_default_registry()

    async def handle_incoming_webhook(
        self,
        raw_body: bytes,
        signature_header: str,
        base_url: str = "http://test",
        custom_client: Optional[httpx.AsyncClient] = None,
    ) -> AgentDecision:
        """Handle incoming webhook notification: identify agent, verify signature, and execute decision."""
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"Invalid JSON payload: {exc}")

        recipient_data = payload.get("recipient", {})
        company_name = recipient_data.get("company_name", "")
        agent = self.registry.get_by_name(company_name)

        if not agent:
            raise ValueError(f"Recipient agent '{company_name}' not found in active registry")

        logger.info(
            "Webhook receiver routing event '%s' to autonomous agent '%s'",
            payload.get("event"),
            company_name,
        )

        return await agent.execute_autonomous_cycle(
            raw_payload_bytes=raw_body,
            signature_header=signature_header,
            base_url=base_url,
            client=custom_client,
        )
