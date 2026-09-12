"""Internal AircraftState model — the canonical representation used across the platform.

This model is intentionally decoupled from the OpenSky state-vector format so that
swapping the ADS-B data provider requires changes only in the provider adapter,
never in consumers of AircraftState.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from pydantic import BaseModel, Field


class AircraftState(BaseModel):
    """Normalized aircraft state produced by any ADS-B provider adapter."""

    icao24: str = Field(..., description="ICAO 24-bit transponder address (hex)")
    callsign: Optional[str] = Field(None, description="Callsign (8 chars)")
    origin_country: str = Field(..., description="Country of registration")
    time_position: Optional[int] = Field(None, description="Unix timestamp of last position update")
    last_contact: int = Field(..., description="Unix timestamp of last message received")
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    baro_altitude: Optional[float] = Field(None, description="Barometric altitude in metres")
    on_ground: bool = Field(False)
    velocity: Optional[float] = Field(None, description="Ground speed in m/s")
    true_track: Optional[float] = Field(None, description="Track angle in degrees clockwise from north")
    vertical_rate: Optional[float] = Field(None, description="Vertical rate in m/s")
    geo_altitude: Optional[float] = Field(None, description="Geometric altitude in metres")
    squawk: Optional[str] = Field(None, description="Transponder squawk code")
    position_source: int = Field(0, description="0=ADS-B, 1=ASTERIX, 2=MLAT, 3=FLARM")
    category: int = Field(0, description="Aircraft category (0=No info, 1-7 per DO-260B)")
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Timestamp when state was ingested")
