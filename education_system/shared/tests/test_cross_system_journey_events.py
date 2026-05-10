"""Step 3 tests — wiring student lifecycle into the cross-system bus.

Two concerns:

1. ``shared.cross_system.journey_events`` — the helper functions that
   producers call. Failure-isolation matters: even if the bus or the
   identity layer is broken the parent caller must keep going.

2. End-to-end via a real subsystem service. We point
   ``shared.auth.db.AUTH_DB_FILE`` at a temp DB, instantiate the
   college ``StudentService`` against its own temp DB, create a
   student, and confirm the row lands in ``cross_system_event_outbox`` with a
   matching ``cross_system_event_consumed`` ack after a poll.
"""

import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.shared.auth import db as auth_db_module
from education_system.shared.auth.schema import initialise_auth_db
from education_system.shared.cross_system import identity_service as ids
from education_system.shared.cross_system import journey_events
from education_system.shared.integrations import cross_system_bus as bus


# ── Common fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def auth_db_path(tmp_path):
    p = str(tmp_path / "auth.db")
    initialise_auth_db(p)
    return p


@pytest.fixture(autouse=True)
def _isolate_subscribers():
    bus.clear_subscribers_for_test()
    yield
    bus.clear_subscribers_for_test()


@pytest.fixture
def patched_auth_db(monkeypatch, auth_db_path):
    """Redirect the global ``AUTH_DB_FILE`` so producers that call
    ``connect()`` without a path land in the test DB."""
    monkeypatch.setattr(auth_db_module, "AUTH_DB_FILE",
                        Path(auth_db_path), raising=True)
    return auth_db_path


# ── Helper-level tests ───────────────────────────────────────────────────

class TestRegisterStudentJourney:
    def test_creates_journey_attaches_record_publishes_event(self, auth_db_path):
        jid = journey_events.register_student_journey(
            system="college", pk=42, student_id="SFC0042",
            first_name="Ada", last_name="Lovelace",
            date_of_birth="2008-01-01",
            auth_db_path=auth_db_path,
        )
        assert jid is not None
        # Identity row created and attached.
        row = ids.get_journey(jid, db_path=auth_db_path)
        assert row["college_pk"] == 42
        assert row["college_student_id"] == "SFC0042"
        # Event landed in the outbox.
        conn = sqlite3.connect(auth_db_path)
        try:
            ev = conn.execute(
                "SELECT event_name, source_system, journey_id, "
                "       target_system FROM cross_system_event_outbox "
                "WHERE journey_id = ?",
                (jid,),
            ).fetchone()
        finally:
            conn.close()
        assert ev is not None
        assert ev[0] == bus.EVENT_JOURNEY_REGISTERED
        assert ev[1] == "college"
        assert ev[3] is None  # broadcast

    def test_missing_keys_returns_none_no_publish(self, auth_db_path):
        # No DOB — helper bails out cleanly.
        jid = journey_events.register_student_journey(
            system="college", pk=1, student_id="SFC0001",
            first_name="A", last_name="B", date_of_birth=None,
            auth_db_path=auth_db_path,
        )
        assert jid is None
        conn = sqlite3.connect(auth_db_path)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM cross_system_event_outbox").fetchone()[0]
        finally:
            conn.close()
        assert n == 0

    def test_bus_failure_is_isolated(self, auth_db_path, monkeypatch):
        """Even if publish blows up, the journey row is created and the
        helper returns the journey_id — the caller must not see the
        failure."""
        def _boom(*_a, **_k):
            raise RuntimeError("bus unreachable")
        monkeypatch.setattr(bus, "publish_cross_system", _boom)

        jid = journey_events.register_student_journey(
            system="college", pk=7, student_id="SFC0007",
            first_name="Be", last_name="Stoic",
            date_of_birth="2008-03-03",
            auth_db_path=auth_db_path,
        )
        assert jid is not None
        assert ids.get_journey(jid, db_path=auth_db_path) is not None


class TestRecordStudentTransition:
    def test_records_and_publishes(self, auth_db_path):
        jid = ids.get_or_create_journey(
            first_name="Carol", last_name="Chen",
            date_of_birth="2007-04-04", current_system="school",
            db_path=auth_db_path,
        )
        ok = journey_events.record_student_transition(
            jid, from_system="school", to_system="college",
            reason="transfer", notes="Imported from secondary",
            auth_db_path=auth_db_path,
        )
        assert ok is True
        # Transition row + bus event both written.
        transitions = ids.list_transitions(jid, db_path=auth_db_path)
        assert any(t["from_system"] == "school" and t["to_system"] == "college"
                   for t in transitions)
        conn = sqlite3.connect(auth_db_path)
        try:
            row = conn.execute(
                "SELECT event_name, journey_id FROM cross_system_event_outbox "
                " WHERE event_name = ? AND journey_id = ?",
                (bus.EVENT_JOURNEY_TRANSITIONED, jid),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None


class TestJourneyIdLookup:
    def test_lookup_by_pk(self, auth_db_path):
        jid = ids.get_or_create_journey(
            first_name="Dee", last_name="Day", date_of_birth="2007-05-05",
            current_system="college", db_path=auth_db_path,
        )
        ids.attach_system_record(jid, "college", pk=11, student_id="SFC0011",
                                  db_path=auth_db_path)
        assert journey_events.journey_id_for_system_record(
            "college", pk=11, auth_db_path=auth_db_path,
        ) == jid

    def test_lookup_by_student_id(self, auth_db_path):
        jid = ids.get_or_create_journey(
            first_name="Eli", last_name="Eel", date_of_birth="2007-06-06",
            current_system="university", db_path=auth_db_path,
        )
        ids.attach_system_record(jid, "university", student_id="C9000001",
                                  db_path=auth_db_path)
        assert journey_events.journey_id_for_system_record(
            "university", student_id="C9000001", auth_db_path=auth_db_path,
        ) == jid


# ── End-to-end via the college service ───────────────────────────────────

class TestCollegeServiceIntegration:
    """A full create-student round-trip writes through to the bus and
    a polling consumer acks it."""

    def test_create_student_emits_event_and_polling_consumer_acks(
        self, tmp_path, patched_auth_db,
    ):
        # Set up a minimal college DB by running its init_db.
        from education_system.college_system.infrastructure.database.schema import (
            init_db,
        )
        from education_system.college_system.modules.domain.students.services.student_service import (
            StudentService,
        )
        college_db = str(tmp_path / "college.db")
        init_db(college_db)

        svc = StudentService(college_db)
        student = svc.create_student(
            first_name="Felicity", last_name="Smoak",
            date_of_birth="2008-07-07",
        )
        assert student["journey_id"] is not None

        # Identity attached + event in the outbox.
        row = ids.find_journey_by_student_id(
            "college", student["student_id"], db_path=patched_auth_db,
        )
        assert row is not None
        assert row["college_pk"] == student["id"]

        conn = sqlite3.connect(patched_auth_db)
        try:
            n_events = conn.execute(
                "SELECT COUNT(*) FROM cross_system_event_outbox "
                " WHERE event_name = ? AND journey_id = ?",
                (bus.EVENT_JOURNEY_REGISTERED, row["journey_id"]),
            ).fetchone()[0]
        finally:
            conn.close()
        assert n_events == 1

        # A subscriber on the university side should pick it up via poll.
        seen: list[dict] = []
        bus.subscribe(bus.EVENT_JOURNEY_REGISTERED, seen.append,
                       handler_name="test.uni_subscriber")
        n = bus.poll_and_dispatch("university", db_path=patched_auth_db)
        assert n == 1
        assert seen and seen[0]["journey_id"] == row["journey_id"]
        assert seen[0]["payload"]["system"] == "college"
        assert seen[0]["payload"]["student_id"] == student["student_id"]

        # Ack persisted with status='ok'.
        conn = sqlite3.connect(patched_auth_db)
        try:
            ack = conn.execute(
                "SELECT status, attempts FROM cross_system_event_consumed "
                " WHERE consumer_system = 'university' "
                "   AND consumer_handler = 'test.uni_subscriber'",
            ).fetchone()
        finally:
            conn.close()
        assert ack is not None
        assert ack[0] == "ok"
        assert ack[1] == 1

    def test_create_student_without_dob_skips_journey_silently(
        self, tmp_path, patched_auth_db,
    ):
        from education_system.college_system.infrastructure.database.schema import (
            init_db,
        )
        from education_system.college_system.modules.domain.students.services.student_service import (
            StudentService,
        )
        college_db = str(tmp_path / "college.db")
        init_db(college_db)
        svc = StudentService(college_db)
        student = svc.create_student(
            first_name="Greg", last_name="House", date_of_birth=None,
        )
        # Student created fine; journey_id not set.
        assert student["journey_id"] is None
        conn = sqlite3.connect(patched_auth_db)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM cross_system_event_outbox").fetchone()[0]
        finally:
            conn.close()
        assert n == 0
