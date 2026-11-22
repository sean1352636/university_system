"""The secondary progression intake attaches a pupil to an open
application instead of creating a second record."""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import person
from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    applicant_details as det,
    college_intake as ci,
    conversion as conv,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)


@pytest.fixture
def intake(admdb, sign_in, monkeypatch):
    # The canonical person lives in the platform DB; the payload carries
    # the names these tests need.
    monkeypatch.setattr(person, "get", lambda journey_id: None)
    return sign_in("adm1", capabilities={access.ADMISSIONS,
                                         access.STUDENTS_MANAGE})


def _payload(**over):
    return {"first_name": "Zed", "last_name": "Testerson",
            "date_of_birth": "2010-03-04", "gender": "male",
            "parent_name": "Pat Testerson", "parent_phone": "07700900456",
            **over}


def _run_anonymous(monkeypatch, journey, payload):
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)
    return ci._admit(journey, payload)


def test_open_application_is_attached(intake, applicant_payload, monkeypatch,
                                      sign_in):
    a = adm.create_applicant(applicant_payload())
    out = _run_anonymous(monkeypatch, "J1", _payload(upn=""))
    assert out is None                      # no student created
    sign_in("adm1", capabilities={access.ADMISSIONS})
    got = adm.get_applicant(a.applicant_id)
    assert got.sex == "male"
    assert [c.name for c in det.list_contacts(a.applicant_id)] == ["Pat Testerson"]
    assert any("progression intake" in n.body
               for n in adm.list_notes(a.applicant_id))
    log = ci.list_intake_log()[0]
    assert (log.action, log.applicant_id, log.matched_on) == (
        "attached", a.applicant_id, "name + DOB")
    assert ci.pending_journey(a.applicant_id) == "J1"


def test_converted_applicant_uses_existing_student(intake, applicant_payload,
                                                   monkeypatch):
    a = adm.create_applicant(applicant_payload())
    adm.make_offer(a.applicant_id, offer_type="Unconditional", conditions=None)
    adm.accept_offer(a.applicant_id)
    _ap, sid = conv.convert_to_student(a.applicant_id, override_reason="test")
    assert _run_anonymous(monkeypatch, "J2", _payload()) == sid


def test_no_match_creates_a_student(intake, monkeypatch, sign_in):
    sid = _run_anonymous(monkeypatch, "J3", _payload(first_name="New"))
    assert sid
    sign_in("adm1")
    assert ci.list_intake_log()[0].action == "created"
