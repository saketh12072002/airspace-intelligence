from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class AircraftBase(BaseModel):
    icao24: str
    callsign: Optional[str] = None
    origin_country: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    baro_altitude: Optional[float] = None
    velocity: Optional[float] = None
    true_track: Optional[float] = None
    vertical_rate: Optional[float] = None
    on_ground: bool = False


class AircraftResponse(AircraftBase):
    id: int
    last_contact: Optional[datetime] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AircraftList(BaseModel):
    count: int
    aircraft: List[AircraftResponse]
