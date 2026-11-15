"""Database integration and pgvector functionality test suite."""

import uuid
from typing import Generator
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database.connection import session_factory, check_database_connection
from app.database.models.agent import Agent
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog
from app.database.models.comment import Comment
from app.database.models.delivery import WebhookDelivery
from app.database.models.event import EventProcessing


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide transactional test database session."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_database_connection():
    """Verify database connectivity and pgvector presence."""
    assert check_database_connection() is True


def test_agent_and_vector_persistence(db_session: Session):
    """Test creating an agent with a 1536-dimensional vector."""
    unique_company = f"TestCorp_{uuid.uuid4().hex[:8]}"
    mock_vector = [0.01 * (i % 50) for i in range(1536)]

    agent = Agent(
        company_name=unique_company,
        industry_category="Fintech",
        webhook_url="https://testcorp.example/webhook",
        interest_manifesto="Digital payments, merchant rewards, UPI campaigns",
        interest_embedding=mock_vector,
        embedding_status="COMPLETED",
        api_key_hash="test_api_key_hash_12345",
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    assert agent.id is not None
    assert agent.company_name == unique_company
    assert len(agent.interest_embedding) == 1536
    assert agent.is_active is True

    # Query back
    retrieved = db_session.execute(
        select(Agent).where(Agent.id == agent.id)
    ).scalar_one_or_none()
    assert retrieved is not None
    assert retrieved.company_name == unique_company

    # Clean up
    db_session.delete(agent)
    db_session.commit()


def test_post_creation_and_relationships(db_session: Session):
    """Test creating post, comments, routing logs, and cascade operations."""
    author = Agent(
        company_name=f"AuthorCorp_{uuid.uuid4().hex[:8]}",
        industry_category="Food Delivery",
        webhook_url="https://authorcorp.example/webhook",
        interest_manifesto="Restaurant logistics and festive discount offers",
        interest_embedding=[0.02 * (i % 50) for i in range(1536)],
        embedding_status="COMPLETED",
        api_key_hash="hash_author_123",
    )
    db_session.add(author)
    db_session.commit()

    post_vector = [0.03 * (i % 50) for i in range(1536)]
    post = Post(
        author_agent_id=author.id,
        title="Diwali Food & Cashback Promo",
        content="Looking for fintech partners offering UPI discounts for Diwali.",
        post_embedding=post_vector,
        status="PENDING",
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)

    assert post.id is not None
    assert post.author.company_name == author.company_name

    # Add comment
    comment = Comment(
        post_id=post.id,
        author_agent_id=author.id,
        content="We are offering exclusive festival deals.",
    )
    db_session.add(comment)

    # Add routing log
    routing_log = RoutingLog(
        post_id=post.id,
        target_agent_id=author.id,
        vector_score=0.88,
        rerank_score=0.91,
        final_score=0.91,
        status="QUALIFIED",
        decision_reason="Strong semantic relevance to UPI and cashback promotions",
    )
    db_session.add(routing_log)

    # Add webhook delivery
    delivery = WebhookDelivery(
        post_id=post.id,
        target_agent_id=author.id,
        attempt_number=1,
        status="PENDING",
    )
    db_session.add(delivery)

    # Add event processing record
    event = EventProcessing(
        event_id=f"evt_{uuid.uuid4().hex}",
        event_type="post.published",
        post_id=post.id,
        status="PENDING",
    )
    db_session.add(event)
    db_session.commit()

    # Verify relationships
    assert len(post.comments) == 1
    assert len(post.routing_logs) == 1
    assert len(post.deliveries) == 1

    # Test cascade delete: deleting author deletes post, comment, routing_log, delivery
    db_session.delete(author)
    db_session.commit()

    post_check = db_session.execute(select(Post).where(Post.id == post.id)).scalar_one_or_none()
    assert post_check is None


def test_vector_cosine_distance_query(db_session: Session):
    """Verify that pgvector cosine distance operators work through SQLAlchemy."""
    agent1 = Agent(
        company_name=f"Fintech_{uuid.uuid4().hex[:8]}",
        industry_category="Fintech",
        webhook_url="https://fintech.example/webhook",
        interest_manifesto="UPI payments, wallets, and merchant cashback",
        interest_embedding=[1.0 if i == 0 else 0.0 for i in range(1536)],
        embedding_status="COMPLETED",
        api_key_hash="hash_fintech_1",
    )
    agent2 = Agent(
        company_name=f"Automobile_{uuid.uuid4().hex[:8]}",
        industry_category="Automobile",
        webhook_url="https://auto.example/webhook",
        interest_manifesto="Commercial vehicles, tractor parts, engine manufacturing",
        interest_embedding=[1.0 if i == 1 else 0.0 for i in range(1536)],
        embedding_status="COMPLETED",
        api_key_hash="hash_auto_2",
    )
    db_session.add_all([agent1, agent2])
    db_session.commit()

    # Query with vector identical to agent1
    query_vector = [1.0 if i == 0 else 0.0 for i in range(1536)]
    results = db_session.execute(
        select(
            Agent.id,
            Agent.company_name,
            (1.0 - Agent.interest_embedding.cosine_distance(query_vector)).label("similarity"),
        )
        .where(Agent.id.in_([agent1.id, agent2.id]))
        .order_by(text("similarity DESC"))
    ).all()

    assert len(results) == 2
    # First result should be agent1 with cosine similarity approx 1.0
    top_agent_id, top_name, top_sim = results[0]
    second_agent_id, second_name, second_sim = results[1]

    assert top_agent_id == agent1.id
    assert abs(top_sim - 1.0) < 1e-4
    assert abs(second_sim - 0.0) < 1e-4

    # Clean up
    db_session.delete(agent1)
    db_session.delete(agent2)
    db_session.commit()
