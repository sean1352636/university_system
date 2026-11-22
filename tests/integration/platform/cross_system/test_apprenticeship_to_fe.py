"""Apprenticeship → FE College: the apprenticeship side of the two-way link.

The diagram's FE College ↔ Apprenticeship arrow is dual enrolment in both
directions; FE → Apprenticeship is ``apprenticeship_applications``, and this
is the reverse, through ``fe_applications``. Stand-in adapters play both
systems; transitions, enrolments and handover filtering are the real
platform code on a tmp auth.db.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import (
    enrolment_schema,
    enrolments,
    fe_applications,
    handover,
    identity_service,
    route_support,
)
from education_system.platform.cross_system.adapters.base import (
    ApplicantResult,
    EnrolmentResult,
    ExportResult,
)
from education_system.platform.identity.auth import db as auth_db
from education_system.platform.identity.auth.schema import initialise_auth_db


class ApprenticeshipSource:
    def __init__(self):
        self.closed: list[tuple] = []

    def export_handover(self, student_id, consent=None, *, destination_system=None):
        return ExportResult(record={
            "learner_identity": {"first_name": "Jo", "last_name": "Hart",
                                 "date_of_birth": "2005-06-01"},
            "contact_details": {"email": "jo@example.test"},
            "standard_completed": {"title": "Engineering technician", "level": 3},
            "epa_result": {"grade": "Pass"},
            "employer_reference": "Acme Ltd",
        }, local_student_id=student_id)

    def close_enrolment(self, student_id, reason, **details):
        self.closed.append((student_id, reason))


class FEDestination:
    def __init__(self):
        self.applicants = []

    def create_applicant(self, request):
        self.applicants.append(request)
        return ApplicantResult(local_applicant_id="FE000042")

    def create_enrolment(self, journey_id, application_id=None, **details):
        return EnrolmentResult(local_student_id="FE000042", start_date="2026-09-07")


@pytest.fixture()
def auth(tmp_path, monkeypatch):
    path = tmp_path / "auth.db"
    monkeypatch.setattr(auth_db, "PLATFORM_AUTH_DB_FILE", path)
    initialise_auth_db(str(path))
    identity_service._initialised.clear()
    enrolment_schema.reset_schema_cache_for_test()
    yield str(path)
    identity_service._initialised.clear()
    enrolment_schema.reset_schema_cache_for_test()


@pytest.fixture()
def systems(monkeypatch):
    source, destination = ApprenticeshipSource(), FEDestination()
    table = {"apprenticeships": source, "fe_college": destination}
    monkeypatch.setattr(fe_applications, "_adapter", table.__getitem__)
    monkeypatch.setattr(route_support, "adapter_for", table.__getitem__)
    return source, destination


def test_the_boundary_has_a_handover_spec():
    assert ("apprenticeships", "fe_college") in handover.HANDOVER_SPECS
    assert "apprenticeships" in fe_applications.SOURCE_SYSTEMS


def test_unknown_source_is_refused():
    with pytest.raises(fe_applications.PathwayError):
        fe_applications.refer("university", "U1", pathway="x", reason="y")


def test_referral_enrols_at_fe_and_keeps_the_apprenticeship(auth, systems):
    source, destination = systems
    referral = fe_applications.refer(
        "apprenticeships", "APP1", pathway="HNC Engineering",
        reason="Off-the-job theory", consent=False, db_path=auth)
    assert referral["status"] == "offered"
    payload = destination.applicants[0].payload
    assert payload["referral_details"]["pathway"] == "HNC Engineering"
    assert "employer_reference" not in payload, "sensitive without consent"

    queue = fe_applications.incoming_referrals(source_system="apprenticeships", db_path=auth)
    assert [r["transition_id"] for r in queue] == [referral["transition_id"]]

    fe_applications.accept_referral(referral["transition_id"], accepted_by="FE admissions",
                                    consent=False, db_path=auth)
    done = fe_applications.enrol_referral(referral["transition_id"], db_path=auth)

    assert done["status"] == "completed"
    assert source.closed == []
    active = {r["system"] for r in enrolments.active_enrolments(done["journey_id"], db_path=auth)}
    assert {"apprenticeships", "fe_college"} <= active


def test_referring_twice_continues_the_open_referral(auth, systems):
    _, destination = systems
    first = fe_applications.refer("apprenticeships", "APP1", pathway="HNC",
                                  reason="Theory", db_path=auth)
    second = fe_applications.refer("apprenticeships", "APP1", pathway="HNC",
                                   reason="Theory", db_path=auth)
    assert second["transition_id"] == first["transition_id"]
    assert len(destination.applicants) == 1
