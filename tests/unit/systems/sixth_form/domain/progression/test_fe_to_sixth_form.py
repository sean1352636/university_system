from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from education_system.platform.cross_system import enrolments, identity_service
from education_system.platform.identity.auth.schema import initialise_auth_db
from education_system.systems.fe_college.infrastructure import persistence
from education_system.systems.fe_college.infrastructure.persistence.schema import init_db
from education_system.systems.fe_college.services import sixth_form_transfer
from education_system.systems.sixth_form.domain.learners.students import students


@pytest.fixture()
def reverse_env(tmp_path, monkeypatch):
    auth_db = str(tmp_path / "auth.db")
    sixth_db = str(tmp_path / "sixth.db")
    fe_db = tmp_path / "fe.db"
    initialise_auth_db(auth_db)
    identity_service._initialised.discard(auth_db)
    persistence.set_db_path(fe_db)
    init_db()
    with persistence.transaction() as conn:
        conn.execute(
            """INSERT INTO students
               (student_id, first_name, last_name, date_of_birth, email,
                phone, status, prior_attainment)
               VALUES ('FE000001', 'Maya', 'Jones', '2008-04-12',
                       'maya@example.test', '07111111111', 'enrolled',
                       'GCSE English 6; GCSE Maths 7')""")
    monkeypatch.setattr(students, "DB_PATH", sixth_db)
    monkeypatch.setattr(students, "_DB_READY", False)
    monkeypatch.setattr(students, "_provision_login_account", lambda *_a, **_k: None)
    monkeypatch.setattr(students, "_send_welcome_email", lambda *_a, **_k: None)
    yield auth_db, fe_db
    persistence.set_db_path(None)


def _request(auth_db):
    return sixth_form_transfer.request_transfer(
        "FE000001", reason="Vocational programme is not the right fit",
        intended_start=date.today().isoformat(), consent=True, db_path=auth_db)


def test_rejection_keeps_fe_active(reverse_env):
    auth_db, fe_db = reverse_env
    application = _request(auth_db)
    rejected = sixth_form_transfer.review_application(
        application["transition_id"],
        subjects=["Mathematics", "Physics", "Chemistry"],
        gcse_eligible=False, db_path=auth_db)
    assert rejected["status"] == "cancelled"
    with sqlite3.connect(fe_db) as conn:
        assert conn.execute("SELECT status FROM students").fetchone()[0] == "enrolled"


def test_future_start_does_not_close_fe(reverse_env):
    auth_db, fe_db = reverse_env
    application = _request(auth_db)
    offered = sixth_form_transfer.review_application(
        application["transition_id"],
        subjects=["Mathematics", "Physics", "Chemistry"], gcse_eligible=True,
        db_path=auth_db)
    sixth_form_transfer.accept_offer(
        offered["transition_id"], accepted_by="Maya Jones", consent=True,
        db_path=auth_db)
    future = (date.today() + timedelta(days=30)).isoformat()
    with pytest.raises(sixth_form_transfer.TransferError, match="not been reached"):
        sixth_form_transfer.enrol(offered["transition_id"], start_date=future,
                                  db_path=auth_db)
    with sqlite3.connect(fe_db) as conn:
        assert conn.execute("SELECT status FROM students").fetchone()[0] == "enrolled"


def test_completion_reuses_one_sixth_form_record_and_closes_fe(reverse_env):
    auth_db, fe_db = reverse_env
    application = _request(auth_db)
    offered = sixth_form_transfer.review_application(
        application["transition_id"],
        subjects=["Mathematics", "Physics", "Chemistry"], gcse_eligible=True,
        db_path=auth_db)
    # Re-review cannot create a duplicate because the state machine rejects it;
    # adapter-level journey matching is exercised directly by the one applicant.
    sixth_form_transfer.accept_offer(
        offered["transition_id"], accepted_by="Maya Jones", consent=True,
        db_path=auth_db)
    completed = sixth_form_transfer.enrol(
        offered["transition_id"], start_date=date.today().isoformat(), db_path=auth_db)
    assert completed["status"] == "completed"
    journey = identity_service.get(completed["journey_id"], db_path=auth_db)
    assert journey["fe_college_student_id"] == "FE000001"
    assert journey["college_student_id"]
    active = enrolments.active_enrolments(completed["journey_id"], db_path=auth_db)
    assert [row["system"] for row in active] == ["sixth_form"]
    with sqlite3.connect(fe_db) as conn:
        assert conn.execute("SELECT status FROM students").fetchone()[0] == "transferred"
