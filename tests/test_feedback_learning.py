"""Integration tests for Phase 12: Feedback and Dynamic Interest Learning."""

import math
import uuid
import pytest

from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog
from app.services.embedding_provider import MockEmbeddingProvider
from app.services.feedback_service import FeedbackService, _cosine_similarity


@pytest.mark.asyncio
async def test_engagement_rate_zero_notifications_safe():
    """Verify engagement rate handles 0 notifications safely without division by zero."""
    with session_factory() as db:
        agent = Agent(
            company_name=f"ZeroAgent_{uuid.uuid4().hex[:8]}",
            industry_category="Fintech",
            webhook_url="https://zero.example/webhook",
            interest_manifesto="Zero notification testing",
            api_key_hash="hash_zero",
            embedding_status="COMPLETED",
        )
        db.add(agent)
        db.commit()

        service = FeedbackService(db=db)
        metrics = service.calculate_agent_metrics(agent.id, db_session=db)

        assert metrics.notifications_received == 0
        assert metrics.responses_submitted == 0
        assert metrics.engagement_rate == 0.0
        assert metrics.ignored_count == 0

        db.delete(agent)
        db.commit()


@pytest.mark.asyncio
async def test_engagement_rate_calculation():
    """Verify engagement rate with 3 notifications and 2 responses = 0.6667."""
    with session_factory() as db:
        agent = Agent(
            company_name=f"EngageAgent_{uuid.uuid4().hex[:8]}",
            industry_category="Banking",
            webhook_url="https://engage.example/webhook",
            interest_manifesto="Banking credit cards",
            api_key_hash="hash_engage",
            embedding_status="COMPLETED",
        )
        db.add(agent)
        db.commit()

        # Dummy post
        post = Post(
            author_agent_id=agent.id,
            title="Promo Post",
            content="Testing feedback engagement rate",
            status="ROUTED",
        )
        db.add(post)
        db.commit()

        # 2 ENGAGED logs, 1 QUALIFIED (ignored) log
        log1 = RoutingLog(
            post_id=post.id, target_agent_id=agent.id,
            vector_score=0.85, rerank_score=0.90, final_score=0.90, status="ENGAGED",
        )
        log2 = RoutingLog(
            post_id=post.id, target_agent_id=agent.id,
            vector_score=0.82, rerank_score=0.88, final_score=0.88, status="ENGAGED",
        )
        log3 = RoutingLog(
            post_id=post.id, target_agent_id=agent.id,
            vector_score=0.76, rerank_score=0.78, final_score=0.78, status="QUALIFIED",
        )
        db.add_all([log1, log2, log3])
        db.commit()

        service = FeedbackService(db=db)
        metrics = service.calculate_agent_metrics(agent.id, db_session=db)

        assert metrics.notifications_received == 3
        assert metrics.responses_submitted == 2
        assert metrics.ignored_count == 1
        assert abs(metrics.engagement_rate - (2 / 3)) < 1e-3

        db.delete(agent)
        db.commit()


@pytest.mark.asyncio
async def test_dynamic_preference_positive_gradient_shift():
    """Verify that engaging with a topic shifts agent vector closer to that topic."""
    provider = MockEmbeddingProvider(dimension=1536)
    with session_factory() as db:
        initial_vec = await provider.embed_text("Banking personal loans and savings")
        target_topic_vec = await provider.embed_text("Diwali UPI instant cashback discounts")

        initial_sim = _cosine_similarity(initial_vec, target_topic_vec)

        agent = Agent(
            company_name=f"ShiftAgent_{uuid.uuid4().hex[:8]}",
            industry_category="Banking",
            webhook_url="https://shift.example/webhook",
            interest_manifesto="Banking personal loans and savings",
            interest_embedding=initial_vec,
            embedding_status="COMPLETED",
            api_key_hash="hash_shift",
        )
        db.add(agent)
        db.commit()

        post = Post(
            author_agent_id=agent.id,
            title="Diwali Cashback Promo",
            content="Diwali UPI instant cashback discounts",
            post_embedding=target_topic_vec,
            status="ROUTED",
        )
        db.add(post)
        db.commit()

        # Agent engaged with this post
        log = RoutingLog(
            post_id=post.id, target_agent_id=agent.id,
            vector_score=0.80, rerank_score=0.85, final_score=0.85, status="ENGAGED",
        )
        db.add(log)
        db.commit()

        service = FeedbackService(db=db, learning_rate_pos=0.10)
        updated_vec = service.update_dynamic_preferences(agent.id, db_session=db)

        assert updated_vec is not None
        assert len(updated_vec) == 1536

        # Verify unit length (L2 norm approx 1.0)
        norm = math.sqrt(sum(x * x for x in updated_vec))
        assert abs(norm - 1.0) < 1e-4

        # Similarity to target topic should have INCREASED
        new_sim = _cosine_similarity(updated_vec, target_topic_vec)
        assert new_sim > initial_sim

        # Verify manifesto text remained intact
        db.refresh(agent)
        assert agent.interest_manifesto == "Banking personal loans and savings"

        db.delete(agent)
        db.commit()


@pytest.mark.asyncio
async def test_dynamic_preference_negative_gradient_shift():
    """Verify that repeatedly ignoring a topic shifts agent vector away from it."""
    provider = MockEmbeddingProvider(dimension=1536)
    with session_factory() as db:
        initial_vec = await provider.embed_text("General technology and software")
        unwanted_vec = await provider.embed_text("Commercial tractor diesel engine spare parts")

        initial_sim = _cosine_similarity(initial_vec, unwanted_vec)

        agent = Agent(
            company_name=f"NegShiftAgent_{uuid.uuid4().hex[:8]}",
            industry_category="Tech",
            webhook_url="https://neg.example/webhook",
            interest_manifesto="General technology and software",
            interest_embedding=initial_vec,
            embedding_status="COMPLETED",
            api_key_hash="hash_neg",
        )
        db.add(agent)
        db.commit()

        post1 = Post(author_agent_id=agent.id, title="Tractor 1", content="Diesel engines", post_embedding=unwanted_vec, status="ROUTED")
        post2 = Post(author_agent_id=agent.id, title="Tractor 2", content="Spare parts", post_embedding=unwanted_vec, status="ROUTED")
        db.add_all([post1, post2])
        db.commit()

        # 2 repeatedly ignored notifications (status = QUALIFIED)
        log1 = RoutingLog(post_id=post1.id, target_agent_id=agent.id, vector_score=0.76, rerank_score=0.77, final_score=0.77, status="QUALIFIED")
        log2 = RoutingLog(post_id=post2.id, target_agent_id=agent.id, vector_score=0.76, rerank_score=0.77, final_score=0.77, status="QUALIFIED")
        db.add_all([log1, log2])
        db.commit()

        service = FeedbackService(db=db, learning_rate_neg=0.08)
        updated_vec = service.update_dynamic_preferences(agent.id, db_session=db)

        # Similarity to unwanted topic should have DECREASED
        new_sim = _cosine_similarity(updated_vec, unwanted_vec)
        assert new_sim < initial_sim

        db.delete(agent)
        db.commit()
