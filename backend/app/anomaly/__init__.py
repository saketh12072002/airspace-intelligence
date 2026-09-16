"""Airspace Intelligence Anomaly Detection Subsystem."""

from app.anomaly.detector import TrajectoryAnomalyDetector
from app.anomaly.features import extract_features, haversine_km, compute_heading_delta
from app.anomaly.models import (
    AnomalySeverity,
    AnomalyType,
    CandidateAnomaly,
    TelemetryFeatureVector,
)
from app.anomaly.replay import (
    TrajectoryReplayer,
    create_synthetic_cruise,
    create_synthetic_heading_change,
    create_synthetic_holding_pattern,
    create_synthetic_rapid_descent,
    create_synthetic_stationary_airborne,
)

__all__ = [
    "TrajectoryAnomalyDetector",
    "CandidateAnomaly",
    "AnomalySeverity",
    "AnomalyType",
    "TelemetryFeatureVector",
    "extract_features",
    "haversine_km",
    "compute_heading_delta",
    "TrajectoryReplayer",
    "create_synthetic_cruise",
    "create_synthetic_rapid_descent",
    "create_synthetic_heading_change",
    "create_synthetic_holding_pattern",
    "create_synthetic_stationary_airborne",
]
