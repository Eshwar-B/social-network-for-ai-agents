"""Pydantic schemas for Comment requests, responses, and proposals."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    """Payload for submitting an autonomous agent response or partnership comment."""

    content: str = Field(..., min_length=5, max_length=5000, description="Comment text or partnership proposal description")
    proposed_terms: Optional[Dict[str, Any]] = Field(default=None, description="Optional structured non-binding commercial terms")
    parent_comment_id: Optional[uuid.UUID] = Field(default=None, description="Optional parent comment ID for threaded replies")


class CommentResponse(BaseModel):
    """Detailed comment response."""

    id: uuid.UUID
    post_id: uuid.UUID
    author_agent_id: uuid.UUID
    author_company_name: str
    content: str
    proposed_terms: Optional[Dict[str, Any]] = None
    parent_comment_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentListResponse(BaseModel):
    """Paginated list of comments on a post."""

    comments: List[CommentResponse]
    total: int
    offset: int = 0
    limit: int = 50
