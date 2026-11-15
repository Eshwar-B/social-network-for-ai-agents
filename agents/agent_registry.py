"""Agent registry managing configured simulated company agents."""

from typing import Dict, List, Optional
import uuid

from agents.base_agent import BaseAgent


class SwiggyAgent(BaseAgent):
    """Autonomous agent representing Swiggy (Food & Grocery Logistics)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            company_name="Swiggy",
            industry_category="Food Delivery",
            interest_manifesto="Online food ordering, cloud kitchen logistics, restaurant dining discounts, and quick commerce delivery.",
            capabilities=[
                "Nationwide restaurant delivery network",
                "Instant hyperlocal grocery fulfillment",
                "Consumer food checkout discounts",
            ],
            **kwargs,
        )


class PhonePeAgent(BaseAgent):
    """Autonomous agent representing PhonePe (Fintech & Digital Payments)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            company_name="PhonePe",
            industry_category="Fintech & Payments",
            interest_manifesto="UPI payments, digital wallet infrastructure, merchant QR codes, and consumer cashback campaigns.",
            capabilities=[
                "High-volume UPI payment processing",
                "Automated instant customer cashback",
                "Merchant integration APIs",
            ],
            **kwargs,
        )


class PaytmAgent(BaseAgent):
    """Autonomous agent representing Paytm (Digital Payments & Merchant Commerce)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            company_name="Paytm",
            industry_category="Fintech & Payments",
            interest_manifesto="Digital payments, merchant soundbox, festive dining cashback, and wallet rewards.",
            capabilities=[
                "Merchant QR and soundbox network",
                "Instant payment reconciliation",
                "Festive merchant reward programs",
            ],
            **kwargs,
        )


class AmazonAgent(BaseAgent):
    """Autonomous agent representing Amazon (E-Commerce & Cloud Retail)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            company_name="Amazon",
            industry_category="E-Commerce",
            interest_manifesto="E-commerce festive mega sales, electronics fulfillment, co-branded credit cards, and seller logistics.",
            capabilities=[
                "Pan-India retail fulfillment logistics",
                "Co-branded banking partnerships",
                "Prime festival promotions",
            ],
            **kwargs,
        )


class BajajAutoAgent(BaseAgent):
    """Autonomous agent representing Bajaj Auto (Automotive Manufacturing)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            company_name="Bajaj Auto",
            industry_category="Automotive",
            interest_manifesto="Two-wheeler manufacturing, commercial three-wheelers, diesel engine spare parts, and vehicle dealerships.",
            capabilities=[
                "Commercial fleet manufacturing",
                "Automotive dealership logistics",
                "Vehicle financing networks",
            ],
            **kwargs,
        )


class AgentRegistry:
    """Registry maintaining active simulated enterprise agents."""

    def __init__(self) -> None:
        self._agents_by_name: Dict[str, BaseAgent] = {}
        self._agents_by_id: Dict[uuid.UUID, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent instance in the registry."""
        self._agents_by_name[agent.company_name.lower()] = agent
        self._agents_by_id[agent.agent_id] = agent

    def get_by_name(self, name: str) -> Optional[BaseAgent]:
        """Lookup an agent by company name."""
        return self._agents_by_name.get(name.lower())

    def get_by_id(self, agent_id: uuid.UUID) -> Optional[BaseAgent]:
        """Lookup an agent by UUID."""
        return self._agents_by_id.get(agent_id)

    def all_agents(self) -> List[BaseAgent]:
        """Return all registered company agents."""
        return list(self._agents_by_name.values())


def create_default_registry() -> AgentRegistry:
    """Factory creating registry populated with the five standard company agents."""
    registry = AgentRegistry()
    registry.register(SwiggyAgent())
    registry.register(PhonePeAgent())
    registry.register(PaytmAgent())
    registry.register(AmazonAgent())
    registry.register(BajajAutoAgent())
    return registry
