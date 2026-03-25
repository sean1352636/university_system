"""Tests for ExamService."""

import pytest
from education_system.secondary_school.core.exceptions import ExamError


class TestCreateExam:
    """Tests for creating exams."""

    def test_create_exam_valid(self, exam_service, sample_subject):
        exam = exam_service.create_exam(
            subject_id=sample_subject["id"],
            title="Mock GCSE Maths",
            exam_type="mock",
            year_group="11",
            date="2025-11-20",
            start_time="09:00",
            duration_minutes=120,
            room="Main Hall",
            total_marks=80,
        )
        assert exam["title"] == "Mock GCSE Maths"
        assert exam["subject_title"] == "Mathematics"
        assert exam["exam_type"] == "mock"
        assert exam["year_group"] == "11"
        assert exam["total_marks"] == 80

    def test_create_exam_invalid_type_raises(self, exam_service, sample_subject):
        with pytest.raises(ExamError, match="Invalid exam type"):
            exam_service.create_exam(
                subject_id=sample_subject["id"],
                title="Bad Exam",
                exam_type="invalid_type",
            )

    def test_create_exam_returns_subject_title(self, exam_service, sample_subject):
        exam = exam_service.create_exam(
            subject_id=sample_subject["id"],
            title="Class Test",
            exam_type="class_test",
        )
        assert "subject_title" in exam
        assert exam["subject_title"] == "Mathematics"
        assert exam["subject_code"] == "MAT01"


class TestListExams:
    """Tests for listing exams."""

    def test_list_exams_returns_created(self, exam_service, sample_subject):
        exam_service.create_exam(
            subject_id=sample_subject["id"], title="Test 1", exam_type="class_test",
        )
        exam_service.create_exam(
            subject_id=sample_subject["id"], title="Test 2", exam_type="mock",
        )
        exams = exam_service.list_exams()
        assert len(exams) >= 2
        titles = [e["title"] for e in exams]
        assert "Test 1" in titles
        assert "Test 2" in titles

    def test_list_exams_filters_by_year_group(self, exam_service, sample_subject):
        exam_service.create_exam(
            subject_id=sample_subject["id"], title="Year 9 Exam",
            exam_type="end_of_term", year_group="9",
        )
        exam_service.create_exam(
            subject_id=sample_subject["id"], title="Year 10 Exam",
            exam_type="end_of_term", year_group="10",
        )
        y9 = exam_service.list_exams(year_group="9")
        assert all(e["year_group"] == "9" for e in y9)
        assert any(e["title"] == "Year 9 Exam" for e in y9)


class TestUpdateExam:
    """Tests for updating exams."""

    def test_update_exam_changes_fields(self, exam_service, sample_exam):
        updated = exam_service.update_exam(
            sample_exam["id"], title="Updated Title", room="Room 101",
        )
        assert updated["title"] == "Updated Title"
        assert updated["room"] == "Room 101"

    def test_update_exam_no_valid_fields_raises(self, exam_service, sample_exam):
        with pytest.raises(ExamError, match="No valid fields"):
            exam_service.update_exam(sample_exam["id"], bogus_field="nope")


class TestUpdateExamStatus:
    """Tests for updating exam status."""

    def test_update_exam_status_valid(self, exam_service, sample_exam):
        exam_service.update_exam_status(sample_exam["id"], "completed")
        exams = exam_service.list_exams()
        found = [e for e in exams if e["id"] == sample_exam["id"]]
        assert found[0]["status"] == "completed"

    def test_update_exam_status_invalid_raises(self, exam_service, sample_exam):
        with pytest.raises(ExamError, match="Invalid status"):
            exam_service.update_exam_status(sample_exam["id"], "bogus_status")


class TestDeleteExam:
    """Tests for deleting exams."""

    def test_delete_exam_removes_exam_and_results(
        self, exam_service, sample_exam, sample_student
    ):
        # Record a result first
        exam_service.record_result(
            sample_exam["id"], sample_student["id"], marks_obtained=75, grade="7",
        )
        exam_service.delete_exam(sample_exam["id"])
        exams = exam_service.list_exams()
        assert all(e["id"] != sample_exam["id"] for e in exams)
        results = exam_service.get_exam_results(sample_exam["id"])
        assert len(results) == 0


class TestRecordResult:
    """Tests for recording exam results."""

    def test_record_result_creates_new(self, exam_service, sample_exam, sample_student):
        result = exam_service.record_result(
            sample_exam["id"], sample_student["id"],
            marks_obtained=85.0, grade="8",
        )
        assert result["marks_obtained"] == 85.0
        assert result["grade"] == "8"
        assert result["exam_id"] == sample_exam["id"]
        assert result["student_id"] == sample_student["id"]

    def test_record_result_upserts_existing(
        self, exam_service, sample_exam, sample_student
    ):
        exam_service.record_result(
            sample_exam["id"], sample_student["id"],
            marks_obtained=60.0, grade="6",
        )
        updated = exam_service.record_result(
            sample_exam["id"], sample_student["id"],
            marks_obtained=75.0, grade="7",
        )
        assert updated["marks_obtained"] == 75.0
        assert updated["grade"] == "7"
        # Should still be only one result for this student/exam
        results = exam_service.get_exam_results(sample_exam["id"])
        assert len(results) == 1

    def test_record_result_absent_flag(
        self, exam_service, sample_exam, sample_student
    ):
        result = exam_service.record_result(
            sample_exam["id"], sample_student["id"], absent=True,
        )
        assert result["absent"] == 1


class TestGetExamResults:
    """Tests for retrieving exam results."""

    def test_get_exam_results(
        self, exam_service, sample_exam, student_service, sample_subject
    ):
        s1 = student_service.create_student(first_name="A", last_name="Alpha")
        s2 = student_service.create_student(first_name="B", last_name="Beta")
        exam_service.record_result(sample_exam["id"], s1["id"], marks_obtained=90)
        exam_service.record_result(sample_exam["id"], s2["id"], marks_obtained=70)
        results = exam_service.get_exam_results(sample_exam["id"])
        assert len(results) == 2
        assert any(r["first_name"] == "A" for r in results)

    def test_get_student_exam_results(
        self, exam_service, sample_subject, sample_student
    ):
        e1 = exam_service.create_exam(
            subject_id=sample_subject["id"], title="Test A", exam_type="class_test",
        )
        e2 = exam_service.create_exam(
            subject_id=sample_subject["id"], title="Test B", exam_type="mock",
        )
        exam_service.record_result(e1["id"], sample_student["id"], marks_obtained=80)
        exam_service.record_result(e2["id"], sample_student["id"], marks_obtained=90)
        results = exam_service.get_student_exam_results(sample_student["id"])
        assert len(results) == 2
        assert any(r["exam_title"] == "Test A" for r in results)
        assert any(r["exam_title"] == "Test B" for r in results)
