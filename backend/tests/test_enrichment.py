"""Tests for flight details enrichment and route resolution."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import UTC, datetime
import httpx

from app.schemas.aircraft_state import AircraftState
from app.services.enrichment.service import EnrichmentService, haversine_distance_km


class FakeRedis:
    """In-memory Redis fake for enrichment tests."""

    def __init__(self):
        self._store = {}

    async def get(self, key: str):
        val = self._store.get(key)
        return val.encode() if isinstance(val, str) else val

    async def set(self, key: str, value: str, ex: int = None):
        self._store[key] = value

    async def hget(self, name: str, key: str):
        return self._store.get(f"{name}:{key}")

    async def aclose(self):
        pass


def test_haversine_distance():
    """Verify distance between Delhi (28.5665, 77.1031) and Mumbai (19.0896, 72.8656) is ~1148 km."""
    dist = haversine_distance_km(28.5665, 77.1031, 19.0896, 72.8656)
    assert 1100 < dist < 1200


@pytest.mark.anyio
async def test_enrichment_fallback_airline():
    """Verify airline heuristic works when external API does not have route."""
    fake_redis = FakeRedis()
    service = EnrichmentService(redis_client=fake_redis)

    state = AircraftState(
        icao24="4009f6",
        callsign="BAW177",
        origin_country="United Kingdom",
        latitude=51.47,
        longitude=-0.45,
        velocity=220.0,
        true_track=270.0,
        time_position=1700000000,
        last_contact=1700000000,
    )

    with patch.object(service.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(404, json={"response": "not found"})
        result = await service.enrich_flight(icao24="4009f6", state=state)

    assert result.icao24 == "4009f6"
    assert result.callsign == "BAW177"
    assert result.route is not None
    assert result.route.airline is not None
    assert result.route.airline.name == "British Airways"
    assert result.route.airline.icao == "BAW"
    assert result.route.airline.iata == "BA"

    await service.aclose()


@pytest.mark.anyio
async def test_enrichment_with_route_and_progress():
    """Verify origin/destination enrichment and flight progress calculation."""
    fake_redis = FakeRedis()
    service = EnrichmentService(redis_client=fake_redis)

    state = AircraftState(
        icao24="3c6444",
        callsign="DLH400",
        origin_country="Germany",
        latitude=45.0,  # mid-flight over Atlantic
        longitude=-30.0,
        velocity=240.0,
        true_track=260.0,
        time_position=1700000000,
        last_contact=1700000000,
    )

    mock_route_response = {
        "response": {
            "flightroute": {
                "callsign": "DLH400",
                "airline": {"name": "Lufthansa", "icao": "DLH", "iata": "LH"},
                "origin": {
                    "iata_code": "FRA",
                    "icao_code": "EDDF",
                    "name": "Frankfurt Airport",
                    "municipality": "Frankfurt",
                    "latitude": 50.033,
                    "longitude": 8.570,
                },
                "destination": {
                    "iata_code": "JFK",
                    "icao_code": "KJFK",
                    "name": "John F Kennedy International Airport",
                    "municipality": "New York",
                    "latitude": 40.639,
                    "longitude": -73.778,
                },
            }
        }
    }

    mock_aircraft_response = {
        "response": {
            "aircraft": {
                "type": "Airbus A340-313",
                "icao_type": "A343",
                "manufacturer": "Airbus",
                "registration": "D-AIFD",
            }
        }
    }

    async def mock_fetch(url, *args, **kwargs):
        if "callsign" in url:
            return httpx.Response(200, json=mock_route_response)
        return httpx.Response(200, json=mock_aircraft_response)

    with patch.object(service.client, "get", side_effect=mock_fetch):
        result = await service.enrich_flight(icao24="3c6444", state=state)

    assert result.route is not None
    assert result.route.origin.iata_code == "FRA"
    assert result.route.destination.iata_code == "JFK"
    assert result.metadata is not None
    assert result.metadata.manufacturer == "Airbus"
    assert result.metadata.registration == "D-AIFD"
    assert result.route.total_distance_km > 6000
    assert result.route.progress_percent is not None
    assert 0 < result.route.progress_percent < 100

    await service.aclose()
