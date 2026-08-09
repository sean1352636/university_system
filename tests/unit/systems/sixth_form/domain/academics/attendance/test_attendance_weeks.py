"""Tests for A/B timetable weeks.

The load-bearing property is the first one: a college that has never
configured a cycle must get exactly the answers it got before this
module existed. Everything else is what happens once it has.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_register as reg,
    attendance_sessions as sessions,
    attendance_weeks as weeks,
)


def next_weekday(target: int) -> _dt.date:
    today = _dt.date.today()
    return today + _dt.timedelta(days=(target - today.weekday()) % 7)


@pytest.fixture
def ab_weeks(attdb):
    """A two-week cycle anchored so that ``attdb.monday`` is week A."""
    weeks.set_pattern(cycle_weeks=2, anchor_date=attdb.monday)
    return attdb


# ── 1. An unconfigured college behaves as before ───────────────────

class TestNoCycle:

    def test_the_default_is_a_single_week(self, attdb):
        assert weeks.get_pattern().is_cycling is False

    def test_every_date_is_week_a(self, attdb):
        assert weeks.week_for_date(attdb.monday) == "A"
        assert weeks.week_for_date(attdb.next_monday) == "A"

    def test_filtering_is_a_no_op(self, attdb):
        from education_system.systems.sixth_form.domain.academics.timetable import (
            timetable as tt,
        )
        slots = tt.list_slots()
        assert weeks.filter_slots(slots, attdb.monday) == slots

    def test_a_stored_week_is_ignored_while_there_is_no_cycle(self, attdb):
        # Pinned under a two-week cycle, then the cycle is turned off:
        # the pin must stop mattering rather than hiding the lesson.
        weeks.set_pattern(cycle_weeks=2, anchor_date=attdb.monday)
        weeks.set_slot_week(attdb.slot, "B")
        weeks.reset_pattern()
        assert weeks.slot_runs_on(attdb.slot, attdb.monday) is True

    def test_expected_lessons_are_unchanged(self, attdb):
        lessons = sessions.expected_lessons(
            group_id=attdb.group, date_from=attdb.monday,
            date_to=attdb.monday)
        assert [lesson.slot_id for lesson in lessons] == [attdb.slot,
                                                          attdb.pm_slot]


# ── 2. The cycle ───────────────────────────────────────────────────

class TestCycle:

    def test_a_two_week_cycle_alternates(self, ab_weeks):
        assert weeks.week_for_date(ab_weeks.monday) == "A"
        assert weeks.week_for_date(ab_weeks.next_monday) == "B"

    def test_every_day_of_a_week_shares_its_label(self, ab_weeks):
        monday = _dt.date.fromisoformat(ab_weeks.monday)
        for offset in range(7):
            date = (monday + _dt.timedelta(days=offset)).isoformat()
            assert weeks.week_for_date(date) == "A"

    def test_the_cycle_runs_backwards_too(self, ab_weeks):
        assert weeks.week_for_date(ab_weeks.prev_monday) == "B"

    def test_a_longer_cycle_is_allowed(self, attdb):
        pattern = weeks.set_pattern(cycle_weeks=3, anchor_date=attdb.monday)
        assert pattern.labels == ("A", "B", "C")

    def test_an_absurd_cycle_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="between 1 and"):
            weeks.set_pattern(cycle_weeks=9)

    def test_changing_the_cycle_keeps_the_anchor(self, attdb):
        weeks.set_pattern(cycle_weeks=2, anchor_date=attdb.monday)
        anchor = weeks.get_pattern().anchor_date
        weeks.set_pattern(cycle_weeks=3)
        assert weeks.get_pattern().anchor_date == anchor

    def test_the_next_week_b_is_reported(self, ab_weeks):
        assert weeks.next_date_in_week("B", after=ab_weeks.monday) == \
            ab_weeks.next_monday

    def test_reset_goes_back_to_one_week(self, ab_weeks):
        assert weeks.reset_pattern().is_cycling is False


# ── 3. Pinning slots ───────────────────────────────────────────────

class TestSlotMap:

    def test_an_unpinned_slot_runs_in_both(self, ab_weeks):
        assert weeks.week_of_slot(ab_weeks.slot) == weeks.BOTH

    def test_a_pinned_slot_runs_in_its_week_only(self, ab_weeks):
        weeks.set_slot_week(ab_weeks.slot, "A")
        assert weeks.slot_runs_on(ab_weeks.slot, ab_weeks.monday) is True
        assert weeks.slot_runs_on(ab_weeks.slot, ab_weeks.next_monday) is False

    def test_both_still_runs_everywhere(self, ab_weeks):
        weeks.set_slot_week(ab_weeks.slot, weeks.BOTH)
        assert weeks.slot_runs_on(ab_weeks.slot, ab_weeks.next_monday) is True

    def test_a_week_outside_the_cycle_is_rejected(self, ab_weeks):
        with pytest.raises(core.ValidationError, match="not part of"):
            weeks.set_slot_week(ab_weeks.slot, "C")

    def test_an_unknown_label_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Week must be"):
            weeks.validate_week("Z")

    def test_labels_are_normalised(self, attdb):
        assert weeks.validate_week("a") == "A"
        assert weeks.validate_week("both") == weeks.BOTH

    def test_a_missing_slot_is_rejected(self, ab_weeks):
        with pytest.raises(core.ValidationError, match="No slot"):
            weeks.set_slot_week(9999, "A")

    def test_clearing_puts_it_back(self, ab_weeks):
        weeks.set_slot_week(ab_weeks.slot, "A")
        assert weeks.clear_slot_week(ab_weeks.slot) is True
        assert weeks.week_of_slot(ab_weeks.slot) == weeks.BOTH

    def test_a_whole_group_can_be_pinned(self, ab_weeks):
        assert weeks.assign_group(ab_weeks.group, "B") == 2
        assert weeks.week_of_slot(ab_weeks.slot) == "B"

    def test_a_shortened_cycle_orphans_its_leftovers(self, attdb):
        weeks.set_pattern(cycle_weeks=3, anchor_date=attdb.monday)
        weeks.set_slot_week(attdb.slot, "C")
        weeks.set_pattern(cycle_weeks=2)
        orphans = weeks.orphaned_assignments()
        assert [o.slot_id for o in orphans] == [attdb.slot]

    def test_the_summary_counts_the_split(self, ab_weeks):
        weeks.set_slot_week(ab_weeks.slot, "A")
        summary = weeks.summary()
        assert summary.by_week["A"] == 1
        assert summary.both == summary.total_slots - 1


# ── 4. What the rest of the system sees ────────────────────────────

class TestDownstream:

    def test_expected_lessons_drop_the_wrong_week(self, ab_weeks):
        weeks.set_slot_week(ab_weeks.slot, "A")
        week_b = sessions.expected_lessons(
            group_id=ab_weeks.group, date_from=ab_weeks.next_monday,
            date_to=ab_weeks.next_monday)
        assert ab_weeks.slot not in [lesson.slot_id for lesson in week_b]
        assert ab_weeks.pm_slot in [lesson.slot_id for lesson in week_b]

    def test_expected_lessons_keep_the_right_week(self, ab_weeks):
        weeks.set_slot_week(ab_weeks.slot, "A")
        week_a = sessions.expected_lessons(
            group_id=ab_weeks.group, date_from=ab_weeks.monday,
            date_to=ab_weeks.monday)
        assert ab_weeks.slot in [lesson.slot_id for lesson in week_a]

    def test_the_chase_list_ignores_lessons_that_do_not_run(self, ab_weeks):
        weeks.set_slot_week(ab_weeks.slot, "A")
        missing = reg.unsubmitted_registers(date_from=ab_weeks.next_monday,
                                            date_to=ab_weeks.next_monday)
        assert ab_weeks.slot not in [m.slot_id for m in missing]

    def test_range_marking_skips_them_too(self, ab_weeks):
        weeks.set_slot_week(ab_weeks.slot, "B")
        reg.mark_range(date_from=ab_weeks.monday, date_to=ab_weeks.monday,
                       status="Authorised", group_id=ab_weeks.group)
        # Week A: the pinned week-B slot must not have been marked.
        assert core.list_records(slot_id=ab_weeks.slot,
                                 date=ab_weeks.monday) == []
        assert core.list_records(slot_id=ab_weeks.pm_slot,
                                 date=ab_weeks.monday)


# ── 5. The calendar ────────────────────────────────────────────────

class TestCalendar:

    def test_the_calendar_labels_every_date(self, ab_weeks):
        days = weeks.week_calendar(ab_weeks.monday, ab_weeks.next_monday)
        assert len(days) == 8
        assert days[0].week == "A"
        assert days[-1].week == "B"

    def test_a_backwards_range_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="on or before"):
            weeks.week_calendar(attdb.next_monday, attdb.monday)

    def test_an_absurd_range_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="366"):
            weeks.week_calendar("2020-01-01", "2026-01-01")
