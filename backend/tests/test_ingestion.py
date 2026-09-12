"""Tests for the ingestion service with mocked provider and Redis."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.aircraft_state import AircraftState
from app.services.base import ADSBProvider
from app.services.ingestion.service import (
    REDIS_KEY_AIRCRAFT_COUNT,
    REDIS_KEY_AIRCRAFT_STATES,
    REDIS_KEY_LAST_INGESTION,
    IngestionService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_aircraft_state(icao24: str = "abc123", **kwargs: Any) -> AircraftState:
    """Build a sample AircraftState with sensible defaults."""
    defaults = dict(
        icao24=icao24,
        callsign="TEST1234",
        origin_country="United States",
        time_position=1609459200,
        last_contact=1609459201,
        longitude=-122.375,
        latitude=37.6188,
        baro_altitude=10972.8,
        on_ground=False,
        velocity=257.15,
        true_track=135.0,
        vertical_rate=0.0,
        geo_altitude=11277.6,
        squawk="1234",
        position_source=0,
        category=1,
    )
    defaults.update(kwargs)
    return AircraftState(**defaults)


class FakeProvider(ADSBProvider):
    """In-memory provider for testing — returns a fixed list of states."""

    def __init__(self, states: Optional[List[AircraftState]] = None) -> None:
        self.states = states or []
        self.connected = False
        self.fetch_count = 0

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def fetch_states(
        self, bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> List[Dict[str, Any]]:
        return [s.model_dump() for s in self.states]

    async def fetch_aircraft_states(
        self, bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> List[AircraftState]:
        self.fetch_count += 1
        return list(self.states)


class FakeRedis:
    """Minimal async Redis mock for testing pipeline operations."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._hashes: dict[str, dict[str, bytes]] = {}
        self._ttls: dict[str, int] = {}

    def pipeline(self, transaction: bool = True) -> "FakePipeline":
        return FakePipeline(self)

    async def hgetall(self, key: str) -> dict[bytes, bytes]:
        return {
            k.encode(): v if isinstance(v, bytes) else v.encode()
            for k, v in self._hashes.get(key, {}).items()
        }

    async def hget(self, key: str, field: str) -> Optional[bytes]:
        h = self._hashes.get(key, {})
        val = h.get(field)
        if val is None:
            return None
        return val if isinstance(val, bytes) else val.encode()

    async def aclose(self) -> None:
        pass

    async def publish(self, channel: str, message: Any) -> int:
        """Fake publish — just records the message, returns subscriber count."""
        self._store.setdefault("_published", []).append((channel, message))
        return 0


class FakePipeline:
    """Minimal pipeline mock that executes operations eagerly on FakeRedis."""

    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple[str, tuple[Any, ...]]] = []

    def delete(self, key: str) -> "FakePipeline":
        self._ops.append(("delete", (key,)))
        return self

    def hset(self, key: str, field: str, value: Any) -> "FakePipeline":
        self._ops.append(("hset", (key, field, value)))
        return self

    def set(self, key: str, value: Any) -> "FakePipeline":
        self._ops.append(("set", (key, value)))
        return self

    def expire(self, key: str, ttl: int) -> "FakePipeline":
        self._ops.append(("expire", (key, ttl)))
        return self

    async def execute(self) -> list[Any]:
        results: list[Any] = []
        for op, args in self._ops:
            if op == "delete":
                self._redis._hashes.pop(args[0], None)
                self._redis._store.pop(args[0], None)
            elif op == "hset":
                key, field, value = args
                self._redis._hashes.setdefault(key, {})[field] = value
            elif op == "set":
                key, value = args
                self._redis._store[key] = value
            elif op == "expire":
                key, ttl = args
                self._redis._ttls[key] = ttl
            results.append(True)
        self._ops.clear()
        return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_once_stores_in_redis() -> None:
    """A single ingestion cycle should store all states in the Redis hash."""
    states = [_make_aircraft_state(f"ac{i:04x}") for i in range(3)]
    provider = FakeProvider(states)
    redis = FakeRedis()
    service = IngestionService(provider, redis, poll_interval=10)  # type: ignore[arg-type]

    result = await service.ingest_once()

    assert len(result) == 3
    assert provider.fetch_count == 1

    # Verify Redis contents
    stored = await service.get_all_states()
    assert len(stored) == 3
    icao_set = {s.icao24 for s in stored}
    assert icao_set == {"ac0000", "ac0001", "ac0002"}


@pytest.mark.asyncio
async def test_ingest_once_empty_does_not_crash() -> None:
    """An empty fetch result should not error or write to Redis."""
    provider = FakeProvider([])
    redis = FakeRedis()
    service = IngestionService(provider, redis, poll_interval=10)  # type: ignore[arg-type]

    result = await service.ingest_once()

    assert result == []
    stored = await service.get_all_states()
    assert stored == []


@pytest.mark.asyncio
async def test_get_state_by_icao() -> None:
    """get_state should retrieve a single aircraft by icao24."""
    states = [_make_aircraft_state("aabbcc")]
    provider = FakeProvider(states)
    redis = FakeRedis()
    service = IngestionService(provider, redis, poll_interval=10)  # type: ignore[arg-type]

    await service.ingest_once()

    single = await service.get_state("aabbcc")
    assert single is not None
    assert single.icao24 == "aabbcc"

    missing = await service.get_state("ffffff")
    assert missing is None


@pytest.mark.asyncio
async def test_ingest_replaces_previous_snapshot() -> None:
    """Each ingestion cycle should fully replace the previous Redis snapshot."""
    provider = FakeProvider([_make_aircraft_state("first1")])
    redis = FakeRedis()
    service = IngestionService(provider, redis, poll_interval=10)  # type: ignore[arg-type]

    await service.ingest_once()

    # Change the provider data
    provider.states = [_make_aircraft_state("second")]
    await service.ingest_once()

    stored = await service.get_all_states()
    assert len(stored) == 1
    assert stored[0].icao24 == "second"


@pytest.mark.asyncio
async def test_poll_interval_enforced_minimum() -> None:
    """poll_interval should never go below 5 seconds (OpenSky hard limit)."""
    provider = FakeProvider()
    redis = FakeRedis()
    service = IngestionService(provider, redis, poll_interval=1)  # type: ignore[arg-type]

    assert service.poll_interval == 5


@pytest.mark.asyncio
async def test_aircraft_state_serialization() -> None:
    """AircraftState should round-trip through JSON serialization cleanly."""
    original = _make_aircraft_state("aabbcc")
    json_str = original.model_dump_json()
    restored = AircraftState.model_validate_json(json_str)

    assert restored.icao24 == original.icao24
    assert restored.callsign == original.callsign
    assert restored.longitude == original.longitude
    assert restored.velocity == original.velocity
    assert restored.category == original.category
