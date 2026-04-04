"""Comprehensive tests for AttendanceService."""

import pytest
from datetime import date


class TestRecordAttendance:
    """Tests for recording attendance."""

    def test_record_attendance_present(self, attendance_service, sample_student):
        record = attendance_service.record_attendance(
            student_id=sample_student["id"],
            date_str="2026-01-15",
            status="present",
            period="AM",
        )
        assert record["status"] == "present"
        assert record["date"] == "2026-01-15"
        assert record["period"] == "AM"
        assert record["student_id"] == sample_student["id"]

    def test_record_attendance_absent(self, attendance_service, sample_student):
        record = attendance_service.record_attendance(
            student_id=sample_student["id"],
            date_str="2026-01-15",
            status="absent",
            period="AM",
        )
        assert record["status"] == "absent"

    def test_record_attendance_late(self, attendance_service, sample_student):
        record = attendance_service.record_attendance(
            student_id=sample_student["id"],
            date_str="2026-01-15",
            status="late",
            period="AM",
        )
        assert record["status"] == "late"

    def test_record_attendance_with_note(self, attendance_service, sample_student):
        record = attendance_service.record_attendance(
            student_id=sample_student["id"],
            date_str="2026-01-15",
            status="absent",
            period="AM",
            note="Medical appointment",
        )
        assert record["note"] == "Medical appointment"

    def test_record_attendance_with_recorded_by(self, attendance_service, sample_student):
        record = attendance_service.record_attendance(
            student_id=sample_student["id"],
            date_str="2026-01-15",
            status="present",
            period="AM",
            recorded_by="Mrs Smith",
        )
        assert record["recorded_by"] == "Mrs Smith"

    def test_record_attendance_with_subject(self, attendance_service, sample_student, sample_subject):
        record = attendance_service.record_attendance(
            student_id=sample_student["id"],
            date_str="2026-01-15",
            status="present",
            subject_id=sample_subject["id"],
            period="1",
        )
        assert record["subject_id"] == sample_subject["id"]

    def test_record_attendance_updates_duplicate(self, attendance_service, sample_student):
        attendance_service.record_attendance(
            student_id=sample_student["id"],
            date_str="2026-01-15",
            status="present",
            period="AM",
        )
        updated = attendance_service.record_attendance(
            student_id=sample_student["id"],
            date_str="2026-01-15",
            status="late",
            period="AM",
        )
        assert updated["status"] == "late"

    def test_record_attendance_different_periods_not_duplicate(self, attendance_service, sample_student):
        r1 = attendance_service.record_attendance(
            student_id=sample_student["id"],
            date_str="2026-01-15",
            status="present",
            period="AM",
        )
        r2 = attendance_service.record_attendance(
            student_id=sample_student["id"],
            date_str="2026-01-15",
            status="present",
            period="PM",
        )
        assert r1["id"] != r2["id"]

    def test_record_attendance_different_dates_not_duplicate(self, attendance_service, sample_student):
        r1 = attendance_service.record_attendance(
            sample_student["id"], "2026-01-15", "present", period="AM",
        )
        r2 = attendance_service.record_attendance(
            sample_student["id"], "2026-01-16", "present", period="AM",
        )
        assert r1["id"] != r2["id"]


class TestGetStudentAttendance:
    """Tests for retrieving student attendance."""

    def test_get_student_attendance_empty(self, attendance_service, sample_student):
        records = attendance_service.get_student_attendance(sample_student["id"])
        assert len(records) == 0

    def test_get_student_attendance_all(self, attendance_service, sample_student):
        attendance_service.record_attendance(sample_student["id"], "2026-01-15", "present", period="AM")
        attendance_service.record_attendance(sample_student["id"], "2026-01-16", "absent", period="AM")
        attendance_service.record_attendance(sample_student["id"], "2026-01-17", "late", period="AM")
        records = attendance_service.get_student_attendance(sample_student["id"])
        assert len(records) == 3

    def test_get_student_attendance_date_range(self, attendance_service, sample_student):
        attendance_service.record_attendance(sample_student["id"], "2026-01-10", "present", period="AM")
        attendance_service.record_attendance(sample_student["id"], "2026-01-15", "present", period="AM")
        attendance_service.record_attendance(sample_student["id"], "2026-01-20", "present", period="AM")
        records = attendance_service.get_student_attendance(
            sample_student["id"], start_date="2026-01-12", end_date="2026-01-18",
        )
        assert len(records) == 1
        assert records[0]["date"] == "2026-01-15"

    def test_get_student_attendance_start_date_only(self, attendance_service, sample_student):
        attendance_service.record_attendance(sample_student["id"], "2026-01-10", "present", period="AM")
        attendance_service.record_attendance(sample_student["id"], "2026-01-20", "present", period="AM")
        records = attendance_service.get_student_attendance(
            sample_student["id"], start_date="2026-01-15",
        )
        assert len(records) == 1
        assert records[0]["date"] == "2026-01-20"

    def test_get_student_attendance_end_date_only(self, attendance_service, sample_student):
        attendance_service.record_attendance(sample_student["id"], "2026-01-10", "present", period="AM")
        attendance_service.record_attendance(sample_student["id"], "2026-01-20", "present", period="AM")
        records = attendance_service.get_student_attendance(
            sample_student["id"], end_date="2026-01-15",
        )
        assert len(records) == 1
        assert records[0]["date"] == "2026-01-10"

    def test_get_student_attendance_ordered_by_date_desc(self, attendance_service, sample_student):
        attendance_service.record_attendance(sample_student["id"], "2026-01-10", "present", period="AM")
        attendance_service.record_attendance(sample_student["id"], "2026-01-20", "present", period="AM")
        attendance_service.record_attendance(sample_student["id"], "2026-01-15", "present", period="AM")
        records = attendance_service.get_student_attendance(sample_student["id"])
        dates = [r["date"] for r in records]
        assert dates == sorted(dates, reverse=True)


class TestAttendanceSummary:
    """Tests for attendance summary statistics."""

    def test_summary_no_records(self, attendance_service, sample_student):
        summary = attendance_service.get_attendance_summary(sample_student["id"])
        assert summary["total"] == 0
        assert summary["present"] == 0
        assert summary["absent"] == 0
        assert summary["late"] == 0
        assert summary["percentage"] == 0.0

    def test_summary_all_present(self, attendance_service, sample_student):
        for day in range(15, 20):
            attendance_service.record_attendance(
                sample_student["id"], f"2026-01-{day}", "present", period="1",
            )
        summary = attendance_service.get_attendance_summary(sample_student["id"])
        assert summary["total"] == 5
        assert summary["present"] == 5
        assert summary["absent"] == 0
        assert summary["late"] == 0
        assert summary["percentage"] == 100.0

    def test_summary_mixed_statuses(self, attendance_service, sample_student):
        attendance_service.record_attendance(sample_student["id"], "2026-01-15", "present", period="1")
        attendance_service.record_attendance(sample_student["id"], "2026-01-16", "present", period="1")
        attendance_service.record_attendance(sample_student["id"], "2026-01-17", "absent", period="1")
        attendance_service.record_attendance(sample_student["id"], "2026-01-18", "late", period="1")
        summary = attendance_service.get_attendance_summary(sample_student["id"])
        assert summary["total"] == 4
        assert summary["present"] == 2
        assert summary["absent"] == 1
        assert summary["late"] == 1
        # (2 present + 1 late) / 4 = 75%
        assert summary["percentage"] == 75.0

    def test_summary_late_counts_as_attended(self, attendance_service, sample_student):
        """Late students should be counted in the attendance percentage."""
        attendance_service.record_attendance(sample_student["id"], "2026-01-15", "late", period="1")
        attendance_service.record_attendance(sample_student["id"], "2026-01-16", "late", period="1")
        summary = attendance_service.get_attendance_summary(sample_student["id"])
        assert summary["percentage"] == 100.0

    def test_summary_all_absent(self, attendance_service, sample_student):
        attendance_service.record_attendance(sample_student["id"], "2026-01-15", "absent", period="1")
        attendance_service.record_attendance(sample_student["id"], "2026-01-16", "absent", period="1")
        summary = attendance_service.get_attendance_summary(sample_student["id"])
        assert summary["percentage"] == 0.0


class TestAttendanceByDate:
    """Tests for getting attendance by date."""

    def test_get_attendance_by_date(self, attendance_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One", year_group="7")
        s2 = student_service.create_student(first_name="B", last_name="Two", year_group="7")
        attendance_service.record_attendance(s1["id"], "2026-01-15", "present")
        attendance_service.record_attendance(s2["id"], "2026-01-15", "absent")
        records = attendance_service.get_attendance_by_date("2026-01-15")
        assert len(records) == 2

    def test_get_attendance_by_date_empty(self, attendance_service):
        records = attendance_service.get_attendance_by_date("2026-01-15")
        assert len(records) == 0

    def test_get_attendance_by_date_year_filter(self, attendance_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One", year_group="7")
        s2 = student_service.create_student(first_name="B", last_name="Two", year_group="8")
        attendance_service.record_attendance(s1["id"], "2026-01-15", "present")
        attendance_service.record_attendance(s2["id"], "2026-01-15", "present")
        records = attendance_service.get_attendance_by_date("2026-01-15", year_group="7")
        assert len(records) == 1
        assert records[0]["year_group"] == "7"

    def test_get_attendance_by_date_includes_student_info(self, attendance_service, student_service):
        s1 = student_service.create_student(first_name="Alice", last_name="Wonder", year_group="9")
        attendance_service.record_attendance(s1["id"], "2026-01-15", "present")
        records = attendance_service.get_attendance_by_date("2026-01-15")
        assert records[0]["first_name"] == "Alice"
        assert records[0]["last_name"] == "Wonder"
        assert records[0]["year_group"] == "9"


class TestCompareYearGroups:
    """Tests for comparing attendance across year groups."""

    def test_compare_year_groups(self, attendance_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One", year_group="7")
        s2 = student_service.create_student(first_name="B", last_name="Two", year_group="8")
        attendance_service.record_attendance(s1["id"], "2026-01-15", "present")
        attendance_service.record_attendance(s2["id"], "2026-01-15", "absent")
        comparison = attendance_service.compare_year_groups()
        assert len(comparison) == 2
        for entry in comparison:
            assert "year_group" in entry
            assert "total" in entry
            assert "percentage" in entry

    def test_compare_year_groups_empty(self, attendance_service):
        comparison = attendance_service.compare_year_groups()
        assert len(comparison) == 0


class TestImportFromCSV:
    """Tests for CSV import."""

    def test_import_from_csv_success(self, attendance_service, sample_student):
        rows = [
            {"student_id": str(sample_student["id"]), "date": "2026-01-15", "status": "present", "period": "AM"},
            {"student_id": str(sample_student["id"]), "date": "2026-01-16", "status": "absent", "period": "AM"},
        ]
        result = attendance_service.import_from_csv(rows)
        assert result["imported"] == 2
        assert result["errors"] == 0

    def test_import_from_csv_with_errors(self, attendance_service, sample_student):
        rows = [
            {"student_id": str(sample_student["id"]), "date": "2026-01-15", "status": "present", "period": "AM"},
            {"student_id": "invalid", "date": "2026-01-16", "status": "present", "period": "AM"},
        ]
        result = attendance_service.import_from_csv(rows)
        assert result["imported"] == 1
        assert result["errors"] == 1

    def test_import_from_csv_empty(self, attendance_service):
        result = attendance_service.import_from_csv([])
        assert result["imported"] == 0
        assert result["errors"] == 0

    def test_import_from_csv_records_are_retrievable(self, attendance_service, sample_student):
        rows = [
            {"student_id": str(sample_student["id"]), "date": "2026-01-15", "status": "present", "period": "AM"},
        ]
        attendance_service.import_from_csv(rows)
        records = attendance_service.get_student_attendance(sample_student["id"])
        assert len(records) == 1
        assert records[0]["status"] == "present"


class TestCheckDuplicateEntry:
    """Tests for duplicate entry checking."""

    def test_check_duplicate_no_records(self, attendance_service):
        assert attendance_service.check_duplicate_entry("2026-01-15", "AM", "7") is False

    def test_check_duplicate_exists(self, attendance_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One", year_group="7")
        attendance_service.record_attendance(s1["id"], "2026-01-15", "present", period="AM")
        assert attendance_service.check_duplicate_entry("2026-01-15", "AM", "7") is True

    def test_check_duplicate_different_period(self, attendance_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One", year_group="7")
        attendance_service.record_attendance(s1["id"], "2026-01-15", "present", period="AM")
        assert attendance_service.check_duplicate_entry("2026-01-15", "PM", "7") is False

    def test_check_duplicate_different_year(self, attendance_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One", year_group="7")
        attendance_service.record_attendance(s1["id"], "2026-01-15", "present", period="AM")
        assert attendance_service.check_duplicate_entry("2026-01-15", "AM", "8") is False


class TestWeeklySummary:
    """Tests for weekly attendance summary."""

    def test_weekly_summary(self, attendance_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One", year_group="7")
        # Mon-Fri of a week
        attendance_service.record_attendance(s1["id"], "2026-01-12", "present", period="AM")
        attendance_service.record_attendance(s1["id"], "2026-01-13", "present", period="AM")
        attendance_service.record_attendance(s1["id"], "2026-01-14", "absent", period="AM")
        summary = attendance_service.get_weekly_summary("7", "2026-01-12")
        assert len(summary) >= 2  # at least present and absent groups

    def test_weekly_summary_empty(self, attendance_service):
        summary = attendance_service.get_weekly_summary("7", "2026-01-12")
        assert len(summary) == 0


class TestHeatmapData:
    """Tests for student heatmap data."""

    def test_heatmap_data(self, attendance_service, sample_student):
        attendance_service.record_attendance(sample_student["id"], "2026-01-15", "present", period="AM")
        attendance_service.record_attendance(sample_student["id"], "2026-01-16", "absent", period="AM")
        data = attendance_service.get_student_heatmap_data(sample_student["id"])
        assert len(data) == 2
        assert data[0]["date"] == "2026-01-15"
        assert data[0]["status"] == "present"

    def test_heatmap_data_with_range(self, attendance_service, sample_student):
        attendance_service.record_attendance(sample_student["id"], "2026-01-10", "present", period="AM")
        attendance_service.record_attendance(sample_student["id"], "2026-01-20", "present", period="AM")
        data = attendance_service.get_student_heatmap_data(
            sample_student["id"], start_date="2026-01-15", end_date="2026-01-25",
        )
        assert len(data) == 1
        assert data[0]["date"] == "2026-01-20"

    def test_heatmap_data_empty(self, attendance_service, sample_student):
        data = attendance_service.get_student_heatmap_data(sample_student["id"])
        assert len(data) == 0


class TestPunctualityStats:
    """Tests for punctuality statistics."""

    def test_punctuality_stats(self, attendance_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One", year_group="7")
        attendance_service.record_attendance(s1["id"], "2026-01-15", "present", period="AM")
        attendance_service.record_attendance(s1["id"], "2026-01-16", "present", period="AM")
        attendance_service.record_attendance(s1["id"], "2026-01-17", "late", period="AM")
        stats = attendance_service.get_punctuality_stats("7")
        assert stats["on_time"] == 2
        assert stats["late"] == 1
        assert stats["total"] == 3

    def test_punctuality_stats_empty(self, attendance_service):
        stats = attendance_service.get_punctuality_stats("7")
        assert stats["total"] == 0 or stats["total"] is None


class TestAllStudentPercentages:
    """Tests for getting all student attendance percentages."""

    def test_all_student_percentages(self, attendance_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One", year_group="7")
        s2 = student_service.create_student(first_name="B", last_name="Two", year_group="7")
        attendance_service.record_attendance(s1["id"], "2026-01-15", "present")
        attendance_service.record_attendance(s1["id"], "2026-01-16", "absent")
        attendance_service.record_attendance(s2["id"], "2026-01-15", "present")
        percentages = attendance_service.get_all_student_percentages("7")
        assert len(percentages) == 2
        for p in percentages:
            assert "percentage" in p

    def test_students_below_threshold(self, attendance_service, student_service):
        s1 = student_service.create_student(first_name="A", last_name="One", year_group="7")
        s2 = student_service.create_student(first_name="B", last_name="Two", year_group="7")
        # s1: 50% attendance
        attendance_service.record_attendance(s1["id"], "2026-01-15", "present")
        attendance_service.record_attendance(s1["id"], "2026-01-16", "absent")
        # s2: 100% attendance
        attendance_service.record_attendance(s2["id"], "2026-01-15", "present")
        attendance_service.record_attendance(s2["id"], "2026-01-16", "present")
        below = attendance_service.get_students_below_threshold("7", threshold=90.0)
        assert len(below) == 1
        assert below[0]["first_name"] == "A"
