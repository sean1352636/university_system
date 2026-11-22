import sqlite3

import pytest

from education_system.systems.university.application.students.lifecycle import (
    PurgeControlError,
    StudentCommand,
    StudentLifecycleService,
    StudentStatus,
    StudentValidationError,
    validate_student_command,
)


@pytest.fixture(autouse=True)
def _curriculum_stub(monkeypatch):
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_selection,
    )

    monkeypatch.setattr(
        admissions_selection,
        "enrol_student_in_curriculum",
        lambda conn, student_id, course, course_name: [],
    )


def _database(path, *, outbox=True):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE students (
          student_id TEXT PRIMARY KEY, email_address TEXT UNIQUE, title TEXT,
          first_name TEXT, middle_name TEXT, last_name TEXT, gender TEXT,
          dob TEXT, age INTEGER, course TEXT, registration_datetime TEXT,
          status TEXT, enrollment_date TEXT, is_active INTEGER,
          entry_qualifications TEXT, ucas_tariff INTEGER
        );
        CREATE TABLE courses (course_code TEXT PRIMARY KEY, course_name TEXT, status TEXT,
                              current_enrollment INTEGER DEFAULT 0);
        INSERT INTO courses VALUES ('CS', 'Computer Science', 'active', 0);
        CREATE TABLE users (id INTEGER PRIMARY KEY, student_id TEXT, is_active INTEGER);
        CREATE TABLE student_modules (student_id TEXT, module_code TEXT);
        CREATE TABLE student_grades (student_id TEXT, grade TEXT);
        CREATE TABLE attendance (student_id TEXT, attended INTEGER);
    """)
    if outbox:
        conn.execute("""CREATE TABLE university_event_outbox (
          event_id TEXT PRIMARY KEY, event_name TEXT, event_version INTEGER,
          aggregate_id TEXT, correlation_id TEXT, causation_id TEXT,
          idempotency_key TEXT UNIQUE, payload_json TEXT, available_at TEXT,
          attempts INTEGER DEFAULT 0, delivered_at TEXT, dead_lettered_at TEXT,
          last_error TEXT)""")
    conn.commit()
    conn.close()


def _command():
    return StudentCommand(first_name="José", last_name="李", dob="2000-01-01", course="CS")


def test_canonical_validation_accepts_unicode_and_seven_digit_ids():
    result = validate_student_command(StudentCommand(
        first_name="Zoë", last_name="O’Neil".replace("’", "'"), dob="2000-01-01",
        course="CS", student_id="1234567",
    ))
    assert result.student_id == "1234567"


def test_create_and_outbox_are_atomic(tmp_path):
    db = tmp_path / "students.db"
    _database(db, outbox=False)
    service = StudentLifecycleService(str(db))

    with pytest.raises(sqlite3.OperationalError):
        service.create(_command(), actor_id="staff", idempotency_key="create:1")

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0


def test_repeated_create_is_idempotent(tmp_path):
    db = tmp_path / "students.db"
    _database(db)
    service = StudentLifecycleService(str(db))

    first = service.create(_command(), actor_id="staff", idempotency_key="create:1")
    second = service.create(_command(), actor_id="staff", idempotency_key="create:1")

    assert second.student_id == first.student_id
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM university_event_outbox").fetchone()[0] == 1


def test_failed_account_provisioning_remains_retryable(tmp_path, monkeypatch):
    db = tmp_path / "students.db"
    _database(db)
    service = StudentLifecycleService(str(db))
    created = service.create(_command(), actor_id="staff", idempotency_key="create:1")
    monkeypatch.setattr(service, "_module_provisioners", lambda: ())
    monkeypatch.setattr(
        "education_system.systems.university.services.student_provisioning.provision_student_login",
        lambda *args, **kwargs: {"legacy_ok": False, "shared_ok": False,
                                "activation_sent": False},
    )

    failed = service.provision(created.student_id)

    assert failed.status is StudentStatus.PROVISIONING_PENDING
    assert "shared sign-in account" in failed.provisioning_error
    with sqlite3.connect(db) as conn:
        student = conn.execute("SELECT status FROM students").fetchone()
        event = conn.execute("SELECT delivered_at,last_error,attempts FROM university_event_outbox").fetchone()
        assert student[0] == "Registration Pending"
        assert event[0] is None
        assert "shared sign-in account" in event[1]
        assert event[2] == 1


def test_successful_provisioning_is_idempotent(tmp_path, monkeypatch):
    db = tmp_path / "students.db"
    _database(db)
    service = StudentLifecycleService(str(db))
    created = service.create(_command(), actor_id="staff", idempotency_key="create:1")
    calls = []
    monkeypatch.setattr(service, "_module_provisioners", lambda: ())
    monkeypatch.setattr(
        "education_system.systems.university.services.student_provisioning.provision_student_login",
        lambda *args, **kwargs: calls.append(created.student_id) or {
            "legacy_ok": True, "shared_ok": True, "activation_sent": True,
        },
    )
    monkeypatch.setattr(
        "education_system.systems.university.domains.learners.interfaces.gui.students.student_crud_gui.sync.chat_rooms._auto_join_module_chat_rooms",
        lambda **kwargs: None,
    )

    first = service.provision(created.student_id)
    second = service.provision(created.student_id)

    assert first.status is StudentStatus.ACTIVE
    assert second.status is StudentStatus.ACTIVE
    assert calls == [created.student_id]


def test_course_change_is_a_transfer_that_keeps_old_modules(tmp_path, monkeypatch):
    db = tmp_path / "students.db"
    _database(db)
    service = StudentLifecycleService(str(db))
    created = service.create(_command(), actor_id="staff", idempotency_key="create:1")
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO courses VALUES ('DS','Data Science','active',0)")
        conn.execute("DROP TABLE student_modules")
        conn.execute("CREATE TABLE student_modules (student_id TEXT, module_code TEXT, "
                     "module_name TEXT, module_type TEXT, year TEXT, status TEXT, "
                     "UNIQUE(student_id, module_code))")
        conn.executemany("INSERT INTO student_modules (student_id, module_code, status) "
                         "VALUES (?, ?, 'Enrolled')",
                         [(created.student_id, "OLD101"), (created.student_id, "SHARED")])
        conn.commit()
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_selection,
    )
    monkeypatch.setattr(
        admissions_selection, "curriculum_for",
        lambda cursor, code, name: [{"module_code": "SHARED", "module_name": "S", "year": 1},
                                    {"module_code": "DS101", "module_name": "D", "year": 1}],
    )

    with pytest.raises(StudentValidationError, match="transfer"):
        service.update(created.student_id, {"course": "DS"}, actor_id="staff",
                       reason="transfer", idempotency_key="update:course:1")
    service.transfer_course(created.student_id, "DS", actor_id="staff", reason="transfer",
                            idempotency_key="transfer:1")

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT course FROM students").fetchone()[0] == "DS"
        assert dict(conn.execute("SELECT module_code, status FROM student_modules").fetchall()) \
            == {"OLD101": "Transferred", "SHARED": "Enrolled", "DS101": "Enrolled"}


def test_deactivation_preserves_academic_records_and_restore_is_reversible(tmp_path):
    db = tmp_path / "students.db"
    _database(db)
    service = StudentLifecycleService(str(db))
    created = service.create(_command(), actor_id="staff", idempotency_key="create:1")
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO student_grades VALUES (?, 'A')", (created.student_id,))
        conn.commit()

    deactivated = service.deactivate(
        created.student_id, actor_id="staff", reason="left",
        idempotency_key="deactivate:1",
    )
    assert deactivated.status is StudentStatus.WITHDRAWN
    service.restore(created.student_id, actor_id="staff", reason="returned", idempotency_key="restore:1")
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT status,is_active FROM students").fetchone()
        assert row == ("Active", 1)
        assert conn.execute("SELECT COUNT(*) FROM student_grades").fetchone()[0] == 1


def test_purge_requires_dual_control_and_legal_hold_clearance(tmp_path):
    db = tmp_path / "students.db"
    _database(db)
    service = StudentLifecycleService(str(db))
    created = service.create(_command(), actor_id="staff", idempotency_key="create:1")
    service.deactivate(created.student_id, actor_id="staff", reason="left", idempotency_key="deactivate:1")

    with pytest.raises(PurgeControlError):
        service.purge(
            created.student_id, actor_id="staff", approved_by="staff", reason="request",
            case_reference="IG-1", reauthenticated=True, legal_hold_check=lambda _sid: False,
            idempotency_key="purge:1",
        )
    with pytest.raises(PurgeControlError):
        service.purge(
            created.student_id, actor_id="staff", approved_by="privacy", reason="request",
            case_reference="IG-1", reauthenticated=True, legal_hold_check=lambda _sid: True,
            idempotency_key="purge:1",
        )
    queued = service.purge(
        created.student_id, actor_id="staff", approved_by="privacy", reason="request",
        case_reference="IG-1", reauthenticated=True, legal_hold_check=lambda _sid: False,
        idempotency_key="purge:1",
    )
    assert queued.status is StudentStatus.WITHDRAWN
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM university_event_outbox WHERE event_name='student.purge.requested'"
        ).fetchone()[0] == 1
