"""Results day refuses enrolled, closed and archived applicants with a
clear message, and lists only live conditional offers."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    gcse_results_day as rd,
    record_safety as rs,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)


@pytest.fixture
def staff(admdb, sign_in):
    return sign_in("adm1", capabilities={access.ADMISSIONS,
                                         access.STUDENTS_MANAGE})


def _offer(applicant_payload, **over):
    a = adm.create_applicant(applicant_payload(**over))
    adm.make_offer(a.applicant_id, offer_type="Conditional",
                   conditions="5 in Maths")
    return a


def test_closed_application_message(staff, applicant_payload):
    a = _offer(applicant_payload)
    adm.reject(a.applicant_id)
    with pytest.raises(adm.ValidationError, match="closed"):
        rd.decline(a.applicant_id)
    with pytest.raises(adm.ValidationError, match="closed"):
        rd.offer_alternative(a.applicant_id, choices=["Biology"])


def test_enrolled_applicant_message(staff, applicant_payload):
    from education_system.systems.sixth_form.domain.admissions import conversion
    a = _offer(applicant_payload)
    adm.accept_offer(a.applicant_id)
    conversion.convert_to_student(a.applicant_id, override_reason="test")
    with pytest.raises(adm.ValidationError, match="already enrolled"):
        rd.decline(a.applicant_id)
    with pytest.raises(adm.ValidationError, match="already enrolled"):
        rd.confirm(a.applicant_id)
    assert a.applicant_id not in {x.applicant_id
                                  for x in rd.conditional_applicants()}


def test_conditional_applicants_exclude_archived(staff, applicant_payload):
    keep = _offer(applicant_payload)
    gone = _offer(applicant_payload, first_name="Arc", email="arc@example.com")
    rs.archive_applicant(gone.applicant_id, reason="duplicate entry")
    ids = {x.applicant_id for x in rd.conditional_applicants()}
    assert keep.applicant_id in ids and gone.applicant_id not in ids
