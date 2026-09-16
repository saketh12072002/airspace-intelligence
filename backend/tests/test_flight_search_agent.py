"""Comprehensive tests for the Airspace Intelligence Flight Search Agent."""

from __future__ import annotations

from datetime import UTC, datetime
import pytest

from app.agent.flight_search_agent import FlightSearchAgent
from app.agent.mcp_client import FlightSearchMCPClient
from app.domain.aircraft_service import AircraftService
from app.domain.airport_service import AirportService
from app.mcp.adapter import create_mcp_server
from app.repositories.aircraft_repo import InMemoryAircraftRepository
from app.repositories.airport_repo import AirportRepository
from app.repositories.history_repo import HistoryRepository
from app.schemas.aircraft_state import AircraftState
from app.tools.registry import create_default_registry


@pytest.fixture
def agent_test_fleet():
    """Realistic fleet for testing aircraft lookup, geographic search, and follow-ups."""
    now_epoch = int(datetime.now(UTC).timestamp())
    return [
        # Air India flight AI203 (callsign AIC203) airborne near Delhi
        AircraftState(
            icao24="80167f",
            callsign="AIC203",
            origin_country="India",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=77.12,
            latitude=28.54,
            baro_altitude=3200.0,
            on_ground=False,
            velocity=180.0,
            true_track=310.0,
            vertical_rate=-4.0,
            geo_altitude=3250.0,
            squawk="4211",
        ),
        # Air India flight AIC101 on ground at Mumbai (BOM)
        AircraftState(
            icao24="800201",
            callsign="AIC101",
            origin_country="India",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=72.88,
            latitude=19.10,
            baro_altitude=39.0,
            on_ground=True,
            velocity=15.0,
            true_track=90.0,
            vertical_rate=0.0,
            geo_altitude=39.0,
            squawk="1200",
        ),
        # SpiceJet airborne within 100km of Mumbai (lat 19.0896, lon 72.8656)
        AircraftState(
            icao24="800abc",
            callsign="SEJ512",
            origin_country="India",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=72.85,
            latitude=19.15,
            baro_altitude=1500.0,
            on_ground=False,
            velocity=110.0,
            true_track=210.0,
            vertical_rate=5.0,
            geo_altitude=1520.0,
            squawk="3144",
        ),
        # Lufthansa en-route over Germany
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
            vertical_rate=0.0,
            geo_altitude=10600.0,
            squawk="1000",
        ),
    ]


@pytest.fixture
async def flight_search_agent(agent_test_fleet):
    """Set up the FlightSearchAgent wired to an in-memory MCP server."""
    aircraft_repo = InMemoryAircraftRepository()
    await aircraft_repo.upsert_many(agent_test_fleet)

    airport_repo = AirportRepository()
    history_repo = HistoryRepository()
    await history_repo.record_positions(agent_test_fleet)

    aircraft_svc = AircraftService(aircraft_repo, history_repo)
    airport_svc = AirportService(airport_repo, aircraft_repo)

    registry = create_default_registry(aircraft_svc, airport_svc)
    mcp_server = create_mcp_server(registry, server_name="agent-test-mcp")
    mcp_client = FlightSearchMCPClient(mcp_server=mcp_server)

    return FlightSearchAgent(mcp_client=mcp_client)


# ==============================================================================
# 1. Direct Aircraft Lookup Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_direct_aircraft_lookup_by_callsign(flight_search_agent):
    response = await flight_search_agent.ask("Where is AI203?")
    assert response.tool_called == "search_aircraft"
    assert "AIC203" in response.text
    assert "80167f" in response.text
    assert "Observed Live Data" in response.text
    assert "Airborne" in response.text
    assert response.referenced_aircraft is not None
    assert response.referenced_aircraft.icao24 == "80167f"


@pytest.mark.asyncio
async def test_direct_aircraft_lookup_by_icao(flight_search_agent):
    response = await flight_search_agent.ask("Where is aircraft 80167f?")
    assert response.tool_called == "get_aircraft"
    assert "80167f" in response.text
    assert "AIC203" in response.text
    assert response.referenced_aircraft.icao24 == "80167f"


# ==============================================================================
# 2. Geographic Area Search Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_geographic_search_near_delhi(flight_search_agent):
    response = await flight_search_agent.ask("Which aircraft are near Delhi?")
    assert response.tool_called == "search_aircraft_in_area"
    assert response.referenced_aircraft is not None
    assert "AIC203" in response.text
    assert "proximity" in response.text.lower() or "away" in response.text.lower()


@pytest.mark.asyncio
async def test_geographic_search_within_radius_mumbai(flight_search_agent):
    response = await flight_search_agent.ask("What aircraft are within 100 km of Mumbai?")
    assert response.tool_called == "search_aircraft_in_area"
    assert response.tool_arguments["radius_km"] == 100.0
    # Both AIC101 (at BOM) and SEJ512 (near BOM) should be discovered
    assert "AIC101" in response.text
    assert "SEJ512" in response.text


# ==============================================================================
# 3. Airline Filtering Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_airline_filtering_air_india(flight_search_agent):
    response = await flight_search_agent.ask("Which Air India aircraft are currently airborne?")
    assert response.tool_called == "search_aircraft"
    assert response.tool_arguments["callsign"] == "AIC"
    # Should list the Air India flights
    assert "AIC203" in response.text or "AIC101" in response.text


# ==============================================================================
# 4. Multi-Turn Follow-Up Questions (Context & Pronoun Resolution)
# ==============================================================================

@pytest.mark.asyncio
async def test_multi_turn_follow_up_pronouns(flight_search_agent):
    session_id = "test-session-multi-turn"

    # Turn 1: Initial query establishing context
    turn1 = await flight_search_agent.ask("Where is AI203?", conversation_id=session_id)
    assert "AIC203" in turn1.text
    assert turn1.referenced_aircraft is not None
    assert turn1.referenced_aircraft.icao24 == "80167f"

    # Turn 2: Follow-up asking for altitude using pronoun "its"
    turn2 = await flight_search_agent.ask("What's its altitude?", conversation_id=session_id)
    assert turn2.tool_called == "get_aircraft"
    assert turn2.tool_arguments["icao24"] == "80167f"
    assert "Altitude" in turn2.text
    assert "ft" in turn2.text
    assert "3,200" in turn2.text or "3200" in turn2.text

    # Turn 3: Follow-up asking for speed using pronoun "it"
    turn3 = await flight_search_agent.ask("How fast is it going?", conversation_id=session_id)
    assert turn3.tool_called == "get_aircraft"
    assert turn3.tool_arguments["icao24"] == "80167f"
    assert "Speed" in turn3.text or "Ground speed" in turn3.text
    assert "knots" in turn3.text or "km/h" in turn3.text


# ==============================================================================
# 5. Missing Aircraft & Zero Hallucination Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_missing_aircraft_not_found(flight_search_agent):
    response = await flight_search_agent.ask("Where is AI9999?")
    # Must explicitly declare flight is unavailable and NOT hallucinate a location
    assert "not currently detected" in response.text or "unavailable" in response.text or "not tracked" in response.text
    assert "AIC9999" in response.text or "AI9999" in response.text
    assert response.referenced_aircraft is None


@pytest.mark.asyncio
async def test_missing_icao_hex(flight_search_agent):
    response = await flight_search_agent.ask("Where is aircraft ffffff?")
    assert "not currently tracked" in response.text or "out of coverage" in response.text


# ==============================================================================
# 6. Invalid Aircraft Identifiers
# ==============================================================================

@pytest.mark.asyncio
async def test_invalid_aircraft_identifier_graceful_handling(flight_search_agent):
    # Short hex that is invalid ICAO
    response = await flight_search_agent.ask("What is the altitude of aircraft 12345?")
    # Should handle cleanly without crashing and indicate issue or unavailablity
    assert response.text is not None
    assert len(response.text) > 10


# ==============================================================================
# 7. Country & Airspace Queries
# ==============================================================================

@pytest.mark.asyncio
async def test_show_aircraft_flying_over_india(flight_search_agent):
    response = await flight_search_agent.ask("Show aircraft currently flying over India.")
    assert response.tool_called == "search_aircraft"
    assert response.tool_arguments.get("country") == "India"
    assert "India" in response.text


# ==============================================================================
# 8. Airport Vicinity & Traffic
# ==============================================================================

@pytest.mark.asyncio
async def test_aircraft_near_delhi_airport(flight_search_agent):
    response = await flight_search_agent.ask("Which aircraft are near Delhi airport?")
    assert response.tool_called in {"get_aircraft_near_airport", "search_aircraft_in_area"}
    assert "AIC203" in response.text or "Indira Gandhi" in response.text
