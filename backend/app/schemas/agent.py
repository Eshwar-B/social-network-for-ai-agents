"""Pydantic schemas for Agent registration, retrieval, and updates."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentBase(BaseModel):
    """Shared properties for company AI agents."""

    company_name: str = Field(..., min_length=2, max_length=255, description="Unique company name")
    industry_category: str = Field(..., min_length=2, max_length=100, description="Industry sector")
    webhook_url: str = Field(..., min_length=8, max_length=1024, description="HTTP/HTTPS webhook URL")
    interest_manifesto: str = Field(..., min_length=10, description="Business interest statement")

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Webhook URL must begin with http:// or https://")
        return v


class AgentCreate(AgentBase):
    """Payload for registering a new company AI agent."""
    pass


class AgentUpdate(BaseModel):
    """Payload for updating an existing agent profile."""

    industry_category: Optional[str] = Field(None, min_length=2, max_length=100)
    webhook_url: Optional[str] = Field(None, min_length=8, max_length=1024)
    interest_manifesto: Optional[str] = Field(None, min_length=10)

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Webhook URL must begin with http:// or https://")
        return v


class AgentResponse(BaseModel):
    """Public agent profile representation."""

    id: uuid.UUID
    company_name: str
    industry_category: str
    webhook_url: str
    interest_manifesto: str
    embedding_status: str
    has_embedding: bool = False
    trust_score: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentRegistrationResponse(BaseModel):
    """Response returned upon successful agent registration, including API key."""

    agent: AgentResponse
    api_key: str = Field(..., description="Secret API key for authenticating as this agent. Store securely.")
    message: str = "Agent registered successfully."


class AgentListResponse(BaseModel):
    """Paginated list of registered agents."""

    agents: List[AgentResponse]
    total: int
    limit: int
    offset: int
