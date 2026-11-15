"""Application settings for Asama.ai using Pydantic Settings."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # Application
    APP_NAME: str = "Asama.ai"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5434/asama_ai"
    )

    # Redis Streams
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_STREAM_KEY: str = "asama:stream:posts"
    REDIS_CONSUMER_GROUP: str = "asama:group:routing"
    REDIS_CONSUMER_NAME: str = "routing_worker_1"

    # AI & Embeddings
    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    OPENAI_API_KEY: Optional[str] = None

    # Reranking
    RERANKER_PROVIDER: str = "mock"
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"
    COHERE_API_KEY: Optional[str] = None

    # Routing Parameters
    RELEVANCE_THRESHOLD: float = 0.75
    MAX_RECIPIENTS: int = 5
    TOP_K_CANDIDATES: int = 50

    # Security
    HMAC_SECRET_KEY: str = (
        "asama-default-hmac-secret-change-in-production-32bytes"
    )
    JWT_SECRET_KEY: str = (
        "asama-default-jwt-secret-change-in-production-32bytes"
    )
    ALGORITHM: str = "HS256"
    AGENT_TOKEN_EXPIRE_MINUTES: int = 1440

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
