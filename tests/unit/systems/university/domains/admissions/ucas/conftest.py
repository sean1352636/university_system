"""Isolation for the university-side UCAS tests.

The module under test straddles two databases and, left alone, writes to
both of the real ones plus the platform audit log and the outgoing mail
queue. Every one of those is redirected here.

Two substrates, redirected two different ways, because the code reaches
them two different ways:

* The **sixth form** modules each hold a module-level ``DB_PATH`` and open
  it themselves, so the path is what gets patched.
* The **university** modules call ``get_connection()`` imported from
  ``infrastructure.database.db``, so the *function* is what gets patched —
  and it has to be patched on each importing module, since each bound the
  name at import time.

Both are pointed at temp files, so a test can write freely without
touching ``sixthform.db`` or ``student_records.db``.
"""

from __future__ import annotations

import importlib
import sqlite3
from types import SimpleNamespace

import pytest

#: The name the fixture makes "us" — deliberately not the real default, so
#: a test that accidentally resolves the live institution name fails
#: rather than passing for the wrong reason.
HOME_UNIVERSITY = "Test University"

#: Sixth-form data modules whose DB_PATH must point at the temp file.
_SF_MODULES = (
    "education_system.systems.sixth_form.domain.learners.students.students",
    "education_system.systems.sixth_form.domain.progression.university.ucas",
)

#: University modules that bound ``get_connection`` at import time.
_UNI_MODULES = (
    "education_system.systems.university.domains.admissions.domain.ucas.ucas_links",
    "education_system.systems.university.domains.admissions.domain.ucas.offer_terms",
    "education_system.systems.university.domains.admissions.domain.ucas.decision_log",
    "education_system.systems.university.domains.admissions.domain.ucas.pipeline_link",
    "education_system.systems.university.domains.admissions.domain.ucas.clearing_link",
    "education_system.systems.university.domains.admissions.domain.ucas.results_day",
)

#: Tables the UCAS module reads on the university side but does not own.
#: Created directly rather than by importing the CRM, whose initialiser
#: pulls in a GUI-adjacent service module.
_UNI_INPUT_DDL = """
CREATE TABLE IF NOT EXISTS admission_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER,
    application_type TEXT,
    program_applied TEXT,
    academic_year TEXT,
    semester TEXT,
    status TEXT DEFAULT 'submitted',
    external_reference TEXT,
    journey_id TEXT
);
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name TEXT
);
CREATE TABLE IF NOT EXISTS clearing_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    ucas_id TEXT,
    tariff_points INTEGER DEFAULT 0,
    qualifications TEXT,
    preferred_course TEXT,
    status TEXT DEFAULT 'pending',
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
    processed_by TEXT,
    processed_at TEXT,
    notes TEXT
);
"""


@pytest.fixture
def ucas_env(tmp_path, monkeypatch):
    """A sixth form with one applicant, and a university that can decide.

    Returns a namespace carrying the imported modules, the seeded ids, and
    ``audit`` — the list every audited decision is appended to, so a test
    can assert an offer was recorded without a real audit database.
    """
    sf_db = str(tmp_path / "sixthform.db")
    uni_db = str(tmp_path / "student_records.db")

    # ── Sixth form ───────────────────────────────────────────────────
    sf = {}
    for dotted in _SF_MODULES:
        module = importlib.import_module(dotted)
        monkeypatch.setattr(module, "DB_PATH", sf_db, raising=False)
        if hasattr(module, "_DB_READY"):
            monkeypatch.setattr(module, "_DB_READY", False, raising=False)
        sf[dotted.rsplit(".", 1)[-1]] = module
    students, sf_ucas = sf["students"], sf["ucas"]
    students.init_db()
    sf_ucas.init_db()

    # ── University ───────────────────────────────────────────────────
    def _uni_connection():
        conn = sqlite3.connect(uni_db)
        conn.row_factory = sqlite3.Row
        return conn

    uni = {}
    for dotted in _UNI_MODULES:
        module = importlib.import_module(dotted)
        monkeypatch.setattr(module, "get_connection", _uni_connection,
                            raising=False)
        if hasattr(module, "_DB_READY"):
            monkeypatch.setattr(module, "_DB_READY", False, raising=False)
        uni[dotted.rsplit(".", 1)[-1]] = module

    seed = sqlite3.connect(uni_db)
    seed.executescript(_UNI_INPUT_DDL)
    seed.commit()
    seed.close()

    from education_system.systems.university.domains.admissions.domain.ucas import (
        results_day,
        ucas as uni_ucas,
    )
    from education_system.systems.sixth_form.domain.progression import (
        university_handover,
    )
    from education_system.systems.university.application.programmes import prospectus

    # Who "we" are, on both sides of the boundary. The sixth form's guard
    # and the university's applicant query have to agree or every test
    # would be exercising the wrong branch.
    monkeypatch.setattr(prospectus, "institution_name",
                        lambda: HOME_UNIVERSITY)
    monkeypatch.setattr(university_handover, "home_university_names",
                        lambda: {HOME_UNIVERSITY.lower()})

    # No real mail, no real audit database.
    monkeypatch.setattr(uni_ucas, "_send_decision_email",
                        lambda *a, **k: None)
    # Confirming a place (results day) e-mails the outcome and closes the
    # learner's logins in the shared auth database — neither is under test.
    monkeypatch.setattr(uni_ucas, "_send_outcome_email",
                        lambda *a, **k: None, raising=False)
    monkeypatch.setattr(students, "disable_leaver_login",
                        lambda *a, **k: None, raising=False)
    monkeypatch.setattr(students, "disable_orphaned_parent_logins",
                        lambda *a, **k: None, raising=False)
    audit: list = []
    real_audit = uni["decision_log"]._audit
    monkeypatch.setattr(uni["decision_log"], "_audit", audit.append)

    # ── Platform auth DB (the cross-system bus) ──────────────────────
    # A decision is now *published* (``ucas.decision.recorded``) and an
    # admission publishes ``university.student.enrolled``; both land in the
    # outbox in the shared auth database. Point the bus — and the journey
    # lookups beside it — at a temp file instead of the live one.
    from education_system.platform.cross_system import identity_service
    from education_system.platform.identity.auth import db as auth_db
    from education_system.platform.identity.auth import schema as auth_schema
    from education_system.platform.integrations.external import (
        cross_system_bus,
    )
    auth_path = str(tmp_path / "auth.db")
    real_auth_connect = auth_db.connect

    def _auth_connect(db_path=None, *args, **kwargs):
        return real_auth_connect(db_path or auth_path, *args, **kwargs)

    monkeypatch.setattr(auth_db, "connect", _auth_connect)
    monkeypatch.setattr(cross_system_bus, "connect", _auth_connect)
    monkeypatch.setattr(identity_service, "connect", _auth_connect)
    monkeypatch.setattr(auth_schema, "connect", _auth_connect, raising=False)
    auth_schema.initialise_auth_db(auth_path)

    # ── One applicant, two choices, ours in slot 1 ───────────────────
    #
    # Inserted directly rather than through ``students.create_student``,
    # which allocates its own student id, reaches past the patched path
    # into the live subjects/staff/messages tables, and provisions a real
    # login account in the shared auth database. None of that is under
    # test here and all of it would be written for real.
    seed = sqlite3.connect(sf_db)
    seed.execute(
        """INSERT INTO students (student_id, first_name, last_name, email,
                                 date_of_birth, subject_1, subject_2,
                                 subject_3, status)
           VALUES ('SF001', 'Robin', 'Fielding',
                   'robin.fielding@example.test', '2007-03-14',
                   'Mathematics', 'Physics', 'Chemistry', 'Active')""")
    seed.commit()
    seed.close()
    application = sf_ucas.create_application({
        "student_id": "SF001",
        "cycle_year": 2027,
        "ucas_id": "1234567890",
        "status": "Submitted",
        "submitted_at": "2026-10-15",
        "personal_statement": "I would like to study engineering.",
    })
    ours = sf_ucas.create_choice(application.application_id, {
        "choice_order": 1,
        "university": HOME_UNIVERSITY,
        "course_code": "ENG1",
        "course_name": "Mechanical Engineering",
        "entry_year": 2027,
    })
    theirs = sf_ucas.create_choice(application.application_id, {
        "choice_order": 2,
        "university": "Elsewhere University",
        "course_code": "ENG2",
        "course_name": "Mechanical Engineering",
        "entry_year": 2027,
        # An external university's decision is the school's to record,
        # so this one is allowed to arrive already decided.
        "decision_status": "Conditional Offer",
        "offer_terms": "BBC",
    })

    return SimpleNamespace(
        sf_db=sf_db,
        uni_db=uni_db,
        home=HOME_UNIVERSITY,
        students=students,
        sf_ucas=sf_ucas,
        uni_ucas=uni_ucas,
        results_day=results_day,
        links=uni["ucas_links"],
        offer_terms=uni["offer_terms"],
        decision_log=uni["decision_log"],
        pipeline_link=uni["pipeline_link"],
        clearing_link=uni["clearing_link"],
        audit=audit,
        # The unstubbed sink, for the one test that exercises the real
        # audit write rather than recording that it was attempted.
        real_audit=real_audit,
        student_id="SF001",
        application_id=application.application_id,
        our_choice_id=ours.choice_id,
        their_choice_id=theirs.choice_id,
        uni_connection=_uni_connection,
    )
