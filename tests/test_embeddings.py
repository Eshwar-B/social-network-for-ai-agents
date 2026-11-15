"""Test suite for embedding generation service and provider abstractions."""

import math
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.main import app
from app.services.embedding_provider import MockEmbeddingProvider, BaseEmbeddingProvider
from app.services.embedding_service import EmbeddingService


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_mock_embedding_provider_properties():
    """Verify mock embedding provider dimension, normalization, and determinism."""
    provider = MockEmbeddingProvider(dimension=1536)
    text = "UPI payments, merchant offers, cashback rewards"

    vec1 = await provider.embed_text(text)
    vec2 = await provider.embed_text(text)

    # 1. Dimension is 1536
    assert len(vec1) == 1536
    assert len(vec2) == 1536

    # 2. Deterministic: same text produces identical vector
    assert vec1 == vec2

    # 3. L2 Normalized: norm is approximately 1.0
    norm = math.sqrt(sum(x * x for x in vec1))
    assert abs(norm - 1.0) < 1e-4


@pytest.mark.asyncio
async def test_embedding_semantic_relative_similarity():
    """Verify that semantically related texts have higher cosine similarity than unrelated ones."""
    provider = MockEmbeddingProvider(dimension=1536)

    food_delivery = "Swiggy food delivery restaurant festive discount"
    food_cashback = "Food delivery cashback discounts on dining orders"
    auto_parts = "Automobile commercial tractors engine parts manufacturing"

    vec_food = await provider.embed_text(food_delivery)
    vec_cashback = await provider.embed_text(food_cashback)
    vec_auto = await provider.embed_text(auto_parts)

    sim_related = sum(a * b for a, b in zip(vec_food, vec_cashback))
    sim_unrelated = sum(a * b for a, b in zip(vec_food, vec_auto))

    assert sim_related > sim_unrelated


@pytest.mark.asyncio
async def test_embedding_service_validation():
    """Verify validation on empty input text."""
    service = EmbeddingService()
    with pytest.raises(ValueError, match="empty text"):
        await service.generate_embedding("")

    with pytest.raises(ValueError, match="empty text"):
        await service.generate_embedding("   ")


@pytest.mark.asyncio
async def test_agent_registration_generates_embedding(client: AsyncClient):
    """Test that registering an agent automatically generates and persists interest embedding."""
    company = f"EmbedTestCorp_{uuid.uuid4().hex[:8]}"
    manifesto = "Fintech payments, merchant solutions, digital credit lines"

    res = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": company,
            "industry_category": "Fintech",
            "webhook_url": "https://embedtest.example/webhook",
            "interest_manifesto": manifesto,
        },
    )
    assert res.status_code == 201
    data = res.json()

    assert data["agent"]["embedding_status"] == "COMPLETED"
    assert data["agent"]["has_embedding"] is True

    # Verify vector directly in database
    agent_id = uuid.UUID(data["agent"]["id"])
    with session_factory() as db:
        agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one()
        assert agent.interest_embedding is not None
        assert len(agent.interest_embedding) == 1536


@pytest.mark.asyncio
async def test_manifesto_update_regenerates_embedding(client: AsyncClient):
    """Test that updating manifesto regenerates embedding vector in database."""
    company = f"UpdateEmbedCorp_{uuid.uuid4().hex[:8]}"
    res = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": company,
            "industry_category": "Retail",
            "webhook_url": "https://update.example/webhook",
            "interest_manifesto": "Initial wholesale inventory management",
        },
    )
    agent_id = res.json()["agent"]["id"]
    api_key = res.json()["api_key"]

    with session_factory() as db:
        agent_init = db.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id))).scalar_one()
        vec_init = list(agent_init.interest_embedding)

    # Update manifesto
    new_manifesto = "Completely altered manifesto for aerospace and jet turbines"
    patch_res = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"interest_manifesto": new_manifesto},
        headers={"X-Agent-API-Key": api_key},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["embedding_status"] == "COMPLETED"

    with session_factory() as db:
        agent_updated = db.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id))).scalar_one()
        vec_updated = list(agent_updated.interest_embedding)

    assert vec_init != vec_updated


class FailingProvider(BaseEmbeddingProvider):
    def get_dimension(self) -> int:
        return 1536

    async def embed_text(self, text: str):
        raise ConnectionError("Simulated API failure")

    async def embed_batch(self, texts):
        raise ConnectionError("Simulated API failure")


@pytest.mark.asyncio
async def test_embedding_service_failure_handling():
    """Verify that provider failure marks embedding_status as FAILED."""
    with session_factory() as db:
        agent = Agent(
            company_name=f"FailCorp_{uuid.uuid4().hex[:8]}",
            industry_category="Testing",
            webhook_url="https://fail.example/webhook",
            interest_manifesto="Testing provider failures and error handling",
            api_key_hash="hash_fail_123",
            embedding_status="PENDING",
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        agent_id = agent.id

        service = EmbeddingService(db=db, provider=FailingProvider())
        with pytest.raises(RuntimeError):
            await service.generate_and_save_agent_embedding(agent_id)

        # Check that status was marked as FAILED in database
        db.refresh(agent)
        assert agent.embedding_status == "FAILED"

        db.delete(agent)
        db.commit()
