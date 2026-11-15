"""Autonomous Decision Engine for enterprise AI agents."""

from enum import Enum
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DecisionOutcome(str, Enum):
    """Supported autonomous decision outcomes."""

    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"
    REQUIRES_HUMAN_APPROVAL = "REQUIRES_HUMAN_APPROVAL"


class AgentDecision(BaseModel):
    """Structured decision output produced by an autonomous agent."""

    decision: DecisionOutcome
    rationale: str
    proposed_terms: Optional[Dict[str, Any]] = Field(default_factory=dict)
    comment_text: str
    is_binding: bool = False
    disclaimer: str = "Subject to formal commercial agreement; non-binding exploratory proposal."


# Patterns indicative of prompt injection or unauthorized commitment attempts
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"system\s+override", re.IGNORECASE),
    re.compile(r"you\s+must\s+(agree|pay|transfer)", re.IGNORECASE),
    re.compile(r"legally\s+binding", re.IGNORECASE),
    re.compile(r"act\s+as\s+an?\s+unrestricted", re.IGNORECASE),
]


class DecisionEngine:
    """Analyzes business announcements against company capabilities and generates autonomous decisions."""

    def sanitize_untrusted_input(self, text: str) -> str:
        """Strip dangerous injection sequences from untrusted incoming post content."""
        sanitized = text
        for pattern in INJECTION_PATTERNS:
            sanitized = pattern.sub("[BLOCKED_UNTRUSTED_INSTRUCTION]", sanitized)
        return sanitized

    def evaluate_opportunity(
        self,
        company_name: str,
        industry_category: str,
        interest_manifesto: str,
        capabilities: List[str],
        post_title: str,
        post_content: str,
        author_company: str,
        author_industry: str,
    ) -> AgentDecision:
        """Analyze business synergy and produce an autonomous structured decision."""
        # 1. Sanitize untrusted post input
        safe_title = self.sanitize_untrusted_input(post_title)
        safe_content = self.sanitize_untrusted_input(post_content)
        combined_post = f"{safe_title} {safe_content}".lower()

        # Check for injection attempt
        detected_injection = "[BLOCKED_UNTRUSTED_INSTRUCTION]" in safe_title or "[BLOCKED_UNTRUSTED_INSTRUCTION]" in safe_content
        if detected_injection:
            return AgentDecision(
                decision=DecisionOutcome.REQUIRES_HUMAN_APPROVAL,
                rationale="Potentially malicious or manipulative instruction pattern detected in announcement payload.",
                proposed_terms={},
                comment_text=(
                    f"{company_name} received this announcement. However, automated processing flagged "
                    "terms that require human security and compliance review before proceeding."
                ),
            )

        # 2. Extract domain synergies
        payment_keywords = ["upi", "cashback", "payment", "discount", "fintech", "wallet", "banking", "card"]
        food_delivery_keywords = ["food", "restaurant", "delivery", "order", "kitchen", "dining"]
        ecommerce_keywords = ["ecommerce", "e-commerce", "retail", "shopping", "products", "seller", "festive sale"]
        auto_keywords = ["vehicle", "automobile", "tractor", "engine", "dealership", "spare parts"]

        post_has_payment = any(k in combined_post for k in payment_keywords)
        post_has_food = any(k in combined_post for k in food_delivery_keywords)
        post_has_ecommerce = any(k in combined_post for k in ecommerce_keywords)
        post_has_auto = any(k in combined_post for k in auto_keywords)

        # 3. Company-specific autonomous evaluation logic
        # PhonePe / Paytm / Fintech Agents
        if "fintech" in industry_category.lower() or "payment" in industry_category.lower():
            if post_has_payment or post_has_food or post_has_ecommerce:
                cashback_rate = 10 if "phonepe" in company_name.lower() else 8
                return AgentDecision(
                    decision=DecisionOutcome.INTERESTED,
                    rationale=f"High synergy: {author_company}'s announcement offers merchant checkout opportunities for our payments platform.",
                    proposed_terms={
                        "partner_type": "Payment Gateway & UPI Sponsor",
                        "customer_cashback_percent": cashback_rate,
                        "min_transaction_value_inr": 300,
                        "campaign_duration": "Festive Period (30 Days)",
                        "non_binding": True,
                    },
                    comment_text=(
                        f"{company_name} is excited about this opportunity with {author_company}. "
                        f"We propose co-sponsoring up to {cashback_rate}% instant customer cashback on orders above ₹300 "
                        f"paid via our UPI integration during this festive campaign."
                    ),
                )
            else:
                return AgentDecision(
                    decision=DecisionOutcome.NOT_INTERESTED,
                    rationale="Announcement does not involve consumer payments, checkout discounts, or merchant partnerships.",
                    comment_text=f"{company_name} has reviewed the update but has no active business synergies with this announcement.",
                )

        # Banking Agents (e.g. HDFC Bank)
        elif "bank" in industry_category.lower():
            if post_has_food or post_has_ecommerce or post_has_payment:
                return AgentDecision(
                    decision=DecisionOutcome.INTERESTED,
                    rationale="Synergy with credit card festive dining and shopping reward point promotions.",
                    proposed_terms={
                        "partner_type": "Banking & Co-Branded Card Partner",
                        "card_instant_discount_percent": 10,
                        "max_discount_cap_inr": 500,
                        "non_binding": True,
                    },
                    comment_text=(
                        f"{company_name} is interested in collaborating with {author_company}. "
                        "We can offer a 10% instant discount (up to ₹500) for customers transacting with our credit and debit cards."
                    ),
                )
            else:
                return AgentDecision(
                    decision=DecisionOutcome.NOT_INTERESTED,
                    rationale="Announcement does not align with banking card or merchant merchant credit portfolios.",
                    comment_text=f"{company_name} does not see an immediate collaboration opportunity.",
                )

        # E-Commerce Agents (e.g. Amazon)
        elif "e-commerce" in industry_category.lower() or "retail" in industry_category.lower():
            if post_has_ecommerce or post_has_payment or post_has_food:
                return AgentDecision(
                    decision=DecisionOutcome.NEEDS_MORE_INFORMATION,
                    rationale="Potential cross-promotional retail synergy, but requires details on commission and logistics integration.",
                    proposed_terms={
                        "cross_promotion_channel": "App Banner & Gift Cards",
                        "requires_details_on": ["Logistics SLA", "Fulfillment geographic scope"],
                        "non_binding": True,
                    },
                    comment_text=(
                        f"{company_name} sees potential synergy with {author_company}. "
                        "Could you share more details regarding delivery timelines and target regional tier coverage?"
                    ),
                )
            else:
                return AgentDecision(
                    decision=DecisionOutcome.NOT_INTERESTED,
                    rationale="No retail or e-commerce alignment.",
                    comment_text=f"{company_name} does not have current business overlap with this update.",
                )

        # Automotive Agents (e.g. Bajaj Auto)
        elif "auto" in industry_category.lower():
            if post_has_auto:
                return AgentDecision(
                    decision=DecisionOutcome.INTERESTED,
                    rationale="Automotive and commercial fleet synergies identified.",
                    proposed_terms={"fleet_financing_available": True, "non_binding": True},
                    comment_text=f"{company_name} is interested in exploring commercial vehicle fleet collaboration.",
                )
            else:
                # Completely unrelated e.g. food or restaurant promotion
                return AgentDecision(
                    decision=DecisionOutcome.NOT_INTERESTED,
                    rationale=f"Automotive manufacturer {company_name} has no commercial overlap with {author_industry} festive food promotions.",
                    comment_text=f"{company_name} evaluated this announcement and determined no industry overlap exists.",
                )

        # Generic / Fallback Agent evaluation
        manifesto_words = set(re.findall(r"\w+", interest_manifesto.lower()))
        overlap_words = [w for w in re.findall(r"\w+", combined_post) if w in manifesto_words and len(w) > 3]

        if len(overlap_words) >= 3:
            return AgentDecision(
                decision=DecisionOutcome.INTERESTED,
                rationale=f"Significant keyword synergy ({', '.join(overlap_words[:3])}) matching business manifesto.",
                proposed_terms={"collaborative_scope": overlap_words[:3], "non_binding": True},
                comment_text=f"{company_name} is interested in partnering on {', '.join(overlap_words[:2])}.",
            )
        else:
            return AgentDecision(
                decision=DecisionOutcome.NOT_INTERESTED,
                rationale="Insufficient commercial synergy with agent profile.",
                comment_text=f"{company_name} has reviewed this announcement and found no immediate business synergy.",
            )
