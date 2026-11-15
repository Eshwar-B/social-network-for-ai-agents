"""Stage C: Cross-encoder reranking provider abstraction and implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional
import uuid

from app.config import settings
from app.core.logging import logger


@dataclass
class RerankCandidate:
    """Input payload representing a candidate agent for reranking."""

    agent_id: uuid.UUID
    company_name: str
    industry_category: str
    webhook_url: str
    interest_manifesto: str
    vector_score: float
    trust_score: float


@dataclass
class RerankResult:
    """Output score and decision evaluation for a candidate agent."""

    agent_id: uuid.UUID
    company_name: str
    industry_category: str
    webhook_url: str
    vector_score: float
    rerank_score: float
    final_score: float
    is_qualified: bool
    rejection_reason: Optional[str] = None


class BaseReranker(ABC):
    """Abstract interface for cross-encoder rerankers and relevance judges."""

    @abstractmethod
    async def rerank(
        self,
        post_title: str,
        post_content: str,
        candidates: List[RerankCandidate],
    ) -> List[RerankResult]:
        """Score each candidate against the full post and calibrate to [0.0, 1.0]."""
        pass


class MockRerankerProvider(BaseReranker):
    """Deterministic, calibrated reranking provider for testing and offline execution.

    Evaluates semantic token overlap, cross-industry affinity, and vector alignment
    to produce calibrated scores strictly bounded in [0.0, 1.0].
    """

    def __init__(self, threshold: float = 0.75) -> None:
        self.threshold = threshold

    async def rerank(
        self,
        post_title: str,
        post_content: str,
        candidates: List[RerankCandidate],
    ) -> List[RerankResult]:
        post_tokens = set(f"{post_title} {post_content}".lower().split())
        results: List[RerankResult] = []

        for cand in candidates:
            cand_tokens = set(f"{cand.company_name} {cand.industry_category} {cand.interest_manifesto}".lower().split())

            # Jaccard lexical overlap
            intersection = post_tokens.intersection(cand_tokens)
            union = post_tokens.union(cand_tokens)
            jaccard = len(intersection) / len(union) if union else 0.0

            # Relevant cross-company partnership and collaboration keywords
            partnership_terms = {
                "cashback", "upi", "discount", "discounts", "payment", "payments",
                "fintech", "wallet", "dining", "food", "rewards", "reward", "cards",
                "credit", "bank", "banking", "festive", "campaign", "partners", "partner"
            }
            lexical_overlap = post_tokens.intersection(cand_tokens)
            synergy_tokens = lexical_overlap.union(cand_tokens.intersection(partnership_terms))

            # Synergy factor based on joint cross-company business intent
            synergy_factor = min(len(synergy_tokens) * 0.18, 0.75) if synergy_tokens else 0.0
            jaccard_factor = min(jaccard * 4.0, 1.0)
            normalized_vec = max(cand.vector_score, 0.0)

            # Cross-encoder joint interaction score
            raw_score = (0.25 * normalized_vec) + (0.30 * jaccard_factor) + (0.45 * synergy_factor)

            # Apply sigmoid calibration to produce normalized probabilities in [0.0, 1.0]
            calibrated_score = 1.0 / (1.0 + math.exp(-6.5 * (raw_score - 0.26)))
            calibrated_score = round(max(min(calibrated_score, 1.0), 0.0), 4)

            is_qualified = calibrated_score >= self.threshold
            rejection = None if is_qualified else f"Score {calibrated_score} below required threshold {self.threshold}"

            results.append(
                RerankResult(
                    agent_id=cand.agent_id,
                    company_name=cand.company_name,
                    industry_category=cand.industry_category,
                    webhook_url=cand.webhook_url,
                    vector_score=cand.vector_score,
                    rerank_score=calibrated_score,
                    final_score=calibrated_score,
                    is_qualified=is_qualified,
                    rejection_reason=rejection,
                )
            )

        # Sort descending by final score
        results.sort(key=lambda r: r.final_score, reverse=True)
        return results


def get_reranker() -> BaseReranker:
    """Factory instantiating the configured reranker implementation."""
    provider_name = (settings.RERANKER_PROVIDER or "mock").lower()

    if provider_name == "cohere" and settings.COHERE_API_KEY:
        # Placeholder for Cohere rerank API integration if key provided
        logger.info("Initializing Cohere reranker provider")
        pass

    logger.info("Using MockRerankerProvider (threshold=%.2f)", settings.RELEVANCE_THRESHOLD)
    return MockRerankerProvider(threshold=settings.RELEVANCE_THRESHOLD)
