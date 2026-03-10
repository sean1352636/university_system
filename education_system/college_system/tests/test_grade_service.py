"""Tests for GradeService."""

import pytest
from education_system.college_system.core.exceptions import GradeError, ValidationError


class TestGradeService:
    @pytest.fixture
    def enrolled_student(self, student_service, course_service, enrollment_service):
        """Create and enroll a student."""
        student = student_service.create_student(first_name="Bob", last_name="Smith")
        course = course_service.create_course(
            course_code="TEST901", title="Intro to CS", guided_learning_hours=3,
        )
        enrollment_service.enroll_student(student["id"], course["id"])
        return student, course

    def test_record_grade(self, grade_service, enrolled_student):
        student, course = enrolled_student
        grade = grade_service.record_grade(student["id"], course["id"], 85)
        assert grade["score"] == 85
        assert grade["letter_grade"] == "A"

    def test_update_grade(self, grade_service, enrolled_student):
        student, course = enrolled_student
        grade_service.record_grade(student["id"], course["id"], 75)
        updated = grade_service.record_grade(student["id"], course["id"], 95)
        assert updated["score"] == 95
        assert updated["letter_grade"] == "A*"

    def test_score_to_letter(self, grade_service):
        assert grade_service.score_to_letter(95) == "A*"
        assert grade_service.score_to_letter(85) == "A"
        assert grade_service.score_to_letter(75) == "B"
        assert grade_service.score_to_letter(65) == "C"
        assert grade_service.score_to_letter(55) == "D"
        assert grade_service.score_to_letter(45) == "E"
        assert grade_service.score_to_letter(35) == "U"

    def test_invalid_score(self, grade_service, enrolled_student):
        student, course = enrolled_student
        with pytest.raises(ValidationError):
            grade_service.record_grade(student["id"], course["id"], 105)

    def test_grade_without_enrollment(self, grade_service, student_service, course_service):
        student = student_service.create_student(first_name="A", last_name="B")
        course = course_service.create_course(course_code="TEST901", title="CS")
        with pytest.raises(GradeError, match="not enrolled"):
            grade_service.record_grade(student["id"], course["id"], 85)

    def test_calculate_ucas_points(self, grade_service, student_service, course_service, enrollment_service):
        student = student_service.create_student(first_name="A", last_name="B")
        c1 = course_service.create_course(course_code="TEST901", title="CS", guided_learning_hours=3)
        c2 = course_service.create_course(course_code="TEST902", title="Math", guided_learning_hours=4)

        enrollment_service.enroll_student(student["id"], c1["id"])
        enrollment_service.enroll_student(student["id"], c2["id"])

        grade_service.record_grade(student["id"], c1["id"], 95)  # A* = 56
        grade_service.record_grade(student["id"], c2["id"], 85)  # A = 48

        ucas_points = grade_service.calculate_ucas_points(student["id"])
        # 56 + 48 = 104
        assert ucas_points == 104

    def test_ucas_no_grades(self, grade_service, student_service):
        student = student_service.create_student(first_name="A", last_name="B")
        assert grade_service.calculate_ucas_points(student["id"]) == 0

    def test_get_transcript(self, grade_service, enrolled_student):
        student, course = enrolled_student
        grade_service.record_grade(student["id"], course["id"], 90)

        transcript = grade_service.get_transcript(student["id"])
        assert transcript["student"]["student_id"] == student["student_id"]
        assert len(transcript["grades"]) == 1
        assert transcript["ucas_points"] > 0
        assert "total_subjects" in transcript

    def test_record_predicted_grade(self, grade_service, enrolled_student):
        student, course = enrolled_student
        result = grade_service.record_predicted_grade(
            student["id"], course["id"], "A*"
        )
        assert result["predicted_grade"] == "A*"
        assert result["grade_type"] == "predicted"

    def test_get_predicted_grades(self, grade_service, enrolled_student):
        student, course = enrolled_student
        grade_service.record_predicted_grade(
            student["id"], course["id"], "B"
        )
        predicted = grade_service.get_student_predicted_grades(student["id"])
        assert len(predicted) == 1
        assert predicted[0]["predicted_grade"] == "B"

    def test_class_statistics(self, grade_service, student_service, course_service, enrollment_service):
        course = course_service.create_course(course_code="TEST901", title="CS")
        scores = [80, 90, 70]
        for i, score in enumerate(scores):
            s = student_service.create_student(first_name=f"S{i}", last_name=f"L{i}")
            enrollment_service.enroll_student(s["id"], course["id"])
            grade_service.record_grade(s["id"], course["id"], score)

        stats = grade_service.get_class_statistics(course["id"])
        assert stats["count"] == 3
        assert stats["average"] == 80.0
        assert stats["min"] == 70
        assert stats["max"] == 90
