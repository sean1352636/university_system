"""Tests for ExportService."""
import pytest
from education_system.secondary_school.modules.domain.admin.data_export.services.export_service import ExportService


@pytest.fixture
def export_service(db_path):
    return ExportService(db_path)


class TestExportStudents:
    def test_export_students_returns_csv(self, export_service, sample_student):
        csv = export_service.export_students()
        assert isinstance(csv, str)
        assert "John" in csv or "Doe" in csv

    def test_export_students_empty_db(self, export_service):
        # No students created, should still return valid CSV (header or empty)
        csv = export_service.export_students()
        assert isinstance(csv, str)


class TestExportGrades:
    def test_export_grades(self, export_service, sample_student, sample_subject, grade_service):
        grade_service.add_grade(student_id=sample_student["id"],
                                subject_id=sample_subject["id"], score=85.0)
        csv = export_service.export_grades()
        assert isinstance(csv, str)
        assert "85" in csv


class TestExportAttendance:
    def test_export_attendance(self, export_service, sample_student, attendance_service):
        attendance_service.record_attendance(sample_student["id"], "2026-03-20", "present")
        csv = export_service.export_attendance()
        assert isinstance(csv, str)
        assert "present" in csv


class TestExportBehaviour:
    def test_export_behaviour(self, export_service, sample_student, behaviour_service):
        behaviour_service.add_record(student_id=sample_student["id"],
                                      record_type="positive", category="effort",
                                      description="Great work", points=2)
        csv = export_service.export_behaviour()
        assert isinstance(csv, str)


class TestExportTimetable:
    def test_export_timetable(self, export_service, sample_subject, timetable_service):
        timetable_service.add_slot(
            subject_id=sample_subject["id"], day_of_week="Monday",
            period=1, year_group="9", term="Autumn",
        )
        csv = export_service.export_timetable()
        assert isinstance(csv, str)
        assert "Monday" in csv
