"""Onboarding rules (2026-10-29): notes never count as evidence, N/A and
Blocked need reasons, renaming keeps a task's rule, a checklist completes
only when its required tasks are done, deleting archives, one open list
per learner per year, right to study needs a second person, sensitive
tasks are masked, leavers' lists are cancelled, and every change is in
the history."""

from __future__ import annotations

import pytest

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
def staff(admdb, sign_in):
    return sign_in("enr1", capabilities={access.STUDENTS_MANAGE})


def _student(first="Ola"):
    return students.create_student({
        "first_name": first, "last_name": "Board", "date_of_birth": "2009-01-02",
        "status": "Active", "personal_email": f"{first.lower()}@example.com"},
        allow_duplicate=True).student_id


def _items(chk):
    return {i.key: i for i in ob.list_items(checklist_id=chk.checklist_id)}


def test_notes_are_never_evidence_and_rename_keeps_the_rule(staff):
    chk = ob.open_enrolment_checklist(_student())
    item = _items(chk)["Photo consent"]
    ob.update_item(item.item_id, {"notes": "Evidence: in the file"})
    with pytest.raises(ob.ValidationError, match="consent"):
        ob.tick(item.item_id)
    ob.update_item(item.item_id, {"task_name": "Photos OK"})
    with pytest.raises(ob.ValidationError, match="consent"):
        ob.tick(item.item_id)
    with pytest.raises(ob.ValidationError, match="at least"):
        ob.tick(item.item_id, evidence="x")


def test_created_done_goes_through_the_gate_and_is_not_left_behind(staff):
    chk = ob.open_enrolment_checklist(_student())
    before = len(ob.list_items(checklist_id=chk.checklist_id))
    with pytest.raises(ob.ValidationError, match="consent"):
        ob.create_item({"checklist_id": chk.checklist_id,
                        "task_name": "Photo consent", "category": "Other",
                        "status": "Done"})
    assert len(ob.list_items(checklist_id=chk.checklist_id)) == before


def test_na_and_blocked_need_reasons_and_id_is_never_na(staff):
    chk = ob.open_enrolment_checklist(_student())
    by = _items(chk)
    with pytest.raises(ob.ValidationError, match="can't be N/A"):
        ob.set_item_status(by["Photocopy of ID / passport"].item_id, "N/A",
                           reason="not needed")
    with pytest.raises(ob.ValidationError, match="at least"):
        ob.set_item_status(by["Parental consent (under 18)"].item_id, "N/A",
                           reason="no")
    with pytest.raises(ob.ValidationError, match="blocking"):
        ob.set_item_status(by["Locker assigned"].item_id, "Blocked")
    out = ob.set_item_status(by["Locker assigned"].item_id, "Blocked",
                             reason="Waiting for keys")
    assert out.blocked_reason == "Waiting for keys"


def test_completion_rules_and_done_items_stay(staff):
    chk = ob.open_enrolment_checklist(_student())
    with pytest.raises(ob.ValidationError, match="required task"):
        ob.update_checklist(chk.checklist_id, {"status": "Completed"})
    with pytest.raises(ob.ValidationError, match="Say why"):
        ob.update_checklist(chk.checklist_id, {"status": "Cancelled"})
    locker = _items(chk)["Locker assigned"]
    ob.tick(locker.item_id)
    assert ob.get_checklist(chk.checklist_id).status == "In Progress"
    with pytest.raises(ob.ValidationError, match="stays on the record"):
        ob.delete_item(locker.item_id)
    for i in ob.list_items(checklist_id=chk.checklist_id):
        if i.required and not i.is_done:
            ob.tick(i.item_id, evidence="Seen on enrolment day")
    assert ob.get_checklist(chk.checklist_id).status == "Completed"


def test_on_hold_is_never_auto_completed(staff):
    chk = ob.open_enrolment_checklist(_student())
    ob.update_checklist(chk.checklist_id, {"status": "On Hold",
                                           "status_reason": "Awaiting docs"})
    for i in ob.list_items(checklist_id=chk.checklist_id):
        if i.required and not i.is_done:
            ob.tick(i.item_id, evidence="Seen on enrolment day")
    assert ob.get_checklist(chk.checklist_id).status == "On Hold"


def test_one_open_list_per_year_and_delete_archives(staff):
    sid = _student()
    chk = ob.open_enrolment_checklist(
        sid, extra_tasks=[("Bursary application", "Finance", True)])
    assert ob.open_enrolment_checklist(sid).checklist_id == chk.checklist_id
    assert chk.academic_year
    with pytest.raises(ob.ValidationError, match="already has an open"):
        ob.create_checklist({"student_id": sid,
                             "template_name": ob.DEFAULT_TEMPLATE})
    assert ob.delete_checklist(chk.checklist_id, reason="made in error")
    assert ob.list_checklists(student_id=sid) == []
    assert len(ob.list_checklists(student_id=sid, archived_only=True)) == 1
    assert ob.restore_checklist(chk.checklist_id).is_open


def test_right_to_study_needs_a_second_person(staff, sign_in):
    chk = ob.open_enrolment_checklist(_student())
    uk = ob.create_item({"checklist_id": chk.checklist_id,
                         "task_name": "UKVI right-to-study check",
                         "category": "Enrolment Paperwork", "required": True})
    got = ob.tick(uk.item_id, evidence="Share code checked online")
    assert got.status == "In Progress" and got.awaiting_second_check
    with pytest.raises(ob.ValidationError, match="someone other"):
        ob.confirm_evidence(uk.item_id)
    sign_in("enr2", capabilities={access.STUDENTS_MANAGE})
    done = ob.confirm_evidence(uk.item_id)
    assert done.status == "Done" and done.second_check_by == "enr2"


def test_sensitive_tasks_are_masked(staff, sign_in):
    chk = ob.open_enrolment_checklist(
        _student("Kai"), extra_tasks=[(ob.CONTACT_DSL_TASK, "Other", True)])
    sign_in("t1", capabilities={access.STUDENTS_VIEW})
    names = [i.task_name for i in ob.list_items(checklist_id=chk.checklist_id)]
    assert ob.RESTRICTED in names and ob.CONTACT_DSL_TASK not in names


def test_leaver_lists_are_cancelled_and_history_is_kept(staff):
    sid = _student()
    chk = ob.open_enrolment_checklist(sid)
    lines = ob.close_for_leaver(sid, "2026-01-01")
    assert lines and ob.get_checklist(chk.checklist_id).status == "Cancelled"
    actions = [h["action"] for h in ob.history(checklist_id=chk.checklist_id)]
    assert actions[0] == "Cancelled" and "Created" in actions
