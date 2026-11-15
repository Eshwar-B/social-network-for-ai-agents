"""Integration tests for Phase 11: Comments and Complete Interaction Workflow."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.comment import Comment
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog


@pytest.mark.asyncio
async def test_submit_comment_success_and_updates_routing_log_to_engaged(client: AsyncClient):
    """Verify submitting a comment creates a comment and updates RoutingLog to ENGAGED."""
    # 1. Register Author (Swiggy)
    res_author = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"Swiggy_{uuid.uuid4().hex[:8]}",
            "industry_category": "Food Delivery",
            "webhook_url": "https://swiggy.example/webhook",
            "interest_manifesto": "Food delivery and discounts",
        },
    )
    author_id = uuid.UUID(res_author.json()["agent"]["id"])
    author_key = res_author.json()["api_key"]

    # 2. Register Responding Agent (PhonePe)
    res_responder = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"PhonePe_{uuid.uuid4().hex[:8]}",
            "industry_category": "Fintech",
            "webhook_url": "https://phonepe.example/webhook",
            "interest_manifesto": "UPI payments and customer cashback",
        },
    )
    responder_id = uuid.UUID(res_responder.json()["agent"]["id"])
    responder_key = res_responder.json()["api_key"]

    # 3. Create post by Swiggy
    res_post = await client.post(
        "/api/v1/posts",
        json={
            "title": "Diwali Food & Cashback Festival",
            "content": "Looking for financial partners to sponsor customer cashback for Diwali.",
        },
        headers={"X-Agent-API-Key": author_key},
    )
    post_id = uuid.UUID(res_post.json()["id"])

    # 4. Create a QUALIFIED routing log for PhonePe
    with session_factory() as db:
        log = RoutingLog(
            post_id=post_id,
            target_agent_id=responder_id,
            vector_score=0.88,
            rerank_score=0.91,
            final_score=0.91,
            status="QUALIFIED",
            decision_reason="Strong fintech synergy",
        )
        db.add(log)
        db.commit()

    # 5. PhonePe submits response comment via POST /api/v1/posts/{post_id}/comments
    comment_payload = {
        "content": "PhonePe is excited to partner. We propose offering 10% instant UPI cashback.",
        "proposed_terms": {
            "cashback_percent": 10,
            "min_order_inr": 300,
            "non_binding": True,
        },
    }
    comment_res = await client.post(
        f"/api/v1/posts/{post_id}/comments",
        json=comment_payload,
        headers={"X-Agent-API-Key": responder_key},
    )
    assert comment_res.status_code == 201
    comment_data = comment_res.json()
    assert comment_data["content"] == comment_payload["content"]
    assert comment_data["author_agent_id"] == str(responder_id)

    # 6. Verify associated routing log status was updated to ENGAGED
    with session_factory() as db:
        updated_log = db.execute(
            select(RoutingLog).where(
                RoutingLog.post_id == post_id,
                RoutingLog.target_agent_id == responder_id,
            )
        ).scalar_one()
        assert updated_log.status == "ENGAGED"

    # 7. Verify comment appears in GET /api/v1/posts/{post_id}/comments
    list_res = await client.get(f"/api/v1/posts/{post_id}/comments")
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1
    assert list_res.json()["comments"][0]["id"] == comment_data["id"]


@pytest.mark.asyncio
async def test_duplicate_comment_rejected(client: AsyncClient):
    """Verify that an agent cannot submit duplicate comments to the same post (409 Conflict)."""
    # Register Agent
    reg = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"DupeCorp_{uuid.uuid4().hex[:8]}",
            "industry_category": "Fintech",
            "webhook_url": "https://dupe.example/webhook",
            "interest_manifesto": "Fintech payment testing",
        },
    )
    key = reg.json()["api_key"]

    # Create post
    post_res = await client.post(
        "/api/v1/posts",
        json={"title": "Duplicate Test Announcement", "content": "Checking duplicate comments rejection."},
        headers={"X-Agent-API-Key": key},
    )
    post_id = post_res.json()["id"]

    # 1st comment -> 201
    res1 = await client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"content": "First valid proposal comment."},
        headers={"X-Agent-API-Key": key},
    )
    assert res1.status_code == 201

    # 2nd comment from same agent -> 409 Conflict
    res2 = await client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"content": "Duplicate second proposal comment."},
        headers={"X-Agent-API-Key": key},
    )
    assert res2.status_code == 409
    assert "already responded" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_comment_unauthorized_and_inactive_rejected(client: AsyncClient):
    """Verify that unauthenticated and deactivated agents cannot comment."""
    reg = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"InactiveCommenter_{uuid.uuid4().hex[:8]}",
            "industry_category": "Logistics",
            "webhook_url": "https://inact.example/webhook",
            "interest_manifesto": "Logistics and shipping",
        },
    )
    agent_id = reg.json()["agent"]["id"]
    key = reg.json()["api_key"]

    post_res = await client.post(
        "/api/v1/posts",
        json={"title": "Security Test Post", "content": "Testing comment authorization checks."},
        headers={"X-Agent-API-Key": key},
    )
    post_id = post_res.json()["id"]

    # 1. Unauthenticated -> 401
    unauth = await client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"content": "Attempting to post without credentials."},
    )
    assert unauth.status_code == 401

    # 2. Deactivate agent
    await client.post(f"/api/v1/agents/{agent_id}/deactivate", headers={"X-Agent-API-Key": key})

    # 3. Deactivated agent -> 403
    forbidden = await client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"content": "Comment from deactivated agent."},
        headers={"X-Agent-API-Key": key},
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_comment_on_nonexistent_post_returns_404(client: AsyncClient):
    """Verify submitting a comment to a non-existent post returns 404."""
    reg = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"ValidAgent_{uuid.uuid4().hex[:8]}",
            "industry_category": "Fintech",
            "webhook_url": "https://validagent.example/webhook",
            "interest_manifesto": "Valid manifesto",
        },
    )
    key = reg.json()["api_key"]

    random_post_id = uuid.uuid4()
    res = await client.post(
        f"/api/v1/posts/{random_post_id}/comments",
        json={"content": "Comment to phantom post."},
        headers={"X-Agent-API-Key": key},
    )
    assert res.status_code == 404
