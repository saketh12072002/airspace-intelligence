"""State and conversation context models for the Flight Search Agent."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AircraftReference(BaseModel):
    """Context memory snapshot of an active or discussed aircraft."""

    icao24: str = Field(description="24-bit ICAO transponder hex address")
    callsign: Optional[str] = Field(default=None, description="Flight callsign")
    origin_country: str = Field(description="Country of aircraft registration")
    latitude: Optional[float] = Field(default=None, description="Observed latitude")
    longitude: Optional[float] = Field(default=None, description="Observed longitude")
    baro_altitude_m: Optional[float] = Field(default=None, description="Altitude in metres")
    altitude_ft: Optional[float] = Field(default=None, description="Altitude in feet")
    velocity_ms: Optional[float] = Field(default=None, description="Velocity in m/s")
    speed_kmh: Optional[float] = Field(default=None, description="Speed in km/h")
    speed_knots: Optional[float] = Field(default=None, description="Speed in knots")
    true_track: Optional[float] = Field(default=None, description="Heading in degrees")
    vertical_rate_ms: Optional[float] = Field(default=None, description="Climb/descent rate in m/s")
    on_ground: bool = Field(default=False, description="Whether aircraft is on ground")
    flight_phase: Optional[str] = Field(default=None, description="Classified flight phase")
    last_contact: Optional[int] = Field(default=None, description="Epoch timestamp of last contact")


class AirportReference(BaseModel):
    """Context memory snapshot of a discussed airport."""

    code: str = Field(description="ICAO or IATA code")
    name: str = Field(description="Airport name")
    municipality: str = Field(description="City or municipality")
    country: str = Field(description="Country")
    latitude: float = Field(description="Airport latitude")
    longitude: float = Field(description="Airport longitude")


class ToolExecutionRecord(BaseModel):
    """Record of an executed tool call and its validated output."""

    tool_name: str
    arguments: Dict[str, Any]
    result: Any
    is_error: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationTurn(BaseModel):
    """A single dialogue exchange containing query, tool executions, and response."""

    turn_index: int
    user_query: str
    tool_records: List[ToolExecutionRecord] = Field(default_factory=list)
    agent_response: str
    referenced_aircraft: Optional[AircraftReference] = None
    referenced_airport: Optional[AirportReference] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationContext(BaseModel):
    """Multi-turn conversation context maintaining active state for pronoun resolution."""

    conversation_id: str
    turns: List[ConversationTurn] = Field(default_factory=list)
    active_aircraft: Optional[AircraftReference] = None
    active_airport: Optional[AirportReference] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def add_turn(
        self,
        user_query: str,
        agent_response: str,
        tool_records: Optional[List[ToolExecutionRecord]] = None,
        referenced_aircraft: Optional[AircraftReference] = None,
        referenced_airport: Optional[AirportReference] = None,
    ) -> ConversationTurn:
        """Append a completed turn and update active context references."""
        turn = ConversationTurn(
            turn_index=len(self.turns) + 1,
            user_query=user_query,
            tool_records=tool_records or [],
            agent_response=agent_response,
            referenced_aircraft=referenced_aircraft or self.active_aircraft,
            referenced_airport=referenced_airport or self.active_airport,
        )
        self.turns.append(turn)

        if referenced_aircraft is not None:
            self.active_aircraft = referenced_aircraft
        if referenced_airport is not None:
            self.active_airport = referenced_airport

        return turn

    def get_last_aircraft(self) -> Optional[AircraftReference]:
        """Return the most recently referenced aircraft in conversation context."""
        return self.active_aircraft

    def get_last_airport(self) -> Optional[AirportReference]:
        """Return the most recently referenced airport in conversation context."""
        return self.active_airport
