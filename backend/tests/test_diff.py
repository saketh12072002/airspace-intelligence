"""Tests for the state diff engine."""

from __future__ import annotations

import pytest

from app.schemas.aircraft_state import AircraftState
from app.ws.diff import StateDiff, compute_diff


def _state(icao: str, **kwargs) -> AircraftState:
    defaults = dict(
        icao24=icao,
        callsign="TST1234",
        origin_country="US",
        last_contact=1000000,
        longitude=-122.0,
        latitude=37.0,
        baro_altitude=10000.0,
        on_ground=False,
        velocity=250.0,
        true_track=90.0,
        vertical_rate=0.0,
        geo_altitude=10500.0,
        squawk="1200",
        position_source=0,
        category=0,
    )
    defaults.update(kwargs)
    return AircraftState(**defaults)


def _snap(*states: AircraftState) -> dict[str, AircraftState]:
    return {s.icao24: s for s in states}


class TestComputeDiff:
    def test_empty_to_empty(self):
        diff = compute_diff({}, {})
        assert not diff.has_changes
        assert diff.added == []
        assert diff.updated == []
        assert diff.removed == []

    def test_all_added(self):
        current = _snap(_state("aa"), _state("bb"))
        diff = compute_diff({}, current)
        assert len(diff.added) == 2
        assert diff.updated == []
        assert diff.removed == []
        assert diff.has_changes

    def test_all_removed(self):
        previous = _snap(_state("aa"), _state("bb"))
        diff = compute_diff(previous, {})
        assert diff.added == []
        assert diff.updated == []
        assert sorted(diff.removed) == ["aa", "bb"]
        assert diff.has_changes

    def test_no_change(self):
        s = _state("aa")
        diff = compute_diff(_snap(s), _snap(s))
        assert not diff.has_changes

    def test_updated_position(self):
        old = _state("aa", latitude=37.0)
        new = _state("aa", latitude=37.5)
        diff = compute_diff(_snap(old), _snap(new))
        assert diff.added == []
        assert diff.removed == []
        assert len(diff.updated) == 1
        assert diff.updated[0].latitude == 37.5

    def test_updated_velocity(self):
        old = _state("aa", velocity=250.0)
        new = _state("aa", velocity=300.0)
        diff = compute_diff(_snap(old), _snap(new))
        assert len(diff.updated) == 1

    def test_non_tracked_field_ignored(self):
        """Changes to non-tracked fields (like time_position) should NOT produce an update."""
        old = _state("aa", time_position=100)
        new = _state("aa", time_position=200)
        diff = compute_diff(_snap(old), _snap(new))
        assert not diff.has_changes

    def test_mixed_changes(self):
        """Some added, some updated, some removed."""
        previous = _snap(
            _state("stay", latitude=37.0),
            _state("gone"),
        )
        current = _snap(
            _state("stay", latitude=38.0),  # updated
            _state("new1"),                  # added
        )
        diff = compute_diff(previous, current)
        assert len(diff.added) == 1
        assert diff.added[0].icao24 == "new1"
        assert len(diff.updated) == 1
        assert diff.updated[0].icao24 == "stay"
        assert diff.removed == ["gone"]

    def test_summary_format(self):
        diff = StateDiff(
            added=[_state("a")],
            updated=[_state("b"), _state("c")],
            removed=["d"],
        )
        assert diff.summary == "+1 ~2 -1"
