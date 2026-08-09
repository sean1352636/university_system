"""Tests for attendance-linked bursary.

Holding a learner's money is a serious act, so the design is cautious:
assessment recommends, a person decides, illness never costs anybody
their bursary, and hardship overrides the lot.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_bursary as bursary,
    attendance_thresholds as thresholds,
)


def mark_period(attdb, student_id: str, *, present: int, absent: int,
                code: str = "O") -> tuple[str, str]:
    """Marks across a period, returning its (from, to) dates."""
    monday = _dt.date.fromisoformat(attdb.prev_monday)
    total = present + absent
    for index in range(total):
        date = (monday - _dt.timedelta(days=index)).isoformat()
        core.save_register(attdb.slot, date,
                           {student_id: {"code": "/" if index < present
                                         else code}}, allow_retro=True)
    return ((monday - _dt.timedelta(days=total - 1)).isoformat(),
            attdb.prev_monday)


# ── 1. Awards ──────────────────────────────────────────────────────

class TestAwards:

    def test_an_award_can_be_recorded(self, attdb):
        award = bursary.create_award(attdb.s1, amount=30.0,
                                     award_type=bursary.DISCRETIONARY)
        assert award.amount == 30.0
        assert award.attendance_linked is True

    def test_vulnerable_group_awards_are_never_attendance_linked(self, attdb):
        # A statutory entitlement, not a reward for turning up.
        award = bursary.create_award(attdb.s1, amount=1200.0,
                                     award_type=bursary.VULNERABLE)
        assert award.attendance_linked is False

    def test_free_meals_are_never_held(self, attdb):
        award = bursary.create_award(attdb.s1, amount=2.50,
                                     award_type=bursary.MEALS)
        assert award.attendance_linked is False

    def test_an_award_can_be_unconditional(self, attdb):
        award = bursary.create_award(attdb.s1, amount=30.0,
                                     conditional=False)
        assert award.attendance_linked is False

    def test_an_unknown_learner_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No student"):
            bursary.create_award("NOPE", amount=30.0)

    def test_a_non_numeric_amount_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="must be a number"):
            bursary.create_award(attdb.s1, amount="lots")

    def test_an_award_can_be_ended(self, attdb):
        award = bursary.create_award(attdb.s1, amount=30.0)
        bursary.end_award(award.award_id)
        assert bursary.list_awards() == []


# ── 2. Assessing ───────────────────────────────────────────────────

class TestAssessing:

    def test_good_attendance_is_paid(self, attdb):
        bursary.create_award(attdb.s1, amount=30.0)
        period_from, period_to = mark_period(attdb, attdb.s1, present=10,
                                             absent=0)
        result = bursary.assess(period_from=period_from,
                                period_to=period_to)
        assert [a.decision for a in result.assessments] == [bursary.PAY]

    def test_poor_attendance_is_recommended_for_hold(self, attdb):
        bursary.create_award(attdb.s1, amount=30.0)
        period_from, period_to = mark_period(attdb, attdb.s1, present=5,
                                             absent=5)
        result = bursary.assess(period_from=period_from,
                                period_to=period_to)
        assert result.to_hold
        assert result.total_held == 30.0

    def test_assessment_writes_nothing(self, attdb):
        bursary.create_award(attdb.s1, amount=30.0)
        period_from, period_to = mark_period(attdb, attdb.s1, present=5,
                                             absent=5)
        bursary.assess(period_from=period_from, period_to=period_to)
        assert bursary.list_payments() == []

    def test_authorised_absence_does_not_cost_the_bursary(self, attdb):
        # A learner in hospital has not broken an agreement, and a
        # scheme that says otherwise drives learners to come in ill.
        bursary.create_award(attdb.s1, amount=30.0)
        period_from, period_to = mark_period(attdb, attdb.s1, present=5,
                                             absent=5, code="I")
        result = bursary.assess(period_from=period_from,
                                period_to=period_to)
        assert [a.decision for a in result.assessments] == [bursary.PAY]

    def test_an_exempt_learner_is_paid(self, attdb):
        bursary.create_award(attdb.s1, amount=30.0)
        bursary.add_exemption(attdb.s1, reason="Hardship",
                              granted_by="head")
        period_from, period_to = mark_period(attdb, attdb.s1, present=1,
                                             absent=9)
        result = bursary.assess(period_from=period_from,
                                period_to=period_to)
        assert result.assessments[0].decision == bursary.PAY
        assert result.assessments[0].exempt is True

    def test_no_data_is_paid_by_default(self, attdb):
        bursary.create_award(attdb.s1, amount=30.0)
        result = bursary.assess(period_from=attdb.tuesday,
                                period_to=attdb.tuesday)
        assert result.assessments[0].decision == bursary.PAY

    def test_the_threshold_is_configurable(self, attdb):
        bursary.create_award(attdb.s1, amount=30.0)
        thresholds.set_threshold(thresholds.BURSARY_HOLD, 40.0)
        period_from, period_to = mark_period(attdb, attdb.s1, present=5,
                                             absent=5)
        result = bursary.assess(period_from=period_from,
                                period_to=period_to)
        assert result.assessments[0].decision == bursary.PAY

    def test_a_backwards_period_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="cannot end before"):
            bursary.assess(period_from=attdb.monday,
                           period_to=attdb.prev_monday)


# ── 3. Deciding ────────────────────────────────────────────────────

class TestDeciding:

    @pytest.fixture
    def poor(self, attdb):
        bursary.create_award(attdb.s1, amount=30.0)
        period_from, period_to = mark_period(attdb, attdb.s1, present=5,
                                             absent=5)
        return bursary.assess(period_from=period_from, period_to=period_to)

    def test_committing_a_hold_records_it(self, attdb, poor):
        payment = bursary.apply_decision(poor.to_hold[0],
                                         decided_by="finance")
        assert payment.state == bursary.HELD
        assert bursary.held_total() == 30.0

    def test_a_decision_must_be_attributed(self, attdb, poor):
        with pytest.raises(core.ValidationError, match="must name"):
            bursary.apply_decision(poor.to_hold[0], decided_by="  ")

    def test_a_person_can_override_the_recommendation(self, attdb, poor):
        payment = bursary.apply_decision(poor.to_hold[0],
                                         decided_by="head",
                                         override=bursary.PAY,
                                         note="Circumstances known")
        assert payment.state == bursary.PAID

    def test_a_run_can_commit_payments_only(self, attdb, poor):
        # The cautious way to run this the first few times.
        counts = bursary.apply_run(poor, decided_by="finance",
                                   pay_only=True)
        assert counts.get(bursary.HOLD, 0) == 0
        assert bursary.held_total() == 0.0

    def test_committing_twice_updates_rather_than_duplicates(self, attdb,
                                                             poor):
        bursary.apply_decision(poor.to_hold[0], decided_by="finance")
        bursary.apply_decision(poor.to_hold[0], decided_by="finance")
        assert len(bursary.list_payments()) == 1


# ── 4. Releasing ───────────────────────────────────────────────────

class TestReleasing:

    @pytest.fixture
    def held(self, attdb):
        bursary.create_award(attdb.s1, amount=30.0)
        period_from, period_to = mark_period(attdb, attdb.s1, present=5,
                                             absent=5)
        result = bursary.assess(period_from=period_from,
                                period_to=period_to)
        return bursary.apply_decision(result.to_hold[0],
                                      decided_by="finance")

    def test_a_held_payment_can_be_released(self, attdb, held):
        # A condition with no way back is a fine, and a fine does not
        # change behaviour the way a recoverable hold does.
        out = bursary.release(held.payment_id, released_by="finance")
        assert out.state == bursary.RELEASED

    def test_a_release_must_be_attributed(self, attdb, held):
        with pytest.raises(core.ValidationError, match="must name"):
            bursary.release(held.payment_id, released_by="  ")

    def test_only_a_held_payment_can_be_released(self, attdb, held):
        bursary.release(held.payment_id, released_by="finance")
        with pytest.raises(core.ValidationError, match="not held"):
            bursary.release(held.payment_id, released_by="finance")

    def test_recovery_releases_automatically(self, attdb, held):
        # A learner who fixes their attendance should get their money
        # back without having to know they can ask.
        monday = _dt.date.fromisoformat(attdb.monday)
        later_from = attdb.monday
        later_to = (monday + _dt.timedelta(days=2)).isoformat()
        for offset in range(3):
            core.save_register(
                attdb.slot,
                (monday + _dt.timedelta(days=offset)).isoformat(),
                {attdb.s1: {"code": "/"}})
        released = bursary.release_on_recovery(date_from=later_from,
                                               date_to=later_to,
                                               released_by="finance")
        assert len(released) == 1

    def test_forfeiting_needs_a_reason_and_a_person(self, attdb, held):
        with pytest.raises(core.ValidationError, match="reason and a named"):
            bursary.forfeit(held.payment_id, reason="  ", by="finance")

    def test_forfeiting_writes_it_off(self, attdb, held):
        out = bursary.forfeit(held.payment_id, reason="Learner left",
                              by="finance")
        assert out.state == bursary.FORFEITED


# ── 5. Exemptions and reporting ────────────────────────────────────

class TestExemptions:

    def test_an_exemption_applies_from_its_start_date(self, attdb):
        bursary.add_exemption(attdb.s1, reason="Young carer",
                              start_date=attdb.prev_monday)
        assert bursary.is_exempt(attdb.s1, on=attdb.monday) is True

    def test_an_exemption_expires(self, attdb):
        bursary.add_exemption(attdb.s1, reason="Medical",
                              start_date=attdb.prev_monday,
                              end_date=attdb.prev_monday)
        assert bursary.is_exempt(attdb.s1, on=attdb.monday) is False

    def test_an_unknown_reason_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Reason must be"):
            bursary.add_exemption(attdb.s1, reason="Just because")

    def test_an_exemption_can_be_removed(self, attdb):
        exemption = bursary.add_exemption(attdb.s1, reason="Hardship")
        assert bursary.remove_exemption(exemption.exemption_id) is True
        assert bursary.is_exempt(attdb.s1) is False

    def test_a_run_summary_is_produced(self, attdb):
        bursary.create_award(attdb.s1, amount=30.0)
        period_from, period_to = mark_period(attdb, attdb.s1, present=10,
                                             absent=0)
        result = bursary.assess(period_from=period_from,
                                period_to=period_to)
        bursary.apply_run(result, decided_by="finance")
        summary = bursary.run_summary(period_from=period_from)
        assert summary["paid"] == 1
        assert summary["amount_paid"] == 30.0

    def test_a_learners_history_is_readable(self, attdb):
        bursary.create_award(attdb.s1, amount=30.0)
        period_from, period_to = mark_period(attdb, attdb.s1, present=10,
                                             absent=0)
        result = bursary.assess(period_from=period_from,
                                period_to=period_to)
        bursary.apply_run(result, decided_by="finance")
        assert len(bursary.student_history(attdb.s1)) == 1
