"""Feature extraction module computing kinematic differentials and flight dynamics metrics."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from app.anomaly.models import TelemetryFeatureVector

# Conversion constants
METRES_TO_FEET = 3.28084
MS_TO_KNOTS = 1.94384
MS_TO_FPM = 196.8504  # Metres/second to feet/minute


def compute_heading_delta(track1: Optional[float], track2: Optional[float]) -> float:
    """Compute the shortest angular difference in degrees (-180 to +180) between two tracks."""
    if track1 is None or track2 is None:
        return 0.0
    diff = (track2 - track1 + 180.0) % 360.0 - 180.0
    return diff


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in kilometres between two coordinates."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def extract_features(
    prev_point: Dict[str, Any],
    curr_point: Dict[str, Any],
) -> TelemetryFeatureVector:
    """Compute differential kinematic features between two consecutive telemetry points.

    Args:
        prev_point: Earlier observation dictionary containing timestamp, lat, lon, alt, vel, etc.
        curr_point: Later observation dictionary.

    Returns:
        TelemetryFeatureVector with calibrated kinematic metrics.
    """
    t1 = prev_point.get("timestamp", 0)
    t2 = curr_point.get("timestamp", 0)
    dt = max(float(t2 - t1), 0.1)  # Guard against division by zero

    # Heading and turn rate
    track1 = prev_point.get("true_track")
    track2 = curr_point.get("true_track")
    heading_delta = compute_heading_delta(track1, track2)
    turn_rate = abs(heading_delta) / dt

    # Altitudes (convert metres to feet if provided in metres)
    alt1_m = prev_point.get("baro_altitude") or prev_point.get("altitude_m") or 0.0
    alt2_m = curr_point.get("baro_altitude") or curr_point.get("altitude_m") or 0.0
    alt1_ft = alt1_m * METRES_TO_FEET
    alt2_ft = alt2_m * METRES_TO_FEET
    alt_delta_ft = alt2_ft - alt1_ft

    # Vertical rate in ft/min
    vr2_ms = curr_point.get("vertical_rate") or curr_point.get("vertical_rate_ms")
    vr1_ms = prev_point.get("vertical_rate") or prev_point.get("vertical_rate_ms")

    if vr2_ms is not None:
        vr_fpm = vr2_ms * MS_TO_FPM
    else:
        vr_fpm = (alt_delta_ft / dt) * 60.0

    if vr1_ms is not None and vr2_ms is not None:
        vr_accel = ((vr2_ms - vr1_ms) * MS_TO_FPM) / dt
    else:
        vr_accel = 0.0

    # Velocity and acceleration
    v1_ms = prev_point.get("velocity") or prev_point.get("velocity_ms") or 0.0
    v2_ms = curr_point.get("velocity") or curr_point.get("velocity_ms") or 0.0
    spd1_kts = v1_ms * MS_TO_KNOTS
    spd2_kts = v2_ms * MS_TO_KNOTS
    accel_kts = (spd2_kts - spd1_kts) / dt

    # Distance moved
    lat1 = prev_point.get("latitude")
    lon1 = prev_point.get("longitude")
    lat2 = curr_point.get("latitude")
    lon2 = curr_point.get("longitude")

    if None not in (lat1, lon1, lat2, lon2):
        dist_km = haversine_km(lat1, lon1, lat2, lon2)
    else:
        dist_km = 0.0

    on_ground = bool(curr_point.get("on_ground", False))
    squawk = curr_point.get("squawk")

    return TelemetryFeatureVector(
        dt_seconds=dt,
        turn_rate_deg_per_sec=round(turn_rate, 2),
        heading_delta_deg=round(heading_delta, 1),
        vertical_rate_fpm=round(vr_fpm, 1),
        vertical_accel_fpm_per_sec=round(vr_accel, 2),
        ground_speed_knots=round(spd2_kts, 1),
        accel_knots_per_sec=round(accel_kts, 2),
        altitude_ft=round(alt2_ft, 1),
        altitude_delta_ft=round(alt_delta_ft, 1),
        distance_moved_km=round(dist_km, 3),
        on_ground=on_ground,
        squawk=str(squawk) if squawk else None,
    )


def compute_trajectory_orbit_ratio(points: List[Dict[str, Any]]) -> Tuple[float, float, float]:
    """Analyze trajectory window for closed-loop / holding patterns.

    Computes:
        - cumulative_heading_change (sum of absolute turn angles)
        - net_displacement_km (distance between first and last point)
        - total_path_length_km (sum of segment distances)

    Returns:
        (cumulative_heading_deg, net_displacement_km, total_path_length_km)
    """
    if len(points) < 3:
        return 0.0, 0.0, 0.0

    total_heading = 0.0
    total_path = 0.0

    for i in range(1, len(points)):
        p_prev = points[i - 1]
        p_curr = points[i]

        t_prev = p_prev.get("true_track")
        t_curr = p_curr.get("true_track")
        dh = abs(compute_heading_delta(t_prev, t_curr))
        total_heading += dh

        lat1, lon1 = p_prev.get("latitude"), p_prev.get("longitude")
        lat2, lon2 = p_curr.get("latitude"), p_curr.get("longitude")
        if None not in (lat1, lon1, lat2, lon2):
            total_path += haversine_km(lat1, lon1, lat2, lon2)

    p_first = points[0]
    p_last = points[-1]
    lat_f, lon_f = p_first.get("latitude"), p_first.get("longitude")
    lat_l, lon_l = p_last.get("latitude"), p_last.get("longitude")

    if None not in (lat_f, lon_f, lat_l, lon_l):
        net_dist = haversine_km(lat_f, lon_f, lat_l, lon_l)
    else:
        net_dist = 0.0

    return round(total_heading, 1), round(net_dist, 2), round(total_path, 2)
