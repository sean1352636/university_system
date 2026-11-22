"""Student records: contact and entry details, likely duplicates, the
change history, withdrawal / reinstatement through the registration
lifecycle (with sign-in), dual-control erasure and the data check.
Temporary databases only; the shared sign-in is a temporary auth.db."""

import sqlite3

import pytest

from education_system.systems.university.application.students import data_quality as dq
from education_system.systems.university.application.students import erasure as er
from education_system.systems.university.application.students import record_rules as rr
from education_system.systems.university.application.students.lifecycle import (
    StudentCommand,
    StudentLifecycleService,
    StudentValidationError,
)
from education_system.systems.university.domains.learners.domain import student_lifecycle
from education_system.systems.university.services import student_provisioning as sp

STUDENTS = """CREATE TABLE students (
    student_id TEXT PRIMARY KEY, email_address TEXT UNIQUE, title TEXT, first_name TEXT,
    middle_name TEXT, last_name TEXT, gender TEXT, dob TEXT, age INTEGER, course TEXT,
    registration_datetime TEXT, status TEXT, enrollment_date TEXT, is_active INTEGER,
    entry_qualifications TEXT, ucas_tariff INTEGER, phone TEXT, address TEXT,
    nationality TEXT, mode_of_study TEXT, campus_code TEXT, expected_return_date TEXT,
    record_closed_at TEXT, pronouns TEXT, emergency_contact TEXT)"""
SCHEMA = [
    STUDENTS,
    "CREATE TABLE courses (course_code TEXT PRIMARY KEY, course_name TEXT, status TEXT, "
    "current_enrollment INTEGER DEFAULT 0, code TEXT, name TEXT, department TEXT)",
    "INSERT INTO courses VALUES ('CS', 'Computer Science', 'active', 0, 'CS', "
    "'Computer Science', 'Computing')",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, student_id TEXT, "
    "first_name TEXT, last_name TEXT, updated_at TEXT)",
    "CREATE TABLE student_modules (student_id TEXT REFERENCES students(student_id), "
    "module_code TEXT, status TEXT)",
    "CREATE TABLE module_grades (student_id TEXT REFERENCES students(student_id), mark REAL)",
    "CREATE TABLE medical_conditions (student_id TEXT REFERENCES students(student_id), "
    "condition TEXT)",
    "CREATE TABLE club_officers (club TEXT, treasurer_id TEXT REFERENCES students(student_id))",
    "CREATE TABLE chat_members (user_id INTEGER REFERENCES users(id), room TEXT)",
    "CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER)",
    "CREATE TABLE student_finance_accounts (student_id TEXT, balance REAL)",
    """CREATE TABLE student_lifecycle_history (history_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT, action TEXT, from_status TEXT, to_status TEXT, effective_date TEXT,
        academic_year TEXT, old_programme TEXT, new_programme TEXT, old_mode TEXT,
        new_mode TEXT, old_campus TEXT, new_campus TEXT, repeat_year INTEGER,
        expected_return_date TEXT, reason TEXT, actor_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE student_lifecycle_actions (action_id INTEGER PRIMARY KEY AUTOINCREMENT,
        history_id INTEGER, student_id TEXT, target_system TEXT, action TEXT,
        payload_json TEXT, status TEXT DEFAULT 'pending')""",
    """CREATE TABLE university_event_outbox (event_id TEXT PRIMARY KEY, event_name TEXT,
        event_version INTEGER, aggregate_id TEXT, correlation_id TEXT, causation_id TEXT,
        idempotency_key TEXT UNIQUE, payload_json TEXT, available_at TEXT,
        attempts INTEGER DEFAULT 0, delivered_at TEXT, dead_lettered_at TEXT, last_error TEXT)""",
]


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_selection,
    )
    monkeypatch.setattr(admissions_selection, "enrol_student_in_curriculum",
                        lambda cursor, sid, code, name: [])
    monkeypatch.setattr(student_lifecycle, "publish_change", lambda *a, **k: None)


@pytest.fixture
def paths(tmp_path):
    db, auth = tmp_path / "students.db", tmp_path / "auth.db"
    with sqlite3.connect(db) as conn:
        for ddl in SCHEMA:
            conn.execute(ddl)
    with sqlite3.connect(auth) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, "
                     "display_name TEXT, email TEXT, is_active INTEGER DEFAULT 1, "
                     "password_hash TEXT, legacy_salt TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, user_id INTEGER, "
                     "is_active INTEGER DEFAULT 1)")
    return str(db), str(auth)


def _command(**kw):
    values = dict(first_name="Ana", last_name="López", dob="2004-04-04", course="CS",
                  gender="female")
    values.update(kw)
    return StudentCommand(**values)


def _create(service, **kw):
    return service.create(_command(**kw), actor_id="admin",
                          idempotency_key=f"c:{kw.get('first_name', 'Ana')}:{kw.get('dob', '')}"
                          ).student_id


def _activate(db, sid):
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE students SET status = 'Active' WHERE student_id = ?", (sid,))


def test_details_are_validated_and_stored(paths):
    db, auth = paths
    service = StudentLifecycleService(db, auth_db_path=auth)
    with pytest.raises(StudentValidationError) as bad:
        service.create(_command(phone="abc", personal_email="nope", fee_status="eu"),
                       actor_id="admin", idempotency_key="bad")
    assert set(bad.value.errors) == {"phone", "personal_email", "fee_status"}
    sid = _create(service, phone="+44 7700 900123", personal_email="ana@example.com",
                  mode_of_study="Full-time", entry_route="ib", entry_qualifications="IB 34")
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT phone, personal_email, mode_of_study, entry_route FROM "
                           "students WHERE student_id = ?", (sid,)).fetchone()
    assert row == ("+44 7700 900123", "ana@example.com", "full-time", "ib")


def test_likely_duplicate_is_refused_unless_confirmed(paths):
    db, auth = paths
    service = StudentLifecycleService(db, auth_db_path=auth)
    first = _create(service)
    with pytest.raises(StudentValidationError, match=first):
        _create(service, first_name="ANA", last_name="Lopez")  # case and accents ignored
    assert _create(service, first_name="ANA", last_name="Lopez", allow_duplicate=True) != first


def test_updates_need_a_reason_and_record_each_changed_field(paths):
    db, auth = paths
    service = StudentLifecycleService(db, auth_db_path=auth)
    sid = _create(service, phone="07700 900111")
    with pytest.raises(StudentValidationError, match="reason"):
        service.update(sid, {"phone": "07700 900222"}, actor_id="admin", reason=" ",
                       idempotency_key="u0")
    service.update(sid, {"phone": "07700 900222", "nationality": "Spanish"},
                   actor_id="admin", reason="Moved", idempotency_key="u1")
    with sqlite3.connect(db) as conn:
        history = rr.change_history(conn, sid)
    changed = {(h["what"], h["old"], h["new"], h["reason"]) for h in history}
    assert ("phone", "07700 900111", "07700 900222", "Moved") in changed
    assert ("nationality", None, "Spanish", "Moved") in changed


def test_withdraw_and_reinstate_go_through_the_lifecycle_and_sign_in(paths):
    db, auth = paths
    service = StudentLifecycleService(db, auth_db_path=auth)
    sid = _create(service)
    _activate(db, sid)
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO student_modules VALUES (?, 'M1', 'Enrolled')", (sid,))
    with sqlite3.connect(auth) as conn:
        conn.execute("INSERT INTO users (id, username) VALUES (5, ?)", (sid,))
        conn.execute("INSERT INTO sessions (user_id) VALUES (5)")

    service.deactivate(sid, actor_id="admin", reason="Left", idempotency_key="w1")
    with sqlite3.connect(db) as conn, sqlite3.connect(auth) as a:
        assert conn.execute("SELECT status, is_active FROM students").fetchone() == ("Withdrawn", 0)
        assert conn.execute("SELECT status FROM student_modules").fetchone() == ("Withdrawn",)
        assert conn.execute("SELECT action, to_status FROM student_lifecycle_history"
                            ).fetchone() == ("withdraw", "Withdrawn")
        assert a.execute("SELECT is_active FROM users").fetchone() == (0,)
        assert a.execute("SELECT is_active FROM sessions").fetchone() == (0,)

    service.restore(sid, actor_id="admin", reason="Back", idempotency_key="r1")
    with sqlite3.connect(db) as conn, sqlite3.connect(auth) as a:
        assert conn.execute("SELECT status, is_active FROM students").fetchone() == ("Active", 1)
        assert conn.execute("SELECT status FROM student_modules").fetchone() == ("Enrolled",)
        assert a.execute("SELECT is_active FROM users").fetchone() == (1,)
    with pytest.raises(StudentValidationError, match="reinstate"):
        service.restore(sid, actor_id="admin", reason="again", idempotency_key="r2")


def _withdrawn_student(paths):
    db, auth = paths
    service = StudentLifecycleService(db, auth_db_path=auth)
    sid = _create(service)
    _activate(db, sid)
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO users (id, username, student_id) VALUES (7, ?, ?)", (sid, sid))
        conn.executemany("INSERT INTO chat_members VALUES (7, ?)", [("r1",), ("r2",)])
        conn.execute("INSERT INTO messages (sender_id, recipient_id) VALUES (7, 1)")
        conn.execute("INSERT INTO student_modules VALUES (?, 'M1', 'Enrolled')", (sid,))
        conn.execute("INSERT INTO module_grades VALUES (?, 64)", (sid,))
        conn.execute("INSERT INTO medical_conditions VALUES (?, 'asthma')", (sid,))
        conn.execute("INSERT INTO club_officers VALUES ('Chess', ?)", (sid,))
    service.deactivate(sid, actor_id="admin", reason="Left", idempotency_key="w")
    return db, sid


def test_erasure_needs_a_different_reauthenticated_approver_and_no_holds(paths):
    db, sid = _withdrawn_student(paths)
    with sqlite3.connect(db) as conn:
        rid = er.request(conn, sid, "IG-7", "Asked to be forgotten", "clerk")
        with pytest.raises(ValueError, match="already open"):
            er.request(conn, sid, "IG-8", "again", "clerk")
        with pytest.raises(ValueError, match="other than the requester"):
            er.decide(conn, rid, True, "clerk", reauthenticated=True)
        with pytest.raises(ValueError, match="password"):
            er.decide(conn, rid, True, "dpo", reauthenticated=False)
        conn.execute("INSERT INTO student_finance_accounts VALUES (?, 120)", (sid,))
        with pytest.raises(ValueError, match="owed"):
            er.decide(conn, rid, True, "dpo", reauthenticated=True)
        conn.execute("UPDATE student_finance_accounts SET balance = 0")
        with pytest.raises(ValueError, match="approved"):
            er.execute(conn, rid, "dpo")
        er.decide(conn, rid, True, "dpo", reauthenticated=True)


def test_erasure_keeps_results_under_an_anonymous_id_and_removes_the_rest(paths):
    db, sid = _withdrawn_student(paths)
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        rid = er.request(conn, sid, "IG-7", "Asked to be forgotten", "clerk")
        er.decide(conn, rid, True, "dpo", reauthenticated=True)
        conn.commit()
        result = er.execute(conn, rid, "dpo")
        conn.commit()
        anon = result["anonymous_id"]
        assert anon.startswith("ERASED-") and result["login"] == sid
        assert conn.execute("SELECT first_name, dob, phone, email_address, status FROM students"
                            ).fetchone() == ("Erased", None, None,
                                             f"{anon.lower()}@erased.invalid", "Closed")
        assert conn.execute("SELECT student_id FROM module_grades").fetchone() == (anon,)
        assert conn.execute("SELECT student_id FROM student_modules").fetchone() == (anon,)
        assert conn.execute("SELECT COUNT(*) FROM medical_conditions").fetchone() == (0,)
        assert conn.execute("SELECT treasurer_id FROM club_officers").fetchone() == (None,)
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM chat_members").fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM student_record_changes WHERE student_id = ?",
                            (sid,)).fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM university_event_outbox WHERE aggregate_id = ?",
                            (sid,)).fetchone() == (0,)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT status, student_id FROM student_erasure_requests"
                            ).fetchone() == ("completed", anon)


def test_erased_sign_in_is_disabled_and_stripped(paths):
    _db, auth = paths
    with sqlite3.connect(auth) as conn:
        conn.execute("INSERT INTO users (id, username, display_name, email) VALUES "
                     "(3, '1234567', 'Ana López', 'ana@x.uk')")
        conn.execute("INSERT INTO sessions (user_id) VALUES (3)")
    assert sp.erase_student_login("1234567", auth)
    with sqlite3.connect(auth) as conn:
        assert conn.execute("SELECT is_active, display_name, email FROM users").fetchone() == \
            (0, "Erased", None)
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone() == (0,)


def test_data_check_finds_problems_and_applies_only_safe_fixes(paths):
    db, _auth = paths
    with sqlite3.connect(db) as conn:
        conn.executemany(
            "INSERT INTO students (student_id, email_address, first_name, last_name, dob, course, "
            "status, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [("A1", "a1@x.uk", "Al", "One", "2001-01-01", "Computer Science", "Active", 1),
             ("A2", "a2@x.uk", "Bo", "Two", "2001-01-01", "Mathematics", "Active", 1),
             ("A3", "a3@x.uk", "Cy", "Three", None, "CS", "Graduated", 1),
             ("A4", "a4@x.uk", "Al", "One", "2001-01-01", "CS", "Active", 1)])
        found = {(i["student_id"], i["kind"]): i["fix"] for i in dq.issues(conn)}
        assert found[("A1", "course")] == {"course": "CS"}
        assert found[("A2", "course")] is None
        assert found[("A3", "status")] == {"status": "Completed"}
        assert found[("A3", "active_flag")] == {"is_active": 0}
        assert ("A3", "dob") in found and ("A1", "duplicate") in found
        changed = dq.apply_fixes(conn, ["course:A1", "status:A3", "active_flag:A3", "course:A2"],
                                 "admin")
        assert changed == 2
        assert conn.execute("SELECT course FROM students WHERE student_id = 'A1'").fetchone() == ("CS",)
        assert conn.execute("SELECT status, is_active FROM students WHERE student_id = 'A3'"
                            ).fetchone() == ("Completed", 0)
        assert conn.execute("SELECT course FROM students WHERE student_id = 'A2'").fetchone() == \
            ("Mathematics",)
        assert rr.change_history(conn, "A1")[0]["reason"] == "Data quality fix"
