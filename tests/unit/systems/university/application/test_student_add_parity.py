"""University Add Student asks for what the other systems' add forms ask:
preferred name, postcode and notes on the record; the emergency contact
and medical notes on the health record (``registration_extras``).
Temporary databases only."""

import sqlite3

import pytest

from education_system.systems.university.application.students import record_rules as rr
from education_system.systems.university.application.students import registration_extras as rx
from education_system.systems.university.application.students.lifecycle import (
    StudentCommand,
    StudentLifecycleService,
    StudentValidationError,
)
from education_system.systems.university.domains.learners.domain import student_lifecycle

SCHEMA = [
    """CREATE TABLE students (
        student_id TEXT PRIMARY KEY, email_address TEXT UNIQUE, title TEXT, first_name TEXT,
        middle_name TEXT, last_name TEXT, gender TEXT, dob TEXT, age INTEGER, course TEXT,
        registration_datetime TEXT, status TEXT, enrollment_date TEXT, is_active INTEGER,
        entry_qualifications TEXT, ucas_tariff INTEGER, phone TEXT, address TEXT,
        nationality TEXT, mode_of_study TEXT, pronouns TEXT, emergency_contact TEXT)""",
    "CREATE TABLE courses (course_code TEXT PRIMARY KEY, course_name TEXT, status TEXT, "
    "current_enrollment INTEGER DEFAULT 0)",
    "INSERT INTO courses VALUES ('CS', 'Computer Science', 'active', 0)",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, student_id TEXT, "
    "first_name TEXT, last_name TEXT, updated_at TEXT)",
    """CREATE TABLE emergency_contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT,
        contact_name TEXT, relationship TEXT, phone_primary TEXT, phone_secondary TEXT,
        email TEXT, address TEXT, priority_order INTEGER, medical_decision_maker INTEGER DEFAULT 0,
        created_at TEXT, is_primary INTEGER DEFAULT 0, name TEXT, phone TEXT)""",
    """CREATE TABLE medical_info (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
        blood_type TEXT, allergies TEXT, medications TEXT, conditions TEXT, doctor_name TEXT,
        doctor_phone TEXT, insurance_provider TEXT, insurance_policy TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
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
def service(tmp_path):
    db = tmp_path / "students.db"
    with sqlite3.connect(db) as conn:
        for ddl in SCHEMA:
            conn.execute(ddl)
    return StudentLifecycleService(str(db), auth_db_path=str(tmp_path / "auth.db"))


def _create(service, **kw):
    values = dict(first_name="Ana", last_name="López", dob="2004-04-04", course="CS",
                  gender="female")
    values.update(kw)
    return service.create(StudentCommand(**values), actor_id="admin",
                          idempotency_key=f"c:{sorted(kw.items())}").student_id


def _one(service, sql, *args):
    with sqlite3.connect(service.db_path) as conn:
        return conn.execute(sql, args).fetchall()


# ── rules ────────────────────────────────────────────────────────────

def test_same_relationship_list_as_fe_college():
    from education_system.systems.fe_college import config as fe

    assert rr.EMERGENCY_RELATIONSHIPS == fe.EMERGENCY_RELATIONSHIPS


@pytest.mark.parametrize("values, field", [
    ({"emergency_contact_name": "Ann"}, "emergency_contact"),
    ({"emergency_contact_phone": "07700 900123"}, "emergency_contact"),
    ({"emergency_contact_name": "Ann", "emergency_contact_phone": "abc"},
     "emergency_contact_phone"),
    ({"emergency_contact_name": "Ann", "emergency_contact_phone": "07700 900123",
      "emergency_contact_relationship": "Neighbour"}, "emergency_contact_relationship"),
    ({"medical_notes": "x" * (rr.NOTES_MAX_LENGTH + 1)}, "medical_notes"),
])
def test_registration_rules(values, field):
    assert field in rr.validate_registration(values)


def test_complete_or_blank_contact_is_fine():
    assert rr.validate_registration({}) == {}
    assert rr.validate_registration({"emergency_contact_name": "Ann",
                                     "emergency_contact_phone": "07700 900123",
                                     "emergency_contact_relationship": "parent"}) == {}


@pytest.mark.parametrize("raw, stored", [
    ("ts1 3ba", "TS1 3BA"), ("SW1A1AA", "SW1A 1AA"), ("10115", "10115"), ("", None)])
def test_postcode_normalised_uk_kept_overseas(raw, stored):
    assert rr.normalise_details({"postcode": raw})["postcode"] == stored


def test_detail_limits():
    errors = rr.validate_details({"preferred_name": "x" * 41, "postcode": "!!",
                                  "notes": "x" * (rr.NOTES_MAX_LENGTH + 1)})
    assert set(errors) == {"preferred_name", "postcode", "notes"}


# ── create ───────────────────────────────────────────────────────────

def test_profile_fields_stored_on_the_record(service):
    sid = _create(service, preferred_name="Ani", postcode="ts1 3ba", notes="Rows for the club")
    assert _one(service, "SELECT preferred_name, postcode, notes FROM students "
                         "WHERE student_id = ?", sid) == [("Ani", "TS1 3BA", "Rows for the club")]


def test_emergency_contact_goes_to_the_health_record(service):
    sid = _create(service, emergency_contact_name="Ann López",
                  emergency_contact_relationship="parent",
                  emergency_contact_phone="07700 900123")
    assert _one(service, "SELECT contact_name, relationship, phone_primary, is_primary, "
                         "priority_order FROM emergency_contacts WHERE student_id = ?", sid
                ) == [("Ann López", "Parent", "07700 900123", 1, 1)]
    assert _one(service, "SELECT emergency_contact FROM students WHERE student_id = ?", sid
                ) == [("Ann López (Parent) 07700 900123",)]


def test_half_a_contact_refuses_the_whole_create(service):
    with pytest.raises(StudentValidationError) as bad:
        _create(service, emergency_contact_name="Ann López")
    assert "emergency_contact" in bad.value.errors
    assert _one(service, "SELECT COUNT(*) FROM students") == [(0,)]


def test_medical_notes_go_to_the_health_record_not_the_history(service):
    sid = _create(service, medical_notes="Asthma; inhaler in bag")
    [(conditions,)] = _one(service, "SELECT conditions FROM medical_info WHERE student_id = ?",
                           sid)
    assert "Asthma; inhaler in bag" in conditions
    history = _one(service, "SELECT field, new_value FROM student_record_changes "
                            "WHERE student_id = ?", sid)
    assert ("medical_record", "medical notes added for the health team") in history
    assert not any("Asthma" in str(v) for _f, v in history)


def test_nothing_given_writes_no_health_rows(service):
    sid = _create(service)
    assert _one(service, "SELECT COUNT(*) FROM emergency_contacts WHERE student_id = ?",
                sid) == [(0,)]
    assert _one(service, "SELECT COUNT(*) FROM medical_info WHERE student_id = ?",
                sid) == [(0,)]


def test_medical_notes_appended_to_an_existing_profile(service):
    sid = _create(service)
    with sqlite3.connect(service.db_path) as conn:
        conn.execute("INSERT INTO medical_info (student_id, conditions) VALUES (?, 'Hay fever')",
                     (sid,))
        assert rx.add_medical_notes(conn, sid, "Peanut allergy", actor_id="admin")
    [(conditions,)] = _one(service, "SELECT conditions FROM medical_info WHERE student_id = ?",
                           sid)
    assert conditions.startswith("Hay fever") and "Peanut allergy" in conditions


# ── edit ─────────────────────────────────────────────────────────────

def test_new_fields_are_editable_with_history(service):
    sid = _create(service, notes="old")
    result = service.update(sid, {"postcode": "sw1a1aa", "preferred_name": "Ani", "notes": None},
                            actor_id="admin", reason="Moved house", idempotency_key="u1")
    assert set(result.changed_fields) == {"postcode", "preferred_name", "notes"}
    assert _one(service, "SELECT postcode, preferred_name, notes FROM students "
                         "WHERE student_id = ?", sid) == [("SW1A 1AA", "Ani", None)]


# ── Gender and address, the same as every system ─────────────────────

def test_same_five_gender_options_as_fe_college():
    from education_system.systems.fe_college import config as fe
    from education_system.systems.university.application.students.lifecycle import (
        GENDER_OPTIONS,
    )

    assert GENDER_OPTIONS == fe.GENDERS


@pytest.mark.parametrize("picked, stored", [
    ("Female", "female"), ("Non-binary", "non-binary"),
    ("Prefer not to say", "prefer not to say")])
def test_gender_label_stored_lower_case(service, picked, stored):
    sid = _create(service, gender=picked)
    assert _one(service, "SELECT gender FROM students WHERE student_id = ?", sid) == [(stored,)]


def test_unknown_gender_refused_on_update(service):
    sid = _create(service)
    with pytest.raises(StudentValidationError) as bad:
        service.update(sid, {"gender": "robot"}, actor_id="admin", reason="x",
                       idempotency_key="g")
    assert "gender" in bad.value.errors


def test_address_lines_build_the_address(service):
    sid = _create(service, address_line1="1 High St", address_line2="Flat 2", town="Leeds")
    row = "SELECT address, address_line1, address_line2, town FROM students WHERE student_id = ?"
    assert _one(service, row, sid) == [("1 High St, Flat 2, Leeds", "1 High St", "Flat 2",
                                        "Leeds")]
    service.update(sid, {"town": "York"}, actor_id="admin", reason="moved", idempotency_key="t")
    assert _one(service, row, sid) == [("1 High St, Flat 2, York", "1 High St", "Flat 2",
                                        "York")]


def test_plain_address_from_api_is_split(service):
    sid = _create(service, address="9 Low Rd, Hull")
    assert _one(service, "SELECT address_line1, address_line2, town FROM students "
                         "WHERE student_id = ?", sid) == [("9 Low Rd", None, "Hull")]
