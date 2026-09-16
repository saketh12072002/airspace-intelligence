"""Domain models, flight phase classifications, and geodesic calculation utilities."""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class FlightPhase(str, Enum):
    """Aviation flight phase classification."""
    ON_GROUND = "ON_GROUND"
    APPROACH = "APPROACH"
    DEPARTURE = "DEPARTURE"
    EN_ROUTE = "EN_ROUTE"


class TrafficDensity(str, Enum):
    """Traffic density scoring classification."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the Great Circle distance in kilometres between two coordinates."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    return round(r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)), 2)


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial compass bearing (0-360 degrees) from coordinate 1 to coordinate 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return round(bearing, 1)


def is_heading_towards(
    track: Optional[float],
    bearing_to_target: float,
    tolerance_deg: float = 60.0,
) -> bool:
    """Determine whether the aircraft true track is oriented towards a target bearing."""
    if track is None:
        return False
    diff = abs((track - bearing_to_target + 180) % 360 - 180)
    return diff <= tolerance_deg


def classify_flight_phase(
    on_ground: bool,
    altitude_m: Optional[float],
    vertical_rate: Optional[float],
    distance_to_airport_km: float,
    true_track: Optional[float] = None,
    airport_lat: Optional[float] = None,
    airport_lon: Optional[float] = None,
    aircraft_lat: Optional[float] = None,
    aircraft_lon: Optional[float] = None,
) -> FlightPhase:
    """Classify the operational flight phase relative to an airport."""
    if on_ground or (altitude_m is not None and altitude_m < 100.0 and distance_to_airport_km <= 5.0):
        return FlightPhase.ON_GROUND

    v_rate = vertical_rate or 0.0

    # Near airport (within 80 km)
    if distance_to_airport_km <= 80.0:
        if v_rate < -0.8:
            return FlightPhase.APPROACH
        if v_rate > 0.8:
            return FlightPhase.DEPARTURE

        # Heading analysis if lat/lon available
        if (
            true_track is not None
            and airport_lat is not None
            and airport_lon is not None
            and aircraft_lat is not None
            and aircraft_lon is not None
        ):
            bearing_to_airport = calculate_bearing(aircraft_lat, aircraft_lon, airport_lat, airport_lon)
            if is_heading_towards(true_track, bearing_to_airport, tolerance_deg=45.0):
                return FlightPhase.APPROACH
            bearing_from_airport = calculate_bearing(airport_lat, airport_lon, aircraft_lat, aircraft_lon)
            if is_heading_towards(true_track, bearing_from_airport, tolerance_deg=45.0):
                return FlightPhase.DEPARTURE

    return FlightPhase.EN_ROUTE


class AltitudeStatistics(BaseModel):
    """Aggregated altitude statistics."""
    model_config = ConfigDict(frozen=True)

    min_altitude_m: float = Field(default=0.0, description="Minimum altitude in metres")
    max_altitude_m: float = Field(default=0.0, description="Maximum altitude in metres")
    avg_altitude_m: float = Field(default=0.0, description="Average altitude in metres")
    median_altitude_m: float = Field(default=0.0, description="Median altitude in metres")
    low_altitude_count: int = Field(default=0, description="Aircraft below 3,000m (10,000 ft)")
    mid_altitude_count: int = Field(default=0, description="Aircraft between 3,000m and 8,000m")
    cruise_altitude_count: int = Field(default=0, description="Aircraft between 8,000m and 12,000m")
    stratosphere_altitude_count: int = Field(default=0, description="Aircraft above 12,000m (40,000+ ft)")


class SpeedStatistics(BaseModel):
    """Aggregated ground speed statistics."""
    model_config = ConfigDict(frozen=True)

    min_speed_kmh: float = Field(default=0.0, description="Minimum velocity in km/h")
    max_speed_kmh: float = Field(default=0.0, description="Maximum velocity in km/h")
    avg_speed_kmh: float = Field(default=0.0, description="Average velocity in km/h")
    median_speed_kmh: float = Field(default=0.0, description="Median velocity in km/h")
