"""Tests for the AI Study Companion service.

Runs against the autouse isolated DB (DEFAULT_DB_PATH patched by the
university conftest). ``log_activity`` is patched on the module that defines
the service (``study_hub.services.planning``) — the old tests patched it on
the ``ai_study_service`` re-export, which has no such attribute.
"""

from datetime import date, timedelta

import pytest

from datetime import date as _date, timedelta as _timedelta


def day(offset: int) -> str:
    return (_date.today() + _timedelta(days=offset)).isoformat()


# ------------------------------------------------------------- Study plans
class TestStudyPlans:
    def test_generate_study_plan(self, service):
        result = service.generate_study_plan("S1", "CS101", day(10), hours_per_day=2)
        assert result["days_until_exam"] == 10
        # One study day per day before the exam; nothing on the exam day.
        assert result["tasks_generated"] >= 10
        assert result["plan_id"] > 0
        plan = service.get_study_plan(result["plan_id"])
        dates = {t["scheduled_date"] for t in plan["tasks"]}
        assert day(10) not in dates and day(0) in dates and day(9) in dates

    def test_generate_plan_past_date_raises(self, service):
        with pytest.raises(ValueError):
            service.generate_study_plan("S1", None, day(-5))

    def test_hours_per_day_validated(self, service):
        with pytest.raises(ValueError):
            service.generate_study_plan("S1", None, day(5), hours_per_day=0)

    def test_plan_is_deterministic_not_random(self, service):
        a = service.get_study_plan(service.generate_study_plan("S1", "CS101", day(8))["plan_id"])
        b = service.get_study_plan(service.generate_study_plan("S2", "CS101", day(8))["plan_id"])
        assert [t["task_title"] for t in a["tasks"]] == [t["task_title"] for t in b["tasks"]]

    def test_phases_and_final_review(self, service):
        plan = service.get_study_plan(service.generate_study_plan("S1", None, day(10))["plan_id"])
        kinds = [t["task_kind"] for t in plan["tasks"]]
        assert kinds[0] == "learn"
        assert "practice" in kinds and "review" in kinds
        assert plan["tasks"][-1]["task_kind"] == "final"

    def test_topics_come_from_module_specification(self, service, student):
        plan = service.get_study_plan(service.generate_study_plan(student, "CS101", day(6))["plan_id"])
        topics = {t["topic"] for t in plan["tasks"] if t["topic"]}
        assert topics <= {"Recursion", "Loops", "Hash tables"} and topics

    def test_exam_and_deadline_aware(self, service, student, db):
        _, transaction = db
        with transaction() as conn:
            conn.execute("INSERT INTO exams (module_code, date, start_time, end_time, room) "
                         "VALUES ('CS101', ?, '09:00', '11:00', 'Hall A')", (day(10),))
            conn.execute("INSERT INTO exams (module_code, date, start_time, end_time) "
                         "VALUES ('CS102', ?, '09:00', '11:00')", (day(4),))
            conn.execute("INSERT INTO assignments (module_code, title, due_date) "
                         "VALUES ('CS101', 'Essay 1', ?)", (day(6) + " 23:59:00",))
        result = service.generate_study_plan(student, "CS101", day(10))
        assert result["exam"]["room"] == "Hall A"
        tasks = service.get_study_plan(result["plan_id"])["tasks"]
        assert not [t for t in tasks if t["scheduled_date"] == day(4)]  # CS102 exam day
        deadline = [t for t in tasks if t["task_kind"] == "deadline"]
        assert deadline and deadline[0]["scheduled_date"] == day(6)
        assert any("CS102 exam" in w for w in result["warnings"])
        assert "Hall A" in tasks[-1]["task_description"]

    def test_draft_exam_is_ignored(self, service, student, db):
        _, transaction = db
        with transaction() as conn:
            conn.execute("INSERT INTO exams (module_code, date, start_time, end_time, status) "
                         "VALUES ('CS101', ?, '09:00', '11:00', 'draft')", (day(5),))
        assert service.exam_for_module(student, "CS101") is None

    def test_second_plan_respects_first(self, service):
        service.generate_study_plan("S1", "CS101", day(6), hours_per_day=2)
        result = service.generate_study_plan("S1", "CS102", day(6), hours_per_day=2)
        assert any("already has" in w for w in result["warnings"])
        tasks = service.get_study_plan(result["plan_id"])["tasks"]
        assert all(t["duration_minutes"] <= 30 or t["task_kind"] == "final" for t in tasks)

    def test_weak_module_gets_more_time(self, service, student, db):
        _, transaction = db
        with transaction() as conn:
            conn.execute("ALTER TABLE module_grades ADD COLUMN status TEXT")
            conn.execute("INSERT INTO module_grades (student_id, module_code, final_score, status) "
                         "VALUES ('S1', 'CS102', 35, 'confirmed')")
            conn.execute("INSERT INTO module_grades (student_id, module_code, final_score, status) "
                         "VALUES ('S1', 'CS101', 20, 'provisional')")
        result = service.generate_study_plan(student, None, day(12), hours_per_day=1)
        tasks = service.get_study_plan(result["plan_id"])["tasks"]
        counts = {c: sum(1 for t in tasks if t["module_code"] == c) for c in ("CS101", "CS102")}
        assert counts["CS102"] > counts["CS101"]
        # The provisional CS101 mark must not be used (or mentioned).
        assert not any("CS101" in w for w in result["warnings"])

    def test_get_study_plan_roundtrip(self, service):
        result = service.generate_study_plan("S2", None, day(5))
        fetched = service.get_study_plan(result["plan_id"])
        assert fetched["plan"]["student_id"] == "S2"
        assert len(fetched["tasks"]) == result["tasks_generated"]
        assert fetched["progress"]["total"] == result["tasks_generated"]

    def test_get_study_plan_missing(self, service):
        assert service.get_study_plan(99999) is None

    def test_complete_task_updates_flag_and_logs_once(self, service, db):
        get_connection, _ = db
        result = service.generate_study_plan("S3", None, day(3))
        task_id = service.get_study_plan(result["plan_id"])["tasks"][0]["task_id"]
        assert service.complete_study_task(task_id, student_id="S3") is True
        service.complete_study_task(task_id, student_id="S3")
        task = [t for t in service.get_study_plan(result["plan_id"])["tasks"]
                if t["task_id"] == task_id][0]
        assert task["completed"] == 1 and task["status"] == "done"
        with get_connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM study_sessions WHERE source = 'plan_task' "
                                "AND source_id = ?", (task_id,)).fetchone()[0] == 1
        service.uncomplete_task(task_id, "S3")
        with get_connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM study_sessions WHERE source = 'plan_task' "
                                "AND source_id = ?", (task_id,)).fetchone()[0] == 0

    def test_owner_check(self, service):
        result = service.generate_study_plan("S1", None, day(3))
        task_id = service.get_study_plan(result["plan_id"])["tasks"][0]["task_id"]
        with pytest.raises(PermissionError):
            service.complete_study_task(task_id, student_id="S2")
        with pytest.raises(PermissionError):
            service.delete_plan(result["plan_id"], "S2")

    def test_plan_completes_when_all_done(self, service):
        result = service.generate_study_plan("S4", None, day(2))
        for t in service.get_study_plan(result["plan_id"])["tasks"]:
            service.complete_study_task(t["task_id"], student_id="S4")
        assert service.get_study_plan(result["plan_id"])["plan"]["status"] == "Completed"

    def test_reschedule_missed(self, service, db):
        _, transaction = db
        result = service.generate_study_plan("S1", None, day(6))
        with transaction() as conn:
            conn.execute("UPDATE study_plan_tasks SET scheduled_date = ? WHERE plan_id = ?",
                         (day(-2), result["plan_id"]))
        moved = service.reschedule_missed(result["plan_id"], "S1")
        assert moved["moved"] == result["tasks_generated"]
        tasks = service.get_study_plan(result["plan_id"])["tasks"]
        assert all(day(0) <= t["scheduled_date"] < day(6) for t in tasks)
        assert all(t["rescheduled_count"] == 1 and t["original_date"] for t in tasks)

    def test_moving_exam_earlier_skips_later_tasks(self, service):
        result = service.generate_study_plan("S1", None, day(8))
        out = service.update_plan(result["plan_id"], "S1", exam_date=day(4))
        assert out["tasks_skipped"] > 0
        plan = service.get_study_plan(result["plan_id"])
        assert plan["plan"]["end_date"] == day(4)
        assert all(t["status"] == "skipped" for t in plan["tasks"] if t["scheduled_date"] >= day(4))

    def test_status_add_edit_delete(self, service):
        result = service.generate_study_plan("S1", None, day(4))
        pid = result["plan_id"]
        assert service.set_plan_status(pid, "paused", "S1") == "Paused"
        with pytest.raises(ValueError):
            service.set_plan_status(pid, "Nonsense", "S1")
        tid = service.add_task(pid, "Read chapter 3", day(1), 45, "High", student_id="S1")
        service.update_task(tid, "S1", title="Read chapter 4", duration_minutes=50)
        service.reschedule_task(tid, day(2), "S1")
        task = [t for t in service.get_study_plan(pid)["tasks"] if t["task_id"] == tid][0]
        assert (task["task_title"], task["duration_minutes"], task["scheduled_date"]) == \
            ("Read chapter 4", 50, day(2))
        service.skip_task(tid, "S1")
        service.delete_task(tid, "S1")
        assert service.delete_plan(pid, "S1") is True
        assert service.get_study_plan(pid) is None


# --------------------------------------------------------------- Flashcards
class TestFlashcards:
    def test_create_and_due(self, service):
        fid = service.create_flashcard("S1", "CS101", "Deck A", "Q?", "A!")
        assert fid > 0
        # next_review is tomorrow, so not yet due
        assert service.get_due_flashcards("S1") == []

    def test_card_validation(self, service):
        with pytest.raises(ValueError):
            service.create_flashcard("S1", None, "Deck", "", "A")

    def test_sm2_intervals(self, service):
        fid = service.create_flashcard("S1", None, "Deck A", "Q", "A")
        assert service.review_flashcard(fid, correct=True)["days_until_next"] == 1
        assert service.review_flashcard(fid, correct=True)["days_until_next"] == 6
        third = service.review_flashcard(fid, correct=True)
        assert third["days_until_next"] == 15 and third["review_count"] == 3

    def test_review_incorrect_resets_run(self, service):
        fid = service.create_flashcard("S1", None, "Deck A", "Q", "A")
        for _ in range(3):
            service.review_flashcard(fid, correct=True)
        lapse = service.review_flashcard(fid, correct=False)
        assert lapse["days_until_next"] == 1 and lapse["correct"] is False
        # The run restarts: the next correct recall is 1 day, not a long interval.
        assert service.review_flashcard(fid, correct=True)["days_until_next"] == 1

    def test_hard_and_easy_grades_move_ease(self, service):
        hard = service.create_flashcard("S1", None, "D", "Q1", "A")
        easy = service.create_flashcard("S1", None, "D", "Q2", "A")
        h = service.review_flashcard(hard, quality="hard")
        e = service.review_flashcard(easy, quality="easy")
        assert h["ease_factor"] < 2.5 < e["ease_factor"]

    def test_reviews_are_recorded(self, service, db):
        get_connection, _ = db
        fid = service.create_flashcard("S1", None, "D", "Q", "A")
        service.review_flashcard(fid, quality="good")
        with get_connection() as conn:
            row = conn.execute("SELECT student_id, quality FROM flashcard_reviews "
                               "WHERE flashcard_id = ?", (fid,)).fetchone()
        assert tuple(row) == ("S1", 4)

    def test_due_respects_suspend_and_limit(self, service, db):
        _, transaction = db
        ids = [service.create_flashcard("S1", None, "D", f"Q{i}", "A") for i in range(5)]
        with transaction() as conn:
            conn.execute("UPDATE flashcards SET next_review = ? WHERE student_id = 'S1'", (day(0),))
        service.set_flashcard_suspended(ids[0], True, "S1")
        service.save_settings("S1", daily_card_limit=2)
        due = service.get_due_flashcards("S1")
        assert len(due) == 2 and ids[0] not in [c["flashcard_id"] for c in due]

    def test_get_decks_statistics(self, service):
        service.create_flashcard("S1", None, "Deck X", "Q1", "A1")
        service.create_flashcard("S1", None, "Deck X", "Q2", "A2")
        decks = service.get_flashcard_decks("S1")
        assert len(decks) == 1
        assert decks[0]["deck_name"] == "Deck X"
        assert decks[0]["total_cards"] == 2

    def test_generate_from_notes_without_ai(self, service):
        notes = ("Recursion: a function that calls itself.\n"
                 "A stack is a structure that is last in, first out.\n"
                 "Random sentence here.")
        result = service.generate_flashcards("S1", "CS101", "Notes", notes, 10)
        assert result["source"] == "extracted"
        assert {c["question"] for c in result["cards"]} == {"What is Recursion?", "What is stack?"}
        assert len(service.list_flashcards("S1", "Notes")) == 2

    def test_card_from_mistake(self, service):
        fid = service.create_flashcard("S1", None, "D", "Capital of France?", "Paris")
        new = service.card_from_mistake(fid, "Lyon", "S1")
        card = [c for c in service.list_flashcards("S1", "D") if c["flashcard_id"] == new][0]
        assert "Lyon" in card["question"] and card["answer"] == "Paris"
        assert card["source"] == "mistake"
        reversed_id = service.card_from_mistake(fid, None, "S1")
        rev = [c for c in service.list_flashcards("S1", "D") if c["flashcard_id"] == reversed_id][0]
        assert rev["answer"] == "Capital of France?"

    def test_edit_rename_delete(self, service):
        fid = service.create_flashcard("S1", None, "Old", "Q", "A")
        service.update_flashcard(fid, "S1", answer="B")
        assert service.rename_deck("S1", "Old", "New") == 1
        assert service.list_flashcards("S1", "New")[0]["answer"] == "B"
        with pytest.raises(PermissionError):
            service.delete_flashcard(fid, "S2")
        assert service.delete_deck("S1", "New") == 1


# --------------------------------------------------------- Concept explainer
class TestConceptExplainer:
    def test_explain_concept_without_ai_uses_course_records(self, service, student):
        result = service.explain_concept(student, "CS101", "Recursion", "Beginner")
        assert result["source"] == "course_materials"
        assert "Recursion" in result["explanation"]
        assert "First key point" not in result["explanation"]
        assert result["explanation_id"] > 0

    def test_explain_includes_own_cards(self, service):
        service.create_flashcard("S1", None, "D", "What is a monad?", "A monoid in endofunctors")
        result = service.explain_concept("S1", None, "monad")
        assert "A monoid in endofunctors" in result["explanation"]

    def test_unknown_level_falls_back_to_beginner(self, service):
        result = service.explain_concept("S1", None, "Recursion", "Expert")
        assert result["difficulty_level"] == "Beginner"

    def test_empty_concept_rejected(self, service):
        with pytest.raises(ValueError):
            service.explain_concept("S1", None, "  ")

    def test_rate_explanation_valid(self, service):
        result = service.explain_concept("S1", None, "Big-O")
        assert service.rate_explanation(result["explanation_id"], 4, student_id="S1") is True

    def test_rate_explanation_out_of_range(self, service):
        result = service.explain_concept("S1", None, "Big-O")
        with pytest.raises(ValueError):
            service.rate_explanation(result["explanation_id"], 6)

    def test_explanation_history(self, service):
        service.explain_concept("S9", None, "A")
        service.explain_concept("S9", None, "B")
        history = service.get_explanation_history("S9")
        assert len(history) == 2

    def test_flashcards_from_explanation(self, service):
        eid = service.save_explanation("S1", "Graphs", "A graph is a set of nodes and edges.\n"
                                                       "A tree is a connected acyclic graph.")
        made = service.flashcards_from_explanation(eid, student_id="S1")
        assert len(made["created"]) == 2
        with pytest.raises(PermissionError):
            service.flashcards_from_explanation(eid, student_id="S2")


# ---------------------------------------------------------------- Analytics
class TestAnalytics:
    def test_analytics_shape(self, service):
        service.generate_study_plan("S5", None, day(4))
        fid = service.create_flashcard("S5", None, "D", "Q", "A")
        service.review_flashcard(fid, quality="good")
        analytics = service.get_study_analytics("S5")
        assert analytics["study_plans"]["total_plans"] == 1
        assert analytics["flashcards"]["total_cards"] == 1
        assert analytics["reviews"] == {"last_30_days": 1, "retention_pct": 100.0}
        assert "weak_modules" in analytics and "streak_days" in analytics

    def test_schema_applied_without_activity_row(self, db):
        from unittest.mock import patch
        with patch("education_system.systems.university.domains.student_life."
                   "domain.study_hub.services.planning.log_activity") as log:
            from education_system.systems.university.domains.student_life.domain.study_hub.services.planning import (
                AIStudyService,
            )
            AIStudyService()
            AIStudyService()
        log.assert_not_called()
