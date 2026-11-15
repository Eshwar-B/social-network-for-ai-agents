"""Embedding generation service coordinating providers, validation, and database updates."""

import asyncio
from typing import List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import logger
from app.database.models.agent import Agent
from app.repositories.agent_repository import AgentRepository
from app.services.embedding_provider import BaseEmbeddingProvider, get_embedding_provider


class EmbeddingService:
    """Service for generating, validating, and persisting dense vector embeddings."""

    def __init__(
        self,
        db: Optional[Session] = None,
        provider: Optional[BaseEmbeddingProvider] = None,
    ) -> None:
        self.db = db
        self.provider = provider or get_embedding_provider()
        self.dimension = settings.EMBEDDING_DIMENSION

    async def generate_embedding(self, text: str, max_retries: int = 3) -> List[float]:
        """Generate a dense vector embedding with validation and retries."""
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text.")

        cleaned_text = text.strip()
        last_error: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                vector = await self.provider.embed_text(cleaned_text)
                if len(vector) != self.dimension:
                    raise ValueError(
                        f"Expected embedding dimension {self.dimension}, got {len(vector)}"
                    )
                return vector
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Embedding generation attempt %d/%d failed: %s",
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        logger.error("All embedding attempts failed: %s", last_error)
        raise RuntimeError(f"Failed to generate embedding: {last_error}")

    async def generate_and_save_agent_embedding(
        self,
        agent_id: uuid.UUID,
    ) -> Agent:
        """Generate interest embedding from agent manifesto and persist in database."""
        if not self.db:
            raise RuntimeError("Database session required for saving agent embedding.")

        repo = AgentRepository(self.db)
        agent = repo.get_by_id(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found.",
            )

        try:
            vector = await self.generate_embedding(agent.interest_manifesto)
            updated_agent = repo.update_embedding(agent, vector, status="COMPLETED")
            logger.info(
                "Successfully generated and stored interest embedding for agent '%s' (ID: %s)",
                updated_agent.company_name,
                updated_agent.id,
            )
            return updated_agent
        except Exception as exc:
            logger.error("Failed to generate embedding for agent '%s': %s", agent.company_name, exc)
            repo.update(agent, {"embedding_status": "FAILED"})
            raise
