"""Tests for ``admissions/sixthform_intake`` — the university-side consumer that
admits sixth-form leavers arriving on the cross-system progression bus.

Coverage:
- pure helpers ``_age_from_dob`` / ``_new_student_id``;
- ``_admit_student`` against a **temp** ``students`` DB (DEFAULT_DB_PATH
  monkeypatched — never the live app DB) with a fake identity service, exercising
  the fresh-admit, already-admitted, name-fallback and id-exhaustion paths;
- ``_stamp_journey_id`` add-column vs existing-column branches;
- ``_import_medical`` success and swallowed-failure;
- the ``handle_progression_completed`` routing branches;
- ``register_intake_consumer`` idempotency and ``drain_intake`` wiring.
"""

from datetime import datetime

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.shared.integrations import cross_system_bus
from education_system.post_18.university_system.modules.domain.admissions import (
    sixthform_intake as si,
)

_DB_PATH_ATTR = (
    "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH"
)

# Minimal students schema matching the columns the repo reads/writes.
_STUDENTS_SCHEMA = """
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,
    email_address TEXT,
    title TEXT,
    first_name TEXT,
    middle_name TEXT,
    last_name TEXT,
    gender TEXT,
    dob TEXT,
    age INTEGER,
    course TEXT,
    registration_datetime TEXT,
    status TEXT,
    enrollment_date TEXT
);
"""


class _FixedDatetime(datetime):
    """datetime whose now() is frozen; strptime etc. inherit real behaviour."""

    @classmethod
    def now(cls, tz=None):  # noqa: D401 - test helper
        return datetime(2026, 7, 23, 12, 0, 0)


class FakeIdentity:
    """Records link/transition calls and returns a canned journey from get()."""

    def __init__(self, journey=None):
        self._journey = journey
        self.links = []
        self.transitions = []

    def get(self, journey_id):
        return self._journey

    def link_system(self, journey_id, system, **kwargs):
        self.links.append((journey_id, system, kwargs))

    def record_transition(self, journey_id, **kwargs):
        self.transitions.append((journey_id, kwargs))


@pytest.fixture()
def temp_students_db(tmp_path, monkeypatch):
    """Point the shared DB layer at a temp file seeded with a students table."""
    db_path = str(tmp_path / "uni.db")
    monkeypatch.setattr(_DB_PATH_ATTR, db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(_STUDENTS_SCHEMA)
    conn.commit()
    conn.close()
    return db_path


def _rows(db_path, query, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# _age_from_dob
# ---------------------------------------------------------------------------

class TestAgeFromDob:
    @pytest.fixture(autouse=True)
    def _freeze(self, monkeypatch):
        monkeypatch.setattr(si, "datetime", _FixedDatetime)

    def test_none_dob_returns_none(self):
        assert si._age_from_dob(None) is None

    def test_empty_string_returns_none(self):
        assert si._age_from_dob("") is None

    def test_malformed_returns_none(self):
        assert si._age_from_dob("not-a-date") is None

    def test_invalid_month_returns_none(self):
        assert si._age_from_dob("2005-13-01") is None

    def test_birthday_already_passed(self):
        # now = 2026-07-23; Jan birthday already happened this year.
        assert si._age_from_dob("2005-01-15") == 21

    def test_birthday_not_yet_reached(self):
        # December birthday hasn't happened yet in July.
        assert si._age_from_dob("2005-12-15") == 20

    def test_birthday_today_counts(self):
        assert si._age_from_dob("2005-07-23") == 21

    def test_day_before_birthday(self):
        assert si._age_from_dob("2005-07-24") == 20


# ---------------------------------------------------------------------------
# _new_student_id
# ---------------------------------------------------------------------------

class TestNewStudentId:
    def test_shape_and_range(self):
        for _ in range(200):
            sid = si._new_student_id()
            assert isinstance(sid, str)
            assert len(sid) == 7
            assert sid.isdigit()
            assert 1000000 <= int(sid) <= 9999999


# ---------------------------------------------------------------------------
# _admit_student
# ---------------------------------------------------------------------------

class TestAdmitStudent:
    def test_already_admitted_returns_none_and_writes_nothing(
        self, temp_students_db, monkeypatch
    ):
        fake = FakeIdentity(journey={"university_student_id": "9999999"})
        monkeypatch.setattr(si, "identity_service", fake)

        result = si._admit_student("J-1", {"first_name": "Amy"})

        assert result is None
        assert _rows(temp_students_db, "SELECT * FROM students") == []
        assert fake.links == []
        assert fake.transitions == []

    def test_fresh_admit_persists_and_links(self, temp_students_db, monkeypatch):
        fake = FakeIdentity(journey={"university_student_id": None})
        monkeypatch.setattr(si, "identity_service", fake)
        monkeypatch.setattr(si, "_new_student_id", lambda: "1234567")

        sid = si._admit_student(
            "J-2",
            {
                "first_name": "Amy",
                "last_name": "Bell",
                "title": "Ms",
                "gender": "F",
                "date_of_birth": "2005-03-01",
            },
        )

        assert sid == "1234567"
        rows = _rows(temp_students_db, "SELECT * FROM students")
        assert len(rows) == 1
        row = rows[0]
        assert row["student_id"] == "1234567"
        assert row["first_name"] == "Amy"
        assert row["last_name"] == "Bell"
        assert row["email_address"] == "C1234567@tees.ac.uk"
        assert row["course"] == "CS"
        assert row["status"] == "Active"
        assert row["dob"] == "2005-03-01"

        # journey stamped onto the students row
        stamped = _rows(
            temp_students_db,
            "SELECT journey_id FROM students WHERE student_id = ?",
            ("1234567",),
        )
        assert stamped[0]["journey_id"] == "J-2"

        # identity service linked + transition recorded
        assert fake.links == [
            ("J-2", "university", {"student_id": "1234567", "set_current": True})
        ]
        assert len(fake.transitions) == 1
        _, tkw = fake.transitions[0]
        assert tkw["from_system"] == "college"
        assert tkw["to_system"] == "university"

    def test_names_fall_back_to_journey_legal_names(
        self, temp_students_db, monkeypatch
    ):
        fake = FakeIdentity(
            journey={
                "university_student_id": None,
                "legal_first_name": "Cara",
                "legal_last_name": "Dunn",
                "date_of_birth": "2004-09-09",
            }
        )
        monkeypatch.setattr(si, "identity_service", fake)
        monkeypatch.setattr(si, "_new_student_id", lambda: "2222222")

        sid = si._admit_student("J-3", {})  # empty payload

        assert sid == "2222222"
        row = _rows(temp_students_db, "SELECT * FROM students")[0]
        assert row["first_name"] == "Cara"
        assert row["last_name"] == "Dunn"
        assert row["dob"] == "2004-09-09"

    def test_id_exhaustion_raises(self, temp_students_db, monkeypatch):
        fake = FakeIdentity(journey=None)
        monkeypatch.setattr(si, "identity_service", fake)
        # Always collide with a pre-existing row.
        monkeypatch.setattr(si, "_new_student_id", lambda: "7654321")
        conn = sqlite3.connect(temp_students_db)
        conn.execute(
            "INSERT INTO students (student_id, status) VALUES ('7654321', 'Active')"
        )
        conn.commit()
        conn.close()

        with pytest.raises(RuntimeError, match="Could not allocate a free"):
            si._admit_student("J-4", {"first_name": "Zed"})

        # No second row created; the pre-existing one is untouched count-wise.
        assert len(_rows(temp_students_db, "SELECT * FROM students")) == 1


# ---------------------------------------------------------------------------
# _stamp_journey_id
# ---------------------------------------------------------------------------

class TestStampJourneyId:
    def test_adds_column_when_missing(self, temp_students_db):
        conn = sqlite3.connect(temp_students_db)
        conn.execute("INSERT INTO students (student_id) VALUES ('1000001')")
        conn.commit()
        conn.close()

        si._stamp_journey_id("1000001", "J-9")

        row = _rows(
            temp_students_db,
            "SELECT journey_id FROM students WHERE student_id = ?",
            ("1000001",),
        )[0]
        assert row["journey_id"] == "J-9"

    def test_uses_existing_column(self, temp_students_db):
        conn = sqlite3.connect(temp_students_db)
        conn.execute("ALTER TABLE students ADD COLUMN journey_id TEXT")
        conn.execute("INSERT INTO students (student_id) VALUES ('1000002')")
        conn.commit()
        conn.close()

        si._stamp_journey_id("1000002", "J-10")

        row = _rows(
            temp_students_db,
            "SELECT journey_id FROM students WHERE student_id = ?",
            ("1000002",),
        )[0]
        assert row["journey_id"] == "J-10"


# ---------------------------------------------------------------------------
# _import_medical
# ---------------------------------------------------------------------------

class TestImportMedical:
    def test_success_delegates(self, monkeypatch):
        import education_system.post_18.university_system.modules.domain.health.records.sixth_form_import as sfi

        captured = {}
        monkeypatch.setattr(
            sfi,
            "import_from_sixth_form",
            lambda **kw: captured.update(kw),
        )

        si._import_medical("1111111", "SF-1")

        assert captured == {"uni_student_id": "1111111", "sf_student_id": "SF-1"}

    def test_failure_is_swallowed(self, monkeypatch):
        import education_system.post_18.university_system.modules.domain.health.records.sixth_form_import as sfi

        def _boom(**kw):
            raise RuntimeError("medical db down")

        monkeypatch.setattr(sfi, "import_from_sixth_form", _boom)

        # Must not raise — admission still stands.
        si._import_medical("1111111", "SF-1")


# ---------------------------------------------------------------------------
# handle_progression_completed
# ---------------------------------------------------------------------------

class TestHandleProgressionCompleted:
    def test_ignores_events_for_other_systems(self, monkeypatch):
        called = []
        monkeypatch.setattr(si, "_admit_student", lambda *a, **k: called.append(a))
        monkeypatch.setattr(si, "_import_medical", lambda *a, **k: called.append(a))

        si.handle_progression_completed(
            {"target_system": "primary", "journey_id": "J-1", "payload": {}}
        )
        assert called == []

    def test_missing_journey_id_is_ignored(self, monkeypatch):
        admit = []
        monkeypatch.setattr(si, "_admit_student", lambda *a, **k: admit.append(a))
        monkeypatch.setattr(si, "_import_medical", lambda *a, **k: admit.append("med"))

        si.handle_progression_completed(
            {"target_system": "university", "payload": {"sf_student_id": "SF-1"}}
        )
        assert admit == []

    def test_admits_and_imports_medical(self, monkeypatch):
        admit_args = {}
        medical_args = {}
        monkeypatch.setattr(
            si,
            "_admit_student",
            lambda jid, payload: admit_args.update(jid=jid, payload=payload) or "5555555",
        )
        monkeypatch.setattr(
            si,
            "_import_medical",
            lambda uni, sf: medical_args.update(uni=uni, sf=sf),
        )

        si.handle_progression_completed(
            {
                "target_system": "university",
                "journey_id": "J-7",
                "payload": {"sf_student_id": "SF-7", "first_name": "Ed"},
            }
        )

        assert admit_args["jid"] == "J-7"
        assert medical_args == {"uni": "5555555", "sf": "SF-7"}

    def test_target_none_is_accepted(self, monkeypatch):
        admit_args = {}
        monkeypatch.setattr(
            si, "_admit_student", lambda jid, payload: admit_args.update(jid=jid) or "6"
        )
        monkeypatch.setattr(si, "_import_medical", lambda *a, **k: None)

        si.handle_progression_completed(
            {"journey_id": "J-8", "payload": {"sf_student_id": "SF-8"}}
        )
        assert admit_args["jid"] == "J-8"

    def test_no_medical_import_when_not_admitted(self, monkeypatch):
        medical = []
        monkeypatch.setattr(si, "_admit_student", lambda jid, payload: None)
        monkeypatch.setattr(si, "_import_medical", lambda *a, **k: medical.append(a))

        si.handle_progression_completed(
            {
                "target_system": "university",
                "journey_id": "J-9",
                "payload": {"sf_student_id": "SF-9"},
            }
        )
        assert medical == []

    def test_no_medical_import_without_sf_id(self, monkeypatch):
        medical = []
        monkeypatch.setattr(si, "_admit_student", lambda jid, payload: "7777777")
        monkeypatch.setattr(si, "_import_medical", lambda *a, **k: medical.append(a))

        si.handle_progression_completed(
            {"target_system": "university", "journey_id": "J-10", "payload": {}}
        )
        assert medical == []


# ---------------------------------------------------------------------------
# register_intake_consumer / drain_intake
# ---------------------------------------------------------------------------

class TestConsumerWiring:
    def test_register_is_idempotent(self, monkeypatch):
        monkeypatch.setattr(si, "_registered", False)
        calls = []
        monkeypatch.setattr(
            cross_system_bus,
            "subscribe",
            lambda event, handler, handler_name=None: calls.append(handler_name),
        )

        si.register_intake_consumer()
        si.register_intake_consumer()

        assert calls == ["university.admissions.sixthform_intake"]
        assert si._registered is True

    def test_drain_registers_then_polls(self, monkeypatch):
        registered = []
        monkeypatch.setattr(
            si, "register_intake_consumer", lambda: registered.append(True)
        )
        seen = {}
        monkeypatch.setattr(
            cross_system_bus,
            "poll_and_dispatch",
            lambda system, db_path=None: seen.update(system=system, db_path=db_path) or 4,
        )

        result = si.drain_intake(db_path="/tmp/x.db")

        assert result == 4
        assert registered == [True]
        assert seen == {"system": "university", "db_path": "/tmp/x.db"}
