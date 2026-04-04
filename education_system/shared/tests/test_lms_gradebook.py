"""Tests for LMS GradebookService."""
import pytest
import sqlite3


@pytest.fixture
def lms_db(tmp_path):
    db = str(tmp_path / "test_lms.db")
    conn = sqlite3.connect(db)
    from education_system.shared.lms.schema import create_lms_tables
    create_lms_tables(conn)
    conn.close()
    return db


@pytest.fixture
def course_id(lms_db):
    from education_system.shared.lms.course_management_service import CourseManagementService
    return CourseManagementService(lms_db).create_course("CS101", "inst1")


class TestGradeEntries:
    def test_add_grade_entry(self, lms_db, course_id):
        from education_system.shared.lms.gradebook_service import GradebookService
        svc = GradebookService(lms_db)
        eid = svc.add_grade_entry(course_id, "stu1", "quiz", 1,
                                  score=85, max_score=100, weight=1.0,
                                  feedback="Good work", graded_by="inst1")
        assert eid is not None

    def test_get_student_grades(self, lms_db, course_id):
        from education_system.shared.lms.gradebook_service import GradebookService
        svc = GradebookService(lms_db)
        svc.add_grade_entry(course_id, "stu1", "quiz", 1, score=80, max_score=100)
        svc.add_grade_entry(course_id, "stu1", "assignment", 2, score=90, max_score=100)
        grades = svc.get_student_grades(course_id, "stu1")
        assert len(grades) == 2

    def test_get_student_grades_empty(self, lms_db, course_id):
        from education_system.shared.lms.gradebook_service import GradebookService
        svc = GradebookService(lms_db)
        grades = svc.get_student_grades(course_id, "stu_none")
        assert grades == []


class TestCourseGradeCalculation:
    def test_calculate_equal_weights(self, lms_db, course_id):
        from education_system.shared.lms.gradebook_service import GradebookService
        svc = GradebookService(lms_db)
        svc.add_grade_entry(course_id, "stu1", "quiz", 1, score=80, max_score=100, weight=1.0)
        svc.add_grade_entry(course_id, "stu1", "quiz", 2, score=90, max_score=100, weight=1.0)
        grade = svc.calculate_course_grade(course_id, "stu1")
        assert grade == 85.0

    def test_calculate_weighted_grades(self, lms_db, course_id):
        from education_system.shared.lms.gradebook_service import GradebookService
        svc = GradebookService(lms_db)
        # Exam worth 3x a quiz
        svc.add_grade_entry(course_id, "stu1", "quiz", 1, score=60, max_score=100, weight=1.0)
        svc.add_grade_entry(course_id, "stu1", "exam", 2, score=90, max_score=100, weight=3.0)
        grade = svc.calculate_course_grade(course_id, "stu1")
        # (0.6*1.0 + 0.9*3.0) / 4.0 * 100 = 82.5
        assert grade == 82.5

    def test_calculate_no_grades(self, lms_db, course_id):
        from education_system.shared.lms.gradebook_service import GradebookService
        svc = GradebookService(lms_db)
        assert svc.calculate_course_grade(course_id, "stu1") == 0.0

    def test_grade_with_feedback(self, lms_db, course_id):
        from education_system.shared.lms.gradebook_service import GradebookService
        svc = GradebookService(lms_db)
        svc.add_grade_entry(course_id, "stu1", "essay", 1, score=75, max_score=100,
                            feedback="Needs more detail", graded_by="inst1")
        grades = svc.get_student_grades(course_id, "stu1")
        assert grades[0]["feedback"] == "Needs more detail"
        assert grades[0]["graded_by"] == "inst1"
