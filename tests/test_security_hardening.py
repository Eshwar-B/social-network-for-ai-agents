"""Integration tests for Phase 13: Security Hardening & Platform Protection."""

import uuid
import pytest
from httpx import AsyncClient

from app.core.rate_limit import SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_security_headers_present_on_responses(client: AsyncClient):
    """Verify OWASP recommended security headers are present on all responses."""
    response = await client.get("/")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "Strict-Transport-Security" in headers
    assert "Referrer-Policy" in headers


@pytest.mark.asyncio
async def test_api_key_rotation_flow(client: AsyncClient):
    """Verify that rotating an agent's API key invalidates the old key and activates the new key."""
    # 1. Register agent
    reg = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"RotateCorp_{uuid.uuid4().hex[:8]}",
            "industry_category": "Fintech",
            "webhook_url": "https://rotate.example/webhook",
            "interest_manifesto": "API key rotation testing manifesto",
        },
    )
    assert reg.status_code == 201
    agent_id = reg.json()["agent"]["id"]
    old_key = reg.json()["api_key"]

    # 2. Verify old key works for post creation
    p1 = await client.post(
        "/api/v1/posts",
        json={"title": "Pre-Rotation Post", "content": "Testing valid post with original API key."},
        headers={"X-Agent-API-Key": old_key},
    )
    assert p1.status_code == 201

    # 3. Rotate API key
    rotate_res = await client.post(
        f"/api/v1/agents/{agent_id}/rotate-api-key",
        headers={"X-Agent-API-Key": old_key},
    )
    assert rotate_res.status_code == 200
    new_key = rotate_res.json()["api_key"]
    assert new_key != old_key
    assert new_key.startswith("asama_ak_")

    # 4. Old key is now invalidated -> 401 Unauthorized
    p_old = await client.post(
        "/api/v1/posts",
        json={"title": "Post With Old Key", "content": "This must be rejected because old key was revoked."},
        headers={"X-Agent-API-Key": old_key},
    )
    assert p_old.status_code == 401

    # 5. New key works -> 201 Created
    p_new = await client.post(
        "/api/v1/posts",
        json={"title": "Post With New Key", "content": "This must succeed with newly rotated key."},
        headers={"X-Agent-API-Key": new_key},
    )
    assert p_new.status_code == 201


@pytest.mark.asyncio
async def test_api_key_rotation_impersonation_blocked(client: AsyncClient):
    """Verify Agent B cannot rotate Agent A's API key (403 Forbidden)."""
    # Register Agent A
    res_a = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"AgentVictim_{uuid.uuid4().hex[:8]}",
            "industry_category": "Retail",
            "webhook_url": "https://victim.example/webhook",
            "interest_manifesto": "Victim agent manifesto",
        },
    )
    agent_a_id = res_a.json()["agent"]["id"]

    # Register Agent B
    res_b = await client.post(
        "/api/v1/agents/register",
        json={
            "company_name": f"AgentAttacker_{uuid.uuid4().hex[:8]}",
            "industry_category": "Logistics",
            "webhook_url": "https://attacker.example/webhook",
            "interest_manifesto": "Attacker agent manifesto",
        },
    )
    attacker_key = res_b.json()["api_key"]

    # Attacker tries to rotate Victim's key -> 403 Forbidden
    hack_attempt = await client.post(
        f"/api/v1/agents/{agent_a_id}/rotate-api-key",
        headers={"X-Agent-API-Key": attacker_key},
    )
    assert hack_attempt.status_code == 403
    assert "Not authorized" in hack_attempt.json()["detail"]


def test_sliding_window_rate_limiter_logic():
    """Verify sliding window rate limiter grants up to limit and denies subsequent requests."""
    limiter = SlidingWindowRateLimiter(requests_per_minute=5)
    client_id = "test_rate_client"

    # First 5 allowed
    for _ in range(5):
        allowed, remaining, _ = limiter.is_allowed(client_id)
        assert allowed is True

    # 6th denied
    allowed, remaining, reset_after = limiter.is_allowed(client_id)
    assert allowed is False
    assert remaining == 0
    assert reset_after > 0
