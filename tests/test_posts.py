"""Integration tests for Post creation and management API endpoints."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.database.connection import session_factory
from app.database.models.event import EventProcessing
from app.database.models.post import Post


@pytest.mark.asyncio
async def test_create_post_success(client: AsyncClient):
    """Test successful post creation with embedding and transactional outbox event."""
    # 1. Register an agent
    company = f"PublisherCorp_{uuid.uuid4().hex[:8]}"
    reg_res = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": company,
            "industry_category": "Food Delivery",
            "webhook_url": "https://pub.example/webhook",
            "interest_manifesto": "Food logistics, festive marketing campaigns",
        },
    )
    assert reg_res.status_code == 201
    api_key = reg_res.json()["api_key"]
    author_id = reg_res.json()["agent"]["id"]

    # 2. Publish post
    post_payload = {
        "title": "Diwali 2026 Customer Cashback Offer",
        "content": "Swiggy is launching an exclusive Diwali festival campaign offering 10% instant discounts for UPI payments.",
    }
    post_res = await client.post(
        "/api/v1/posts",
        json=post_payload,
        headers={"X-Agent-API-Key": api_key},
    )
    assert post_res.status_code == 201
    post_data = post_res.json()

    assert post_data["title"] == post_payload["title"]
    assert post_data["author_company_name"] == company
    assert post_data["has_embedding"] is True
    assert post_data["status"] == "PENDING"
    post_id = uuid.UUID(post_data["id"])

    # 3. Verify PostgreSQL persistence & 1536-D vector
    with session_factory() as db:
        post = db.execute(select(Post).where(Post.id == post_id)).scalar_one()
        assert post.post_embedding is not None
        assert len(post.post_embedding) == 1536

        # 4. Verify transactional outbox event record created
        event = db.execute(
            select(EventProcessing).where(EventProcessing.post_id == post_id)
        ).scalar_one_or_none()
        assert event is not None
        assert event.event_type == "post.published"
        assert event.status == "PENDING"
        assert event.payload["post_id"] == str(post_id)
        assert event.payload["author_agent_id"] == str(author_id)


@pytest.mark.asyncio
async def test_create_post_unauthorized(client: AsyncClient):
    """Test that creating a post without authentication fails with 401."""
    res = await client.post(
        "/api/v1/posts",
        json={
            "title": "Unauthorized Title",
            "content": "Unauthorized content that should be rejected by security layer.",
        },
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_post_inactive_agent_rejected(client: AsyncClient):
    """Test that a deactivated agent cannot create posts (403 Forbidden)."""
    company = f"InactiveAuthor_{uuid.uuid4().hex[:8]}"
    reg_res = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": company,
            "industry_category": "Logistics",
            "webhook_url": "https://inactive.example/webhook",
            "interest_manifesto": "Freight forwarding and warehouse supply lines",
        },
    )
    agent_id = reg_res.json()["agent"]["id"]
    api_key = reg_res.json()["api_key"]

    # Deactivate
    await client.post(
        f"/api/v1/agents/{agent_id}/deactivate",
        headers={"X-Agent-API-Key": api_key},
    )

    # Attempt to post
    post_res = await client.post(
        "/api/v1/posts",
        json={
            "title": "Post from deactivated company",
            "content": "This should be rejected because the agent is deactivated.",
        },
        headers={"X-Agent-API-Key": api_key},
    )
    assert post_res.status_code == 403


@pytest.mark.asyncio
async def test_create_post_validation_errors(client: AsyncClient):
    """Test validation errors for too short title or content."""
    company = f"ValidAuthor_{uuid.uuid4().hex[:8]}"
    reg_res = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": company,
            "industry_category": "Fintech",
            "webhook_url": "https://val.example/webhook",
            "interest_manifesto": "Valid manifesto for validation testing",
        },
    )
    api_key = reg_res.json()["api_key"]

    # Short title
    res_bad_title = await client.post(
        "/api/v1/posts",
        json={"title": "No", "content": "Valid length content that meets the length constraint."},
        headers={"X-Agent-API-Key": api_key},
    )
    assert res_bad_title.status_code == 422

    # Short content
    res_bad_content = await client.post(
        "/api/v1/posts",
        json={"title": "Valid Announcement Title", "content": "Tiny"},
        headers={"X-Agent-API-Key": api_key},
    )
    assert res_bad_content.status_code == 422


@pytest.mark.asyncio
async def test_post_retrieval_and_comments(client: AsyncClient):
    """Test retrieving post by ID, post listing, and comment listing."""
    company = f"ListingCorp_{uuid.uuid4().hex[:8]}"
    reg_res = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": company,
            "industry_category": "E-Commerce",
            "webhook_url": "https://list.example/webhook",
            "interest_manifesto": "E-commerce festive partnerships and retail campaigns",
        },
    )
    api_key = reg_res.json()["api_key"]

    post_res = await client.post(
        "/api/v1/posts",
        json={
            "title": "Diwali Super Sale Announcement",
            "content": "Exclusive discounts for online merchants and bank card partnerships.",
        },
        headers={"X-Agent-API-Key": api_key},
    )
    post_id = post_res.json()["id"]

    # 1. Retrieve post by ID
    get_res = await client.get(f"/api/v1/posts/{post_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Diwali Super Sale Announcement"

    # 2. List posts
    list_res = await client.get("/api/v1/posts?limit=10&offset=0")
    assert list_res.status_code == 200
    assert any(p["id"] == post_id for p in list_res.json()["posts"])

    # 3. Retrieve comments (initially empty)
    comments_res = await client.get(f"/api/v1/posts/{post_id}/comments")
    assert comments_res.status_code == 200
    assert comments_res.json()["total"] == 0
    assert comments_res.json()["comments"] == []
