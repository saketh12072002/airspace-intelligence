"""Tests for the OpenSky client with mocked HTTP responses."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.schemas.aircraft_state import AircraftState
from app.services.opensky.client import (
    OpenSkyAPIError,
    OpenSkyAuthError,
    OpenSkyClient,
    OpenSkyRateLimitError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_settings(**overrides: Any) -> Settings:
    """Create a Settings instance with test defaults."""
    defaults = {
        "database_url": "postgresql://test:test@localhost/test",
        "redis_url": "redis://localhost:6379/0",
        "opensky_base_url": "https://opensky-network.org/api",
        "opensky_username": "",
        "opensky_password": "",
        "cors_origins": ["http://localhost:3000"],
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _sample_state_vector(
    icao24: str = "abc123",
    callsign: str = "TEST1234",
    on_ground: bool = False,
) -> list[Any]:
    """Build a single OpenSky state vector (18-element list)."""
    return [
        icao24,           # 0  icao24
        f" {callsign} ",  # 1  callsign (padded — tests stripping)
        "United States",  # 2  origin_country
        1609459200,       # 3  time_position
        1609459201,       # 4  last_contact
        -122.375,         # 5  longitude
        37.6188,          # 6  latitude
        10972.8,          # 7  baro_altitude
        on_ground,        # 8  on_ground
        257.15,           # 9  velocity
        135.0,            # 10 true_track
        0.0,              # 11 vertical_rate
        None,             # 12 sensors
        11277.6,          # 13 geo_altitude
        "1234",           # 14 squawk
        False,            # 15 spi
        0,                # 16 position_source
        1,                # 17 category
    ]


def _opensky_response(num_aircraft: int = 3) -> dict[str, Any]:
    """Build a full OpenSky /states/all response with *num_aircraft* vectors."""
    states = [
        _sample_state_vector(icao24=f"ac{i:04x}", callsign=f"TST{i:04d}")
        for i in range(num_aircraft)
    ]
    return {"time": 1609459200, "states": states}


# ---------------------------------------------------------------------------
# Tests — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_aircraft_states_success() -> None:
    """Successful /states/all call should return normalised AircraftState objects."""
    payload = _opensky_response(5)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    )
    settings = _make_settings()
    client = OpenSkyClient(settings)
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.opensky_base_url)

    states = await client.fetch_aircraft_states()

    assert len(states) == 5
    assert all(isinstance(s, AircraftState) for s in states)
    assert states[0].icao24 == "ac0000"
    assert states[0].callsign == "TST0000"
    assert states[0].origin_country == "United States"
    assert states[0].longitude == -122.375
    assert states[0].latitude == 37.6188
    assert states[0].baro_altitude == 10972.8
    assert states[0].velocity == 257.15
    assert states[0].category == 1


@pytest.mark.asyncio
async def test_fetch_with_bounding_box() -> None:
    """Bounding-box parameters should be forwarded as query params."""
    captured_params: dict[str, str] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json=_opensky_response(1))

    settings = _make_settings()
    client = OpenSkyClient(settings)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(_handler), base_url=settings.opensky_base_url)

    await client.fetch_aircraft_states(bounds=(45.0, 5.0, 48.0, 10.0))

    assert captured_params["lamin"] == "45.0"
    assert captured_params["lomin"] == "5.0"
    assert captured_params["lamax"] == "48.0"
    assert captured_params["lomax"] == "10.0"


@pytest.mark.asyncio
async def test_fetch_with_authentication() -> None:
    """When credentials are configured, requests should carry Basic auth."""
    captured_auth: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        auth_header = request.headers.get("authorization", "")
        captured_auth.append(auth_header)
        return httpx.Response(200, json=_opensky_response(1))

    settings = _make_settings(opensky_username="user", opensky_password="pass")
    client = OpenSkyClient(settings)
    # Re-create client with auth — connect() handles this, but we mock transport
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(_handler),
        base_url=settings.opensky_base_url,
        auth=(settings.opensky_username, settings.opensky_password),
    )

    await client.fetch_aircraft_states()

    assert len(captured_auth) == 1
    assert captured_auth[0].startswith("Basic ")


@pytest.mark.asyncio
async def test_fetch_empty_states() -> None:
    """API returning states=null should produce an empty list, not crash."""
    payload = {"time": 1609459200, "states": None}
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    )
    settings = _make_settings()
    client = OpenSkyClient(settings)
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.opensky_base_url)

    states = await client.fetch_aircraft_states()
    assert states == []


@pytest.mark.asyncio
async def test_fetch_states_generic_returns_dicts() -> None:
    """The base-class ``fetch_states`` method should return raw dicts."""
    payload = _opensky_response(2)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    )
    settings = _make_settings()
    client = OpenSkyClient(settings)
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.opensky_base_url)

    result = await client.fetch_states()

    assert len(result) == 2
    assert all(isinstance(r, dict) for r in result)
    assert result[0]["icao24"] == "ac0000"


# ---------------------------------------------------------------------------
# Tests — error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_401_raises_auth_error() -> None:
    """HTTP 401 should raise OpenSkyAuthError."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, text="Unauthorized")
    )
    settings = _make_settings()
    client = OpenSkyClient(settings)
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.opensky_base_url)

    with pytest.raises(OpenSkyAuthError):
        await client.fetch_aircraft_states()


@pytest.mark.asyncio
async def test_429_raises_rate_limit_error() -> None:
    """HTTP 429 should raise OpenSkyRateLimitError with retry_after."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(429, text="Too Many Requests", headers={"Retry-After": "30"})
    )
    settings = _make_settings()
    client = OpenSkyClient(settings)
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.opensky_base_url)

    with pytest.raises(OpenSkyRateLimitError) as exc_info:
        await client.fetch_aircraft_states()

    assert exc_info.value.retry_after == 30


@pytest.mark.asyncio
async def test_500_raises_api_error() -> None:
    """Generic server errors should raise OpenSkyAPIError."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(500, text="Internal Server Error")
    )
    settings = _make_settings()
    client = OpenSkyClient(settings)
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.opensky_base_url)

    with pytest.raises(OpenSkyAPIError) as exc_info:
        await client.fetch_aircraft_states()

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_timeout_propagates() -> None:
    """httpx.TimeoutException should propagate to the caller."""
    def _timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timed out")

    settings = _make_settings()
    client = OpenSkyClient(settings)
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(_timeout_handler),
        base_url=settings.opensky_base_url,
    )

    with pytest.raises(httpx.TimeoutException):
        await client.fetch_aircraft_states()


@pytest.mark.asyncio
async def test_malformed_json_raises_api_error() -> None:
    """A response with invalid JSON should raise OpenSkyAPIError."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"NOT JSON", headers={"Content-Type": "text/plain"})
    )
    settings = _make_settings()
    client = OpenSkyClient(settings)
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.opensky_base_url)

    with pytest.raises(OpenSkyAPIError):
        await client.fetch_aircraft_states()


@pytest.mark.asyncio
async def test_malformed_state_vector_skipped() -> None:
    """An individual malformed vector should be skipped, not crash the batch."""
    payload = {
        "time": 1609459200,
        "states": [
            _sample_state_vector(icao24="good1"),
            ["too", "short"],  # malformed — only 2 elements
            _sample_state_vector(icao24="good2"),
        ],
    }
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    )
    settings = _make_settings()
    client = OpenSkyClient(settings)
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.opensky_base_url)

    states = await client.fetch_aircraft_states()

    assert len(states) == 2
    assert states[0].icao24 == "good1"
    assert states[1].icao24 == "good2"


@pytest.mark.asyncio
async def test_17_element_vector_no_category() -> None:
    """Older responses without the category field (17 elements) should parse fine."""
    vec = _sample_state_vector()[:17]  # strip category
    payload = {"time": 1609459200, "states": [vec]}
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    )
    settings = _make_settings()
    client = OpenSkyClient(settings)
    client._client = httpx.AsyncClient(transport=transport, base_url=settings.opensky_base_url)

    states = await client.fetch_aircraft_states()

    assert len(states) == 1
    assert states[0].category == 0  # default


@pytest.mark.asyncio
async def test_not_connected_raises() -> None:
    """Calling fetch without connect() should raise RuntimeError."""
    settings = _make_settings()
    client = OpenSkyClient(settings)

    with pytest.raises(RuntimeError, match="not connected"):
        await client.fetch_aircraft_states()
