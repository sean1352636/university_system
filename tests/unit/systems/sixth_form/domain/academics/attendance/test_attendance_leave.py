"""Tests for planned-absence requests.

Request, decide, then mark — in that order, so the register reflects a
decision the college made rather than an absence it recoded afterwards.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_exams as exams,
    attendance_leave as leave,
)


# ── 1. Requesting ──────────────────────────────────────────────────

class TestRequesting:

    def test_a_request_writes_no_mark(self, attdb):
        leave.request_leave(attdb.s1, attdb.monday,
                            kind="University open day")
        assert core.list_records(student_id=attdb.s1) == []

    def test_notice_is_measured(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.next_monday,
                                      kind="Interview",
                                      on=attdb.prev_monday)
        assert request.notice_days == 14
        assert request.short_notice is False

    def test_short_notice_is_flagged_not_refused(self, attdb):
        # A driving-test cancellation does not respect policy.
        request = leave.request_leave(attdb.s1, attdb.monday,
                                      kind="Driving test",
                                      on=attdb.monday)
        assert request.short_notice is True

    def test_an_unknown_kind_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Kind must be"):
            leave.request_leave(attdb.s1, attdb.monday, kind="Festival")

    def test_an_unknown_learner_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No student"):
            leave.request_leave("NOPE", attdb.monday)

    def test_overlapping_leave_is_refused(self, attdb):
        leave.request_leave(attdb.s1, attdb.monday, date_to=attdb.next_monday)
        with pytest.raises(core.ValidationError, match="already has leave"):
            leave.request_leave(attdb.s1, attdb.monday)

    def test_an_end_before_a_start_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="cannot end before"):
            leave.request_leave(attdb.s1, attdb.next_monday,
                                date_to=attdb.monday)

    @pytest.mark.parametrize("kind,code", [
        ("University open day", "C"),
        ("Family holiday", "H"),
        ("College activity", "B"),
        ("Medical appointment", "M"),
        ("Religious observance", "R"),
    ])
    def test_each_kind_implies_a_code(self, attdb, kind, code):
        assert leave.code_for_kind(kind) == code

    def test_pending_requests_are_listed_soonest_first(self, attdb):
        leave.request_leave(attdb.s1, attdb.next_monday)
        leave.request_leave(attdb.s2, attdb.monday)
        assert [r.date_from for r in leave.pending()] == [attdb.monday,
                                                           attdb.next_monday]


# ── 2. Clashes ─────────────────────────────────────────────────────

class TestClashes:

    def test_an_exam_in_the_span_is_a_clash(self, attdb):
        sitting = exams.create_sitting({"paper_code": "9MA0/01",
                                        "date": attdb.monday,
                                        "start_time": "09:00"})
        exams.add_candidate(sitting.sitting_id, attdb.s1, seat="1")
        request = leave.request_leave(attdb.s1, attdb.monday,
                                      kind="Family holiday")
        found = leave.clashes(request.request_id)
        assert [c.what for c in found] == ["Exam sitting"]

    def test_approving_over_an_exam_is_refused(self, attdb):
        # The mistake this whole workflow exists to prevent.
        sitting = exams.create_sitting({"paper_code": "9MA0/01",
                                        "date": attdb.monday,
                                        "start_time": "09:00"})
        exams.add_candidate(sitting.sitting_id, attdb.s1, seat="1")
        request = leave.request_leave(attdb.s1, attdb.monday,
                                      kind="Family holiday")
        with pytest.raises(core.ValidationError, match="sitting"):
            leave.approve(request.request_id, decided_by="head")

    def test_it_can_be_overridden_deliberately(self, attdb):
        sitting = exams.create_sitting({"paper_code": "9MA0/01",
                                        "date": attdb.monday,
                                        "start_time": "09:00"})
        exams.add_candidate(sitting.sitting_id, attdb.s1, seat="1")
        request = leave.request_leave(attdb.s1, attdb.monday,
                                      kind="Bereavement")
        result = leave.approve(request.request_id, decided_by="head",
                               ignore_clashes=True)
        assert result.marks_written >= 1

    def test_a_clear_span_has_no_clashes(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday)
        assert leave.clashes(request.request_id) == []


# ── 3. Approving ───────────────────────────────────────────────────

class TestApproving:

    def test_approval_codes_the_register(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday,
                                      kind="University open day",
                                      destination="Leeds")
        result = leave.approve(request.request_id, decided_by="head")
        assert result.marks_written == 2
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.code == "C"
        assert record.notes == "University open day: Leeds"

    def test_a_college_activity_marks_off_site(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday,
                                      kind="College activity",
                                      destination="Science Museum")
        leave.approve(request.request_id, decided_by="head")
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.is_offsite is True
        assert record.offsite_location == "Science Museum"

    def test_approval_needs_a_named_approver(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday)
        with pytest.raises(core.ValidationError, match="approved by "
                                                       "somebody named"):
            leave.approve(request.request_id, decided_by="  ")

    def test_approving_twice_is_refused(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday)
        leave.approve(request.request_id, decided_by="head")
        with pytest.raises(core.ValidationError, match="already approved"):
            leave.approve(request.request_id, decided_by="head")

    def test_declining_needs_a_reason(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday)
        with pytest.raises(core.ValidationError, match="reason is required"):
            leave.decline(request.request_id, reason="  ")

    def test_declining_writes_no_marks(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday)
        leave.decline(request.request_id, reason="Too close to exams",
                      decided_by="head")
        assert core.list_records(student_id=attdb.s1) == []

    def test_a_withdrawn_request_cannot_be_approved(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday)
        leave.withdraw(request.request_id, reason="No longer needed")
        with pytest.raises(core.ValidationError, match="withdrawn"):
            leave.approve(request.request_id, decided_by="head")

    def test_an_approved_request_cannot_be_withdrawn(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday)
        leave.approve(request.request_id, decided_by="head")
        with pytest.raises(core.ValidationError, match="cancel it instead"):
            leave.withdraw(request.request_id)


# ── 4. Cancelling ──────────────────────────────────────────────────

class TestCancelling:

    def test_cancelling_voids_the_marks(self, attdb):
        # The interview was cancelled; the learner is in college after
        # all, and crediting an absence that never happened is wrong.
        request = leave.request_leave(attdb.s1, attdb.monday,
                                      kind="Interview")
        leave.approve(request.request_id, decided_by="head")
        leave.cancel(request.request_id, reason="Interview cancelled",
                     actor="head")
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.voided is True

    def test_cancelling_needs_a_reason(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday)
        leave.approve(request.request_id, decided_by="head")
        with pytest.raises(core.ValidationError, match="reason is required"):
            leave.cancel(request.request_id, reason="  ")

    def test_only_approved_leave_can_be_cancelled(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday)
        with pytest.raises(core.ValidationError, match="not approved"):
            leave.cancel(request.request_id, reason="Never mind")


# ── 5. Allowance and reporting ─────────────────────────────────────

class TestAllowance:

    def test_discretionary_leave_uses_the_allowance(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday,
                                      kind="Family holiday")
        leave.approve(request.request_id, decided_by="head")
        assert leave.leave_used(attdb.s1).used_days == 1

    def test_educational_leave_does_not(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday,
                                      kind="University open day")
        leave.approve(request.request_id, decided_by="head")
        assert leave.leave_used(attdb.s1).used_days == 0

    def test_upcoming_leave_is_listed(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday)
        leave.approve(request.request_id, decided_by="head")
        assert [r.request_id for r in leave.upcoming(days=14)] == \
            [request.request_id]

    def test_who_is_out_on_a_date_is_answerable(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday)
        leave.approve(request.request_id, decided_by="head")
        assert [r.student_id for r in leave.on_leave(attdb.monday)] == \
            [attdb.s1]

    def test_days_are_counted_by_kind(self, attdb):
        request = leave.request_leave(attdb.s1, attdb.monday,
                                      kind="Family holiday")
        leave.approve(request.request_id, decided_by="head")
        assert leave.kind_breakdown()["Family holiday"] == 1

    def test_short_notice_requests_are_reported(self, attdb):
        leave.request_leave(attdb.s1, attdb.monday, on=attdb.monday)
        assert len(leave.short_notice_report()) == 1
