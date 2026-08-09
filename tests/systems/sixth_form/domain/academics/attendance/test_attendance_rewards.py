"""Tests for attendance rewards.

The improvement award is the one that matters: it reaches the learner
who went from 71% to 84%, which is harder than staying at 100% and is
the behaviour a college actually wants to reinforce.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_rewards as rewards,
)


def mark_run(attdb, student_id: str, *, attended: int, total: int,
             offset: int = 0, late: int = 0) -> None:
    monday = _dt.date.fromisoformat(attdb.prev_monday)
    for index in range(total):
        date = (monday - _dt.timedelta(days=index + offset)).isoformat()
        if index < late:
            payload = {"code": "L", "minutes_late": 5}
        else:
            payload = {"code": "/" if index < attended else "O"}
        core.save_register(attdb.slot, date, {student_id: payload},
                           allow_retro=True)


def window(attdb, *, days: int, offset: int = 0) -> tuple[str, str]:
    monday = _dt.date.fromisoformat(attdb.prev_monday)
    return ((monday - _dt.timedelta(days=days - 1 + offset)).isoformat(),
            (monday - _dt.timedelta(days=offset)).isoformat())


# ── 1. Nominating ──────────────────────────────────────────────────

class TestNominating:

    def test_full_attendance_earns_a_nomination(self, attdb):
        mark_run(attdb, attdb.s1, attended=10, total=10)
        period_from, period_to = window(attdb, days=10)
        result = rewards.nominate(period_from=period_from,
                                  period_to=period_to, min_sessions=1)
        kinds = {c.kind for c in result.candidates
                 if c.student_id == attdb.s1}
        assert rewards.FULL_ATTENDANCE in kinds

    def test_high_but_not_full_earns_the_lesser_award(self, attdb):
        mark_run(attdb, attdb.s1, attended=39, total=40)     # 97.5%
        period_from, period_to = window(attdb, days=40)
        result = rewards.nominate(period_from=period_from,
                                  period_to=period_to, min_sessions=1)
        kinds = {c.kind for c in result.candidates
                 if c.student_id == attdb.s1}
        assert rewards.HIGH_ATTENDANCE in kinds
        assert rewards.FULL_ATTENDANCE not in kinds

    def test_a_learner_with_too_few_sessions_is_skipped(self, attdb):
        # 100% of three lessons is not an achievement.
        mark_run(attdb, attdb.s1, attended=3, total=3)
        period_from, period_to = window(attdb, days=3)
        result = rewards.nominate(period_from=period_from,
                                  period_to=period_to, min_sessions=10)
        assert result.candidates == []

    def test_improvement_is_measured_against_the_previous_period(self,
                                                                  attdb):
        mark_run(attdb, attdb.s1, attended=5, total=10, offset=10)   # 50%
        mark_run(attdb, attdb.s1, attended=9, total=10)              # 90%
        period_from, period_to = window(attdb, days=10)
        result = rewards.nominate(period_from=period_from,
                                  period_to=period_to, min_sessions=1)
        improved = [c for c in result.of_kind(rewards.MOST_IMPROVED)
                    if c.student_id == attdb.s1]
        assert improved
        assert improved[0].improvement == pytest.approx(40.0)

    def test_a_flat_learner_earns_no_improvement_award(self, attdb):
        mark_run(attdb, attdb.s1, attended=9, total=10, offset=10)
        mark_run(attdb, attdb.s1, attended=9, total=10)
        period_from, period_to = window(attdb, days=10)
        result = rewards.nominate(period_from=period_from,
                                  period_to=period_to, min_sessions=1)
        assert [c for c in result.of_kind(rewards.MOST_IMPROVED)
                if c.student_id == attdb.s1] == []

    def test_punctuality_needs_perfect_attendance_and_no_lates(self, attdb):
        mark_run(attdb, attdb.s1, attended=10, total=10)
        period_from, period_to = window(attdb, days=10)
        result = rewards.nominate(period_from=period_from,
                                  period_to=period_to, min_sessions=1)
        kinds = {c.kind for c in result.candidates
                 if c.student_id == attdb.s1}
        assert rewards.PUNCTUALITY in kinds

    def test_a_late_mark_costs_the_punctuality_award(self, attdb):
        mark_run(attdb, attdb.s1, attended=10, total=10, late=1)
        period_from, period_to = window(attdb, days=10)
        result = rewards.nominate(period_from=period_from,
                                  period_to=period_to, min_sessions=1)
        kinds = {c.kind for c in result.candidates
                 if c.student_id == attdb.s1}
        assert rewards.PUNCTUALITY not in kinds

    def test_the_same_award_is_not_nominated_twice(self, attdb):
        # An award that arrives repeatedly stops being an award.
        mark_run(attdb, attdb.s1, attended=10, total=10)
        period_from, period_to = window(attdb, days=10)
        first = rewards.nominate(period_from=period_from,
                                 period_to=period_to, min_sessions=1)
        rewards.record_all(first)
        second = rewards.nominate(period_from=period_from,
                                  period_to=period_to, min_sessions=1)
        assert second.candidates == []
        assert second.skipped_existing > 0

    def test_a_backwards_period_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="cannot end before"):
            rewards.nominate(period_from=attdb.monday,
                             period_to=attdb.prev_monday)

    def test_most_improved_is_rankable(self, attdb):
        mark_run(attdb, attdb.s1, attended=5, total=10, offset=10)
        mark_run(attdb, attdb.s1, attended=9, total=10)
        period_from, period_to = window(attdb, days=10)
        ranked = rewards.most_improved(period_from=period_from,
                                       period_to=period_to)
        assert ranked[0].student_id == attdb.s1


# ── 2. Awarding ────────────────────────────────────────────────────

class TestAwarding:

    @pytest.fixture
    def nominated(self, attdb):
        mark_run(attdb, attdb.s1, attended=10, total=10)
        period_from, period_to = window(attdb, days=10)
        result = rewards.nominate(period_from=period_from,
                                  period_to=period_to, min_sessions=1)
        stored = rewards.record_all(result, period_label="Autumn 1",
                                    nominated_by="head")
        return stored[0]

    def test_a_nomination_starts_unconfirmed(self, attdb, nominated):
        assert nominated.state == rewards.NOMINATED

    def test_confirming_makes_it_an_award(self, attdb, nominated):
        out = rewards.confirm(nominated.award_id, awarded_by="head")
        assert out.state == rewards.AWARDED
        assert out.awarded_by == "head"

    def test_confirming_needs_somebody_to_give_it(self, attdb, nominated):
        with pytest.raises(core.ValidationError, match="somebody to give"):
            rewards.confirm(nominated.award_id, awarded_by="  ")

    def test_confirming_twice_is_refused(self, attdb, nominated):
        rewards.confirm(nominated.award_id, awarded_by="head")
        with pytest.raises(core.ValidationError, match="already"):
            rewards.confirm(nominated.award_id, awarded_by="head")

    def test_a_nomination_can_be_declined(self, attdb, nominated):
        out = rewards.decline(nominated.award_id,
                              reason="Learner would rather not be named")
        assert out.state == rewards.DECLINED

    def test_declining_needs_a_reason(self, attdb, nominated):
        with pytest.raises(core.ValidationError, match="reason is required"):
            rewards.decline(nominated.award_id, reason="  ")

    def test_a_batch_can_be_confirmed(self, attdb, nominated):
        assert rewards.confirm_all(awarded_by="head") >= 1

    def test_an_unconfirmed_award_cannot_be_issued(self, attdb, nominated):
        with pytest.raises(core.ValidationError, match="not been confirmed"):
            rewards.issue_certificate(nominated.award_id)

    def test_issuing_records_the_citation(self, attdb, nominated):
        rewards.confirm(nominated.award_id, awarded_by="head")
        out = rewards.issue_certificate(nominated.award_id,
                                        issued_by="head")
        assert out.state == rewards.ISSUED

    def test_the_citation_reads_sensibly(self, attdb, nominated):
        text = rewards.citation_text(nominated)
        assert nominated.student_id in text or "Ada" in text
        assert nominated.kind.lower() in text


# ── 3. Reporting ───────────────────────────────────────────────────

class TestReporting:

    def test_pending_nominations_are_listed(self, attdb):
        mark_run(attdb, attdb.s1, attended=10, total=10)
        period_from, period_to = window(attdb, days=10)
        rewards.record_all(rewards.nominate(period_from=period_from,
                                            period_to=period_to,
                                            min_sessions=1))
        assert rewards.pending_nominations()

    def test_the_roll_of_honour_groups_by_kind(self, attdb):
        mark_run(attdb, attdb.s1, attended=10, total=10)
        period_from, period_to = window(attdb, days=10)
        rewards.record_all(rewards.nominate(period_from=period_from,
                                            period_to=period_to,
                                            min_sessions=1))
        roll = rewards.roll_of_honour(period_from=period_from,
                                      period_to=period_to)
        assert rewards.FULL_ATTENDANCE in roll

    def test_awards_are_counted_by_kind(self, attdb):
        mark_run(attdb, attdb.s1, attended=10, total=10)
        period_from, period_to = window(attdb, days=10)
        rewards.record_all(rewards.nominate(period_from=period_from,
                                            period_to=period_to,
                                            min_sessions=1))
        assert rewards.counts()[rewards.FULL_ATTENDANCE] == 1

    def test_reach_measures_how_many_learners_are_touched(self, attdb):
        # A scheme that only rewards the same twenty learners has
        # stopped doing anything for anybody else.
        mark_run(attdb, attdb.s1, attended=10, total=10)
        period_from, period_to = window(attdb, days=10)
        rewards.record_all(rewards.nominate(period_from=period_from,
                                            period_to=period_to,
                                            min_sessions=1))
        reach = rewards.reach(period_from=period_from, period_to=period_to)
        assert reach["learners_rewarded"] == 1
        assert reach["active_learners"] == 3

    def test_a_learners_awards_are_listed(self, attdb):
        mark_run(attdb, attdb.s1, attended=10, total=10)
        period_from, period_to = window(attdb, days=10)
        rewards.record_all(rewards.nominate(period_from=period_from,
                                            period_to=period_to,
                                            min_sessions=1))
        assert rewards.student_awards(attdb.s1)

    def test_an_unknown_kind_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Kind must be"):
            rewards.validate_kind("Best hair")
