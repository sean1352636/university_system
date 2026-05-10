"""Step 4 — college UCAS firm-choice → university draft student flow.

End-to-end:

1. College ``StudentService.create_student`` registers a journey
   (covered by step 3).
2. ``UCASService.create_application`` + ``add_choice`` + ``set_firm_insurance``
   publishes ``student.progression.offered`` targeted at the
   university.
3. The ``cross_system_progression.on_progression_offered`` subscriber,
   wired against a temp university DB, creates a ``Pending`` row and
   attaches the per-system record to the shared journey.
4. ``cross_system_event_consumed`` shows the ack.

The university subsystem is exercised against a *minimal* university
``students`` table built with the same shape as
``database_utils.init_db`` produces — running the real ``init_db`` is
heavy and irrelevant to this test.
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
from education_system.shared.integrations import cross_system_bus as bus

from education_system.college_system.infrastructure.database.schema import (
    init_db as college_init_db,
)
from education_system.college_system.modules.domain.students.services.student_service import (
    StudentService,
)
from education_system.college_system.modules.domain.ucas.services.ucas_service import (
    UCASService,
)

from education_system.university_system.modules.domain.admissions.services import (
    cross_system_progression,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_subscribers():
    bus.clear_subscribers_for_test()
    yield
    bus.clear_subscribers_for_test()


@pytest.fixture
def auth_db_path(tmp_path, monkeypatch):
    """Real shared auth DB with all step 1+ tables; producers fall back
    here via ``connect()``."""
    p = str(tmp_path / "auth.db")
    initialise_auth_db(p)
    monkeypatch.setattr(auth_db_module, "AUTH_DB_FILE", Path(p), raising=True)
    return p


@pytest.fixture
def college_db_path(tmp_path):
    p = str(tmp_path / "college.db")
    college_init_db(p)
    return p


@pytest.fixture
def university_db_path(tmp_path):
    """Minimal university students table — same shape as
    ``database_utils.init_db`` produces, plus the ``journey_id`` column
    from step 2."""
    p = str(tmp_path / "university.db")
    conn = sqlite3.connect(p)
    conn.execute(
        """CREATE TABLE students (
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
            status TEXT DEFAULT 'Active',
            enrollment_date TEXT,
            journey_id TEXT
        )"""
    )
    conn.commit()
    conn.close()
    return p


@pytest.fixture
def wire_uni(university_db_path, auth_db_path):
    """Subscribe the university progression handler against the temp DBs."""
    cross_system_progression.wire_subscribers(
        university_db_path=university_db_path,
        auth_db_path=auth_db_path,
    )
    return university_db_path


def _stage_offer(college_db_path: str) -> tuple[StudentService, UCASService,
                                                 dict, int, int]:
    """Create a college student + a UCAS application + a single choice.
    Returns ``(student_svc, ucas_svc, student, application_id, choice_id)``."""
    student_svc = StudentService(college_db_path)
    ucas_svc = UCASService(college_db_path)
    student = student_svc.create_student(
        first_name="Felicity", last_name="Smoak",
        date_of_birth="2008-07-07",
    )
    app = ucas_svc.create_application(student["id"], academic_year="2026/27")
    choice = ucas_svc.add_choice(
        app["id"],
        university_name="Tees University",
        course_title="BSc Computer Science",
        ucas_code="G400",
        choice_number=1,
    )
    return student_svc, ucas_svc, student, app["id"], choice["id"]


# ── Producer-only: set_firm_insurance writes the outbox row ──────────────

class TestProducerEmitsProgressionOffered:
    def test_firm_choice_publishes_event_targeted_at_university(
        self, college_db_path, auth_db_path,
    ):
        _, ucas_svc, student, app_id, choice_id = _stage_offer(college_db_path)
        ucas_svc.set_firm_insurance(app_id, firm_id=choice_id)

        conn = sqlite3.connect(auth_db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM cross_system_event_outbox "
                " WHERE event_name = ? ORDER BY created_at DESC LIMIT 1",
                (bus.EVENT_STUDENT_PROGRESSION_OFFERED,),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row["source_system"] == "college"
        assert row["target_system"] == "university"
        # Journey id was set by step 3's create_student hook.
        assert row["journey_id"] == student["journey_id"]
        assert "Tees University" in row["payload_json"]
        assert "G400" in row["payload_json"]

    def test_no_event_when_journey_missing(
        self, college_db_path, auth_db_path,
    ):
        # Make a college student WITHOUT a DOB — step 3 will skip
        # the journey, so step 4 has nothing to publish either.
        student_svc = StudentService(college_db_path)
        ucas_svc = UCASService(college_db_path)
        student = student_svc.create_student(
            first_name="Greg", last_name="House", date_of_birth=None,
        )
        assert student["journey_id"] is None
        app = ucas_svc.create_application(student["id"])
        choice = ucas_svc.add_choice(
            app["id"], university_name="Tees", course_title="X")
        ucas_svc.set_firm_insurance(app["id"], firm_id=choice["id"])

        conn = sqlite3.connect(auth_db_path)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM cross_system_event_outbox "
                " WHERE event_name = ?",
                (bus.EVENT_STUDENT_PROGRESSION_OFFERED,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert n == 0


# ── End-to-end: producer → poll → consumer creates uni student ──────────

class TestEndToEndProgressionFlow:
    def test_uni_pending_row_created_and_journey_linked(
        self, college_db_path, auth_db_path, wire_uni,
    ):
        university_db_path = wire_uni
        _, ucas_svc, student, app_id, choice_id = _stage_offer(college_db_path)
        ucas_svc.set_firm_insurance(app_id, firm_id=choice_id)

        # University poller picks the event up.
        n = bus.poll_and_dispatch("university", db_path=auth_db_path)
        assert n == 1

        # Uni students table now has one Pending row linked to the journey.
        uni_conn = sqlite3.connect(university_db_path)
        uni_conn.row_factory = sqlite3.Row
        try:
            rows = uni_conn.execute(
                "SELECT student_id, first_name, last_name, dob, course, "
                "       status, journey_id, email_address "
                "  FROM students").fetchall()
        finally:
            uni_conn.close()
        assert len(rows) == 1
        uni_row = rows[0]
        assert uni_row["status"] == "Pending"
        assert uni_row["journey_id"] == student["journey_id"]
        assert uni_row["first_name"] == "Felicity"
        assert uni_row["last_name"] == "Smoak"
        assert uni_row["dob"] == "2008-07-07"
        assert uni_row["course"] == "BSc Computer Science"
        assert uni_row["email_address"].startswith("C")
        assert uni_row["email_address"].endswith("@tees.ac.uk")

        # Shared journey row now has the university link.
        journey = ids.get_journey(student["journey_id"], db_path=auth_db_path)
        assert journey["university_student_id"] == uni_row["student_id"]
        assert journey["current_system"] == "university"

        # Transition row recorded.
        transitions = ids.list_transitions(
            student["journey_id"], db_path=auth_db_path)
        assert any(t["to_system"] == "university"
                   and t["from_system"] == "college"
                   and t["reason"] == "progression"
                   for t in transitions)

        # Ack persisted.
        conn = sqlite3.connect(auth_db_path)
        try:
            ack = conn.execute(
                "SELECT status FROM cross_system_event_consumed "
                " WHERE consumer_system = 'university'",
            ).fetchone()
        finally:
            conn.close()
        assert ack and ack[0] == "ok"

    def test_redelivery_is_idempotent(
        self, college_db_path, auth_db_path, wire_uni,
    ):
        university_db_path = wire_uni
        _, ucas_svc, student, app_id, choice_id = _stage_offer(college_db_path)
        ucas_svc.set_firm_insurance(app_id, firm_id=choice_id)

        # First poll creates the row + ack.
        bus.poll_and_dispatch("university", db_path=auth_db_path)

        # Re-publish the same logical event under a new event_id (e.g.
        # if the firm choice gets confirmed again). Handler must not
        # double-create a uni student.
        bus.publish_cross_system(
            bus.EVENT_STUDENT_PROGRESSION_OFFERED,
            source_system="college", source_module="redeliver-test",
            journey_id=student["journey_id"], target_system="university",
            target_university="Tees University",
            course_title="BSc Computer Science", ucas_code="G400",
            application_id=app_id,
        )
        bus.poll_and_dispatch("university", db_path=auth_db_path)

        uni_conn = sqlite3.connect(university_db_path)
        try:
            n = uni_conn.execute(
                "SELECT COUNT(*) FROM students").fetchone()[0]
        finally:
            uni_conn.close()
        assert n == 1   # still one row; the second event was a no-op

    def test_unknown_journey_id_drops_silently(
        self, college_db_path, auth_db_path, wire_uni,
    ):
        # Publish a progression event for a journey that doesn't exist.
        bus.publish_cross_system(
            bus.EVENT_STUDENT_PROGRESSION_OFFERED,
            source_system="college", source_module="t",
            journey_id="00000000-0000-0000-0000-000000000000",
            target_system="university",
            target_university="Tees", course_title="X",
        )
        # Handler must run, not raise, ack as 'ok' (we don't want endless
        # retries for unrecoverable inputs), and create no uni rows.
        bus.poll_and_dispatch("university", db_path=auth_db_path)
        uni_conn = sqlite3.connect(wire_uni)
        try:
            n = uni_conn.execute(
                "SELECT COUNT(*) FROM students").fetchone()[0]
        finally:
            uni_conn.close()
        assert n == 0
