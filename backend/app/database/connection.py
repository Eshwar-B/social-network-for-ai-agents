"""Database connection and session lifecycle management."""

from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings
from app.core.logging import logger

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False,
)

# Thread-safe session factory
session_factory = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session to FastAPI dependency injection."""
    db = session_factory()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection() -> bool:
    """Verify database connectivity and pgvector extension availability."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            vector_check = conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
            logger.info(
                "Database health check: status=%s, pgvector=%s",
                "healthy" if result == 1 else "unhealthy",
                "available" if vector_check == "vector" else "missing",
            )
            return result == 1 and vector_check == "vector"
    except Exception as exc:
        logger.error("Database connection check failed: %s", exc)
        return False
