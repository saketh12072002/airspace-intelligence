"""State listener — bridges the ingestion worker and WebSocket clients.

Subscribes to a Redis Pub/Sub channel that the ingestion worker publishes to
after every cycle.  On each notification the listener:

1.  Reads the latest aircraft snapshot from Redis.
2.  Computes a diff (added / updated / removed) against the previous snapshot.
3.  Broadcasts the diff to all connected WebSocket clients.

This runs as a background ``asyncio.Task`` inside the FastAPI process.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.schemas.aircraft_state import AircraftState
from app.services.ingestion.service import REDIS_KEY_AIRCRAFT_STATES
from app.ws.aircraft_manager import AircraftConnectionManager
from app.ws.diff import StateDiff, compute_diff

logger = get_logger(__name__)

# Redis Pub/Sub channel the ingestion worker publishes to.
REDIS_CHANNEL_AIRCRAFT_UPDATE = "aircraft:update"


class StateListener:
    """Listens for ingestion notifications and broadcasts diffs to WebSocket clients.

    Args:
        redis_client: An ``aioredis`` client instance (separate from the one used
            for pub/sub subscription — ``aioredis`` requires a dedicated connection
            for subscribe mode).
        manager: The :class:`AircraftConnectionManager` to broadcast to.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        manager: AircraftConnectionManager,
    ) -> None:
        self.redis = redis_client
        self.manager = manager
        self._previous: Dict[str, AircraftState] = {}
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None

        # Basic metrics
        self.cycles: int = 0
        self.total_broadcast_ms: float = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start listening in a background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_loop(), name="state-listener")
        logger.info("StateListener started (channel=%s)", REDIS_CHANNEL_AIRCRAFT_UPDATE)

    async def stop(self) -> None:
        """Stop the listener."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("StateListener stopped (cycles=%d)", self.cycles)

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    async def _listen_loop(self) -> None:
        """Subscribe to the Redis channel and process notifications."""
        pubsub = self.redis.pubsub()
        try:
            await pubsub.subscribe(REDIS_CHANNEL_AIRCRAFT_UPDATE)
            logger.info("Subscribed to Redis channel %s", REDIS_CHANNEL_AIRCRAFT_UPDATE)

            while self._running:
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                    if message is not None and message.get("type") == "message":
                        await self._on_update()
                    else:
                        # No message received within timeout — yield control.
                        await asyncio.sleep(0.05)
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Error in state listener loop")
                    await asyncio.sleep(1)
        finally:
            await pubsub.unsubscribe(REDIS_CHANNEL_AIRCRAFT_UPDATE)
            await pubsub.aclose()

    # ------------------------------------------------------------------
    # Update handler
    # ------------------------------------------------------------------

    async def _on_update(self) -> None:
        """Read latest state from Redis, diff, and broadcast."""
        t0 = time.monotonic()

        # Read the full snapshot from the Redis hash.
        raw: dict[bytes | str, bytes | str] = await self.redis.hgetall(REDIS_KEY_AIRCRAFT_STATES)
        current: Dict[str, AircraftState] = {}
        for _key, val in raw.items():
            try:
                v = val if isinstance(val, (str, bytes)) else str(val)
                state = AircraftState.model_validate_json(v)
                current[state.icao24] = state
            except Exception:
                continue  # skip unparseable entries

        # Compute diff.
        diff = compute_diff(self._previous, current)
        self._previous = current
        self.cycles += 1

        if not diff.has_changes and self.manager.client_count == 0:
            return

        # Build the broadcast message.
        msg = _build_update_message(diff)
        elapsed_ms = (time.monotonic() - t0) * 1000
        self.total_broadcast_ms += elapsed_ms

        if diff.has_changes:
            await self.manager.broadcast(msg)

        logger.info(
            "Broadcast cycle #%d: %s (%d clients, %.0f ms)",
            self.cycles,
            diff.summary,
            self.manager.client_count,
            elapsed_ms,
        )


def _build_update_message(diff: StateDiff) -> dict[str, Any]:
    """Serialise a :class:`StateDiff` into the wire-format dict."""
    return {
        "type": "aircraft_update",
        "timestamp": datetime.now(UTC).isoformat(),
        "added": [s.model_dump(mode="json") for s in diff.added],
        "updated": [s.model_dump(mode="json") for s in diff.updated],
        "removed": diff.removed,
    }
