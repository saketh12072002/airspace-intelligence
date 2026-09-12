"""State diff engine — computes added / updated / removed aircraft between snapshots.

This module is a pure function with no I/O dependencies, making it trivial to
test in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from app.schemas.aircraft_state import AircraftState


@dataclass(frozen=True, slots=True)
class StateDiff:
    """Result of comparing two aircraft-state snapshots."""

    added: List[AircraftState] = field(default_factory=list)
    updated: List[AircraftState] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)  # icao24 addresses only

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.updated or self.removed)

    @property
    def summary(self) -> str:
        return f"+{len(self.added)} ~{len(self.updated)} -{len(self.removed)}"


# Fields that, when changed, constitute a meaningful update worth broadcasting.
_TRACKED_FIELDS = frozenset({
    "latitude",
    "longitude",
    "baro_altitude",
    "velocity",
    "true_track",
    "vertical_rate",
    "on_ground",
    "geo_altitude",
    "squawk",
    "callsign",
})


def compute_diff(
    previous: Dict[str, AircraftState],
    current: Dict[str, AircraftState],
) -> StateDiff:
    """Compare *previous* and *current* state maps and return a :class:`StateDiff`.

    Args:
        previous: ``{icao24: AircraftState}`` from the last cycle.
        current:  ``{icao24: AircraftState}`` from the new cycle.

    Returns:
        A :class:`StateDiff` with lists of added, updated, and removed aircraft.
    """
    prev_keys = set(previous)
    curr_keys = set(current)

    added_keys = curr_keys - prev_keys
    removed_keys = prev_keys - curr_keys
    common_keys = prev_keys & curr_keys

    added = [current[k] for k in added_keys]
    removed = sorted(removed_keys)  # sorted for deterministic output

    updated: list[AircraftState] = []
    for k in common_keys:
        old = previous[k]
        new = current[k]
        if _has_meaningful_change(old, new):
            updated.append(new)

    return StateDiff(added=added, updated=updated, removed=removed)


def _has_meaningful_change(old: AircraftState, new: AircraftState) -> bool:
    """Return True if *new* differs from *old* on any tracked field."""
    for fname in _TRACKED_FIELDS:
        if getattr(old, fname) != getattr(new, fname):
            return True
    return False
