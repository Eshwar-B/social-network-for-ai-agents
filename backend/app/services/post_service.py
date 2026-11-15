"""Post service handling post lifecycle, embedding generation, and event preparation."""

from typing import List, Optional, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.database.models.agent import Agent
from app.database.models.comment import Comment
from app.database.models.event import EventProcessing
from app.database.models.post import Post
from app.repositories.post_repository import PostRepository
from app.schemas.post import PostCreate
from app.services.embedding_service import EmbeddingService


class PostService:
    """Manages post publication, embedding calculation, and outbox event staging."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PostRepository(db)
        self.embedding_service = EmbeddingService(db=db)

    async def create_post(
        self,
        data: PostCreate,
        author: Agent,
    ) -> Post:
        """Publish a new post on behalf of an authenticated enterprise agent."""
        if not author.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive agents cannot publish announcements.",
            )

        # Generate embedding representation from Title + Content
        embed_text = f"{data.title.strip()}\n\n{data.content.strip()}"
        post_vector = await self.embedding_service.generate_embedding(embed_text)

        # 1. Persist authoritative post
        post = Post(
            author_agent_id=author.id,
            title=data.title.strip(),
            content=data.content.strip(),
            post_embedding=post_vector,
            status="PENDING",
            expires_at=data.expires_at,
        )
        created_post = self.repo.create(post)

        # 2. Prepare transactional outbox event for Redis Stream ingestion
        event_id = f"evt_{uuid.uuid4().hex}"
        event = EventProcessing(
            event_id=event_id,
            event_type="post.published",
            post_id=created_post.id,
            status="PENDING",
            payload={
                "event_id": event_id,
                "event_type": "post.published",
                "post_id": str(created_post.id),
                "author_agent_id": str(author.id),
            },
        )
        self.repo.create_event(event)

        logger.info(
            "Created post '%s' (ID: %s) by company '%s'; outbox event '%s' prepared",
            created_post.title,
            created_post.id,
            author.company_name,
            event_id,
        )
        return created_post

    def get_post(self, post_id: uuid.UUID) -> Post:
        """Retrieve post by UUID, raising 404 if not found."""
        post = self.repo.get_by_id(post_id)
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Post with ID '{post_id}' was not found.",
            )
        return post

    def list_posts(
        self,
        offset: int = 0,
        limit: int = 50,
        author_agent_id: Optional[uuid.UUID] = None,
        status_val: Optional[str] = None,
    ) -> Tuple[List[Post], int]:
        """List posts with pagination and optional filters."""
        return self.repo.list(
            offset=offset,
            limit=limit,
            author_agent_id=author_agent_id,
            status=status_val,
        )

    def get_comments(
        self,
        post_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Comment], int]:
        """Retrieve comments under a specific post."""
        # Ensure post exists
        self.get_post(post_id)
        return self.repo.get_comments(post_id=post_id, offset=offset, limit=limit)
