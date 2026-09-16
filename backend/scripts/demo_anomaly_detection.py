"""Interactive demonstration of the Anomaly Detection subsystem and Anomaly Agent."""

from __future__ import annotations

import json
from app.agents.anomaly_agent import AnomalyAgent
from app.anomaly.detector import TrajectoryAnomalyDetector
from app.anomaly.replay import (
    TrajectoryReplayer,
    create_synthetic_cruise,
    create_synthetic_heading_change,
    create_synthetic_holding_pattern,
    create_synthetic_rapid_descent,
    create_synthetic_stationary_airborne,
)


def main():
    detector = TrajectoryAnomalyDetector()
    replayer = TrajectoryReplayer(detector=detector)
    agent = AnomalyAgent()

    print("=" * 80)
    print("AIRSPACE INTELLIGENCE — ANOMALY DETECTION & ANOMALY AGENT SHOWCASE")
    print("=" * 80)

    # Scenario 1: Nominal Cruise
    print("\n[Scenario 1: Nominal Cruise Flight]")
    cruise_traj = create_synthetic_cruise(steps=6)
    anomalies_1 = replayer.replay_trajectory(cruise_traj)
    print(f"Traversed {len(cruise_traj)} points. Detected anomalies: {len(anomalies_1)} (Classification: NORMAL)")

    # Scenario 2: Rapid Descent
    print("\n" + "-" * 80)
    print("[Scenario 2: Rapid Descent at High Altitude]")
    descent_traj = create_synthetic_rapid_descent()
    anomalies_2 = replayer.replay_trajectory(descent_traj)
    print(f"Traversed {len(descent_traj)} points. Detected anomalies: {len(anomalies_2)}")
    if anomalies_2:
        anom = anomalies_2[0]
        print(f"  • Type: {anom.anomaly_type.value}")
        print(f"  • Severity: {anom.severity.value} (Confidence: {anom.confidence:.0%})")
        print(f"  • Observed: {anom.observed_values}")
        print(f"  • Baseline: {anom.baseline_values}")
        print("\n[Anomaly Agent Investigation]:")
        exp = agent.explain_anomaly(anom)
        print(f"  Summary: {exp.summary}")
        print(f"  Emergency Declared: {exp.is_emergency_declared}")
        print(f"  Missing Factors: {exp.missing_context_factors}")
        print(f"  Objective Explanation:\n  \"{exp.objective_explanation}\"")

    # Scenario 3: Unexpected 90-Degree Heading Change
    print("\n" + "-" * 80)
    print("[Scenario 3: Unexpected Heading Change at Cruise Altitude]")
    heading_traj = create_synthetic_heading_change()
    anomalies_3 = replayer.replay_trajectory(heading_traj)
    print(f"Traversed {len(heading_traj)} points. Detected anomalies: {len(anomalies_3)}")
    if anomalies_3:
        anom = anomalies_3[0]
        print(f"  • Type: {anom.anomaly_type.value} ({anom.severity.value})")
        print(f"  • Observed: {anom.observed_values}")
        print("\n[Anomaly Agent Investigation]:")
        exp = agent.explain_anomaly(anom)
        print(f"  Objective Explanation:\n  \"{exp.objective_explanation}\"")

    # Scenario 4: Holding Pattern Orbit
    print("\n" + "-" * 80)
    print("[Scenario 4: Holding Pattern Closed-Loop Orbit]")
    holding_traj = create_synthetic_holding_pattern()
    anomalies_4 = replayer.replay_trajectory(holding_traj)
    print(f"Traversed {len(holding_traj)} points. Detected anomalies: {len(anomalies_4)}")
    if anomalies_4:
        anom = anomalies_4[0]
        print(f"  • Type: {anom.anomaly_type.value} ({anom.severity.value})")
        print(f"  • Observed: {anom.observed_values}")
        print("\n[Anomaly Agent Investigation]:")
        exp = agent.explain_anomaly(anom)
        print(f"  Objective Explanation:\n  \"{exp.objective_explanation}\"")

    # Scenario 5: Stationary Airborne Position
    print("\n" + "-" * 80)
    print("[Scenario 5: Stationary Airborne Position (0 Knots at 20,000 ft)]")
    stationary_traj = create_synthetic_stationary_airborne()
    anomalies_5 = replayer.replay_trajectory(stationary_traj)
    print(f"Traversed {len(stationary_traj)} points. Detected anomalies: {len(anomalies_5)}")
    if anomalies_5:
        anom = anomalies_5[0]
        print(f"  • Type: {anom.anomaly_type.value} ({anom.severity.value})")
        print(f"  • Observed: {anom.observed_values}")
        print("\n[Anomaly Agent Investigation]:")
        exp = agent.explain_anomaly(anom)
        print(f"  Objective Explanation:\n  \"{exp.objective_explanation}\"")

    print("\n" + "=" * 80)
    print("[✓] Anomaly Detection & Anomaly Agent demonstration complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
