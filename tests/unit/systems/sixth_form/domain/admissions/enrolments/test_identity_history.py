"""Enrolment ID checks keep their history and carry the right to study."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    identity_checks as idc,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students,
)


@pytest.fixture
def sid(admdb, sign_in):
    sign_in("enr1", capabilities={access.STUDENTS_MANAGE})
    return students.create_student({
        "first_name": "Ida", "last_name": "Check", "date_of_birth": "2009-01-02",
        "status": "Active", "personal_email": "ida@example.com"},
        allow_duplicate=True).student_id


def test_second_check_keeps_the_first_in_history(sid):
    idc.record_id_check(sid, document_type="Passport", document_number="AB1234567",
                        checked_on="2025-09-01")
    out = idc.record_id_check(sid, document_type="Driving licence",
                              document_number="XY-99 88", checked_on="2025-09-02",
                              right_to_study="Yes - UK or Irish citizen")
    assert (out.id_document_type, out.id_number_last4) == ("Driving licence", "9988")
    assert out.right_to_study == "Yes - UK or Irish citizen"
    hist = idc.id_history(sid)
    assert [h["id_document_type"] for h in hist] == ["Driving licence", "Passport"]
    assert all(h["recorded_by"] == "enr1" for h in hist)


def test_visa_needs_expiry(sid):
    with pytest.raises(idc.ValidationError, match="expiry"):
        idc.record_id_check(sid, document_type="Passport", document_number="1234",
                            right_to_study="Yes - visa (check expiry)")
    out = idc.record_id_check(sid, document_type="Passport", document_number="1234",
                              right_to_study="Yes - visa (check expiry)",
                              visa_type="Student", visa_expiry="2027-08-31")
    assert out.visa_expiry == "2027-08-31"


def test_writes_are_gated(sid, sign_in):
    sign_in("t1", capabilities={access.STUDENTS_VIEW})
    with pytest.raises(access.AccessDenied):
        idc.record_id_check(sid, document_type="Passport", document_number="1234")
    assert idc.get_check(sid) is None      # reads stay open
