"""Tests for GradeService — additional edge cases and CRUD coverage."""

import pytest

from education_system.college_system.modules.domain.grades.services.grade_service import GradeService
from education_system.college_system.core.exceptions import GradeError, ValidationError


class TestGradeRecording:
    @pytest.fixture
    def svc(self, db_path):
        return GradeService(db_path)

    @pytest.fixture
    def enrolled(self, student_service, course_service, enrollment_service):
        student = student_service.create_student(first_name="Alice", last_name="Brown")
        course = course_service.create_course(
            course_code="TEST901", title="Physics", guided_learning_hours=3,
        )
        enrollment_service.enroll_student(student["id"], course["id"])
        return student, course

    def test_record_grade(self, svc, enrolled):
        student, course = enrolled
        grade = svc.record_grade(student["id"], course["id"], 85)
        assert grade["score"] == 85
        assert grade["letter_grade"] == "A"

    def test_record_grade_updates_existing(self, svc, enrolled):
        student, course = enrolled
        svc.record_grade(student["id"], course["id"], 70)
        updated = svc.record_grade(student["id"], course["id"], 90)
        assert updated["score"] == 90
        assert updated["letter_grade"] == "A*"

    def test_record_grade_not_enrolled_raises(self, svc, student_service, course_service):
        student = student_service.create_student(first_name="X", last_name="Y")
        course = course_service.create_course(course_code="TEST901", title="Math")
        with pytest.raises(GradeError, match="not enrolled"):
            svc.record_grade(student["id"], course["id"], 80)

    def test_record_grade_invalid_score_raises(self, svc, enrolled):
        student, course = enrolled
        with pytest.raises(ValidationError):
            svc.record_grade(student["id"], course["id"], 105)

    def test_record_grade_negative_score_raises(self, svc, enrolled):
        student, course = enrolled
        with pytest.raises(ValidationError):
            svc.record_grade(student["id"], course["id"], -5)


class TestScoreToLetter:
    @pytest.fixture
    def svc(self, db_path):
        return GradeService(db_path)

    def test_a_star(self, svc):
        assert svc.score_to_letter(95) == "A*"
        assert svc.score_to_letter(100) == "A*"

    def test_a(self, svc):
        assert svc.score_to_letter(85) == "A"
        assert svc.score_to_letter(89) == "A"

    def test_b(self, svc):
        assert svc.score_to_letter(75) == "B"

    def test_c(self, svc):
        assert svc.score_to_letter(65) == "C"

    def test_d(self, svc):
        assert svc.score_to_letter(55) == "D"

    def test_e(self, svc):
        assert svc.score_to_letter(45) == "E"

    def test_u(self, svc):
        assert svc.score_to_letter(35) == "U"
        assert svc.score_to_letter(0) == "U"


class TestUCASPoints:
    @pytest.fixture
    def svc(self, db_path):
        return GradeService(db_path)

    def test_calculate_ucas_points(self, svc, student_service, course_service,
                                    enrollment_service):
        student = student_service.create_student(first_name="U", last_name="CAS")
        c1 = course_service.create_course(course_code="TEST901", title="CS",
                                           guided_learning_hours=3)
        c2 = course_service.create_course(course_code="TEST902", title="Math",
                                           guided_learning_hours=4)
        enrollment_service.enroll_student(student["id"], c1["id"])
        enrollment_service.enroll_student(student["id"], c2["id"])
        svc.record_grade(student["id"], c1["id"], 95)  # A*
        svc.record_grade(student["id"], c2["id"], 85)  # A
        points = svc.calculate_ucas_points(student["id"])
        assert points == 104  # 56 + 48

    def test_ucas_points_no_grades(self, svc, student_service):
        student = student_service.create_student(first_name="No", last_name="Grades")
        assert svc.calculate_ucas_points(student["id"]) == 0


class TestTranscript:
    @pytest.fixture
    def svc(self, db_path):
        return GradeService(db_path)

    def test_get_transcript(self, svc, student_service, course_service,
                             enrollment_service):
        student = student_service.create_student(first_name="Trans", last_name="Script")
        course = course_service.create_course(course_code="TEST901", title="English",
                                               guided_learning_hours=3)
        enrollment_service.enroll_student(student["id"], course["id"])
        svc.record_grade(student["id"], course["id"], 88)
        transcript = svc.get_transcript(student["id"])
        assert transcript["student"]["student_id"] == student["student_id"]
        assert len(transcript["grades"]) == 1
        assert transcript["ucas_points"] > 0
        assert "total_subjects" in transcript

    def test_get_transcript_empty(self, svc, student_service):
        student = student_service.create_student(first_name="No", last_name="Data")
        transcript = svc.get_transcript(student["id"])
        assert len(transcript["grades"]) == 0
        assert transcript["ucas_points"] == 0


class TestPredictedGrades:
    @pytest.fixture
    def svc(self, db_path):
        return GradeService(db_path)

    @pytest.fixture
    def enrolled(self, student_service, course_service, enrollment_service):
        student = student_service.create_student(first_name="Pred", last_name="Grade")
        course = course_service.create_course(
            course_code="TEST901", title="History", guided_learning_hours=3,
        )
        enrollment_service.enroll_student(student["id"], course["id"])
        return student, course

    def test_record_predicted_grade(self, svc, enrolled):
        student, course = enrolled
        result = svc.record_predicted_grade(student["id"], course["id"], "A*")
        assert result["predicted_grade"] == "A*"
        assert result["grade_type"] == "predicted"

    def test_get_student_predicted_grades(self, svc, enrolled):
        student, course = enrolled
        svc.record_predicted_grade(student["id"], course["id"], "B")
        predicted = svc.get_student_predicted_grades(student["id"])
        assert len(predicted) == 1
        assert predicted[0]["predicted_grade"] == "B"


class TestClassStatistics:
    @pytest.fixture
    def svc(self, db_path):
        return GradeService(db_path)

    def test_get_class_statistics(self, svc, student_service, course_service,
                                   enrollment_service):
        course = course_service.create_course(course_code="TEST901", title="Stats")
        scores = [80, 90, 70, 60]
        for i, score in enumerate(scores):
            s = student_service.create_student(first_name=f"S{i}", last_name=f"L{i}")
            enrollment_service.enroll_student(s["id"], course["id"])
            svc.record_grade(s["id"], course["id"], score)
        stats = svc.get_class_statistics(course["id"])
        assert stats["count"] == 4
        assert stats["average"] == 75.0
        assert stats["min"] == 60
        assert stats["max"] == 90

    def test_get_class_statistics_no_grades(self, svc, sample_course):
        stats = svc.get_class_statistics(sample_course["id"])
        assert stats["count"] == 0
