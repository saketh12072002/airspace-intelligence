"""FastAPI application entry-point."""

from __future__ import annotations

import contextlib

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.api.routes import health
from app.ws.aircraft_manager import aircraft_manager
from app.ws.routes import router as ws_router
from app.ws.state_listener import StateListener

# Setup logging before anything else
setup_logging()
logger = get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for the FastAPI application.

    Starts the Redis-backed :class:`StateListener` which bridges the
    ingestion worker and connected WebSocket clients.
    """
    settings = get_settings()
    logger.info("Starting up Airspace Intelligence API...")

    # --- Redis for the state listener ---
    redis_client: aioredis.Redis | None = None
    listener: StateListener | None = None

    if settings.redis_url:
        try:
            redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)
            listener = StateListener(redis_client=redis_client, manager=aircraft_manager)
            await listener.start()
            logger.info("StateListener started — streaming aircraft updates to /ws/aircraft")
        except Exception:
            logger.exception("Failed to start StateListener (continuing without it)")
            redis_client = None
            listener = None

    yield

    # Shutdown
    if listener:
        await listener.stop()
    if redis_client:
        await redis_client.aclose()
    logger.info("Shutting down Airspace Intelligence API...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="Airspace Intelligence API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    from app.api.routes import api_router, health
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    return app


app = create_app()
