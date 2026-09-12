"""Pydantic models for the raw OpenSky Network REST API responses.

These models mirror the API wire format exactly and are used only inside the
OpenSky provider adapter.  They should never leak into the rest of the
application — use :class:`app.schemas.aircraft_state.AircraftState` instead.

Reference: https://openskynetwork.github.io/opensky-api/rest.html
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class OpenSkyStateVector(BaseModel):
    """A single state vector as returned by /states/all.

    The OpenSky API returns each vector as a positional JSON array.  The class
    method :meth:`from_list` handles that conversion.

    Field indices (0-based):
        0  icao24            6  latitude          12 sensors
        1  callsign          7  baro_altitude     13 geo_altitude
        2  origin_country    8  on_ground         14 squawk
        3  time_position     9  velocity          15 spi
        4  last_contact     10  true_track        16 position_source
        5  longitude        11  vertical_rate     17 category (optional)
    """

    icao24: str
    callsign: Optional[str] = None
    origin_country: str = ""
    time_position: Optional[int] = None
    last_contact: int = 0
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    baro_altitude: Optional[float] = None
    on_ground: bool = False
    velocity: Optional[float] = None
    true_track: Optional[float] = None
    vertical_rate: Optional[float] = None
    sensors: Optional[List[int]] = None
    geo_altitude: Optional[float] = None
    squawk: Optional[str] = None
    spi: bool = False
    position_source: int = 0
    category: int = 0

    @classmethod
    def from_list(cls, data: List[Any]) -> "OpenSkyStateVector":
        """Parse a positional list returned by the OpenSky API into a typed model.

        The list may contain 17 or 18 elements (``category`` was added later and
        can be absent in older responses).
        """
        if len(data) < 17:
            raise ValueError(f"State vector must have at least 17 elements, got {len(data)}")

        return cls(
            icao24=data[0],
            callsign=data[1].strip() if isinstance(data[1], str) else None,
            origin_country=data[2] or "",
            time_position=data[3],
            last_contact=data[4] or 0,
            longitude=data[5],
            latitude=data[6],
            baro_altitude=data[7],
            on_ground=bool(data[8]),
            velocity=data[9],
            true_track=data[10],
            vertical_rate=data[11],
            sensors=data[12],
            geo_altitude=data[13],
            squawk=data[14],
            spi=bool(data[15]),
            position_source=data[16] if data[16] is not None else 0,
            category=data[17] if len(data) > 17 and data[17] is not None else 0,
        )


class OpenSkyStatesResponse(BaseModel):
    """Top-level envelope for ``GET /states/all``."""

    time: int
    states: Optional[List[List[Any]]] = None

    def parse_states(self) -> List[OpenSkyStateVector]:
        """Convert the raw nested-list ``states`` into typed objects."""
        if not self.states:
            return []
        results: List[OpenSkyStateVector] = []
        for raw in self.states:
            try:
                results.append(OpenSkyStateVector.from_list(raw))
            except (ValueError, IndexError, TypeError):
                # Skip malformed individual vectors — do not drop the entire batch.
                continue
        return results
