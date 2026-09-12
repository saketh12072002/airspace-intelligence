"""Abstract ADS-B data provider.

Every concrete provider (OpenSky, ADSBExchange, FlightAware, …) must subclass
:class:`ADSBProvider` and implement its abstract methods.  This lets the
ingestion layer swap providers without touching any other part of the stack.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.aircraft_state import AircraftState


class ADSBProvider(ABC):
    """Interface that every ADS-B data source must implement."""

    @abstractmethod
    async def connect(self) -> None:
        """Initialise network resources (HTTP clients, sockets, …)."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Release network resources."""

    @abstractmethod
    async def fetch_states(
        self,
        bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Return raw state dicts (for generic consumers).

        Args:
            bounds: Optional ``(lamin, lomin, lamax, lomax)`` bounding box.
        """

    @abstractmethod
    async def fetch_aircraft_states(
        self,
        bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> List[AircraftState]:
        """Return normalised :class:`AircraftState` objects.

        Args:
            bounds: Optional ``(lamin, lomin, lamax, lomax)`` bounding box.
        """
