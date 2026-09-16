"""Comprehensive tests for the Anomaly Detection subsystem and Anomaly Agent."""

from __future__ import annotations

import pytest

from app.agents.anomaly_agent import AnomalyAgent
from app.anomaly.detector import TrajectoryAnomalyDetector
from app.anomaly.models import AnomalySeverity, AnomalyType
from app.anomaly.replay import (
    TrajectoryReplayer,
    create_synthetic_cruise,
    create_synthetic_heading_change,
    create_synthetic_holding_pattern,
    create_synthetic_rapid_descent,
    create_synthetic_stationary_airborne,
)


@pytest.fixture
def detector():
    return TrajectoryAnomalyDetector()


@pytest.fixture
def replayer(detector):
    return TrajectoryReplayer(detector=detector)


@pytest.fixture
def anomaly_agent():
    return AnomalyAgent()


# ==============================================================================
# 1. Nominal Normal Flight Test
# ==============================================================================

def test_nominal_cruise_produces_no_anomalies(replayer):
    """A standard cruise trajectory must be evaluated as completely NORMAL."""
    normal_trajectory = create_synthetic_cruise(steps=8)
    anomalies = replayer.replay_trajectory(normal_trajectory)
    assert len(anomalies) == 0


# ==============================================================================
# 2. Rapid Descent Anomaly Test
# ==============================================================================

def test_rapid_descent_detection(replayer):
    """An emergency-rate descent (-7,000 ft/min) must be flagged as HIGH_CONFIDENCE_ANOMALY."""
    rapid_descent_traj = create_synthetic_rapid_descent()
    anomalies = replayer.replay_trajectory(rapid_descent_traj)

    descent_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.RAPID_DESCENT]
    assert len(descent_anomalies) >= 1

    first = descent_anomalies[0]
    assert first.severity == AnomalySeverity.HIGH_CONFIDENCE_ANOMALY
    assert first.confidence >= 0.90
    assert first.observed_values["vertical_rate_fpm"] <= -6000.0


# ==============================================================================
# 3. Unexpected Heading Change Test
# ==============================================================================

def test_unexpected_heading_change_detection(replayer):
    """An abrupt 90° heading shift at FL350 must trigger UNEXPECTED_HEADING_CHANGE."""
    heading_traj = create_synthetic_heading_change()
    anomalies = replayer.replay_trajectory(heading_traj)

    hdg_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.UNEXPECTED_HEADING_CHANGE]
    assert len(hdg_anomalies) >= 1

    first = hdg_anomalies[0]
    assert first.severity in {AnomalySeverity.HIGH_CONFIDENCE_ANOMALY, AnomalySeverity.SUSPICIOUS}
    assert abs(first.observed_values["heading_delta_deg"]) >= 45.0
    assert first.observed_values["turn_rate_deg_per_sec"] >= 4.0


# ==============================================================================
# 4. Holding Pattern Detection Test
# ==============================================================================

def test_holding_pattern_detection(replayer):
    """A 360-degree orbiting trajectory must trigger HOLDING_PATTERN as SUSPICIOUS."""
    holding_traj = create_synthetic_holding_pattern()
    anomalies = replayer.replay_trajectory(holding_traj)

    hold_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.HOLDING_PATTERN]
    assert len(hold_anomalies) >= 1

    first = hold_anomalies[0]
    # Holding is an operational condition, NOT labeled an emergency
    assert first.severity == AnomalySeverity.SUSPICIOUS
    assert first.observed_values["cumulative_heading_deg"] >= 360.0
    assert first.observed_values["orbit_ratio"] <= 0.35


# ==============================================================================
# 5. Stationary Airborne Position Test
# ==============================================================================

def test_stationary_airborne_position(replayer):
    """0 knots ground speed at 20,000 ft must trigger STATIONARY_AIRBORNE_POSITION."""
    freeze_traj = create_synthetic_stationary_airborne()
    anomalies = replayer.replay_trajectory(freeze_traj)

    freeze_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.STATIONARY_AIRBORNE_POSITION]
    assert len(freeze_anomalies) >= 1

    first = freeze_anomalies[0]
    assert first.severity == AnomalySeverity.HIGH_CONFIDENCE_ANOMALY
    assert first.observed_values["ground_speed_knots"] <= 15.0
    assert first.confidence >= 0.90


# ==============================================================================
# 6. Altitude Step Discontinuity Test
# ==============================================================================

def test_unusual_altitude_step_change(detector):
    """An instantaneous 4,000 ft altitude jump in 5 seconds indicates sensor/transponder error."""
    p1 = {
        "icao24": "80167f",
        "timestamp": 1700000000,
        "latitude": 28.5,
        "longitude": 77.1,
        "baro_altitude": 6000.0,
        "velocity": 200.0,
        "true_track": 90.0,
        "on_ground": False,
    }
    p2 = {
        "icao24": "80167f",
        "timestamp": 1700000005,  # 5 seconds later
        "latitude": 28.51,
        "longitude": 77.12,
        "baro_altitude": 7500.0,  # +1500m ≈ +4,920 ft jump in 5s!
        "velocity": 200.0,
        "true_track": 90.0,
        "on_ground": False,
    }
    anomalies = detector.detect_anomalies(curr_point=p2, prev_point=p1)
    types = [a.anomaly_type for a in anomalies]
    assert AnomalyType.UNUSUAL_ALTITUDE_CHANGE in types


# ==============================================================================
# 7. Telemetry Disappearance / Gap Test
# ==============================================================================

def test_telemetry_gap_disappearance(detector):
    """A 90-second transponder gap at FL300 triggers AIRCRAFT_APPEARING_DISAPPEARING."""
    p1 = {
        "icao24": "80167f",
        "timestamp": 1700000000,
        "latitude": 28.5,
        "longitude": 77.1,
        "baro_altitude": 9144.0,  # 30,000 ft
        "velocity": 220.0,
        "true_track": 90.0,
        "on_ground": False,
    }
    p2 = {
        "icao24": "80167f",
        "timestamp": 1700000095,  # 95 seconds gap!
        "latitude": 28.5,
        "longitude": 77.5,
        "baro_altitude": 9144.0,
        "velocity": 220.0,
        "true_track": 90.0,
        "on_ground": False,
    }
    anomalies = detector.detect_anomalies(curr_point=p2, prev_point=p1)
    types = [a.anomaly_type for a in anomalies]
    assert AnomalyType.AIRCRAFT_APPEARING_DISAPPEARING in types


# ==============================================================================
# 8. Emergency Squawk Test
# ==============================================================================

def test_emergency_squawk_detection(detector):
    """Squawk 7700 must trigger SQUAWK_OR_SYSTEM_ANOMALY with HIGH_CONFIDENCE_ANOMALY."""
    p = {
        "icao24": "80167f",
        "callsign": "AIC911",
        "timestamp": 1700000000,
        "latitude": 28.5,
        "longitude": 77.1,
        "baro_altitude": 6000.0,
        "velocity": 200.0,
        "true_track": 90.0,
        "on_ground": False,
        "squawk": "7700",
    }
    anomalies = detector.detect_anomalies(curr_point=p)
    assert len(anomalies) >= 1
    assert anomalies[0].anomaly_type == AnomalyType.SQUAWK_OR_SYSTEM_ANOMALY
    assert anomalies[0].severity == AnomalySeverity.HIGH_CONFIDENCE_ANOMALY


# ==============================================================================
# 9. Anomaly Agent Explanation & Zero Hallucination Tests
# ==============================================================================

def test_anomaly_agent_does_not_assert_emergency_for_rapid_descent(replayer, anomaly_agent):
    """The agent must explain rapid descent objectively without claiming an emergency or inventing causes."""
    rapid_descent_traj = create_synthetic_rapid_descent()
    anomalies = replayer.replay_trajectory(rapid_descent_traj)
    descent_anomaly = next(a for a in anomalies if a.anomaly_type == AnomalyType.RAPID_DESCENT)

    explanation = anomaly_agent.explain_anomaly(descent_anomaly)

    # Must NOT claim a confirmed emergency when no squawk 7700 is present
    assert explanation.is_emergency_declared is False
    assert "The aircraft is experiencing an emergency" not in explanation.objective_explanation

    # Must explicitly state that data is insufficient to determine the cause
    assert "insufficient to determine" in explanation.objective_explanation.lower()

    # Must state missing context (weather, ATC instructions)
    assert any("weather" in f.lower() for f in explanation.missing_context_factors)
    assert any("atc" in f.lower() for f in explanation.missing_context_factors)


def test_anomaly_agent_heading_change_explanation(replayer, anomaly_agent):
    """The agent must explain heading divergence without speculating on pilot or mechanical intent."""
    heading_traj = create_synthetic_heading_change()
    anomalies = replayer.replay_trajectory(heading_traj)
    hdg_anomaly = next(a for a in anomalies if a.anomaly_type == AnomalyType.UNEXPECTED_HEADING_CHANGE)

    explanation = anomaly_agent.explain_anomaly(hdg_anomaly)

    assert "heading" in explanation.summary.lower()
    assert "insufficient to determine the cause" in explanation.objective_explanation.lower()
    assert explanation.is_emergency_declared is False


def test_anomaly_agent_holding_pattern_explanation(replayer, anomaly_agent):
    """Holding pattern explanation must recognize operational sequencing vs emergency."""
    holding_traj = create_synthetic_holding_pattern()
    anomalies = replayer.replay_trajectory(holding_traj)
    hold_anomaly = next(a for a in anomalies if a.anomaly_type == AnomalyType.HOLDING_PATTERN)

    explanation = anomaly_agent.explain_anomaly(hold_anomaly)

    assert explanation.severity == AnomalySeverity.SUSPICIOUS
    assert "holding" in explanation.summary.lower()
    assert "operational" in explanation.objective_explanation.lower()
    assert explanation.is_emergency_declared is False
