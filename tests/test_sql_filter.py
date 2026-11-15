"""Integration test suite for Stage A SQL eligibility filtering."""

import uuid
import pytest
from sqlalchemy.orm import Session

from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.blocklist import AgentBlocklist
from app.routing.sql_filter import SQLAgentFilter


@pytest.fixture
def db_session():
    with session_factory() as session:
        yield session


def _create_test_agent(
    db: Session,
    company: str,
    industry: str,
    is_active: bool = True,
    has_embedding: bool = True,
) -> Agent:
    vec = [0.01 * (i % 50) for i in range(1536)] if has_embedding else None
    status_val = "COMPLETED" if has_embedding else "PENDING"
    agent = Agent(
        company_name=f"{company}_{uuid.uuid4().hex[:8]}",
        industry_category=industry,
        webhook_url="https://example.com/webhook",
        interest_manifesto=f"Manifesto for {company} in {industry}",
        interest_embedding=vec,
        embedding_status=status_val,
        is_active=is_active,
        api_key_hash=f"hash_{uuid.uuid4().hex}",
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def test_sql_filter_all_exclusion_rules(db_session: Session):
    """Test comprehensive exclusion rules: publisher, inactive, missing embedding, blocklist, industry."""
    # 1. Author Agent
    author = _create_test_agent(db_session, "AuthorCorp", "Food Delivery")

    # 2. Eligible Agent
    eligible_agent = _create_test_agent(db_session, "EligibleFintech", "Fintech")

    # 3. Inactive Agent
    inactive_agent = _create_test_agent(db_session, "InactiveCorp", "Fintech", is_active=False)

    # 4. Agent without embedding
    no_embed_agent = _create_test_agent(db_session, "NoEmbedCorp", "Banking", has_embedding=False)

    # 5. Explicitly Blocked Agent
    blocked_agent = _create_test_agent(db_session, "CompetitorCorp", "Food Delivery")
    block_rule = AgentBlocklist(
        agent_id=author.id,
        blocked_agent_id=blocked_agent.id,
    )
    db_session.add(block_rule)

    # 6. Excluded Industry Agent
    gambling_agent = _create_test_agent(db_session, "CasinoCorp", "Gambling")
    industry_block = AgentBlocklist(
        agent_id=author.id,
        blocked_industry="Gambling",
    )
    db_session.add(industry_block)
    db_session.commit()

    # Run Stage A SQL Filter
    filter_service = SQLAgentFilter(db_session)
    result = filter_service.filter_eligible_agents(author_agent_id=author.id)

    eligible_ids = {c.id for c in result.candidates}

    # 1. Author is excluded
    assert author.id not in eligible_ids

    # 2. Eligible agent is present
    assert eligible_agent.id in eligible_ids

    # 3. Inactive agent is excluded
    assert inactive_agent.id not in eligible_ids

    # 4. Agent without embedding is excluded
    assert no_embed_agent.id not in eligible_ids

    # 5. Explicitly blocked agent is excluded
    assert blocked_agent.id not in eligible_ids

    # 6. Excluded industry agent is excluded
    assert gambling_agent.id not in eligible_ids

    # Verify statistics
    stats = result.stats
    assert stats.total_agents >= 6
    assert stats.inactive_excluded >= 1
    assert stats.missing_embedding_excluded >= 1
    assert stats.blocked_agents_excluded >= 1
    assert stats.blocked_industries_excluded >= 1
    assert stats.execution_time_ms < 50.0  # Fast sub-50ms execution


def test_sql_filter_explicit_industry_exclusion_parameter(db_session: Session):
    """Test passing explicit industry exclusion list at query time."""
    author = _create_test_agent(db_session, "TechCorp", "Technology")
    auto_agent = _create_test_agent(db_session, "AutoMaker", "Automotive")

    filter_service = SQLAgentFilter(db_session)
    result = filter_service.filter_eligible_agents(
        author_agent_id=author.id,
        explicit_excluded_industries=["Automotive"],
    )

    eligible_ids = {c.id for c in result.candidates}
    assert auto_agent.id not in eligible_ids
