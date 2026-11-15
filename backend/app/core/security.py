"""Security utilities for agent authentication and HMAC signature verification."""

import hashlib
import hmac
import secrets
from typing import Optional
import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.database.models.agent import Agent


def generate_agent_api_key() -> str:
    """Generate a secure, random API key for an agent."""
    token = secrets.token_urlsafe(32)
    return f"asama_ak_{token}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA-256 with HMAC secret salt."""
    return hmac.new(
        settings.HMAC_SECRET_KEY.encode("utf-8"),
        api_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify that a plain API key matches its stored hash in constant time."""
    computed = hash_api_key(plain_key)
    return hmac.compare_digest(computed, hashed_key)


def get_current_agent(
    x_agent_api_key: Optional[str] = Header(None, alias="X-Agent-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> Agent:
    """FastAPI dependency to authenticate requests using an Agent API key."""
    api_key: Optional[str] = None

    if x_agent_api_key:
        api_key = x_agent_api_key.strip()
    elif authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() in ("bearer", "apikey"):
            api_key = parts[1]
        elif len(parts) == 1:
            api_key = parts[0]

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials. Provide X-Agent-API-Key or Authorization header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    key_hash = hash_api_key(api_key)
    agent = db.execute(
        select(Agent).where(Agent.api_key_hash == key_hash)
    ).scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Agent API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent account is deactivated. Contact support or activate agent.",
        )

    return agent
