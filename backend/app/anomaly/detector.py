"""Deterministic and statistical trajectory anomaly detector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.anomaly.features import (
    compute_heading_delta,
    compute_trajectory_orbit_ratio,
    extract_features,
)
from app.anomaly.models import (
    AnomalySeverity,
    AnomalyType,
    CandidateAnomaly,
    TelemetryFeatureVector,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# Standard emergency squawk codes
EMERGENCY_SQUAWKS = {
    "7700": "General In-Flight Emergency",
    "7600": "Radio Communication Failure / Lost Comm",
    "7500": "Unlawful Interference / Hijacking",
}


class TrajectoryAnomalyDetector:
    """Deterministic and statistical rule engine evaluating aircraft telemetry against standard flight envelopes.

    Operates without LLM dependencies to ensure 100% deterministic, high-speed,
    and verifiable candidate anomaly generation.
    """

    def __init__(
        self,
        rapid_descent_threshold_fpm: float = -4000.0,
        severe_descent_threshold_fpm: float = -6000.0,
        rapid_climb_threshold_fpm: float = 4500.0,
        turn_rate_threshold_deg_s: float = 4.0,
        high_altitude_threshold_ft: float = 12000.0,
        telemetry_gap_threshold_sec: float = 60.0,
    ) -> None:
        self.rapid_descent_fpm = rapid_descent_threshold_fpm
        self.severe_descent_fpm = severe_descent_threshold_fpm
        self.rapid_climb_fpm = rapid_climb_threshold_fpm
        self.turn_rate_deg_s = turn_rate_threshold_deg_s
        self.high_altitude_ft = high_altitude_threshold_ft
        self.telemetry_gap_sec = telemetry_gap_threshold_sec

    def detect_anomalies(
        self,
        curr_point: Dict[str, Any],
        prev_point: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[CandidateAnomaly]:
        """Analyze a telemetry observation and optional history window for candidate anomalies.

        Returns:
            List of detected CandidateAnomaly objects (empty if flight behavior is NORMAL).
        """
        anomalies: List[CandidateAnomaly] = []
        aircraft_id = str(curr_point.get("icao24", "unknown")).lower()
        callsign = curr_point.get("callsign")

        # ----------------------------------------------------------------------
        # Check 1: Emergency Squawk Codes (SQUAWK_OR_SYSTEM_ANOMALY)
        # ----------------------------------------------------------------------
        squawk = str(curr_point.get("squawk", "")).strip()
        if squawk in EMERGENCY_SQUAWKS:
            desc = EMERGENCY_SQUAWKS[squawk]
            anomalies.append(
                CandidateAnomaly(
                    aircraft_id=aircraft_id,
                    callsign=callsign,
                    anomaly_type=AnomalyType.SQUAWK_OR_SYSTEM_ANOMALY,
                    severity=AnomalySeverity.HIGH_CONFIDENCE_ANOMALY,
                    observed_values={"squawk": squawk, "meaning": desc},
                    baseline_values={"standard_squawk": "Assigned ATC code (e.g. 1000-7477)"},
                    confidence=1.0,
                    supporting_observations=[f"Transponder broadcast emergency squawk {squawk} ({desc})."],
                )
            )

        # If we have no previous point to compare against, only single-point checks apply
        if not prev_point:
            return anomalies

        # Extract kinematics over (prev_point, curr_point)
        feats: TelemetryFeatureVector = extract_features(prev_point, curr_point)

        # If aircraft is confirmed on the ground at low speed, nominal ground operations apply
        if feats.on_ground and feats.altitude_ft < 1500.0:
            return anomalies

        # ----------------------------------------------------------------------
        # Check 2: Rapid Descent (RAPID_DESCENT)
        # ----------------------------------------------------------------------
        if feats.vertical_rate_fpm <= self.rapid_descent_fpm and feats.altitude_ft > 5000.0:
            is_severe = feats.vertical_rate_fpm <= self.severe_descent_fpm
            sev = AnomalySeverity.HIGH_CONFIDENCE_ANOMALY if is_severe else AnomalySeverity.SUSPICIOUS
            conf = 0.95 if is_severe else 0.85

            anomalies.append(
                CandidateAnomaly(
                    aircraft_id=aircraft_id,
                    callsign=callsign,
                    anomaly_type=AnomalyType.RAPID_DESCENT,
                    severity=sev,
                    observed_values={
                        "vertical_rate_fpm": feats.vertical_rate_fpm,
                        "altitude_ft": feats.altitude_ft,
                        "altitude_loss_ft": feats.altitude_delta_ft,
                    },
                    baseline_values={"normal_descent_max_fpm": -2500.0},
                    confidence=conf,
                    supporting_observations=[
                        f"Descent rate of {feats.vertical_rate_fpm:,.0f} ft/min exceeds normal limits.",
                        f"Altitude dropped by {abs(feats.altitude_delta_ft):,.0f} ft in {feats.dt_seconds:.1f} seconds.",
                    ],
                )
            )

        # ----------------------------------------------------------------------
        # Check 3: Rapid Climb (RAPID_CLIMB)
        # ----------------------------------------------------------------------
        if feats.vertical_rate_fpm >= self.rapid_climb_fpm and feats.altitude_ft > 8000.0:
            is_extreme = feats.vertical_rate_fpm >= 6500.0
            sev = AnomalySeverity.HIGH_CONFIDENCE_ANOMALY if is_extreme else AnomalySeverity.SUSPICIOUS
            conf = 0.90 if is_extreme else 0.75

            anomalies.append(
                CandidateAnomaly(
                    aircraft_id=aircraft_id,
                    callsign=callsign,
                    anomaly_type=AnomalyType.RAPID_CLIMB,
                    severity=sev,
                    observed_values={
                        "vertical_rate_fpm": feats.vertical_rate_fpm,
                        "altitude_ft": feats.altitude_ft,
                    },
                    baseline_values={"normal_climb_max_fpm": 3500.0},
                    confidence=conf,
                    supporting_observations=[
                        f"Climb rate of {feats.vertical_rate_fpm:,.0f} ft/min substantially exceeds standard profile.",
                    ],
                )
            )

        # ----------------------------------------------------------------------
        # Check 4: Unusual Altitude Step Change (UNUSUAL_ALTITUDE_CHANGE)
        # ----------------------------------------------------------------------
        # E.g. Altitude jumps by > 3000 ft in <= 5 seconds (sensor / transponder glitch)
        if feats.dt_seconds <= 10.0 and abs(feats.altitude_delta_ft) > 3000.0:
            anomalies.append(
                CandidateAnomaly(
                    aircraft_id=aircraft_id,
                    callsign=callsign,
                    anomaly_type=AnomalyType.UNUSUAL_ALTITUDE_CHANGE,
                    severity=AnomalySeverity.HIGH_CONFIDENCE_ANOMALY,
                    observed_values={
                        "altitude_delta_ft": feats.altitude_delta_ft,
                        "dt_seconds": feats.dt_seconds,
                    },
                    baseline_values={"max_physical_rate_ft_in_10s": 1500.0},
                    confidence=0.92,
                    supporting_observations=[
                        f"Discontinuous altitude shift of {feats.altitude_delta_ft:,.0f} ft in {feats.dt_seconds:.1f}s violates physical envelope (likely transponder/sensor error).",
                    ],
                )
            )

        # ----------------------------------------------------------------------
        # Check 5: Unexpected Heading Change (UNEXPECTED_HEADING_CHANGE)
        # ----------------------------------------------------------------------
        if feats.altitude_ft > self.high_altitude_ft and not feats.on_ground:
            if feats.turn_rate_deg_per_sec >= self.turn_rate_deg_s or (
                feats.dt_seconds <= 15.0 and abs(feats.heading_delta_deg) >= 45.0
            ):
                is_extreme = abs(feats.heading_delta_deg) >= 60.0 or feats.turn_rate_deg_per_sec >= 6.0
                sev = AnomalySeverity.HIGH_CONFIDENCE_ANOMALY if is_extreme else AnomalySeverity.SUSPICIOUS
                conf = 0.90 if is_extreme else 0.80

                anomalies.append(
                    CandidateAnomaly(
                        aircraft_id=aircraft_id,
                        callsign=callsign,
                        anomaly_type=AnomalyType.UNEXPECTED_HEADING_CHANGE,
                        severity=sev,
                        observed_values={
                            "turn_rate_deg_per_sec": feats.turn_rate_deg_per_sec,
                            "heading_delta_deg": feats.heading_delta_deg,
                            "altitude_ft": feats.altitude_ft,
                        },
                        baseline_values={"standard_rate_turn_max_deg_s": 3.0},
                        confidence=conf,
                        supporting_observations=[
                            f"Abrupt heading change of {feats.heading_delta_deg}° at turn rate {feats.turn_rate_deg_per_sec}°/s at FL{feats.altitude_ft/100:.0f}.",
                        ],
                    )
                )

        # ----------------------------------------------------------------------
        # Check 6: Extended Stationary Airborne Position (STATIONARY_AIRBORNE_POSITION)
        # ----------------------------------------------------------------------
        if not feats.on_ground and feats.altitude_ft > 1500.0:
            if feats.ground_speed_knots <= 15.0 and feats.distance_moved_km <= 0.05 and feats.dt_seconds >= 20.0:
                anomalies.append(
                    CandidateAnomaly(
                        aircraft_id=aircraft_id,
                        callsign=callsign,
                        anomaly_type=AnomalyType.STATIONARY_AIRBORNE_POSITION,
                        severity=AnomalySeverity.HIGH_CONFIDENCE_ANOMALY,
                        observed_values={
                            "ground_speed_knots": feats.ground_speed_knots,
                            "altitude_ft": feats.altitude_ft,
                            "distance_moved_km": feats.distance_moved_km,
                            "dt_seconds": feats.dt_seconds,
                        },
                        baseline_values={"minimum_airborne_speed_knots": 80.0},
                        confidence=0.95,
                        supporting_observations=[
                            f"Aircraft is airborne at {feats.altitude_ft:,.0f} ft but ground speed is {feats.ground_speed_knots} knots with near-zero displacement (indicates frozen GPS/transponder).",
                        ],
                    )
                )

        # ----------------------------------------------------------------------
        # Check 7: Unusual Speed / Deceleration Change (UNUSUAL_SPEED_CHANGE)
        # ----------------------------------------------------------------------
        # Abrupt deceleration > 12 knots/sec or dangerously low speed at high altitude (stall regime)
        if feats.altitude_ft > 20000.0 and not feats.on_ground:
            if feats.ground_speed_knots < 110.0 and feats.ground_speed_knots > 15.0:
                anomalies.append(
                    CandidateAnomaly(
                        aircraft_id=aircraft_id,
                        callsign=callsign,
                        anomaly_type=AnomalyType.UNUSUAL_SPEED_CHANGE,
                        severity=AnomalySeverity.HIGH_CONFIDENCE_ANOMALY,
                        observed_values={
                            "ground_speed_knots": feats.ground_speed_knots,
                            "altitude_ft": feats.altitude_ft,
                        },
                        baseline_values={"min_cruise_speed_knots": 200.0},
                        confidence=0.88,
                        supporting_observations=[
                            f"Ground speed of {feats.ground_speed_knots:.0f} knots at {feats.altitude_ft:,.0f} ft is below normal cruise regime (potential aerodynamic stall hazard).",
                        ],
                    )
                )
            elif abs(feats.accel_knots_per_sec) > 15.0:
                anomalies.append(
                    CandidateAnomaly(
                        aircraft_id=aircraft_id,
                        callsign=callsign,
                        anomaly_type=AnomalyType.UNUSUAL_SPEED_CHANGE,
                        severity=AnomalySeverity.SUSPICIOUS,
                        observed_values={"acceleration_knots_per_sec": feats.accel_knots_per_sec},
                        baseline_values={"normal_accel_max_knots_s": 5.0},
                        confidence=0.80,
                        supporting_observations=[
                            f"Severe speed change rate of {feats.accel_knots_per_sec:.1f} kts/s.",
                        ],
                    )
                )

        # ----------------------------------------------------------------------
        # Check 8: Telemetry Silence / Signal Gap (AIRCRAFT_APPEARING_DISAPPEARING)
        # ----------------------------------------------------------------------
        if feats.dt_seconds >= self.telemetry_gap_sec and feats.altitude_ft > 8000.0:
            anomalies.append(
                CandidateAnomaly(
                    aircraft_id=aircraft_id,
                    callsign=callsign,
                    anomaly_type=AnomalyType.AIRCRAFT_APPEARING_DISAPPEARING,
                    severity=AnomalySeverity.SUSPICIOUS,
                    observed_values={
                        "gap_duration_sec": feats.dt_seconds,
                        "altitude_ft": feats.altitude_ft,
                    },
                    baseline_values={"expected_interval_sec": 10.0},
                    confidence=0.80,
                    supporting_observations=[
                        f"Transponder signal gap of {feats.dt_seconds:.0f}s while operating at {feats.altitude_ft:,.0f} ft.",
                    ],
                )
            )

        # ----------------------------------------------------------------------
        # Checks 9 & 10: Multi-Point History Window (Holding Pattern & Route Deviation)
        # ----------------------------------------------------------------------
        if history and len(history) >= 5:
            # 9. Holding Pattern Detection
            tot_heading, net_dist, tot_path = compute_trajectory_orbit_ratio(history)
            if tot_heading >= 360.0 and tot_path >= 15.0 and (net_dist / max(tot_path, 1.0)) <= 0.35:
                anomalies.append(
                    CandidateAnomaly(
                        aircraft_id=aircraft_id,
                        callsign=callsign,
                        anomaly_type=AnomalyType.HOLDING_PATTERN,
                        severity=AnomalySeverity.SUSPICIOUS,
                        observed_values={
                            "cumulative_heading_deg": tot_heading,
                            "net_displacement_km": net_dist,
                            "total_path_km": tot_path,
                            "orbit_ratio": round(net_dist / tot_path, 2),
                        },
                        baseline_values={"linear_flight_orbit_ratio": "> 0.80"},
                        confidence=0.90,
                        supporting_observations=[
                            f"Trajectory exhibits closed-loop orbiting with {tot_heading:.0f}° cumulative heading change and net displacement of only {net_dist:.1f} km over {tot_path:.1f} km path.",
                        ],
                    )
                )

            # 10. Significant Route Deviation
            # Compare current track against median track of earlier history
            past_tracks = [p.get("true_track") for p in history[:-1] if p.get("true_track") is not None]
            if len(past_tracks) >= 4 and feats.altitude_ft > self.high_altitude_ft:
                avg_past_track = sum(past_tracks) / len(past_tracks)
                dev_angle = abs(compute_heading_delta(avg_past_track, curr_point.get("true_track")))
                if dev_angle >= 35.0:
                    anomalies.append(
                        CandidateAnomaly(
                            aircraft_id=aircraft_id,
                            callsign=callsign,
                            anomaly_type=AnomalyType.SIGNIFICANT_ROUTE_DEVIATION,
                            severity=AnomalySeverity.SUSPICIOUS,
                            observed_values={
                                "current_track_deg": curr_point.get("true_track"),
                                "baseline_avg_track_deg": round(avg_past_track, 1),
                                "track_deviation_deg": round(dev_angle, 1),
                            },
                            baseline_values={"standard_airway_divergence_deg": "< 15.0"},
                            confidence=0.82,
                            supporting_observations=[
                                f"Sustained heading deviation of {dev_angle:.1f}° from established trajectory baseline ({avg_past_track:.1f}°).",
                            ],
                        )
                    )

        return anomalies
