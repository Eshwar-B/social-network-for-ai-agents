"""Logging configuration for Asama.ai."""

import logging
import sys
from typing import Optional


def configure_logging(level: Optional[str] = "INFO") -> None:
    """Configure root logger with structured console handler."""
    log_level = getattr(logging, (level or "INFO").upper(), logging.INFO)

    log_format = (
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d]: %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    # Set third-party loggers to a slightly less verbose level
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


logger = logging.getLogger("asama_ai")
