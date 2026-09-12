"""Standalone ingestion worker — run independently of the FastAPI process.

Usage::

    python -m app.services.ingestion.worker

The worker reads configuration from environment variables / ``.env`` and runs
the ingestion loop until interrupted with Ctrl-C.
"""

from __future__ import annotations

import asyncio
import signal

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.services.ingestion.service import IngestionService
from app.services.opensky.client import OpenSkyClient

setup_logging()
logger = get_logger(__name__)


async def main() -> None:
    """Bootstrap and run the ingestion loop."""
    settings = get_settings()

    # --- Redis ---
    redis_client = aioredis.from_url(
        settings.redis_url,
        decode_responses=False,
    )
    logger.info("Connected to Redis at %s", settings.redis_url)

    # --- Provider ---
    provider = OpenSkyClient(settings)

    # --- Service ---
    service = IngestionService(
        provider=provider,
        redis_client=redis_client,
        poll_interval=settings.ingestion_interval_seconds,
        bounds=settings.parsed_ingestion_bounds,
    )

    # --- Graceful shutdown ---
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    # --- Run ---
    await service.start()

    try:
        await stop_event.wait()
    finally:
        await service.stop()
        await redis_client.aclose()
        logger.info("Worker shut down cleanly")


if __name__ == "__main__":
    asyncio.run(main())
