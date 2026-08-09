"""Tests for the retro-marking window.

Covers the three states a register date passes through as it ages, the
policy that decides where the lines are, what the window does to the
core write paths, and the override log that makes a retrospective write
attributable.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_authorisation as authz,
    attendance_codes as codes,
    attendance_register as reg,
    attendance_window as window,
)


def days_ago(n: int) -> str:
    return (_dt.date.today() - _dt.timedelta(days=n)).isoformat()


def days_ahead(n: int) -> str:
    return (_dt.date.today() + _dt.timedelta(days=n)).isoformat()


# ── 1. The policy ──────────────────────────────────────────────────

class TestPolicy:

    def test_a_fresh_college_gets_the_shipped_defaults(self, attdb):
        policy = window.get_policy()
        assert policy.enabled is True
        assert policy.open_days == window.DEFAULT_OPEN_DAYS
        assert policy.close_days == window.DEFAULT_CLOSE_DAYS

    def test_the_policy_can_be_changed(self, attdb):
        policy = window.set_policy(open_days=5, close_days=30, actor="head")
        assert (policy.open_days, policy.close_days) == (5, 30)
        assert policy.updated_by == "head"

    def test_a_partial_change_keeps_the_rest(self, attdb):
        window.set_policy(open_days=5, close_days=30)
        policy = window.set_policy(open_days=7)
        assert policy.close_days == 30

    def test_closing_before_opening_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="cannot be less"):
            window.set_policy(open_days=30, close_days=10)

    def test_nonsense_days_are_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="whole number"):
            window.set_policy(open_days="soon")

    def test_reset_restores_the_defaults(self, attdb):
        window.set_policy(open_days=1, close_days=2)
        policy = window.reset_policy()
        assert policy.open_days == window.DEFAULT_OPEN_DAYS


# ── 2. Classifying a date ──────────────────────────────────────────

class TestEvaluate:

    def test_today_is_open(self, attdb):
        assert window.evaluate(days_ago(0)).state == window.OPEN

    def test_inside_the_window_is_open(self, attdb):
        assert window.evaluate(days_ago(10)).state == window.OPEN

    def test_the_boundary_day_is_still_open(self, attdb):
        # `open_days` is inclusive: a fortnight old on a 14-day window is
        # the last day of free editing, not the first day past it.
        assert window.evaluate(days_ago(14)).state == window.OPEN

    def test_past_the_window_needs_a_reason(self, attdb):
        decision = window.evaluate(days_ago(20))
        assert decision.state == window.REASON_REQUIRED
        assert decision.allowed is False
        assert decision.requires_reason is True

    def test_a_reason_makes_it_allowed(self, attdb):
        decision = window.evaluate(days_ago(20), reason="Late medical note")
        assert decision.allowed is True

    def test_past_the_cutoff_is_closed(self, attdb):
        decision = window.evaluate(days_ago(90))
        assert decision.state == window.CLOSED
        assert decision.allowed is False

    def test_a_reason_does_not_reopen_a_closed_date(self, attdb):
        assert window.evaluate(days_ago(90), reason="Because").allowed is False

    def test_the_near_future_is_allowed(self, attdb):
        # Marking next week's known absence is normal.
        decision = window.evaluate(days_ahead(7))
        assert decision.state == window.OPEN
        assert decision.is_future is True

    def test_the_far_future_is_refused(self, attdb):
        decision = window.evaluate(days_ahead(500))
        assert decision.state == window.TOO_FAR_AHEAD
        assert decision.allowed is False

    def test_a_disabled_policy_opens_everything(self, attdb):
        window.set_policy(enabled=False)
        assert window.evaluate(days_ago(9999)).state == window.OPEN

    def test_evaluate_writes_nothing(self, attdb):
        window.evaluate(days_ago(90))
        assert window.list_overrides() == []

    def test_the_deadlines_are_reported(self, attdb):
        window.set_policy(open_days=14, close_days=60)
        assert window.closes_on("2026-01-01") == "2026-01-15"
        assert window.final_deadline("2026-01-01") == "2026-03-02"


# ── 3. Gating a write ──────────────────────────────────────────────

class TestAssertOpen:

    def test_an_open_date_passes_silently(self, attdb):
        window.assert_open(days_ago(1))
        assert window.list_overrides() == []

    def test_a_closed_date_raises(self, attdb):
        with pytest.raises(core.ValidationError, match="amendment cutoff"):
            window.assert_open(days_ago(90))

    def test_allow_retro_gets_through(self, attdb):
        decision = window.assert_open(days_ago(90), allow_retro=True,
                                      actor="head")
        assert decision.state == window.CLOSED

    def test_a_retro_write_is_logged_with_its_actor(self, attdb):
        window.assert_open(days_ago(90), allow_retro=True, actor="head",
                           reason="Migrating history", source="test")
        entry = window.list_overrides()[0]
        assert entry.actor == "head"
        assert entry.reason == "Migrating history"
        assert entry.state == window.CLOSED

    def test_a_reasoned_amendment_is_logged_too(self, attdb):
        window.assert_open(days_ago(20), reason="Note arrived late",
                           actor="jsmith")
        assert window.list_overrides()[0].state == window.REASON_REQUIRED


# ── 4. What it does to save_register ───────────────────────────────

class TestSaveRegister:

    def test_a_current_register_saves_normally(self, attdb):
        assert core.save_register(attdb.slot, attdb.monday,
                                  {attdb.s1: {"status": "Present"}}) == 1

    def test_an_ancient_register_is_refused(self, attdb):
        with pytest.raises(core.ValidationError, match="amendment cutoff"):
            core.save_register(attdb.slot, attdb.ancient,
                               {attdb.s1: {"status": "Present"}})

    def test_allow_retro_is_the_way_in(self, attdb):
        assert core.save_register(attdb.slot, attdb.ancient,
                                  {attdb.s1: {"status": "Present"}},
                                  allow_retro=True) == 1

    def test_an_out_of_window_save_needs_a_reason(self, attdb):
        window.set_policy(open_days=1, close_days=400)
        with pytest.raises(core.ValidationError, match="needs a reason"):
            core.save_register(attdb.slot, attdb.prev_monday,
                               {attdb.s1: {"status": "Present"}})

    def test_a_reason_lets_it_through(self, attdb):
        window.set_policy(open_days=1, close_days=400)
        assert core.save_register(attdb.slot, attdb.prev_monday,
                                  {attdb.s1: {"status": "Present"}},
                                  reason="Register found in a drawer") == 1

    def test_an_out_of_window_save_writes_an_amendment_trail(self, attdb):
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_audit as audit,
        )
        window.set_policy(open_days=1, close_days=400)
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"status": "Present"}},
                           reason="Paper register typed up", actor="jsmith")
        trail = audit.list_amendments(student_id=attdb.s1)
        assert trail
        assert all(e.reason == "Paper register typed up" for e in trail)


# ── 5. The curated amendment paths still reach old marks ───────────

class TestAmendmentPaths:

    @pytest.fixture
    def ancient_absence(self, attdb):
        core.save_register(attdb.slot, attdb.ancient,
                           {attdb.s1: {"status": "Absent"}},
                           allow_retro=True)
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.ancient)
        assert record is not None
        return record

    def test_authorising_works_on_a_closed_date(self, attdb,
                                                ancient_absence):
        # The whole point of the window: after it shuts, these are the
        # only ways in — and they each record who did it.
        out = authz.authorise(ancient_absence.record_id,
                              authorised_by="head", note="Evidence received")
        assert out.is_authorised is True

    def test_recoding_works_on_a_closed_date(self, attdb, ancient_absence):
        out = codes.set_code(ancient_absence.record_id, "I", actor="head")
        assert out.code == "I"

    def test_a_plain_edit_does_not(self, attdb, ancient_absence):
        with pytest.raises(core.ValidationError, match="amendment cutoff"):
            core.update_record(ancient_absence.record_id,
                               {"notes": "changed my mind"})

    def test_a_plain_edit_with_retro_does(self, attdb, ancient_absence):
        out = core.update_record(ancient_absence.record_id,
                                 {"notes": "Corrected"}, allow_retro=True,
                                 actor="head", reason="Data cleanse")
        assert out.notes == "Corrected"


# ── 6. Range marking skips closed dates rather than failing ────────

class TestRangeMarking:

    def test_a_closed_date_is_skipped_not_fatal(self, attdb):
        window.set_policy(open_days=0, close_days=0)
        result = reg.mark_range(
            date_from=attdb.prev_monday, date_to=attdb.monday,
            status="Authorised", group_id=attdb.group)
        assert result.skipped_closed
        assert result.written == 0

    def test_open_dates_in_the_same_range_still_write(self, attdb):
        # Only the past Monday is closed; today's is inside the window.
        window.set_policy(open_days=3, close_days=3)
        result = reg.mark_range(
            date_from=attdb.prev_monday, date_to=attdb.monday,
            status="Authorised", group_id=attdb.group)
        assert attdb.monday in result.dates
        assert result.written > 0


# ── 7. The chase list ──────────────────────────────────────────────

class TestClosingSoon:

    def test_a_register_about_to_close_is_listed(self, attdb):
        window.set_policy(open_days=8, close_days=60)
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"status": "Present"}})
        rows = window.closing_soon(within_days=3)
        assert [r.date for r in rows] == [attdb.prev_monday]
        assert rows[0].days_remaining <= 3

    def test_a_fresh_register_is_not_listed(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        assert window.closing_soon(within_days=1) == []

    def test_submitted_registers_are_excluded_by_default(self, attdb):
        window.set_policy(open_days=8, close_days=60)
        core.save_register(
            attdb.slot, attdb.prev_monday,
            {sid: {"status": "Present"} for sid in attdb.students})
        reg.submit_register(attdb.slot, attdb.prev_monday,
                            submitted_by="teacher")
        assert window.closing_soon(within_days=3) == []
        assert window.closing_soon(within_days=3, include_submitted=True)
