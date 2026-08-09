"""Tests for first-day calling.

Priority is the whole design: twenty absences and forty minutes means
the order of the list is the decision.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_absence_reports as reports,
    attendance_calling as calling,
    attendance_leave as leave,
)


# ── 1. Building the list ───────────────────────────────────────────

class TestBuild:

    def test_an_unexplained_absence_makes_the_list(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        result = calling.build_list(date=attdb.prev_monday)
        assert result.created == 1
        assert [c.student_id for c in result.calls] == [attdb.s1]

    def test_an_authorised_absence_does_not(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "I"}})
        assert calling.build_list(date=attdb.prev_monday).created == 0

    def test_a_present_learner_does_not(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"status": "Present"}})
        assert calling.build_list(date=attdb.prev_monday).created == 0

    def test_an_absence_report_keeps_them_off_the_list(self, attdb):
        # Ringing a parent who phoned in teaches them that phoning in
        # achieves nothing.
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "N"}})
        reports.report_absence(attdb.s1, attdb.prev_monday,
                               reason_text="Flu")
        result = calling.build_list(date=attdb.prev_monday)
        assert result.created == 0
        assert result.skipped_explained == 1

    def test_approved_leave_keeps_them_off_it(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.prev_monday,
                                      kind="Interview")
        leave.approve(request.request_id, decided_by="head")
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        assert calling.build_list(
            date=attdb.prev_monday).skipped_explained == 1

    def test_building_twice_does_not_duplicate(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        calling.build_list(date=attdb.prev_monday)
        second = calling.build_list(date=attdb.prev_monday)
        assert second.created == 0
        assert second.already_open == 1

    def test_authorised_absences_can_be_included_deliberately(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "I"}})
        result = calling.build_list(date=attdb.prev_monday,
                                    include_authorised=True)
        assert result.created == 1

    def test_the_list_is_sorted_by_priority(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {sid: {"code": "O"} for sid in attdb.students})
        calling.build_list(date=attdb.prev_monday)
        queue = calling.call_list(date=attdb.prev_monday)
        ranks = [c.rank for c in queue]
        assert ranks == sorted(ranks)


# ── 2. Priority ────────────────────────────────────────────────────

class TestPriority:

    def test_an_ordinary_absence_is_normal(self, attdb):
        priority, reason = calling.priority_for(attdb.s1, attdb.prev_monday)
        assert priority == calling.NORMAL
        assert reason

    def test_a_second_consecutive_day_is_high(self, attdb):
        import datetime as _dt
        day = _dt.date.fromisoformat(attdb.prev_monday)
        yesterday = (day - _dt.timedelta(days=1)).isoformat()
        core.save_register(attdb.slot, yesterday,
                           {attdb.s1: {"code": "O"}})
        priority, reason = calling.priority_for(attdb.s1, attdb.prev_monday)
        assert priority == calling.HIGH
        assert "Second day" in reason

    def test_a_safeguarding_flag_is_urgent(self, attdb):
        from education_system.systems.sixth_form.domain.academics.attendance \
            import attendance_safeguarding as safeguarding
        safeguarding.raise_alert(attdb.s1,
                                 safeguarding.CONSECUTIVE_ABSENCE,
                                 first_date=attdb.prev_monday, days=4)
        priority, reason = calling.priority_for(attdb.s1, attdb.prev_monday)
        assert priority == calling.URGENT
        assert "safeguarding" in reason.lower()


# ── 3. Logging calls ───────────────────────────────────────────────

class TestLogging:

    @pytest.fixture
    def call(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        calling.build_list(date=attdb.prev_monday)
        return calling.call_for(attdb.s1, attdb.prev_monday)

    def test_contact_made_closes_the_call(self, attdb, call):
        out = calling.log_call(call.call_id, calling.SPOKE_PARENT,
                               called_by="office", notes="Ill")
        assert out.state == calling.DONE
        assert out.resolved is True

    def test_no_answer_leaves_it_open(self, attdb, call):
        out = calling.log_call(call.call_id, calling.NO_ANSWER,
                               called_by="office")
        assert out.state == calling.IN_PROGRESS
        assert out.attempts == 1

    def test_repeated_no_answers_become_unreachable(self, attdb, call):
        for _ in range(calling.MAX_ATTEMPTS):
            out = calling.log_call(call.call_id, calling.NO_ANSWER)
        assert out.state == calling.UNREACHABLE

    def test_a_bad_number_is_unreachable_at_once(self, attdb, call):
        out = calling.log_call(call.call_id, calling.WRONG_NUMBER)
        assert out.state == calling.UNREACHABLE

    def test_every_attempt_is_kept(self, attdb, call):
        calling.log_call(call.call_id, calling.NO_ANSWER)
        calling.log_call(call.call_id, calling.VOICEMAIL)
        assert len(calling.attempts_for(call.call_id)) == 2

    def test_an_unknown_outcome_is_rejected(self, attdb, call):
        with pytest.raises(core.ValidationError, match="Outcome must be"):
            calling.log_call(call.call_id, "Shouted out of the window")

    def test_a_call_can_be_deferred(self, attdb, call):
        out = calling.defer(call.call_id, reason="On a trip", actor="office")
        assert out.state == calling.DEFERRED

    def test_deferring_needs_a_reason(self, attdb, call):
        with pytest.raises(core.ValidationError, match="reason is required"):
            calling.defer(call.call_id, reason="  ")

    def test_an_explanation_becomes_an_absence_report(self, attdb, call):
        # Closes the loop: the reason given on the phone becomes a
        # report somebody codes, not a note nobody reads.
        calling.record_explanation(call.call_id, reason_text="Hospital",
                                   called_by="office")
        assert reports.reports_for(attdb.s1, date=attdb.prev_monday)


# ── 4. Reporting ───────────────────────────────────────────────────

class TestReporting:

    def test_the_morning_is_measured(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {sid: {"code": "O"} for sid in attdb.students})
        calling.build_list(date=attdb.prev_monday)
        first = calling.call_for(attdb.s1, attdb.prev_monday)
        calling.log_call(first.call_id, calling.SPOKE_PARENT)
        stats = calling.stats(date=attdb.prev_monday)
        assert stats.total == 3
        assert stats.done == 1
        assert stats.contact_made == 1
        assert stats.completion_rate == pytest.approx(33.3, abs=0.1)

    def test_unreachable_learners_are_listed(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        calling.build_list(date=attdb.prev_monday)
        call = calling.call_for(attdb.s1, attdb.prev_monday)
        calling.log_call(call.call_id, calling.WRONG_NUMBER)
        assert [c.student_id for c in calling.unreachable()] == [attdb.s1]

    def test_outcomes_are_counted(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        calling.build_list(date=attdb.prev_monday)
        call = calling.call_for(attdb.s1, attdb.prev_monday)
        calling.log_call(call.call_id, calling.VOICEMAIL)
        assert calling.outcome_breakdown()[calling.VOICEMAIL] == 1
