"""Shared fixture for the Sixth Form attendance tests.

Points every attendance-adjacent module at one temporary SQLite file and
seeds a small, predictable college: one course, two class groups (one
with three learners, one empty), and three timetable slots.

The academic-year module is redirected too even though most tests never
touch it — :mod:`attendance_sessions` asks it which days the college is
open, and an un-redirected module would reach the real ``sixthform.db``
and migrate it.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3

import pytest

from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year as ay,
)
from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_absence_reports as absence_reports,
    attendance_activities as activities,
    attendance_analytics as analytics,
    attendance_anomalies as anomalies,
    attendance_appeals as appeals,
    attendance_audit as audit,
    attendance_authorisation as authz,
    attendance_bursary as bursary,
    attendance_calendar as att_calendar,
    attendance_calling as calling,
    attendance_census as census,
    attendance_codes as codes,
    attendance_cohorts as cohorts,
    attendance_cover as cover,
    attendance_escalation as escalation,
    attendance_evidence as evidence,
    attendance_exams as exams,
    attendance_governor_report as governor_report,
    attendance_import as importer,
    attendance_integration as integration,
    attendance_kiosk as kiosk,
    attendance_leave as leave,
    attendance_letters as letters,
    attendance_notifications as notifications,
    attendance_nudges as nudges,
    attendance_offline as offline,
    attendance_placements as placements,
    attendance_punctuality as punctuality,
    attendance_register as reg,
    attendance_rewards as rewards,
    attendance_rollcall as rollcall,
    attendance_safeguarding as safeguarding,
    attendance_sessions as sessions,
    attendance_thresholds as thresholds,
    attendance_weeks as weeks,
    attendance_window as window,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as cg,
)
from education_system.systems.sixth_form.domain.academics.courses import (
    courses as courses_mod,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system.systems.sixth_form.domain.assessment.exam_entries import (
    exam_entries,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as students_mod,
)
from education_system.systems.sixth_form.domain.progression.work_experience import (
    work_experience,
)

# Every module whose DB_PATH has to move to the temp file. Missing one
# is not a failing test — it is a test that quietly writes to the real
# sixthform.db, so this list has to track every module in the package.
_MODULES = (
    # Features 1-10: capture, off-timetable registers, policy.
    core, reg, codes, audit, authz, sessions, window, weeks,
    cover, kiosk, offline, importer, activities, placements,
    exams, rollcall,
    # Features 11-40: intake, comms, intervention, analysis, config.
    thresholds, att_calendar, absence_reports, leave, evidence, appeals,
    calling, notifications, nudges, letters, escalation, punctuality,
    cohorts, safeguarding, bursary, rewards, analytics, anomalies,
    governor_report, census, integration,
    # Neighbouring modules the package reads from.
    tt, cg, courses_mod, students_mod, ay, work_experience, exam_entries,
)


def next_weekday(target: int) -> _dt.date:
    """The next date (today included) whose weekday matches ``target``."""
    today = _dt.date.today()
    return today + _dt.timedelta(days=(target - today.weekday()) % 7)


@pytest.fixture
def attdb(tmp_path, monkeypatch):
    db_path = str(tmp_path / "sixthform.db")
    for mod in _MODULES:
        monkeypatch.setattr(mod, "DB_PATH", db_path, raising=False)
        ready = getattr(mod, "_DB_READY", None)
        if isinstance(ready, set):
            # academic_year keys its readiness by path, not by a flag.
            monkeypatch.setattr(mod, "_DB_READY", set(), raising=False)
        elif ready is not None:
            monkeypatch.setattr(mod, "_DB_READY", False, raising=False)
    sessions.init_db()
    audit.init_db()
    weeks.init_db()
    window.init_db()
    thresholds.init_db()
    att_calendar.init_db()

    # Seeded by SQL rather than through students.create_student, which
    # would provision a login in the shared platform auth.db.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO courses (course_id, course_code, subject, title, "
        "year_group, academic_year) VALUES (1, 'MAT-A', 'Mathematics', "
        "'A Level Maths', 12, '2025/26')")
    conn.executemany(
        "INSERT INTO class_groups (group_id, course_id, group_name) "
        "VALUES (?, 1, ?)", [(1, "12A"), (2, "12B")])
    for i, name in enumerate(("Ada", "Alan", "Grace"), 1):
        sid = f"T{i:04d}"
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, email, "
            "status) VALUES (?, ?, 'Test', ?, 'Active')",
            (sid, name, f"{sid.lower()}@example.test"))
        conn.execute(
            "INSERT INTO class_group_students (group_id, student_id) "
            "VALUES (1, ?)", (sid,))
    conn.executemany(
        "INSERT INTO timetable_slots (slot_id, group_id, day, period, "
        "start_time, end_time, room) VALUES (?, ?, ?, ?, ?, ?, 'R1')",
        [(1, 1, 1, 1, "09:00", "09:55"),   # 12A, Monday P1 — morning
         (2, 1, 1, 6, "14:55", "15:50"),   # 12A, Monday P6 — afternoon
         (3, 2, 2, 1, "09:00", "09:55")])  # 12B (no members), Tuesday P1
    conn.commit()
    conn.close()

    class NS:
        pass

    ns = NS()
    ns.db = db_path
    ns.students = ["T0001", "T0002", "T0003"]
    ns.s1, ns.s2, ns.s3 = ns.students
    ns.slot = 1            # Monday morning
    ns.pm_slot = 2         # Monday afternoon
    ns.empty_slot = 3      # Tuesday, no roster
    ns.group = 1
    monday = next_weekday(0)
    ns.monday = monday.isoformat()
    ns.tuesday = next_weekday(1).isoformat()
    ns.prev_monday = (monday - _dt.timedelta(days=7)).isoformat()
    ns.next_monday = (monday + _dt.timedelta(days=7)).isoformat()
    # Comfortably past the default 60-day amendment cutoff, for the
    # tests that need a register the window has closed.
    ns.ancient = (monday - _dt.timedelta(days=400)).isoformat()
    return ns


@pytest.fixture
def one_absence(attdb):
    """A single unexplained absence, ready to be decided about.

    Returns the record so tests can reach for ``record_id`` without
    re-querying.
    """
    core.save_register(attdb.slot, attdb.monday,
                       {attdb.s1: {"status": "Absent"}})
    record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
    assert record is not None
    return record
