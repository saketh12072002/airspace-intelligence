"""Integration tests for the Airspace Intelligence Model Context Protocol (MCP) server."""

from __future__ import annotations

from datetime import UTC, datetime
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from app.domain.aircraft_service import AircraftService
from app.domain.airport_service import AirportService
from app.mcp.adapter import create_mcp_server
from app.repositories.aircraft_repo import InMemoryAircraftRepository
from app.repositories.airport_repo import AirportRepository
from app.repositories.history_repo import HistoryRepository
from app.schemas.aircraft_state import AircraftState
from app.tools.registry import create_default_registry


@pytest.fixture
def test_aircraft_fleet():
    """Curated realistic test aircraft across different regions and flight phases."""
    now_epoch = int(datetime.now(UTC).timestamp())
    return [
        # Inbound to DEL / VIDP (lat: 28.5665, lon: 77.1031)
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
        ),
        # Departing New York JFK (KJFK)
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
        ),
    ]


@pytest.fixture
async def mcp_test_server(test_aircraft_fleet):
    """Construct an isolated in-memory MCPServer instance for integration tests."""
    aircraft_repo = InMemoryAircraftRepository()
    await aircraft_repo.upsert_many(test_aircraft_fleet)

    airport_repo = AirportRepository()
    history_repo = HistoryRepository()
    await history_repo.record_positions(test_aircraft_fleet)

    aircraft_svc = AircraftService(aircraft_repo, history_repo)
    airport_svc = AirportService(airport_repo, aircraft_repo)

    registry = create_default_registry(aircraft_svc, airport_svc)
    return create_mcp_server(registry, server_name="test-mcp-copilot")


# ==============================================================================
# 1. Tool Catalog and Discovery Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_mcp_server_lists_all_8_tools(mcp_test_server):
    tools = await mcp_test_server.list_tools()
    assert len(tools) == 8

    expected_tool_names = {
        "search_aircraft",
        "get_aircraft",
        "get_aircraft_history",
        "search_aircraft_in_area",
        "get_aircraft_near_airport",
        "get_airport",
        "get_airport_traffic",
        "get_flight_statistics",
    }
    actual_names = {t.name for t in tools}
    assert actual_names == expected_tool_names

    # Verify each tool has an informative description and input schema
    for t in tools:
        assert len(t.description) > 20
        assert t.input_schema is not None
        assert t.input_schema.get("type") == "object"
        assert "properties" in t.input_schema


# ==============================================================================
# 2. Tool Execution via MCP Protocol
# ==============================================================================

@pytest.mark.asyncio
async def test_mcp_search_aircraft(mcp_test_server):
    res = await mcp_test_server.call_tool(
        "search_aircraft",
        {"country": "India", "limit": 10},
    )
    assert res.is_error is False
    assert res.structured_content is not None
    data = res.structured_content
    assert data["total_matched"] == 2
    assert len(data["aircraft"]) == 2
    assert data["aircraft"][0]["origin_country"] == "India"


@pytest.mark.asyncio
async def test_mcp_get_aircraft(mcp_test_server):
    res = await mcp_test_server.call_tool(
        "get_aircraft",
        {"icao24": "80167f"},
    )
    assert res.is_error is False
    data = res.structured_content
    assert data["found"] is True
    assert data["icao24"] == "80167f"
    assert data["aircraft"]["callsign"] == "AIC101"
    assert data["aircraft"]["altitude_ft"] is not None


@pytest.mark.asyncio
async def test_mcp_get_aircraft_history(mcp_test_server):
    res = await mcp_test_server.call_tool(
        "get_aircraft_history",
        {"icao24": "80167f", "limit": 10},
    )
    assert res.is_error is False
    data = res.structured_content
    assert data["icao24"] == "80167f"
    assert data["record_count"] >= 1
    assert data["history"][0]["latitude"] == 28.54


@pytest.mark.asyncio
async def test_mcp_search_aircraft_in_area(mcp_test_server):
    res = await mcp_test_server.call_tool(
        "search_aircraft_in_area",
        {
            "latitude": 28.5665,
            "longitude": 77.1031,
            "radius_km": 100.0,
        },
    )
    assert res.is_error is False
    data = res.structured_content
    assert data["total_found"] == 2
    assert data["radius_km"] == 100.0
    # Closest first
    assert data["aircraft"][0]["distance_km"] <= data["aircraft"][1]["distance_km"]


@pytest.mark.asyncio
async def test_mcp_get_aircraft_near_airport(mcp_test_server):
    res = await mcp_test_server.call_tool(
        "get_aircraft_near_airport",
        {"airport_code": "DEL", "radius_km": 60.0},
    )
    assert res.is_error is False
    data = res.structured_content
    assert data["found"] is True
    assert data["airport"]["iata_code"] == "DEL"
    assert data["airport"]["icao_code"] == "VIDP"
    assert data["total_found"] == 2


@pytest.mark.asyncio
async def test_mcp_get_airport(mcp_test_server):
    res = await mcp_test_server.call_tool(
        "get_airport",
        {"airport_code": "KJFK"},
    )
    assert res.is_error is False
    data = res.structured_content
    assert data["found"] is True
    assert data["airport"]["icao_code"] == "KJFK"
    assert data["airport"]["iata_code"] == "JFK"
    assert data["airport"]["municipality"] == "New York"
    assert data["airport"]["timezone"] == "America/New_York"


@pytest.mark.asyncio
async def test_mcp_get_airport_traffic(mcp_test_server):
    res = await mcp_test_server.call_tool(
        "get_airport_traffic",
        {"airport_code": "VIDP", "radius_km": 80.0},
    )
    assert res.is_error is False
    data = res.structured_content
    assert data["found"] is True
    assert data["total_aircraft"] == 2
    assert data["ground_count"] == 1
    assert data["inbound_count"] == 1
    assert "Indira Gandhi International Airport" in data["summary"]


@pytest.mark.asyncio
async def test_mcp_get_flight_statistics(mcp_test_server):
    res = await mcp_test_server.call_tool("get_flight_statistics", {})
    assert res.is_error is False
    data = res.structured_content
    assert data["total_aircraft"] == 4
    assert data["airborne_count"] == 3
    assert data["on_ground_count"] == 1
    assert data["traffic_density"] in {"LOW", "MODERATE", "HIGH", "VERY_HIGH"}
    assert "min_speed_kmh" in data["speed_stats"]
    assert "cruise_altitude_count" in data["altitude_stats"]


# ==============================================================================
# 3. Input Sanitization and Schema Validation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_mcp_rejects_out_of_range_latitude(mcp_test_server):
    with pytest.raises(ToolError, match="less than or equal to 90"):
        await mcp_test_server.call_tool(
            "search_aircraft_in_area",
            {
                "latitude": 95.0,  # Invalid: > 90.0
                "longitude": 77.1,
                "radius_km": 50.0,
            },
        )


@pytest.mark.asyncio
async def test_mcp_rejects_negative_radius(mcp_test_server):
    with pytest.raises(ToolError, match="greater than 0"):
        await mcp_test_server.call_tool(
            "search_aircraft_in_area",
            {
                "latitude": 28.5,
                "longitude": 77.1,
                "radius_km": -15.0,  # Invalid: <= 0
            },
        )


@pytest.mark.asyncio
async def test_mcp_rejects_excessive_limit(mcp_test_server):
    with pytest.raises(ToolError, match="less than or equal to 500"):
        await mcp_test_server.call_tool(
            "search_aircraft",
            {"limit": 2000},  # Invalid: max 500
        )


# ==============================================================================
# 4. Least Privilege and Security Boundary Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_mcp_least_privilege_audit(mcp_test_server):
    """Verify that only authorized aviation tools are present and no sensitive tools exist."""
    tools = await mcp_test_server.list_tools()
    tool_names = [t.name.lower() for t in tools]

    forbidden_keywords = [
        "sql",
        "db",
        "database",
        "query",
        "exec",
        "eval",
        "shell",
        "bash",
        "system",
        "http",
        "fetch",
        "request",
        "delete",
        "drop",
        "insert",
        "update",
    ]

    for name in tool_names:
        for keyword in forbidden_keywords:
            assert keyword not in name, f"Forbidden keyword '{keyword}' found in tool '{name}'"


@pytest.mark.asyncio
async def test_mcp_rejects_unregistered_tool_call(mcp_test_server):
    with pytest.raises(ToolError, match="Unknown tool"):
        await mcp_test_server.call_tool("execute_sql_query", {"query": "SELECT * FROM aircraft"})
