"""Aircraft domain service executing pure aviation business logic and queries."""

from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Optional, Tuple

from app.core.logging import get_logger
from app.domain.models import AltitudeStatistics, SpeedStatistics, TrafficDensity
from app.repositories.base import AircraftRepositoryBase, HistoryRepositoryBase
from app.schemas.aircraft_state import AircraftState

logger = get_logger(__name__)


class AircraftService:
    """Domain service encapsulating aircraft querying, spatial filtering, and telemetry statistics."""

    def __init__(
        self,
        aircraft_repo: AircraftRepositoryBase,
        history_repo: Optional[HistoryRepositoryBase] = None,
    ) -> None:
        self.aircraft_repo = aircraft_repo
        self.history_repo = history_repo

    async def get_aircraft(self, icao24: str) -> Optional[AircraftState]:
        """Retrieve latest aircraft state by 24-bit ICAO address."""
        clean_icao = icao24.strip().lower()
        return await self.aircraft_repo.get_by_icao24(clean_icao)

    async def search_aircraft(
        self,
        callsign: Optional[str] = None,
        icao24: Optional[str] = None,
        country: Optional[str] = None,
        bounds: Optional[Tuple[float, float, float, float]] = None,
        limit: int = 50,
    ) -> list[AircraftState]:
        """Search aircraft matching optional filters."""
        return await self.aircraft_repo.search(
            callsign=callsign,
            icao24=icao24,
            country=country,
            bounds=bounds,
            limit=limit,
        )

    async def search_in_area(
        self,
        lat: float,
        lon: float,
        radius_km: float,
        min_altitude_m: Optional[float] = None,
        max_altitude_m: Optional[float] = None,
        limit: int = 50,
    ) -> list[tuple[AircraftState, float]]:
        """Search aircraft within a radial distance from a coordinate, sorted by distance."""
        return await self.aircraft_repo.search_in_radius(
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            min_altitude_m=min_altitude_m,
            max_altitude_m=max_altitude_m,
            limit=limit,
        )

    async def get_aircraft_history(
        self,
        icao24: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Fetch chronological position history records for an aircraft."""
        clean_icao = icao24.strip().lower()
        if not self.history_repo:
            # If no history repository attached, synthesize latest state if available
            current = await self.get_aircraft(clean_icao)
            if current and current.latitude is not None and current.longitude is not None:
                return [
                    {
                        "icao24": clean_icao,
                        "callsign": current.callsign,
                        "timestamp": current.last_contact or int(datetime.now(UTC).timestamp()),
                        "latitude": current.latitude,
                        "longitude": current.longitude,
                        "baro_altitude": current.baro_altitude,
                        "velocity": current.velocity,
                        "true_track": current.true_track,
                        "vertical_rate": current.vertical_rate,
                        "on_ground": current.on_ground,
                    }
                ]
            return []

        return await self.history_repo.get_history(
            icao24=clean_icao,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    async def get_flight_statistics(
        self,
        bounds: Optional[Tuple[float, float, float, float]] = None,
        country: Optional[str] = None,
        time_window_minutes: Optional[int] = None,
    ) -> dict:
        """Compute aggregated telemetry metrics and traffic density for aircraft."""
        # Query aircraft matching region/country
        aircraft_list = await self.aircraft_repo.search(
            country=country,
            bounds=bounds,
            limit=10000,
        )

        total = len(aircraft_list)
        if total == 0:
            return {
                "total_aircraft": 0,
                "airborne_count": 0,
                "on_ground_count": 0,
                "altitude_stats": AltitudeStatistics(),
                "speed_stats": SpeedStatistics(),
                "traffic_density": TrafficDensity.LOW,
                "top_origin_countries": [],
                "calculated_at": datetime.now(UTC),
            }

        airborne = 0
        on_ground = 0
        altitudes: list[float] = []
        speeds: list[float] = []
        country_counts: dict[str, int] = {}

        low_alt = 0
        mid_alt = 0
        cruise_alt = 0
        strat_alt = 0

        for ac in aircraft_list:
            if ac.on_ground:
                on_ground += 1
            else:
                airborne += 1

            # Origin country distribution
            c = ac.origin_country or "Unknown"
            country_counts[c] = country_counts.get(c, 0) + 1

            # Altitudes
            if ac.baro_altitude is not None:
                alt = ac.baro_altitude
                altitudes.append(alt)
                if alt < 3000.0:
                    low_alt += 1
                elif alt < 8000.0:
                    mid_alt += 1
                elif alt < 12000.0:
                    cruise_alt += 1
                else:
                    strat_alt += 1

            # Speeds (OpenSky velocity is in m/s, convert to km/h: v * 3.6)
            if ac.velocity is not None:
                speed_kmh = round(ac.velocity * 3.6, 1)
                speeds.append(speed_kmh)

        # Altitude statistics
        if altitudes:
            alt_stats = AltitudeStatistics(
                min_altitude_m=round(min(altitudes), 1),
                max_altitude_m=round(max(altitudes), 1),
                avg_altitude_m=round(statistics.mean(altitudes), 1),
                median_altitude_m=round(statistics.median(altitudes), 1),
                low_altitude_count=low_alt,
                mid_altitude_count=mid_alt,
                cruise_altitude_count=cruise_alt,
                stratosphere_altitude_count=strat_alt,
            )
        else:
            alt_stats = AltitudeStatistics()

        # Speed statistics
        if speeds:
            spd_stats = SpeedStatistics(
                min_speed_kmh=round(min(speeds), 1),
                max_speed_kmh=round(max(speeds), 1),
                avg_speed_kmh=round(statistics.mean(speeds), 1),
                median_speed_kmh=round(statistics.median(speeds), 1),
            )
        else:
            spd_stats = SpeedStatistics()

        # Traffic density estimation
        if total > 500:
            density = TrafficDensity.VERY_HIGH
        elif total > 150:
            density = TrafficDensity.HIGH
        elif total > 30:
            density = TrafficDensity.MODERATE
        else:
            density = TrafficDensity.LOW

        top_countries = [
            {"country": c, "count": count}
            for c, count in sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        return {
            "total_aircraft": total,
            "airborne_count": airborne,
            "on_ground_count": on_ground,
            "altitude_stats": alt_stats,
            "speed_stats": spd_stats,
            "traffic_density": density,
            "top_origin_countries": top_countries,
            "calculated_at": datetime.now(UTC),
        }
