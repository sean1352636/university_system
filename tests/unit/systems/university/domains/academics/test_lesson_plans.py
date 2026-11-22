"""Unit tests for lesson planning after the merge into Module Scheduling.

The Lesson Planner used to own a second timetable in ``lesson_plans``: free
text day/time/room, no term, no foreign keys, invisible to conflict detection,
saved by deleting every row and re-inserting. The timetable is now
``module_schedule`` alone, and a lesson is content — title, type, notes —
hanging off one of its slots.

These tests pin that split: content edits never touch the timetable, and the
timetable is never edited from here.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.domains.teaching.domain.module_scheduling import (
    lesson_plans as lp,
)

_SCHEMA = """
CREATE TABLE modules (
    module_code TEXT PRIMARY KEY, module_name TEXT
);
CREATE TABLE rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT, building TEXT, room_number TEXT
);
CREATE TABLE instructors (
    id INTEGER PRIMARY KEY AUTOINCREMENT, first_name TEXT, last_name TEXT
);
CREATE TABLE module_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_code TEXT REFERENCES modules(module_code),
    day_of_week TEXT, start_time TEXT, end_time TEXT,
    room_id INTEGER, instructor_id INTEGER, session_type TEXT,
    semester TEXT, year TEXT, status TEXT, recurrence TEXT,
    parent_schedule_id INTEGER
);
CREATE TABLE lesson_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course TEXT, title TEXT, instructor TEXT, type TEXT,
    day TEXT, start TEXT, end TEXT, room TEXT, notes TEXT,
    updated_at TEXT, updated_by TEXT
);

INSERT INTO modules (module_code, module_name) VALUES
    ('CS-Y1-1','Programming'), ('CS-Y1-2','Systems');
INSERT INTO rooms (building, room_number) VALUES ('Main','101');
INSERT INTO instructors (first_name, last_name) VALUES ('Ada','Lovelace');
INSERT INTO module_schedule (module_code, day_of_week, start_time, end_time,
                             room_id, instructor_id, session_type, semester,
                             year, status, recurrence)
VALUES ('CS-Y1-1','Monday','09:00','11:00',1,1,'Lecture','Autumn','2026','published','weekly'),
       ('CS-Y1-2','Tuesday','14:00','16:00',1,1,'Lab','Autumn','2026','draft','weekly');
"""


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "lessons.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        path,
    )
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    lp.ensure_schema()
    return path


def _exec(path, sql, params=()):
    conn = sqlite3.connect(path)
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def _count(path, table):
    conn = sqlite3.connect(path)
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return n


class TestSlots:

    def test_slots_come_from_the_timetable(self, db):
        slots = lp.scheduled_slots()
        assert [s["module_code"] for s in slots] == ["CS-Y1-1", "CS-Y1-2"]

    def test_room_and_instructor_are_resolved_not_free_text(self, db):
        monday = lp.scheduled_slots()[0]
        assert monday["room"] == "Main 101"
        assert monday["instructor"] == "Ada Lovelace"

    def test_slots_are_ordered_by_day_then_time(self, db):
        days = [s["day_of_week"] for s in lp.scheduled_slots()]
        assert days == ["Monday", "Tuesday"]

    def test_filters(self, db):
        assert len(lp.scheduled_slots(module_code="CS-Y1-1")) == 1
        assert len(lp.scheduled_slots(semester="Autumn")) == 2
        assert lp.scheduled_slots(semester="Spring") == []

    def test_slot_carries_draft_status(self, db):
        assert {s["status"] for s in lp.scheduled_slots()} == {"published", "draft"}


class TestContent:

    def test_save_then_read_back(self, db):
        slot = lp.scheduled_slots()[0]
        lesson_id = lp.save_lesson(slot["schedule_id"], title="Recursion",
                                   lesson_type="Lecture", notes="Base cases",
                                   module_code=slot["module_code"])
        assert lesson_id
        again = lp.scheduled_slots()[0]
        assert (again["title"], again["lesson_type"], again["notes"]) == \
            ("Recursion", "Lecture", "Base cases")

    def test_second_save_updates_rather_than_duplicating(self, db):
        slot = lp.scheduled_slots()[0]
        lp.save_lesson(slot["schedule_id"], title="First")
        lp.save_lesson(slot["schedule_id"], title="Second")
        assert _count(db, "lesson_plan_content") == 1
        assert lp.scheduled_slots()[0]["title"] == "Second"

    def test_each_slot_holds_its_own_lesson(self, db):
        first, second = lp.scheduled_slots()
        lp.save_lesson(first["schedule_id"], title="Lecture one")
        lp.save_lesson(second["schedule_id"], title="Lab one")
        titles = {s["module_code"]: s["title"] for s in lp.scheduled_slots()}
        assert titles == {"CS-Y1-1": "Lecture one", "CS-Y1-2": "Lab one"}

    def test_deleting_a_lesson_leaves_the_slot(self, db):
        """A lesson plan is not a class: deleting one must not untimetable it."""
        slot = lp.scheduled_slots()[0]
        lesson_id = lp.save_lesson(slot["schedule_id"], title="Recursion")
        before = _count(db, "module_schedule")
        assert lp.delete_lesson(lesson_id)
        assert _count(db, "module_schedule") == before
        assert lp.scheduled_slots()[0]["title"] is None

    def test_removing_a_slot_removes_its_lesson(self, db):
        """The reverse does cascade — content cannot outlive its slot."""
        slot = lp.scheduled_slots()[0]
        lp.save_lesson(slot["schedule_id"], title="Recursion")
        conn = sqlite3.connect(db)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM module_schedule WHERE id = ?", (slot["schedule_id"],))
        conn.commit()
        conn.close()
        assert _count(db, "lesson_plan_content") == 0


class TestMigration:

    @pytest.fixture()
    def legacy(self, db):
        _exec(db, "INSERT INTO lesson_plans (course, title, type, day, start, end, "
                  "room, notes) VALUES ('CS-Y1-1 - Programming','Recursion',"
                  "'Lecture','Monday','09:00','11:00','Main 101','Bring laptop')")
        _exec(db, "INSERT INTO lesson_plans (course, title, type, day, start, end, "
                  "room) VALUES ('CS-Y1-2 - Systems','Pipelines','Lab','Friday',"
                  "'10:00','12:00','Lab 2')")
        _exec(db, "INSERT INTO lesson_plans (course, title, type, day, start, end) "
                  "VALUES ('GONE-1 - Retired','Orphan','Seminar','Monday','13:00','14:00')")
        return db

    def test_dry_run_writes_nothing(self, legacy):
        result = lp.migrate_legacy_lessons()
        assert result["applied"] is False
        assert _count(legacy, "lesson_plan_content") == 0

    def test_matching_slot_is_reused(self, legacy):
        result = lp.migrate_legacy_lessons(apply=True)
        assert [e["title"] for e in result["attached"]] == ["Recursion"]
        monday = lp.scheduled_slots()[0]
        assert monday["title"] == "Recursion"
        assert monday["notes"] == "Bring laptop"

    def test_unmatched_time_creates_a_draft_slot(self, legacy):
        """A migrated guess must not appear on a published timetable."""
        result = lp.migrate_legacy_lessons(apply=True)
        assert [e["title"] for e in result["slot_created"]] == ["Pipelines"]
        friday = [s for s in lp.scheduled_slots() if s["day_of_week"] == "Friday"]
        assert len(friday) == 1
        assert friday[0]["status"] == "draft"
        assert friday[0]["title"] == "Pipelines"

    def test_missing_module_keeps_the_lesson_unscheduled(self, legacy):
        """Losing the lesson would be worse than keeping it without a slot."""
        result = lp.migrate_legacy_lessons(apply=True)
        assert [e["title"] for e in result["unscheduled"]] == ["Orphan"]
        orphans = lp.unscheduled_lessons()
        assert len(orphans) == 1
        assert orphans[0]["module_code"] == "GONE-1"
        assert orphans[0]["legacy_slot"] == "Monday 13:00-14:00"

    def test_no_slot_is_created_for_a_missing_module(self, legacy):
        """module_schedule.module_code is a foreign key onto modules."""
        before = _count(legacy, "module_schedule")
        lp.migrate_legacy_lessons(apply=True)
        assert _count(legacy, "module_schedule") == before + 1   # Friday only

    def test_rerun_is_idempotent(self, legacy):
        lp.migrate_legacy_lessons(apply=True)
        rows = _count(legacy, "lesson_plan_content")
        second = lp.migrate_legacy_lessons(apply=True)
        assert _count(legacy, "lesson_plan_content") == rows
        assert len(second["skipped"]) == 3

    def test_absent_legacy_table_is_not_an_error(self, db):
        _exec(db, "DROP TABLE lesson_plans")
        assert lp.migrate_legacy_lessons(apply=True)["attached"] == []


class TestAttach:

    def test_unscheduled_lesson_can_be_given_a_slot(self, db):
        lesson_id = lp.save_lesson(None, title="Orphan", module_code="GONE-1")
        assert len(lp.unscheduled_lessons()) == 1
        slot = lp.scheduled_slots()[0]
        assert lp.attach_to_slot(lesson_id, slot["schedule_id"])
        assert lp.unscheduled_lessons() == []
        assert lp.scheduled_slots()[0]["title"] == "Orphan"

    def test_attaching_adopts_the_slots_module(self, db):
        lesson_id = lp.save_lesson(None, title="Orphan", module_code="GONE-1")
        slot = lp.scheduled_slots()[0]
        lp.attach_to_slot(lesson_id, slot["schedule_id"])
        conn = sqlite3.connect(db)
        code = conn.execute("SELECT module_code FROM lesson_plan_content "
                            "WHERE lesson_id = ?", (lesson_id,)).fetchone()[0]
        conn.close()
        assert code == slot["module_code"]
