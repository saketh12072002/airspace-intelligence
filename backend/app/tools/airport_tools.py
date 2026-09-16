"""Domain tool implementations for airport queries, nearby aircraft discovery, and traffic analysis."""

from __future__ import annotations

from typing import Optional
from app.domain.airport_service import AirportService
from app.tools.aircraft_tools import _normalize_aircraft_state
from app.tools.base import BaseTool
from app.tools.schemas import (
    AircraftWithDistanceData,
    AirportMetadataData,
    AirportTrafficRecordData,
    GetAircraftNearAirportInput,
    GetAircraftNearAirportOutput,
    GetAirportInput,
    GetAirportOutput,
    GetAirportTrafficInput,
    GetAirportTrafficOutput,
)


class GetAirportTool(BaseTool[GetAirportInput, GetAirportOutput]):
    """Tool 6: Retrieve airport metadata and operational specifications."""

    name = "get_airport"
    description = (
        "Lookup airport metadata, geographic coordinates, municipality, country, "
        "and timezone by 4-letter ICAO code (e.g. 'VIDP') or 3-letter IATA code (e.g. 'DEL')."
    )
    input_schema = GetAirportInput
    output_schema = GetAirportOutput

    def __init__(self, service: AirportService) -> None:
        self.service = service

    async def execute(self, params: GetAirportInput) -> GetAirportOutput:
        clean_code = params.airport_code.strip().upper()
        apt = self.service.get_airport(clean_code)

        if not apt:
            return GetAirportOutput(
                found=False,
                airport_code=clean_code,
                airport=None,
                message=f"Airport with code '{clean_code}' not found in database.",
            )

        return GetAirportOutput(
            found=True,
            airport_code=clean_code,
            airport=AirportMetadataData(**apt),
            message=None,
        )


class GetAircraftNearAirportTool(BaseTool[GetAircraftNearAirportInput, GetAircraftNearAirportOutput]):
    """Tool 5: Discover aircraft within a radial distance around an airport."""

    name = "get_aircraft_near_airport"
    description = (
        "Find all active aircraft currently operating within a specified radial distance "
        "(in km) around an airport, sorted by proximity to the airfield."
    )
    input_schema = GetAircraftNearAirportInput
    output_schema = GetAircraftNearAirportOutput

    def __init__(self, service: AirportService) -> None:
        self.service = service

    async def execute(self, params: GetAircraftNearAirportInput) -> GetAircraftNearAirportOutput:
        clean_code = params.airport_code.strip().upper()
        result = await self.service.get_aircraft_near_airport(
            airport_code=clean_code,
            radius_km=params.radius_km,
            limit=params.limit,
        )

        if not result:
            return GetAircraftNearAirportOutput(
                found=False,
                airport=None,
                radius_km=params.radius_km,
                total_found=0,
                nearby_aircraft=[],
                message=f"Airport with code '{clean_code}' not found in database.",
            )

        apt, nearby_pairs = result
        nearby_aircraft = [
            AircraftWithDistanceData(
                aircraft=_normalize_aircraft_state(ac),
                distance_km=dist_km,
            )
            for ac, dist_km in nearby_pairs
        ]

        return GetAircraftNearAirportOutput(
            found=True,
            airport=AirportMetadataData(**apt),
            radius_km=params.radius_km,
            total_found=len(nearby_aircraft),
            nearby_aircraft=nearby_aircraft,
            message=None if nearby_aircraft else f"No active aircraft currently detected within {params.radius_km:.0f}km.",
        )


class GetAirportTrafficTool(BaseTool[GetAirportTrafficInput, GetAirportTrafficOutput]):
    """Tool 7: Analyze airport operational traffic breakdown and flight phases."""

    name = "get_airport_traffic"
    description = (
        "Analyze operational flight traffic around an airport: breakdown of inbound (approach), "
        "outbound (departure), ground operations, and en-route overflights with synthesized summary."
    )
    input_schema = GetAirportTrafficInput
    output_schema = GetAirportTrafficOutput

    def __init__(self, service: AirportService) -> None:
        self.service = service

    async def execute(self, params: GetAirportTrafficInput) -> GetAirportTrafficOutput:
        clean_code = params.airport_code.strip().upper()
        data = await self.service.get_airport_traffic(
            airport_code=clean_code,
            time_window_minutes=params.time_window_minutes,
            radius_km=params.radius_km,
        )

        if not data:
            return GetAirportTrafficOutput(
                found=False,
                airport=None,
                time_window_minutes=params.time_window_minutes,
                radius_km=params.radius_km,
                total_aircraft=0,
                inbound_count=0,
                outbound_count=0,
                ground_count=0,
                en_route_count=0,
                traffic=[],
                summary=f"Airport with code '{clean_code}' not found in database.",
            )

        return GetAirportTrafficOutput(
            found=True,
            airport=AirportMetadataData(**data["airport"]),
            time_window_minutes=data["time_window_minutes"],
            radius_km=data["radius_km"],
            total_aircraft=data["total_aircraft"],
            inbound_count=data["inbound_count"],
            outbound_count=data["outbound_count"],
            ground_count=data["ground_count"],
            en_route_count=data["en_route_count"],
            traffic=[AirportTrafficRecordData(**t) for t in data["traffic"]],
            summary=data["summary"],
        )
