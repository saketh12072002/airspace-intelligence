from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Aircraft(Base):
    __tablename__ = "aircraft"

    id: int = Column(Integer, primary_key=True, index=True)
    icao24: str = Column(String, unique=True, index=True, nullable=False)
    callsign: Optional[str] = Column(String, nullable=True)
    origin_country: Optional[str] = Column(String, nullable=True)
    longitude: Optional[float] = Column(Float, nullable=True)
    latitude: Optional[float] = Column(Float, nullable=True)
    baro_altitude: Optional[float] = Column(Float, nullable=True)
    velocity: Optional[float] = Column(Float, nullable=True)
    true_track: Optional[float] = Column(Float, nullable=True)
    vertical_rate: Optional[float] = Column(Float, nullable=True)
    on_ground: bool = Column(Boolean, default=False, nullable=False)
    last_contact: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    updated_at: datetime = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
