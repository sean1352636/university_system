"""Draft schedule rows must not appear in personal timetables.

A term clone copies every published ``module_schedule`` slot into a draft row
for the next term (``parent_schedule_id`` points back). The weekly grid and the
term view read ``module_schedule`` directly and drew both, so a student saw two
identical 9am sessions of the same module on Monday.
"""

import sqlite3
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import pytest

from education_system.systems.university.domains.academics.interfaces.gui._cross_dialogs import (
    timetable as grid_module,
)
from education_system.systems.university.domains.academics.interfaces.gui import (
    timetable_management,
)

SCHEMA = [
    "CREATE TABLE student_modules (student_id TEXT, module_code TEXT, status TEXT)",
    "CREATE TABLE rooms (id INTEGER PRIMARY KEY, building TEXT, room_number TEXT)",
    """CREATE TABLE module_schedule (
        id INTEGER PRIMARY KEY, module_code TEXT, day_of_week TEXT,
        start_time TEXT, end_time TEXT, room_id INTEGER, session_type TEXT,
        semester TEXT, year INTEGER, status TEXT, parent_schedule_id INTEGER)""",
    "CREATE TABLE exams (id INTEGER PRIMARY KEY, module_code TEXT, date TEXT, "
    "start_time TEXT, end_time TEXT, room TEXT)",
]


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "records.db")
    c = sqlite3.connect(path)
    for stmt in SCHEMA:
        c.execute(stmt)
    c.execute("INSERT INTO student_modules VALUES ('S1', 'CIS0002', 'Enrolled')")
    c.execute("INSERT INTO rooms VALUES (10, 'Main', '101')")
    c.execute("INSERT INTO module_schedule VALUES "
              "(11, 'CIS0002', 'Monday', '09:00', '13:00', 10, 'Lab', "
              "'Summer', 2026, 'published', NULL)")
    c.execute("INSERT INTO module_schedule VALUES "
              "(15, 'CIS0002', 'Monday', '09:00', '13:00', 10, 'Lab', "
              "'Fall', 2027, 'draft', 11)")
    c.execute("INSERT INTO module_schedule VALUES "
              "(20, 'CIS0002', 'Wednesday', '10:00', '11:00', 10, 'Lecture', "
              "'Summer', 2026, NULL, NULL)")
    c.commit()
    c.close()

    @contextmanager
    def connect(*_a, **_k):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    import education_system.systems.university.infrastructure.database.db as db_mod
    monkeypatch.setattr(db_mod, "get_connection", connect)
    monkeypatch.setattr(timetable_management, "get_connection", connect)
    return path


def test_weekly_grid_skips_draft_clone(db):
    panel = SimpleNamespace(_scope="student", _scope_id="S1",
                            _week_start=date(2026, 9, 14))
    panel._modules_in_scope = lambda conn: grid_module.WeeklyGridPanel._modules_in_scope(panel, conn)
    lectures, _ = grid_module.WeeklyGridPanel._load_rows(panel)
    assert sorted(r["id"] for r in lectures) == [11, 20]   # NULL status counts as published
    monday = [r for r in lectures if r["day_of_week"] == "Monday"]
    assert len(monday) == 1


def test_term_view_skips_draft_clone(db):
    gui = SimpleNamespace()
    gui._modules_for = lambda conn, scope, target: timetable_management.TimetableManagementGUI._modules_for(
        gui, conn, scope, target)
    rows = timetable_management.TimetableManagementGUI._collect_term_rows(
        gui, "2026-09-14", "2026-09-20", "student", "S1")
    mondays = [r for r in rows if r[1] == "Monday"]
    assert len(mondays) == 1
    assert [r[4] for r in rows] == ["Lab", "Lecture"]
