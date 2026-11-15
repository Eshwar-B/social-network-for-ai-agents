"""Stage B: pgvector semantic approximate nearest neighbour search for agent routing."""

from dataclasses import dataclass
import time
from typing import List, Optional
import uuid

from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import logger
from app.database.models.agent import Agent
from app.database.models.blocklist import AgentBlocklist
from app.routing.sql_filter import CandidateAgent, SQLAgentFilter


@dataclass
class ScoredCandidate:
    """Candidate agent with dense vector similarity score."""

    agent_id: uuid.UUID
    company_name: str
    industry_category: str
    webhook_url: str
    interest_manifesto: str
    vector_score: float
    trust_score: float


@dataclass
class VectorSearchStats:
    """Audit metrics recorded during Stage B vector similarity retrieval."""

    candidates_retrieved: int
    min_vector_score: float
    max_vector_score: float
    execution_time_ms: float


@dataclass
class VectorSearchResult:
    """Container holding top candidate agents and Stage B performance metrics."""

    candidates: List[ScoredCandidate]
    stats: VectorSearchStats


class VectorAgentSearch:
    """Stage B dense vector semantic retrieval using pgvector cosine similarity."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def search_top_candidates(
        self,
        post_vector: List[float],
        author_agent_id: uuid.UUID,
        top_k: Optional[int] = None,
        explicit_excluded_industries: Optional[List[str]] = None,
        eligible_agent_ids: Optional[List[uuid.UUID]] = None,
    ) -> VectorSearchResult:
        """Retrieve top K semantically relevant eligible agents using pgvector cosine distance.

        Uses the HNSW index on `agents.interest_embedding` with `vector_cosine_ops`.
        """
        start_time = time.perf_counter()
        k = top_k or settings.TOP_K_CANDIDATES

        # Similarity calculation: 1 - cosine_distance
        # pgvector provides cosine_distance operator `<=>`
        distance_expr = Agent.interest_embedding.cosine_distance(post_vector)
        similarity_expr = (1.0 - distance_expr).label("vector_similarity")

        # Base query incorporating Stage A guardrails
        query = (
            select(
                Agent.id,
                Agent.company_name,
                Agent.industry_category,
                Agent.webhook_url,
                Agent.interest_manifesto,
                Agent.trust_score,
                similarity_expr,
            )
            .where(
                Agent.id != author_agent_id,
                Agent.is_active == True,  # noqa: E712
                Agent.embedding_status == "COMPLETED",
                Agent.interest_embedding.isnot(None),
            )
        )

        # If eligible agent IDs from Stage A were pre-computed, restrict to them
        if eligible_agent_ids is not None:
            if not eligible_agent_ids:
                # Empty eligible candidate pool
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return VectorSearchResult(
                    candidates=[],
                    stats=VectorSearchStats(
                        candidates_retrieved=0,
                        min_vector_score=0.0,
                        max_vector_score=0.0,
                        execution_time_ms=round(elapsed_ms, 2),
                    ),
                )
            query = query.where(Agent.id.in_(eligible_agent_ids))
        else:
            # Otherwise, evaluate blocklists directly in query
            blocklist_records = self.db.execute(
                select(AgentBlocklist).where(AgentBlocklist.agent_id == author_agent_id)
            ).scalars().all()

            blocked_agent_ids = [
                b.blocked_agent_id for b in blocklist_records if b.blocked_agent_id is not None
            ]
            blocked_industries = [
                b.blocked_industry.strip().lower()
                for b in blocklist_records
                if b.blocked_industry is not None
            ]
            if explicit_excluded_industries:
                blocked_industries.extend([i.strip().lower() for i in explicit_excluded_industries])

            if blocked_agent_ids:
                query = query.where(Agent.id.not_in(blocked_agent_ids))
            if blocked_industries:
                query = query.where(func.lower(Agent.industry_category).not_in(blocked_industries))

        # Order by similarity descending and cap at Top K
        query = query.order_by(desc("vector_similarity")).limit(k)

        rows = self.db.execute(query).all()
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        candidates: List[ScoredCandidate] = []
        scores: List[float] = []

        for row in rows:
            agent_id, company, industry, webhook, manifesto, trust, sim = row
            # Clamp similarity to [-1.0, 1.0] range (normally [0.0, 1.0] for unit vectors)
            clamped_sim = max(min(float(sim), 1.0), -1.0)
            candidates.append(
                ScoredCandidate(
                    agent_id=agent_id,
                    company_name=company,
                    industry_category=industry,
                    webhook_url=webhook,
                    interest_manifesto=manifesto,
                    vector_score=round(clamped_sim, 4),
                    trust_score=float(trust),
                )
            )
            scores.append(clamped_sim)

        min_score = round(min(scores), 4) if scores else 0.0
        max_score = round(max(scores), 4) if scores else 0.0

        stats = VectorSearchStats(
            candidates_retrieved=len(candidates),
            min_vector_score=min_score,
            max_vector_score=max_score,
            execution_time_ms=round(elapsed_ms, 2),
        )

        logger.info(
            "Stage B vector search: retrieved=%d, min_score=%.4f, max_score=%.4f, time=%.2fms",
            len(candidates),
            min_score,
            max_score,
            elapsed_ms,
        )

        return VectorSearchResult(candidates=candidates, stats=stats)
