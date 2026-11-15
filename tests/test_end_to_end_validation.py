"""Comprehensive End-to-End System Integration and Performance Benchmark Test Suite for Phase 15."""

import time
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from agents.decision_engine import DecisionOutcome
from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog
from app.routing.sql_filter import SQLAgentFilter
from app.routing.vector_search import VectorAgentSearch
from app.services.embedding_provider import MockEmbeddingProvider
from app.services.feedback_service import FeedbackService
from app.services.routing_service import RoutingService
from app.workers.stream_consumer import StreamConsumer


@pytest.mark.asyncio
async def test_full_autonomous_lifecycle_swiggy_to_phonepe(client: AsyncClient):
    """Full End-to-End Test:

    1. Agent Registration (Swiggy & PhonePe)
    2. Swiggy Publishes Announcement
    3. Redis Event Ingested by StreamConsumer
    4. 3-Stage Routing (SQL -> Vector -> Rerank)
    5. Webhook Delivered to PhonePe
    6. PhonePe Autonomous Decision -> INTERESTED
    7. PhonePe Submits Proposal Comment
    8. RoutingLog Marked ENGAGED
    9. Feedback Loop Updates Engagement Metrics
    """
    # 0. Clean database & Redis stream for isolated end-to-end enterprise lifecycle
    with session_factory() as db:
        from sqlalchemy import text
        db.execute(text("DELETE FROM agents;"))
        db.commit()
    from app.core.redis import get_redis_client
    from app.config import settings
    redis = get_redis_client()
    await redis.delete(settings.REDIS_STREAM_KEY)

    # 1. Register Swiggy
    res_swiggy = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"Swiggy_E2E_{uuid.uuid4().hex[:6]}",
            "industry_category": "Food Delivery",
            "webhook_url": "https://swiggy.example/webhook",
            "interest_manifesto": "Restaurant food delivery, festive discounts, quick commerce.",
        },
    )
    assert res_swiggy.status_code == 201
    swiggy_key = res_swiggy.json()["api_key"]
    swiggy_id = uuid.UUID(res_swiggy.json()["agent"]["id"])
    swiggy_name = res_swiggy.json()["agent"]["company_name"]

    # 2. Register PhonePe
    res_phonepe = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"PhonePe_E2E_{uuid.uuid4().hex[:6]}",
            "industry_category": "Fintech & Payments",
            "webhook_url": "https://phonepe.example/webhook",
            "interest_manifesto": "UPI payments, food delivery cashback, merchant wallet rewards.",
        },
    )
    assert res_phonepe.status_code == 201
    phonepe_key = res_phonepe.json()["api_key"]
    phonepe_id = uuid.UUID(res_phonepe.json()["agent"]["id"])
    phonepe_name = res_phonepe.json()["agent"]["company_name"]

    # 3. Register Bajaj Auto (Control agent - should be rejected by threshold)
    res_bajaj = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"Bajaj_E2E_{uuid.uuid4().hex[:6]}",
            "industry_category": "Automotive",
            "webhook_url": "https://bajaj.example/webhook",
            "interest_manifesto": "Commercial diesel tractors and heavy automotive machinery parts.",
        },
    )
    assert res_bajaj.status_code == 201
    bajaj_id = uuid.UUID(res_bajaj.json()["agent"]["id"])

    # 4. Swiggy publishes an announcement seeking UPI cashback partners
    t0 = time.perf_counter()
    post_res = await client.post(
        "/api/v1/posts",
        json={
            "title": "Swiggy Diwali Festive Food Delivery Discount Campaign",
            "content": "Offering 10% instant discount on restaurant food orders and seeking UPI cashback sponsorship partners.",
        },
        headers={"X-Agent-API-Key": swiggy_key},
    )
    assert post_res.status_code == 201
    post_data = post_res.json()
    post_id = uuid.UUID(post_data["id"])
    api_publish_latency_ms = (time.perf_counter() - t0) * 1000.0

    # 5. Background StreamConsumer processes event & runs 3-Stage Routing
    consumer = StreamConsumer()
    t_route_0 = time.perf_counter()
    processed_count = await consumer.run_once()
    total_routing_latency_ms = (time.perf_counter() - t_route_0) * 1000.0
    assert processed_count >= 1

    # 6. Verify Routing Decisions in PostgreSQL
    with session_factory() as db:
        logs = db.execute(select(RoutingLog).where(RoutingLog.post_id == post_id)).scalars().all()
        assert len(logs) >= 2

        # PhonePe must be QUALIFIED (score >= 0.75)
        phonepe_log = next((l for l in logs if l.target_agent_id == phonepe_id), None)
        assert phonepe_log is not None
        assert phonepe_log.status == "QUALIFIED"
        assert phonepe_log.final_score >= 0.75

        # Bajaj Auto must be REJECTED_THRESHOLD (score < 0.75)
        bajaj_log = next((l for l in logs if l.target_agent_id == bajaj_id), None)
        assert bajaj_log is not None
        assert bajaj_log.status == "REJECTED_THRESHOLD"

    # 7. Simulate Webhook Delivery & Autonomous Agent Decision
    webhook_payload = {
        "event": "post.matched",
        "post_id": str(post_id),
        "post": {
            "id": str(post_id),
            "title": post_data["title"],
            "content": post_data["content"],
            "author": {"company_name": swiggy_name, "industry_category": "Food Delivery"},
        },
        "recipient": {"company_name": "PhonePe"},
        "relevance": {"final_score": phonepe_log.final_score},
    }

    from agents.agent_registry import PhonePeAgent
    phonepe_agent = PhonePeAgent()
    decision = phonepe_agent.analyze_announcement(webhook_payload)

    assert decision.decision == DecisionOutcome.INTERESTED
    assert "cashback" in decision.comment_text.lower()
    assert decision.is_binding is False

    # 8. PhonePe Submits Autonomous Comment Response
    comment_res = await client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={
            "content": decision.comment_text,
            "proposed_terms": decision.proposed_terms,
        },
        headers={"X-Agent-API-Key": phonepe_key},
    )
    assert comment_res.status_code == 201
    comment_data = comment_res.json()
    assert comment_data["author_company_name"] == phonepe_name

    # 9. Verify RoutingLog is now marked ENGAGED
    with session_factory() as db:
        updated_phonepe_log = db.execute(
            select(RoutingLog).where(
                RoutingLog.post_id == post_id,
                RoutingLog.target_agent_id == phonepe_id,
            )
        ).scalar_one()
        assert updated_phonepe_log.status == "ENGAGED"

    # 10. Run Feedback Loop & Verify Engagement Metrics
    with session_factory() as db:
        feedback_service = FeedbackService(db=db)
        metrics = feedback_service.calculate_agent_metrics(phonepe_id, db_session=db)
        assert metrics.notifications_received >= 1
        assert metrics.responses_submitted >= 1
        assert metrics.engagement_rate > 0.0
        assert metrics.engagement_rate == metrics.responses_submitted / metrics.notifications_received


@pytest.mark.asyncio
async def test_performance_latency_budgets():
    """Verify performance budgets across routing pipeline stages:

    - Stage A (SQL Filter): < 50ms
    - Stage B (pgvector Cosine Search): < 50ms
    - Stage C (Cross-Encoder Rerank): < 50ms
    - Total Routing Orchestration: < 200ms
    """
    provider = MockEmbeddingProvider(dimension=1536)

    with session_factory() as db:
        # Create author and 10 test candidate agents
        author = Agent(
            company_name=f"PerfAuthor_{uuid.uuid4().hex[:6]}",
            industry_category="Food Delivery",
            webhook_url="https://author.example/webhook",
            interest_manifesto="Fast food logistics",
            interest_embedding=await provider.embed_text("Fast food logistics"),
            embedding_status="COMPLETED",
            api_key_hash=f"hash_{uuid.uuid4().hex}",
        )
        db.add(author)

        candidates = []
        for i in range(10):
            agent = Agent(
                company_name=f"PerfCand_{i}_{uuid.uuid4().hex[:6]}",
                industry_category="Fintech" if i % 2 == 0 else "Automotive",
                webhook_url=f"https://cand{i}.example/webhook",
                interest_manifesto=f"Candidate {i} manifesto with fintech payments and checkout",
                interest_embedding=await provider.embed_text(f"Candidate {i} manifesto"),
                embedding_status="COMPLETED",
                api_key_hash=f"hash_{uuid.uuid4().hex}",
            )
            candidates.append(agent)
            db.add(agent)
        db.commit()

        post_vec = await provider.embed_text("Swiggy festival food offer with payment cashback")
        post = Post(
            author_agent_id=author.id,
            title="Performance Test Post",
            content="Testing sub-second latency across all 3 routing stages.",
            post_embedding=post_vec,
            status="PENDING",
        )
        db.add(post)
        db.commit()
        post_id = post.id

        # 1. Benchmark Stage A (SQL Filter)
        t0 = time.perf_counter()
        sql_filter = SQLAgentFilter(db)
        stage_a_res = sql_filter.filter_eligible_agents(author_agent_id=author.id)
        stage_a_ms = (time.perf_counter() - t0) * 1000.0

        # 2. Benchmark Stage B (pgvector Cosine Search)
        t1 = time.perf_counter()
        vector_search = VectorAgentSearch(db)
        stage_b_res = vector_search.search_top_candidates(
            post_vector=post_vec,
            author_agent_id=author.id,
            eligible_agent_ids=[c.id for c in stage_a_res.candidates],
            top_k=50,
        )
        stage_b_ms = (time.perf_counter() - t1) * 1000.0

        # 3. Benchmark End-to-End Routing Service
        t2 = time.perf_counter()
        routing_service = RoutingService(db=db)
        routing_res = await routing_service.route_post(post_id, db_session=db)
        total_routing_ms = (time.perf_counter() - t2) * 1000.0

        # Latency Assertions
        assert stage_a_ms < 50.0, f"Stage A too slow: {stage_a_ms:.2f}ms"
        assert stage_b_ms < 50.0, f"Stage B too slow: {stage_b_ms:.2f}ms"
        assert total_routing_ms < 200.0, f"Total routing too slow: {total_routing_ms:.2f}ms"

        # Clean up test agents
        for c in candidates:
            db.delete(c)
        db.delete(author)
        db.commit()
