"""Flight and aircraft enrichment service.

Enriches raw ADS-B aircraft state with flight route information (departure/destination
airports), airline details, aircraft airframe specifications (model, manufacturer,
registration), and photos using ADSBdb API with Redis caching and offline fallbacks.
"""

from __future__ import annotations

import json
import math
from typing import Optional, Tuple
import httpx
import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.schemas.aircraft_state import AircraftState
from app.schemas.flight_details import (
    AircraftMetadata,
    AirlineInfo,
    AirportInfo,
    FlightDetailsResponse,
    FlightRoute,
)

logger = get_logger(__name__)

ADSBDB_BASE_URL = "https://api.adsbdb.com/v0"
ROUTE_CACHE_TTL = 86400  # 24 hours
AIRCRAFT_CACHE_TTL = 604800  # 7 days

# Common airline designators (ICAO 3-letter -> Name, IATA, Country)
AIRLINE_DIRECTORY = {
    "AIC": ("Air India", "AI", "India"),
    "IGO": ("IndiGo", "6E", "India"),
    "SEJ": ("SpiceJet", "SG", "India"),
    "VTI": ("Vistara", "UK", "India"),
    "AXB": ("Air India Express", "IX", "India"),
    "AKJ": ("Akasa Air", "QP", "India"),
    "UAE": ("Emirates", "EK", "United Arab Emirates"),
    "ETD": ("Etihad Airways", "EY", "United Arab Emirates"),
    "QTR": ("Qatar Airways", "QR", "Qatar"),
    "DLH": ("Lufthansa", "LH", "Germany"),
    "BAW": ("British Airways", "BA", "United Kingdom"),
    "AFR": ("Air France", "AF", "France"),
    "KLM": ("KLM Royal Dutch Airlines", "KL", "Netherlands"),
    "SIA": ("Singapore Airlines", "SQ", "Singapore"),
    "THY": ("Turkish Airlines", "TK", "Turkey"),
    "UAL": ("United Airlines", "UA", "United States"),
    "AAL": ("American Airlines", "AA", "United States"),
    "DAL": ("Delta Air Lines", "DL", "United States"),
    "SWA": ("Southwest Airlines", "WN", "United States"),
    "RYR": ("Ryanair", "FR", "Ireland"),
    "EZY": ("easyJet", "U2", "United Kingdom"),
    "WZZ": ("Wizz Air", "W6", "Hungary"),
    "ANA": ("All Nippon Airways", "NH", "Japan"),
    "JAL": ("Japan Airlines", "JL", "Japan"),
    "CPA": ("Cathay Pacific", "CX", "Hong Kong"),
    "QFA": ("Qantas", "QF", "Australia"),
}


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the Great Circle distance between two points in kilometres."""
    r = 6371.0  # Earth's radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


class EnrichmentService:
    """Provides flight route and aircraft specifications with Redis caching."""

    def __init__(self, redis_client: aioredis.Redis, timeout: float = 4.0) -> None:
        self.redis = redis_client
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def aclose(self) -> None:
        await self.client.aclose()

    async def get_route(self, callsign: str) -> Optional[FlightRoute]:
        """Lookup flight route by callsign (e.g. 'DLH400', 'AIC101')."""
        clean_callsign = callsign.strip().upper()
        if not clean_callsign:
            return None

        cache_key = f"flight:route:{clean_callsign}"
        try:
            cached = await self.redis.get(cache_key)
            if cached:
                return FlightRoute.model_validate_json(cached)
        except Exception as e:
            logger.warning("Redis cache get error for route %s: %s", clean_callsign, e)

        route: Optional[FlightRoute] = None
        try:
            resp = await self.client.get(f"{ADSBDB_BASE_URL}/callsign/{clean_callsign}")
            if resp.status_code == 200:
                data = resp.json().get("response", {}).get("flightroute")
                if data:
                    origin_data = data.get("origin") or {}
                    dest_data = data.get("destination") or {}
                    airline_data = data.get("airline") or {}

                    origin = AirportInfo(
                        iata_code=origin_data.get("iata_code"),
                        icao_code=origin_data.get("icao_code"),
                        name=origin_data.get("name"),
                        municipality=origin_data.get("municipality"),
                        country_name=origin_data.get("country_name"),
                        country_iso=origin_data.get("country_iso_name"),
                        latitude=origin_data.get("latitude"),
                        longitude=origin_data.get("longitude"),
                        elevation=origin_data.get("elevation"),
                    )

                    destination = AirportInfo(
                        iata_code=dest_data.get("iata_code"),
                        icao_code=dest_data.get("icao_code"),
                        name=dest_data.get("name"),
                        municipality=dest_data.get("municipality"),
                        country_name=dest_data.get("country_name"),
                        country_iso=dest_data.get("country_iso_name"),
                        latitude=dest_data.get("latitude"),
                        longitude=dest_data.get("longitude"),
                        elevation=dest_data.get("elevation"),
                    )

                    airline = AirlineInfo(
                        name=airline_data.get("name"),
                        icao=airline_data.get("icao"),
                        iata=airline_data.get("iata"),
                        callsign=airline_data.get("callsign"),
                        country=airline_data.get("country"),
                    )

                    route = FlightRoute(
                        callsign=clean_callsign,
                        callsign_icao=data.get("callsign_icao", clean_callsign),
                        callsign_iata=data.get("callsign_iata"),
                        airline=airline,
                        origin=origin,
                        destination=destination,
                    )
        except Exception as e:
            logger.info("External route lookup failed for %s: %s", clean_callsign, e)

        # Offline heuristic fallback for airline if external route not found
        if not route:
            prefix = clean_callsign[:3]
            if prefix in AIRLINE_DIRECTORY:
                name, iata, country = AIRLINE_DIRECTORY[prefix]
                flight_num = clean_callsign[3:].lstrip("0")
                iata_callsign = f"{iata}{flight_num}" if iata else None
                route = FlightRoute(
                    callsign=clean_callsign,
                    callsign_icao=clean_callsign,
                    callsign_iata=iata_callsign,
                    airline=AirlineInfo(name=name, icao=prefix, iata=iata, country=country),
                )

        if route:
            try:
                await self.redis.set(cache_key, route.model_dump_json(), ex=ROUTE_CACHE_TTL)
            except Exception as e:
                logger.warning("Redis cache set error for route: %s", e)

        return route

    async def get_aircraft_metadata(self, icao24: str) -> Optional[AircraftMetadata]:
        """Lookup aircraft airframe specifications by ICAO24 hex address."""
        clean_icao = icao24.strip().lower()
        if not clean_icao:
            return None

        cache_key = f"aircraft:meta:{clean_icao}"
        try:
            cached = await self.redis.get(cache_key)
            if cached:
                return AircraftMetadata.model_validate_json(cached)
        except Exception as e:
            logger.warning("Redis cache get error for meta %s: %s", clean_icao, e)

        meta: Optional[AircraftMetadata] = None
        try:
            resp = await self.client.get(f"{ADSBDB_BASE_URL}/aircraft/{clean_icao}")
            if resp.status_code == 200:
                data = resp.json().get("response", {}).get("aircraft")
                if data:
                    meta = AircraftMetadata(
                        type=data.get("type"),
                        icao_type=data.get("icao_type"),
                        manufacturer=data.get("manufacturer"),
                        registration=data.get("registration"),
                        registered_owner=data.get("registered_owner"),
                        registered_owner_country=data.get("registered_owner_country_name"),
                        url_photo=data.get("url_photo"),
                        url_photo_thumbnail=data.get("url_photo_thumbnail"),
                    )
        except Exception as e:
            logger.info("External aircraft metadata lookup failed for %s: %s", clean_icao, e)

        if meta:
            try:
                await self.redis.set(cache_key, meta.model_dump_json(), ex=AIRCRAFT_CACHE_TTL)
            except Exception as e:
                logger.warning("Redis cache set error for metadata: %s", e)

        return meta

    async def enrich_flight(
        self,
        icao24: str,
        state: Optional[AircraftState] = None,
    ) -> FlightDetailsResponse:
        """Consolidate live telemetry, flight route, and aircraft metadata."""
        callsign = state.callsign.strip() if (state and state.callsign) else ""

        route = await self.get_route(callsign) if callsign else None
        meta = await self.get_aircraft_metadata(icao24)

        # Calculate distances and flight progress if origin, destination, and current coords are present
        if route and route.origin and route.destination:
            o_lat, o_lon = route.origin.latitude, route.origin.longitude
            d_lat, d_lon = route.destination.latitude, route.destination.longitude

            if o_lat is not None and o_lon is not None and d_lat is not None and d_lon is not None:
                total_dist = haversine_distance_km(o_lat, o_lon, d_lat, d_lon)
                route.total_distance_km = round(total_dist, 1)

                if state and state.latitude is not None and state.longitude is not None:
                    flown = haversine_distance_km(o_lat, o_lon, state.latitude, state.longitude)
                    remaining = haversine_distance_km(state.latitude, state.longitude, d_lat, d_lon)
                    route.distance_flown_km = round(flown, 1)
                    route.distance_remaining_km = round(remaining, 1)

                    if total_dist > 0:
                        progress = min(100.0, max(0.0, (flown / total_dist) * 100.0))
                        route.progress_percent = round(progress, 1)

        return FlightDetailsResponse(
            icao24=icao24.lower(),
            callsign=callsign or None,
            state=state,
            metadata=meta,
            route=route,
        )
