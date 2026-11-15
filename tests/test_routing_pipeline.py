"""Comprehensive integration test suite for Phase 8: Three-Stage Semantic Relevance Routing Engine."""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog
from app.main import app
from app.routing.reranker import MockRerankerProvider, RerankCandidate
from app.services.embedding_provider import MockEmbeddingProvider
from app.services.routing_service import RoutingService
from app.workers.stream_consumer import StreamConsumer


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_reranker_threshold_and_limit_enforcement():
    """Verify that MockReranker strictly enforces the 0.75 threshold."""
    reranker = MockRerankerProvider(threshold=0.75)
    candidates = [
        RerankCandidate(
            agent_id=uuid.uuid4(),
            company_name="HighRelevanceCorp",
            industry_category="Fintech",
            webhook_url="https://high.example/webhook",
            interest_manifesto="Diwali food delivery discounts, UPI cashback payment partnerships",
            vector_score=0.92,
            trust_score=1.0,
        ),
        RerankCandidate(
            agent_id=uuid.uuid4(),
            company_name="LowRelevanceCorp",
            industry_category="Automobile",
            webhook_url="https://low.example/webhook",
            interest_manifesto="Heavy tractor diesel engines and machinery spare parts",
            vector_score=0.15,
            trust_score=1.0,
        ),
    ]

    results = await reranker.rerank(
        post_title="Diwali Food Delivery Festive Offer",
        post_content="Offering 10% instant discount for customers paying with UPI cashback partners.",
        candidates=candidates,
    )

    high_cand = next(r for r in results if r.company_name == "HighRelevanceCorp")
    low_cand = next(r for r in results if r.company_name == "LowRelevanceCorp")

    assert high_cand.final_score >= 0.75
    assert high_cand.is_qualified is True
    assert high_cand.rejection_reason is None

    assert low_cand.final_score < 0.75
    assert low_cand.is_qualified is False
    assert "below required threshold" in low_cand.rejection_reason


@pytest.mark.asyncio
async def test_maximum_five_recipients_limit_enforced():
    """Verify that even when 7 candidates qualify, at most 5 are selected, and remainder marked REJECTED_LIMIT."""
    with session_factory() as db:
        provider = MockEmbeddingProvider(dimension=1536)

        # 1. Author Agent
        author = Agent(
            company_name=f"AuthorLimit_{uuid.uuid4().hex[:8]}",
            industry_category="Fintech",
            webhook_url="https://author.example/webhook",
            interest_manifesto="Fintech payment promotions",
            interest_embedding=await provider.embed_text("Fintech payment promotions"),
            embedding_status="COMPLETED",
            api_key_hash=f"hash_{uuid.uuid4().hex}",
        )
        db.add(author)

        # 2. Create 7 identical high-scoring agents
        candidates = []
        for i in range(7):
            manifesto = "Diwali festive cashback discounts, UPI payment campaigns, food promotions"
            vec = await provider.embed_text(manifesto)
            agent = Agent(
                company_name=f"FintechCandidate_{i}_{uuid.uuid4().hex[:8]}",
                industry_category="Fintech",
                webhook_url=f"https://candidate{i}.example/webhook",
                interest_manifesto=manifesto,
                interest_embedding=vec,
                embedding_status="COMPLETED",
                api_key_hash=f"hash_{uuid.uuid4().hex}",
            )
            candidates.append(agent)
            db.add(agent)

        db.commit()

        # 3. Create post
        post_text = "Diwali food delivery festive discounts with UPI payment cashback"
        post = Post(
            author_agent_id=author.id,
            title="Diwali Promo",
            content=post_text,
            post_embedding=await provider.embed_text(post_text),
            status="PENDING",
        )
        db.add(post)
        db.commit()
        post_id = post.id

        # 4. Execute 3-stage routing scoping to these 7 candidates
        routing_service = RoutingService(db=db)
        result = await routing_service.route_post(
            post_id,
            db_session=db,
            eligible_agent_ids=[c.id for c in candidates],
        )

        # Verify: Exactly 5 qualified recipients
        assert result.qualified_count == 5
        assert len(result.qualified_recipients) == 5

        # Verify: 2 candidates marked REJECTED_LIMIT
        limit_rejected = [r for r in result.rejected_candidates if r.status == "REJECTED_LIMIT"]
        assert len(limit_rejected) == 2

        # 5. Verify routing_logs persisted in PostgreSQL
        logs = db.execute(
            select(RoutingLog).where(RoutingLog.post_id == post_id)
        ).scalars().all()
        assert len(logs) == 7

        qualified_logs = [l for l in logs if l.status == "QUALIFIED"]
        rejected_limit_logs = [l for l in logs if l.status == "REJECTED_LIMIT"]
        assert len(qualified_logs) == 5
        assert len(rejected_limit_logs) == 2

        # Clean up test-specific agents to ensure test isolation
        for c in candidates:
            db.delete(c)
        db.delete(author)
        db.commit()


@pytest.mark.asyncio
async def test_end_to_end_multi_agent_enterprise_routing(client: AsyncClient):
    """Integrated enterprise test: Swiggy, PhonePe, Paytm, Amazon, HDFC Bank, Bajaj Auto.

    Verifies complete pipeline:
    API Registration -> Embedding Gen -> Post Publication -> Redis Stream -> Worker -> 3-Stage Routing -> Routing Logs.
    """
    # Ensure a clean database state for multi-agent enterprise scenario
    with session_factory() as db:
        db.execute(select(Agent)).all()
        # Clean up any leftover agents from earlier unit tests
        from sqlalchemy import text
        db.execute(text("DELETE FROM agents;"))
        db.commit()

    companies = [
        {
            "name": f"Swiggy_{uuid.uuid4().hex[:6]}",
            "industry": "Food Delivery",
            "manifesto": "Online restaurant food delivery, grocery logistics, cloud kitchens",
        },
        {
            "name": f"PhonePe_{uuid.uuid4().hex[:6]}",
            "industry": "Fintech & Payments",
            "manifesto": "Digital payments, online food delivery cashback discounts, UPI payment campaigns",
        },
        {
            "name": f"Paytm_{uuid.uuid4().hex[:6]}",
            "industry": "Fintech & Payments",
            "manifesto": "Merchant QR codes, dining cashback, instant UPI wallet payments",
        },
        {
            "name": f"HDFC_Bank_{uuid.uuid4().hex[:6]}",
            "industry": "Banking",
            "manifesto": "Co-branded credit cards, merchant discounts, festive shopping reward points",
        },
        {
            "name": f"Amazon_{uuid.uuid4().hex[:6]}",
            "industry": "E-Commerce",
            "manifesto": "E-commerce festive sales, electronic goods, household retail fulfillment",
        },
        {
            "name": f"Bajaj_Auto_{uuid.uuid4().hex[:6]}",
            "industry": "Automotive",
            "manifesto": "Commercial two-wheelers, heavy diesel tractors, engine spare parts",
        },
    ]

    registered_agents = {}
    for comp in companies:
        reg_res = await client.post(
            "/api/v1/agents/register",
            json={
                "company_name": comp["name"],
                "industry_category": comp["industry"],
                "webhook_url": f"https://{comp['name'].lower()}.example/webhook",
                "interest_manifesto": comp["manifesto"],
            },
        )
        assert reg_res.status_code == 201
        data = reg_res.json()
        registered_agents[comp["name"]] = {
            "id": uuid.UUID(data["agent"]["id"]),
            "api_key": data["api_key"],
        }

    swiggy_name = companies[0]["name"]
    swiggy_key = registered_agents[swiggy_name]["api_key"]
    swiggy_id = registered_agents[swiggy_name]["id"]

    phonepe_name = companies[1]["name"]
    phonepe_id = registered_agents[phonepe_name]["id"]

    bajaj_name = companies[5]["name"]
    bajaj_id = registered_agents[bajaj_name]["id"]

    # 1. Swiggy publishes a Diwali food delivery announcement seeking UPI cashback partners
    post_res = await client.post(
        "/api/v1/posts",
        json={
            "title": "Swiggy Diwali Festive Food Delivery Discount Offer",
            "content": "Swiggy is offering 10% instant discount on food orders and looking for fintech partners to sponsor UPI cashback.",
        },
        headers={"X-Agent-API-Key": swiggy_key},
    )
    assert post_res.status_code == 201
    post_id = uuid.UUID(post_res.json()["id"])

    # 2. Background consumer processes the stream event and executes the 3-stage routing engine
    consumer = StreamConsumer()
    processed_count = await consumer.run_once()
    assert processed_count >= 1

    # 3. Verify PostgreSQL Routing Logs
    with session_factory() as db:
        post_after = db.execute(select(Post).where(Post.id == post_id)).scalar_one()
        assert post_after.status == "ROUTED"

        logs = db.execute(
            select(RoutingLog).where(RoutingLog.post_id == post_id)
        ).scalars().all()
        assert len(logs) >= 4

        # Author (Swiggy) must NOT be in routing logs (Stage A SQL excluded)
        assert all(l.target_agent_id != swiggy_id for l in logs)

        # PhonePe should be QUALIFIED (score >= 0.75)
        phonepe_log = next((l for l in logs if l.target_agent_id == phonepe_id), None)
        assert phonepe_log is not None
        assert phonepe_log.status == "QUALIFIED"
        assert phonepe_log.final_score >= 0.75
        assert phonepe_log.vector_score > 0.0

        # Bajaj Auto (unrelated tractor company) should be REJECTED_THRESHOLD (score < 0.75)
        bajaj_log = next((l for l in logs if l.target_agent_id == bajaj_id), None)
        assert bajaj_log is not None
        assert bajaj_log.status == "REJECTED_THRESHOLD"
        assert bajaj_log.final_score < 0.75
        assert "below required relevance threshold" in bajaj_log.decision_reason
