"""Integration test suite for Redis Streams and asynchronous event processing."""

import asyncio
import json
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.redis import check_redis_connection, get_redis_client
from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.event import EventProcessing
from app.database.models.post import Post
from app.events.publisher import EventPublisher
from app.main import app
from app.workers.stream_consumer import StreamConsumer


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_redis_connection():
    """Verify that Redis server on configured port is reachable."""
    is_connected = await check_redis_connection()
    assert is_connected is True


@pytest.mark.asyncio
async def test_stream_event_publishing_and_consumer():
    """Test publishing event to Redis stream and consumer processing."""
    test_stream = f"asama:test:stream:{uuid.uuid4().hex[:8]}"
    test_group = f"asama:test:group:{uuid.uuid4().hex[:8]}"
    test_consumer = "test_worker_1"

    # Create dummy author and post
    with session_factory() as db:
        author = Agent(
            company_name=f"RedisCorp_{uuid.uuid4().hex[:8]}",
            industry_category="Fintech",
            webhook_url="https://rediscorp.example/webhook",
            interest_manifesto="Digital payments testing",
            api_key_hash="hash_redis_123",
            embedding_status="COMPLETED",
        )
        db.add(author)
        db.commit()
        db.refresh(author)

        post = Post(
            author_agent_id=author.id,
            title="Redis Stream Announcement",
            content="Testing Redis stream asynchronous event processing and routing trigger.",
            status="PENDING",
        )
        db.add(post)
        db.commit()
        db.refresh(post)

        event_id = f"evt_{uuid.uuid4().hex}"
        event = EventProcessing(
            event_id=event_id,
            event_type="post.published",
            post_id=post.id,
            status="PENDING",
            payload={"event_id": event_id, "post_id": str(post.id), "author_agent_id": str(author.id)},
        )
        db.add(event)
        db.commit()
        post_id = post.id

    # 1. Publish event to Redis Stream
    publisher = EventPublisher(stream_key=test_stream)
    msg_id = await publisher.publish_post_published(
        event_id=event_id,
        post_id=post_id,
        author_agent_id=author.id,
    )
    assert msg_id is not None

    # 2. Consume event with StreamConsumer
    consumer = StreamConsumer(
        stream_key=test_stream,
        consumer_group=test_group,
        consumer_name=test_consumer,
    )
    processed = await consumer.run_once()
    assert processed >= 1

    # 3. Verify PostgreSQL status updated to ROUTED and event COMPLETED
    with session_factory() as db:
        post_after = db.execute(select(Post).where(Post.id == post_id)).scalar_one()
        assert post_after.status == "ROUTED"

        event_after = db.execute(select(EventProcessing).where(EventProcessing.event_id == event_id)).scalar_one()
        assert event_after.status == "COMPLETED"


@pytest.mark.asyncio
async def test_idempotent_event_processing():
    """Verify that reprocessing an already completed event does not re-execute."""
    test_stream = f"asama:test:stream:{uuid.uuid4().hex[:8]}"
    test_group = f"asama:test:group:{uuid.uuid4().hex[:8]}"

    with session_factory() as db:
        author = Agent(
            company_name=f"IdemCorp_{uuid.uuid4().hex[:8]}",
            industry_category="Retail",
            webhook_url="https://idem.example/webhook",
            interest_manifesto="Retail operations",
            api_key_hash="hash_idem_123",
            embedding_status="COMPLETED",
        )
        db.add(author)
        db.commit()

        post = Post(
            author_agent_id=author.id,
            title="Idempotency Test Post",
            content="Checking duplicate processing prevention",
            status="PENDING",
        )
        db.add(post)
        db.commit()

        event_id = f"evt_{uuid.uuid4().hex}"
        event = EventProcessing(
            event_id=event_id,
            event_type="post.published",
            post_id=post.id,
            status="COMPLETED",  # Already marked completed!
            attempt_count=1,
            payload={"event_id": event_id, "post_id": str(post.id)},
        )
        db.add(event)
        db.commit()
        post_id = post.id

    consumer = StreamConsumer(
        stream_key=test_stream,
        consumer_group=test_group,
        consumer_name="worker_idem",
    )
    payload = {"event_id": event_id, "post_id": str(post_id)}
    # Direct processing call
    result = await consumer.process_event("dummy_msg_id", "post.published", payload)
    assert result is True

    # Post should still have attempt_count 1 because it was skipped
    with session_factory() as db:
        ev = db.execute(select(EventProcessing).where(EventProcessing.event_id == event_id)).scalar_one()
        assert ev.attempt_count == 1


@pytest.mark.asyncio
async def test_pending_message_recovery():
    """Verify that pending unacknowledged messages are recovered upon worker restart."""
    test_stream = f"asama:test:stream:{uuid.uuid4().hex[:8]}"
    test_group = f"asama:test:group:{uuid.uuid4().hex[:8]}"
    consumer_name = "worker_restart"

    client = get_redis_client()
    # Create group
    await client.xgroup_create(test_stream, test_group, id="0", mkstream=True)

    # Publish an event
    with session_factory() as db:
        author = Agent(
            company_name=f"PelCorp_{uuid.uuid4().hex[:8]}",
            industry_category="Fintech",
            webhook_url="https://pel.example/webhook",
            interest_manifesto="Pending message recovery",
            api_key_hash="hash_pel_123",
            embedding_status="COMPLETED",
        )
        db.add(author)
        db.commit()

        post = Post(
            author_agent_id=author.id,
            title="Pel Test Post",
            content="Testing pending message recovery",
            status="PENDING",
        )
        db.add(post)
        db.commit()

        event_id = f"evt_{uuid.uuid4().hex}"
        event = EventProcessing(
            event_id=event_id,
            event_type="post.published",
            post_id=post.id,
            status="PENDING",
            payload={"event_id": event_id, "post_id": str(post.id)},
        )
        db.add(event)
        db.commit()
        post_id = post.id

    # Read message into PEL WITHOUT acknowledging (simulating a crash)
    await client.xadd(test_stream, {"event_type": "post.published", "payload": json.dumps({"event_id": event_id, "post_id": str(post_id)})})
    pel_read = await client.xreadgroup(test_group, consumer_name, streams={test_stream: ">"}, count=1)
    assert len(pel_read) > 0  # Read into PEL

    # Verify message is pending in Redis
    pending_info = await client.xpending(test_stream, test_group)
    assert pending_info["pending"] >= 1

    # Now create consumer and recover pending messages
    consumer = StreamConsumer(
        stream_key=test_stream,
        consumer_group=test_group,
        consumer_name=consumer_name,
    )
    recovered_count = await consumer.read_and_process_pending()
    assert recovered_count >= 1

    # Verify message was acknowledged in Redis
    pending_after = await client.xpending(test_stream, test_group)
    assert pending_after["pending"] == 0


@pytest.mark.asyncio
async def test_end_to_end_post_publication_to_redis(client: AsyncClient):
    """Test full workflow: create post via API -> event in Redis stream -> consumed by worker."""
    company = f"AsyncPubCorp_{uuid.uuid4().hex[:8]}"
    reg_res = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": company,
            "industry_category": "Logistics",
            "webhook_url": "https://asyncpub.example/webhook",
            "interest_manifesto": "Freight logistics, supply chain partnerships",
        },
    )
    api_key = reg_res.json()["api_key"]

    # 1. API creates post & publishes to Redis Stream
    post_res = await client.post(
        "/api/v1/posts",
        json={
            "title": "Supply Chain Collaboration",
            "content": "Looking for national delivery partners with express fulfillment.",
        },
        headers={"X-Agent-API-Key": api_key},
    )
    assert post_res.status_code == 201
    post_id = uuid.UUID(post_res.json()["id"])

    # 2. Run consumer worker once to process the published stream event
    consumer = StreamConsumer()
    processed = await consumer.run_once()
    assert processed >= 1

    # 3. Authoritative post in PostgreSQL should now be ROUTED
    with session_factory() as db:
        post = db.execute(select(Post).where(Post.id == post_id)).scalar_one()
        assert post.status == "ROUTED"
