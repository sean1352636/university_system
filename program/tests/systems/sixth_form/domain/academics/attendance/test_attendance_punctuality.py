"""Tests for punctuality tracking.

Lateness hides inside attendance: a learner present for every lesson and
eleven minutes late to half of them reads as 100%, which is true and
useless. These count the minutes instead.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_punctuality as punctuality,
    attendance_thresholds as thresholds,
)


def late_marks(attdb, student_id: str, *, count: int,
               minutes: int = 10) -> None:
    monday = _dt.date.fromisoformat(attdb.prev_monday)
    for index in range(count):
        date = (monday - _dt.timedelta(days=index)).isoformat()
        core.save_register(attdb.slot, date,
                           {student_id: {"code": "L",
                                         "minutes_late": minutes}},
                           allow_retro=True)


# ── 1. Measuring ───────────────────────────────────────────────────

class TestMeasuring:

    def test_an_on_time_learner_has_nothing_to_report(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        record = punctuality.record_for(attdb.s1)
        assert record.late == 0
        assert record.minutes_lost == 0
        assert record.on_time == 1

    def test_late_minutes_are_totalled(self, attdb):
        late_marks(attdb, attdb.s1, count=3, minutes=20)
        record = punctuality.record_for(attdb.s1)
        assert record.late == 3
        assert record.minutes_lost == 60
        assert record.hours_lost == 1.0

    def test_the_average_lateness_is_reported(self, attdb):
        late_marks(attdb, attdb.s1, count=2, minutes=15)
        assert punctuality.record_for(attdb.s1).average_minutes == 15.0

    def test_the_late_rate_is_a_share_of_lessons(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "L", "minutes_late": 5}})
        core.save_register(attdb.pm_slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        assert punctuality.record_for(attdb.s1).late_rate == 50.0

    def test_an_after_close_arrival_is_counted_separately(self, attdb):
        # Present in the room, absent in the data — the group nobody
        # looks at.
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "U", "minutes_late": 45}})
        record = punctuality.record_for(attdb.s1)
        assert record.after_close == 1
        assert record.late == 1

    def test_after_close_marks_are_findable(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "U", "minutes_late": 45}})
        rows = punctuality.after_register_closed()
        assert [r.student_id for r in rows] == [attdb.s1]

    def test_absences_do_not_count_as_lateness(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        record = punctuality.record_for(attdb.s1)
        assert record.late == 0
        assert record.lessons == 0

    def test_shorthand_returns_the_minutes(self, attdb):
        late_marks(attdb, attdb.s1, count=2, minutes=30)
        assert punctuality.minutes_lost(attdb.s1) == 60


# ── 2. The league ──────────────────────────────────────────────────

class TestLeague:

    def test_the_league_is_worst_first(self, attdb):
        late_marks(attdb, attdb.s1, count=1, minutes=5)
        late_marks(attdb, attdb.s2, count=1, minutes=40)
        league = punctuality.league()
        assert [r.student_id for r in league] == [attdb.s2, attdb.s1]

    def test_punctual_learners_are_excluded(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        assert punctuality.league(minimum_lates=1) == []

    def test_names_are_joined_on(self, attdb):
        late_marks(attdb, attdb.s1, count=1)
        assert punctuality.league()[0].student_name == "Ada Test"

    def test_the_college_total_is_reported(self, attdb):
        late_marks(attdb, attdb.s1, count=2, minutes=30)
        summary = punctuality.college_summary()
        assert summary["late_marks"] == 2
        assert summary["hours_lost"] == 1.0
        assert summary["learners_late"] == 1


# ── 3. Patterns ────────────────────────────────────────────────────

class TestPatterns:

    def test_lateness_is_grouped_by_period(self, attdb):
        # Period 1 lateness is transport; period 5 is lunch.
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "L", "minutes_late": 10}})
        insight = punctuality.patterns()
        assert insight.by_period.get(1) == 1
        assert insight.first_period_share == 100.0

    def test_lateness_is_grouped_by_weekday(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "L", "minutes_late": 10}})
        insight = punctuality.patterns()
        assert insight.worst_weekday == 1        # a Monday

    def test_one_learner_can_be_isolated(self, attdb):
        late_marks(attdb, attdb.s1, count=2)
        late_marks(attdb, attdb.s2, count=1)
        insight = punctuality.patterns(student_id=attdb.s1)
        assert sum(insight.by_period.values()) == 2


# ── 4. Triggers ────────────────────────────────────────────────────

class TestTriggers:

    @pytest.mark.parametrize("count,action", [
        (1, None),
        (3, punctuality.CONVERSATION),
        (5, punctuality.DETENTION),
        (9, punctuality.PARENT_CONTACT),
        (15, punctuality.ESCALATE),
    ])
    def test_the_ladder_picks_the_response(self, attdb, count, action):
        assert punctuality.action_for(count) == action

    def test_a_trigger_records_the_window(self, attdb):
        late_marks(attdb, attdb.s1, count=5)
        trigger = punctuality.raise_trigger(attdb.s1)
        assert trigger.late_count == 5
        assert trigger.state == punctuality.RAISED

    def test_the_sweep_raises_for_learners_over_the_line(self, attdb):
        thresholds.set_threshold(thresholds.LATE_COUNT_TRIGGER, 3.0)
        late_marks(attdb, attdb.s1, count=4)
        result = punctuality.sweep()
        assert result.raised == 1

    def test_a_dry_run_raises_nothing(self, attdb):
        thresholds.set_threshold(thresholds.LATE_COUNT_TRIGGER, 3.0)
        late_marks(attdb, attdb.s1, count=4)
        result = punctuality.sweep(dry_run=True)
        assert result.raised == 1
        assert punctuality.list_triggers() == []

    def test_the_sweep_does_not_reissue_an_open_sanction(self, attdb):
        # A detention issued every morning stops meaning anything.
        thresholds.set_threshold(thresholds.LATE_COUNT_TRIGGER, 3.0)
        late_marks(attdb, attdb.s1, count=4)
        punctuality.sweep()
        second = punctuality.sweep()
        assert second.raised == 0
        assert second.skipped_existing == 1

    def test_a_punctual_learner_triggers_nothing(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        assert punctuality.sweep().raised == 0

    def test_minutes_alone_can_trigger(self, attdb):
        thresholds.set_threshold(thresholds.LATE_COUNT_TRIGGER, 99.0)
        thresholds.set_threshold(thresholds.LATE_MINUTES_TRIGGER, 30.0)
        late_marks(attdb, attdb.s1, count=2, minutes=20)
        assert punctuality.sweep().raised == 1

    def test_a_trigger_can_be_actioned_and_served(self, attdb):
        late_marks(attdb, attdb.s1, count=5)
        trigger = punctuality.raise_trigger(attdb.s1)
        punctuality.action_trigger(trigger.trigger_id,
                                   actioned_by="Mr Patel",
                                   due_on=attdb.monday)
        out = punctuality.serve(trigger.trigger_id, on=attdb.monday)
        assert out.state == punctuality.SERVED

    def test_a_missed_sanction_is_its_own_event(self, attdb):
        late_marks(attdb, attdb.s1, count=5)
        trigger = punctuality.raise_trigger(attdb.s1)
        out = punctuality.mark_missed(trigger.trigger_id,
                                      note="Did not attend")
        assert out.state == punctuality.MISSED

    def test_a_trigger_can_be_waived_with_a_reason(self, attdb):
        late_marks(attdb, attdb.s1, count=5)
        trigger = punctuality.raise_trigger(attdb.s1)
        out = punctuality.waive(trigger.trigger_id,
                                reason="Bus route changed")
        assert out.state == punctuality.WAIVED

    def test_waiving_needs_a_reason(self, attdb):
        late_marks(attdb, attdb.s1, count=5)
        trigger = punctuality.raise_trigger(attdb.s1)
        with pytest.raises(core.ValidationError, match="reason is required"):
            punctuality.waive(trigger.trigger_id, reason="  ")

    def test_outstanding_sanctions_are_listed(self, attdb):
        late_marks(attdb, attdb.s1, count=5)
        punctuality.raise_trigger(attdb.s1)
        assert len(punctuality.outstanding()) == 1

    def test_an_unknown_action_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Action must be"):
            punctuality.validate_action("Stern look")
