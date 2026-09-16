"""Historical replay simulation engine running trajectories through feature extraction and anomaly detectors."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from app.anomaly.detector import TrajectoryAnomalyDetector
from app.anomaly.models import CandidateAnomaly
from app.core.logging import get_logger

logger = get_logger(__name__)


class TrajectoryReplayer:
    """Simulates real-time telemetry streaming by feeding sequential trajectory points into the detector."""

    def __init__(self, detector: Optional[TrajectoryAnomalyDetector] = None) -> None:
        self.detector = detector or TrajectoryAnomalyDetector()

    def replay_trajectory(
        self,
        points: List[Dict[str, Any]],
        window_size: int = 15,
    ) -> List[CandidateAnomaly]:
        """Replay a chronological sequence of telemetry observations and detect all candidate anomalies.

        Args:
            points: Chronologically ordered list of telemetry snapshots.
            window_size: Maximum historical points maintained in sliding window.

        Returns:
            List of all CandidateAnomaly events detected throughout the replay.
        """
        all_detected: List[CandidateAnomaly] = []
        if not points:
            return all_detected

        # Analyze first point for standalone anomalies
        first_anomalies = self.detector.detect_anomalies(curr_point=points[0])
        all_detected.extend(first_anomalies)

        # Step through trajectory sequentially
        for i in range(1, len(points)):
            prev = points[i - 1]
            curr = points[i]
            history_window = points[max(0, i - window_size) : i + 1]

            step_anomalies = self.detector.detect_anomalies(
                curr_point=curr,
                prev_point=prev,
                history=history_window,
            )
            all_detected.extend(step_anomalies)

        logger.info(
            "Replay of %d points completed: %d candidate anomalies detected",
            len(points),
            len(all_detected),
        )
        return all_detected


# ==============================================================================
# Synthetic Trajectory Generators for Replay Testing
# ==============================================================================

def create_synthetic_cruise(
    icao24: str = "80167f",
    callsign: str = "AIC101",
    start_time: int = 1700000000,
    steps: int = 10,
    start_lat: float = 28.5,
    start_lon: float = 77.1,
    altitude_m: float = 10668.0,  # 35,000 ft
    speed_ms: float = 230.0,      # ~450 knots
    track_deg: float = 90.0,
) -> List[Dict[str, Any]]:
    """Generate a nominal commercial airliner cruise trajectory."""
    points = []
    lat, lon = start_lat, start_lon

    for i in range(steps):
        t = start_time + (i * 10)  # 10 second intervals
        # Advance eastwards
        lon += 0.02
        points.append({
            "icao24": icao24,
            "callsign": callsign,
            "timestamp": t,
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "baro_altitude": altitude_m,
            "velocity": speed_ms,
            "true_track": track_deg,
            "vertical_rate": 0.0,
            "on_ground": False,
            "squawk": "4211",
        })
    return points


def create_synthetic_rapid_descent(
    icao24: str = "80167f",
    callsign: str = "AIC203",
    start_time: int = 1700000000,
) -> List[Dict[str, Any]]:
    """Generate a high-altitude trajectory with an emergency-rate rapid descent (-7,000 ft/min)."""
    points = create_synthetic_cruise(
        icao24=icao24,
        callsign=callsign,
        start_time=start_time,
        steps=3,
        altitude_m=10668.0,  # 35,000 ft
    )

    t_curr = points[-1]["timestamp"]
    lat = points[-1]["latitude"]
    lon = points[-1]["longitude"]
    alt_m = points[-1]["baro_altitude"]

    # Execute 4 steps of rapid descent (-35.5 m/s ≈ -7,000 ft/min)
    descent_rate_ms = -35.5
    for i in range(1, 5):
        t_curr += 10
        lon += 0.02
        alt_m += descent_rate_ms * 10
        points.append({
            "icao24": icao24,
            "callsign": callsign,
            "timestamp": t_curr,
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "baro_altitude": round(alt_m, 1),
            "velocity": 240.0,
            "true_track": 90.0,
            "vertical_rate": descent_rate_ms,
            "on_ground": False,
            "squawk": "4211",
        })

    return points


def create_synthetic_heading_change(
    icao24: str = "80167f",
    callsign: str = "AIC304",
    start_time: int = 1700000000,
) -> List[Dict[str, Any]]:
    """Generate a cruise flight that performs an abrupt 90-degree turn in 10 seconds."""
    points = create_synthetic_cruise(
        icao24=icao24,
        callsign=callsign,
        start_time=start_time,
        steps=3,
        track_deg=90.0,  # Heading East
    )

    t_curr = points[-1]["timestamp"] + 10
    lat = points[-1]["latitude"]
    lon = points[-1]["longitude"] + 0.01

    # Sudden 90 degree sharp turn to North (turn rate = 9.0 deg/s)
    points.append({
        "icao24": icao24,
        "callsign": callsign,
        "timestamp": t_curr,
        "latitude": round(lat + 0.02, 4),
        "longitude": round(lon, 4),
        "baro_altitude": 10668.0,
        "velocity": 230.0,
        "true_track": 0.0,  # Abrupt shift to North (0 deg)
        "vertical_rate": 0.0,
        "on_ground": False,
        "squawk": "4211",
    })

    return points


def create_synthetic_holding_pattern(
    icao24: str = "80167f",
    callsign: str = "AIC405",
    start_time: int = 1700000000,
    center_lat: float = 28.5,
    center_lon: float = 77.1,
    radius_deg: float = 0.05,
) -> List[Dict[str, Any]]:
    """Generate a complete 360-degree orbiting holding pattern."""
    points = []
    # 8 points describing an orbit circle (360 degrees)
    for i in range(9):
        angle_rad = (i / 8.0) * 2.0 * math.pi
        t = start_time + (i * 20)
        lat = center_lat + radius_deg * math.sin(angle_rad)
        lon = center_lon + radius_deg * math.cos(angle_rad)
        track = (math.degrees(angle_rad + math.pi / 2.0)) % 360.0

        points.append({
            "icao24": icao24,
            "callsign": callsign,
            "timestamp": t,
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "baro_altitude": 3048.0,  # 10,000 ft constant
            "velocity": 120.0,        # ~230 knots holding speed
            "true_track": round(track, 1),
            "vertical_rate": 0.0,
            "on_ground": False,
            "squawk": "4211",
        })
    return points


def create_synthetic_stationary_airborne(
    icao24: str = "80167f",
    callsign: str = "AIC506",
    start_time: int = 1700000000,
) -> List[Dict[str, Any]]:
    """Generate an anomalous stationary airborne flight (0 knots at 20,000 ft)."""
    points = [
        {
            "icao24": icao24,
            "callsign": callsign,
            "timestamp": start_time,
            "latitude": 28.5,
            "longitude": 77.1,
            "baro_altitude": 6096.0,  # 20,000 ft
            "velocity": 0.0,          # 0 knots!
            "true_track": 90.0,
            "vertical_rate": 0.0,
            "on_ground": False,
            "squawk": "4211",
        },
        {
            "icao24": icao24,
            "callsign": callsign,
            "timestamp": start_time + 30,  # 30 seconds later
            "latitude": 28.5,              # Zero displacement
            "longitude": 77.1,
            "baro_altitude": 6096.0,
            "velocity": 0.0,
            "true_track": 90.0,
            "vertical_rate": 0.0,
            "on_ground": False,
            "squawk": "4211",
        },
    ]
    return points
