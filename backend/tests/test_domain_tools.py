"""Comprehensive unit tests for the 8 aviation domain tools, schemas, and registry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest
from pydantic import ValidationError

from app.domain.aircraft_service import AircraftService
from app.domain.airport_service import AirportService
from app.repositories.aircraft_repo import InMemoryAircraftRepository
from app.repositories.airport_repo import AirportRepository
from app.repositories.history_repo import HistoryRepository
from app.schemas.aircraft_state import AircraftState
from app.tools import (
    GetAircraftHistoryInput,
    GetAircraftInput,
    GetAircraftNearAirportInput,
    GetAirportInput,
    GetAirportTrafficInput,
    GetFlightStatisticsInput,
    SearchAircraftInAreaInput,
    SearchAircraftInput,
    create_default_registry,
)


@pytest.fixture
def sample_aircraft():
    """Collection of realistic aircraft states across flight phases and regions."""
    now_epoch = int(datetime.now(UTC).timestamp())
    return [
        # Inbound approach to DEL / VIDP (lat: 28.5665, lon: 77.1031)
        AircraftState(
            icao24="80167f",
            callsign="AIC101",
            origin_country="India",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=77.12,
            latitude=28.54,
            baro_altitude=1200.0,
            on_ground=False,
            velocity=110.0,
            true_track=310.0,
            vertical_rate=-4.5,
            geo_altitude=1220.0,
            squawk="4211",
            spi=False,
            position_source=0,
            category=0,
        ),
        # On ground at DEL / VIDP
        AircraftState(
            icao24="800abc",
            callsign="SEJ202",
            origin_country="India",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=77.10,
            latitude=28.56,
            baro_altitude=230.0,
            on_ground=True,
            velocity=12.0,
            true_track=90.0,
            vertical_rate=0.0,
            geo_altitude=230.0,
            squawk="1200",
            spi=False,
            position_source=0,
            category=0,
        ),
        # En-route over Germany near Frankfurt (EDDF)
        AircraftState(
            icao24="3c6444",
            callsign="DLH400",
            origin_country="Germany",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=8.57,
            latitude=50.03,
            baro_altitude=10500.0,
            on_ground=False,
            velocity=240.0,
            true_track=95.0,
            vertical_rate=0.2,
            geo_altitude=10600.0,
            squawk="1000",
            spi=False,
            position_source=0,
            category=0,
        ),
        # Outbound climb from JFK / KJFK (lat: 40.6398, lon: -73.7789)
        AircraftState(
            icao24="a12345",
            callsign="AAL100",
            origin_country="United States",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=-73.65,
            latitude=40.70,
            baro_altitude=2200.0,
            on_ground=False,
            velocity=145.0,
            true_track=70.0,
            vertical_rate=9.0,
            geo_altitude=2250.0,
            squawk="3401",
            spi=False,
            position_source=0,
            category=0,
        ),
    ]


@pytest.fixture
async def tool_context(sample_aircraft):
    """Assemble domain services and registry wired to in-memory repositories."""
    aircraft_repo = InMemoryAircraftRepository()
    await aircraft_repo.upsert_many(sample_aircraft)

    airport_repo = AirportRepository()
    history_repo = HistoryRepository()
    await history_repo.record_positions(sample_aircraft)

    aircraft_service = AircraftService(aircraft_repo, history_repo)
    airport_service = AirportService(airport_repo, aircraft_repo)

    registry = create_default_registry(aircraft_service, airport_service)
    return {
        "registry": registry,
        "aircraft_service": aircraft_service,
        "airport_service": airport_service,
        "history_repo": history_repo,
    }


# ==============================================================================
# Tool 1: search_aircraft Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_search_aircraft_by_callsign(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("search_aircraft", {"callsign": "AIC101"})
    assert res.total_matched == 1
    assert res.aircraft[0].icao24 == "80167f"
    assert res.aircraft[0].callsign == "AIC101"
    assert res.aircraft[0].origin_country == "India"
    assert res.aircraft[0].altitude_ft is not None


@pytest.mark.asyncio
async def test_search_aircraft_by_country(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("search_aircraft", {"country": "India"})
    assert res.total_matched == 2
    icaos = {a.icao24 for a in res.aircraft}
    assert icaos == {"80167f", "800abc"}


@pytest.mark.asyncio
async def test_search_aircraft_by_bounds(tool_context):
    registry = tool_context["registry"]
    # Bounding box around New Delhi
    res = await registry.execute(
        "search_aircraft",
        {
            "bounds": {
                "lamin": 28.0,
                "lomin": 76.5,
                "lamax": 29.0,
                "lomax": 77.5,
            }
        },
    )
    assert res.total_matched == 2


@pytest.mark.asyncio
async def test_search_aircraft_input_validation():
    # Bad ICAO length/chars
    with pytest.raises(ValidationError):
        SearchAircraftInput(icao24="INVALID_HEX")

    # Invalid latitude order
    with pytest.raises(ValidationError):
        SearchAircraftInput(bounds={"lamin": 30.0, "lomin": 10.0, "lamax": 20.0, "lomax": 15.0})


# ==============================================================================
# Tool 2: get_aircraft Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_aircraft_found(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_aircraft", {"icao24": "80167F"})  # Test case insensitivity
    assert res.found is True
    assert res.aircraft is not None
    assert res.aircraft.icao24 == "80167f"
    assert res.aircraft.callsign == "AIC101"
    assert res.message is None


@pytest.mark.asyncio
async def test_get_aircraft_not_found(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_aircraft", {"icao24": "ffffff"})
    assert res.found is False
    assert res.aircraft is None
    assert "not currently tracked" in res.message


@pytest.mark.asyncio
async def test_get_aircraft_invalid_hex():
    with pytest.raises(ValidationError):
        GetAircraftInput(icao24="12345")  # Too short


# ==============================================================================
# Tool 3: get_aircraft_history Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_aircraft_history(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_aircraft_history", {"icao24": "80167f"})
    assert res.record_count >= 1
    assert res.history[0].icao24 == "80167f"
    assert res.history[0].callsign == "AIC101"
    assert res.history[0].latitude == 28.54


@pytest.mark.asyncio
async def test_get_aircraft_history_empty(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_aircraft_history", {"icao24": "112233"})
    assert res.record_count == 0
    assert res.history == []


# ==============================================================================
# Tool 4: search_aircraft_in_area Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_search_aircraft_in_area(tool_context):
    registry = tool_context["registry"]
    # Search within 100km of New Delhi coordinates
    res = await registry.execute(
        "search_aircraft_in_area",
        {
            "latitude": 28.5665,
            "longitude": 77.1031,
            "radius_km": 100.0,
        },
    )
    assert res.total_found == 2
    # Verify sorting: closest first
    assert res.aircraft[0].distance_km <= res.aircraft[1].distance_km


@pytest.mark.asyncio
async def test_search_aircraft_in_area_altitude_filter(tool_context):
    registry = tool_context["registry"]
    # Only airborne aircraft above 1000m
    res = await registry.execute(
        "search_aircraft_in_area",
        {
            "latitude": 28.5665,
            "longitude": 77.1031,
            "radius_km": 100.0,
            "min_altitude_m": 1000.0,
        },
    )
    assert res.total_found == 1
    assert res.aircraft[0].aircraft.icao24 == "80167f"


@pytest.mark.asyncio
async def test_search_aircraft_in_area_validation():
    with pytest.raises(ValidationError):
        SearchAircraftInAreaInput(latitude=100.0, longitude=0.0, radius_km=50.0)  # Lat out of range
    with pytest.raises(ValidationError):
        SearchAircraftInAreaInput(latitude=0.0, longitude=0.0, radius_km=-10.0)  # Negative radius


# ==============================================================================
# Tool 5: get_aircraft_near_airport Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_aircraft_near_airport_icao(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_aircraft_near_airport", {"airport_code": "VIDP", "radius_km": 60.0})
    assert res.found is True
    assert res.airport.icao_code == "VIDP"
    assert res.airport.name == "Indira Gandhi International Airport"
    assert res.total_found == 2
    assert res.nearby_aircraft[0].distance_km <= res.nearby_aircraft[1].distance_km


@pytest.mark.asyncio
async def test_get_aircraft_near_airport_iata(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_aircraft_near_airport", {"airport_code": "DEL", "radius_km": 60.0})
    assert res.found is True
    assert res.airport.iata_code == "DEL"
    assert res.total_found == 2


@pytest.mark.asyncio
async def test_get_aircraft_near_airport_not_found(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_aircraft_near_airport", {"airport_code": "ZZZZ"})
    assert res.found is False
    assert res.airport is None
    assert res.total_found == 0


# ==============================================================================
# Tool 6: get_airport Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_airport_by_icao(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_airport", {"airport_code": "KJFK"})
    assert res.found is True
    assert res.airport.icao_code == "KJFK"
    assert res.airport.iata_code == "JFK"
    assert res.airport.country_iso == "US"
    assert res.airport.timezone == "America/New_York"


@pytest.mark.asyncio
async def test_get_airport_by_iata(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_airport", {"airport_code": "LHR"})
    assert res.found is True
    assert res.airport.icao_code == "EGLL"
    assert res.airport.municipality == "London"


@pytest.mark.asyncio
async def test_get_airport_unknown(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_airport", {"airport_code": "XYZ9"})
    assert res.found is False
    assert res.airport is None
    assert "not found" in res.message


# ==============================================================================
# Tool 7: get_airport_traffic Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_airport_traffic_breakdown(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_airport_traffic", {"airport_code": "VIDP", "radius_km": 80.0})
    assert res.found is True
    assert res.total_aircraft == 2
    assert res.ground_count == 1
    assert res.inbound_count == 1
    assert "Indira Gandhi International Airport" in res.summary
    assert len(res.traffic) == 2


@pytest.mark.asyncio
async def test_get_airport_traffic_departure(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_airport_traffic", {"airport_code": "JFK", "radius_km": 50.0})
    assert res.found is True
    assert res.total_aircraft == 1
    assert res.outbound_count == 1
    assert res.traffic[0].flight_phase == "DEPARTURE"


# ==============================================================================
# Tool 8: get_flight_statistics Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_flight_statistics_global(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_flight_statistics", {})
    assert res.total_aircraft == 4
    assert res.airborne_count == 3
    assert res.on_ground_count == 1
    assert res.altitude_stats.max_altitude_m == 10500.0
    assert res.speed_stats.max_speed_kmh is not None
    assert res.traffic_density in {"LOW", "MODERATE", "HIGH", "VERY_HIGH"}
    assert len(res.top_origin_countries) >= 2


@pytest.mark.asyncio
async def test_get_flight_statistics_country_filter(tool_context):
    registry = tool_context["registry"]
    res = await registry.execute("get_flight_statistics", {"country": "Germany"})
    assert res.total_aircraft == 1
    assert res.airborne_count == 1
    assert res.altitude_stats.min_altitude_m == 10500.0


# ==============================================================================
# Registry and MCP Manifest Tests
# ==============================================================================

def test_registry_manifest(tool_context):
    registry = tool_context["registry"]
    manifest = registry.get_mcp_manifest()
    assert len(manifest) == 8

    names = [m["name"] for m in manifest]
    expected_names = [
        "search_aircraft",
        "get_aircraft",
        "get_aircraft_history",
        "search_aircraft_in_area",
        "get_flight_statistics",
        "get_airport",
        "get_aircraft_near_airport",
        "get_airport_traffic",
    ]
    for expected in expected_names:
        assert expected in names

    # Verify MCP JSON Schema structure
    for tool_def in manifest:
        assert "name" in tool_def
        assert "description" in tool_def
        assert "inputSchema" in tool_def
        assert tool_def["inputSchema"]["type"] == "object"
        assert "properties" in tool_def["inputSchema"]


@pytest.mark.asyncio
async def test_registry_dispatch_unknown_tool(tool_context):
    registry = tool_context["registry"]
    with pytest.raises(KeyError, match="Unknown tool 'fly_to_moon'"):
        await registry.execute("fly_to_moon", {})
