from __future__ import annotations

import sqlite3

from education_system.platform.cross_system import enrolments, identity_service
from education_system.platform.identity.auth.schema import initialise_auth_db
from education_system.systems.fe_college.infrastructure import persistence
from education_system.systems.sixth_form.domain.learners.students import students
from education_system.systems.sixth_form.domain.progression import post16_pathway


def _setup(tmp_path, monkeypatch):
    sixth_db = str(tmp_path / "sixth.db")
    auth_db = str(tmp_path / "auth.db")
    fe_db = tmp_path / "fe.db"
    monkeypatch.setattr(students, "DB_PATH", sixth_db)
    monkeypatch.setattr(students, "_DB_READY", False)
    monkeypatch.setattr(students, "_provision_login_account", lambda *_a, **_k: None)
    monkeypatch.setattr(students, "_send_welcome_email", lambda *_a, **_k: None)
    persistence.set_db_path(fe_db)
    initialise_auth_db(auth_db)
    identity_service._initialised.discard(auth_db)
    students.init_db()
    student = students.create_student({
        "first_name": "Ava", "last_name": "Patel",
        "date_of_birth": "2008-02-03", "phone": "07123456789",
        "subject_1": "Mathematics", "subject_2": "Physics",
        "subject_3": "Chemistry", "status": "Active",
    })
    return student, auth_db, fe_db


def test_concurrent_fe_pathway_keeps_sixth_form_open(tmp_path, monkeypatch):
    student, auth_db, fe_db = _setup(tmp_path, monkeypatch)
    try:
        referral = post16_pathway.refer(
            student.student_id, pathway="T Level Engineering",
            reason="Mixed academic and vocational programme",
            intended_start="2026-09-01", consent=True, db_path=auth_db)
        assert referral["status"] == "offered"

        with sqlite3.connect(fe_db) as conn:
            applicant = conn.execute(
                "SELECT journey_id, status, email FROM students").fetchone()
        assert applicant[1] == "applicant"
        assert applicant[2] == student.email

        approved = post16_pathway.accept_referral(
            referral["transition_id"], accepted_by="Ava Patel",
            consent=True, db_path=auth_db)
        assert approved["status"] == "handover_approved"

        completed = post16_pathway.enrol_referral(
            referral["transition_id"], concurrent=True,
            start_date="2026-09-01", db_path=auth_db)
        assert completed["status"] == "completed"
        assert students.get_student(student.student_id).status == "Active"
        active = enrolments.active_enrolments(completed["journey_id"], db_path=auth_db)
        assert {row["system"] for row in active} == {"sixth_form", "fe_college"}
    finally:
        persistence.set_db_path(None)


def test_transfer_closes_sixth_form_record(tmp_path, monkeypatch):
    student, auth_db, _fe_db = _setup(tmp_path, monkeypatch)
    try:
        referral = post16_pathway.refer(
            student.student_id, pathway="Access programme", reason="Full transfer",
            consent=False, db_path=auth_db)
        post16_pathway.accept_referral(
            referral["transition_id"], accepted_by="FE admissions",
            consent=False, db_path=auth_db)
        post16_pathway.enrol_referral(
            referral["transition_id"], concurrent=False, db_path=auth_db)
        assert students.get_student(student.student_id).status == "Left"
    finally:
        persistence.set_db_path(None)
