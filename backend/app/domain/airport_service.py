"""Airport domain service executing airport lookups, radial searches, and traffic analysis."""

from __future__ import annotations

from typing import Optional
from app.core.logging import get_logger
from app.domain.models import FlightPhase, classify_flight_phase
from app.repositories.base import AircraftRepositoryBase, AirportRepositoryBase
from app.schemas.aircraft_state import AircraftState

logger = get_logger(__name__)


class AirportService:
    """Domain service managing airport queries, nearby aircraft discovery, and traffic analysis."""

    def __init__(
        self,
        airport_repo: AirportRepositoryBase,
        aircraft_repo: AircraftRepositoryBase,
    ) -> None:
        self.airport_repo = airport_repo
        self.aircraft_repo = aircraft_repo

    def get_airport(self, code: str) -> Optional[dict]:
        """Lookup airport by ICAO (e.g. 'VIDP') or IATA (e.g. 'DEL') code."""
        return self.airport_repo.get_by_code(code)

    async def get_aircraft_near_airport(
        self,
        airport_code: str,
        radius_km: float = 50.0,
        limit: int = 50,
    ) -> Optional[tuple[dict, list[tuple[AircraftState, float]]]]:
        """Find aircraft currently within radius_km of the airport."""
        apt = self.airport_repo.get_by_code(airport_code)
        if not apt:
            return None

        lat, lon = apt["latitude"], apt["longitude"]
        nearby = await self.aircraft_repo.search_in_radius(
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            limit=limit,
        )
        return apt, nearby

    async def get_airport_traffic(
        self,
        airport_code: str,
        time_window_minutes: int = 60,
        radius_km: float = 100.0,
        limit: int = 100,
    ) -> Optional[dict]:
        """Analyze local arrivals, departures, ground movements, and en-route overflights."""
        result = await self.get_aircraft_near_airport(
            airport_code=airport_code,
            radius_km=radius_km,
            limit=limit,
        )
        if not result:
            return None

        airport, nearby_pairs = result
        apt_lat = airport["latitude"]
        apt_lon = airport["longitude"]

        inbound: list[dict] = []
        outbound: list[dict] = []
        ground: list[dict] = []
        en_route: list[dict] = []
        traffic_list: list[dict] = []

        for ac, dist_km in nearby_pairs:
            phase = classify_flight_phase(
                on_ground=ac.on_ground,
                altitude_m=ac.baro_altitude,
                vertical_rate=ac.vertical_rate,
                distance_to_airport_km=dist_km,
                true_track=ac.true_track,
                airport_lat=apt_lat,
                airport_lon=apt_lon,
                aircraft_lat=ac.latitude,
                aircraft_lon=ac.longitude,
            )

            item = {
                "icao24": ac.icao24,
                "callsign": ac.callsign.strip() if ac.callsign else None,
                "origin_country": ac.origin_country,
                "latitude": ac.latitude,
                "longitude": ac.longitude,
                "altitude_m": ac.baro_altitude,
                "velocity_kmh": round(ac.velocity * 3.6, 1) if ac.velocity is not None else None,
                "true_track": ac.true_track,
                "vertical_rate_ms": ac.vertical_rate,
                "distance_to_airport_km": dist_km,
                "flight_phase": phase.value,
            }
            traffic_list.append(item)

            if phase == FlightPhase.ON_GROUND:
                ground.append(item)
            elif phase == FlightPhase.APPROACH:
                inbound.append(item)
            elif phase == FlightPhase.DEPARTURE:
                outbound.append(item)
            else:
                en_route.append(item)

        apt_name = f"{airport['name']} ({airport.get('iata_code') or airport['icao_code']})"
        summary = (
            f"Traffic for {apt_name} within {radius_km:.0f}km: "
            f"{len(inbound)} inbound (approach), {len(outbound)} outbound (departure), "
            f"{len(ground)} on ground, {len(en_route)} overflying en-route."
        )

        return {
            "airport": airport,
            "time_window_minutes": time_window_minutes,
            "radius_km": radius_km,
            "total_aircraft": len(traffic_list),
            "inbound_count": len(inbound),
            "outbound_count": len(outbound),
            "ground_count": len(ground),
            "en_route_count": len(en_route),
            "traffic": traffic_list,
            "summary": summary,
        }
