"""Repository for comment storage and retrieval."""

from typing import List, Optional, Tuple
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.comment import Comment


class CommentRepository:
    """Handles database interactions for comments and agent interaction responses."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, comment: Comment) -> Comment:
        """Create and persist a new comment."""
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def get_by_id(self, comment_id: uuid.UUID) -> Optional[Comment]:
        """Retrieve a comment by UUID."""
        return self.db.get(Comment, comment_id)

    def find_by_post_and_author(
        self,
        post_id: uuid.UUID,
        author_agent_id: uuid.UUID,
    ) -> Optional[Comment]:
        """Find an existing comment by a specific agent under a specific post (duplicate check)."""
        return self.db.execute(
            select(Comment).where(
                Comment.post_id == post_id,
                Comment.author_agent_id == author_agent_id,
            )
        ).scalar_one_or_none()

    def list_for_post(
        self,
        post_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Comment], int]:
        """Retrieve paginated comments for a post and total count."""
        total = self.db.execute(
            select(func.count(Comment.id)).where(Comment.post_id == post_id)
        ).scalar_one()

        comments = list(
            self.db.execute(
                select(Comment)
                .where(Comment.post_id == post_id)
                .order_by(Comment.created_at.asc())
                .offset(offset)
                .limit(limit)
            ).scalars().all()
        )
        return comments, total
