"""Feedback and dynamic agent preference learning service."""

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Tuple
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.comment import Comment
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog


@dataclass
class EngagementMetrics:
    """Engagement statistics for an enterprise agent."""

    agent_id: uuid.UUID
    company_name: str
    notifications_received: int
    responses_submitted: int
    engagement_rate: float
    trust_score: float
    ignored_count: int


def _normalize_vector(vec: List[float]) -> List[float]:
    """Normalize a vector to unit length (L2 norm = 1.0)."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm < 1e-9:
        return vec
    return [x / norm for x in vec]


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two unit vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    return max(-1.0, min(1.0, dot))


class FeedbackService:
    """Calculates agent engagement metrics and dynamically updates interest preferences."""

    def __init__(
        self,
        db: Optional[Session] = None,
        learning_rate_pos: float = 0.05,
        learning_rate_neg: float = 0.02,
    ) -> None:
        self._db = db
        self.alpha = learning_rate_pos
        self.beta = learning_rate_neg

    def calculate_agent_metrics(
        self,
        agent_id: uuid.UUID,
        db_session: Optional[Session] = None,
    ) -> EngagementMetrics:
        """Calculate engagement rate and trust score for a specific agent."""
        db = db_session or self._db
        if not db:
            with session_factory() as local_db:
                return self._calculate_metrics(agent_id, local_db)
        return self._calculate_metrics(agent_id, db)

    def _calculate_metrics(self, agent_id: uuid.UUID, db: Session) -> EngagementMetrics:
        agent = db.get(Agent, agent_id)
        if not agent:
            raise ValueError(f"Agent '{agent_id}' was not found.")

        # Qualified notifications delivered
        notifications_count = db.execute(
            select(func.count(RoutingLog.id)).where(
                RoutingLog.target_agent_id == agent_id,
                RoutingLog.status.in_(["QUALIFIED", "ENGAGED"]),
            )
        ).scalar_one()

        # Responses submitted (ENGAGED logs)
        engaged_count = db.execute(
            select(func.count(RoutingLog.id)).where(
                RoutingLog.target_agent_id == agent_id,
                RoutingLog.status == "ENGAGED",
            )
        ).scalar_one()

        # Handle zero notifications safely
        if notifications_count > 0:
            rate = engaged_count / notifications_count
        else:
            rate = 0.0

        ignored_count = max(0, notifications_count - engaged_count)

        # Trust score baseline 1.0, adjusted smoothly in [0.5, 1.5]
        # +0.5 for 100% engagement, -0.3 for 0% with > 5 ignored
        if notifications_count >= 3:
            adjusted_trust = 0.8 + (rate * 0.4)
            agent.trust_score = round(max(0.5, min(1.5, adjusted_trust)), 3)
            db.commit()

        return EngagementMetrics(
            agent_id=agent.id,
            company_name=agent.company_name,
            notifications_received=notifications_count,
            responses_submitted=engaged_count,
            engagement_rate=round(rate, 4),
            trust_score=round(agent.trust_score, 3),
            ignored_count=ignored_count,
        )

    def update_dynamic_preferences(
        self,
        agent_id: uuid.UUID,
        db_session: Optional[Session] = None,
    ) -> Optional[List[float]]:
        """Perform gradual vector adjustment towards engaged topics and away from repeatedly ignored topics."""
        db = db_session or self._db
        if not db:
            with session_factory() as local_db:
                return self._update_preferences(agent_id, local_db)
        return self._update_preferences(agent_id, db)

    def _update_preferences(self, agent_id: uuid.UUID, db: Session) -> Optional[List[float]]:
        agent = db.get(Agent, agent_id)
        if not agent or not agent.interest_embedding:
            return None

        current_vector = list(agent.interest_embedding)

        # 1. Gather engaged post embeddings (positive influence)
        engaged_logs = list(
            db.execute(
                select(RoutingLog).where(
                    RoutingLog.target_agent_id == agent_id,
                    RoutingLog.status == "ENGAGED",
                )
            ).scalars().all()
        )

        # 2. Gather repeatedly ignored post embeddings (negative influence)
        ignored_logs = list(
            db.execute(
                select(RoutingLog).where(
                    RoutingLog.target_agent_id == agent_id,
                    RoutingLog.status == "QUALIFIED",
                )
            ).scalars().all()
        )

        if not engaged_logs and not ignored_logs:
            return current_vector

        updated_vec = list(current_vector)

        # Apply positive gradient for engaged posts
        for log in engaged_logs:
            post = db.get(Post, log.post_id)
            if post and post.post_embedding:
                post_vec = list(post.post_embedding)
                for i in range(len(updated_vec)):
                    updated_vec[i] += self.alpha * post_vec[i]

        # Apply negative gradient away from ignored posts (only if >= 2 ignored to avoid overreacting)
        if len(ignored_logs) >= 2:
            for log in ignored_logs:
                post = db.get(Post, log.post_id)
                if post and post.post_embedding:
                    post_vec = list(post.post_embedding)
                    for i in range(len(updated_vec)):
                        updated_vec[i] -= self.beta * post_vec[i]

        # Re-normalize to unit sphere
        normalized_vector = _normalize_vector(updated_vec)

        # Persist updated dynamic interest embedding while keeping manifesto intact
        agent.interest_embedding = normalized_vector
        db.commit()

        logger.info(
            "Updated dynamic preference embedding for agent '%s' (%d engaged, %d ignored)",
            agent.company_name,
            len(engaged_logs),
            len(ignored_logs),
        )
        return normalized_vector

    def run_feedback_loop_for_all_agents(
        self,
        db_session: Optional[Session] = None,
    ) -> Dict[str, EngagementMetrics]:
        """Background feedback job: update metrics and dynamic preferences for all active agents."""
        db = db_session or self._db
        if not db:
            with session_factory() as local_db:
                return self._run_all(local_db)
        return self._run_all(db)

    def _run_all(self, db: Session) -> Dict[str, EngagementMetrics]:
        agents = list(db.execute(select(Agent).where(Agent.is_active == True)).scalars().all())
        results = {}
        for agent in agents:
            metrics = self._calculate_metrics(agent.id, db)
            self._update_preferences(agent.id, db)
            results[agent.company_name] = metrics
        return results
