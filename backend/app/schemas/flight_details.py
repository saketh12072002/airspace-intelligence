"""Pydantic schemas for enriched flight details, routes, airports, and aircraft metadata."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.aircraft_state import AircraftState


class AirportInfo(BaseModel):
    """Details about an origin or destination airport."""
    iata_code: Optional[str] = None
    icao_code: Optional[str] = None
    name: Optional[str] = None
    municipality: Optional[str] = None
    country_name: Optional[str] = None
    country_iso: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    elevation: Optional[float] = None


class AirlineInfo(BaseModel):
    """Details about the airline/operator."""
    name: Optional[str] = None
    icao: Optional[str] = None
    iata: Optional[str] = None
    callsign: Optional[str] = None
    country: Optional[str] = None


class AircraftMetadata(BaseModel):
    """Static aircraft airframe specifications."""
    type: Optional[str] = None
    icao_type: Optional[str] = None
    manufacturer: Optional[str] = None
    registration: Optional[str] = None
    registered_owner: Optional[str] = None
    registered_owner_country: Optional[str] = None
    url_photo: Optional[str] = None
    url_photo_thumbnail: Optional[str] = None


class FlightRoute(BaseModel):
    """Flight route information (departure to destination)."""
    callsign: str
    callsign_icao: Optional[str] = None
    callsign_iata: Optional[str] = None
    airline: Optional[AirlineInfo] = None
    origin: Optional[AirportInfo] = None
    destination: Optional[AirportInfo] = None
    total_distance_km: Optional[float] = None
    distance_flown_km: Optional[float] = None
    distance_remaining_km: Optional[float] = None
    progress_percent: Optional[float] = None


class FlightDetailsResponse(BaseModel):
    """Consolidated flight details endpoint response."""
    icao24: str
    callsign: Optional[str] = None
    state: Optional[AircraftState] = None
    metadata: Optional[AircraftMetadata] = None
    route: Optional[FlightRoute] = None
