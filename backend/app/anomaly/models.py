"""Data models and enums for the Airspace Intelligence Anomaly Detection Subsystem."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnomalySeverity(str, Enum):
    """Categorized severity level for detected aircraft behavior."""

    NORMAL = "NORMAL"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH_CONFIDENCE_ANOMALY = "HIGH_CONFIDENCE_ANOMALY"


class AnomalyType(str, Enum):
    """Catalog of candidate aviation telemetry anomalies."""

    UNEXPECTED_HEADING_CHANGE = "UNEXPECTED_HEADING_CHANGE"
    SIGNIFICANT_ROUTE_DEVIATION = "SIGNIFICANT_ROUTE_DEVIATION"
    UNUSUAL_ALTITUDE_CHANGE = "UNUSUAL_ALTITUDE_CHANGE"
    RAPID_DESCENT = "RAPID_DESCENT"
    RAPID_CLIMB = "RAPID_CLIMB"
    UNUSUAL_SPEED_CHANGE = "UNUSUAL_SPEED_CHANGE"
    AIRCRAFT_APPEARING_DISAPPEARING = "AIRCRAFT_APPEARING_DISAPPEARING"
    HOLDING_PATTERN = "HOLDING_PATTERN"
    STATIONARY_AIRBORNE_POSITION = "STATIONARY_AIRBORNE_POSITION"
    SQUAWK_OR_SYSTEM_ANOMALY = "SQUAWK_OR_SYSTEM_ANOMALY"


class TelemetryFeatureVector(BaseModel):
    """Kinematic differential features computed over consecutive telemetry snapshots."""

    dt_seconds: float = Field(description="Elapsed time in seconds between telemetry points")
    turn_rate_deg_per_sec: float = Field(description="Heading change rate in degrees/sec")
    heading_delta_deg: float = Field(description="Heading delta in degrees (-180 to +180)")
    vertical_rate_fpm: float = Field(description="Vertical speed in feet/minute")
    vertical_accel_fpm_per_sec: float = Field(default=0.0, description="Vertical acceleration")
    ground_speed_knots: float = Field(description="Current ground speed in knots")
    accel_knots_per_sec: float = Field(description="Ground speed acceleration in knots/sec")
    altitude_ft: float = Field(description="Current altitude in feet")
    altitude_delta_ft: float = Field(description="Net altitude change in feet over window")
    distance_moved_km: float = Field(description="Great-circle distance moved in km")
    on_ground: bool = Field(default=False, description="Whether aircraft is on ground")
    squawk: Optional[str] = Field(default=None, description="Current transponder squawk code")


class CandidateAnomaly(BaseModel):
    """A detected candidate anomaly produced by deterministic/statistical algorithms."""

    aircraft_id: str = Field(description="Aircraft 24-bit ICAO hex address or callsign")
    callsign: Optional[str] = Field(default=None, description="Assigned flight callsign")
    anomaly_type: AnomalyType = Field(description="Type of candidate anomaly")
    detection_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when anomaly was detected",
    )
    severity: AnomalySeverity = Field(
        description="Severity classification: NORMAL, SUSPICIOUS, HIGH_CONFIDENCE_ANOMALY",
    )
    observed_values: Dict[str, Any] = Field(
        description="Observed telemetry values triggering the anomaly",
    )
    baseline_values: Dict[str, Any] = Field(
        description="Expected normal baseline thresholds or standard flight envelope values",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Statistical or deterministic confidence score (0.0 to 1.0)",
    )
    supporting_observations: List[str] = Field(
        default_factory=list,
        description="Corroborating factual observations (e.g. altitude loss, heading shift, squawk)",
    )
