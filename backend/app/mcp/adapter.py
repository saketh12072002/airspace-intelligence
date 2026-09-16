"""Model Context Protocol (MCP) adapter exposing aviation domain tools to AI agents."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from app.core.logging import get_logger
from app.tools.registry import ToolRegistry
from app.tools.schemas import (
    GeoBoundingBox,
    GetAircraftHistoryOutput,
    GetAircraftNearAirportOutput,
    GetAircraftOutput,
    GetAirportOutput,
    GetAirportTrafficOutput,
    GetFlightStatisticsOutput,
    SearchAircraftInAreaOutput,
    SearchAircraftOutput,
)

logger = get_logger(__name__)


def create_mcp_server(
    registry: ToolRegistry,
    server_name: str = "airspace-intelligence-copilot",
    server_version: str = "0.2.0",
) -> MCPServer:
    """Create and configure an official Model Context Protocol (MCP) server.

    This server acts strictly as an adapter over the existing domain ToolRegistry.
    Under least privilege security principles, ONLY the 8 authorized aviation domain
    capabilities are exposed. No database queries, SQL execution, arbitrary HTTP
    requests, or filesystem operations can be performed through this server.

    Args:
        registry: The instantiated ToolRegistry containing the 8 aviation domain tools.
        server_name: Identifier for the MCP server.
        server_version: Semantic version of the MCP tool service.

    Returns:
        Configured MCPServer ready for stdio or SSE transport.
    """
    server = MCPServer(
        name=server_name,
        version=server_version,
        instructions=(
            "Airspace Intelligence Copilot MCP Server.\n"
            "Provides real-time commercial and general aviation flight tracking, "
            "airport infrastructure metadata, terminal airspace traffic analysis, "
            "and airspace telemetry statistics.\n"
            "Operates deterministically using verified ADS-B transponder data."
        ),
    )

    # --------------------------------------------------------------------------
    # Tool 1: search_aircraft
    # --------------------------------------------------------------------------
    @server.tool(
        name="search_aircraft",
        description=(
            "Search for currently active aircraft using callsign, 24-bit ICAO transponder "
            "hex code, country of registration, or geographic bounding box. Returns a list "
            "of normalized aircraft states with altitude (feet/metres), ground speed (knots/km/h), "
            "and heading. Use this when the user asks to find specific flights or see aircraft "
            "from a particular country or within a geographic area."
        ),
    )
    async def search_aircraft(
        callsign: Optional[str] = Field(
            default=None,
            description="Assigned flight callsign (e.g. 'AIC101', 'DLH400', 'BAW177').",
        ),
        icao24: Optional[str] = Field(
            default=None,
            description="24-bit ICAO transponder address in hex (e.g. '80167f', '3c6444').",
        ),
        country: Optional[str] = Field(
            default=None,
            description="Country of aircraft registration (e.g. 'India', 'United States').",
        ),
        bounds: Optional[GeoBoundingBox] = Field(
            default=None,
            description="Optional geographic bounding box filter with lamin, lomin, lamax, lomax.",
        ),
        limit: int = Field(
            default=50,
            ge=1,
            le=500,
            description="Maximum number of matching aircraft to return (1-500, default 50).",
        ),
    ) -> SearchAircraftOutput:
        params: dict = {"limit": limit}
        if callsign is not None:
            params["callsign"] = callsign
        if icao24 is not None:
            params["icao24"] = icao24
        if country is not None:
            params["country"] = country
        if bounds is not None:
            params["bounds"] = bounds.model_dump()

        result = await registry.execute("search_aircraft", params)
        return result  # type: ignore[return-value]

    # --------------------------------------------------------------------------
    # Tool 2: get_aircraft
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_aircraft",
        description=(
            "Retrieve the latest normalized real-time state for a single aircraft by its "
            "24-bit ICAO hex code (e.g. '80167f'). Returns full telemetry including exact "
            "coordinates, altitude, ground speed, vertical rate (climb/descent), and on-ground status. "
            "Use this when inspecting a specific aircraft or tracking a single transponder."
        ),
    )
    async def get_aircraft(
        icao24: str = Field(
            description="24-bit ICAO transponder address in hex (e.g. '80167f', '4006c0').",
        ),
    ) -> GetAircraftOutput:
        result = await registry.execute("get_aircraft", {"icao24": icao24})
        return result  # type: ignore[return-value]

    # --------------------------------------------------------------------------
    # Tool 3: get_aircraft_history
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_aircraft_history",
        description=(
            "Retrieve chronological historical position and flight telemetry track for an "
            "aircraft by its 24-bit ICAO hex code. Supports optional start and end time filtering. "
            "Use this to reconstruct flight paths, analyze climb/descent profiles, or review past tracks."
        ),
    )
    async def get_aircraft_history(
        icao24: str = Field(
            description="24-bit ICAO transponder address in hex (e.g. '80167f').",
        ),
        start_time: Optional[datetime] = Field(
            default=None,
            description="Optional ISO 8601 start timestamp for history query.",
        ),
        end_time: Optional[datetime] = Field(
            default=None,
            description="Optional ISO 8601 end timestamp for history query.",
        ),
        limit: int = Field(
            default=100,
            ge=1,
            le=1000,
            description="Maximum number of historical points to return (1-1000, default 100).",
        ),
    ) -> GetAircraftHistoryOutput:
        params: dict = {"icao24": icao24, "limit": limit}
        if start_time is not None:
            params["start_time"] = start_time.isoformat()
        if end_time is not None:
            params["end_time"] = end_time.isoformat()

        result = await registry.execute("get_aircraft_history", params)
        return result  # type: ignore[return-value]

    # --------------------------------------------------------------------------
    # Tool 4: search_aircraft_in_area
    # --------------------------------------------------------------------------
    @server.tool(
        name="search_aircraft_in_area",
        description=(
            "Find all active aircraft currently within a specified radial distance (in km) "
            "from a geographic coordinate. Results are sorted by distance from the center point "
            "(closest first) and can be filtered by altitude. Use this when the user asks "
            "'what flights are near this location' or 'show aircraft within 100km of coordinates'."
        ),
    )
    async def search_aircraft_in_area(
        latitude: float = Field(
            ge=-90.0,
            le=90.0,
            description="Center latitude in decimal degrees (-90.0 to 90.0).",
        ),
        longitude: float = Field(
            ge=-180.0,
            le=180.0,
            description="Center longitude in decimal degrees (-180.0 to 180.0).",
        ),
        radius_km: float = Field(
            gt=0.0,
            le=2000.0,
            description="Search radius in kilometres (max 2000 km).",
        ),
        min_altitude_m: Optional[float] = Field(
            default=None,
            ge=0.0,
            description="Optional minimum altitude filter in metres.",
        ),
        max_altitude_m: Optional[float] = Field(
            default=None,
            ge=0.0,
            description="Optional maximum altitude filter in metres.",
        ),
        limit: int = Field(
            default=50,
            ge=1,
            le=500,
            description="Maximum aircraft to return (1-500, default 50).",
        ),
    ) -> SearchAircraftInAreaOutput:
        params: dict = {
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km,
            "limit": limit,
        }
        if min_altitude_m is not None:
            params["min_altitude_m"] = min_altitude_m
        if max_altitude_m is not None:
            params["max_altitude_m"] = max_altitude_m

        result = await registry.execute("search_aircraft_in_area", params)
        return result  # type: ignore[return-value]

    # --------------------------------------------------------------------------
    # Tool 5: get_aircraft_near_airport
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_aircraft_near_airport",
        description=(
            "Find all active aircraft currently operating within a specified radial distance "
            "(in km) around an airport. Resolves airport code (ICAO or IATA) automatically, "
            "calculates distances from the airfield, and orders results with closest aircraft first. "
            "Use this when the user asks about aircraft near or approaching a specific airport."
        ),
    )
    async def get_aircraft_near_airport(
        airport_code: str = Field(
            description="4-letter ICAO (e.g. 'VIDP', 'KJFK', 'EGLL') or 3-letter IATA (e.g. 'DEL', 'JFK', 'LHR') code.",
        ),
        radius_km: float = Field(
            default=50.0,
            gt=0.0,
            le=500.0,
            description="Vicinity radius in kilometres around the airport (default 50.0 km, max 500 km).",
        ),
        limit: int = Field(
            default=50,
            ge=1,
            le=500,
            description="Maximum nearby aircraft to return (1-500, default 50).",
        ),
    ) -> GetAircraftNearAirportOutput:
        result = await registry.execute(
            "get_aircraft_near_airport",
            {"airport_code": airport_code, "radius_km": radius_km, "limit": limit},
        )
        return result  # type: ignore[return-value]

    # --------------------------------------------------------------------------
    # Tool 6: get_airport
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_airport",
        description=(
            "Lookup official airport specifications and operational metadata by 4-letter ICAO "
            "code (e.g. 'VIDP', 'EGLL') or 3-letter IATA code (e.g. 'DEL', 'LHR'). Returns airport "
            "name, municipality, country ISO code, geographic coordinates, airfield elevation, "
            "and IANA timezone. Use this when the user requests information about an airport."
        ),
    )
    async def get_airport(
        airport_code: str = Field(
            description="Airport designator: 4-letter ICAO or 3-letter IATA code (e.g. 'VIDP', 'DEL', 'KJFK').",
        ),
    ) -> GetAirportOutput:
        result = await registry.execute("get_airport", {"airport_code": airport_code})
        return result  # type: ignore[return-value]

    # --------------------------------------------------------------------------
    # Tool 7: get_airport_traffic
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_airport_traffic",
        description=(
            "Analyze operational flight traffic around an airport. Uses aviation heuristics to "
            "classify each aircraft into flight phases: inbound (approach/descending towards runway), "
            "outbound (departure/climbing away), ground operations (taxi/runway), and en-route overflights. "
            "Returns counts per phase, detailed traffic records, and an operational summary. "
            "Use this when asked about airport congestion, arrival/departure counts, or airfield activity."
        ),
    )
    async def get_airport_traffic(
        airport_code: str = Field(
            description="ICAO or IATA airport code (e.g. 'VIDP', 'DEL', 'LHR', 'JFK').",
        ),
        time_window_minutes: int = Field(
            default=60,
            ge=5,
            le=1440,
            description="Time window for traffic analysis in minutes (default 60 min, range 5-1440).",
        ),
        radius_km: float = Field(
            default=100.0,
            gt=0.0,
            le=300.0,
            description="Vicinity radius in kilometres around the airport (default 100 km, max 300 km).",
        ),
    ) -> GetAirportTrafficOutput:
        result = await registry.execute(
            "get_airport_traffic",
            {
                "airport_code": airport_code,
                "time_window_minutes": time_window_minutes,
                "radius_km": radius_km,
            },
        )
        return result  # type: ignore[return-value]

    # --------------------------------------------------------------------------
    # Tool 8: get_flight_statistics
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_flight_statistics",
        description=(
            "Compute real-time flight telemetry statistics, altitude distribution percentiles, "
            "speed distributions, and airspace traffic density rating ('LOW', 'MODERATE', 'HIGH', 'VERY_HIGH') "
            "across the entire tracked fleet or filtered by bounding box / registration country. "
            "Use this when asked for high-level airspace overviews, fleet metrics, or regional traffic density."
        ),
    )
    async def get_flight_statistics(
        bounds: Optional[GeoBoundingBox] = Field(
            default=None,
            description="Optional geographic bounding box filter with lamin, lomin, lamax, lomax.",
        ),
        country: Optional[str] = Field(
            default=None,
            description="Optional country name filter (e.g. 'India', 'Germany', 'United States').",
        ),
        time_window_minutes: Optional[int] = Field(
            default=None,
            ge=5,
            le=1440,
            description="Optional time window in minutes (5-1440).",
        ),
    ) -> GetFlightStatisticsOutput:
        params: dict = {}
        if bounds is not None:
            params["bounds"] = bounds.model_dump()
        if country is not None:
            params["country"] = country
        if time_window_minutes is not None:
            params["time_window_minutes"] = time_window_minutes

        result = await registry.execute("get_flight_statistics", params)
        return result  # type: ignore[return-value]

    logger.info(
        "MCPServer '%s' configured with %d aviation domain tools",
        server_name,
        8,
    )
    return server
