"""Tests for ReportService."""

import pytest


class TestAttendanceSummary:
    """Tests for attendance summary report."""

    def test_attendance_summary_returns_stats_with_percentages(
        self, report_service, attendance_service, sample_student, sample_subject,
        enrollment_service,
    ):
        enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
        # Record some attendance
        attendance_service.record_attendance(
            sample_student["id"], date_str="2025-10-01", status="present",
            subject_id=sample_subject["id"],
        )
        attendance_service.record_attendance(
            sample_student["id"], date_str="2025-10-02", status="present",
            subject_id=sample_subject["id"],
        )
        attendance_service.record_attendance(
            sample_student["id"], date_str="2025-10-03", status="absent",
            subject_id=sample_subject["id"],
        )
        attendance_service.record_attendance(
            sample_student["id"], date_str="2025-10-04", status="late",
            subject_id=sample_subject["id"],
        )
        summary = report_service.attendance_summary()
        assert len(summary) >= 1
        student_row = [s for s in summary if s["sid"] == sample_student["student_id"]][0]
        assert student_row["total"] == 4
        assert student_row["present"] == 2
        assert student_row["absent"] == 1
        assert student_row["late"] == 1
        assert student_row["pct"] == 50.0


class TestGradeSummary:
    """Tests for grade summary report."""

    def test_grade_summary_returns_average_scores(
        self, report_service, grade_service, sample_student, sample_subject,
        enrollment_service,
    ):
        enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
        grade_service.add_grade(
            student_id=sample_student["id"], subject_id=sample_subject["id"],
            score=80.0,
        )
        grade_service.add_grade(
            student_id=sample_student["id"], subject_id=sample_subject["id"],
            score=60.0,
        )
        summary = report_service.grade_summary()
        assert len(summary) >= 1
        row = summary[0]
        assert row["avg_score"] == 70.0
        assert row["assessments"] == 2
        assert row["subject_title"] == "Mathematics"


class TestBehaviourSummary:
    """Tests for behaviour summary report."""

    def test_behaviour_summary_returns_point_totals(
        self, report_service, behaviour_service, sample_student
    ):
        behaviour_service.add_record(
            student_id=sample_student["id"], record_type="positive",
            category="Helpful", points=5, recorded_by="Staff",
        )
        behaviour_service.add_record(
            student_id=sample_student["id"], record_type="negative",
            category="Late", points=2, recorded_by="Staff",
        )
        summary = report_service.behaviour_summary()
        assert len(summary) >= 1
        row = [s for s in summary if s["sid"] == sample_student["student_id"]][0]
        assert row["positive_pts"] == 5
        assert row["negative_pts"] == 2
        assert row["total_incidents"] == 2


class TestSubjectPerformance:
    """Tests for subject performance report."""

    def test_subject_performance_returns_stats(
        self, report_service, grade_service, student_service,
        sample_subject, enrollment_service,
    ):
        s1 = student_service.create_student(first_name="A", last_name="One")
        s2 = student_service.create_student(first_name="B", last_name="Two")
        enrollment_service.enroll_student(s1["id"], sample_subject["id"])
        enrollment_service.enroll_student(s2["id"], sample_subject["id"])
        grade_service.add_grade(
            student_id=s1["id"], subject_id=sample_subject["id"], score=90.0,
        )
        grade_service.add_grade(
            student_id=s2["id"], subject_id=sample_subject["id"], score=70.0,
        )
        perf = report_service.subject_performance()
        assert len(perf) >= 1
        maths = [p for p in perf if p["subject_code"] == "MAT01"][0]
        assert maths["students"] == 2
        assert maths["avg_score"] == 80.0
        assert maths["min_score"] == 70.0
        assert maths["max_score"] == 90.0


class TestYearGroupOverview:
    """Tests for year group overview report."""

    def test_year_group_overview_returns_counts(
        self, report_service, student_service
    ):
        student_service.create_student(
            first_name="A", last_name="One", year_group="9",
        )
        student_service.create_student(
            first_name="B", last_name="Two", year_group="9",
        )
        student_service.create_student(
            first_name="C", last_name="Three", year_group="10",
        )
        overview = report_service.year_group_overview()
        assert len(overview) >= 2
        y9 = [o for o in overview if o["year_group"] == "9"][0]
        assert y9["total"] >= 2
        assert "active" in y9
        assert "sen" in y9
