"""Step 5 — closing the progression loop with ``progression.completed``.

Continues the step-4 flow: once the university confirms enrolment of a
``Pending`` student via ``confirm_enrolment``, the bus carries
``student.progression.completed`` to the college subsystem, which
flips the college student's ``status`` from ``active`` to
``progressed`` and records the back-link to the university student id.
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
from education_system.college_system.modules.domain.students.services import (
    cross_system_progression_consumer as college_consumer,
)
from education_system.college_system.modules.domain.ucas.services.ucas_service import (
    UCASService,
)

from education_system.university_system.modules.domain.admissions.services import (
    cross_system_progression as uni_progression,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_subscribers():
    bus.clear_subscribers_for_test()
    yield
    bus.clear_subscribers_for_test()


@pytest.fixture
def auth_db_path(tmp_path, monkeypatch):
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
    ``database_utils.init_db`` produces, plus the ``journey_id`` column."""
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


def _stage_progression_to_pending(college_db_path, university_db_path,
                                   auth_db_path):
    """Run the step-4 flow up to a Pending uni row and return
    (college_student_dict, application_id, uni_student_id)."""
    uni_progression.wire_subscribers(
        university_db_path=university_db_path,
        auth_db_path=auth_db_path,
    )
    student_svc = StudentService(college_db_path)
    ucas_svc = UCASService(college_db_path)
    student = student_svc.create_student(
        first_name="Holly", last_name="Hunter", date_of_birth="2008-09-09",
    )
    app = ucas_svc.create_application(student["id"])
    choice = ucas_svc.add_choice(
        app["id"], university_name="Tees University",
        course_title="BSc Math", ucas_code="G100",
    )
    ucas_svc.set_firm_insurance(app["id"], firm_id=choice["id"])
    bus.poll_and_dispatch("university", db_path=auth_db_path)

    # Drain the in-process subscribers between the two halves of the
    # flow so step-4 wiring doesn't fire during step-5 polls.
    bus.clear_subscribers_for_test()

    journey = ids.find_journey_by_student_id(
        "college", student["student_id"], db_path=auth_db_path)
    return student, app["id"], journey["university_student_id"]


# ── Producer-only: confirm_enrolment writes the outbox row ───────────────

class TestConfirmEnrolmentEmitsCompleted:
    def test_pending_to_active_publishes_completed_event(
        self, college_db_path, university_db_path, auth_db_path,
    ):
        student, _, uni_student_id = _stage_progression_to_pending(
            college_db_path, university_db_path, auth_db_path,
        )
        ok = uni_progression.confirm_enrolment(
            uni_student_id,
            university_db_path=university_db_path,
            auth_db_path=auth_db_path,
        )
        assert ok is True

        # Status flipped + enrollment_date stamped.
        conn = sqlite3.connect(university_db_path)
        try:
            row = conn.execute(
                "SELECT status, enrollment_date FROM students "
                " WHERE student_id = ?", (uni_student_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == "Active"
        assert row[1] is not None and row[1] != ""

        # Bus row landed targeted at college.
        conn = sqlite3.connect(auth_db_path)
        conn.row_factory = sqlite3.Row
        try:
            ev = conn.execute(
                "SELECT * FROM cross_system_event_outbox "
                " WHERE event_name = ? AND journey_id = ?",
                (bus.EVENT_STUDENT_PROGRESSION_COMPLETED,
                 student["journey_id"]),
            ).fetchone()
        finally:
            conn.close()
        assert ev is not None
        assert ev["target_system"] == "college"
        assert uni_student_id in ev["payload_json"]

    def test_idempotent_on_already_active(
        self, college_db_path, university_db_path, auth_db_path,
    ):
        _, _, uni_student_id = _stage_progression_to_pending(
            college_db_path, university_db_path, auth_db_path,
        )
        assert uni_progression.confirm_enrolment(
            uni_student_id, university_db_path=university_db_path,
            auth_db_path=auth_db_path,
        ) is True
        # Second call: already Active, no-op (no second event).
        assert uni_progression.confirm_enrolment(
            uni_student_id, university_db_path=university_db_path,
            auth_db_path=auth_db_path,
        ) is False
        conn = sqlite3.connect(auth_db_path)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM cross_system_event_outbox "
                " WHERE event_name = ?",
                (bus.EVENT_STUDENT_PROGRESSION_COMPLETED,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert n == 1

    def test_unknown_student_returns_false(
        self, university_db_path, auth_db_path,
    ):
        ok = uni_progression.confirm_enrolment(
            "9999999",
            university_db_path=university_db_path,
            auth_db_path=auth_db_path,
        )
        assert ok is False


# ── End-to-end: uni confirm → college flips to 'progressed' ──────────────

class TestEndToEndProgressionCompleted:
    def test_full_round_trip_offered_then_completed(
        self, college_db_path, university_db_path, auth_db_path,
    ):
        student, _, uni_student_id = _stage_progression_to_pending(
            college_db_path, university_db_path, auth_db_path,
        )

        # Wire the college consumer for completed events.
        college_consumer.wire_subscribers(
            college_db_path=college_db_path,
            auth_db_path=auth_db_path,
        )

        # Uni confirms enrolment → publishes completed.
        uni_progression.confirm_enrolment(
            uni_student_id,
            university_db_path=university_db_path,
            auth_db_path=auth_db_path,
        )
        # College polls and applies it.
        n = bus.poll_and_dispatch("college", db_path=auth_db_path)
        assert n == 1

        # College student row now status='progressed' + back-link set.
        conn = sqlite3.connect(college_db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT status, progressed_to_university_id "
                "  FROM students WHERE id = ?", (student["id"],),
            ).fetchone()
        finally:
            conn.close()
        assert row["status"] == "progressed"
        assert row["progressed_to_university_id"] == uni_student_id

        # Ack persisted with status='ok'.
        conn = sqlite3.connect(auth_db_path)
        try:
            ack = conn.execute(
                "SELECT status FROM cross_system_event_consumed "
                " WHERE consumer_system = 'college'",
            ).fetchone()
        finally:
            conn.close()
        assert ack and ack[0] == "ok"

    def test_redelivery_is_idempotent(
        self, college_db_path, university_db_path, auth_db_path,
    ):
        student, _, uni_student_id = _stage_progression_to_pending(
            college_db_path, university_db_path, auth_db_path,
        )
        college_consumer.wire_subscribers(
            college_db_path=college_db_path, auth_db_path=auth_db_path,
        )
        uni_progression.confirm_enrolment(
            uni_student_id, university_db_path=university_db_path,
            auth_db_path=auth_db_path,
        )
        bus.poll_and_dispatch("college", db_path=auth_db_path)

        # Re-publish the same logical event under a fresh event_id.
        bus.publish_cross_system(
            bus.EVENT_STUDENT_PROGRESSION_COMPLETED,
            source_system="university", source_module="redeliver-test",
            journey_id=student["journey_id"], target_system="college",
            university_student_id=uni_student_id, course="BSc Math",
        )
        bus.poll_and_dispatch("college", db_path=auth_db_path)

        # Still 'progressed', not somehow flipped or re-stamped.
        conn = sqlite3.connect(college_db_path)
        try:
            status = conn.execute(
                "SELECT status FROM students WHERE id = ?",
                (student["id"],),
            ).fetchone()[0]
        finally:
            conn.close()
        assert status == "progressed"

    def test_unknown_journey_drops_silently(
        self, college_db_path, auth_db_path,
    ):
        college_consumer.wire_subscribers(
            college_db_path=college_db_path, auth_db_path=auth_db_path,
        )
        bus.publish_cross_system(
            bus.EVENT_STUDENT_PROGRESSION_COMPLETED,
            source_system="university", source_module="t",
            journey_id="00000000-0000-0000-0000-000000000000",
            target_system="college",
            university_student_id="9999999", course="X",
        )
        # Handler runs without error and leaves the college DB alone.
        n = bus.poll_and_dispatch("college", db_path=auth_db_path)
        assert n == 1
        conn = sqlite3.connect(college_db_path)
        try:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM students "
                " WHERE status = 'progressed'").fetchone()[0]
        finally:
            conn.close()
        assert cnt == 0
