"""Section meetings reach the Academic Calendar's own read, and meeting forms
survive being made modal before their window is on screen."""

import sqlite3
import tkinter as tk
from types import SimpleNamespace

from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.core.ext_common import (
    grab_when_viewable,
)
from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.core.timetable_tab import (
    _times_with,
)
from education_system.systems.university.domains.teaching.domain.academic_calendar.manager.events import (
    EventsMixin,
)


class _Db:
    def __init__(self, conn):
        self.conn = conn

    def execute_query(self, query, params=()):
        return self.conn.execute(query, params).fetchall()


def _calendar(source_type):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE semesters (name TEXT, start_date TEXT, end_date TEXT, academic_year_id TEXT);
        CREATE TABLE unified_events (source_event_id TEXT, title TEXT, event_date TEXT,
            start_datetime TEXT, end_datetime TEXT, description TEXT, event_type TEXT,
            created_at TEXT, updated_at TEXT, created_by TEXT, start_time TEXT, end_time TEXT,
            location TEXT, audience TEXT, assignment_id TEXT, trip_id TEXT, organizer_name TEXT,
            participants TEXT, status TEXT, country_code TEXT, region TEXT, is_active INTEGER,
            source_type TEXT);
        INSERT INTO semesters VALUES ('Fall', '2026-09-01', '2026-12-20', '2026-2027');
    """)
    conn.execute("INSERT INTO unified_events (source_event_id, title, event_date, source_type) "
                 "VALUES ('1:2026-11-02', 'ACC-001 class', '2026-11-02', ?)", (source_type,))
    return EventsMixin.view_calendar(SimpleNamespace(db_manager=_Db(conn)))


def test_calendar_shows_classes_mirrored_from_the_timetable():
    ok, rows = _calendar("section_meeting")
    assert ok and [r["event_name"] for r in rows] == ["ACC-001 class"]


def test_calendar_still_leaves_out_other_systems_events():
    ok, rows = _calendar("community")
    assert ok and [r["event_name"] for r in rows] == [None]


class _Window:
    def __init__(self, failures):
        self.failures = failures
        self.grabbed = False
        self.alive = True

    def winfo_exists(self):
        return self.alive

    def grab_set(self):
        if self.failures:
            self.failures -= 1
            raise tk.TclError("grab failed: window not viewable")
        self.grabbed = True

    def after(self, _ms, callback, *args):
        callback(*args)


def test_grab_retries_until_the_window_is_viewable():
    window = _Window(failures=3)
    grab_when_viewable(window)
    assert window.grabbed


def test_grab_gives_up_quietly_if_the_window_never_appears():
    window = _Window(failures=1000)
    grab_when_viewable(window, tries=2)
    assert not window.grabbed


def test_time_menu_keeps_a_saved_time_between_its_steps():
    assert "09:15" in _times_with("09:00")
    times = _times_with("09:07")
    assert "09:07" in times and times == sorted(times)
