"""Tests for the AI Study Companion service.

Runs against the autouse isolated DB (DEFAULT_DB_PATH patched by the
university_system conftest). ``log_activity`` is patched to a no-op so tests
don't depend on the audit sink's schema.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

MODULE = (
    "education_system.post_18.university_system.modules.domain.academics."
    "ai_study.services.ai_study_service"
)


@pytest.fixture()
def service():
    with patch(f"{MODULE}.log_activity"):
        from education_system.post_18.university_system.modules.domain.academics.ai_study.services.ai_study_service import (
            AIStudyService,
        )
        yield AIStudyService()


def _future(days):
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


# ------------------------------------------------------------- Study plans
class TestStudyPlans:
    def test_generate_study_plan(self, service):
        result = service.generate_study_plan("S1", "CS101", _future(10), hours_per_day=2)
        assert result["days_until_exam"] in (9, 10)
        assert result["total_hours"] == result["days_until_exam"] * 2
        assert result["tasks_generated"] == result["days_until_exam"]
        assert result["plan_id"] > 0

    def test_generate_plan_past_date_raises(self, service):
        with pytest.raises(ValueError):
            service.generate_study_plan("S1", None, _future(-5))

    def test_get_study_plan_roundtrip(self, service):
        result = service.generate_study_plan("S2", None, _future(5))
        fetched = service.get_study_plan(result["plan_id"])
        assert fetched is not None
        assert fetched["plan"]["student_id"] == "S2"
        assert len(fetched["tasks"]) == result["tasks_generated"]

    def test_get_study_plan_missing(self, service):
        assert service.get_study_plan(99999) is None

    def test_complete_task_updates_flag(self, service):
        result = service.generate_study_plan("S3", None, _future(3))
        plan = service.get_study_plan(result["plan_id"])
        task_id = plan["tasks"][0]["task_id"]
        assert service.complete_study_task(task_id) is True
        refreshed = service.get_study_plan(result["plan_id"])
        completed = [t for t in refreshed["tasks"] if t["task_id"] == task_id][0]
        assert completed["completed"] == 1


# --------------------------------------------------------------- Flashcards
class TestFlashcards:
    def test_create_and_due(self, service):
        fid = service.create_flashcard("S1", "CS101", "Deck A", "Q?", "A!")
        assert fid > 0
        # next_review is tomorrow, so not yet due
        assert service.get_due_flashcards("S1") == []

    def test_review_correct_increases_interval(self, service):
        fid = service.create_flashcard("S1", None, "Deck A", "Q", "A")
        r1 = service.review_flashcard(fid, correct=True)
        assert r1["review_count"] == 1
        assert r1["days_until_next"] == 3  # intervals[min(1, ...)]

    def test_review_incorrect_resets(self, service):
        fid = service.create_flashcard("S1", None, "Deck A", "Q", "A")
        service.review_flashcard(fid, correct=True)
        r = service.review_flashcard(fid, correct=False)
        assert r["days_until_next"] == 1

    def test_get_decks_statistics(self, service):
        service.create_flashcard("S7", "C1", "Deck X", "Q1", "A1")
        service.create_flashcard("S7", "C1", "Deck X", "Q2", "A2")
        decks = service.get_flashcard_decks("S7")
        assert len(decks) == 1
        assert decks[0]["deck_name"] == "Deck X"
        assert decks[0]["total_cards"] == 2


# ------------------------------------------------------------ Explanations
class TestExplanations:
    def test_explain_concept_returns_text(self, service):
        result = service.explain_concept("S1", None, "Recursion", "Beginner")
        assert result["concept_name"] == "Recursion"
        assert "Recursion" in result["explanation"]
        assert result["explanation_id"] > 0

    def test_explain_unknown_level_falls_back_to_beginner(self, service):
        result = service.explain_concept("S1", None, "Topic", "Nonsense")
        assert "Simple Explanation" in result["explanation"]

    def test_rate_explanation_valid(self, service):
        result = service.explain_concept("S1", None, "Topic")
        assert service.rate_explanation(result["explanation_id"], 4) is True

    def test_rate_explanation_out_of_range(self, service):
        result = service.explain_concept("S1", None, "Topic")
        with pytest.raises(ValueError):
            service.rate_explanation(result["explanation_id"], 9)

    def test_explanation_history(self, service):
        service.explain_concept("S8", None, "A")
        service.explain_concept("S8", None, "B")
        history = service.get_explanation_history("S8")
        assert len(history) == 2


# ------------------------------------------------------------- Analytics
class TestAnalytics:
    def test_analytics_shape(self, service):
        service.generate_study_plan("S1", None, _future(4))
        service.create_flashcard("S1", None, "D", "Q", "A")
        analytics = service.get_study_analytics("S1")
        assert analytics["study_plans"]["total_plans"] == 1
        assert analytics["flashcards"]["total_cards"] == 1
