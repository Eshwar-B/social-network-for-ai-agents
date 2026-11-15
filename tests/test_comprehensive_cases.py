"""Comprehensive test suite covering all types of test cases:
- Boundary values and threshold limits
- Security and authentication schemes (Bearer, ApiKey, HMAC, impersonation)
- Negative test cases (404 Not Found, 422 Unprocessable, 401 Unauthorized, 403 Forbidden, 409 Conflict)
- Pipeline edge cases (empty candidate pool, missing embeddings, idempotent retries)
- Worker resiliency against corrupted/missing stream messages
"""

import json
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.redis import get_redis_client
from app.core.security import generate_agent_api_key, hash_api_key, verify_api_key
from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog
from app.routing.reranker import MockRerankerProvider, RerankCandidate
from app.services.embedding_provider import MockEmbeddingProvider
from app.services.routing_service import RoutingService
from app.workers.stream_consumer import StreamConsumer


# ============================================================================
# 1. API NEGATIVE CASES & NOT FOUND (404) TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_get_nonexistent_agent_returns_404(client: AsyncClient):
    """Verify that querying a random non-existent agent UUID returns 404."""
    random_id = uuid.uuid4()
    response = await client.get(f"/api/v1/agents/{random_id}")
    assert response.status_code == 404
    assert f"Agent with ID '{random_id}' was not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_nonexistent_post_returns_404(client: AsyncClient):
    """Verify that querying a random non-existent post UUID returns 404."""
    random_id = uuid.uuid4()
    response = await client.get(f"/api/v1/posts/{random_id}")
    assert response.status_code == 404
    assert f"Post with ID '{random_id}' was not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_nonexistent_post_comments_returns_404(client: AsyncClient):
    """Verify that querying comments on a non-existent post returns 404."""
    random_id = uuid.uuid4()
    response = await client.get(f"/api/v1/posts/{random_id}/comments")
    assert response.status_code == 404
    assert f"Post with ID '{random_id}' was not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_uuid_returns_422(client: AsyncClient):
    """Verify that passing an invalid UUID string in path returns 422."""
    response = await client.get("/api/v1/agents/not-a-valid-uuid")
    assert response.status_code == 422

    post_resp = await client.get("/api/v1/posts/invalid-post-uuid")
    assert post_resp.status_code == 422


# ============================================================================
# 2. PAGINATION BOUNDARY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_agent_pagination_bounds(client: AsyncClient):
    """Verify pagination validation boundaries for agents endpoint."""
    # Negative offset -> 422
    res_neg_offset = await client.get("/api/v1/agents?offset=-1")
    assert res_neg_offset.status_code == 422

    # Zero limit -> 422
    res_zero_limit = await client.get("/api/v1/agents?limit=0")
    assert res_zero_limit.status_code == 422

    # Limit > 100 -> 422
    res_high_limit = await client.get("/api/v1/agents?limit=101")
    assert res_high_limit.status_code == 422

    # Normal valid limit -> 200
    res_valid = await client.get("/api/v1/agents?limit=10&offset=0")
    assert res_valid.status_code == 200


@pytest.mark.asyncio
async def test_post_pagination_bounds(client: AsyncClient):
    """Verify pagination validation boundaries for posts endpoint."""
    # Negative offset -> 422
    res_neg = await client.get("/api/v1/posts?offset=-5")
    assert res_neg.status_code == 422

    # Zero limit -> 422
    res_zero = await client.get("/api/v1/posts?limit=0")
    assert res_zero.status_code == 422

    # Limit > 100 -> 422
    res_high = await client.get("/api/v1/posts?limit=150")
    assert res_high.status_code == 422


# ============================================================================
# 3. SECURITY, CRYPTOGRAPHY & AUTHENTICATION SCHEMES
# ============================================================================

def test_security_api_key_lifecycle_and_helpers():
    """Verify API key generation, prefix, and constant-time HMAC hashing."""
    key = generate_agent_api_key()
    assert key.startswith("asama_ak_")
    assert len(key) >= 40

    hashed = hash_api_key(key)
    assert len(hashed) == 64  # SHA-256 hex digest

    # Correct key matches
    assert verify_api_key(key, hashed) is True

    # Tampered key rejected
    tampered_key = key[:-1] + ("0" if key[-1] != "0" else "1")
    assert verify_api_key(tampered_key, hashed) is False

    # Empty key rejected
    assert verify_api_key("", hashed) is False


@pytest.mark.asyncio
async def test_security_bearer_and_apikey_header_prefixes(client: AsyncClient):
    """Verify that Authorization: Bearer <key> and Authorization: ApiKey <key> are accepted."""
    company = f"AuthTestCorp_{uuid.uuid4().hex[:8]}"
    reg_res = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": company,
            "industry_category": "Fintech",
            "webhook_url": "https://authtest.example/webhook",
            "interest_manifesto": "Valid manifesto for auth testing.",
        },
    )
    assert reg_res.status_code == 201
    agent_id = reg_res.json()["agent"]["id"]
    api_key = reg_res.json()["api_key"]

    # 1. Update using Authorization: Bearer <api_key>
    bearer_res = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"webhook_url": "https://bearer-updated.example/webhook"},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert bearer_res.status_code == 200
    assert bearer_res.json()["webhook_url"] == "https://bearer-updated.example/webhook"

    # 2. Update using Authorization: ApiKey <api_key>
    apikey_res = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"webhook_url": "https://apikey-updated.example/webhook"},
        headers={"Authorization": f"ApiKey {api_key}"},
    )
    assert apikey_res.status_code == 200
    assert apikey_res.json()["webhook_url"] == "https://apikey-updated.example/webhook"


@pytest.mark.asyncio
async def test_security_wrong_api_key_returns_401(client: AsyncClient):
    """Verify that an invalid/fabricated API key returns 401 Unauthorized."""
    res = await client.post(
        "/api/v1/posts",
        json={
            "title": "Unauthenticated Post",
            "content": "This content should not be published due to bad key.",
        },
        headers={"X-Agent-API-Key": "asama_ak_invalid_fabricated_key_12345"},
    )
    assert res.status_code == 401
    assert "Invalid Agent API key" in res.json()["detail"]


@pytest.mark.asyncio
async def test_security_impersonation_protection_activate_deactivate(client: AsyncClient):
    """Verify that Agent B cannot activate or deactivate Agent A's profile."""
    # Register Agent A
    res_a = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"AgentA_{uuid.uuid4().hex[:8]}",
            "industry_category": "Logistics",
            "webhook_url": "https://agenta.example/webhook",
            "interest_manifesto": "Manifesto for Agent A in logistics",
        },
    )
    agent_a_id = res_a.json()["agent"]["id"]

    # Register Agent B
    res_b = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"AgentB_{uuid.uuid4().hex[:8]}",
            "industry_category": "Retail",
            "webhook_url": "https://agentb.example/webhook",
            "interest_manifesto": "Manifesto for Agent B in retail",
        },
    )
    api_key_b = res_b.json()["api_key"]

    # Agent B tries to deactivate Agent A -> 403 Forbidden
    deact_res = await client.post(
        f"/api/v1/agents/{agent_a_id}/deactivate",
        headers={"X-Agent-API-Key": api_key_b},
    )
    assert deact_res.status_code == 403
    assert "Not authorized" in deact_res.json()["detail"]

    # Agent B tries to activate Agent A -> 403 Forbidden
    act_res = await client.post(
        f"/api/v1/agents/{agent_a_id}/activate",
        headers={"X-Agent-API-Key": api_key_b},
    )
    assert act_res.status_code == 403
    assert "Not authorized" in act_res.json()["detail"]


# ============================================================================
# 4. BOUNDARY VALUES FOR STRING LENGTHS
# ============================================================================

@pytest.mark.asyncio
async def test_boundary_manifesto_min_length(client: AsyncClient):
    """Verify manifesto boundary: 9 chars fails (422), 10 chars succeeds (201)."""
    # 9 chars -> 422
    res_9 = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"BoundCorp_{uuid.uuid4().hex[:8]}",
            "industry_category": "Testing",
            "webhook_url": "https://bound.example/webhook",
            "interest_manifesto": "123456789",  # 9 chars
        },
    )
    assert res_9.status_code == 422

    # 10 chars -> 201
    res_10 = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"BoundCorp_{uuid.uuid4().hex[:8]}",
            "industry_category": "Testing",
            "webhook_url": "https://bound.example/webhook",
            "interest_manifesto": "1234567890",  # exactly 10 chars
        },
    )
    assert res_10.status_code == 201


@pytest.mark.asyncio
async def test_boundary_post_title_and_content_length(client: AsyncClient):
    """Verify post boundaries: title min 3 chars, content min 10 chars."""
    reg = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"PostBoundCorp_{uuid.uuid4().hex[:8]}",
            "industry_category": "Testing",
            "webhook_url": "https://postbound.example/webhook",
            "interest_manifesto": "Valid manifesto length for post boundary test.",
        },
    )
    key = reg.json()["api_key"]

    # Title 2 chars -> 422
    res_title_2 = await client.post(
        "/api/v1/posts",
        json={"title": "12", "content": "Valid content of sufficient length."},
        headers={"X-Agent-API-Key": key},
    )
    assert res_title_2.status_code == 422

    # Content 9 chars -> 422
    res_content_9 = await client.post(
        "/api/v1/posts",
        json={"title": "Valid Title", "content": "123456789"},
        headers={"X-Agent-API-Key": key},
    )
    assert res_content_9.status_code == 422

    # Title 3 chars, content 10 chars -> 201
    res_exact_min = await client.post(
        "/api/v1/posts",
        json={"title": "123", "content": "1234567890"},
        headers={"X-Agent-API-Key": key},
    )
    assert res_exact_min.status_code == 201


# ============================================================================
# 5. ROUTING ENGINE EDGE CASES & RESILIENCY
# ============================================================================

@pytest.mark.asyncio
async def test_routing_empty_candidate_pool():
    """Verify that when no other agents exist, routing handles empty candidate pool gracefully."""
    provider = MockEmbeddingProvider(dimension=1536)
    with session_factory() as db:
        # Sole author agent
        author = Agent(
            company_name=f"LonelyAuthor_{uuid.uuid4().hex[:8]}",
            industry_category="Autonomous",
            webhook_url="https://lonely.example/webhook",
            interest_manifesto="Operating completely alone with no partners",
            interest_embedding=await provider.embed_text("Operating alone"),
            embedding_status="COMPLETED",
            api_key_hash=f"hash_{uuid.uuid4().hex}",
        )
        db.add(author)
        db.commit()

        post = Post(
            author_agent_id=author.id,
            title="Announcement with no candidates",
            content="Nobody else exists in the network to receive this notification.",
            post_embedding=await provider.embed_text("Announcement alone"),
            status="PENDING",
        )
        db.add(post)
        db.commit()
        post_id = post.id

        # Route with explicit empty candidate list
        service = RoutingService(db=db)
        result = await service.route_post(
            post_id=post_id,
            db_session=db,
            eligible_agent_ids=[],
        )

        assert result.stage_a_eligible_count == 0
        assert result.qualified_count == 0
        assert result.qualified_recipients == []
        assert result.rejected_candidates == []

        # Post status updated to ROUTED
        db.refresh(post)
        assert post.status == "ROUTED"

        # Clean up
        db.delete(author)
        db.commit()


@pytest.mark.asyncio
async def test_routing_post_not_found_raises_error():
    """Verify that attempting to route a non-existent post raises ValueError."""
    service = RoutingService()
    with pytest.raises(ValueError, match="not found for routing"):
        await service.route_post(post_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_routing_post_missing_embedding_raises_error():
    """Verify that routing a post without embedding raises ValueError."""
    with session_factory() as db:
        author = Agent(
            company_name=f"NoEmbedAuthor_{uuid.uuid4().hex[:8]}",
            industry_category="Testing",
            webhook_url="https://noembed.example/webhook",
            interest_manifesto="Author testing missing embedding handling",
            api_key_hash=f"hash_{uuid.uuid4().hex}",
            embedding_status="COMPLETED",
        )
        db.add(author)
        db.commit()

        post = Post(
            author_agent_id=author.id,
            title="Post Without Embedding",
            content="This post intentionally has no vector embedding.",
            post_embedding=None,  # Missing!
            status="PENDING",
        )
        db.add(post)
        db.commit()
        post_id = post.id

        service = RoutingService(db=db)
        with pytest.raises(ValueError, match="has no vector embedding"):
            await service.route_post(post_id=post_id, db_session=db)

        # Clean up
        db.delete(author)
        db.commit()


@pytest.mark.asyncio
async def test_routing_idempotency_no_duplicate_logs():
    """Verify that executing route_post twice does not produce duplicate routing logs."""
    provider = MockEmbeddingProvider(dimension=1536)
    with session_factory() as db:
        author = Agent(
            company_name=f"IdemRouteAuthor_{uuid.uuid4().hex[:8]}",
            industry_category="Fintech",
            webhook_url="https://idemroute.example/webhook",
            interest_manifesto="Fintech partnership routing",
            interest_embedding=await provider.embed_text("Fintech manifesto"),
            embedding_status="COMPLETED",
            api_key_hash=f"hash_{uuid.uuid4().hex}",
        )
        recipient = Agent(
            company_name=f"IdemRouteTarget_{uuid.uuid4().hex[:8]}",
            industry_category="Fintech",
            webhook_url="https://idemtarget.example/webhook",
            interest_manifesto="Fintech cashback partnerships",
            interest_embedding=await provider.embed_text("Fintech cashback manifesto"),
            embedding_status="COMPLETED",
            api_key_hash=f"hash_{uuid.uuid4().hex}",
        )
        db.add_all([author, recipient])
        db.commit()

        post = Post(
            author_agent_id=author.id,
            title="Idempotent Routing Test",
            content="Fintech promotion to test duplicate routing log prevention.",
            post_embedding=await provider.embed_text("Fintech post content"),
            status="PENDING",
        )
        db.add(post)
        db.commit()
        post_id = post.id

        service = RoutingService(db=db)
        # First execution
        await service.route_post(post_id, db_session=db, eligible_agent_ids=[recipient.id])
        logs_first = db.execute(select(RoutingLog).where(RoutingLog.post_id == post_id)).scalars().all()
        assert len(logs_first) == 1

        # Second execution (retry)
        await service.route_post(post_id, db_session=db, eligible_agent_ids=[recipient.id])
        logs_second = db.execute(select(RoutingLog).where(RoutingLog.post_id == post_id)).scalars().all()
        # Must still be exactly 1 record!
        assert len(logs_second) == 1

        # Clean up
        db.delete(author)
        db.delete(recipient)
        db.commit()


@pytest.mark.asyncio
async def test_reranker_exact_boundary_thresholds():
    """Verify threshold boundary: final_score >= 0.75 is QUALIFIED, < 0.75 is REJECTED_THRESHOLD."""
    reranker = MockRerankerProvider(threshold=0.75)

    # Candidate A: calibrated to high similarity (>= 0.75)
    cand_a = RerankCandidate(
        agent_id=uuid.uuid4(),
        company_name="QualifyCorp",
        industry_category="Fintech",
        webhook_url="https://qualify.example/webhook",
        interest_manifesto="Exclusive Diwali instant discounts for UPI cashback payment offers",
        vector_score=0.90,
        trust_score=1.0,
    )
    # Candidate B: unrelated (< 0.75)
    cand_b = RerankCandidate(
        agent_id=uuid.uuid4(),
        company_name="RejectCorp",
        industry_category="Automotive",
        webhook_url="https://reject.example/webhook",
        interest_manifesto="Commercial diesel engines and spare tractor axles",
        vector_score=0.15,
        trust_score=1.0,
    )

    results = await reranker.rerank(
        post_title="Diwali Food Delivery Discount Offer",
        post_content="Instant discounts on food delivery orders paying with UPI cashback partners.",
        candidates=[cand_a, cand_b],
    )

    res_a = next(r for r in results if r.company_name == "QualifyCorp")
    res_b = next(r for r in results if r.company_name == "RejectCorp")

    assert res_a.final_score >= 0.75
    assert res_a.is_qualified is True
    assert res_a.rejection_reason is None

    assert res_b.final_score < 0.75
    assert res_b.is_qualified is False
    assert "below required threshold" in res_b.rejection_reason


# ============================================================================
# 6. STREAM CONSUMER RESILIENCY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_stream_consumer_corrupt_message_resilience():
    """Verify worker gracefully handles corrupted or malformed JSON payloads in Redis Stream."""
    stream_key = f"asama:test:corrupt:{uuid.uuid4().hex[:8]}"
    group_key = f"asama:test:group:{uuid.uuid4().hex[:8]}"

    redis_client = get_redis_client()
    await redis_client.xgroup_create(stream_key, group_key, id="0", mkstream=True)

    # Inject a corrupted message (not valid JSON payload)
    await redis_client.xadd(stream_key, {"event_type": "post.published", "payload": "{malformed_json: true,"})

    consumer = StreamConsumer(
        stream_key=stream_key,
        consumer_group=group_key,
        consumer_name="resilient_worker",
    )

    # Worker must process and acknowledge without raising an unhandled exception
    processed = await consumer.run_once()
    assert processed >= 1

    # Verify message was acknowledged
    pending = await redis_client.xpending(stream_key, group_key)
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_stream_consumer_nonexistent_post_resilience():
    """Verify worker gracefully handles stream event pointing to non-existent post."""
    stream_key = f"asama:test:orphan:{uuid.uuid4().hex[:8]}"
    group_key = f"asama:test:group:{uuid.uuid4().hex[:8]}"

    redis_client = get_redis_client()
    await redis_client.xgroup_create(stream_key, group_key, id="0", mkstream=True)

    orphan_event = {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "post_id": str(uuid.uuid4()),  # Does not exist in PostgreSQL!
        "author_agent_id": str(uuid.uuid4()),
    }
    await redis_client.xadd(stream_key, {"event_type": "post.published", "payload": json.dumps(orphan_event)})

    consumer = StreamConsumer(
        stream_key=stream_key,
        consumer_group=group_key,
        consumer_name="resilient_worker_2",
    )

    # Worker must handle the missing post gracefully and acknowledge
    processed = await consumer.run_once()
    assert processed >= 1

    pending = await redis_client.xpending(stream_key, group_key)
    assert pending["pending"] == 0


# ============================================================================
# 7. FILTERING & LISTING PARAMETER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_agent_listing_is_active_filter(client: AsyncClient):
    """Verify listing agents with is_active=true vs is_active=false query parameters."""
    company = f"FilterCorp_{uuid.uuid4().hex[:8]}"
    reg = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": company,
            "industry_category": "Logistics",
            "webhook_url": "https://filter.example/webhook",
            "interest_manifesto": "Valid manifesto for active filtering test.",
        },
    )
    agent_id = reg.json()["agent"]["id"]
    api_key = reg.json()["api_key"]

    # Initially active
    list_active = await client.get("/api/v1/agents?is_active=true&limit=100")
    assert list_active.status_code == 200
    assert any(a["id"] == agent_id for a in list_active.json()["agents"])

    # Deactivate
    await client.post(f"/api/v1/agents/{agent_id}/deactivate", headers={"X-Agent-API-Key": api_key})

    # Now verify it appears under is_active=false and not under is_active=true
    list_active_after = await client.get("/api/v1/agents?is_active=true&limit=100")
    assert not any(a["id"] == agent_id for a in list_active_after.json()["agents"])

    list_inactive = await client.get("/api/v1/agents?is_active=false&limit=100")
    assert any(a["id"] == agent_id for a in list_inactive.json()["agents"])


@pytest.mark.asyncio
async def test_post_listing_status_filter(client: AsyncClient):
    """Verify listing posts with status query parameter."""
    company = f"PostStatusCorp_{uuid.uuid4().hex[:8]}"
    reg = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": company,
            "industry_category": "Fintech",
            "webhook_url": "https://poststatus.example/webhook",
            "interest_manifesto": "Fintech promotional manifesto for status test.",
        },
    )
    key = reg.json()["api_key"]

    post = await client.post(
        "/api/v1/posts",
        json={"title": "Status Filter Announcement", "content": "Checking status query filter in post listing."},
        headers={"X-Agent-API-Key": key},
    )
    post_id = post.json()["id"]

    # Filter by status=PENDING
    res_pending = await client.get("/api/v1/posts?status=PENDING&limit=100")
    assert res_pending.status_code == 200
    assert any(p["id"] == post_id for p in res_pending.json()["posts"])

    # Filter by non-existent status
    res_other = await client.get("/api/v1/posts?status=ARCHIVED&limit=100")
    assert res_other.status_code == 200
    assert not any(p["id"] == post_id for p in res_other.json()["posts"])
