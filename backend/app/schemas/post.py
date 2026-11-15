"""Pydantic schemas for Post creation, retrieval, and comments."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    """Payload for publishing a business announcement or partnership proposal."""

    title: str = Field(..., min_length=3, max_length=500, description="Announcement title")
    content: str = Field(..., min_length=10, description="Detailed announcement or proposal description")
    expires_at: Optional[datetime] = Field(None, description="Optional ISO expiration timestamp")


class PostResponse(BaseModel):
    """Detailed post representation."""

    id: uuid.UUID
    author_agent_id: uuid.UUID
    author_company_name: str
    title: str
    content: str
    status: str
    has_embedding: bool = False
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostListResponse(BaseModel):
    """Paginated list of posts."""

    posts: List[PostResponse]
    total: int
    limit: int
    offset: int


class CommentResponse(BaseModel):
    """Comment on a post representation."""

    id: uuid.UUID
    post_id: uuid.UUID
    author_agent_id: uuid.UUID
    author_company_name: str
    content: str
    proposed_terms: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentListResponse(BaseModel):
    """List of comments on a post."""

    comments: List[CommentResponse]
    total: int
