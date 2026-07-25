"""Tests for the lesson/timetable planner CRUD service."""

import pytest

from education_system.systems.university.domain.academics.course_planning.services import (
    lesson_service as svc,
)

pytestmark = pytest.mark.usefixtures("lesson_db")


# ── Lessons ──────────────────────────────────────────────────────────

class TestLessonCrud:
    def test_add_returns_id_and_get_roundtrips(self):
        lid = svc.add_lesson("CS101", "Intro", instructor="Dr Ada", day="Mon", start="09:00", end="11:00")
        assert isinstance(lid, int) and lid > 0
        row = svc.get_lesson(lid)
        assert row["course"] == "CS101"
        assert row["title"] == "Intro"
        assert row["updated_at"]  # audit stamp populated

    def test_get_missing_returns_none(self):
        assert svc.get_lesson(4242) is None

    def test_list_ordered_by_day_then_start(self):
        svc.add_lesson("B", "b", day="Tue", start="09:00", end="10:00")
        svc.add_lesson("A", "a", day="Mon", start="14:00", end="15:00")
        svc.add_lesson("C", "c", day="Mon", start="08:00", end="09:00")
        titles = [r["course"] for r in svc.list_lessons()]
        # Mon 08:00, Mon 14:00, then Tue 09:00.
        assert titles == ["C", "A", "B"]

    def test_list_search_filters_substring(self):
        svc.add_lesson("CS101", "Algorithms", instructor="Dr Ada")
        svc.add_lesson("HIS200", "History", instructor="Dr Bell")
        found = svc.list_lessons(search="ada")
        assert len(found) == 1
        assert found[0]["course"] == "CS101"

    def test_update_only_known_fields(self):
        lid = svc.add_lesson("CS101", "Intro", room="R1")
        assert svc.update_lesson(lid, room="R2", bogus="x") is True
        assert svc.get_lesson(lid)["room"] == "R2"

    def test_update_with_nothing_valid_is_false(self):
        lid = svc.add_lesson("CS101", "Intro")
        assert svc.update_lesson(lid, bogus="x") is False

    def test_delete_removes_row(self):
        lid = svc.add_lesson("CS101", "Intro")
        assert svc.delete_lesson(lid) is True
        assert svc.get_lesson(lid) is None

    def test_delete_missing_is_false(self):
        assert svc.delete_lesson(9999) is False


# ── Courses ──────────────────────────────────────────────────────────

class TestCourseCrud:
    def test_add_and_get(self):
        svc.add_course("CS101", "Intro to CS", dept="Computing", credits="15")
        row = svc.get_course("CS101")
        assert row["name"] == "Intro to CS"
        assert row["dept"] == "Computing"

    def test_duplicate_code_rejected(self):
        svc.add_course("CS101", "Intro")
        with pytest.raises(ValueError):
            svc.add_course("CS101", "Duplicate")

    def test_list_ordered_by_code(self):
        svc.add_course("CS201", "Second")
        svc.add_course("CS101", "First")
        assert [c["code"] for c in svc.list_courses()] == ["CS101", "CS201"]

    def test_update_applies_known_and_ignores_unknown_keys(self):
        svc.add_course("CS101", "Intro")
        assert svc.update_course("CS101", name="Renamed", bogus="x") is True
        assert svc.get_course("CS101")["name"] == "Renamed"
        # 'code' isn't in the honoured field set, so the row stays keyed CS101.
        assert svc.get_course("CS101") is not None

    def test_update_nothing_valid_is_false(self):
        svc.add_course("CS101", "Intro")
        assert svc.update_course("CS101", bogus="x") is False

    def test_delete_course(self):
        svc.add_course("CS101", "Intro")
        assert svc.delete_course("CS101") is True
        assert svc.get_course("CS101") is None


# ── Contact-hours summary ────────────────────────────────────────────

class TestContactHours:
    def test_sums_hours_per_course_code(self):
        svc.add_lesson("CS101 - Intro", "Lecture", start="09:00", end="11:00")
        svc.add_lesson("CS101", "Lab", start="14:00", end="15:00")
        svc.add_lesson("HIS200", "Seminar", start="10:00", end="12:00")
        summary = {e["course"]: e for e in svc.contact_hours_by_course()}
        # 'CS101 - Intro' groups under the leading 'CS101' code.
        assert summary["CS101"]["lessons"] == 2
        assert summary["CS101"]["hours"] == 3  # (11-9) + (15-14)
        assert summary["HIS200"]["hours"] == 2

    def test_unparseable_times_are_skipped(self):
        svc.add_lesson("CS101", "Bad", start="", end="")
        svc.add_lesson("CS101", "Good", start="09:00", end="10:00")
        summary = {e["course"]: e for e in svc.contact_hours_by_course()}
        assert summary["CS101"]["lessons"] == 1
        assert summary["CS101"]["hours"] == 1

    def test_empty_when_no_lessons(self):
        assert svc.contact_hours_by_course() == []
