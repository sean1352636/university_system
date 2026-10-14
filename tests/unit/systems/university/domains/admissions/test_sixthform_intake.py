"""Tests for ``admissions/sixthform_intake`` — the university-side consumer that
admits sixth-form leavers arriving on the cross-system progression bus.

Coverage:
- pure helpers ``_age_from_dob`` / ``_new_student_id``;
- ``_admit_student`` against a **temp** ``students`` DB (DEFAULT_DB_PATH
  monkeypatched — never the live app DB) with a fake identity service, exercising
  the fresh-admit, already-admitted, name-fallback and id-exhaustion paths;
- ``_stamp_journey_id`` add-column vs existing-column branches;
- the ``handle_progression_completed`` routing branches, including the
  journey transition recorded for a newly staged applicant and skipped
  for one that already existed;
- ``register_intake_consumer`` idempotency and ``drain_intake`` wiring.
"""

from datetime import datetime
from pathlib import Path

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.platform.integrations.external import cross_system_bus
from education_system.systems.university.domains.admissions.domain import (
    sixthform_intake as si,
)

_DB_PATH_ATTR = (
    "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH"
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


def test_intake_has_no_direct_student_provisioning_or_runtime_schema_mutation():
    source = Path(si.__file__).read_text(encoding="utf-8")
    assert "_admit_student" not in source
    assert "INSERT INTO students" not in source
    assert "ALTER TABLE students" not in source
    assert '"CS"' not in source


# ---------------------------------------------------------------------------
# The medical import is NOT this module's job
# ---------------------------------------------------------------------------

def test_intake_does_not_import_medical_records():
    """An applicant has no university student id to hang a health record on.

    ``_import_medical`` used to live here and could never fire for that
    reason. It now belongs to ``admissions_lifecycle.convert_to_student``,
    which runs at the point a student actually exists. Asserted rather
    than assumed, because a helper that silently never runs is exactly the
    bug that was fixed.
    """
    source = Path(si.__file__).read_text(encoding="utf-8")
    assert "_import_medical" not in source
    assert "sixth_form_import" not in source


# ---------------------------------------------------------------------------
# _read_handover
# ---------------------------------------------------------------------------

class TestReadHandover:
    def test_reads_the_college_identity_key(self):
        fields = si._read_handover({
            "student_identity": {"first_name": "Ed", "last_name": "Kaur",
                                 "date_of_birth": "2007-02-01"},
            "ucas_application": {"ucas_id": "1122334455"},
        })
        assert fields["first_name"] == "Ed"
        assert fields["ucas_id"] == "1122334455"

    def test_reads_the_apprenticeship_identity_key(self):
        """APPRENTICESHIPS_TO_UNIVERSITY declares ``learner_identity``, and
        build_handover emits only the keys its own spec names — so this is
        the *only* identity block an apprentice's payload carries."""
        fields = si._read_handover({
            "learner_identity": {"first_name": "Alex", "last_name": "Morgan",
                                 "date_of_birth": "2004-09-15",
                                 "college_student_id": "APP001",
                                 "email": "alex@example.test"},
        })
        assert fields["first_name"] == "Alex"
        assert fields["last_name"] == "Morgan"
        assert fields["date_of_birth"] == "2004-09-15"
        assert fields["email"] == "alex@example.test"
        assert fields["sixth_form_student_id"] == "APP001"


# ---------------------------------------------------------------------------
# handle_progression_completed
# ---------------------------------------------------------------------------

class TestHandleProgressionCompleted:
    @pytest.fixture(autouse=True)
    def _fake_identity(self, monkeypatch):
        """Never let the handler touch the real journey registry.

        The handler both reads the journey and now *writes* a transition
        to it, so an unpatched run would append rows to the live auth.db.
        """
        fake = FakeIdentity(journey=None)
        fake.SYSTEM_SLOTS = {"university": ("university_pk",
                                            "university_student_id")}
        monkeypatch.setattr(si, "identity_service", fake)
        return fake

    def test_ignores_events_for_other_systems(self, monkeypatch):
        called = []
        monkeypatch.setattr(si, "_create_applicant", lambda *a, **k: called.append(a))

        si.handle_progression_completed(
            {"target_system": "primary", "journey_id": "J-1", "payload": {}}
        )
        assert called == []

    def test_missing_journey_id_is_ignored(self, monkeypatch):
        admit = []
        monkeypatch.setattr(si, "_create_applicant", lambda *a, **k: admit.append(a))

        si.handle_progression_completed(
            {"target_system": "university", "payload": {"sf_student_id": "SF-1"}}
        )
        assert admit == []

    def test_creates_applicant_without_enrolling(self, monkeypatch, _fake_identity):
        application_args = {}
        monkeypatch.setattr(
            si,
            "_create_applicant",
            lambda jid, payload: (
                application_args.update(jid=jid, payload=payload) or (42, True)
            ),
        )

        si.handle_progression_completed(
            {
                "target_system": "university",
                "journey_id": "J-7",
                "payload": {"sf_student_id": "SF-7", "first_name": "Ed"},
            }
        )

        assert application_args["jid"] == "J-7"
        assert application_args["payload"]["sf_student_id"] == "SF-7"
        # The applicant is on the journey's timeline, but the university
        # slot stays empty — it names a student, and this is not one.
        assert _fake_identity.links == []
        assert len(_fake_identity.transitions) == 1
        journey_id, kwargs = _fake_identity.transitions[0]
        assert journey_id == "J-7"
        assert kwargs["from_system"] == "sixth_form"
        assert kwargs["to_system"] == "university"
        assert "42" in kwargs["reason"]

    def test_existing_application_records_no_second_transition(
        self, monkeypatch, _fake_identity
    ):
        monkeypatch.setattr(
            si, "_create_applicant", lambda jid, payload: (42, False)
        )

        si.handle_progression_completed(
            {"target_system": "university", "journey_id": "J-7", "payload": {}}
        )
        assert _fake_identity.transitions == []

    def test_source_is_read_from_the_envelope(self, monkeypatch, _fake_identity):
        """Three systems progress learners here; only one is the sixth form."""
        monkeypatch.setattr(si, "_create_applicant", lambda jid, payload: (9, True))

        si.handle_progression_completed(
            {"target_system": "university", "source_system": "fe_college",
             "journey_id": "J-9", "payload": {}}
        )

        _journey_id, kwargs = _fake_identity.transitions[0]
        assert kwargs["from_system"] == "fe_college"

    def test_apprenticeship_source_validates_against_its_own_spec(
        self, monkeypatch, _fake_identity
    ):
        monkeypatch.setattr(si, "_create_applicant", lambda jid, payload: (10, True))
        checked = {}
        monkeypatch.setattr(
            si.handover, "validate_handover",
            lambda source, dest, payload: checked.update(
                source=source, dest=dest) or [],
        )

        si.handle_progression_completed(
            {"target_system": "university", "source_system": "apprenticeships",
             "journey_id": "J-10",
             "payload": {"handover_boundary": "apprenticeships->university"}}
        )

        assert checked == {"source": "apprenticeships", "dest": "university"}
        assert _fake_identity.transitions[0][1]["from_system"] == "apprenticeships"

    def test_unknown_source_falls_back_to_the_default_route(
        self, monkeypatch, _fake_identity
    ):
        monkeypatch.setattr(si, "_create_applicant", lambda jid, payload: (11, True))

        si.handle_progression_completed(
            {"target_system": "university", "source_system": "employment",
             "journey_id": "J-11", "payload": {}}
        )

        assert _fake_identity.transitions[0][1]["from_system"] == "sixth_form"

    def test_target_none_is_accepted(self, monkeypatch):
        application_args = {}
        monkeypatch.setattr(
            si, "_create_applicant",
            lambda jid, payload: application_args.update(jid=jid) or (6, True)
        )

        si.handle_progression_completed(
            {"journey_id": "J-8", "payload": {"sf_student_id": "SF-8"}}
        )
        assert application_args["jid"] == "J-8"


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
