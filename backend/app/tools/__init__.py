"""Aviation domain tool layer for AI copilot agent integration."""

from app.tools.aircraft_tools import (
    GetAircraftHistoryTool,
    GetAircraftTool,
    GetFlightStatisticsTool,
    SearchAircraftInAreaTool,
    SearchAircraftTool,
)
from app.tools.airport_tools import (
    GetAircraftNearAirportTool,
    GetAirportTool,
    GetAirportTrafficTool,
)
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry, create_default_registry
from app.tools.schemas import (
    AircraftStateData,
    AircraftWithDistanceData,
    AirportMetadataData,
    AirportTrafficRecordData,
    AltitudeStatsOutput,
    GeoBoundingBox,
    GetAircraftHistoryInput,
    GetAircraftHistoryOutput,
    GetAircraftInput,
    GetAircraftNearAirportInput,
    GetAircraftNearAirportOutput,
    GetAircraftOutput,
    GetAirportInput,
    GetAirportOutput,
    GetAirportTrafficInput,
    GetAirportTrafficOutput,
    GetFlightStatisticsInput,
    GetFlightStatisticsOutput,
    PositionRecordData,
    SearchAircraftInAreaInput,
    SearchAircraftInAreaOutput,
    SearchAircraftInput,
    SearchAircraftOutput,
    SpeedStatsOutput,
)

__all__ = [
    # Base and Registry
    "BaseTool",
    "ToolRegistry",
    "create_default_registry",
    # 8 Tools
    "SearchAircraftTool",
    "GetAircraftTool",
    "GetAircraftHistoryTool",
    "SearchAircraftInAreaTool",
    "GetAircraftNearAirportTool",
    "GetAirportTool",
    "GetAirportTrafficTool",
    "GetFlightStatisticsTool",
    # Schemas
    "AircraftStateData",
    "AircraftWithDistanceData",
    "AirportMetadataData",
    "AirportTrafficRecordData",
    "AltitudeStatsOutput",
    "SpeedStatsOutput",
    "GeoBoundingBox",
    "SearchAircraftInput",
    "SearchAircraftOutput",
    "GetAircraftInput",
    "GetAircraftOutput",
    "GetAircraftHistoryInput",
    "GetAircraftHistoryOutput",
    "SearchAircraftInAreaInput",
    "SearchAircraftInAreaOutput",
    "GetAircraftNearAirportInput",
    "GetAircraftNearAirportOutput",
    "GetAirportInput",
    "GetAirportOutput",
    "GetAirportTrafficInput",
    "GetAirportTrafficOutput",
    "GetFlightStatisticsInput",
    "GetFlightStatisticsOutput",
    "PositionRecordData",
]
