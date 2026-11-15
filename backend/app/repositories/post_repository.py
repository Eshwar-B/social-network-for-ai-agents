"""Repository for Post, Comment, and Outbox Event database operations."""

from typing import List, Optional, Tuple
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database.models.comment import Comment
from app.database.models.event import EventProcessing
from app.database.models.post import Post


class PostRepository:
    """Encapsulates database operations for Posts, Comments, and Event Records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, post: Post) -> Post:
        """Persist a new Post."""
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def get_by_id(self, post_id: uuid.UUID) -> Optional[Post]:
        """Retrieve post by primary UUID, eagerly loading author."""
        return self.db.execute(
            select(Post)
            .options(joinedload(Post.author))
            .where(Post.id == post_id)
        ).scalar_one_or_none()

    def list(
        self,
        offset: int = 0,
        limit: int = 50,
        author_agent_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[Post], int]:
        """List posts with pagination and optional author/status filters."""
        query = select(Post).options(joinedload(Post.author))
        count_query = select(func.count(Post.id))

        if author_agent_id is not None:
            query = query.where(Post.author_agent_id == author_agent_id)
            count_query = count_query.where(Post.author_agent_id == author_agent_id)

        if status is not None:
            query = query.where(Post.status == status)
            count_query = count_query.where(Post.status == status)

        total = self.db.execute(count_query).scalar() or 0
        posts = (
            self.db.execute(
                query.order_by(Post.created_at.desc()).offset(offset).limit(limit)
            )
            .scalars()
            .all()
        )
        return list(posts), total

    def update_status(self, post: Post, status_val: str) -> Post:
        """Update post processing status."""
        post.status = status_val
        self.db.commit()
        self.db.refresh(post)
        return post

    def get_comments(
        self,
        post_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Comment], int]:
        """Retrieve comments for a post."""
        query = (
            select(Comment)
            .options(joinedload(Comment.author))
            .where(Comment.post_id == post_id)
            .order_by(Comment.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        count_query = select(func.count(Comment.id)).where(Comment.post_id == post_id)

        total = self.db.execute(count_query).scalar() or 0
        comments = self.db.execute(query).scalars().all()
        return list(comments), total

    def add_comment(self, comment: Comment) -> Comment:
        """Add a comment/response to a post."""
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def create_event(self, event: EventProcessing) -> EventProcessing:
        """Create an outbox event record within transactional context."""
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
