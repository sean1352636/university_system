"""Tier-4 integration tests: attendance auto-flag, cohort sweep,
tutor-group agenda from concern, study-match auto-suggest on enrol."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_db(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE attendance_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, module_code TEXT, date TEXT,
            status TEXT, notes TEXT, recorded_by TEXT,
            recorded_at TEXT, session_id INTEGER,
            UNIQUE(student_id, module_code, date)
        );
        CREATE TABLE risks (
            risk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, category TEXT, department TEXT,
            description TEXT, likelihood INTEGER, impact INTEGER,
            status TEXT DEFAULT 'Open', owner TEXT, mitigation TEXT,
            created TEXT, updated TEXT, reference_id TEXT,
            next_review_date TEXT, expires_at TEXT
        );
        CREATE TABLE disciplinary_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, offense_type TEXT, severity TEXT,
            description TEXT, date_occurred TEXT, date_reported TEXT,
            reported_by TEXT, location TEXT, status TEXT DEFAULT 'Open'
        );
        CREATE TABLE tutor_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, academic_year TEXT,
            programme TEXT, lead_tutor_id INTEGER,
            capacity INTEGER, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE tutor_group_members (
            membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER, student_id TEXT,
            role TEXT, is_active INTEGER DEFAULT 1,
            joined_date TEXT
        );
        CREATE TABLE tutor_group_meetings (
            meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER, scheduled_at TEXT,
            duration_minutes INTEGER DEFAULT 60,
            location TEXT, agenda TEXT,
            attendance_count INTEGER, notes TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT
        );
        """
    )
    conn.commit(); conn.close()

    from education_system.systems.university.infrastructure.database import db as db_mod

    def fake_get(*_a, **_k):
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        return c

    class FakeTx:
        def __enter__(self): self.conn = fake_get(); return self.conn
        def __exit__(self, *exc):
            try: self.conn.commit()
            finally: self.conn.close()

    def fake_tx(*_a, **_k): return FakeTx()

    monkeypatch.setattr(db_mod, "get_connection", fake_get)
    monkeypatch.setattr(db_mod, "transaction", fake_tx)

    from education_system.systems.university.services.bus import (
        integration_bus, attendance_bus, cases_bus, risk_bus,
    )
    monkeypatch.setattr(integration_bus, "get_connection", fake_get)
    monkeypatch.setattr(integration_bus, "transaction", fake_tx)
    monkeypatch.setattr(cases_bus, "get_connection", fake_get)
    monkeypatch.setattr(risk_bus, "get_connection", fake_get)
    # attendance_bus' weekly idempotency cache survives between tests
    attendance_bus._RECENT_FLAGS.clear()

    from education_system.systems.university.interfaces.gui.academics import _event_bus
    _event_bus.reset_for_tests()
    integration_bus.reset_for_tests()
    integration_bus.wire_subscribers()

    yield db_path

    _event_bus.reset_for_tests()
    integration_bus.reset_for_tests()
    attendance_bus._RECENT_FLAGS.clear()


def _seed(db_path, sql, params=()):
    c = sqlite3.connect(str(db_path)); c.execute(sql, params); c.commit(); c.close()

def _query(db_path, sql, params=()):
    c = sqlite3.connect(str(db_path)); c.row_factory = sqlite3.Row
    rows = c.execute(sql, params).fetchall(); c.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# #18 — attendance write → auto-flag below 70%
# ---------------------------------------------------------------------------

def test_attendance_record_auto_flags_low_pct(tmp_db):
    from education_system.systems.university.domain.academics.services.attendance import records as att_records

    # Seed history: 8 absent, 2 present out of 10 → 20% before this batch.
    for i in range(8):
        _seed(tmp_db,
              "INSERT INTO attendance_records "
              "(student_id, module_code, date, status, recorded_at) "
              "VALUES ('S1','CS101', date('now', ?), 'absent', datetime('now'))",
              (f"-{i+1} days",))
    for i in range(2):
        _seed(tmp_db,
              "INSERT INTO attendance_records "
              "(student_id, module_code, date, status, recorded_at) "
              "VALUES ('S1','CS101', date('now', ?), 'present', datetime('now'))",
              (f"-{i+10} days",))

    # New session: another absent
    att_records.record_attendance(
        "CS101", "2026-04-30",
        [("S1", "absent", "")],
        recorded_by="staff1",
    )

    cases = _query(tmp_db,
                   "SELECT user_id, severity FROM disciplinary_records "
                   "WHERE LOWER(offense_type) LIKE '%attendance%'")
    assert cases
    assert cases[0]["user_id"] == "S1"


def test_attendance_record_no_flag_above_threshold(tmp_db):
    from education_system.systems.university.domain.academics.services.attendance import records as att_records

    # 9 of 10 present → 90% — above 70%
    for i in range(9):
        _seed(tmp_db,
              "INSERT INTO attendance_records "
              "(student_id, module_code, date, status, recorded_at) "
              "VALUES ('S2','CS101', date('now', ?), 'present', datetime('now'))",
              (f"-{i+1} days",))
    _seed(tmp_db,
          "INSERT INTO attendance_records "
          "(student_id, module_code, date, status, recorded_at) "
          "VALUES ('S2','CS101', date('now','-10 days'), 'absent', datetime('now'))")

    att_records.record_attendance(
        "CS101", "2026-04-30",
        [("S2", "present", "")],
        recorded_by="staff1",
    )

    cases = _query(tmp_db,
                   "SELECT * FROM disciplinary_records WHERE user_id='S2'")
    assert cases == []


# ---------------------------------------------------------------------------
# #19 — sweep_cohort_attendance_risk
# ---------------------------------------------------------------------------

def test_cohort_sweep_raises_module_risk(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    # 10 attendance entries on CS101 → 50% present (below 65% threshold)
    for i in range(5):
        _seed(tmp_db,
              "INSERT INTO attendance_records "
              "(student_id, module_code, date, status) "
              "VALUES (?, 'CS101', date('now','-1 days'), 'present')",
              (f"S{i}",))
    for i in range(5, 10):
        _seed(tmp_db,
              "INSERT INTO attendance_records "
              "(student_id, module_code, date, status) "
              "VALUES (?, 'CS101', date('now','-1 days'), 'absent')",
              (f"S{i}",))

    # Healthy cohort (90%) on CS200 — should not raise.
    for i in range(9):
        _seed(tmp_db,
              "INSERT INTO attendance_records "
              "(student_id, module_code, date, status) "
              "VALUES (?, 'CS200', date('now','-1 days'), 'present')",
              (f"S{i}",))
    _seed(tmp_db,
          "INSERT INTO attendance_records "
          "(student_id, module_code, date, status) "
          "VALUES ('S99','CS200', date('now','-1 days'), 'absent')")

    result = integration_bus.sweep_cohort_attendance_risk()
    assert result["checked"] == 2
    assert result["raised"] == 1

    risks = _query(tmp_db,
                   "SELECT reference_id FROM risks "
                   "WHERE reference_id LIKE 'module:%'")
    assert risks
    assert risks[0]["reference_id"] == "module:CS101"


# ---------------------------------------------------------------------------
# #20 — attendance concern → tutor group agenda
# ---------------------------------------------------------------------------

def test_attendance_concern_appends_to_next_meeting_agenda(tmp_db):
    from education_system.systems.university.interfaces.gui.academics._event_bus import (
        publish, EVENT_CASE_OPENED,
    )

    _seed(tmp_db,
          "INSERT INTO tutor_groups (group_id, name, academic_year, programme, "
          "lead_tutor_id, capacity) VALUES (1,'TG-A','2025/26','CS',10,20)")
    _seed(tmp_db,
          "INSERT INTO tutor_group_members "
          "(group_id, student_id, role, is_active, joined_date) "
          "VALUES (1,'S5','student',1, date('now'))")
    _seed(tmp_db,
          "INSERT INTO tutor_group_meetings "
          "(group_id, scheduled_at, agenda, status, created_at) "
          "VALUES (1, datetime('now','+7 days'), 'Existing agenda', 'scheduled', datetime('now'))")

    publish(EVENT_CASE_OPENED,
            case_id=42, kind="attendance_concern",
            subject_id="S5", severity="High")

    rows = _query(tmp_db,
                  "SELECT agenda FROM tutor_group_meetings WHERE group_id=1")
    assert "Existing agenda" in rows[0]["agenda"]
    assert "Attendance concern" in rows[0]["agenda"]
    assert "S5" in rows[0]["agenda"]


def test_attendance_concern_creates_pending_when_no_meeting(tmp_db):
    from education_system.systems.university.interfaces.gui.academics._event_bus import (
        publish, EVENT_CASE_OPENED,
    )

    _seed(tmp_db,
          "INSERT INTO tutor_groups (group_id, name, academic_year, programme, "
          "lead_tutor_id, capacity) VALUES (2,'TG-B','2025/26','CS',11,20)")
    _seed(tmp_db,
          "INSERT INTO tutor_group_members "
          "(group_id, student_id, role, is_active, joined_date) "
          "VALUES (2,'S6','student',1, date('now'))")

    publish(EVENT_CASE_OPENED,
            case_id=43, kind="attendance_concern",
            subject_id="S6", severity="Critical")

    rows = _query(tmp_db,
                  "SELECT status, agenda FROM tutor_group_meetings WHERE group_id=2")
    assert rows
    assert rows[0]["status"] == "pending"
    assert "S6" in rows[0]["agenda"]


def test_other_case_kinds_do_not_touch_tutor_groups(tmp_db):
    from education_system.systems.university.interfaces.gui.academics._event_bus import (
        publish, EVENT_CASE_OPENED,
    )

    _seed(tmp_db,
          "INSERT INTO tutor_groups (group_id, name, academic_year, programme, "
          "lead_tutor_id, capacity) VALUES (3,'TG-C','2025/26','CS',12,20)")
    _seed(tmp_db,
          "INSERT INTO tutor_group_members "
          "(group_id, student_id, role, is_active, joined_date) "
          "VALUES (3,'S7','student',1, date('now'))")

    publish(EVENT_CASE_OPENED,
            case_id=44, kind="academic_misconduct",
            subject_id="S7", severity="High")

    rows = _query(tmp_db, "SELECT * FROM tutor_group_meetings WHERE group_id=3")
    assert rows == []


# ---------------------------------------------------------------------------
# #21 — enrolment → study match auto-suggest
# ---------------------------------------------------------------------------

def test_enrolment_invokes_match_suggestions(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    captured = []

    class FakeSvc:
        def find_study_matches(self, student_id, course_id=None, limit=10):
            return [
                {"student_id": "P1", "compatibility_score": 80},
                {"student_id": "P2", "compatibility_score": 65},
            ]

        def create_match_suggestion(self, sid, peer_id, course_id=None):
            captured.append((sid, peer_id, course_id))
            return 1

    with patch(
        "education_system.systems.university.domain."
        "academics.study_matching.services.study_matching_service."
        "StudyMatchingService",
        return_value=FakeSvc(),
    ):
        integration_bus.publish_enrolment_added("S1", "CS101")

    assert len(captured) == 2
    assert captured[0] == ("S1", "P1", "CS101")
    assert captured[1] == ("S1", "P2", "CS101")
