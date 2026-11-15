"""Integration tests for Phase 9: Signed Webhook Notification Delivery, HMAC, Retry, and Circuit Breaker."""

import time
import uuid
import httpx
import pytest

from app.database.connection import session_factory
from app.database.models.agent import Agent
from app.database.models.delivery import WebhookDelivery
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog
from app.services.notification_service import CircuitBreaker, NotificationService
from app.utils.hmac_utils import (
    generate_webhook_signature,
    is_safe_webhook_url,
    verify_webhook_signature,
)
from app.workers.notification_worker import NotificationWorker


# ============================================================================
# 1. HMAC SIGNING, VERIFICATION & REPLAY PROTECTION
# ============================================================================

def test_hmac_signature_generation_and_verification():
    """Verify standard HMAC signature generation and verification."""
    secret = "secret_key_12345"
    payload = b'{"event":"post.matched","post_id":"123"}'

    sig, ts = generate_webhook_signature(payload, secret)
    header = f"t={ts},v1={sig}"

    # Valid verification
    assert verify_webhook_signature(payload, header, secret, max_age_seconds=300) is True

    # Tampered payload rejected
    tampered_payload = b'{"event":"post.matched","post_id":"999"}'
    assert verify_webhook_signature(tampered_payload, header, secret) is False

    # Tampered signature rejected
    bad_header = f"t={ts},v1={sig[:-2]}00"
    assert verify_webhook_signature(payload, bad_header, secret) is False

    # Wrong secret rejected
    assert verify_webhook_signature(payload, header, "wrong_secret") is False


def test_hmac_replay_protection():
    """Verify that expired timestamps are rejected to prevent replay attacks."""
    secret = "test_replay_secret"
    payload = b'{"action":"replay_test"}'

    # Timestamp from 10 minutes ago
    old_ts = int(time.time()) - 600
    sig, _ = generate_webhook_signature(payload, secret, timestamp=old_ts)
    old_header = f"t={old_ts},v1={sig}"

    # Default max_age is 300s (5 minutes) -> rejected
    assert verify_webhook_signature(payload, old_header, secret, max_age_seconds=300) is False

    # Future timestamp beyond tolerance -> rejected
    future_ts = int(time.time()) + 600
    future_sig, _ = generate_webhook_signature(payload, secret, timestamp=future_ts)
    future_header = f"t={future_ts},v1={future_sig}"
    assert verify_webhook_signature(payload, future_header, secret, max_age_seconds=300) is False


# ============================================================================
# 2. SSRF PROTECTION TESTS
# ============================================================================

def test_ssrf_url_validation():
    """Verify SSRF filters block private IPs, cloud metadata, and invalid schemes."""
    # Invalid schemes
    assert is_safe_webhook_url("ftp://example.com/webhook") is False
    assert is_safe_webhook_url("file:///etc/passwd") is False
    assert is_safe_webhook_url("javascript:alert(1)") is False

    # AWS/Cloud metadata IP (169.254.169.254)
    assert is_safe_webhook_url("http://169.254.169.254/latest/meta-data") is False
    assert is_safe_webhook_url("http://metadata.google.internal/computeMetadata") is False

    # Safe external HTTPS endpoints
    assert is_safe_webhook_url("https://api.swiggy.example/webhook") is True
    assert is_safe_webhook_url("https://phonepe.com/callback") is True

    # Localhost handling
    assert is_safe_webhook_url("http://localhost:8000/webhook", allow_localhost=True) is True
    assert is_safe_webhook_url("http://127.0.0.1:8000/webhook", allow_localhost=True) is True
    assert is_safe_webhook_url("http://127.0.0.1:8000/webhook", allow_localhost=False) is False


# ============================================================================
# 3. WEBHOOK DELIVERY & RETRY TESTS WITH MOCK HTTPX TRANSPORT
# ============================================================================

@pytest.mark.asyncio
async def test_webhook_successful_delivery_and_persistence():
    """Verify successful delivery creates a delivery record with SUCCESS and status 200."""
    received_requests = []

    def mock_handler(request: httpx.Request):
        received_requests.append(request)
        return httpx.Response(200, json={"status": "received"})

    transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    with session_factory() as db:
        agent = Agent(
            company_name=f"NotifyAgent_{uuid.uuid4().hex[:8]}",
            industry_category="Fintech",
            webhook_url="https://notify.example/webhook",
            interest_manifesto="Fintech webhook test",
            api_key_hash="hash_notify_123",
            embedding_status="COMPLETED",
        )
        db.add(agent)
        db.commit()

        post = Post(
            author_agent_id=agent.id,
            title="Notification Test Post",
            content="Testing webhook delivery pipeline",
            status="ROUTED",
        )
        db.add(post)
        db.commit()

        service = NotificationService(db=db, max_attempts=2, initial_backoff_sec=0.01)
        delivery = await service.deliver_webhook(
            target_agent=agent,
            post=post,
            vector_score=0.88,
            rerank_score=0.92,
            final_score=0.92,
            db_session=db,
            custom_client=mock_client,
        )

        assert delivery.status == "SUCCESS"
        assert delivery.response_status_code == 200
        assert delivery.attempt_number == 1
        assert len(received_requests) == 1

        # Verify signature header present and valid
        sent_request = received_requests[0]
        sig_header = sent_request.headers.get("X-Asama-Signature")
        assert sig_header is not None
        assert verify_webhook_signature(sent_request.content, sig_header, agent.api_key_hash) is True

        # Verify delivery persisted in database
        persisted = db.get(WebhookDelivery, delivery.id)
        assert persisted is not None
        assert persisted.status == "SUCCESS"

        # Clean up
        db.delete(agent)
        db.commit()

    await mock_client.aclose()


@pytest.mark.asyncio
async def test_webhook_retry_and_eventual_success():
    """Verify that transient 500 errors trigger retry with backoff, succeeding on attempt 2."""
    attempt_counter = 0

    def mock_flaky_handler(request: httpx.Request):
        nonlocal attempt_counter
        attempt_counter += 1
        if attempt_counter == 1:
            return httpx.Response(503, text="Service Unavailable")
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(mock_flaky_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    with session_factory() as db:
        agent = Agent(
            company_name=f"FlakyAgent_{uuid.uuid4().hex[:8]}",
            industry_category="Banking",
            webhook_url="https://flaky.example/webhook",
            interest_manifesto="Flaky webhook testing",
            api_key_hash="hash_flaky_123",
            embedding_status="COMPLETED",
        )
        db.add(agent)
        db.commit()

        post = Post(
            author_agent_id=agent.id,
            title="Retry Test Post",
            content="Testing retry mechanism with backoff",
            status="ROUTED",
        )
        db.add(post)
        db.commit()

        service = NotificationService(db=db, max_attempts=3, initial_backoff_sec=0.01)
        delivery = await service.deliver_webhook(
            target_agent=agent,
            post=post,
            vector_score=0.85,
            rerank_score=0.89,
            final_score=0.89,
            db_session=db,
            custom_client=mock_client,
        )

        assert delivery.status == "SUCCESS"
        assert delivery.attempt_number == 2
        assert delivery.response_status_code == 200
        assert attempt_counter == 2

        db.delete(agent)
        db.commit()

    await mock_client.aclose()


@pytest.mark.asyncio
async def test_webhook_max_attempts_failure():
    """Verify that when endpoint permanently returns 500, delivery fails after max attempts."""
    attempts = 0

    def mock_fail_handler(request: httpx.Request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(mock_fail_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    with session_factory() as db:
        agent = Agent(
            company_name=f"DeadAgent_{uuid.uuid4().hex[:8]}",
            industry_category="Retail",
            webhook_url="https://dead.example/webhook",
            interest_manifesto="Dead webhook testing",
            api_key_hash="hash_dead_123",
            embedding_status="COMPLETED",
        )
        db.add(agent)
        db.commit()

        post = Post(
            author_agent_id=agent.id,
            title="Max Attempt Post",
            content="Testing exhaustion of max attempts",
            status="ROUTED",
        )
        db.add(post)
        db.commit()

        service = NotificationService(db=db, max_attempts=3, initial_backoff_sec=0.01)
        delivery = await service.deliver_webhook(
            target_agent=agent,
            post=post,
            vector_score=0.80,
            rerank_score=0.82,
            final_score=0.82,
            db_session=db,
            custom_client=mock_client,
        )

        assert delivery.status == "FAILED"
        assert delivery.attempt_number == 3
        assert delivery.response_status_code == 500
        assert attempts == 3
        assert "HTTP status 500" in delivery.error_message

        db.delete(agent)
        db.commit()

    await mock_client.aclose()


# ============================================================================
# 4. CIRCUIT BREAKER TEST
# ============================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_tripping():
    """Verify that repeated consecutive failures trip the circuit breaker."""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=10.0)
    endpoint = "https://failing-endpoint.example/webhook"

    assert breaker.is_available(endpoint) is True

    # 1st failure
    breaker.record_failure(endpoint)
    assert breaker.is_available(endpoint) is True

    # 2nd failure
    breaker.record_failure(endpoint)
    assert breaker.is_available(endpoint) is True

    # 3rd failure -> Breaker trips!
    tripped = breaker.record_failure(endpoint)
    assert tripped is True
    assert breaker.is_available(endpoint) is False

    # Subsequent calls blocked by circuit breaker
    assert breaker.is_available(endpoint) is False

    # Simulate success on another endpoint
    breaker.record_success("https://healthy.example/webhook")
    assert breaker.is_available("https://healthy.example/webhook") is True


# ============================================================================
# 5. END-TO-END NOTIFICATION WORKER DISPATCH
# ============================================================================

@pytest.mark.asyncio
async def test_notification_worker_dispatch_for_post():
    """Verify NotificationWorker finds qualified routing logs and delivers webhooks."""
    delivered_urls = []

    def mock_delivery_handler(request: httpx.Request):
        delivered_urls.append(str(request.url))
        return httpx.Response(200, json={"received": True})

    transport = httpx.MockTransport(mock_delivery_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    with session_factory() as db:
        author = Agent(
            company_name=f"Author_{uuid.uuid4().hex[:6]}",
            industry_category="Food Delivery",
            webhook_url="https://author.example/webhook",
            interest_manifesto="Food delivery",
            api_key_hash="hash_a",
            embedding_status="COMPLETED",
        )
        recipient_1 = Agent(
            company_name=f"Recip1_{uuid.uuid4().hex[:6]}",
            industry_category="Fintech",
            webhook_url="https://recip1.example/webhook",
            interest_manifesto="Fintech payments",
            api_key_hash="hash_r1",
            embedding_status="COMPLETED",
        )
        recipient_2 = Agent(
            company_name=f"Recip2_{uuid.uuid4().hex[:6]}",
            industry_category="Fintech",
            webhook_url="https://recip2.example/webhook",
            interest_manifesto="Fintech cashback",
            api_key_hash="hash_r2",
            embedding_status="COMPLETED",
        )
        db.add_all([author, recipient_1, recipient_2])
        db.commit()

        post = Post(
            author_agent_id=author.id,
            title="Dispatch Test Post",
            content="Testing end to end notification worker dispatch",
            status="ROUTED",
        )
        db.add(post)
        db.commit()

        # Add qualified routing logs for recipient_1 and recipient_2
        log1 = RoutingLog(
            post_id=post.id,
            target_agent_id=recipient_1.id,
            vector_score=0.85,
            rerank_score=0.90,
            final_score=0.90,
            status="QUALIFIED",
            decision_reason="Qualified recipient 1",
        )
        log2 = RoutingLog(
            post_id=post.id,
            target_agent_id=recipient_2.id,
            vector_score=0.82,
            rerank_score=0.87,
            final_score=0.87,
            status="QUALIFIED",
            decision_reason="Qualified recipient 2",
        )
        db.add_all([log1, log2])
        db.commit()

        # Dispatch with NotificationWorker
        service = NotificationService(db=db, initial_backoff_sec=0.01)
        worker = NotificationWorker(notification_service=service)
        deliveries = await worker.dispatch_for_post(post.id, db_session=db, custom_client=mock_client)

        assert len(deliveries) == 2
        assert all(d.status == "SUCCESS" for d in deliveries)
        assert len(delivered_urls) == 2
        assert "https://recip1.example/webhook" in delivered_urls
        assert "https://recip2.example/webhook" in delivered_urls

        # Clean up
        db.delete(author)
        db.delete(recipient_1)
        db.delete(recipient_2)
        db.commit()

    await mock_client.aclose()
