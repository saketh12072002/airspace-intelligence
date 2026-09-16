"""Repositories package."""

from app.repositories.base import (
    AircraftRepositoryBase,
    AirportRepositoryBase,
    HistoryRepositoryBase,
)
from app.repositories.aircraft_repo import (
    InMemoryAircraftRepository,
    RedisAircraftRepository,
)
from app.repositories.airport_repo import AirportRepository
from app.repositories.history_repo import HistoryRepository

__all__ = [
    "AircraftRepositoryBase",
    "AirportRepositoryBase",
    "HistoryRepositoryBase",
    "RedisAircraftRepository",
    "InMemoryAircraftRepository",
    "AirportRepository",
    "HistoryRepository",
]
