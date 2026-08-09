"""Tests for attendance cohorts.

Direction is what a filtered list cannot give you: a learner at 88% and
rising needs a different conversation from one at 88% and falling, and
they look identical sorted by percentage.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_cohorts as cohorts,
)


def mark_window(attdb, student_id: str, *, attended: int, total: int,
                offset: int = 0) -> None:
    """Marks over a run of days, ``offset`` days further back."""
    monday = _dt.date.fromisoformat(attdb.prev_monday)
    for index in range(total):
        date = (monday - _dt.timedelta(days=index + offset)).isoformat()
        core.save_register(attdb.slot, date,
                           {student_id: {"code": "/" if index < attended
                                         else "O"}}, allow_retro=True)


# ── 1. Banding ─────────────────────────────────────────────────────

class TestBanding:

    @pytest.mark.parametrize("percentage,band", [
        (100.0, cohorts.ON_TARGET),
        (96.0, cohorts.ON_TARGET),
        (95.0, cohorts.AT_RISK),
        (91.0, cohorts.AT_RISK),
        (90.0, cohorts.PERSISTENT),
        (60.0, cohorts.PERSISTENT),
        (50.0, cohorts.SEVERE),
        (20.0, cohorts.SEVERE),
    ])
    def test_a_figure_lands_in_one_band(self, attdb, percentage, band):
        # Ordered most serious first, so a learner at 45% is counted
        # once, as severely absent.
        assert cohorts.band_for(percentage) == band

    def test_no_data_bands_nowhere(self, attdb):
        assert cohorts.band_for(None) is None

    def test_a_learner_with_no_marks_is_not_a_member(self, attdb):
        assert cohorts.member_for(attdb.s1, date_from=attdb.prev_monday,
                                  date_to=attdb.prev_monday) is None


# ── 2. Cohorts ─────────────────────────────────────────────────────

class TestCohorts:

    def test_a_persistent_absentee_is_listed(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=10)      # 80%
        cohort = cohorts.persistent_absentees()
        assert [m.student_id for m in cohort.members] == [attdb.s1]
        assert cohort.size == 1

    def test_a_severe_absentee_is_not_double_counted(self, attdb):
        mark_window(attdb, attdb.s1, attended=2, total=10)      # 20%
        assert cohorts.severe_absentees().size == 1
        assert cohorts.persistent_absentees().size == 0

    def test_members_are_worst_first(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=10)      # 80%
        mark_window(attdb, attdb.s2, attended=6, total=10)      # 60%
        cohort = cohorts.persistent_absentees()
        assert [m.student_id for m in cohort.members] == [attdb.s2, attdb.s1]

    def test_names_are_joined_on(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=10)
        assert cohorts.persistent_absentees().members[0].student_name == \
            "Ada Test"

    def test_the_average_is_reported(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=10)
        assert cohorts.persistent_absentees().average == 80.0

    def test_bands_are_counted_together(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=10)
        mark_window(attdb, attdb.s2, attended=10, total=10)
        counts = cohorts.band_counts()
        assert counts[cohorts.PERSISTENT] == 1
        assert counts[cohorts.ON_TARGET] == 1

    def test_a_group_can_be_isolated(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=10)
        assert cohorts.persistent_absentees(group_id=attdb.group).size == 1
        assert cohorts.persistent_absentees(group_id=2).size == 0

    def test_an_unknown_band_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Band must be"):
            cohorts.cohort("Doing fine, actually")


# ── 3. Direction ───────────────────────────────────────────────────

class TestDirection:

    def test_a_learner_with_no_history_reads_as_new(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=5)
        member = cohorts.member_for(
            attdb.s1,
            date_from=(_dt.date.fromisoformat(attdb.prev_monday)
                       - _dt.timedelta(days=4)).isoformat(),
            date_to=attdb.prev_monday)
        assert member.direction == cohorts.NEW
        assert member.arrow == "·"

    def test_an_improving_learner_is_flagged(self, attdb):
        window_from = (_dt.date.fromisoformat(attdb.prev_monday)
                       - _dt.timedelta(days=4)).isoformat()
        # Previous window: all absent. Current window: all present.
        mark_window(attdb, attdb.s1, attended=0, total=5, offset=5)
        mark_window(attdb, attdb.s1, attended=5, total=5)
        member = cohorts.member_for(attdb.s1, date_from=window_from,
                                    date_to=attdb.prev_monday)
        assert member.direction == cohorts.IMPROVING
        assert member.change > 0

    def test_a_falling_learner_is_flagged(self, attdb):
        window_from = (_dt.date.fromisoformat(attdb.prev_monday)
                       - _dt.timedelta(days=4)).isoformat()
        mark_window(attdb, attdb.s1, attended=5, total=5, offset=5)
        mark_window(attdb, attdb.s1, attended=0, total=5)
        member = cohorts.member_for(attdb.s1, date_from=window_from,
                                    date_to=attdb.prev_monday)
        assert member.direction == cohorts.FALLING


# ── 4. Snapshots ───────────────────────────────────────────────────

class TestSnapshots:

    def test_a_snapshot_records_the_banding(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=10)
        snapshot_id = cohorts.take_snapshot(label="Half term 1",
                                            taken_by="head")
        bands = cohorts.snapshot_bands(snapshot_id)
        assert bands.get(cohorts.PERSISTENT) == 1

    def test_snapshots_are_listed(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=10)
        cohorts.take_snapshot(label="One")
        assert len(cohorts.list_snapshots()) == 1

    def test_movement_between_snapshots_is_reported(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=10)      # 80%
        first = cohorts.take_snapshot(label="Before")
        # The learner recovers.
        mark_window(attdb, attdb.s1, attended=10, total=10)
        second = cohorts.take_snapshot(label="After")
        moves = cohorts.movement(first, second)
        assert [m.student_id for m in moves] == [attdb.s1]
        assert moves[0].improved is True

    def test_the_movement_summary_gives_the_headline(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=10)
        first = cohorts.take_snapshot(label="Before")
        mark_window(attdb, attdb.s1, attended=10, total=10)
        second = cohorts.take_snapshot(label="After")
        summary = cohorts.movement_summary(first, second)
        assert summary["improved"] == 1
        assert summary["net_change"] == -1


# ── 5. Recovery arithmetic ─────────────────────────────────────────

class TestRecovery:

    def test_a_learner_already_above_needs_nothing(self, attdb):
        mark_window(attdb, attdb.s1, attended=10, total=10)
        recovery = cohorts.sessions_to_reach(attdb.s1, target_pct=90.0)
        assert recovery.sessions_needed is None

    def test_the_sessions_needed_are_computed(self, attdb):
        # 8/10 = 80%. To reach 90%: (8+n)/(10+n) >= 0.9 → n >= 20.
        mark_window(attdb, attdb.s1, attended=8, total=10)
        recovery = cohorts.sessions_to_reach(attdb.s1, target_pct=90.0)
        assert recovery.sessions_needed == 20

    def test_an_out_of_reach_target_is_said_plainly(self, attdb):
        # Better said in October than discovered in June.
        mark_window(attdb, attdb.s1, attended=8, total=10)
        recovery = cohorts.sessions_to_reach(attdb.s1, target_pct=90.0,
                                             sessions_remaining=5)
        assert recovery.achievable is False
        assert "cannot reach" in recovery.label

    def test_a_reachable_target_says_so(self, attdb):
        mark_window(attdb, attdb.s1, attended=8, total=10)
        recovery = cohorts.sessions_to_reach(attdb.s1, target_pct=90.0,
                                             sessions_remaining=40)
        assert recovery.achievable is True

    def test_unreachable_targets_are_listed(self, attdb):
        mark_window(attdb, attdb.s1, attended=5, total=10)
        rows = cohorts.unreachable_targets(sessions_remaining=2,
                                           target_pct=90.0)
        assert attdb.s1 in [r.student_id for r in rows]

    def test_headroom_is_the_other_side_of_the_sum(self, attdb):
        mark_window(attdb, attdb.s1, attended=10, total=10)
        assert cohorts.headroom(attdb.s1, target_pct=90.0,
                                sessions_remaining=10) >= 1
