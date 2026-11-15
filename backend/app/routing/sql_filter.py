"""Stage A: SQL-based metadata eligibility filtering for agent routing."""

from dataclasses import dataclass
import time
from typing import List, Optional, Set
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.database.models.agent import Agent
from app.database.models.blocklist import AgentBlocklist


@dataclass
class CandidateAgent:
    """Eligible candidate agent with profile metadata and interest embedding."""

    id: uuid.UUID
    company_name: str
    industry_category: str
    webhook_url: str
    interest_manifesto: str
    interest_embedding: List[float]
    trust_score: float


@dataclass
class SQLFilterStats:
    """Breakdown statistics recorded during Stage A filtering."""

    total_agents: int
    eligible_count: int
    publisher_excluded: int
    inactive_excluded: int
    missing_embedding_excluded: int
    blocked_agents_excluded: int
    blocked_industries_excluded: int
    execution_time_ms: float


@dataclass
class SQLFilterResult:
    """Container holding eligible candidate agents and audit statistics."""

    candidates: List[CandidateAgent]
    stats: SQLFilterStats


class SQLAgentFilter:
    """Stage A filter evaluating hard metadata rules and exclusions in SQL."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def filter_eligible_agents(
        self,
        author_agent_id: uuid.UUID,
        explicit_excluded_industries: Optional[List[str]] = None,
    ) -> SQLFilterResult:
        """Dynamically retrieve eligible agents while applying all metadata guardrails."""
        start_time = time.perf_counter()

        # 1. Fetch author blocklists (blocked agent IDs and blocked industries)
        blocklist_records = self.db.execute(
            select(AgentBlocklist).where(AgentBlocklist.agent_id == author_agent_id)
        ).scalars().all()

        blocked_agent_ids: Set[uuid.UUID] = {
            b.blocked_agent_id for b in blocklist_records if b.blocked_agent_id is not None
        }
        blocked_industries: Set[str] = {
            b.blocked_industry.strip().lower()
            for b in blocklist_records
            if b.blocked_industry is not None
        }

        # Add explicit post-level excluded industries if provided
        if explicit_excluded_industries:
            for ind in explicit_excluded_industries:
                blocked_industries.add(ind.strip().lower())

        # 2. Gather total agents count for metrics
        total_agents = self.db.execute(select(func.count(Agent.id))).scalar() or 0

        # 3. Gather exclusion metrics for transparency and audit logging
        inactive_count = (
            self.db.execute(
                select(func.count(Agent.id)).where(
                    Agent.id != author_agent_id,
                    Agent.is_active == False,  # noqa: E712
                )
            ).scalar()
            or 0
        )

        missing_embedding_count = (
            self.db.execute(
                select(func.count(Agent.id)).where(
                    Agent.id != author_agent_id,
                    Agent.is_active == True,  # noqa: E712
                    (Agent.embedding_status != "COMPLETED") | (Agent.interest_embedding.is_(None)),
                )
            ).scalar()
            or 0
        )

        # 4. Build primary eligibility query
        query = select(Agent).where(
            Agent.id != author_agent_id,
            Agent.is_active == True,  # noqa: E712
            Agent.embedding_status == "COMPLETED",
            Agent.interest_embedding.isnot(None),
        )

        if blocked_agent_ids:
            query = query.where(Agent.id.not_in(list(blocked_agent_ids)))

        if blocked_industries:
            query = query.where(func.lower(Agent.industry_category).not_in(list(blocked_industries)))

        eligible_records = self.db.execute(query).scalars().all()

        # Count blocked exclusions
        blocked_agents_excluded = len(blocked_agent_ids)
        blocked_industries_excluded = len(blocked_industries)

        candidates = [
            CandidateAgent(
                id=a.id,
                company_name=a.company_name,
                industry_category=a.industry_category,
                webhook_url=a.webhook_url,
                interest_manifesto=a.interest_manifesto,
                interest_embedding=list(a.interest_embedding),
                trust_score=a.trust_score,
            )
            for a in eligible_records
        ]

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        stats = SQLFilterStats(
            total_agents=total_agents,
            eligible_count=len(candidates),
            publisher_excluded=1 if total_agents > 0 else 0,
            inactive_excluded=inactive_count,
            missing_embedding_excluded=missing_embedding_count,
            blocked_agents_excluded=blocked_agents_excluded,
            blocked_industries_excluded=blocked_industries_excluded,
            execution_time_ms=round(elapsed_ms, 2),
        )

        logger.info(
            "Stage A SQL filter: total=%d, eligible=%d, inactive_excl=%d, miss_emb_excl=%d, time=%.2fms",
            total_agents,
            len(candidates),
            inactive_count,
            missing_embedding_count,
            elapsed_ms,
        )

        return SQLFilterResult(candidates=candidates, stats=stats)
