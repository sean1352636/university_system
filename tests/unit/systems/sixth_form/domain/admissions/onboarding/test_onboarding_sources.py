"""Record-backed onboarding tasks, ID-check sync, refused-consent
follow-ups, induction registers, reports, the chase job, the portal view
and the enrolment-day board's empty-checklist rule."""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolment_day,
    identity_checks as idc,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    consent_followups as cf,
    evidence_sources as es,
    induction,
    onboarding as ob,
    onboarding_jobs,
    onboarding_portal as portal,
    onboarding_reports as rep,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students,
)
from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
    tutor_groups as tg,
)

CAPS = {access.STUDENTS_MANAGE, access.ADMISSIONS, access.PASTORAL}


@pytest.fixture
def staff(admdb, sign_in):
    return sign_in("enr1", capabilities=CAPS)


def _student(first="Ola", **extra):
    return students.create_student({
        "first_name": first, "last_name": "Board",
        "date_of_birth": "2009-01-02", "status": "Active",
        "personal_email": f"{first.lower()}@example.com", **extra},
        allow_duplicate=True).student_id


def _by_key(chk):
    return {i.key: i for i in ob.list_items(checklist_id=chk.checklist_id)}


def _add(chk, task, required=True, **kw):
    return ob.create_item({"checklist_id": chk.checklist_id,
                           "task_name": task, "category": "Other",
                           "required": required, **kw})


def test_rules_are_registered_for_template_keys():
    assert es.rule_for("Student ID card issued") is es.id_card_rule
    assert es.rule_for("Email / network account created") is es.it_account_rule
    assert es.rule_for("Library account activated") is es.library_rule
    assert es.rule_for("Meet form tutor") is es.meet_tutor_rule
    assert es.rule_for("Proof of address") is es.proof_of_address_rule
    assert es.rule_for("Bursary reviewed") is es.bursary_reviewed_rule
    assert es.rule_for("Photo consent") is None           # own rule
    assert es.rule_for("Acceptable-use policy signed") is None


def test_login_unreadable_means_cant_tell(staff):
    chk = ob.open_enrolment_checklist(_student())
    item = _by_key(chk)["Email / network account created"]
    assert ob.evidence_problem(item) is None        # auth.db blocked in tests


def test_tutor_group_rule_and_resync(staff):
    sid = _student()
    chk = ob.open_enrolment_checklist(sid, template="Empty (no items)")
    item = _add(chk, "Tutor group assigned")
    assert ob.evidence_problem(item) is None        # no groups in use yet
    g = tg.create_group({"name": "12A", "year_group": 12})
    with pytest.raises(ob.ValidationError, match="tutor group"):
        ob.tick(item.item_id)
    tg.assign_student(sid, g.tutor_group_id)
    res = es.resync(chk.checklist_id)
    assert res.ticked and ob.get_item(item.item_id).evidence_ref == \
        "tutorgroup:12A"
    tg.unassign_student(sid)
    res = es.resync(chk.checklist_id)
    assert res.reopened and ob.get_item(item.item_id).status == "Pending"


def test_address_rule_resync_never_touches_hand_evidence(staff):
    sid = _student()
    chk = ob.open_enrolment_checklist(sid, template="Empty (no items)")
    uk = _add(chk, "UK address confirmed")
    proof = _add(chk, "Proof of address")
    with pytest.raises(ob.ValidationError, match="home address"):
        ob.tick(uk.item_id)
    with pytest.raises(ob.ValidationError, match="home address"):
        ob.tick(proof.item_id)
    ob.tick(proof.item_id, evidence="Council tax bill seen")
    students.update_student(sid, {"address": "1 High St", "postcode": "AB1 2CD"})
    es.resync(chk.checklist_id)
    assert ob.get_item(uk.item_id).evidence_ref == "student:address"
    students.update_student(sid, {"address": "", "postcode": ""})
    es.resync(chk.checklist_id)
    assert ob.get_item(uk.item_id).status == "Pending"
    after = ob.get_item(proof.item_id)
    assert after.is_done and after.evidence == "Council tax bill seen"


def test_id_check_ticks_every_id_task_and_revoke_reopens(staff):
    sid = _student()
    chk = ob.open_enrolment_checklist(sid, template="International student")
    idc.record_id_check(sid, document_type="Passport", document_number="12345",
                        right_to_study="Yes - UK or Irish citizen")
    by = _by_key(chk)
    assert by["Passport / visa scanned"].is_done
    assert by["UKVI right-to-study check"].evidence_ref == "idcheck"
    idc.record_id_check(sid, document_type="Passport", document_number="12345",
                        right_to_study="No")
    by = _by_key(chk)
    assert by["UKVI right-to-study check"].status == "Pending"
    assert by["Passport / visa scanned"].is_done
    idc.revoke_id_check(sid, reason="Document was not genuine")
    item = _by_key(chk)["Passport / visa scanned"]
    assert item.status == "Pending" and "not genuine" in item.notes


def test_refused_consent_opens_one_follow_up(staff):
    chk = ob.open_enrolment_checklist(_student())
    photo = _by_key(chk)["Photo consent"]
    link = ob.record_consent(photo.item_id, granted=False, given_by="Mum")
    f1 = cf.after_consent(link)
    assert f1.task_name == "Follow up refused photo consent"
    assert cf.after_consent(link).item_id == f1.item_id
    link = ob.record_consent(photo.item_id, granted=True, given_by="Mum")
    cf.after_consent(link)
    assert ob.get_item(f1.item_id).is_done


def test_induction_register_ticks_and_untick(staff):
    sid = _student()
    chk = ob.open_enrolment_checklist(sid)
    today = _dt.date.today().isoformat()
    s = induction.create_session({"title": "Safeguarding talk",
                                  "session_date": today, "start_time": "09:00",
                                  "end_time": "10:00", "capacity": 1,
                                  "task_key": "Safeguarding briefing"})
    other = _student("Kai")
    res = induction.book(s.session_id, [sid, other])
    assert res.booked == [sid] and "full" in res.skipped[0][1]
    out = induction.mark_register(s.session_id, {sid: "Present"})
    item = _by_key(chk)["Safeguarding briefing"]
    assert out.ticked and item.evidence_ref == f"induction:{s.session_id}"
    induction.mark_register(s.session_id, {sid: "Absent"})
    assert _by_key(chk)["Safeguarding briefing"].status == "Pending"
    with pytest.raises(ob.ValidationError, match="own record"):
        induction.create_session({"title": "x", "session_date": today,
                                  "start_time": "09:00",
                                  "task_key": "Photo consent"})


def test_induction_writes_are_gated(staff, sign_in):
    sign_in("t1", capabilities={access.STUDENTS_VIEW})
    with pytest.raises(access.AccessDenied):
        induction.create_session({"title": "x", "session_date": "2026-09-01",
                                  "start_time": "09:00"})


def test_reports_and_csv(staff):
    sid = _student()
    chk = ob.open_enrolment_checklist(sid, due_date="2020-01-01")
    _add(chk, "Overdue thing", due_date="2020-01-01")
    rows = rep.outstanding_tasks(overdue_only=True)
    assert any(r.task == "Overdue thing" for r in rows)
    dash = rep.dashboard("year_group", academic_year=chk.academic_year)
    assert sum(r.checklists for r in dash) >= 1
    assert sum(r.overdue for r in dash) >= 1
    text = rep.export_csv("outstanding")
    assert text.startswith("student_id,") and "Overdue thing" in text


def test_chase_notifies_once_a_week(staff, monkeypatch):
    sid = _student()
    chk = ob.open_enrolment_checklist(sid, assigned_to="enr1")
    _add(chk, "Overdue thing", due_date="2020-01-01")
    sent = []
    from education_system.systems.sixth_form.domains.communications.domain.notifications import (
        notifications,
    )
    monkeypatch.setattr(notifications, "create_notification",
                        lambda p: sent.append(p))
    r = onboarding_jobs.chase_overdue()
    assert r.notified.get("enr1") and sent[0]["channel"] == "In-App"
    again = onboarding_jobs.chase_overdue()
    assert again.skipped_recent == 1 and len(sent) == 1


def test_portal_shows_own_tasks_and_completes_through_rules(staff):
    sid = _student()
    chk = ob.open_enrolment_checklist(
        sid, extra_tasks=[(ob.CONTACT_DSL_TASK, "Other", True)])
    aup = _by_key(chk)["Acceptable-use policy signed"]
    ob.update_item(aup.item_id, {"owner_role": "learner"})
    view = portal.learner_checklist(sid)
    assert ob.CONTACT_DSL_TASK not in [t["task"] for t in view["tasks"]]
    assert [t["item_id"] for t in view["to_do"]] == [aup.item_id]
    with pytest.raises(ob.ValidationError, match="college staff"):
        portal.learner_complete(sid, _by_key(chk)["Locker assigned"].item_id)
    portal.learner_complete(sid, aup.item_id, note="Read and agreed")
    done = ob.get_item(aup.item_id)
    assert done.is_done and done.completed_by == f"learner:{sid}"
    assert ob.history(checklist_id=chk.checklist_id)[0]["changed_by"] == \
        f"learner:{sid}"


def test_empty_checklist_is_not_ready(staff):
    sid = _student()
    ob.open_enrolment_checklist(sid, template="Empty (no items)")
    rows = enrolment_day._onboarding_items(sid)
    assert rows[0].name == "Onboarding checklist" and rows[0].done is False
