"""Tests for configurable attendance thresholds.

Scope resolution and direction are the two things everything else in the
package depends on being right.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_thresholds as thresholds,
)


# ── 1. Shipped defaults ────────────────────────────────────────────

class TestDefaults:

    def test_the_sector_figures_are_seeded(self, attdb):
        assert thresholds.value_of(thresholds.PERSISTENT_ABSENCE) == 90.0
        assert thresholds.value_of(thresholds.SEVERE_ABSENCE) == 50.0

    def test_every_shipped_key_resolves(self, attdb):
        for key, _direction, _value, _unit, _desc in thresholds.SHIPPED:
            assert thresholds.resolve(key) is not None

    def test_seeding_twice_does_not_duplicate(self, attdb):
        thresholds.seed_defaults()
        assert len(thresholds.list_thresholds(
            key=thresholds.PERSISTENT_ABSENCE)) == 1

    def test_an_unconfigured_key_falls_back(self, attdb):
        assert thresholds.value_of("invented_key", default=42.0) == 42.0

    def test_an_unconfigured_key_without_a_default_is_none(self, attdb):
        assert thresholds.value_of("invented_key") is None


# ── 2. Direction ───────────────────────────────────────────────────

class TestDirection:

    def test_a_below_threshold_trips_underneath(self, attdb):
        assert thresholds.is_breached(thresholds.PERSISTENT_ABSENCE,
                                      85.0) is True
        assert thresholds.is_breached(thresholds.PERSISTENT_ABSENCE,
                                      95.0) is False

    def test_the_boundary_counts(self, attdb):
        # Sector practice reads this as "90% or below", and getting it
        # wrong moves a learner in or out of a cohort by one session.
        assert thresholds.is_breached(thresholds.PERSISTENT_ABSENCE,
                                      90.0) is True

    def test_an_above_threshold_trips_over(self, attdb):
        assert thresholds.is_breached(thresholds.LATE_COUNT_TRIGGER,
                                      6.0) is True
        assert thresholds.is_breached(thresholds.LATE_COUNT_TRIGGER,
                                      2.0) is False

    def test_a_missing_measurement_never_trips(self, attdb):
        assert thresholds.is_breached(thresholds.PERSISTENT_ABSENCE,
                                      None) is False

    def test_an_unknown_direction_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Direction must be"):
            thresholds.set_threshold("thing", 1, direction="sideways")


# ── 3. Scope ───────────────────────────────────────────────────────

class TestScope:

    def test_a_year_override_beats_the_college_default(self, attdb):
        thresholds.set_threshold(thresholds.TARGET_ATTENDANCE, 97.0,
                                 scope=thresholds.SCOPE_YEAR,
                                 scope_value="13")
        assert thresholds.value_of(thresholds.TARGET_ATTENDANCE) == 95.0
        assert thresholds.value_of(thresholds.TARGET_ATTENDANCE,
                                   year_group=13) == 97.0

    def test_a_cohort_override_beats_a_year_one(self, attdb):
        thresholds.set_threshold(thresholds.TARGET_ATTENDANCE, 97.0,
                                 scope=thresholds.SCOPE_YEAR,
                                 scope_value="13")
        thresholds.set_threshold(thresholds.TARGET_ATTENDANCE, 85.0,
                                 scope=thresholds.SCOPE_COHORT,
                                 scope_value="resit")
        assert thresholds.value_of(thresholds.TARGET_ATTENDANCE,
                                   year_group=13, cohort="resit") == 85.0

    def test_an_unrelated_year_still_gets_the_default(self, attdb):
        thresholds.set_threshold(thresholds.TARGET_ATTENDANCE, 97.0,
                                 scope=thresholds.SCOPE_YEAR,
                                 scope_value="13")
        assert thresholds.value_of(thresholds.TARGET_ATTENDANCE,
                                   year_group=12) == 95.0

    def test_an_override_inherits_direction_and_unit(self, attdb):
        out = thresholds.set_threshold(thresholds.PERSISTENT_ABSENCE, 88.0,
                                       scope=thresholds.SCOPE_YEAR,
                                       scope_value="12")
        assert out.direction == thresholds.BELOW
        assert out.unit == "%"

    def test_a_scoped_threshold_needs_something_to_apply_to(self, attdb):
        with pytest.raises(core.ValidationError, match="needs a"):
            thresholds.set_threshold("thing", 1,
                                     scope=thresholds.SCOPE_YEAR)

    def test_an_override_can_be_cleared(self, attdb):
        thresholds.set_threshold(thresholds.TARGET_ATTENDANCE, 97.0,
                                 scope=thresholds.SCOPE_YEAR,
                                 scope_value="13")
        assert thresholds.clear_override(thresholds.TARGET_ATTENDANCE,
                                         scope=thresholds.SCOPE_YEAR,
                                         scope_value="13") is True
        assert thresholds.value_of(thresholds.TARGET_ATTENDANCE,
                                   year_group=13) == 95.0

    def test_the_college_default_cannot_be_cleared(self, attdb):
        # It is the fallback; clearing it would leave nothing underneath.
        with pytest.raises(core.ValidationError, match="cannot be cleared"):
            thresholds.clear_override(thresholds.TARGET_ATTENDANCE,
                                      scope=thresholds.SCOPE_COLLEGE,
                                      scope_value="x")


# ── 4. Using them ──────────────────────────────────────────────────

class TestUsage:

    def test_breaches_reports_everything_crossed(self, attdb):
        found = thresholds.breaches({
            thresholds.PERSISTENT_ABSENCE: 85.0,
            thresholds.LATE_COUNT_TRIGGER: 9.0,
            thresholds.SEVERE_ABSENCE: 85.0,
        })
        keys = {b.key for b in found}
        assert thresholds.PERSISTENT_ABSENCE in keys
        assert thresholds.LATE_COUNT_TRIGGER in keys
        assert thresholds.SEVERE_ABSENCE not in keys

    def test_missing_measurements_are_ignored(self, attdb):
        assert thresholds.breaches(
            {thresholds.PERSISTENT_ABSENCE: None}) == []

    @pytest.mark.parametrize("percentage,expected", [
        (99.0, None),
        (91.0, thresholds.LETTER_1),
        (87.0, thresholds.LETTER_2),
        (80.0, thresholds.LETTER_3),
    ])
    def test_the_worst_letter_is_the_one_earned(self, attdb, percentage,
                                                expected):
        # A learner at 80% gets letter 3, not three letters.
        assert thresholds.worst_letter(percentage) == expected

    def test_everything_resolves_at_once(self, attdb):
        values = thresholds.as_dict()
        assert values[thresholds.PERSISTENT_ABSENCE] == 90.0
        assert len(values) >= len(thresholds.SHIPPED)

    def test_a_value_can_be_changed(self, attdb):
        out = thresholds.set_threshold(thresholds.PERSISTENT_ABSENCE, 92.0,
                                       actor="head")
        assert out.value == 92.0
        assert out.updated_by == "head"

    def test_a_non_numeric_value_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="must be a number"):
            thresholds.set_threshold(thresholds.PERSISTENT_ABSENCE, "high")

    def test_reset_restores_the_shipped_figures(self, attdb):
        thresholds.set_threshold(thresholds.PERSISTENT_ABSENCE, 50.0)
        thresholds.reset_to_shipped(actor="head")
        assert thresholds.value_of(thresholds.PERSISTENT_ABSENCE) == 90.0
