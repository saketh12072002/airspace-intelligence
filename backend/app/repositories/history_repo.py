"""Flight position history repository supporting Redis, memory, and database."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Optional
import json
import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.repositories.base import HistoryRepositoryBase
from app.schemas.aircraft_state import AircraftState

logger = get_logger(__name__)

# Max chronological history records retained per aircraft in memory/cache
MAX_HISTORY_PER_AIRCRAFT = 1000
REDIS_HISTORY_PREFIX = "aircraft:history:"


class HistoryRepository(HistoryRepositoryBase):
    """Chronological position history repository using Redis sorted sets and memory buffer."""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None) -> None:
        self.redis = redis_client
        # In-memory fallback / local fast buffer: icao24 -> deque of state dicts
        self._memory_store: dict[str, deque[dict]] = defaultdict(
            lambda: deque(maxlen=MAX_HISTORY_PER_AIRCRAFT)
        )

    async def record_positions(self, states: list[AircraftState]) -> None:
        """Record position snapshots for aircraft states."""
        now_epoch = int(datetime.now(UTC).timestamp())

        for state in states:
            clean_icao = state.icao24.lower()
            record = {
                "icao24": clean_icao,
                "callsign": state.callsign.strip() if state.callsign else None,
                "timestamp": state.last_contact or state.time_position or now_epoch,
                "latitude": state.latitude,
                "longitude": state.longitude,
                "baro_altitude": state.baro_altitude,
                "velocity": state.velocity,
                "true_track": state.true_track,
                "vertical_rate": state.vertical_rate,
                "on_ground": state.on_ground,
            }

            # 1. Update memory store
            self._memory_store[clean_icao].append(record)

            # 2. Update Redis sorted set if client available
            if self.redis:
                key = f"{REDIS_HISTORY_PREFIX}{clean_icao}"
                score = float(record["timestamp"])
                try:
                    payload = json.dumps(record)
                    # Use pipeline or fire-and-forget in caller for bulk
                    await self.redis.zadd(key, {payload: score})
                    await self.redis.expire(key, 86400)  # 24 hour history retention
                except Exception as e:
                    logger.debug("Redis history zadd error for %s: %s", clean_icao, e)

    async def get_history(
        self,
        icao24: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        clean_icao = icao24.strip().lower()

        start_epoch = int(start_time.timestamp()) if start_time else 0
        end_epoch = int(end_time.timestamp()) if end_time else int(datetime.now(UTC).timestamp()) + 3600

        # Try Redis sorted set first
        if self.redis:
            key = f"{REDIS_HISTORY_PREFIX}{clean_icao}"
            try:
                raw_items = await self.redis.zrangebyscore(
                    key,
                    min=start_epoch,
                    max=end_epoch,
                    start=0,
                    num=limit,
                )
                if raw_items:
                    records = []
                    for item in raw_items:
                        if isinstance(item, bytes):
                            item = item.decode("utf-8")
                        records.append(json.loads(item))
                    # Sort ascending by timestamp
                    records.sort(key=lambda r: r.get("timestamp", 0))
                    return records
            except Exception as e:
                logger.debug("Redis zrangebyscore error for %s: %s", clean_icao, e)

        # Fallback to in-memory store
        records = []
        if clean_icao in self._memory_store:
            for r in self._memory_store[clean_icao]:
                ts = r.get("timestamp", 0)
                if start_epoch <= ts <= end_epoch:
                    records.append(r)
                if len(records) >= limit:
                    break

        records.sort(key=lambda r: r.get("timestamp", 0))
        return records
