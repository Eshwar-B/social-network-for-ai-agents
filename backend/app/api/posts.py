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
from app.schemas.comment import CommentCreate
from app.schemas.post import (
    CommentListResponse,
    CommentResponse,
    PostCreate,
    PostListResponse,
    PostResponse,
)
from app.services.comment_service import CommentService
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


@router.post(
    "/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an autonomous response or comment to a post",
)
def create_comment(
    post_id: uuid.UUID,
    payload: CommentCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> CommentResponse:
    """Submit an autonomous response or partnership proposal to a post."""
    service = CommentService(db)
    comment = service.create_comment(
        post_id=post_id,
        author=current_agent,
        data=payload,
    )
    return _to_comment_response(comment)


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


@router.get(
    "/{post_id}/routing-logs",
    summary="Retrieve 3-stage routing decisions and evaluations for a post",
)
def get_post_routing_logs(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve all routing evaluations and recipient decisions for the visualizer."""
    from app.repositories.routing_repository import RoutingRepository
    from app.database.models.agent import Agent

    repo = RoutingRepository(db)
    logs = repo.get_logs_for_post(post_id)

    results = []
    for log in logs:
        target_agent = db.get(Agent, log.target_agent_id)
        results.append({
            "id": str(log.id),
            "post_id": str(log.post_id),
            "target_agent_id": str(log.target_agent_id),
            "target_company_name": target_agent.company_name if target_agent else "Unknown",
            "target_industry": target_agent.industry_category if target_agent else "Unknown",
            "vector_score": round(log.vector_score, 4) if log.vector_score is not None else 0.0,
            "rerank_score": round(log.rerank_score, 4) if log.rerank_score is not None else 0.0,
            "final_score": round(log.final_score, 4) if log.final_score is not None else 0.0,
            "status": log.status,
            "decision_reason": log.decision_reason,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    return {"post_id": str(post_id), "routing_logs": results, "total": len(results)}
