import logging
import sys
from typing import Optional

from app.core.config import get_settings


def setup_logging() -> None:
    """Setup basic structured logging for the application."""
    settings = get_settings()
    
    # Configure the root logger
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Suppress verbose third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
