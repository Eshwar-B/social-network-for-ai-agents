"""Three-stage semantic relevance routing orchestrator for Asama.ai."""

from dataclasses import dataclass
import time
from typing import List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import logger
from app.database.connection import session_factory
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog
from app.routing.reranker import BaseReranker, RerankCandidate, get_reranker
from app.routing.sql_filter import SQLAgentFilter
from app.routing.vector_search import VectorAgentSearch


@dataclass
class SelectedRecipient:
    """Agent selected as a qualified recipient for notification delivery."""

    agent_id: uuid.UUID
    company_name: str
    industry_category: str
    webhook_url: str
    vector_score: float
    rerank_score: float
    final_score: float


@dataclass
class RejectedRecipient:
    """Agent evaluated but rejected due to threshold or limit constraints."""

    agent_id: uuid.UUID
    company_name: str
    final_score: float
    status: str
    rejection_reason: str


@dataclass
class RoutingExecutionResult:
    """Complete summary of the three-stage routing decision workflow."""

    post_id: uuid.UUID
    author_company: str
    stage_a_eligible_count: int
    stage_b_candidates_count: int
    qualified_count: int
    qualified_recipients: List[SelectedRecipient]
    rejected_candidates: List[RejectedRecipient]
    latency_ms: float


class RoutingService:
    """Orchestrates Stage A (SQL), Stage B (pgvector), and Stage C (Reranker)."""

    def __init__(
        self,
        db: Optional[Session] = None,
        reranker: Optional[BaseReranker] = None,
    ) -> None:
        self._db = db
        self.reranker = reranker or get_reranker()
        self.threshold = settings.RELEVANCE_THRESHOLD
        self.max_recipients = settings.MAX_RECIPIENTS
        self.top_k = settings.TOP_K_CANDIDATES

    async def route_post(
        self,
        post_id: uuid.UUID,
        db_session: Optional[Session] = None,
        eligible_agent_ids: Optional[List[uuid.UUID]] = None,
    ) -> RoutingExecutionResult:
        """Execute the end-to-end 3-stage routing workflow for a post."""
        start_time = time.perf_counter()
        db = db_session or self._db
        if not db:
            with session_factory() as local_db:
                return await self._execute_routing(post_id, local_db, start_time, eligible_agent_ids)

        return await self._execute_routing(post_id, db, start_time, eligible_agent_ids)

    async def _execute_routing(
        self,
        post_id: uuid.UUID,
        db: Session,
        start_time: float,
        explicit_eligible_agent_ids: Optional[List[uuid.UUID]] = None,
    ) -> RoutingExecutionResult:
        """Internal execution with active database session."""
        # 1. Retrieve authoritative post and post embedding
        post = db.execute(
            select(Post).where(Post.id == post_id)
        ).scalar_one_or_none()

        if not post:
            raise ValueError(f"Post '{post_id}' not found for routing.")

        if post.post_embedding is None:
            raise ValueError(f"Post '{post_id}' has no vector embedding.")

        author_id = post.author_agent_id
        author_company = post.author.company_name if post.author else "Unknown"
        post_vector = list(post.post_embedding)

        # 2. STAGE A: SQL Eligibility Filtering
        sql_filter = SQLAgentFilter(db)
        stage_a_result = sql_filter.filter_eligible_agents(author_agent_id=author_id)
        if explicit_eligible_agent_ids is not None:
            eligible_agent_ids = [c.id for c in stage_a_result.candidates if c.id in explicit_eligible_agent_ids]
        else:
            eligible_agent_ids = [c.id for c in stage_a_result.candidates]

        logger.info(
            "Routing post %s (Author: %s): Stage A found %d eligible agents",
            post_id,
            author_company,
            len(eligible_agent_ids),
        )

        if not eligible_agent_ids:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            post.status = "ROUTED"
            db.commit()
            return RoutingExecutionResult(
                post_id=post_id,
                author_company=author_company,
                stage_a_eligible_count=0,
                stage_b_candidates_count=0,
                qualified_count=0,
                qualified_recipients=[],
                rejected_candidates=[],
                latency_ms=round(elapsed_ms, 2),
            )

        # 3. STAGE B: pgvector Dense Semantic Search (Top K = 50)
        vector_search = VectorAgentSearch(db)
        stage_b_result = vector_search.search_top_candidates(
            post_vector=post_vector,
            author_agent_id=author_id,
            eligible_agent_ids=eligible_agent_ids,
            top_k=self.top_k,
        )

        logger.info(
            "Routing post %s: Stage B retrieved %d vector candidates",
            post_id,
            len(stage_b_result.candidates),
        )

        # 4. STAGE C: Cross-Encoder Reranking
        rerank_inputs = [
            RerankCandidate(
                agent_id=c.agent_id,
                company_name=c.company_name,
                industry_category=c.industry_category,
                webhook_url=c.webhook_url,
                interest_manifesto=c.interest_manifesto,
                vector_score=c.vector_score,
                trust_score=c.trust_score,
            )
            for c in stage_b_result.candidates
        ]

        rerank_results = await self.reranker.rerank(
            post_title=post.title,
            post_content=post.content,
            candidates=rerank_inputs,
        )

        # 5. Threshold enforcement (score >= 0.75) and Recipient Limit (max 5)
        qualified_recipients: List[SelectedRecipient] = []
        rejected_candidates: List[RejectedRecipient] = []
        routing_log_entries: List[RoutingLog] = []

        for candidate in rerank_results:
            is_above_threshold = candidate.final_score >= self.threshold

            if is_above_threshold:
                if len(qualified_recipients) < self.max_recipients:
                    # Qualified and within top 5 cap
                    decision_status = "QUALIFIED"
                    decision_reason = (
                        f"Score {candidate.final_score:.4f} meets threshold {self.threshold} "
                        f"and ranks #{len(qualified_recipients) + 1} of top {self.max_recipients}"
                    )
                    qualified_recipients.append(
                        SelectedRecipient(
                            agent_id=candidate.agent_id,
                            company_name=candidate.company_name,
                            industry_category=candidate.industry_category,
                            webhook_url=candidate.webhook_url,
                            vector_score=candidate.vector_score,
                            rerank_score=candidate.rerank_score,
                            final_score=candidate.final_score,
                        )
                    )
                else:
                    # Above threshold but exceeded recipient limit
                    decision_status = "REJECTED_LIMIT"
                    decision_reason = (
                        f"Score {candidate.final_score:.4f} qualified but exceeded maximum "
                        f"recipient quota ({self.max_recipients})"
                    )
                    rejected_candidates.append(
                        RejectedRecipient(
                            agent_id=candidate.agent_id,
                            company_name=candidate.company_name,
                            final_score=candidate.final_score,
                            status=decision_status,
                            rejection_reason=decision_reason,
                        )
                    )
            else:
                # Below threshold
                decision_status = "REJECTED_THRESHOLD"
                decision_reason = (
                    f"Score {candidate.final_score:.4f} below required relevance threshold {self.threshold}"
                )
                rejected_candidates.append(
                    RejectedRecipient(
                        agent_id=candidate.agent_id,
                        company_name=candidate.company_name,
                        final_score=candidate.final_score,
                        status=decision_status,
                        rejection_reason=decision_reason,
                    )
                )

            # Prepare routing log for persistence
            routing_log_entries.append(
                RoutingLog(
                    post_id=post_id,
                    target_agent_id=candidate.agent_id,
                    vector_score=candidate.vector_score,
                    rerank_score=candidate.rerank_score,
                    final_score=candidate.final_score,
                    status=decision_status,
                    decision_reason=decision_reason,
                )
            )

        # 6. Persist routing decisions in PostgreSQL
        db.add_all(routing_log_entries)
        post.status = "ROUTED"
        db.commit()

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        logger.info(
            "Completed 3-stage routing for post %s in %.2fms: %d qualified recipients, %d rejected",
            post_id,
            elapsed_ms,
            len(qualified_recipients),
            len(rejected_candidates),
        )

        return RoutingExecutionResult(
            post_id=post_id,
            author_company=author_company,
            stage_a_eligible_count=len(eligible_agent_ids),
            stage_b_candidates_count=len(stage_b_result.candidates),
            qualified_count=len(qualified_recipients),
            qualified_recipients=qualified_recipients,
            rejected_candidates=rejected_candidates,
            latency_ms=round(elapsed_ms, 2),
        )
