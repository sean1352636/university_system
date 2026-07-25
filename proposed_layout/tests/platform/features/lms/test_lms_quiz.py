"""Tests for LMS QuizService."""
import pytest
import sqlite3


@pytest.fixture
def lms_db(tmp_path):
    db = str(tmp_path / "test_lms.db")
    conn = sqlite3.connect(db)
    from education_system.platform.features.lms.schema import create_lms_tables
    create_lms_tables(conn)
    conn.close()
    return db


@pytest.fixture
def lesson_id(lms_db):
    """Create a course, module, and lesson, returning the lesson id."""
    from education_system.platform.features.lms.course_management_service import CourseManagementService
    from education_system.platform.features.lms.course_content_service import CourseContentService
    cid = CourseManagementService(lms_db).create_course("CS101", "inst1")
    mid = CourseContentService(lms_db).create_module(cid, "Module 1")
    return CourseContentService(lms_db).create_lesson(mid, "Lesson 1")


class TestQuizCreation:
    def test_create_quiz(self, lms_db, lesson_id):
        from education_system.platform.features.lms.quiz_service import QuizService
        svc = QuizService(lms_db)
        qid = svc.create_quiz(lesson_id, "Week 1 Quiz", pass_mark=60, time_limit_mins=30)
        assert qid is not None

    def test_add_question(self, lms_db, lesson_id):
        from education_system.platform.features.lms.quiz_service import QuizService
        svc = QuizService(lms_db)
        qid = svc.create_quiz(lesson_id, "Quiz 1")
        q1 = svc.add_question(qid, "What is 2+2?", "multiple_choice", "4",
                              marks=1, options=["2", "3", "4", "5"], order_index=0)
        assert q1 is not None

    def test_list_questions(self, lms_db, lesson_id):
        from education_system.platform.features.lms.quiz_service import QuizService
        svc = QuizService(lms_db)
        qid = svc.create_quiz(lesson_id, "Quiz 1")
        svc.add_question(qid, "Q1", "multiple_choice", "A", options=["A", "B"], order_index=0)
        svc.add_question(qid, "Q2", "short_answer", "Paris", order_index=1)
        questions = svc.list_questions(qid)
        assert len(questions) == 2
        assert questions[0]["question_text"] == "Q1"
        assert questions[0]["options"] == ["A", "B"]
        assert questions[1].get("options_json") is None  # no options for short answer


class TestQuizSubmission:
    def _setup_quiz(self, lms_db, lesson_id):
        from education_system.platform.features.lms.quiz_service import QuizService
        svc = QuizService(lms_db)
        qid = svc.create_quiz(lesson_id, "Quiz 1", pass_mark=50)
        q1 = svc.add_question(qid, "2+2?", "short_answer", "4", marks=2, order_index=0)
        q2 = svc.add_question(qid, "Capital of France?", "short_answer", "Paris", marks=2, order_index=1)
        return svc, qid, q1, q2

    def test_submit_perfect_score(self, lms_db, lesson_id):
        svc, qid, q1, q2 = self._setup_quiz(lms_db, lesson_id)
        result = svc.submit_quiz(qid, "stu1", {str(q1): "4", str(q2): "Paris"})
        assert result["score"] == 100
        assert result["passed"] is True
        assert result["earned"] == 4
        assert result["total"] == 4

    def test_submit_partial_score(self, lms_db, lesson_id):
        svc, qid, q1, q2 = self._setup_quiz(lms_db, lesson_id)
        result = svc.submit_quiz(qid, "stu1", {str(q1): "4", str(q2): "London"})
        assert result["score"] == 50
        assert result["passed"] is True

    def test_submit_failing_score(self, lms_db, lesson_id):
        svc, qid, q1, q2 = self._setup_quiz(lms_db, lesson_id)
        result = svc.submit_quiz(qid, "stu1", {str(q1): "5", str(q2): "London"})
        assert result["score"] == 0
        assert result["passed"] is False

    def test_get_quiz_results(self, lms_db, lesson_id):
        svc, qid, q1, q2 = self._setup_quiz(lms_db, lesson_id)
        svc.submit_quiz(qid, "stu1", {str(q1): "4", str(q2): "Paris"})
        svc.submit_quiz(qid, "stu2", {str(q1): "4", str(q2): "London"})
        all_results = svc.get_quiz_results(qid)
        assert len(all_results) == 2
        stu1_results = svc.get_quiz_results(qid, student_id="stu1")
        assert len(stu1_results) == 1

    def test_get_quiz_stats(self, lms_db, lesson_id):
        svc, qid, q1, q2 = self._setup_quiz(lms_db, lesson_id)
        svc.submit_quiz(qid, "stu1", {str(q1): "4", str(q2): "Paris"})  # 100
        svc.submit_quiz(qid, "stu2", {str(q1): "5", str(q2): "London"})  # 0
        stats = svc.get_quiz_stats(qid)
        assert stats["attempts"] == 2
        assert stats["unique_students"] == 2
        assert stats["avg_score"] == 50.0
        assert stats["pass_rate"] == 50.0
