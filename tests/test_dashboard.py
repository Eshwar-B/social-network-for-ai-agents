"""Integration tests for Phase 14: Frontend Dashboard and Routing Logs endpoints."""

import uuid
import pytest
from httpx import AsyncClient

from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog


@pytest.mark.asyncio
async def test_dashboard_endpoint_serves_html(client: AsyncClient):
    """Verify GET /dashboard returns the compiled HTML application."""
    response = await client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Asama.ai" in response.text


@pytest.mark.asyncio
async def test_post_routing_logs_endpoint(client: AsyncClient):
    """Verify GET /api/v1/posts/{post_id}/routing-logs returns evaluation details."""
    with session_factory() as db:
        author = Agent(
            company_name=f"DashAuthor_{uuid.uuid4().hex[:6]}",
            industry_category="Food Delivery",
            webhook_url="https://dashauthor.example/webhook",
            interest_manifesto="Food delivery",
            api_key_hash="hash_dash_author",
            embedding_status="COMPLETED",
        )
        target = Agent(
            company_name=f"DashTarget_{uuid.uuid4().hex[:6]}",
            industry_category="Fintech",
            webhook_url="https://dashtarget.example/webhook",
            interest_manifesto="Fintech cashback",
            api_key_hash="hash_dash_target",
            embedding_status="COMPLETED",
        )
        db.add_all([author, target])
        db.commit()

        post = Post(
            author_agent_id=author.id,
            title="Dashboard Visualizer Post",
            content="Testing visualizer endpoint data flow",
            status="ROUTED",
        )
        db.add(post)
        db.commit()

        log = RoutingLog(
            post_id=post.id,
            target_agent_id=target.id,
            vector_score=0.88,
            rerank_score=0.92,
            final_score=0.92,
            status="QUALIFIED",
            decision_reason="Strong fintech synergy for cashback",
        )
        db.add(log)
        db.commit()
        post_id = post.id

    # Query routing logs endpoint
    res = await client.get(f"/api/v1/posts/{post_id}/routing-logs")
    assert res.status_code == 200
    data = res.json()

    assert data["post_id"] == str(post_id)
    assert data["total"] == 1
    assert data["routing_logs"][0]["target_company_name"] == target.company_name
    assert data["routing_logs"][0]["final_score"] == 0.92
    assert data["routing_logs"][0]["status"] == "QUALIFIED"
