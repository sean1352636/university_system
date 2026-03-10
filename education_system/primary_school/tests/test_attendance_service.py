"""Tests for AttendanceService in the Primary School Management System."""

import pytest

from education_system.primary_school.core.exceptions import AttendanceError


class TestRecordAttendance:
    """Tests for recording attendance marks."""

    def test_record_present_am(self, attendance_service, sample_pupil):
        """Recording an AM present mark should succeed."""
        result = attendance_service.record_attendance(
            pupil_id=sample_pupil["pupil_id"],
            date="2026-03-10",
            session="AM",
            status="/",
        )
        assert result["record_id"] is not None
        assert result["pupil_id"] == sample_pupil["pupil_id"]
        assert result["date"] == "2026-03-10"
        assert result["status"] == "/"

    def test_record_present_pm(self, attendance_service, sample_pupil):
        """Recording a PM present mark should succeed."""
        result = attendance_service.record_attendance(
            pupil_id=sample_pupil["pupil_id"],
            date="2026-03-10",
            session="PM",
            status="\\",
        )
        assert result["status"] == "\\"

    def test_record_illness_absence(self, attendance_service, sample_pupil):
        """Recording an illness absence should succeed."""
        result = attendance_service.record_attendance(
            pupil_id=sample_pupil["pupil_id"],
            date="2026-03-10",
            session="AM",
            status="I",
            note="Sent home with a temperature",
        )
        assert result["status"] == "I"

    def test_record_late_mark(self, attendance_service, sample_pupil):
        """Recording a late mark should succeed."""
        result = attendance_service.record_attendance(
            pupil_id=sample_pupil["pupil_id"],
            date="2026-03-10",
            session="AM",
            status="L",
            note="Arrived at 9:15",
            recorded_by="Mrs Smith",
        )
        assert result["status"] == "L"

    def test_record_unauthorised_absence(self, attendance_service, sample_pupil):
        """Recording an unauthorised absence should succeed."""
        result = attendance_service.record_attendance(
            pupil_id=sample_pupil["pupil_id"],
            date="2026-03-10",
            session="AM",
            status="O",
        )
        assert result["status"] == "O"

    def test_record_authorised_holiday(self, attendance_service, sample_pupil):
        """Recording an authorised holiday should succeed."""
        result = attendance_service.record_attendance(
            pupil_id=sample_pupil["pupil_id"],
            date="2026-03-10",
            session="AM",
            status="H",
        )
        assert result["status"] == "H"

    def test_record_duplicate_raises(self, attendance_service, sample_pupil):
        """Recording a duplicate attendance entry should raise AttendanceError."""
        attendance_service.record_attendance(
            sample_pupil["pupil_id"], "2026-03-10", "AM", "/",
        )
        with pytest.raises(AttendanceError):
            attendance_service.record_attendance(
                sample_pupil["pupil_id"], "2026-03-10", "AM", "/",
            )

    def test_record_missing_pupil_id_raises(self, attendance_service):
        """Missing pupil ID should raise AttendanceError."""
        with pytest.raises(AttendanceError):
            attendance_service.record_attendance(
                pupil_id=None, date="2026-03-10", session="AM",
            )

    def test_record_missing_date_raises(self, attendance_service, sample_pupil):
        """Missing date should raise AttendanceError."""
        with pytest.raises(AttendanceError):
            attendance_service.record_attendance(
                pupil_id=sample_pupil["pupil_id"], date=None, session="AM",
            )

    def test_record_default_session_and_status(self, attendance_service, sample_pupil):
        """Default session should be AM and default status should be /."""
        result = attendance_service.record_attendance(
            pupil_id=sample_pupil["pupil_id"],
            date="2026-03-10",
        )
        records = attendance_service.get_attendance(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert len(records) == 1
        assert records[0]["session"] == "AM"
        assert records[0]["status"] == "/"


class TestGetAttendance:
    """Tests for retrieving attendance records."""

    def test_get_by_pupil_id(self, attendance_service, sample_pupil):
        """Filtering by pupil ID should return only that pupil's records."""
        attendance_service.record_attendance(
            sample_pupil["pupil_id"], "2026-03-10", "AM", "/",
        )
        records = attendance_service.get_attendance(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert len(records) == 1

    def test_get_by_date(self, attendance_service, sample_pupil):
        """Filtering by date should return only records for that date."""
        attendance_service.record_attendance(
            sample_pupil["pupil_id"], "2026-03-10", "AM", "/",
        )
        attendance_service.record_attendance(
            sample_pupil["pupil_id"], "2026-03-11", "AM", "/",
        )
        records = attendance_service.get_attendance(date="2026-03-10")
        assert len(records) == 1

    def test_get_by_session(self, attendance_service, sample_pupil):
        """Filtering by session should return only AM or PM records."""
        attendance_service.record_attendance(
            sample_pupil["pupil_id"], "2026-03-10", "AM", "/",
        )
        attendance_service.record_attendance(
            sample_pupil["pupil_id"], "2026-03-10", "PM", "\\",
        )
        am_records = attendance_service.get_attendance(
            pupil_id=sample_pupil["pupil_id"], session="AM",
        )
        assert len(am_records) == 1
        assert am_records[0]["session"] == "AM"

    def test_get_multiple_days(self, attendance_service, sample_pupil):
        """Should return records across multiple dates."""
        for day in range(10, 15):
            attendance_service.record_attendance(
                sample_pupil["pupil_id"], f"2026-03-{day}", "AM", "/",
            )
        records = attendance_service.get_attendance(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert len(records) == 5

    def test_get_empty_results(self, attendance_service):
        """Getting attendance from empty database should return empty list."""
        records = attendance_service.get_attendance()
        assert records == []


class TestUpdateAttendance:
    """Tests for updating attendance records."""

    def test_update_status(self, attendance_service, sample_pupil):
        """Updating an attendance status should persist."""
        result = attendance_service.record_attendance(
            sample_pupil["pupil_id"], "2026-03-10", "AM", "/",
        )
        updated = attendance_service.update_attendance(
            result["record_id"], status="L",
        )
        assert updated["status"] == "L"

    def test_update_note(self, attendance_service, sample_pupil):
        """Updating an attendance note should persist."""
        result = attendance_service.record_attendance(
            sample_pupil["pupil_id"], "2026-03-10", "AM", "L",
        )
        updated = attendance_service.update_attendance(
            result["record_id"], note="Arrived late due to traffic",
        )
        assert updated["note"] == "Arrived late due to traffic"

    def test_update_no_valid_fields(self, attendance_service, sample_pupil):
        """Updating with no valid fields should return None."""
        result = attendance_service.record_attendance(
            sample_pupil["pupil_id"], "2026-03-10", "AM", "/",
        )
        updated = attendance_service.update_attendance(
            result["record_id"], invalid="test",
        )
        assert updated is None


class TestPupilAttendanceSummary:
    """Tests for the pupil attendance summary."""

    def test_summary_counts(self, attendance_service, sample_pupil):
        """Summary should count different attendance statuses correctly."""
        pid = sample_pupil["pupil_id"]
        # 3 present, 1 illness, 1 late
        attendance_service.record_attendance(pid, "2026-03-10", "AM", "/")
        attendance_service.record_attendance(pid, "2026-03-10", "PM", "\\")
        attendance_service.record_attendance(pid, "2026-03-11", "AM", "/")
        attendance_service.record_attendance(pid, "2026-03-11", "PM", "I")
        attendance_service.record_attendance(pid, "2026-03-12", "AM", "L")

        summary = attendance_service.get_pupil_attendance_summary(pid)
        assert summary["total"] == 5
        assert summary["present"] == 3
        assert summary["absent_authorised"] == 1  # illness
        assert summary["late"] == 1

    def test_summary_empty(self, attendance_service, sample_pupil):
        """Summary for a pupil with no records should have zero total."""
        summary = attendance_service.get_pupil_attendance_summary(
            sample_pupil["pupil_id"],
        )
        assert summary["total"] == 0
        # SUM returns None when no rows match the CASE expression
        assert summary["present"] in (0, None)


class TestClassRegister:
    """Tests for the class register view."""

    def test_class_register_with_attendance(self, attendance_service, pupil_service,
                                             class_service):
        """Class register should show pupils with their attendance marks."""
        class_service.create_class("RA", "Reception", room="Room 1")
        p1 = pupil_service.create_pupil("Alice", "Adams", "Reception", class_name="RA")
        p2 = pupil_service.create_pupil("Ben", "Baker", "Reception", class_name="RA")

        attendance_service.record_attendance(p1["pupil_id"], "2026-03-10", "AM", "/")
        attendance_service.record_attendance(p2["pupil_id"], "2026-03-10", "AM", "I")

        register = attendance_service.get_class_register("RA", "2026-03-10")
        assert len(register) == 2
        statuses = {r["pupil_id"]: r["status"] for r in register}
        assert statuses[p1["pupil_id"]] == "/"
        assert statuses[p2["pupil_id"]] == "I"

    def test_class_register_no_attendance(self, attendance_service, pupil_service,
                                           class_service):
        """Class register for a date with no marks should show pupils with None status."""
        class_service.create_class("1B", "Year 1", room="Room 5")
        pupil_service.create_pupil("Charlie", "Clark", "Year 1", class_name="1B")

        register = attendance_service.get_class_register("1B", "2026-03-10")
        assert len(register) == 1
        assert register[0]["status"] is None

    def test_class_register_empty_class(self, attendance_service, class_service):
        """Class register for a class with no pupils should be empty."""
        class_service.create_class("6Z", "Year 6")
        register = attendance_service.get_class_register("6Z", "2026-03-10")
        assert register == []
