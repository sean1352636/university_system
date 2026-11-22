"""Admissions foundations: permissions, status rules, duplicates,
archive/delete/merge, two-person erasure, sensitive data and the
conversion gates."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    applicant_details as det,
    conversion as conv,
    record_safety as rs,
    status_rules,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)


@pytest.fixture
def staff(admdb, sign_in):
    return sign_in("adm1", capabilities={access.ADMISSIONS,
                                         access.STUDENTS_MANAGE})


# ── Permissions ────────────────────────────────────────────────────

def test_anonymous_cannot_read_applicants(admdb, monkeypatch):
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)
    with pytest.raises(access.AccessDenied):
        adm.list_applicants()


def test_teacher_cannot_open_an_applicant(admdb, sign_in, applicant_payload):
    sign_in("adm1")
    a = adm.create_applicant(applicant_payload())
    sign_in("t1", capabilities={access.STUDENTS_VIEW, access.TEACHING})
    with pytest.raises(access.AccessDenied):
        adm.get_applicant(a.applicant_id)


def test_system_actor_is_scoped_to_the_block(admdb, monkeypatch):
    from education_system.systems.sixth_form.domain.admissions import _guard
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)
    with _guard.system_actor("job"):
        assert adm.list_applicants() == []
    with pytest.raises(access.AccessDenied):
        adm.list_applicants()


def test_events_record_who(staff, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    assert {e.actor for e in adm.list_events(a.applicant_id)} == {"adm1"}


# ── Status rules ───────────────────────────────────────────────────

def test_cannot_skip_to_offer_accepted(staff, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    with pytest.raises(adm.ValidationError, match="Allowed next"):
        adm.accept_offer(a.applicant_id)


def test_rejected_needs_reopen_with_reason(staff, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    adm.reject(a.applicant_id)
    with pytest.raises(adm.ValidationError, match="closed"):
        adm.make_offer(a.applicant_id)
    with pytest.raises(adm.ValidationError):
        adm.reopen_application(a.applicant_id, reason="")
    out = adm.reopen_application(a.applicant_id, reason="appeal upheld")
    assert out.status == "Under Review"


def test_enrolled_only_through_conversion(staff, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    adm.make_offer(a.applicant_id)
    adm.accept_offer(a.applicant_id)
    with pytest.raises(adm.ValidationError, match="convert"):
        adm.set_status(a.applicant_id, "Enrolled")
    with pytest.raises(adm.ValidationError, match="student link"):
        adm.update_applicant(a.applicant_id, {"converted_student_id": "X1"})


def test_new_application_starts_at_the_beginning(staff, applicant_payload):
    with pytest.raises(adm.ValidationError, match="starts as"):
        adm.create_applicant(applicant_payload(status="Offer Accepted"))


def test_allowed_next_never_offers_enrolled():
    assert "Enrolled" not in status_rules.allowed_next("Offer Accepted")
    assert status_rules.allowed_next("Rejected") == ()


def test_defer_moves_intake(staff, applicant_payload):
    a = adm.create_applicant(applicant_payload(intake_year="2027/28"))
    adm.make_offer(a.applicant_id)
    out = adm.defer(a.applicant_id, to_intake="2028/29", reason="gap year")
    assert (out.status, out.intake_year, out.deferred_from) == (
        "Deferred", "2028/29", "2027/28")


def test_withdraw_reason_is_checked(staff, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    with pytest.raises(adm.ValidationError):
        adm.withdraw(a.applicant_id, reason="bored")
    out = adm.withdraw(a.applicant_id, reason="Moved away")
    assert out.withdrawal_reason == "Moved away"


# ── Duplicates, archive, delete, merge ─────────────────────────────

def test_duplicate_needs_confirmation(staff, applicant_payload):
    adm.create_applicant(applicant_payload())
    with pytest.raises(adm.PossibleDuplicate) as e:
        adm.create_applicant(applicant_payload())
    assert len(e.value.matches) == 1
    adm.create_applicant(applicant_payload(), allow_duplicate=True)


def test_delete_refused_once_progressed(staff, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    adm.make_offer(a.applicant_id)
    with pytest.raises(adm.HasHistory):
        adm.delete_applicant(a.applicant_id)
    rs.archive_applicant(a.applicant_id, reason="entered twice")
    assert adm.list_applicants() == []
    assert [x.applicant_id for x in rs.list_archived()] == [a.applicant_id]
    with pytest.raises(adm.ValidationError, match="archived"):
        adm.reject(a.applicant_id)
    rs.restore_applicant(a.applicant_id)
    assert adm.get_applicant(a.applicant_id).is_archived is False


def test_delete_fresh_mistake_removes_children(staff, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    adm.add_note(a.applicant_id, "typo", author="adm1")
    assert adm.delete_applicant(a.applicant_id) is True
    assert adm.list_notes(a.applicant_id) == []
    assert adm.list_events(a.applicant_id) == []


def test_merge_moves_rows_and_archives(staff, applicant_payload):
    keep = adm.create_applicant(applicant_payload())
    dup = adm.create_applicant(applicant_payload(email="z2@example.com",
                                                 address="1 High St"),
                               allow_duplicate=True)
    adm.add_note(dup.applicant_id, "phoned", author="adm1")
    det.add_contact(dup.applicant_id, {"name": "Pat", "phone": "07700900456"})
    r = rs.merge_applicants(keep.applicant_id, dup.applicant_id)
    assert r.moved["admissions_notes"] == 1
    assert r.moved["admissions_contacts"] == 1
    assert "address" in r.filled
    kept = adm.get_applicant(keep.applicant_id)
    assert kept.address == "1 High St" and kept.subjects == ["Mathematics"]
    gone = adm.get_applicant(dup.applicant_id)
    assert gone.merged_into == keep.applicant_id and gone.is_archived
    with pytest.raises(adm.ValidationError, match="merged"):
        rs.restore_applicant(dup.applicant_id)


# ── Erasure ────────────────────────────────────────────────────────

def test_erasure_needs_a_second_person(staff, sign_in, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    with pytest.raises(adm.ValidationError, match="two people"):
        adm.erase_applicant(a.applicant_id)
    req = rs.request_erasure(a.applicant_id, reason="asked 2026-10-27")
    sign_in("adm1", capabilities={access.ADMISSIONS, access.GOVERNANCE})
    with pytest.raises(adm.ValidationError, match="second person"):
        rs.approve_erasure(req.request_id)
    sign_in("adm2", capabilities={access.ADMISSIONS})
    with pytest.raises(access.AccessDenied):
        rs.approve_erasure(req.request_id)
    sign_in("gov2", capabilities={access.ADMISSIONS, access.GOVERNANCE})
    assert rs.approve_erasure(req.request_id) is True
    assert adm.get_applicant(a.applicant_id) is None
    log = rs.erasure_log()
    assert log[0]["applicant_id"] == a.applicant_id
    assert log[0]["approved_by"] == "gov2"


# ── Sensitive information and identity ─────────────────────────────

def test_sensitive_text_only_for_its_area(staff, sign_in, admdb,
                                          applicant_payload):
    a = adm.create_applicant(applicant_payload())
    with pytest.raises(access.AccessDenied):
        det.set_sensitive(a.applicant_id, "safeguarding", "known to CSC")
    sign_in("dsl1", capabilities={access.SAFEGUARDING})
    det.set_sensitive(a.applicant_id, "safeguarding", "known to CSC",
                      received_from="Old School")
    assert det.get_sensitive(a.applicant_id).visible["safeguarding"] == \
        "known to CSC"
    assert [i.applicant_id for i in det.dsl_queue()] == [a.applicant_id]
    sign_in("adm1")
    view = det.get_sensitive(a.applicant_id)
    assert view.held["safeguarding"] and "safeguarding" not in view.visible
    assert any(area == "admissions safeguarding"
               for _u, area, _a, _k in admdb["sensitive_log"])


def test_profile_validation(staff, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    with pytest.raises(adm.ValidationError):
        det.update_profile(a.applicant_id, sex="x")
    out = det.update_profile(a.applicant_id, sex="Female", ethnicity="31",
                             looked_after="yes")
    assert (out.sex, out.ethnicity, out.looked_after) == ("female", "31", True)


def test_identity_keeps_last4_and_history(staff, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    assert det.identity_ok(a.applicant_id)[0] is False
    det.record_identity_check(a.applicant_id, document_type="Passport",
                              document_number="AB 1234 5678",
                              right_to_study="Yes - UK or Irish citizen")
    rec = det.get_identity(a.applicant_id)
    assert rec.id_number_last4 == "5678"
    assert det.identity_ok(a.applicant_id)[0] is True
    det.record_identity_check(a.applicant_id, document_type="Passport",
                              document_number="999999",
                              right_to_study="Yes - visa (check expiry)",
                              visa_expiry="2020-01-01")
    assert det.identity_ok(a.applicant_id) == (False,
                                               "Visa expired on 2020-01-01")
    assert len(det.identity_history(a.applicant_id)) == 2


# ── Conversion ─────────────────────────────────────────────────────

def _accepted(applicant_payload, **over):
    a = adm.create_applicant(applicant_payload(**over))
    adm.make_offer(a.applicant_id, offer_type="Conditional",
                   conditions="5 in Maths")
    adm.accept_offer(a.applicant_id)
    return a


def test_conversion_gates_and_override(staff, applicant_payload):
    a = _accepted(applicant_payload)
    with pytest.raises(conv.ConversionBlocked) as e:
        conv.convert_to_student(a.applicant_id)
    assert len(e.value.gates) == 2
    det.add_contact(a.applicant_id, {"name": "Pat Testerson",
                                     "relationship": "Mother",
                                     "phone": "07700900456",
                                     "is_emergency": True})
    det.update_profile(a.applicant_id, sex="male")
    out, sid = conv.convert_to_student(a.applicant_id,
                                       override_reason="results confirmed by phone")
    assert out.status == "Enrolled" and out.converted_student_id == sid
    assert conv.convert_to_student(a.applicant_id)[1] == sid   # no-op
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    st = students.get_student(sid)
    assert (st.gender, st.emergency_contact_name) == ("male", "Pat Testerson")
    steps = {s["step"] for s in conv.get_conversion(a.applicant_id).steps}
    assert "override" in steps


def test_conversion_needs_students_manage(admdb, sign_in, applicant_payload):
    sign_in("adm1")
    a = _accepted(applicant_payload)
    with pytest.raises(access.AccessDenied):
        conv.convert_to_student(a.applicant_id, override_reason="x")


def test_second_conversion_refused_while_claimed(staff, applicant_payload):
    a = _accepted(applicant_payload)
    conv._claim(a.applicant_id)
    with pytest.raises(adm.ValidationError, match="already being converted"):
        conv.convert_to_student(a.applicant_id, override_reason="x")


# ── GCSE concern check ─────────────────────────────────────────────

def test_gcse_concern_ignores_counts():
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_reports,
    )
    assert applicant_reports.gcse_concern("Maths 7", "5 GCSEs") is None
    msg = applicant_reports.gcse_concern(
        "Maths 7, English 4, Science 6",
        "5 GCSEs at grade 4 including 6 in Maths")
    assert "English 4" in msg and "Science" not in msg
