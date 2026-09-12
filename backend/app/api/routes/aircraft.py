import json
from typing import Optional
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
import redis.asyncio as aioredis
from pydantic import BaseModel

from app.core.config import get_settings
from app.schemas.aircraft_state import AircraftState
from app.schemas.flight_details import FlightDetailsResponse
from app.services.enrichment.service import EnrichmentService

router = APIRouter()

# Dependency to get a Redis connection for the request
async def get_redis():
    settings = get_settings()
    if not settings.redis_url:
        raise HTTPException(status_code=503, detail="Redis is not configured")
    client = aioredis.from_url(settings.redis_url, decode_responses=False)
    try:
        yield client
    finally:
        await client.aclose()


class AircraftListResponse(BaseModel):
    count: int
    updated_at: str
    aircraft: list[AircraftState]


@router.get("", response_model=AircraftListResponse)
async def list_aircraft(
    redis: aioredis.Redis = Depends(get_redis),
    limit: int = 1000,
    offset: int = 0
):
    """Retrieve a snapshot of currently tracked aircraft from Redis."""
    
    # In a real production scenario with 10k+ aircraft, we might want to paginate 
    # or filter by bounding box. For now, we retrieve all values from the hash.
    # Note: hgetall can be expensive for huge datasets, but Redis is fast.
    raw_data = await redis.hgetall("aircraft:states")
    last_update = await redis.get("aircraft:last_ingestion")
    
    if last_update:
        last_update = last_update.decode("utf-8")
    else:
        last_update = datetime.now(UTC).isoformat()
    
    aircraft_list = []
    for _key, val in raw_data.items():
        try:
            aircraft_list.append(AircraftState.model_validate_json(val))
        except Exception:
            continue
            
    # Apply rudimentary pagination/limits for safety
    paginated = aircraft_list[offset : offset + limit]
    
    return AircraftListResponse(
        count=len(aircraft_list),
        updated_at=last_update,
        aircraft=paginated
    )


@router.get("/{icao24}", response_model=AircraftState)
async def get_aircraft(
    icao24: str, 
    redis: aioredis.Redis = Depends(get_redis)
):
    """Retrieve the current state of a specific aircraft by its ICAO24 address."""
    icao24_lower = icao24.lower()
    raw_data = await redis.hget("aircraft:states", icao24_lower)
    
    if not raw_data:
        raise HTTPException(status_code=404, detail="Aircraft not found or out of coverage")
        
    try:
        return AircraftState.model_validate_json(raw_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse aircraft data: {e}")


@router.get("/{icao24}/details", response_model=FlightDetailsResponse)
async def get_aircraft_details(
    icao24: str,
    redis: aioredis.Redis = Depends(get_redis),
):
    """Retrieve enriched flight details including origin/destination airports, airline, and specs."""
    icao24_lower = icao24.lower()
    raw_data = await redis.hget("aircraft:states", icao24_lower)

    state: Optional[AircraftState] = None
    if raw_data:
        try:
            state = AircraftState.model_validate_json(raw_data)
        except Exception:
            pass

    enrichment = EnrichmentService(redis_client=redis)
    try:
        return await enrichment.enrich_flight(icao24=icao24_lower, state=state)
    finally:
        await enrichment.aclose()

