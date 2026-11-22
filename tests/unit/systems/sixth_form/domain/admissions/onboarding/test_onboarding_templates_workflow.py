"""Onboarding templates (stored, versioned, learner-type) and workflow
(choosing a template from real records, add-ons, owner queues, bulk
actions, cohort opening, Year 13 re-onboarding, the bursary link)."""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    bursary_link,
    onboarding as ob,
    templates as tpl,
    workflow as wf,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students,
)

ALL = {access.ADMISSIONS, access.STUDENTS_MANAGE, access.SEND,
       access.MEDICAL, access.SAFEGUARDING, access.PASTORAL}
PAST, NEXT = "2025/26", "2026/27"


@pytest.fixture
def staff(admdb, sign_in, monkeypatch):
    from education_system.systems.sixth_form.domain.staff import staff as st
    if admdb:
        monkeypatch.setattr(st, "DB_PATH", admdb["path"])
        monkeypatch.setattr(st, "_DB_READY", False)
        monkeypatch.setattr(tpl, "_READY_PATHS", set())
    try:
        from education_system.platform.identity.staff_directory import (
            staff_directory_service,
        )
        monkeypatch.setattr(staff_directory_service, "register_local_staff",
                            lambda *a, **k: None)
    except ImportError:
        pass
    return sign_in("adm1", capabilities=ALL)


_n = [0]


def _student(**extra):
    _n[0] += 1
    first = f"Tem{_n[0]}"
    return students.create_student({
        "first_name": first, "last_name": "Plate", "date_of_birth": "2009-01-02",
        "status": "Active", "personal_email": f"{first.lower()}@example.com",
        **extra}, allow_duplicate=True).student_id


def _enrol(sid, year=NEXT, group=12, start=None, status="Enrolled",
           tutor_group=None):
    return enrolments.create_enrolment({
        "student_id": sid, "academic_year": year, "year_group": group,
        "start_date": start or f"{year[:4]}-09-04", "status": status,
        "tutor_group": tutor_group})


def _items(chk):
    return {i.key: i for i in ob.list_items(checklist_id=chk.checklist_id)}


def test_built_ins_are_seeded_and_saves_are_versioned(staff):
    names = {t.name for t in tpl.list_templates()}
    assert set(ob.TEMPLATES) <= names
    assert {tpl.YEAR13_TRANSFER_TEMPLATE, tpl.SEND_TEMPLATE,
            tpl.CARE_TEMPLATE, tpl.YEAR13_RETURN_TEMPLATE} <= names
    intl = tpl.get_template(tpl.INTERNATIONAL_TEMPLATE)
    keys = {i.key: i for i in intl.items}
    assert keys[tpl.UKVI_KEY].required
    assert any(k.startswith("CAS") for k in keys)
    first = ob.open_enrolment_checklist(_student())
    std = tpl.get_template(ob.DEFAULT_TEMPLATE)
    items = [i.__dict__ for i in std.items] + [
        {"task": "Car parking permit", "category": "Equipment",
         "required": False, "due_offset_days": 3, "owner_role": "admissions"}]
    saved = tpl.save_template(ob.DEFAULT_TEMPLATE, items=items,
                              learner_type=tpl.YEAR12, note="parking")
    assert saved.version == std.version + 1
    vers = tpl.versions(ob.DEFAULT_TEMPLATE)
    assert vers[0]["changes"] == "+Car parking permit"
    assert vers[0]["saved_by"] == "adm1"
    second = ob.open_enrolment_checklist(_student())
    assert "Car parking permit" not in _items(first)
    assert _items(second)["Car parking permit"].owner_role == "Admissions"
    assert tpl.templates_used(first.checklist_id)[0]["version"] == std.version
    assert tpl.templates_used(second.checklist_id)[0]["version"] == saved.version
    # The old version is kept as it was.
    assert len(tpl.get_template(ob.DEFAULT_TEMPLATE,
                                version=std.version).items) == len(std.items)


def test_template_rules_and_gate(staff, sign_in):
    with pytest.raises(ob.ValidationError, match="UKVI"):
        tpl.save_template("Intl lite", learner_type=tpl.INTERNATIONAL,
                          items=[{"task": "Passport / visa scanned",
                                  "category": "Enrolment Paperwork"}])
    with pytest.raises(ob.ValidationError, match="owner"):
        tpl.save_template("Odd", items=[{"task": "X task",
                                         "category": "Other",
                                         "owner_role": "Caretaking"}])
    with pytest.raises(ob.ValidationError, match="twice"):
        tpl.save_template("Dup", items=[
            {"task": "Same", "category": "Other"},
            {"task": "Same", "category": "Other"}])
    with pytest.raises(ob.ValidationError, match="default"):
        tpl.set_active(ob.DEFAULT_TEMPLATE, False, reason="not wanted")
    sign_in("viewer", capabilities=set())
    with pytest.raises(access.AccessDenied):
        tpl.save_template("Nope", items=[{"task": "A", "category": "Other"}])


def test_due_dates_follow_the_start_date_and_offsets(staff):
    sid = _student()
    e = _enrol(sid, start=f"{NEXT[:4]}-09-07")
    chk = ob.open_enrolment_checklist(sid, enrolment_id=e.enrolment_id)
    items = _items(chk)
    start = _dt.date(int(NEXT[:4]), 9, 7)
    ukvi = items["Photocopy of ID / passport"]
    assert ukvi.due_date == start.isoformat()
    lib = items["Library account activated"]
    assert lib.due_date == (start + _dt.timedelta(days=10)).isoformat()
    assert lib.owner_role == "Library"
    assert chk.academic_year == NEXT and chk.enrolment_id == e.enrolment_id


def test_choose_template_reads_the_records(staff):
    sid = _student(nationality="French")
    _enrol(sid)
    c = wf.choose_template(sid)
    assert c.template == tpl.INTERNATIONAL_TEMPLATE
    assert any("nationality" in r for r in c.reasons)
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks as idc,
    )
    idc.record_id_check(sid, document_type="Passport",
                        document_number="12345678",
                        right_to_study="Yes - settled / pre-settled / ILR")
    assert wf.choose_template(sid).template == ob.DEFAULT_TEMPLATE

    y13 = _student()
    _enrol(y13, group=13)
    assert wf.choose_template(y13).template == tpl.YEAR13_TRANSFER_TEMPLATE

    late = _student()
    _enrol(late, start=f"{int(NEXT[:4]) + 1}-01-06")
    assert wf.choose_template(late).template == tpl.MID_YEAR_TEMPLATE


def test_send_and_care_add_ons(staff):
    from education_system.systems.sixth_form.domain.pastoral.send import send
    sid = _student()
    e = _enrol(sid)
    send.create_entry({"student_id": sid, "register_status": "SEN Support",
                       "primary_need": "Cognition & Learning",
                       "date_added": _dt.date.today().isoformat()})
    res = wf.open_for_learner(sid, enrolment=e)
    assert res.choice.addons == [tpl.SEND_TEMPLATE]
    items = _items(res.checklist)
    assert items[tpl.EHCP_REVIEW_KEY].status == "N/A"
    assert items["Access arrangements assessed (exams)"].owner_role == "Exams"
    assert res.checklist.learner_type == f"{tpl.YEAR12} + {tpl.SEND}"
    # Re-running adds nothing twice.
    again = wf.open_for_learner(sid, enrolment=e)
    assert again.checklist.checklist_id == res.checklist.checklist_id
    assert len(_items(again.checklist)) == len(items)
    used = [u["template_name"] for u in
            tpl.templates_used(res.checklist.checklist_id)]
    assert used == [ob.DEFAULT_TEMPLATE, tpl.SEND_TEMPLATE]
    hist = {h["action"] for h in ob.history(checklist_id=res.checklist.checklist_id)}
    assert "Template applied" in hist


def test_conversion_links_the_bursary_task(staff, applicant_payload):
    from education_system.systems.sixth_form.domain.admissions import (
        admissions as adm, applicant_details as det, conversion as conv,
    )
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries,
    )
    a = adm.create_applicant(applicant_payload())
    det.update_profile(a.applicant_id, bursary_interest=True, ehcp=True)
    det.record_identity_check(a.applicant_id, document_type="Passport",
                              document_number="123456789",
                              right_to_study="Yes - UK or Irish citizen")
    adm.make_offer(a.applicant_id, offer_type="Unconditional", conditions=None)
    adm.accept_offer(a.applicant_id)
    _a, sid = conv.convert_to_student(a.applicant_id)
    rec = conv.get_conversion(a.applicant_id)
    chk = ob.get_checklist(rec.checklist_id)
    items = _items(chk)
    task = items[bursary_link.BURSARY_KEY]
    app = bursaries.list_applications(student_id=sid)[0]
    assert task.required and task.evidence_ref == f"bursary:{app.application_id}"
    assert tpl.EHCP_REVIEW_KEY in items             # EHCP on the application
    with pytest.raises(ob.ValidationError, match="Draft"):
        ob.tick(task.item_id)
    bursaries.set_status(app.application_id, "Submitted")
    done = ob.tick(task.item_id)
    assert done.status == "Done"
    assert done.evidence_ref == f"bursary:{app.application_id}"


def test_owner_queues_assignment_and_bulk(staff):
    from education_system.systems.sixth_form.domain.staff import staff as st
    it = st.create_staff({"first_name": "Ian", "last_name": "Tech",
                          "role": "IT Support", "department": "IT"})
    sid = _student()
    chk = ob.open_enrolment_checklist(sid)
    items = _items(chk)
    it_tasks = [i for i in items.values() if i.owner_role == "IT"]
    assert it_tasks
    assert {q.item.item_id for q in wf.my_queue("it")} >= {
        i.item_id for i in it_tasks}
    mine = {q.item.item_id: q.why for q in wf.my_queue(it.staff_id)}
    assert all(mine[i.item_id] == "IT" for i in it_tasks)
    with pytest.raises(ob.ValidationError, match="active member"):
        wf.assign_item(items["Lanyard issued"].item_id, assignee="nobody99")
    wf.assign_item(items["Lanyard issued"].item_id, assignee=it.email)
    assert ob.get_item(items["Lanyard issued"].item_id).assigned_to == it.staff_id
    assert mine.keys() < {q.item.item_id for q in wf.my_queue(it.staff_id)}
    with pytest.raises(ob.ValidationError):
        wf.my_queue("someone unknown")

    ids = [items["Lanyard issued"].item_id, items["Locker assigned"].item_id,
           items["Photocopy of ID / passport"].item_id]
    res = wf.bulk_set_status(ids, "N/A", reason="Not used at this college")
    assert res.done == ids[:2]
    assert res.failed and res.failed[0][0] == ids[2]       # ID task: never N/A
    moved = wf.bulk_assign(ids[:2], owner_role="Admissions", assignee=None)
    assert moved.done == ids[:2]
    assert ob.get_item(ids[0]).owner_role == "Admissions"
    assert ob.get_item(ids[0]).assigned_to is None


def test_bulk_open_for_cohort_reports_each_learner(staff):
    a, b = _student(), _student(nationality="Brazilian")
    _enrol(a, tutor_group=None)
    _enrol(b, tutor_group=None)
    ob.open_enrolment_checklist(a, academic_year=NEXT)
    lines = {x.student_id: x for x in wf.bulk_open_for_cohort(
        NEXT, year_group=12)}
    assert lines[a].result == "skipped"
    assert lines[b].result == "opened"
    assert lines[b].template == tpl.INTERNATIONAL_TEMPLATE
    again = {x.student_id: x.result for x in wf.bulk_open_for_cohort(NEXT)}
    assert again[b] == "skipped"


def test_reonboard_year_13_is_idempotent(staff):
    back, newcomer = _student(), _student()
    _enrol(back, year=PAST, group=12, start=f"{PAST[:4]}-09-04",
           status="Completed")
    _enrol(back, year=NEXT, group=13)
    _enrol(newcomer, year=NEXT, group=13)
    lines = {x.student_id: x for x in wf.reonboard_cohort(PAST, NEXT)}
    assert lines[back].result == "opened"
    assert lines[newcomer].result == "skipped"
    chk = ob.get_checklist(lines[back].checklist_id)
    assert (chk.template_name, chk.academic_year) == (
        tpl.YEAR13_RETURN_TEMPLATE, NEXT)
    assert "Year 13 timetable confirmed" in _items(chk)
    assert wf.choose_template(back).template == tpl.YEAR13_RETURN_TEMPLATE
    rerun = {x.student_id: x.result for x in wf.reonboard_cohort(PAST, NEXT)}
    assert rerun[back] == "skipped"
