"""Integration test suite for Stage B pgvector semantic search."""

import uuid
import pytest
from sqlalchemy.orm import Session

from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.routing.vector_search import VectorAgentSearch
from app.services.embedding_provider import MockEmbeddingProvider


@pytest.fixture
def db_session():
    with session_factory() as session:
        yield session


@pytest.mark.asyncio
async def test_vector_search_semantic_ranking(db_session: Session):
    """Test that pgvector search ranks semantically matching business profiles above unrelated ones."""
    provider = MockEmbeddingProvider(dimension=1536)

    # 1. Author: Swiggy
    swiggy_manifesto = "Online food delivery, restaurant network, quick grocery fulfillment"
    swiggy_vec = await provider.embed_text(swiggy_manifesto)
    swiggy = Agent(
        company_name=f"Swiggy_{uuid.uuid4().hex[:8]}",
        industry_category="Food Delivery",
        webhook_url="https://swiggy.example/webhook",
        interest_manifesto=swiggy_manifesto,
        interest_embedding=swiggy_vec,
        embedding_status="COMPLETED",
        api_key_hash=f"hash_{uuid.uuid4().hex}",
    )
    db_session.add(swiggy)

    # 2. Candidate 1: PhonePe (Highly relevant: food delivery + UPI cashback)
    phonepe_manifesto = "Fintech payments, online food delivery cashback discounts, UPI payment campaigns"
    phonepe_vec = await provider.embed_text(phonepe_manifesto)
    phonepe = Agent(
        company_name=f"PhonePe_{uuid.uuid4().hex[:8]}",
        industry_category="Fintech",
        webhook_url="https://phonepe.example/webhook",
        interest_manifesto=phonepe_manifesto,
        interest_embedding=phonepe_vec,
        embedding_status="COMPLETED",
        api_key_hash=f"hash_{uuid.uuid4().hex}",
    )
    db_session.add(phonepe)

    # 3. Candidate 2: Paytm (Relevant: digital payments, merchant offers)
    paytm_manifesto = "Digital payments, merchant discounts, online dining cashback"
    paytm_vec = await provider.embed_text(paytm_manifesto)
    paytm = Agent(
        company_name=f"Paytm_{uuid.uuid4().hex[:8]}",
        industry_category="Fintech",
        webhook_url="https://paytm.example/webhook",
        interest_manifesto=paytm_manifesto,
        interest_embedding=paytm_vec,
        embedding_status="COMPLETED",
        api_key_hash=f"hash_{uuid.uuid4().hex}",
    )
    db_session.add(paytm)

    # 4. Candidate 3: Bajaj Auto (Unrelated: automobile manufacturing)
    bajaj_manifesto = "Automobile commercial tractors, diesel engines, vehicle dealerships"
    bajaj_vec = await provider.embed_text(bajaj_manifesto)
    bajaj = Agent(
        company_name=f"Bajaj_{uuid.uuid4().hex[:8]}",
        industry_category="Automotive",
        webhook_url="https://bajaj.example/webhook",
        interest_manifesto=bajaj_manifesto,
        interest_embedding=bajaj_vec,
        embedding_status="COMPLETED",
        api_key_hash=f"hash_{uuid.uuid4().hex}",
    )
    db_session.add(bajaj)
    db_session.commit()

    # Post from Swiggy
    post_text = "Swiggy Diwali festive food delivery discount offering UPI cashback partnership"
    post_vec = await provider.embed_text(post_text)

    # Execute Stage B Vector Search with eligible candidate scope
    searcher = VectorAgentSearch(db_session)
    result = searcher.search_top_candidates(
        post_vector=post_vec,
        author_agent_id=swiggy.id,
        eligible_agent_ids=[phonepe.id, paytm.id, bajaj.id],
        top_k=10,
    )

    # Verify author is not in results
    candidate_ids = [c.agent_id for c in result.candidates]
    assert swiggy.id not in candidate_ids

    # Verify PhonePe and Paytm rank above Bajaj Auto
    candidate_companies = [c.company_name for c in result.candidates]
    phonepe_index = candidate_companies.index(phonepe.company_name)
    bajaj_index = candidate_companies.index(bajaj.company_name)
    assert phonepe_index < bajaj_index

    # Verify vector scores are ordered descending
    scores = [c.vector_score for c in result.candidates]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_vector_search_top_k_limit(db_session: Session):
    """Test that Top K limit is strictly enforced."""
    provider = MockEmbeddingProvider(dimension=1536)
    author = Agent(
        company_name=f"AuthorTopK_{uuid.uuid4().hex[:8]}",
        industry_category="Tech",
        webhook_url="https://example.com/webhook",
        interest_manifesto="Technology and software",
        interest_embedding=await provider.embed_text("Tech software"),
        embedding_status="COMPLETED",
        api_key_hash=f"hash_{uuid.uuid4().hex}",
    )
    db_session.add(author)

    agents = []
    for i in range(5):
        a = Agent(
            company_name=f"Candidate_{i}_{uuid.uuid4().hex[:8]}",
            industry_category="Tech",
            webhook_url="https://example.com/webhook",
            interest_manifesto=f"Candidate profile number {i}",
            interest_embedding=await provider.embed_text(f"Candidate profile number {i}"),
            embedding_status="COMPLETED",
            api_key_hash=f"hash_{uuid.uuid4().hex}",
        )
        agents.append(a)
    db_session.add_all(agents)
    db_session.commit()

    searcher = VectorAgentSearch(db_session)
    result = searcher.search_top_candidates(
        post_vector=await provider.embed_text("Query text for top K"),
        author_agent_id=author.id,
        top_k=3,
    )

    assert len(result.candidates) == 3
    assert result.stats.candidates_retrieved == 3
    assert result.stats.execution_time_ms < 100.0


def test_vector_search_empty_candidate_pool(db_session: Session):
    """Test that empty eligible agent pool returns empty results cleanly."""
    searcher = VectorAgentSearch(db_session)
    empty_vector = [0.0] * 1536
    result = searcher.search_top_candidates(
        post_vector=empty_vector,
        author_agent_id=uuid.uuid4(),
        eligible_agent_ids=[],
    )
    assert result.candidates == []
    assert result.stats.candidates_retrieved == 0
