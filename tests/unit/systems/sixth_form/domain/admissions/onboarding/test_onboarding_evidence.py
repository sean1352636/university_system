"""Consent and ID onboarding items need the record, or written evidence
saying where the proof is (kept with who verified it)."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    identity_checks as idc,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as ob,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students,
)


@pytest.fixture
def items(admdb, sign_in):
    sign_in("enr1", capabilities={access.STUDENTS_MANAGE})
    sid = students.create_student({
        "first_name": "Ola", "last_name": "Board", "date_of_birth": "2009-01-02",
        "status": "Active", "personal_email": "ola@example.com"},
        allow_duplicate=True).student_id
    chk = ob.open_enrolment_checklist(sid)
    return sid, {i.task_name: i for i in ob.list_items(
        checklist_id=chk.checklist_id)}


def test_consent_item_needs_record_or_evidence(items):
    _sid, by_name = items
    item = by_name["Photo consent"]
    with pytest.raises(ob.ValidationError, match="consent"):
        ob.tick(item.item_id)
    done = ob.tick(item.item_id, evidence="Signed form in the enrolment file")
    assert done.is_done and done.evidence.startswith("Signed form")
    assert done.verified_by == "enr1"


def test_id_item_ticks_once_the_check_is_recorded(items):
    sid, by_name = items
    item = by_name["Photocopy of ID / passport"]
    with pytest.raises(ob.ValidationError, match="ID check"):
        ob.tick(item.item_id)
    idc.record_id_check(sid, document_type="Passport", document_number="12345")
    assert ob.get_item(item.item_id).is_done     # ticked by the check itself


def test_not_applicable_with_a_reason_is_allowed(items):
    _sid, by_name = items
    item = by_name["Parental consent (under 18)"]
    out = ob.update_item(item.item_id, {"status": "N/A",
                                        "na_reason": "Learner is 18"})
    assert out.status == "N/A"


def test_other_items_tick_freely(items):
    _sid, by_name = items
    assert ob.tick(by_name["Locker assigned"].item_id).is_done
