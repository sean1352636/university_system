"""Tests for the attendance safeguarding bridge.

The pattern that matters is a *run* of unexplained absence with nobody
reachable — not a percentage. A learner at 94% who has not been seen
since Tuesday is the more urgent question.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_calendar as calendar,
    attendance_safeguarding as safeguarding,
    attendance_thresholds as thresholds,
)


def absent_run(attdb, student_id: str, *, days: int,
               code: str = "O") -> list[str]:
    """Mark the last ``days`` teaching days as unexplained absence."""
    today = _dt.date.today()
    window = calendar.teaching_days(
        (today - _dt.timedelta(days=days * 3)).isoformat(),
        today.isoformat())[-days:]
    for date in window:
        core.save_register(attdb.slot, date, {student_id: {"code": code}},
                           allow_retro=True)
    return window


# ── 1. Detecting a run ─────────────────────────────────────────────

class TestAbsenceRun:

    def test_a_run_of_unexplained_absence_is_found(self, attdb):
        dates = absent_run(attdb, attdb.s1, days=4)
        run = safeguarding.absence_run(attdb.s1)
        assert run is not None
        assert run.days == 4
        assert run.first_date == dates[0]

    def test_a_learner_with_no_marks_has_no_run(self, attdb):
        assert safeguarding.absence_run(attdb.s1) is None

    def test_an_attending_mark_breaks_the_run(self, attdb):
        absent_run(attdb, attdb.s1, days=4)
        today = _dt.date.today().isoformat()
        core.save_register(attdb.slot, today, {attdb.s1: {"code": "/"}})
        assert safeguarding.absence_run(attdb.s1) is None

    def test_an_authorised_absence_is_not_a_run(self, attdb):
        absent_run(attdb, attdb.s1, days=4, code="I")
        assert safeguarding.absence_run(attdb.s1) is None

    def test_no_contact_is_reported_with_the_run(self, attdb):
        absent_run(attdb, attdb.s1, days=4)
        run = safeguarding.absence_run(attdb.s1)
        assert run.contact_made is False
        assert run.contact_attempts == 0


# ── 2. Sweeping ────────────────────────────────────────────────────

class TestSweep:

    def test_a_short_absence_raises_nothing(self, attdb):
        absent_run(attdb, attdb.s1, days=1)
        assert safeguarding.sweep().raised == 0

    def test_a_run_past_the_threshold_raises_an_alert(self, attdb):
        absent_run(attdb, attdb.s1, days=4)
        result = safeguarding.sweep(raised_by="office")
        assert result.raised == 1
        assert result.alerts[0].student_id == attdb.s1

    def test_a_dry_run_raises_nothing(self, attdb):
        absent_run(attdb, attdb.s1, days=4)
        assert safeguarding.sweep(dry_run=True).raised == 1
        assert safeguarding.list_alerts() == []

    def test_sweeping_twice_updates_rather_than_duplicates(self, attdb):
        # A learner missing for six days generates one alert that gets
        # more serious, not six alerts.
        absent_run(attdb, attdb.s1, days=4)
        safeguarding.sweep()
        second = safeguarding.sweep()
        assert second.raised == 0
        assert second.existing == 1
        assert len(safeguarding.list_alerts()) == 1

    def test_a_long_run_with_no_contact_is_high(self, attdb):
        thresholds.set_threshold(thresholds.CME_REFERRAL_DAYS, 3.0)
        absent_run(attdb, attdb.s1, days=4)
        result = safeguarding.sweep()
        assert result.alerts[0].level == safeguarding.HIGH

    def test_the_threshold_is_configurable(self, attdb):
        thresholds.set_threshold(thresholds.UNEXPLAINED_DAYS_ALERT, 10.0)
        absent_run(attdb, attdb.s1, days=4)
        assert safeguarding.sweep().raised == 0


# ── 3. Alerts ──────────────────────────────────────────────────────

class TestAlerts:

    @pytest.fixture
    def alert(self, attdb):
        absent_run(attdb, attdb.s1, days=4)
        return safeguarding.sweep(raised_by="office").alerts[0]

    def test_an_open_alert_flags_the_learner(self, attdb, alert):
        # Read by the calling module to push them up the list.
        assert safeguarding.is_flagged(attdb.s1) is True
        assert safeguarding.is_flagged(attdb.s2) is False

    def test_open_alerts_are_most_serious_first(self, attdb, alert):
        rows = safeguarding.open_alerts()
        ranks = [a.rank for a in rows]
        assert ranks == sorted(ranks)
        assert rows[0].student_name == "Ada Test"

    def test_acknowledging_is_not_acting(self, attdb, alert):
        out = safeguarding.acknowledge(alert.alert_id, by="DSL")
        assert out.state == safeguarding.ACKNOWLEDGED
        assert out.is_open is True

    def test_acknowledging_needs_a_name(self, attdb, alert):
        with pytest.raises(core.ValidationError, match="needs a name"):
            safeguarding.acknowledge(alert.alert_id, by="  ")

    def test_recording_an_action_says_what_was_done(self, attdb, alert):
        out = safeguarding.mark_actioned(alert.alert_id, by="DSL",
                                         note="Home visit arranged")
        assert out.state == safeguarding.ACTIONED
        assert out.outcome == "Home visit arranged"

    def test_closing_needs_an_outcome_and_a_person(self, attdb, alert):
        # Always a person, never the sweep.
        with pytest.raises(core.ValidationError, match="stated outcome"):
            safeguarding.close_alert(alert.alert_id, outcome="  ", by="DSL")
        with pytest.raises(core.ValidationError, match="named"):
            safeguarding.close_alert(alert.alert_id, outcome="Seen", by="  ")

    def test_closing_clears_the_flag(self, attdb, alert):
        safeguarding.close_alert(alert.alert_id, outcome="Learner returned",
                                 by="DSL")
        assert safeguarding.is_flagged(attdb.s1) is False

    def test_an_unacknowledged_alert_is_surfaced(self, attdb, alert):
        # This list must never be long.
        assert len(safeguarding.unacknowledged(hours=0)) == 1

    def test_an_unknown_trigger_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Trigger must be"):
            safeguarding.raise_alert(attdb.s1, "Bad vibes")


# ── 4. CME referrals ───────────────────────────────────────────────

class TestReferrals:

    def test_candidates_are_listed_not_acted_on(self, attdb):
        thresholds.set_threshold(thresholds.CME_REFERRAL_DAYS, 3.0)
        absent_run(attdb, attdb.s1, days=4)
        candidates = safeguarding.referral_candidates()
        assert [r.student_id for r in candidates] == [attdb.s1]
        assert safeguarding.list_referrals() == []

    def test_a_referral_records_who_raised_it(self, attdb):
        absent_run(attdb, attdb.s1, days=4)
        referral = safeguarding.raise_cme_referral(
            attdb.s1, raised_by="DSL", local_authority="County",
            narrative="No contact since Monday")
        assert referral.state == safeguarding.DRAFT
        assert referral.raised_by == "DSL"
        assert referral.days_missing == 4

    def test_a_referral_must_name_who_raised_it(self, attdb):
        with pytest.raises(core.ValidationError, match="must name"):
            safeguarding.raise_cme_referral(attdb.s1, raised_by="  ")

    def test_submitting_records_the_date(self, attdb):
        referral = safeguarding.raise_cme_referral(attdb.s1,
                                                   raised_by="DSL")
        out = safeguarding.submit_referral(referral.referral_id,
                                           reference="LA-1234")
        assert out.state == safeguarding.SUBMITTED
        assert out.reference == "LA-1234"

    def test_resolving_needs_an_outcome(self, attdb):
        referral = safeguarding.raise_cme_referral(attdb.s1,
                                                   raised_by="DSL")
        with pytest.raises(core.ValidationError, match="stated outcome"):
            safeguarding.resolve_referral(referral.referral_id, outcome="  ")

    def test_a_learner_with_an_open_referral_is_not_re_listed(self, attdb):
        thresholds.set_threshold(thresholds.CME_REFERRAL_DAYS, 3.0)
        absent_run(attdb, attdb.s1, days=4)
        safeguarding.raise_cme_referral(attdb.s1, raised_by="DSL")
        assert safeguarding.referral_candidates() == []
