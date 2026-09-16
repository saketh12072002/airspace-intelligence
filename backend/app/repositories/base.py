"""Repository interfaces for aircraft, airports, and flight history."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Tuple
from app.schemas.aircraft_state import AircraftState


class AircraftRepositoryBase(ABC):
    """Abstract interface for querying real-time aircraft states."""

    @abstractmethod
    async def get_by_icao24(self, icao24: str) -> Optional[AircraftState]:
        """Fetch a single aircraft state by ICAO24 address."""
        ...

    @abstractmethod
    async def get_all(self) -> list[AircraftState]:
        """Fetch all currently tracked aircraft states."""
        ...

    @abstractmethod
    async def search(
        self,
        callsign: Optional[str] = None,
        icao24: Optional[str] = None,
        country: Optional[str] = None,
        bounds: Optional[Tuple[float, float, float, float]] = None,
        limit: int = 50,
    ) -> list[AircraftState]:
        """Search aircraft matching optional filters."""
        ...

    @abstractmethod
    async def search_in_radius(
        self,
        lat: float,
        lon: float,
        radius_km: float,
        min_altitude_m: Optional[float] = None,
        max_altitude_m: Optional[float] = None,
        limit: int = 50,
    ) -> list[tuple[AircraftState, float]]:
        """Search aircraft within a geographic radius, returning (state, distance_km)."""
        ...


class AirportRepositoryBase(ABC):
    """Abstract interface for querying airport metadata."""

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[dict]:
        """Fetch airport metadata by ICAO or IATA code."""
        ...

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search airports by name, city, or code."""
        ...

    @abstractmethod
    def find_nearest(self, lat: float, lon: float, max_radius_km: float = 500.0) -> Optional[tuple[dict, float]]:
        """Find the nearest airport to given coordinates, returning (airport, distance_km)."""
        ...


class HistoryRepositoryBase(ABC):
    """Abstract interface for querying and recording aircraft position history."""

    @abstractmethod
    async def record_positions(self, states: list[AircraftState]) -> None:
        """Record historical position snapshots."""
        ...

    @abstractmethod
    async def get_history(
        self,
        icao24: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Fetch chronological position records for an aircraft."""
        ...
