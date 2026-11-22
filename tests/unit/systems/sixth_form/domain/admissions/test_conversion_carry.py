"""Conversion carries contacts, ID check, SEND / medical / safeguarding
information and welfare flags to their own records, one step each."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    applicant_details as det,
    conversion as conv,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)

ALL = {access.ADMISSIONS, access.STUDENTS_MANAGE, access.SEND,
       access.MEDICAL, access.SAFEGUARDING}


@pytest.fixture
def staff(admdb, sign_in):
    return sign_in("adm1", capabilities=ALL)


def _ready(applicant_payload):
    a = adm.create_applicant(applicant_payload())
    aid = a.applicant_id
    det.add_contact(aid, {"name": "Pat Testerson", "relationship": "Mother",
                          "phone": "07700900456", "email": "pat@example.com",
                          "is_emergency": True,
                          "parental_responsibility": True})
    det.add_contact(aid, {"name": "Grandad", "relationship": "Grandparent",
                          "phone": "07700900457"})
    det.update_profile(aid, sex="female", lldd=True, young_carer=True,
                       looked_after=True, bursary_interest=True)
    det.set_sensitive(aid, "send", "Dyslexia")
    det.set_sensitive(aid, "medical", "Asthma")
    det.set_sensitive(aid, "safeguarding", "Known to CSC",
                      received_from="Feeder High")
    det.record_identity_check(aid, document_type="Passport",
                              document_number="123456789",
                              right_to_study="Yes - UK or Irish citizen")
    adm.make_offer(aid, offer_type="Unconditional", conditions=None)
    adm.accept_offer(aid)
    return aid


def _steps(aid):
    return {(s["step"], s["result"]) for s in conv.get_conversion(aid).steps}


def test_everything_lands_in_its_own_record(staff, applicant_payload):
    aid = _ready(applicant_payload)
    _a, sid = conv.convert_to_student(aid)
    rec = conv.get_conversion(aid)
    assert rec.converted_by == "adm1"
    steps = _steps(aid)
    for name in ("contact", "SEND register", "medical", "safeguarding",
                 "looked after", "young carer", "bursary", "ID check"):
        assert (name, "ok") in steps, name
    # The one-word contact cannot be split into first/last name: kept.
    assert ("contact", "failed") in steps
    assert rec.carried["contacts"] == ["Grandad"]
    # Sensitive text never goes into the conversion record.
    assert "Dyslexia" not in str(rec.carried) + str(rec.steps)

    from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
        parent_contacts,
    )
    pcs = parent_contacts.contacts_for_student(sid)
    assert [(c.first_name, c.last_name, c.relationship) for c in pcs] == [
        ("Pat", "Testerson", "Mother")]
    from education_system.systems.sixth_form.domain.pastoral.send import send
    entry = send.entries_for_student(sid)[0]
    assert "Dyslexia" in entry.notes
    from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
        medical_records,
    )
    assert "Asthma" in medical_records.get_profile(sid).notes
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks,
    )
    chk = identity_checks.get_check(sid)
    assert (chk.id_document_type, chk.id_number_last4, chk.right_to_study) == (
        "Passport", "6789", "Yes - UK or Irish citizen")
    assert chk.source == f"admissions applicant {aid}"
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries,
    )
    apps = bursaries.list_applications(student_id=sid)
    assert [(x.status, x.bursary_type, x.eligibility_basis) for x in apps] == [
        ("Draft", "Vulnerable Bursary", "Looked-After Child")]
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        onboarding,
    )
    tasks = {i.task_name for c in onboarding.list_checklists(student_id=sid)
             for i in onboarding.list_items(checklist_id=c.checklist_id)}
    assert any(t.startswith("Designated teacher") for t in tasks)
    assert any(t.startswith("Young carer") for t in tasks)


def test_start_date_must_fall_in_the_year(staff, applicant_payload):
    aid = _ready(applicant_payload)
    with pytest.raises(adm.ValidationError, match="outside"):
        conv.convert_to_student(aid, academic_year="2025/26",
                                start_date="2027-01-05")


def test_mid_year_joiner_start_date(staff, applicant_payload):
    aid = _ready(applicant_payload)
    year = conv.default_academic_year()
    start = f"{int(year[:4]) + 1}-01-06"
    _a, sid = conv.convert_to_student(aid, academic_year=year,
                                      start_date=start, tutor_group="12B")
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments,
    )
    e = enrolments.current_enrolment(sid)
    assert (e.academic_year, e.start_date, e.tutor_group) == (year, start, "12B")
