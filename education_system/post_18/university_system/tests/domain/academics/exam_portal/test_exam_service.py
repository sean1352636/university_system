"""Tests for the Exam Portal service layer.

Covers exam CRUD, questions, attempts, auto-grading, manual grading,
results, analytics, integrity logging, and CSV export.
"""

import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from education_system.post_18.university_system.infrastructure.database.db import sqlite3


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _suppress_activity_logger():
    with patch(
        "education_system.post_18.university_system.modules.shared.utils.simple_activity_logger.module_api.logger"
    ) as mock_logger:
        mock_logger.log_activity = MagicMock()
        yield


@pytest.fixture()
def svc(tmp_path, monkeypatch):
    """Create an ExamPortalService backed by a temp database."""
    db_path = str(tmp_path / "test_exam.db")

    # Create a minimal DB so get_connection works. This is a throwaway
    # per-test DB, so durability doesn't matter: skip fsync-on-commit
    # (synchronous=OFF) to avoid the dominant cost in this suite — the
    # service opens a fresh connection per method call and commits each
    # time, and fsync per commit is ~5x slower than not.
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.close()

    # Patch get_connection to use our temp DB
    from contextlib import contextmanager

    @contextmanager
    def _fake_get_connection():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA synchronous=OFF")
        try:
            yield c
        finally:
            c.close()

    monkeypatch.setattr(
        "education_system.post_18.university_system.modules.domain.academics.services.exam_management.exam_service.get_connection",
        _fake_get_connection,
    )

    from education_system.post_18.university_system.modules.domain.academics.services.exam_management.exam_service import ExamPortalService
    return ExamPortalService()


# ── Exam CRUD ───────────────────────────────────────────────────────

class TestExamCRUD:
    def test_create_exam(self, svc):
        eid = svc.create_exam("Maths Final", "instructor1", duration_minutes=90)
        assert eid is not None
        assert eid > 0

    def test_get_exam(self, svc):
        eid = svc.create_exam("Physics Midterm", "instructor1")
        exam = svc.get_exam(eid)
        assert exam["title"] == "Physics Midterm"
        assert exam["status"] == "draft"
        assert exam["duration_minutes"] == 60

    def test_update_exam(self, svc):
        eid = svc.create_exam("Test", "instructor1")
        svc.update_exam(eid, title="Updated Test", duration_minutes=120)
        exam = svc.get_exam(eid)
        assert exam["title"] == "Updated Test"
        assert exam["duration_minutes"] == 120

    def test_delete_exam(self, svc):
        eid = svc.create_exam("To Delete", "instructor1")
        svc.delete_exam(eid)
        assert svc.get_exam(eid) is None

    def test_list_exams(self, svc):
        svc.create_exam("Exam A", "instructor1")
        svc.create_exam("Exam B", "instructor2")
        exams = svc.list_exams()
        assert len(exams) == 2

    def test_list_exams_filter_by_status(self, svc):
        eid = svc.create_exam("Draft Exam", "instructor1")
        svc.create_exam("Another Draft", "instructor1")
        svc.add_question(eid, "mcq", "Q?", marks=1, options=["A", "B"], correct_answer="A")
        svc.publish_exam(eid)
        assert len(svc.list_exams(status="published")) == 1
        assert len(svc.list_exams(status="draft")) == 1

    def test_publish_unpublish(self, svc):
        eid = svc.create_exam("Pub Test", "instructor1")
        svc.publish_exam(eid)
        assert svc.get_exam(eid)["status"] == "published"
        svc.unpublish_exam(eid)
        assert svc.get_exam(eid)["status"] == "draft"

    def test_create_exam_with_all_options(self, svc):
        eid = svc.create_exam(
            "Full Options", "instructor1",
            description="A test exam",
            module_code="CS101",
            duration_minutes=120,
            pass_mark=60.0,
            total_marks=200.0,
            shuffle_questions=1,
            shuffle_answers=1,
            max_attempts=3,
            instructions="Read carefully",
        )
        exam = svc.get_exam(eid)
        assert exam["module_code"] == "CS101"
        assert exam["pass_mark"] == 60.0
        assert exam["total_marks"] == 200.0
        assert exam["max_attempts"] == 3
        assert exam["shuffle_questions"] == 1


# ── Questions ───────────────────────────────────────────────────────

class TestQuestions:
    def test_add_mcq_question(self, svc):
        eid = svc.create_exam("Q Test", "inst")
        qid = svc.add_question(
            eid, "mcq", "What is 2+2?",
            marks=2.0,
            options=["3", "4", "5"],
            correct_answer="4",
        )
        assert qid > 0
        qs = svc.get_questions(eid)
        assert len(qs) == 1
        assert qs[0]["question_type"] == "mcq"
        assert qs[0]["options"] == ["3", "4", "5"]

    def test_add_true_false(self, svc):
        eid = svc.create_exam("TF", "inst")
        qid = svc.add_question(eid, "true_false", "The sky is blue.", correct_answer="True")
        qs = svc.get_questions(eid)
        assert qs[0]["correct_answer"] == "True"

    def test_add_short_answer(self, svc):
        eid = svc.create_exam("SA", "inst")
        svc.add_question(eid, "short_answer", "Capital of France?", correct_answer="Paris")
        qs = svc.get_questions(eid)
        assert qs[0]["question_type"] == "short_answer"

    def test_add_essay(self, svc):
        eid = svc.create_exam("Essay", "inst")
        svc.add_question(eid, "essay", "Discuss the causes of WWI.", marks=20)
        qs = svc.get_questions(eid)
        assert qs[0]["marks"] == 20

    def test_add_fill_blank(self, svc):
        eid = svc.create_exam("FB", "inst")
        svc.add_question(eid, "fill_blank", "Water is ___.", correct_answer="H2O")
        qs = svc.get_questions(eid)
        assert qs[0]["question_type"] == "fill_blank"

    def test_update_question(self, svc):
        eid = svc.create_exam("UQ", "inst")
        qid = svc.add_question(eid, "mcq", "Old text", options=["A"])
        svc.update_question(qid, question_text="New text", marks=5.0)
        qs = svc.get_questions(eid)
        assert qs[0]["question_text"] == "New text"
        assert qs[0]["marks"] == 5.0

    def test_delete_question(self, svc):
        eid = svc.create_exam("DQ", "inst")
        qid = svc.add_question(eid, "mcq", "Delete me")
        svc.delete_question(qid)
        assert svc.get_question_count(eid) == 0

    def test_question_count(self, svc):
        eid = svc.create_exam("Count", "inst")
        svc.add_question(eid, "mcq", "Q1")
        svc.add_question(eid, "mcq", "Q2")
        svc.add_question(eid, "mcq", "Q3")
        assert svc.get_question_count(eid) == 3

    def test_question_ordering(self, svc):
        eid = svc.create_exam("Order", "inst")
        svc.add_question(eid, "mcq", "First")
        svc.add_question(eid, "mcq", "Second")
        svc.add_question(eid, "mcq", "Third")
        qs = svc.get_questions(eid)
        assert qs[0]["question_text"] == "First"
        assert qs[2]["question_text"] == "Third"

    def test_shuffle_questions(self, svc):
        eid = svc.create_exam("Shuffle", "inst")
        for i in range(20):
            svc.add_question(eid, "mcq", f"Q{i}")
        qs_normal = [q["question_text"] for q in svc.get_questions(eid, shuffle=False)]
        # Shuffling should produce a different order (with very high probability for 20 items)
        qs_shuffled = [q["question_text"] for q in svc.get_questions(eid, shuffle=True)]
        # Both should have the same items
        assert sorted(qs_normal) == sorted(qs_shuffled)


# ── Attempts ────────────────────────────────────────────────────────

class TestAttempts:
    def _create_published_exam(self, svc, title="Test Exam"):
        eid = svc.create_exam(title, "inst", duration_minutes=30)
        svc.add_question(eid, "mcq", "Q1?", options=["A", "B"], correct_answer="A", marks=5)
        svc.add_question(eid, "true_false", "True?", correct_answer="True", marks=5)
        svc.publish_exam(eid)
        return eid

    def test_start_attempt(self, svc):
        eid = self._create_published_exam(svc)
        attempt = svc.start_attempt(eid, "student1", student_name="Alice")
        assert attempt is not None
        assert attempt["status"] == "in_progress"
        assert attempt["time_remaining"] == 30 * 60

    def test_cannot_start_on_draft_exam(self, svc):
        eid = svc.create_exam("Draft", "inst")
        attempt = svc.start_attempt(eid, "student1")
        assert attempt is None

    def test_max_attempts_enforced(self, svc):
        eid = svc.create_exam("Max1", "inst", max_attempts=1)
        svc.add_question(eid, "mcq", "Q?", options=["A"], correct_answer="A")
        svc.publish_exam(eid)

        a1 = svc.start_attempt(eid, "student1")
        assert a1 is not None
        svc.submit_attempt(a1["id"])

        a2 = svc.start_attempt(eid, "student1")
        assert a2 is None  # Max 1 attempt reached

    def test_resume_existing_attempt(self, svc):
        eid = self._create_published_exam(svc)
        a1 = svc.start_attempt(eid, "student1")
        a2 = svc.start_attempt(eid, "student1")
        assert a1["id"] == a2["id"]  # Same in-progress attempt returned

    def test_save_and_get_answers(self, svc):
        eid = self._create_published_exam(svc)
        attempt = svc.start_attempt(eid, "student1")
        qs = svc.get_questions(eid)

        svc.save_answer(attempt["id"], qs[0]["id"], "A")
        svc.save_answer(attempt["id"], qs[1]["id"], "True", flagged=True)

        answers = svc.get_answers(attempt["id"])
        assert len(answers) == 2
        assert any(a["flagged"] for a in answers)

    def test_save_answer_overwrites(self, svc):
        eid = self._create_published_exam(svc)
        attempt = svc.start_attempt(eid, "student1")
        qs = svc.get_questions(eid)

        svc.save_answer(attempt["id"], qs[0]["id"], "B")
        svc.save_answer(attempt["id"], qs[0]["id"], "A")  # Change answer

        answers = svc.get_answers(attempt["id"])
        assert len(answers) == 1
        assert answers[0]["answer_text"] == "A"

    def test_update_time_remaining(self, svc):
        eid = self._create_published_exam(svc)
        attempt = svc.start_attempt(eid, "student1")
        svc.update_time_remaining(attempt["id"], 500)
        updated = svc.get_attempt(attempt["id"])
        assert updated["time_remaining"] == 500


# ── Auto-Grading ────────────────────────────────────────────────────

class TestAutoGrading:
    def _setup_exam(self, svc):
        eid = svc.create_exam("Auto Grade", "inst", total_marks=15, pass_mark=50)
        svc.add_question(eid, "mcq", "2+2?", options=["3", "4", "5"],
                         correct_answer="4", marks=5)
        svc.add_question(eid, "true_false", "Sky is blue?",
                         correct_answer="True", marks=5)
        svc.add_question(eid, "fill_blank", "H___",
                         correct_answer="H2O", marks=5)
        svc.publish_exam(eid)
        return eid

    def test_all_correct(self, svc):
        eid = self._setup_exam(svc)
        attempt = svc.start_attempt(eid, "student1")
        qs = svc.get_questions(eid)

        svc.save_answer(attempt["id"], qs[0]["id"], "4")
        svc.save_answer(attempt["id"], qs[1]["id"], "True")
        svc.save_answer(attempt["id"], qs[2]["id"], "H2O")

        result = svc.submit_attempt(attempt["id"])
        assert result["score"] == 15.0
        assert result["percentage"] == 100.0
        assert result["passed"] is True

    def test_all_wrong(self, svc):
        eid = self._setup_exam(svc)
        attempt = svc.start_attempt(eid, "student1")
        qs = svc.get_questions(eid)

        svc.save_answer(attempt["id"], qs[0]["id"], "3")
        svc.save_answer(attempt["id"], qs[1]["id"], "False")
        svc.save_answer(attempt["id"], qs[2]["id"], "CO2")

        result = svc.submit_attempt(attempt["id"])
        assert result["score"] == 0.0
        assert result["passed"] is False

    def test_partial_score(self, svc):
        eid = self._setup_exam(svc)
        attempt = svc.start_attempt(eid, "student1")
        qs = svc.get_questions(eid)

        svc.save_answer(attempt["id"], qs[0]["id"], "4")   # correct
        svc.save_answer(attempt["id"], qs[1]["id"], "False")  # wrong
        # Q3 unanswered

        result = svc.submit_attempt(attempt["id"])
        assert result["score"] == 5.0
        assert result["percentage"] == pytest.approx(33.3, abs=0.1)

    def test_auto_submit_flag(self, svc):
        eid = self._setup_exam(svc)
        attempt = svc.start_attempt(eid, "student1")
        result = svc.submit_attempt(attempt["id"], auto=True)
        updated = svc.get_attempt(attempt["id"])
        assert updated["auto_submitted"] == 1

    def test_case_insensitive_grading(self, svc):
        eid = svc.create_exam("Case", "inst", total_marks=5, pass_mark=50)
        svc.add_question(eid, "fill_blank", "Capital?",
                         correct_answer="Paris", marks=5)
        svc.publish_exam(eid)
        attempt = svc.start_attempt(eid, "student1")
        qs = svc.get_questions(eid)
        svc.save_answer(attempt["id"], qs[0]["id"], "paris")
        result = svc.submit_attempt(attempt["id"])
        assert result["score"] == 5.0


# ── Manual Grading ──────────────────────────────────────────────────

class TestManualGrading:
    def test_essay_needs_manual_grading(self, svc):
        eid = svc.create_exam("Essay Exam", "inst", total_marks=20)
        svc.add_question(eid, "essay", "Discuss...", marks=20)
        svc.publish_exam(eid)

        attempt = svc.start_attempt(eid, "student1")
        qs = svc.get_questions(eid)
        svc.save_answer(attempt["id"], qs[0]["id"], "My essay about...")

        result = svc.submit_attempt(attempt["id"])
        assert result["needs_manual_grading"] is True
        assert result["status"] == "submitted"

    def test_grade_answer(self, svc):
        eid = svc.create_exam("Grade", "inst", total_marks=10)
        svc.add_question(eid, "essay", "Write...", marks=10)
        svc.publish_exam(eid)

        attempt = svc.start_attempt(eid, "student1")
        qs = svc.get_questions(eid)
        svc.save_answer(attempt["id"], qs[0]["id"], "My response")
        svc.submit_attempt(attempt["id"])

        answers = svc.get_answers(attempt["id"])
        svc.grade_answer(answers[0]["id"], 8.0, "Good work")

        result = svc.finalise_grading(attempt["id"], "instructor1")
        assert result["score"] == 8.0
        assert result["percentage"] == 80.0
        assert result["passed"] is True

    def test_get_ungraded_attempts(self, svc):
        eid = svc.create_exam("Ungraded", "inst")
        svc.add_question(eid, "essay", "Write...", marks=10)
        svc.publish_exam(eid)

        attempt = svc.start_attempt(eid, "student1")
        qs = svc.get_questions(eid)
        svc.save_answer(attempt["id"], qs[0]["id"], "Answer")
        svc.submit_attempt(attempt["id"])

        ungraded = svc.get_ungraded_attempts()
        assert len(ungraded) == 1
        assert ungraded[0]["id"] == attempt["id"]


# ── Results ─────────────────────────────────────────────────────────

class TestResults:
    def test_get_student_attempts(self, svc):
        eid = svc.create_exam("Results", "inst", max_attempts=5)
        svc.add_question(eid, "mcq", "Q?", options=["A"], correct_answer="A")
        svc.publish_exam(eid)

        a1 = svc.start_attempt(eid, "student1")
        svc.submit_attempt(a1["id"])
        a2 = svc.start_attempt(eid, "student1")
        svc.submit_attempt(a2["id"])

        attempts = svc.get_student_attempts("student1")
        assert len(attempts) == 2

    def test_get_exam_results(self, svc):
        eid = svc.create_exam("Multi", "inst", max_attempts=5)
        svc.add_question(eid, "mcq", "Q?", options=["A", "B"], correct_answer="A", marks=10)
        svc.publish_exam(eid)

        for sid in ["s1", "s2", "s3"]:
            a = svc.start_attempt(eid, sid)
            qs = svc.get_questions(eid)
            svc.save_answer(a["id"], qs[0]["id"], "A")
            svc.submit_attempt(a["id"])

        results = svc.get_exam_results(eid)
        assert len(results) == 3

    def test_available_exams_respects_time_window(self, svc):
        eid = svc.create_exam("Future", "inst",
                              start_time="2099-01-01 00:00",
                              end_time="2099-12-31 23:59")
        svc.add_question(eid, "mcq", "Q?", options=["A"], correct_answer="A")
        svc.publish_exam(eid)

        available = svc.list_available_exams("student1")
        # Exam is in the future, should not be available
        assert len(available) == 0


# ── Integrity ───────────────────────────────────────────────────────

class TestIntegrity:
    def test_log_integrity_event(self, svc):
        eid = svc.create_exam("Integrity", "inst")
        svc.add_question(eid, "mcq", "Q?", options=["A"], correct_answer="A")
        svc.publish_exam(eid)

        attempt = svc.start_attempt(eid, "student1")
        svc.log_integrity_event(attempt["id"], "tab_switch", "switched to another tab")
        svc.log_integrity_event(attempt["id"], "copy_paste")

        updated = svc.get_attempt(attempt["id"])
        assert updated["integrity_flags"] == 2


# ── Analytics ───────────────────────────────────────────────────────

class TestAnalytics:
    def test_exam_analytics(self, svc):
        eid = svc.create_exam("Analytics", "inst", total_marks=10, pass_mark=50,
                              max_attempts=10)
        svc.add_question(eid, "mcq", "Q1", options=["A", "B"], correct_answer="A", marks=5)
        svc.add_question(eid, "mcq", "Q2", options=["C", "D"], correct_answer="C", marks=5)
        svc.publish_exam(eid)

        # Student 1: all correct
        a1 = svc.start_attempt(eid, "s1")
        qs = svc.get_questions(eid)
        svc.save_answer(a1["id"], qs[0]["id"], "A")
        svc.save_answer(a1["id"], qs[1]["id"], "C")
        svc.submit_attempt(a1["id"])

        # Student 2: all wrong
        a2 = svc.start_attempt(eid, "s2")
        svc.save_answer(a2["id"], qs[0]["id"], "B")
        svc.save_answer(a2["id"], qs[1]["id"], "D")
        svc.submit_attempt(a2["id"])

        analytics = svc.get_exam_analytics(eid)
        assert analytics["total_attempts"] == 2
        assert analytics["average_score"] == 50.0
        assert analytics["pass_count"] == 1
        assert analytics["pass_rate"] == 50.0
        assert len(analytics["questions"]) == 2


# ── CSV Export ──────────────────────────────────────────────────────

class TestExport:
    def test_export_csv(self, svc):
        eid = svc.create_exam("Export", "inst", max_attempts=5)
        svc.add_question(eid, "mcq", "Q?", options=["A"], correct_answer="A", marks=10)
        svc.publish_exam(eid)

        attempt = svc.start_attempt(eid, "student1", student_name="Alice")
        qs = svc.get_questions(eid)
        svc.save_answer(attempt["id"], qs[0]["id"], "A")
        svc.submit_attempt(attempt["id"])

        csv = svc.export_results_csv(eid)
        lines = csv.strip().split("\n")
        assert len(lines) == 2  # header + 1 result
        assert "student1" in lines[1]
        assert "Alice" in lines[1]
