"""Integration tests for Agent registration and management API endpoints."""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_register_agent_success(client: AsyncClient):
    """Test successful registration of a new company agent."""
    company = f"Swiggy_{uuid.uuid4().hex[:8]}"
    payload = {
        "company_name": company,
        "industry_category": "Food Delivery",
        "webhook_url": "https://swiggy.example/api/v1/webhook",
        "interest_manifesto": "Diwali food delivery promotions, restaurant partnerships, and UPI payment offers.",
    }

    response = await client.post("/api/v1/agents/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "api_key" in data
    assert data["api_key"].startswith("asama_ak_")
    assert data["agent"]["company_name"] == company
    assert data["agent"]["is_active"] is True
    assert data["agent"]["embedding_status"] == "PENDING"
    assert data["agent"]["has_embedding"] is False


@pytest.mark.asyncio
async def test_register_duplicate_agent_fails(client: AsyncClient):
    """Test that registering an existing company name returns 409 Conflict."""
    company = f"PhonePe_{uuid.uuid4().hex[:8]}"
    payload = {
        "company_name": company,
        "industry_category": "Payments & Fintech",
        "webhook_url": "https://phonepe.example/webhook",
        "interest_manifesto": "Digital payments, UPI cashback, merchant integrations.",
    }

    res1 = await client.post("/api/v1/agents/register", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/agents/register", json=payload)
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_register_agent_validation_errors(client: AsyncClient):
    """Test validation errors for invalid URL or short company name."""
    # Invalid URL
    payload_bad_url = {
        "company_name": f"BadCorp_{uuid.uuid4().hex[:8]}",
        "industry_category": "Retail",
        "webhook_url": "ftp://not-an-http-url",
        "interest_manifesto": "Valid manifesto of sufficient length.",
    }
    res = await client.post("/api/v1/agents/register", json=payload_bad_url)
    assert res.status_code == 422

    # Manifesto too short
    payload_short_manifesto = {
        "company_name": f"ShortCorp_{uuid.uuid4().hex[:8]}",
        "industry_category": "Retail",
        "webhook_url": "https://valid.example/webhook",
        "interest_manifesto": "Short",
    }
    res = await client.post("/api/v1/agents/register", json=payload_short_manifesto)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_agent_retrieval_and_listing(client: AsyncClient):
    """Test getting an agent by ID and listing registered agents."""
    company = f"Amazon_{uuid.uuid4().hex[:8]}"
    payload = {
        "company_name": company,
        "industry_category": "E-Commerce",
        "webhook_url": "https://amazon.example/webhook",
        "interest_manifesto": "E-commerce festive offers, logistics, and co-branded bank credit cards.",
    }
    reg_res = await client.post("/api/v1/agents/register", json=payload)
    assert reg_res.status_code == 201
    agent_id = reg_res.json()["agent"]["id"]

    # Get by ID
    get_res = await client.get(f"/api/v1/agents/{agent_id}")
    assert get_res.status_code == 200
    assert get_res.json()["company_name"] == company

    # List agents
    list_res = await client.get("/api/v1/agents?limit=10&offset=0")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(a["id"] == agent_id for a in list_data["agents"])


@pytest.mark.asyncio
async def test_agent_update_authentication_and_authorization(client: AsyncClient):
    """Test agent updates, valid authentication, and impersonation protection."""
    # Register Agent A
    res_a = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"HDFC_{uuid.uuid4().hex[:8]}",
            "industry_category": "Banking",
            "webhook_url": "https://hdfc.example/webhook",
            "interest_manifesto": "Credit card promotions, personal loans, co-branded merchant rewards.",
        },
    )
    agent_a_id = res_a.json()["agent"]["id"]
    api_key_a = res_a.json()["api_key"]

    # Register Agent B
    res_b = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"Bajaj_{uuid.uuid4().hex[:8]}",
            "industry_category": "Automobile",
            "webhook_url": "https://bajaj.example/webhook",
            "interest_manifesto": "Automobile financing, commercial dealerships, insurance.",
        },
    )
    agent_b_id = res_b.json()["agent"]["id"]
    api_key_b = res_b.json()["api_key"]

    # 1. Update Agent A with Agent A's key -> Success
    update_res = await client.patch(
        f"/api/v1/agents/{agent_a_id}",
        json={"webhook_url": "https://hdfc-updated.example/webhook"},
        headers={"X-Agent-API-Key": api_key_a},
    )
    assert update_res.status_code == 200
    assert update_res.json()["webhook_url"] == "https://hdfc-updated.example/webhook"

    # 2. Update without auth -> 401 Unauthorized
    unauth_res = await client.patch(
        f"/api/v1/agents/{agent_a_id}",
        json={"webhook_url": "https://hacker.example/webhook"},
    )
    assert unauth_res.status_code == 401

    # 3. Impersonation protection: Agent B attempts to update Agent A -> 403 Forbidden
    impersonate_res = await client.patch(
        f"/api/v1/agents/{agent_a_id}",
        json={"webhook_url": "https://impersonated.example/webhook"},
        headers={"X-Agent-API-Key": api_key_b},
    )
    assert impersonate_res.status_code == 403
    assert "Not authorized" in impersonate_res.json()["detail"]


@pytest.mark.asyncio
async def test_agent_activation_and_deactivation(client: AsyncClient):
    """Test activating and deactivating an agent, verifying auth checks."""
    res = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"DeactivateCorp_{uuid.uuid4().hex[:8]}",
            "industry_category": "Logistics",
            "webhook_url": "https://logistics.example/webhook",
            "interest_manifesto": "Last-mile delivery partnerships, supply chain integrations.",
        },
    )
    agent_id = res.json()["agent"]["id"]
    api_key = res.json()["api_key"]

    # Deactivate
    deact_res = await client.post(
        f"/api/v1/agents/{agent_id}/deactivate",
        headers={"X-Agent-API-Key": api_key},
    )
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False

    # Deactivated agent trying to update -> 403 Forbidden
    forbidden_res = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"webhook_url": "https://new-url.example/webhook"},
        headers={"X-Agent-API-Key": api_key},
    )
    assert forbidden_res.status_code == 403
    assert "deactivated" in forbidden_res.json()["detail"]

    # Reactivate directly in DB or with authorized admin/service pattern
    with session_factory() as db:
        agent = db.get(Agent, uuid.UUID(agent_id))
        agent.is_active = True
        db.commit()

    # Now verify active
    get_res = await client.get(f"/api/v1/agents/{agent_id}")
    assert get_res.json()["is_active"] is True
