"""University → Apprenticeship: a degree apprenticeship through the engine.

This is a dual registration, not a transfer. The learner joins the
apprenticeship and stays a university student, so the transition
completes with the university enrolment still open, and the university
adapter's ``close_enrolment`` is never asked to act.

Stand-in adapters play both systems. The university package writes at
import time, so it is never imported here. Transitions, enrolments and
the handover filtering are the real platform code, on a tmp auth.db.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import (
    apprenticeship_applications as apps,
)
from education_system.platform.cross_system import enrolment_schema, enrolments, identity_service
from education_system.platform.cross_system.adapters.base import (
    ApplicantResult,
    EnrolmentResult,
    ExportResult,
)
from education_system.platform.identity.auth import db as auth_db
from education_system.platform.identity.auth.schema import initialise_auth_db


class UniversitySource:
    """What the university exports for a student starting a degree
    apprenticeship: the UNIVERSITY_TO_APPRENTICESHIPS keys."""

    def __init__(self, *, registered: bool = True):
        self.registered = registered
        self.closed: list[tuple] = []

    def export_handover(self, student_id, consent=None, *, destination_system=None):
        record = {
            "learner_identity": {"first_name": "Sam", "last_name": "Reid",
                                 "date_of_birth": "2004-02-11"},
            "contact_details": {"email": "sam@example.test", "phone": "07000 111222"},
            "achieved_qualifications": "A levels: Maths A, Physics B",
            "module_credits": {"credits_earned": 120},
        }
        if self.registered:
            record["programme_registration"] = {
                "university_student_id": student_id,
                "course": "BSc Software Engineering"}
        return ExportResult(record=record, local_student_id=student_id)

    def close_enrolment(self, student_id, reason, **details):
        self.closed.append((student_id, reason))


class ApprenticeshipsDestination:
    def __init__(self):
        self.applicants = []
        self.starts = []

    def create_applicant(self, request):
        self.applicants.append(request)
        return ApplicantResult(local_applicant_id="A-7")

    def create_enrolment(self, journey_id, application_id=None, **details):
        self.starts.append((journey_id, details))
        return EnrolmentResult(local_student_id="A-7", start_date="2026-09-07")


FIELDS = {
    "intended_programme": {"title": "Digital technology solutions",
                           "level": 6, "reference": "ST0119"},
    "eligibility_evidence": "Right to work checked",
    "prior_attainment": "GCSE English 6, Maths 7",
    "consent": True,
}


@pytest.fixture()
def auth(tmp_path, monkeypatch):
    path = tmp_path / "auth.db"
    # Belt and braces: routes are given db_path, and the default is
    # redirected too, so nothing can fall through to the live auth.db.
    monkeypatch.setattr(auth_db, "PLATFORM_AUTH_DB_FILE", path)
    initialise_auth_db(str(path))
    identity_service._initialised.clear()
    enrolment_schema.reset_schema_cache_for_test()
    yield str(path)
    identity_service._initialised.clear()
    enrolment_schema.reset_schema_cache_for_test()


@pytest.fixture()
def adapters(monkeypatch):
    source, destination = UniversitySource(), ApprenticeshipsDestination()
    monkeypatch.setattr(apps, "_adapters", lambda _system: (source, destination))
    return source, destination


def test_the_university_is_a_concurrent_source():
    assert "university" in apps.SOURCE_SYSTEMS
    assert "university" in apps.CONCURRENT_BY_DEFAULT


def test_degree_apprenticeship_keeps_the_university_enrolment_open(auth, adapters):
    source, destination = adapters

    submitted = apps.submit("university", "U100", reason="Degree apprenticeship",
                            db_path=auth, **FIELDS)
    assert submitted["status"] == "offered"
    request = destination.applicants[0]
    assert request.source_system == "university"
    assert request.payload["programme_registration"]["university_student_id"] == "U100"

    apps.accept_offer(submitted["transition_id"], accepted_by="Sam Reid",
                      db_path=auth, **FIELDS)
    done = apps.start_programme(submitted["transition_id"], programme_id=3,
                                employer_id=9, start_date="2026-09-07", db_path=auth)

    assert done["status"] == "completed"
    assert source.closed == [], "the university record must not be closed"
    active = {row["system"] for row in
              enrolments.active_enrolments(done["journey_id"], db_path=auth)}
    assert {"university", "apprenticeships"} <= active


def test_the_programme_registration_is_required(adapters):
    source, _ = adapters
    source.registered = False

    preview = apps.preview("university", "U100", **FIELDS)

    assert not preview.ready
    assert "programme_registration" in preview.missing_required


def test_submitting_twice_continues_the_open_application(auth, adapters):
    _, destination = adapters

    first = apps.submit("university", "U100", reason="Degree apprenticeship",
                        db_path=auth, **FIELDS)
    second = apps.submit("university", "U100", reason="Degree apprenticeship",
                         db_path=auth, **FIELDS)

    assert second["transition_id"] == first["transition_id"]
    assert len(destination.applicants) == 1
