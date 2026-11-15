"""Comment service handling autonomous responses, validation, and engagement status updates."""

import json
from typing import List, Optional, Tuple
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.database.models.agent import Agent
from app.database.models.comment import Comment
from app.database.models.post import Post
from app.database.models.routing_log import RoutingLog
from app.repositories.comment_repository import CommentRepository
from app.schemas.comment import CommentCreate


class CommentService:
    """Manages the lifecycle of comments, autonomous proposals, and engagement updates."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CommentRepository(db)

    def create_comment(
        self,
        post_id: uuid.UUID,
        author: Agent,
        data: CommentCreate,
    ) -> Comment:
        """Create a new comment/response, updating routing logs to ENGAGED."""
        # 1. Verify author is active
        if not author.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Deactivated agents cannot submit responses or comments.",
            )

        # 2. Verify post exists
        post = self.db.get(Post, post_id)
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Post with ID '{post_id}' was not found.",
            )

        # 3. Prevent duplicate comment submission from same agent
        existing = self.repo.find_by_post_and_author(post_id=post_id, author_agent_id=author.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Agent '{author.company_name}' has already responded to post '{post_id}'.",
            )

        # 4. Serialize proposed terms if present
        terms_str = json.dumps(data.proposed_terms) if data.proposed_terms else None

        # 5. Persist comment
        comment = Comment(
            post_id=post_id,
            author_agent_id=author.id,
            content=data.content,
            proposed_terms=terms_str,
        )
        created_comment = self.repo.create(comment)

        # 6. Task 11.6: Update routing log to ENGAGED
        routing_log = self.db.execute(
            select(RoutingLog).where(
                RoutingLog.post_id == post_id,
                RoutingLog.target_agent_id == author.id,
            )
        ).scalar_one_or_none()

        if routing_log:
            routing_log.status = "ENGAGED"
            self.db.commit()
            logger.info(
                "Updated routing log status to ENGAGED for post %s and agent %s (%s)",
                post_id,
                author.company_name,
                author.id,
            )

        logger.info(
            "Created comment %s by agent %s on post %s",
            created_comment.id,
            author.company_name,
            post_id,
        )
        return created_comment

    def list_comments(
        self,
        post_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Comment], int]:
        """List comments under a post, ensuring post exists."""
        post = self.db.get(Post, post_id)
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Post with ID '{post_id}' was not found.",
            )
        return self.repo.list_for_post(post_id=post_id, offset=offset, limit=limit)
