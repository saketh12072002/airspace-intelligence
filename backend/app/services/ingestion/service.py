"""Ingestion service — periodically fetches ADS-B data and caches it in Redis.

The service is intentionally decoupled from FastAPI routes.  It can be run as a
standalone ``asyncio`` worker (see :mod:`app.services.ingestion.worker`) or
started inside the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Optional, Tuple

import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.repositories.base import HistoryRepositoryBase
from app.schemas.aircraft_state import AircraftState
from app.services.base import ADSBProvider
from app.services.opensky.client import OpenSkyRateLimitError

logger = get_logger(__name__)

# Redis key conventions
REDIS_KEY_AIRCRAFT_STATES = "aircraft:states"  # Hash: icao24 → JSON
REDIS_KEY_LAST_INGESTION = "aircraft:last_ingestion"  # String: ISO timestamp
REDIS_KEY_AIRCRAFT_COUNT = "aircraft:count"  # String: int
REDIS_CHANNEL_AIRCRAFT_UPDATE = "aircraft:update"  # Pub/Sub notification channel


class IngestionService:
    """Periodically polls an :class:`ADSBProvider` and stores results in Redis.

    Args:
        provider: Any concrete ADS-B provider (OpenSky, etc.).
        redis_client: An ``aioredis`` client instance.
        poll_interval: Seconds between polling cycles.
        bounds: Optional ``(lamin, lomin, lamax, lomax)`` bounding box.
        history_repo: Optional history repository for capturing flight tracks.
    """

    def __init__(
        self,
        provider: ADSBProvider,
        redis_client: aioredis.Redis,
        poll_interval: int = 10,
        bounds: Optional[Tuple[float, float, float, float]] = None,
        history_repo: Optional[HistoryRepositoryBase] = None,
    ) -> None:
        self.provider = provider
        self.redis = redis_client
        self.poll_interval = max(poll_interval, 5)  # Never faster than 5s (OpenSky hard limit)
        self.bounds = bounds
        self.history_repo = history_repo
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the ingestion loop in a background task."""
        if self._running:
            logger.warning("IngestionService is already running")
            return

        await self.provider.connect()
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="ingestion-loop")
        logger.info(
            "IngestionService started (interval=%ds, bounds=%s)",
            self.poll_interval,
            self.bounds,
        )

    async def stop(self) -> None:
        """Signal the loop to stop and wait for it to finish."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self.provider.disconnect()
        logger.info("IngestionService stopped")

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Run ingestion cycles until stopped."""
        while self._running:
            try:
                await self.ingest_once()
            except asyncio.CancelledError:
                break
            except OpenSkyRateLimitError as exc:
                backoff = exc.retry_after or self.poll_interval * 2
                logger.warning("Rate-limited — backing off %ds", backoff)
                await asyncio.sleep(backoff)
                continue
            except Exception:
                logger.exception("Unhandled error during ingestion cycle")

            await asyncio.sleep(self.poll_interval)

    # ------------------------------------------------------------------
    # Single ingestion cycle
    # ------------------------------------------------------------------

    async def ingest_once(self) -> list[AircraftState]:
        """Execute one fetch→store cycle. Returns the fetched states.

        This method is public so that tests and one-shot scripts can call it
        without starting the background loop.
        """
        t0 = time.monotonic()

        states = await self.provider.fetch_aircraft_states(bounds=self.bounds)
        elapsed_ms = (time.monotonic() - t0) * 1000

        if states:
            await self._store_states(states)

        logger.info(
            "Ingestion cycle complete: %d aircraft in %.0f ms",
            len(states),
            elapsed_ms,
        )
        return states

    # ------------------------------------------------------------------
    # Redis storage
    # ------------------------------------------------------------------

    async def _store_states(self, states: list[AircraftState]) -> None:
        """Write all aircraft states into a Redis hash keyed by icao24.

        Each value is the full :class:`AircraftState` serialised as JSON.
        A pipeline is used to batch the writes for efficiency.
        """
        now = datetime.now(UTC).isoformat()

        pipe = self.redis.pipeline(transaction=False)

        # Clear old state and write fresh snapshot
        pipe.delete(REDIS_KEY_AIRCRAFT_STATES)
        for state in states:
            pipe.hset(
                REDIS_KEY_AIRCRAFT_STATES,
                state.icao24,
                state.model_dump_json(),
            )

        pipe.set(REDIS_KEY_LAST_INGESTION, now)
        pipe.set(REDIS_KEY_AIRCRAFT_COUNT, len(states))

        # Set a TTL so stale data auto-expires if ingestion stops
        pipe.expire(REDIS_KEY_AIRCRAFT_STATES, self.poll_interval * 5)

        await pipe.execute()

        # Update historical track records if history repository configured
        if self.history_repo:
            try:
                await self.history_repo.record_positions(states)
            except Exception:
                logger.exception("Failed to record position history in history_repo")

        # Notify the FastAPI StateListener via Redis Pub/Sub.
        await self.redis.publish(REDIS_CHANNEL_AIRCRAFT_UPDATE, now)

        logger.debug("Stored %d states in Redis (last_ingestion=%s)", len(states), now)

    # ------------------------------------------------------------------
    # Read helpers (used by API routes later)
    # ------------------------------------------------------------------

    async def get_all_states(self) -> list[AircraftState]:
        """Read all cached aircraft states from Redis."""
        raw: dict[bytes, bytes] = await self.redis.hgetall(REDIS_KEY_AIRCRAFT_STATES)
        return [AircraftState.model_validate_json(v) for v in raw.values()]

    async def get_state(self, icao24: str) -> Optional[AircraftState]:
        """Read a single aircraft state from Redis by ICAO 24-bit address."""
        raw: Optional[bytes] = await self.redis.hget(REDIS_KEY_AIRCRAFT_STATES, icao24)
        if raw is None:
            return None
        return AircraftState.model_validate_json(raw)
