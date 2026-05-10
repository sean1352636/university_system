"""Step 6 — results-day grades flow via ``student.progression.accepted``.

Sits between step 4 (``offered`` — creates the uni Pending row) and
step 5 (``completed`` — flips the row to Active). Adds a third event:
when the college records final grades on the firm-choice application,
the bus carries them to the university and the matching Pending row
gets ``entry_qualifications`` + ``conditions_met`` populated.

Promotion to Active stays a separate manual ``confirm_enrolment``
call so staff can review failed conditions first.
"""

import json
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

from education_system.college_system.core.exceptions import UCASError
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
    ``database_utils.init_db`` produces, plus the columns added by the
    cross-system migrations (``journey_id``, ``entry_qualifications``,
    ``conditions_met``)."""
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
            journey_id TEXT,
            entry_qualifications TEXT,
            conditions_met INTEGER
        )"""
    )
    conn.commit()
    conn.close()
    return p


def _stage_to_pending(college_db_path, university_db_path, auth_db_path):
    """Run step-4's offered flow so a Pending uni row exists. Returns
    (college_student, application_id, uni_student_id)."""
    uni_progression.wire_subscribers(
        university_db_path=university_db_path,
        auth_db_path=auth_db_path,
    )
    student_svc = StudentService(college_db_path)
    ucas_svc = UCASService(college_db_path)
    student = student_svc.create_student(
        first_name="Iris", last_name="Ito", date_of_birth="2008-10-10",
    )
    app = ucas_svc.create_application(student["id"])
    choice = ucas_svc.add_choice(
        app["id"], university_name="Tees University",
        course_title="BSc Maths", ucas_code="G100",
    )
    ucas_svc.set_firm_insurance(app["id"], firm_id=choice["id"])
    bus.poll_and_dispatch("university", db_path=auth_db_path)
    journey = ids.find_journey_by_student_id(
        "college", student["student_id"], db_path=auth_db_path)
    return student, app["id"], journey["university_student_id"]


# ── Producer-only ────────────────────────────────────────────────────────

class TestRecordResultsEmitsAccepted:
    def test_records_grades_locally_and_publishes_event(
        self, college_db_path, university_db_path, auth_db_path,
    ):
        student, app_id, _ = _stage_to_pending(
            college_db_path, university_db_path, auth_db_path,
        )
        ucas_svc = UCASService(college_db_path)
        grades = {"A-Level Maths": "A*", "A-Level Physics": "A",
                  "EPQ": "B"}
        updated = ucas_svc.record_results(
            app_id, grades=grades, conditions_met=True)

        # College row now has the grades + flag + timestamp.
        assert json.loads(updated["final_grades_json"]) == grades
        assert updated["conditions_met"] == 1
        assert updated["results_recorded_at"] is not None

        # Bus row landed targeted at university.
        conn = sqlite3.connect(auth_db_path)
        conn.row_factory = sqlite3.Row
        try:
            ev = conn.execute(
                "SELECT * FROM cross_system_event_outbox "
                " WHERE event_name = ? AND journey_id = ?",
                (bus.EVENT_STUDENT_PROGRESSION_ACCEPTED,
                 student["journey_id"]),
            ).fetchone()
        finally:
            conn.close()
        assert ev is not None
        assert ev["target_system"] == "university"
        payload = json.loads(ev["payload_json"])
        assert payload["final_grades"] == grades
        assert payload["conditions_met"] is True
        assert payload["application_id"] == app_id

    def test_conditions_not_met_still_publishes(
        self, college_db_path, university_db_path, auth_db_path,
    ):
        _, app_id, _ = _stage_to_pending(
            college_db_path, university_db_path, auth_db_path,
        )
        ucas_svc = UCASService(college_db_path)
        ucas_svc.record_results(
            app_id, grades={"A-Level Maths": "C"}, conditions_met=False)
        conn = sqlite3.connect(auth_db_path)
        conn.row_factory = sqlite3.Row
        try:
            ev = conn.execute(
                "SELECT payload_json FROM cross_system_event_outbox "
                " WHERE event_name = ?",
                (bus.EVENT_STUDENT_PROGRESSION_ACCEPTED,),
            ).fetchone()
        finally:
            conn.close()
        payload = json.loads(ev["payload_json"])
        assert payload["conditions_met"] is False

    def test_unknown_application_raises(self, college_db_path):
        ucas_svc = UCASService(college_db_path)
        with pytest.raises(UCASError):
            ucas_svc.record_results(
                999_999, grades={"X": "A"}, conditions_met=True)

    def test_empty_grades_rejected(
        self, college_db_path, university_db_path, auth_db_path,
    ):
        _, app_id, _ = _stage_to_pending(
            college_db_path, university_db_path, auth_db_path,
        )
        ucas_svc = UCASService(college_db_path)
        with pytest.raises(UCASError):
            ucas_svc.record_results(app_id, grades={}, conditions_met=True)


# ── End-to-end producer → poll → consumer ────────────────────────────────

class TestEndToEndAcceptedFlow:
    def test_uni_pending_row_gets_grades_and_flag(
        self, college_db_path, university_db_path, auth_db_path,
    ):
        student, app_id, uni_student_id = _stage_to_pending(
            college_db_path, university_db_path, auth_db_path,
        )
        ucas_svc = UCASService(college_db_path)
        grades = {"A-Level Maths": "A", "A-Level Computing": "A*"}
        ucas_svc.record_results(
            app_id, grades=grades, conditions_met=True)

        # University poller picks the accepted event up.
        n = bus.poll_and_dispatch("university", db_path=auth_db_path)
        assert n == 1

        conn = sqlite3.connect(university_db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT status, entry_qualifications, conditions_met "
                "  FROM students WHERE student_id = ?",
                (uni_student_id,),
            ).fetchone()
        finally:
            conn.close()
        # Still Pending — grades alone don't enrol.
        assert row["status"] == "Pending"
        assert json.loads(row["entry_qualifications"]) == grades
        assert row["conditions_met"] == 1

    def test_failed_conditions_recorded_but_not_promoted(
        self, college_db_path, university_db_path, auth_db_path,
    ):
        _, app_id, uni_student_id = _stage_to_pending(
            college_db_path, university_db_path, auth_db_path,
        )
        ucas_svc = UCASService(college_db_path)
        ucas_svc.record_results(
            app_id, grades={"A-Level Maths": "D"}, conditions_met=False)
        bus.poll_and_dispatch("university", db_path=auth_db_path)

        conn = sqlite3.connect(university_db_path)
        try:
            row = conn.execute(
                "SELECT status, conditions_met FROM students "
                " WHERE student_id = ?", (uni_student_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == "Pending"
        assert row[1] == 0

    def test_accepted_before_offered_drops(
        self, college_db_path, university_db_path, auth_db_path,
    ):
        """If the accepted event somehow arrives without an existing
        uni record, the handler drops cleanly. This covers the race
        where two pollers run out of order."""
        uni_progression.wire_subscribers(
            university_db_path=university_db_path,
            auth_db_path=auth_db_path,
        )
        # Make a journey with a college link but no uni link.
        jid = ids.get_or_create_journey(
            first_name="Jay", last_name="Jay",
            date_of_birth="2008-11-11", current_system="college",
            db_path=auth_db_path,
        )
        ids.attach_system_record(
            jid, "college", pk=1, student_id="SFC9999",
            db_path=auth_db_path,
        )
        bus.publish_cross_system(
            bus.EVENT_STUDENT_PROGRESSION_ACCEPTED,
            source_system="college", source_module="t",
            journey_id=jid, target_system="university",
            target_university="Tees", course_title="BSc",
            application_id=42, college_student_id="SFC9999",
            final_grades={"A": "A*"}, conditions_met=True,
        )
        bus.poll_and_dispatch("university", db_path=auth_db_path)
        # No row created; no row updated.
        conn = sqlite3.connect(university_db_path)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM students").fetchone()[0]
        finally:
            conn.close()
        assert n == 0

    def test_full_offered_accepted_completed_chain(
        self, college_db_path, university_db_path, auth_db_path,
    ):
        """Complete cycle: offered → accepted → confirm_enrolment →
        completed. Verifies all three events fire and the uni row ends
        up Active with grades populated."""
        from education_system.college_system.modules.domain.students.services import (
            cross_system_progression_consumer as college_consumer,
        )

        student, app_id, uni_student_id = _stage_to_pending(
            college_db_path, university_db_path, auth_db_path,
        )
        college_consumer.wire_subscribers(
            college_db_path=college_db_path, auth_db_path=auth_db_path,
        )

        # 2/3: results day.
        UCASService(college_db_path).record_results(
            app_id,
            grades={"A-Level Maths": "A", "A-Level Physics": "A*"},
            conditions_met=True,
        )
        bus.poll_and_dispatch("university", db_path=auth_db_path)

        # 3/3: enrolment confirmation.
        uni_progression.confirm_enrolment(
            uni_student_id,
            university_db_path=university_db_path,
            auth_db_path=auth_db_path,
        )
        bus.poll_and_dispatch("college", db_path=auth_db_path)

        # End state: uni Active with grades; college progressed.
        conn = sqlite3.connect(university_db_path)
        conn.row_factory = sqlite3.Row
        try:
            uni_row = conn.execute(
                "SELECT status, entry_qualifications, conditions_met "
                "  FROM students WHERE student_id = ?",
                (uni_student_id,),
            ).fetchone()
        finally:
            conn.close()
        assert uni_row["status"] == "Active"
        assert json.loads(uni_row["entry_qualifications"])["A-Level Maths"] == "A"

        conn = sqlite3.connect(college_db_path)
        conn.row_factory = sqlite3.Row
        try:
            col_row = conn.execute(
                "SELECT status, progressed_to_university_id "
                "  FROM students WHERE id = ?", (student["id"],),
            ).fetchone()
        finally:
            conn.close()
        assert col_row["status"] == "progressed"
        assert col_row["progressed_to_university_id"] == uni_student_id

        # All three events landed in the outbox.
        conn = sqlite3.connect(auth_db_path)
        try:
            names = {r[0] for r in conn.execute(
                "SELECT event_name FROM cross_system_event_outbox "
                " WHERE journey_id = ?", (student["journey_id"],),
            ).fetchall()}
        finally:
            conn.close()
        assert {bus.EVENT_STUDENT_PROGRESSION_OFFERED,
                bus.EVENT_STUDENT_PROGRESSION_ACCEPTED,
                bus.EVENT_STUDENT_PROGRESSION_COMPLETED}.issubset(names)
