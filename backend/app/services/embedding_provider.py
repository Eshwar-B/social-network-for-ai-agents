"""Replaceable embedding provider abstraction and concrete implementations."""

from abc import ABC, abstractmethod
import hashlib
import math
from typing import List, Optional

from app.config import settings
from app.core.logging import logger


class BaseEmbeddingProvider(ABC):
    """Abstract interface for text embedding providers."""

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the fixed dimension of the generated embeddings."""
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate a dense vector embedding for the input text."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate dense vector embeddings for a batch of texts."""
        pass


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """Production provider using OpenAI text-embedding-3-small."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        if not self.api_key:
            raise ValueError("OpenAI API key must be provided for OpenAIEmbeddingProvider.")

        # Lazy import openai
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=self.api_key)

    def get_dimension(self) -> int:
        return self.dimension

    async def embed_text(self, text: str) -> List[float]:
        cleaned = text.strip().replace("\n", " ")
        response = await self.client.embeddings.create(
            input=[cleaned],
            model=self.model,
            dimensions=self.dimension,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        cleaned = [t.strip().replace("\n", " ") for t in texts]
        response = await self.client.embeddings.create(
            input=cleaned,
            model=self.model,
            dimensions=self.dimension,
        )
        return [item.embedding for item in response.data]


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic local mock embedding provider for testing and offline environments.

    Uses a deterministic feature-hashing algorithm with L2 normalization to produce
    reproducible 1536-dimensional unit vectors. Texts sharing words or semantic tokens
    will have measurably higher cosine similarity than unrelated texts.
    """

    def __init__(self, dimension: int = 1536) -> None:
        self.dimension = dimension

    def get_dimension(self) -> int:
        return self.dimension

    def _generate_vector(self, text: str) -> List[float]:
        """Generate a deterministic 1536-D unit vector based on input text tokens."""
        vector = [0.0] * self.dimension
        words = text.lower().split()
        if not words:
            # Fallback zero vector or minimal epsilon
            vector[0] = 1.0
            return vector

        for word in words:
            # Map word to 4 different dimensions using multiple salt hashes
            for salt in (b"dim1", b"dim2", b"dim3", b"dim4"):
                h = hashlib.sha256(word.encode("utf-8") + salt).digest()
                idx = int.from_bytes(h[:4], "big") % self.dimension
                val = (int.from_bytes(h[4:6], "big") / 32768.0) - 1.0
                vector[idx] += val

        # Compute L2 norm
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 1e-9:
            vector = [x / norm for x in vector]
        else:
            vector[0] = 1.0

        return vector

    async def embed_text(self, text: str) -> List[float]:
        return self._generate_vector(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._generate_vector(t) for t in texts]


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Factory creating the configured embedding provider."""
    provider_name = (settings.EMBEDDING_PROVIDER or "mock").lower()

    if provider_name == "openai" and settings.OPENAI_API_KEY:
        try:
            logger.info("Initializing OpenAIEmbeddingProvider with model %s", settings.EMBEDDING_MODEL)
            return OpenAIEmbeddingProvider()
        except Exception as exc:
            logger.warning("Failed to initialize OpenAI provider (%s), falling back to MockEmbeddingProvider", exc)
            return MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)

    logger.info("Using MockEmbeddingProvider (dimension=%d)", settings.EMBEDDING_DIMENSION)
    return MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
