"""Tests for inbound absence reporting and self-certification.

A report is a claim, not a mark: it lands in a queue and becomes a coded
absence only when somebody decides what code it deserves.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_absence_reports as reports,
    attendance_thresholds as thresholds,
)


# ── 1. Taking a report ─────────────────────────────────────────────

class TestReporting:

    def test_a_report_writes_no_mark(self, attdb):
        reports.report_absence(attdb.s1, attdb.prev_monday,
                               reason_text="Flu")
        assert core.list_records(student_id=attdb.s1) == []
        assert reports.queue_count() == 1

    def test_a_report_records_how_it_arrived(self, attdb):
        report = reports.report_absence(attdb.s1, attdb.prev_monday,
                                        channel=reports.PORTAL,
                                        reported_by=reports.PARENT,
                                        reporter_name="A Parent")
        assert report.channel == reports.PORTAL
        assert report.reporter_name == "A Parent"

    def test_a_single_day_span_reads_as_one_date(self, attdb):
        report = reports.report_absence(attdb.s1, attdb.prev_monday)
        assert report.days == 1
        assert report.span == attdb.prev_monday

    def test_an_unknown_learner_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No student"):
            reports.report_absence("NOPE", attdb.prev_monday)

    def test_an_end_before_a_start_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="cannot end before"):
            reports.report_absence(attdb.s1, attdb.monday,
                                   date_to=attdb.prev_monday)

    def test_the_far_future_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="days ahead"):
            reports.report_absence(attdb.s1, "2030-01-01")

    def test_an_unknown_channel_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Channel must be"):
            reports.report_absence(attdb.s1, attdb.prev_monday,
                                   channel="Carrier pigeon")

    def test_the_queue_is_oldest_absence_first(self, attdb):
        reports.report_absence(attdb.s1, attdb.monday)
        reports.report_absence(attdb.s2, attdb.prev_monday)
        assert [r.date_from for r in reports.queue()] == [attdb.prev_monday,
                                                          attdb.monday]

    def test_the_queue_carries_names(self, attdb):
        reports.report_absence(attdb.s1, attdb.prev_monday)
        assert reports.queue()[0].student_name == "Ada Test"


# ── 2. Deciding ────────────────────────────────────────────────────

class TestDeciding:

    def test_accepting_writes_the_marks(self, attdb):
        report = reports.report_absence(attdb.s1, attdb.prev_monday,
                                        reason_text="Flu")
        result = reports.accept(report.report_id, code="I",
                                decided_by="office")
        assert result.marks_written == 2      # two Monday lessons
        record = core.get_record_for(attdb.slot, attdb.s1,
                                     attdb.prev_monday)
        assert record.code == "I"

    def test_the_reason_travels_onto_the_mark(self, attdb):
        report = reports.report_absence(attdb.s1, attdb.prev_monday,
                                        reason_text="Dentist")
        reports.accept(report.report_id, code="M")
        record = core.get_record_for(attdb.slot, attdb.s1,
                                     attdb.prev_monday)
        assert record.notes == "Dentist"

    def test_a_day_with_no_lessons_is_skipped_not_counted(self, attdb):
        report = reports.report_absence(attdb.s1, attdb.tuesday)
        result = reports.accept(report.report_id, code="I")
        assert result.marks_written == 0
        assert attdb.tuesday in result.skipped

    def test_accepting_twice_is_refused(self, attdb):
        report = reports.report_absence(attdb.s1, attdb.prev_monday)
        reports.accept(report.report_id, code="I")
        with pytest.raises(core.ValidationError, match="already been "
                                                       "accepted"):
            reports.accept(report.report_id, code="I")

    def test_rejecting_keeps_the_report(self, attdb):
        # "We were told and did not accept it" is a different record
        # from "nobody told us".
        report = reports.report_absence(attdb.s1, attdb.prev_monday)
        out = reports.reject(report.report_id, reason="Third this month",
                             decided_by="head")
        assert out.state == reports.REJECTED
        assert out.decision_note == "Third this month"
        assert reports.get_report(report.report_id) is not None

    def test_rejecting_needs_a_reason(self, attdb):
        report = reports.report_absence(attdb.s1, attdb.prev_monday)
        with pytest.raises(core.ValidationError, match="reason is required"):
            reports.reject(report.report_id, reason="  ")

    def test_an_unknown_report_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No absence report"):
            reports.accept(9999)


# ── 3. Self-certification ──────────────────────────────────────────

class TestSelfCertification:

    def test_self_certifying_codes_immediately(self, attdb):
        report = reports.self_certify(attdb.s1, attdb.prev_monday,
                                      reason_text="Cold")
        assert report.state == reports.ACCEPTED
        assert report.self_certified is True
        record = core.get_record_for(attdb.slot, attdb.s1,
                                     attdb.prev_monday)
        assert record.code == reports.SELF_CERT_CODE

    def test_the_mark_is_stamped_as_self_service(self, attdb):
        reports.self_certify(attdb.s1, attdb.prev_monday)
        record = core.get_record_for(attdb.slot, attdb.s1,
                                     attdb.prev_monday)
        assert record.data_source == reports.SELF_CERT_SOURCE

    def test_the_allowance_starts_full(self, attdb):
        status = reports.self_cert_status(attdb.s1)
        assert status.used_days == 0
        assert status.remaining == status.cap

    def test_certifying_uses_the_allowance(self, attdb):
        reports.self_certify(attdb.s1, attdb.prev_monday)
        assert reports.self_cert_status(attdb.s1).used_days == 1

    def test_the_cap_is_enforced(self, attdb):
        # A learner ill four times this term needs a conversation, not
        # a fifth form.
        thresholds.set_threshold(thresholds.SELF_CERT_CAP, 1.0)
        reports.self_certify(attdb.s1, attdb.prev_monday)
        with pytest.raises(core.ValidationError, match="self-certified day"):
            reports.self_certify(attdb.s1, attdb.monday)

    def test_a_longer_span_than_the_allowance_is_refused(self, attdb):
        thresholds.set_threshold(thresholds.SELF_CERT_CAP, 1.0)
        with pytest.raises(core.ValidationError, match="self-certified day"):
            reports.self_certify(attdb.s1, attdb.prev_monday,
                                 date_to=attdb.monday)

    def test_heavy_users_are_reported(self, attdb):
        reports.self_certify(attdb.s1, attdb.prev_monday)
        rows = reports.self_certification_report()
        assert [s.student_id for s in rows] == [attdb.s1]


# ── 4. Reading back ────────────────────────────────────────────────

class TestReads:

    def test_a_report_covering_a_date_is_findable(self, attdb):
        reports.report_absence(attdb.s1, attdb.prev_monday,
                               date_to=attdb.monday)
        found = reports.reports_for(attdb.s1, date=attdb.monday)
        assert len(found) == 1

    def test_explained_is_true_while_a_report_stands(self, attdb):
        reports.report_absence(attdb.s1, attdb.prev_monday)
        assert reports.explained(attdb.s1, attdb.prev_monday) is True

    def test_explained_is_false_once_rejected(self, attdb):
        report = reports.report_absence(attdb.s1, attdb.prev_monday)
        reports.reject(report.report_id, reason="Not accepted")
        assert reports.explained(attdb.s1, attdb.prev_monday) is False

    def test_explained_is_false_for_an_unreported_day(self, attdb):
        assert reports.explained(attdb.s1, attdb.monday) is False

    def test_channels_are_counted(self, attdb):
        reports.report_absence(attdb.s1, attdb.prev_monday,
                               channel=reports.PHONE)
        reports.report_absence(attdb.s2, attdb.prev_monday,
                               channel=reports.PHONE)
        reports.report_absence(attdb.s3, attdb.prev_monday,
                               channel=reports.PORTAL)
        breakdown = reports.channel_breakdown()
        assert breakdown[reports.PHONE] == 2
        assert breakdown[reports.PORTAL] == 1
