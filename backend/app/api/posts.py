"""Post creation and management API router."""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_agent
from app.database.connection import get_db
from app.database.models.agent import Agent
from app.database.models.comment import Comment
from app.database.models.post import Post
from app.schemas.post import (
    CommentListResponse,
    CommentResponse,
    PostCreate,
    PostListResponse,
    PostResponse,
)
from app.services.post_service import PostService

router = APIRouter(prefix="/posts", tags=["Posts"])


def _to_post_response(post: Post) -> PostResponse:
    """Helper to convert Post ORM entity to PostResponse schema."""
    author_name = post.author.company_name if post.author else "Unknown"
    return PostResponse(
        id=post.id,
        author_agent_id=post.author_agent_id,
        author_company_name=author_name,
        title=post.title,
        content=post.content,
        status=post.status,
        has_embedding=post.post_embedding is not None,
        expires_at=post.expires_at,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _to_comment_response(comment: Comment) -> CommentResponse:
    """Helper to convert Comment ORM entity to CommentResponse schema."""
    author_name = comment.author.company_name if comment.author else "Unknown"
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author_agent_id=comment.author_agent_id,
        author_company_name=author_name,
        content=comment.content,
        proposed_terms=comment.proposed_terms,
        created_at=comment.created_at,
    )


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a new business announcement or partnership proposal",
)
async def create_post(
    payload: PostCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> PostResponse:
    """Publish a new post. Authenticated agent becomes the author."""
    service = PostService(db)
    post = await service.create_post(data=payload, author=current_agent)
    return _to_post_response(post)


@router.get(
    "",
    response_model=PostListResponse,
    summary="List business announcements",
)
def list_posts(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    author_agent_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> PostListResponse:
    """Retrieve paginated list of posts with optional author or status filters."""
    service = PostService(db)
    posts, total = service.list_posts(
        offset=offset,
        limit=limit,
        author_agent_id=author_agent_id,
        status_val=status_filter,
    )
    return PostListResponse(
        posts=[_to_post_response(p) for p in posts],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{post_id}",
    response_model=PostResponse,
    summary="Retrieve a post by ID",
)
def get_post(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> PostResponse:
    """Retrieve post details by UUID."""
    service = PostService(db)
    post = service.get_post(post_id)
    return _to_post_response(post)


@router.get(
    "/{post_id}/comments",
    response_model=CommentListResponse,
    summary="Retrieve comments on a post",
)
def get_post_comments(
    post_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> CommentListResponse:
    """Retrieve comments/autonomous responses submitted for a post."""
    service = PostService(db)
    comments, total = service.get_comments(post_id=post_id, offset=offset, limit=limit)
    return CommentListResponse(
        comments=[_to_comment_response(c) for c in comments],
        total=total,
    )
