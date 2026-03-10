"""Tests for ExamsService."""

import pytest


class TestExamsService:
    @pytest.fixture
    def exams_service(self, db_path):
        from education_system.college_system.modules.domain.exams.services.exams_service import ExamsService
        return ExamsService(db_path)

    def test_create_entry(self, exams_service, sample_student, sample_course):
        entry = exams_service.create_entry(
            student_id=sample_student["id"],
            course_id=sample_course["id"],
            exam_board="AQA",
            qualification="A-Level", exam_series="June 2026",
        )
        assert entry["exam_board"] == "AQA"
        assert entry["course_id"] == sample_course["id"]

    def test_list_entries(self, exams_service, sample_student, sample_course):
        exams_service.create_entry(
            student_id=sample_student["id"],
            course_id=sample_course["id"],
            exam_board="AQA",
            qualification="A-Level", exam_series="June 2026",
        )
        entries = exams_service.list_entries(student_id=sample_student["id"])
        assert len(entries) >= 1

    def test_update_entry_status(self, exams_service, sample_student, sample_course):
        entry = exams_service.create_entry(
            student_id=sample_student["id"],
            course_id=sample_course["id"],
            exam_board="OCR",
            qualification="A-Level", exam_series="June 2026",
        )
        updated = exams_service.update_entry_status(entry["id"], status="entered")
        assert updated["status"] == "entered"

    def test_create_timetable_slot(self, exams_service, sample_student, sample_course):
        entry = exams_service.create_entry(
            student_id=sample_student["id"],
            course_id=sample_course["id"],
            exam_board="AQA",
            qualification="A-Level",
        )
        slot = exams_service.create_timetable_slot(
            exam_entry_id=entry["id"],
            exam_date="2026-06-10", start_time="09:00",
            duration_minutes=120, room="Main Hall",
        )
        assert slot["exam_date"] == "2026-06-10"
        assert slot["duration_minutes"] == 120

    def test_list_timetable(self, exams_service, sample_student, sample_course):
        entry = exams_service.create_entry(
            student_id=sample_student["id"],
            course_id=sample_course["id"],
            exam_board="AQA",
            qualification="A-Level",
        )
        exams_service.create_timetable_slot(
            exam_entry_id=entry["id"],
            exam_date="2026-06-10", start_time="09:00", duration_minutes=90,
        )
        slots = exams_service.list_timetable()
        assert len(slots) >= 1

    def test_record_result(self, exams_service, sample_student, sample_course):
        result = exams_service.record_result(
            student_id=sample_student["id"],
            course_id=sample_course["id"],
            exam_board="AQA",
            qualification="A-Level", grade="A*",
            series="June 2026",
        )
        assert result["grade"] == "A*"

    def test_get_student_results(self, exams_service, sample_student, sample_course):
        exams_service.record_result(
            student_id=sample_student["id"],
            course_id=sample_course["id"],
            exam_board="AQA",
            qualification="A-Level", grade="A",
        )
        results = exams_service.get_student_results(sample_student["id"])
        assert len(results) >= 1
