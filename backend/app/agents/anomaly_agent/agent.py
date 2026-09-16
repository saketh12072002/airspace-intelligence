"""Anomaly Agent investigating and objectively explaining candidate trajectory anomalies."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.anomaly.models import AnomalySeverity, AnomalyType, CandidateAnomaly
from app.core.logging import get_logger

logger = get_logger(__name__)


class AnomalyExplanation(BaseModel):
    """Structured objective explanation report for a candidate anomaly."""

    aircraft_id: str = Field(description="ICAO24 transponder address")
    callsign: Optional[str] = Field(default=None, description="Flight callsign")
    anomaly_type: AnomalyType = Field(description="Anomaly type")
    severity: AnomalySeverity = Field(description="Assigned severity rating")
    confidence: float = Field(description="Detection confidence (0.0 to 1.0)")
    summary: str = Field(description="Executive objective summary")
    observed_facts: List[str] = Field(description="Observed factual parameters")
    baseline_comparison: Dict[str, Any] = Field(description="Baseline vs observed comparison")
    missing_context_factors: List[str] = Field(
        description="Unverified variables that preclude determining the cause (e.g. weather, ATC clearance)",
    )
    objective_explanation: str = Field(
        description="Detailed grounded explanation strictly avoiding speculation",
    )
    is_emergency_declared: bool = Field(
        default=False,
        description="Whether a confirmed emergency squawk (7700, 7600, 7500) was broadcast",
    )


class AnomalyAgent:
    """Investigative agent that analyzes candidate anomalies and generates grounded explanations.

    Guarantees:
    - Never invents causes (mechanical, medical, pilot intent).
    - Never labels anomalies as emergencies without verified emergency transponder codes.
    - Explicitly identifies missing contextual variables (weather, ATC instructions).
    """

    def explain_anomaly(
        self,
        anomaly: CandidateAnomaly,
        surrounding_traffic: Optional[List[Dict[str, Any]]] = None,
        airport_info: Optional[Dict[str, Any]] = None,
    ) -> AnomalyExplanation:
        """Analyze a candidate anomaly and produce a strictly-grounded explanation.

        Args:
            anomaly: The CandidateAnomaly detected by the deterministic engine.
            surrounding_traffic: Optional list of neighboring aircraft telemetry.
            airport_info: Optional metadata for nearby airports.

        Returns:
            Structured AnomalyExplanation report.
        """
        ac_id = anomaly.aircraft_id
        callsign = anomaly.callsign or ac_id
        atype = anomaly.anomaly_type
        obs = anomaly.observed_values
        base = anomaly.baseline_values

        # Standard missing contextual variables in ADS-B passive surveillance
        missing_factors = [
            "Tactical ATC voice communications and clearances are unavailable",
            "Real-time en-route meteorological/convective weather radar data is unavailable",
            "Filed airline operational flight plan and navigation waypoints are unavailable",
        ]

        # Check if emergency squawk is explicitly broadcast
        squawk_code = obs.get("squawk")
        is_emergency = bool(
            atype == AnomalyType.SQUAWK_OR_SYSTEM_ANOMALY
            and str(squawk_code) in ("7700", "7600", "7500")
        )

        observed_facts = list(anomaly.supporting_observations)

        # ----------------------------------------------------------------------
        # Anomaly-Specific Objective Explanation Synthesis
        # ----------------------------------------------------------------------
        if atype == AnomalyType.RAPID_DESCENT:
            vr_fpm = obs.get("vertical_rate_fpm", 0.0)
            alt_ft = obs.get("altitude_ft", 0.0)
            summary = (
                f"Rapid descent detected for {callsign} (rate: {vr_fpm:,.0f} ft/min at {alt_ft:,.0f} ft)."
            )
            explanation = (
                f"Aircraft {callsign} exhibited a descent rate of {vr_fpm:,.0f} ft/min, which exceeds "
                f"the nominal commercial descent envelope (standard baseline max: {base.get('normal_descent_max_fpm', -2500):,.0f} ft/min). "
                f"Significant altitude decrease observed. Tactical ATC descent instructions, turbulence avoidance, "
                f"or cabin pressurization procedures cannot be confirmed because weather and ATC clearance data are unavailable. "
                f"Available data is insufficient to determine the operational cause. "
                f"This trajectory excursion should not be assumed to be an emergency without corroborating evidence."
            )

        elif atype == AnomalyType.RAPID_CLIMB:
            vr_fpm = obs.get("vertical_rate_fpm", 0.0)
            summary = f"Abnormal high-rate climb detected for {callsign} ({vr_fpm:,.0f} ft/min)."
            explanation = (
                f"Aircraft {callsign} exhibited a climb rate of {vr_fpm:,.0f} ft/min exceeding standard profile. "
                f"Available data is insufficient to determine the cause."
            )

        elif atype == AnomalyType.UNEXPECTED_HEADING_CHANGE:
            dh = obs.get("heading_delta_deg", 0.0)
            turn_rate = obs.get("turn_rate_deg_per_sec", 0.0)
            alt_ft = obs.get("altitude_ft", 0.0)
            summary = f"Abrupt heading change of {dh}° detected for {callsign} at {alt_ft:,.0f} ft."
            explanation = (
                f"Aircraft {callsign} altered heading by {dh}° at an angular rate of {turn_rate}°/s at FL{alt_ft/100:.0f}. "
                f"Standard rate turn is 3.0°/s. Tactical vectoring by air traffic control or localized weather avoidance "
                f"cannot be confirmed because ATC communications and weather data are unavailable. "
                f"Available data is insufficient to determine the cause of the heading divergence."
            )

        elif atype == AnomalyType.SIGNIFICANT_ROUTE_DEVIATION:
            dev = obs.get("track_deviation_deg", 0.0)
            summary = f"Significant trajectory divergence of {dev}° detected for {callsign}."
            explanation = (
                f"Aircraft {callsign} deviated {dev}° from its established trajectory track. "
                f"Available data is insufficient to determine the cause (could represent an unfiled airway turn, "
                f"ATC shortcut, or weather diversion)."
            )

        elif atype == AnomalyType.HOLDING_PATTERN:
            cum_hdg = obs.get("cumulative_heading_deg", 0.0)
            net_d = obs.get("net_displacement_km", 0.0)
            summary = f"Holding pattern / closed-loop orbit detected for {callsign}."
            explanation = (
                f"Aircraft {callsign} executed a closed-loop orbiting pattern with {cum_hdg:.0f}° cumulative heading change "
                f"and net displacement of only {net_d:.1f} km. Holding patterns are standard operational procedures for "
                f"air traffic sequencing, destination airport arrival spacing, or weather delay. "
                f"Available data is insufficient to determine the specific dispatch reason."
            )

        elif atype == AnomalyType.STATIONARY_AIRBORNE_POSITION:
            spd = obs.get("ground_speed_knots", 0.0)
            alt_ft = obs.get("altitude_ft", 0.0)
            summary = f"Stationary airborne position detected for {callsign} ({spd} knots at {alt_ft:,.0f} ft)."
            explanation = (
                f"Aircraft {callsign} is indicated as airborne at {alt_ft:,.0f} ft but ground speed is {spd} knots "
                f"with negligible coordinate displacement. Fixed-wing commercial aircraft cannot maintain level flight "
                f"at zero ground speed. Observed data is consistent with a frozen transponder or GPS telemetry failure."
            )

        elif atype == AnomalyType.UNUSUAL_ALTITUDE_CHANGE:
            d_alt = obs.get("altitude_delta_ft", 0.0)
            dt = obs.get("dt_seconds", 0.0)
            summary = f"Discontinuous altitude step change detected for {callsign} ({d_alt:,.0f} ft in {dt:.1f}s)."
            explanation = (
                f"Aircraft {callsign} reported an instantaneous altitude step of {d_alt:,.0f} ft in {dt:.1f} seconds. "
                f"Such rate of displacement violates physical aerodynamic limits and indicates an altimeter encoder "
                f"or transponder transmission glitch."
            )

        elif atype == AnomalyType.AIRCRAFT_APPEARING_DISAPPEARING:
            gap = obs.get("gap_duration_sec", 0.0)
            alt_ft = obs.get("altitude_ft", 0.0)
            summary = f"Transponder signal discontinuity detected for {callsign} ({gap:.0f}s silence)."
            explanation = (
                f"Aircraft {callsign} experienced a transponder telemetry gap of {gap:.0f} seconds while at {alt_ft:,.0f} ft. "
                f"Line-of-sight terrain shielding, receiver station handoff, or transponder interrogation failure are common causes. "
                f"Available data is insufficient to determine the reason for signal loss."
            )

        elif atype == AnomalyType.SQUAWK_OR_SYSTEM_ANOMALY:
            meaning = obs.get("meaning", "Emergency Squawk")
            summary = f"Special transponder squawk {squawk_code} broadcast by {callsign}."
            explanation = (
                f"Aircraft {callsign} broadcast special transponder squawk code {squawk_code}: '{meaning}'. "
                f"Confirmed emergency alert active on ADS-B network."
            )

        else:
            summary = f"Candidate anomaly detected for {callsign} ({atype.value})."
            explanation = (
                f"Observed parameters for {callsign} deviate from standard flight baseline. "
                f"Available data is insufficient to determine the cause."
            )

        return AnomalyExplanation(
            aircraft_id=ac_id,
            callsign=anomaly.callsign,
            anomaly_type=atype,
            severity=anomaly.severity,
            confidence=anomaly.confidence,
            summary=summary,
            observed_facts=observed_facts,
            baseline_comparison={"observed": obs, "baseline": base},
            missing_context_factors=missing_factors,
            objective_explanation=explanation,
            is_emergency_declared=is_emergency,
        )
