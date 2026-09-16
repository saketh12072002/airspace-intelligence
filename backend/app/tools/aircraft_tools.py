"""Domain tool implementations for aircraft searching, single state, history, radial search, and statistics."""

from __future__ import annotations

from typing import Optional
from app.domain.aircraft_service import AircraftService
from app.schemas.aircraft_state import AircraftState
from app.tools.base import BaseTool
from app.tools.schemas import (
    AircraftStateData,
    AircraftWithDistanceData,
    AltitudeStatsOutput,
    GetAircraftHistoryInput,
    GetAircraftHistoryOutput,
    GetAircraftInput,
    GetAircraftOutput,
    GetFlightStatisticsInput,
    GetFlightStatisticsOutput,
    PositionRecordData,
    SearchAircraftInAreaInput,
    SearchAircraftInAreaOutput,
    SearchAircraftInput,
    SearchAircraftOutput,
    SpeedStatsOutput,
)


def _normalize_aircraft_state(state: AircraftState) -> AircraftStateData:
    """Transform internal AircraftState schema to tool output format with unit conversions."""
    alt_m = state.baro_altitude
    alt_ft = round(alt_m * 3.28084, 1) if alt_m is not None else None

    vel_ms = state.velocity
    spd_kmh = round(vel_ms * 3.6, 1) if vel_ms is not None else None
    spd_kts = round(vel_ms * 1.94384, 1) if vel_ms is not None else None

    return AircraftStateData(
        icao24=state.icao24.lower(),
        callsign=state.callsign.strip() if state.callsign else None,
        origin_country=state.origin_country,
        latitude=state.latitude,
        longitude=state.longitude,
        baro_altitude_m=alt_m,
        altitude_ft=alt_ft,
        velocity_ms=vel_ms,
        speed_kmh=spd_kmh,
        speed_knots=spd_kts,
        true_track=state.true_track,
        vertical_rate_ms=state.vertical_rate,
        on_ground=state.on_ground,
        last_contact=state.last_contact,
    )


class SearchAircraftTool(BaseTool[SearchAircraftInput, SearchAircraftOutput]):
    """Tool 1: Search active aircraft by callsign, ICAO hex, country, or bounding box."""

    name = "search_aircraft"
    description = (
        "Search currently active aircraft using callsign, 24-bit ICAO hex code, "
        "registration country, or geographic bounding box."
    )
    input_schema = SearchAircraftInput
    output_schema = SearchAircraftOutput

    def __init__(self, service: AircraftService) -> None:
        self.service = service

    async def execute(self, params: SearchAircraftInput) -> SearchAircraftOutput:
        bounds_tuple = None
        if params.bounds:
            bounds_tuple = (
                params.bounds.lamin,
                params.bounds.lomin,
                params.bounds.lamax,
                params.bounds.lomax,
            )

        states = await self.service.search_aircraft(
            callsign=params.callsign,
            icao24=params.icao24,
            country=params.country,
            bounds=bounds_tuple,
            limit=params.limit,
        )

        normalized = [_normalize_aircraft_state(s) for s in states]
        return SearchAircraftOutput(
            total_matched=len(normalized),
            aircraft=normalized,
        )


class GetAircraftTool(BaseTool[GetAircraftInput, GetAircraftOutput]):
    """Tool 2: Retrieve the latest state of a specific aircraft by its ICAO24 address."""

    name = "get_aircraft"
    description = "Retrieve the latest normalized real-time state for an aircraft by its 24-bit ICAO hex code."
    input_schema = GetAircraftInput
    output_schema = GetAircraftOutput

    def __init__(self, service: AircraftService) -> None:
        self.service = service

    async def execute(self, params: GetAircraftInput) -> GetAircraftOutput:
        clean_icao = params.icao24.lower()
        state = await self.service.get_aircraft(clean_icao)

        if not state:
            return GetAircraftOutput(
                found=False,
                icao24=clean_icao,
                aircraft=None,
                message=f"Aircraft with ICAO24 '{clean_icao}' is not currently tracked or out of coverage.",
            )

        return GetAircraftOutput(
            found=True,
            icao24=clean_icao,
            aircraft=_normalize_aircraft_state(state),
            message=None,
        )


class GetAircraftHistoryTool(BaseTool[GetAircraftHistoryInput, GetAircraftHistoryOutput]):
    """Tool 3: Retrieve chronological position and flight state history for an aircraft."""

    name = "get_aircraft_history"
    description = (
        "Retrieve the chronological historical position track and telemetry history "
        "for an aircraft within an optional time range."
    )
    input_schema = GetAircraftHistoryInput
    output_schema = GetAircraftHistoryOutput

    def __init__(self, service: AircraftService) -> None:
        self.service = service

    async def execute(self, params: GetAircraftHistoryInput) -> GetAircraftHistoryOutput:
        clean_icao = params.icao24.lower()
        records = await self.service.get_aircraft_history(
            icao24=clean_icao,
            start_time=params.start_time,
            end_time=params.end_time,
            limit=params.limit,
        )

        formatted_records = [
            PositionRecordData(
                icao24=clean_icao,
                callsign=r.get("callsign"),
                timestamp=r.get("timestamp", 0),
                latitude=r.get("latitude"),
                longitude=r.get("longitude"),
                baro_altitude=r.get("baro_altitude"),
                velocity=r.get("velocity"),
                true_track=r.get("true_track"),
                vertical_rate=r.get("vertical_rate"),
                on_ground=r.get("on_ground", False),
            )
            for r in records
        ]

        return GetAircraftHistoryOutput(
            icao24=clean_icao,
            record_count=len(formatted_records),
            history=formatted_records,
        )


class SearchAircraftInAreaTool(BaseTool[SearchAircraftInAreaInput, SearchAircraftInAreaOutput]):
    """Tool 4: Radial geographic search around coordinates."""

    name = "search_aircraft_in_area"
    description = (
        "Find all active aircraft currently within a specified radial distance (in km) "
        "from a geographic coordinate, sorted by distance from center."
    )
    input_schema = SearchAircraftInAreaInput
    output_schema = SearchAircraftInAreaOutput

    def __init__(self, service: AircraftService) -> None:
        self.service = service

    async def execute(self, params: SearchAircraftInAreaInput) -> SearchAircraftInAreaOutput:
        results = await self.service.search_in_area(
            lat=params.latitude,
            lon=params.longitude,
            radius_km=params.radius_km,
            min_altitude_m=params.min_altitude_m,
            max_altitude_m=params.max_altitude_m,
            limit=params.limit,
        )

        aircraft_with_dist = [
            AircraftWithDistanceData(
                aircraft=_normalize_aircraft_state(state),
                distance_km=dist_km,
            )
            for state, dist_km in results
        ]

        return SearchAircraftInAreaOutput(
            center_latitude=params.latitude,
            center_longitude=params.longitude,
            radius_km=params.radius_km,
            total_found=len(aircraft_with_dist),
            aircraft=aircraft_with_dist,
        )


class GetFlightStatisticsTool(BaseTool[GetFlightStatisticsInput, GetFlightStatisticsOutput]):
    """Tool 8: Compute aggregated telemetry metrics and traffic density rating."""

    name = "get_flight_statistics"
    description = (
        "Compute real-time flight telemetry statistics, altitude distributions, speed percentiles, "
        "and airspace traffic density rating for an optional region or country."
    )
    input_schema = GetFlightStatisticsInput
    output_schema = GetFlightStatisticsOutput

    def __init__(self, service: AircraftService) -> None:
        self.service = service

    async def execute(self, params: GetFlightStatisticsInput) -> GetFlightStatisticsOutput:
        bounds_tuple = None
        if params.bounds:
            bounds_tuple = (
                params.bounds.lamin,
                params.bounds.lomin,
                params.bounds.lamax,
                params.bounds.lomax,
            )

        data = await self.service.get_flight_statistics(
            bounds=bounds_tuple,
            country=params.country,
            time_window_minutes=params.time_window_minutes,
        )

        alt = data["altitude_stats"]
        spd = data["speed_stats"]

        return GetFlightStatisticsOutput(
            total_aircraft=data["total_aircraft"],
            airborne_count=data["airborne_count"],
            on_ground_count=data["on_ground_count"],
            altitude_stats=AltitudeStatsOutput(
                min_altitude_m=alt.min_altitude_m,
                max_altitude_m=alt.max_altitude_m,
                avg_altitude_m=alt.avg_altitude_m,
                median_altitude_m=alt.median_altitude_m,
                low_altitude_count=alt.low_altitude_count,
                mid_altitude_count=alt.mid_altitude_count,
                cruise_altitude_count=alt.cruise_altitude_count,
                stratosphere_altitude_count=alt.stratosphere_altitude_count,
            ),
            speed_stats=SpeedStatsOutput(
                min_speed_kmh=spd.min_speed_kmh,
                max_speed_kmh=spd.max_speed_kmh,
                avg_speed_kmh=spd.avg_speed_kmh,
                median_speed_kmh=spd.median_speed_kmh,
            ),
            traffic_density=data["traffic_density"].value,
            top_origin_countries=data["top_origin_countries"],
            calculated_at=data["calculated_at"],
        )
