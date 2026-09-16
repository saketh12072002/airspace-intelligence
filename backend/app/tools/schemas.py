"""Strict Pydantic schemas for domain tools inputs and outputs."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==============================================================================
# Shared Sub-Models
# ==============================================================================

class AircraftStateData(BaseModel):
    """Normalized real-time aircraft state information."""
    model_config = ConfigDict(frozen=True)

    icao24: str = Field(description="24-bit ICAO transponder address in hex")
    callsign: Optional[str] = Field(default=None, description="Assigned flight callsign")
    origin_country: str = Field(description="Country of aircraft registration")
    latitude: Optional[float] = Field(default=None, description="Latitude in decimal degrees")
    longitude: Optional[float] = Field(default=None, description="Longitude in decimal degrees")
    baro_altitude_m: Optional[float] = Field(default=None, description="Barometric altitude in metres")
    altitude_ft: Optional[float] = Field(default=None, description="Altitude in feet")
    velocity_ms: Optional[float] = Field(default=None, description="Ground speed in metres/second")
    speed_kmh: Optional[float] = Field(default=None, description="Ground speed in km/h")
    speed_knots: Optional[float] = Field(default=None, description="Ground speed in knots")
    true_track: Optional[float] = Field(default=None, description="Heading in degrees from true North (0-360)")
    vertical_rate_ms: Optional[float] = Field(default=None, description="Climb/descent rate in metres/second")
    on_ground: bool = Field(default=False, description="Whether the aircraft is on ground")
    last_contact: int = Field(description="Unix timestamp of last transponder message")


class AircraftWithDistanceData(BaseModel):
    """Aircraft state combined with radial distance to target point."""
    model_config = ConfigDict(frozen=True)

    aircraft: AircraftStateData = Field(description="Aircraft normalized state")
    distance_km: float = Field(description="Distance from target coordinates in kilometres")


class AirportMetadataData(BaseModel):
    """Detailed airport metadata and operational geographic specifications."""
    model_config = ConfigDict(frozen=True)

    icao_code: str = Field(description="4-letter ICAO airport designator")
    iata_code: Optional[str] = Field(default=None, description="3-letter IATA airport designator")
    name: str = Field(description="Official name of the airport")
    municipality: str = Field(description="City or municipality served")
    country_name: str = Field(description="Country where the airport is situated")
    country_iso: str = Field(description="ISO 3166-1 alpha-2 country code")
    latitude: float = Field(description="Airport latitude in decimal degrees")
    longitude: float = Field(description="Airport longitude in decimal degrees")
    elevation_ft: Optional[float] = Field(default=None, description="Airport elevation in feet")
    timezone: Optional[str] = Field(default=None, description="IANA timezone name")


class PositionRecordData(BaseModel):
    """Chronological historical telemetry snapshot for an aircraft."""
    model_config = ConfigDict(frozen=True)

    icao24: str = Field(description="24-bit ICAO transponder address")
    callsign: Optional[str] = Field(default=None, description="Flight callsign")
    timestamp: int = Field(description="Unix timestamp of the telemetry observation")
    latitude: Optional[float] = Field(default=None, description="Observed latitude")
    longitude: Optional[float] = Field(default=None, description="Observed longitude")
    baro_altitude: Optional[float] = Field(default=None, description="Observed barometric altitude in metres")
    velocity: Optional[float] = Field(default=None, description="Observed velocity in m/s")
    true_track: Optional[float] = Field(default=None, description="Observed true track heading")
    vertical_rate: Optional[float] = Field(default=None, description="Observed vertical rate in m/s")
    on_ground: bool = Field(default=False, description="On-ground flag")


class AirportTrafficRecordData(BaseModel):
    """Telemetry and flight phase record for traffic around an airport."""
    model_config = ConfigDict(frozen=True)

    icao24: str = Field(description="24-bit ICAO address")
    callsign: Optional[str] = Field(default=None, description="Callsign")
    origin_country: str = Field(description="Country of registration")
    latitude: Optional[float] = Field(default=None, description="Latitude")
    longitude: Optional[float] = Field(default=None, description="Longitude")
    altitude_m: Optional[float] = Field(default=None, description="Altitude in metres")
    velocity_kmh: Optional[float] = Field(default=None, description="Velocity in km/h")
    true_track: Optional[float] = Field(default=None, description="Heading in degrees")
    vertical_rate_ms: Optional[float] = Field(default=None, description="Vertical rate in m/s")
    distance_to_airport_km: float = Field(description="Radial distance to airport in km")
    flight_phase: str = Field(description="Phase of flight: APPROACH, DEPARTURE, ON_GROUND, EN_ROUTE")


class CountryDistributionData(BaseModel):
    """Aircraft count per country of registration."""
    model_config = ConfigDict(frozen=True)

    country: str = Field(description="Country name")
    count: int = Field(description="Number of aircraft")


class GeoBoundingBox(BaseModel):
    """Geographic bounding box coordinates."""
    model_config = ConfigDict(frozen=True)

    lamin: float = Field(ge=-90.0, le=90.0, description="Minimum latitude (South)")
    lomin: float = Field(ge=-180.0, le=180.0, description="Minimum longitude (West)")
    lamax: float = Field(ge=-90.0, le=90.0, description="Maximum latitude (North)")
    lomax: float = Field(ge=-180.0, le=180.0, description="Maximum longitude (East)")

    @field_validator("lamax")
    @classmethod
    def validate_latitude_order(cls, v: float, info) -> float:
        lamin = info.data.get("lamin")
        if lamin is not None and v < lamin:
            raise ValueError(f"lamax ({v}) must be greater than or equal to lamin ({lamin})")
        return v

    @field_validator("lomax")
    @classmethod
    def validate_longitude_order(cls, v: float, info) -> float:
        lomin = info.data.get("lomin")
        if lomin is not None and v < lomin:
            raise ValueError(f"lomax ({v}) must be greater than or equal to lomin ({lomin})")
        return v


# ==============================================================================
# Tool 1: search_aircraft
# ==============================================================================

class SearchAircraftInput(BaseModel):
    """Parameters for searching active aircraft by identifiers or region."""
    model_config = ConfigDict(extra="forbid")

    callsign: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=10,
        description="Flight callsign (e.g. 'AIC101', 'DLH400', 'IGO612')",
    )
    icao24: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{6}$",
        description="24-bit ICAO transponder address in hex (e.g. '80167f', '3c6444')",
    )
    country: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=60,
        description="Country of aircraft registration (e.g. 'India', 'United States')",
    )
    bounds: Optional[GeoBoundingBox] = Field(
        default=None,
        description="Optional geographic bounding box filter",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of matching aircraft to return",
    )


class SearchAircraftOutput(BaseModel):
    """Normalized search results for aircraft."""
    model_config = ConfigDict(frozen=True)

    total_matched: int = Field(description="Total number of aircraft matching search criteria")
    aircraft: List[AircraftStateData] = Field(description="List of normalized aircraft states")


# ==============================================================================
# Tool 2: get_aircraft
# ==============================================================================

class GetAircraftInput(BaseModel):
    """Parameters for retrieving the latest state of an individual aircraft."""
    model_config = ConfigDict(extra="forbid")

    icao24: str = Field(
        pattern=r"^[0-9a-fA-F]{6}$",
        description="24-bit ICAO transponder hex address (e.g. '80167f')",
    )


class GetAircraftOutput(BaseModel):
    """Latest state of a single aircraft."""
    model_config = ConfigDict(frozen=True)

    found: bool = Field(description="Whether the aircraft is currently active and tracked")
    icao24: str = Field(description="Requested 24-bit ICAO address")
    aircraft: Optional[AircraftStateData] = Field(
        default=None,
        description="Normalized aircraft state if tracked",
    )
    message: Optional[str] = Field(
        default=None,
        description="Descriptive message if aircraft is not tracked",
    )


# ==============================================================================
# Tool 3: get_aircraft_history
# ==============================================================================

class GetAircraftHistoryInput(BaseModel):
    """Parameters for retrieving chronological position history for an aircraft."""
    model_config = ConfigDict(extra="forbid")

    icao24: str = Field(
        pattern=r"^[0-9a-fA-F]{6}$",
        description="24-bit ICAO transponder address in hex",
    )
    start_time: Optional[datetime] = Field(
        default=None,
        description="Start timestamp for history query (ISO 8601)",
    )
    end_time: Optional[datetime] = Field(
        default=None,
        description="End timestamp for history query (ISO 8601)",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of historical positions to return",
    )


class GetAircraftHistoryOutput(BaseModel):
    """Chronological historical track of aircraft positions."""
    model_config = ConfigDict(frozen=True)

    icao24: str = Field(description="24-bit ICAO address")
    record_count: int = Field(description="Number of historical position points returned")
    history: List[PositionRecordData] = Field(
        description="Chronological sequence of past positions",
    )


# ==============================================================================
# Tool 4: search_aircraft_in_area
# ==============================================================================

class SearchAircraftInAreaInput(BaseModel):
    """Parameters for radial geographic search around coordinates."""
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(
        ge=-90.0,
        le=90.0,
        description="Center point latitude in decimal degrees",
    )
    longitude: float = Field(
        ge=-180.0,
        le=180.0,
        description="Center point longitude in decimal degrees",
    )
    radius_km: float = Field(
        gt=0.0,
        le=2000.0,
        description="Search radius in kilometres (max 2000 km)",
    )
    min_altitude_m: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Optional minimum altitude filter in metres",
    )
    max_altitude_m: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Optional maximum altitude filter in metres",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of results to return",
    )


class SearchAircraftInAreaOutput(BaseModel):
    """Aircraft located within the specified geographic radius."""
    model_config = ConfigDict(frozen=True)

    center_latitude: float = Field(description="Search center latitude")
    center_longitude: float = Field(description="Search center longitude")
    radius_km: float = Field(description="Search radius in kilometres")
    total_found: int = Field(description="Total aircraft found within the radius")
    aircraft: List[AircraftWithDistanceData] = Field(
        description="Aircraft sorted by radial distance (closest first)",
    )


# ==============================================================================
# Tool 5: get_aircraft_near_airport
# ==============================================================================

class GetAircraftNearAirportInput(BaseModel):
    """Parameters for finding aircraft near a specific airport."""
    model_config = ConfigDict(extra="forbid")

    airport_code: str = Field(
        pattern=r"^[a-zA-Z0-9]{3,4}$",
        description="ICAO 4-letter (e.g. 'VIDP', 'KJFK') or IATA 3-letter (e.g. 'DEL', 'JFK') airport code",
    )
    radius_km: float = Field(
        default=50.0,
        gt=0.0,
        le=500.0,
        description="Radius in kilometres around the airport (default 50km, max 500km)",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of nearby aircraft to return",
    )


class GetAircraftNearAirportOutput(BaseModel):
    """Aircraft in the vicinity of an airport."""
    model_config = ConfigDict(frozen=True)

    found: bool = Field(description="Whether the airport was found in the database")
    airport: Optional[AirportMetadataData] = Field(
        default=None,
        description="Airport details and coordinates",
    )
    radius_km: float = Field(description="Radius queried in kilometres")
    total_found: int = Field(description="Number of aircraft currently in range")
    nearby_aircraft: List[AircraftWithDistanceData] = Field(
        description="Aircraft ordered by proximity to the airport",
    )
    message: Optional[str] = Field(
        default=None,
        description="Notice if airport was not found or has no traffic",
    )


# ==============================================================================
# Tool 6: get_airport
# ==============================================================================

class GetAirportInput(BaseModel):
    """Parameters for looking up airport metadata by code."""
    model_config = ConfigDict(extra="forbid")

    airport_code: str = Field(
        pattern=r"^[a-zA-Z0-9]{3,4}$",
        description="Airport designator: 4-letter ICAO (e.g. 'VIDP', 'EGLL') or 3-letter IATA (e.g. 'DEL', 'LHR')",
    )


class GetAirportOutput(BaseModel):
    """Airport metadata response."""
    model_config = ConfigDict(frozen=True)

    found: bool = Field(description="Whether the airport was located")
    airport_code: str = Field(description="Requested airport code")
    airport: Optional[AirportMetadataData] = Field(
        default=None,
        description="Airport metadata if found",
    )
    message: Optional[str] = Field(
        default=None,
        description="Descriptive message if airport code was not recognized",
    )


# ==============================================================================
# Tool 7: get_airport_traffic
# ==============================================================================

class GetAirportTrafficInput(BaseModel):
    """Parameters for airport traffic analysis."""
    model_config = ConfigDict(extra="forbid")

    airport_code: str = Field(
        pattern=r"^[a-zA-Z0-9]{3,4}$",
        description="ICAO or IATA code of the airport (e.g. 'VIDP', 'BOM', 'JFK')",
    )
    time_window_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,
        description="Time window for traffic analysis in minutes (default 60 min)",
    )
    radius_km: float = Field(
        default=100.0,
        gt=0.0,
        le=300.0,
        description="Vicinity radius in kilometres around the airport (default 100km)",
    )


class GetAirportTrafficOutput(BaseModel):
    """Operational traffic breakdown around an airport."""
    model_config = ConfigDict(frozen=True)

    found: bool = Field(description="Whether the airport was located")
    airport: Optional[AirportMetadataData] = Field(default=None, description="Airport details")
    time_window_minutes: int = Field(description="Analyzed time window in minutes")
    radius_km: float = Field(description="Analyzed vicinity radius in kilometres")
    total_aircraft: int = Field(description="Total aircraft in airport vicinity")
    inbound_count: int = Field(description="Aircraft on approach / descending towards airport")
    outbound_count: int = Field(description="Aircraft on climb / departing airport")
    ground_count: int = Field(description="Aircraft confirmed on airport ground/taxiway")
    en_route_count: int = Field(description="Aircraft crossing through airspace en-route")
    traffic: List[AirportTrafficRecordData] = Field(description="Detailed per-aircraft traffic list")
    summary: str = Field(description="Concise human-readable traffic assessment")


# ==============================================================================
# Tool 8: get_flight_statistics
# ==============================================================================

class GetFlightStatisticsInput(BaseModel):
    """Parameters for computing regional telemetry metrics and traffic density."""
    model_config = ConfigDict(extra="forbid")

    bounds: Optional[GeoBoundingBox] = Field(
        default=None,
        description="Optional geographic bounding box filter",
    )
    country: Optional[str] = Field(
        default=None,
        description="Optional country filter (e.g. 'India', 'Germany')",
    )
    time_window_minutes: Optional[int] = Field(
        default=None,
        ge=5,
        le=1440,
        description="Optional time window in minutes",
    )


class AltitudeStatsOutput(BaseModel):
    """Aggregated altitude statistics."""
    model_config = ConfigDict(frozen=True)

    min_altitude_m: float = Field(description="Lowest observed altitude in metres")
    max_altitude_m: float = Field(description="Highest observed altitude in metres")
    avg_altitude_m: float = Field(description="Mean altitude in metres")
    median_altitude_m: float = Field(description="Median altitude in metres")
    low_altitude_count: int = Field(description="Count below 3,000m (< FL100)")
    mid_altitude_count: int = Field(description="Count between 3,000m and 8,000m")
    cruise_altitude_count: int = Field(description="Count between 8,000m and 12,000m (Cruise FL260-FL390)")
    stratosphere_altitude_count: int = Field(description="Count above 12,000m (> FL390)")


class SpeedStatsOutput(BaseModel):
    """Aggregated ground speed statistics."""
    model_config = ConfigDict(frozen=True)

    min_speed_kmh: float = Field(description="Lowest observed speed in km/h")
    max_speed_kmh: float = Field(description="Highest observed speed in km/h")
    avg_speed_kmh: float = Field(description="Mean speed in km/h")
    median_speed_kmh: float = Field(description="Median speed in km/h")


class GetFlightStatisticsOutput(BaseModel):
    """Consolidated flight statistics and airspace traffic density analysis."""
    model_config = ConfigDict(frozen=True)

    total_aircraft: int = Field(description="Total aircraft matching criteria")
    airborne_count: int = Field(description="Airborne aircraft count")
    on_ground_count: int = Field(description="Ground aircraft count")
    altitude_stats: AltitudeStatsOutput = Field(description="Altitude distribution and metrics")
    speed_stats: SpeedStatsOutput = Field(description="Velocity distribution and metrics")
    traffic_density: str = Field(description="Airspace density rating: LOW, MODERATE, HIGH, VERY_HIGH")
    top_origin_countries: List[CountryDistributionData] = Field(
        description="Top registered aircraft origin countries",
    )
    calculated_at: datetime = Field(description="Timestamp when statistics were computed")
