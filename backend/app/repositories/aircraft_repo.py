"""Aircraft repository querying Redis latest state store with spatial and filter queries."""

from __future__ import annotations

import math
from typing import Optional, Tuple
import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.repositories.base import AircraftRepositoryBase
from app.schemas.aircraft_state import AircraftState

logger = get_logger(__name__)
REDIS_KEY_AIRCRAFT_STATES = "aircraft:states"


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class RedisAircraftRepository(AircraftRepositoryBase):
    """Concrete repository reading real-time normalized aircraft states from Redis."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def get_by_icao24(self, icao24: str) -> Optional[AircraftState]:
        clean_icao = icao24.strip().lower()
        raw = await self.redis.hget(REDIS_KEY_AIRCRAFT_STATES, clean_icao)
        if not raw:
            return None
        try:
            return AircraftState.model_validate_json(raw)
        except Exception as e:
            logger.error("Failed to parse state for %s: %s", clean_icao, e)
            return None

    async def get_all(self) -> list[AircraftState]:
        raw_dict = await self.redis.hgetall(REDIS_KEY_AIRCRAFT_STATES)
        results: list[AircraftState] = []
        for val in raw_dict.values():
            try:
                results.append(AircraftState.model_validate_json(val))
            except Exception:
                continue
        return results

    async def search(
        self,
        callsign: Optional[str] = None,
        icao24: Optional[str] = None,
        country: Optional[str] = None,
        bounds: Optional[Tuple[float, float, float, float]] = None,
        limit: int = 50,
    ) -> list[AircraftState]:
        all_states = await self.get_all()

        c_callsign = callsign.strip().upper() if callsign else None
        c_icao = icao24.strip().lower() if icao24 else None
        c_country = country.strip().lower() if country else None

        filtered: list[AircraftState] = []
        for s in all_states:
            if c_icao and s.icao24.lower() != c_icao:
                continue

            if c_callsign:
                if not s.callsign or c_callsign not in s.callsign.strip().upper():
                    continue

            if c_country:
                if not s.origin_country or c_country not in s.origin_country.strip().lower():
                    continue

            if bounds is not None:
                lamin, lomin, lamax, lomax = bounds
                if s.latitude is None or s.longitude is None:
                    continue
                if not (lamin <= s.latitude <= lamax and lomin <= s.longitude <= lomax):
                    continue

            filtered.append(s)
            if len(filtered) >= limit:
                break

        return filtered

    async def search_in_radius(
        self,
        lat: float,
        lon: float,
        radius_km: float,
        min_altitude_m: Optional[float] = None,
        max_altitude_m: Optional[float] = None,
        limit: int = 50,
    ) -> list[tuple[AircraftState, float]]:
        all_states = await self.get_all()
        in_range: list[tuple[AircraftState, float]] = []

        for s in all_states:
            if s.latitude is None or s.longitude is None:
                continue

            if min_altitude_m is not None:
                alt = s.baro_altitude or 0.0
                if alt < min_altitude_m:
                    continue

            if max_altitude_m is not None:
                alt = s.baro_altitude or 0.0
                if alt > max_altitude_m:
                    continue

            dist = _haversine_distance(lat, lon, s.latitude, s.longitude)
            if dist <= radius_km:
                in_range.append((s, round(dist, 2)))

        # Sort closest first
        in_range.sort(key=lambda x: x[1])
        return in_range[:limit]


class InMemoryAircraftRepository(AircraftRepositoryBase):
    """In-memory aircraft repository for deterministic testing and standalone use."""

    def __init__(self, initial_states: Optional[list[AircraftState]] = None) -> None:
        self._states: dict[str, AircraftState] = {}
        if initial_states:
            for s in initial_states:
                self._states[s.icao24.lower()] = s

    def set_state(self, state: AircraftState) -> None:
        self._states[state.icao24.lower()] = state

    async def upsert(self, state: AircraftState) -> None:
        self.set_state(state)

    async def upsert_many(self, states: list[AircraftState]) -> None:
        for s in states:
            self.set_state(s)

    async def get_by_icao24(self, icao24: str) -> Optional[AircraftState]:
        return self._states.get(icao24.strip().lower())

    async def get_all(self) -> list[AircraftState]:
        return list(self._states.values())

    async def search(
        self,
        callsign: Optional[str] = None,
        icao24: Optional[str] = None,
        country: Optional[str] = None,
        bounds: Optional[Tuple[float, float, float, float]] = None,
        limit: int = 50,
    ) -> list[AircraftState]:
        c_callsign = callsign.strip().upper() if callsign else None
        c_icao = icao24.strip().lower() if icao24 else None
        c_country = country.strip().lower() if country else None

        filtered: list[AircraftState] = []
        for s in self._states.values():
            if c_icao and s.icao24.lower() != c_icao:
                continue
            if c_callsign:
                if not s.callsign or c_callsign not in s.callsign.strip().upper():
                    continue
            if c_country:
                if not s.origin_country or c_country not in s.origin_country.strip().lower():
                    continue
            if bounds is not None:
                lamin, lomin, lamax, lomax = bounds
                if s.latitude is None or s.longitude is None:
                    continue
                if not (lamin <= s.latitude <= lamax and lomin <= s.longitude <= lomax):
                    continue
            filtered.append(s)
            if len(filtered) >= limit:
                break
        return filtered

    async def search_in_radius(
        self,
        lat: float,
        lon: float,
        radius_km: float,
        min_altitude_m: Optional[float] = None,
        max_altitude_m: Optional[float] = None,
        limit: int = 50,
    ) -> list[tuple[AircraftState, float]]:
        in_range: list[tuple[AircraftState, float]] = []
        for s in self._states.values():
            if s.latitude is None or s.longitude is None:
                continue
            if min_altitude_m is not None:
                alt = s.baro_altitude or 0.0
                if alt < min_altitude_m:
                    continue
            if max_altitude_m is not None:
                alt = s.baro_altitude or 0.0
                if alt > max_altitude_m:
                    continue
            dist = _haversine_distance(lat, lon, s.latitude, s.longitude)
            if dist <= radius_km:
                in_range.append((s, round(dist, 2)))

        in_range.sort(key=lambda x: x[1])
        return in_range[:limit]
