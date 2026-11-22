"""Enrolment-day work: leaver steps, course changes, enrolment checks,
the status board / confirmation, agreements, right-to-study reads, the
visa expiry job and the Year 13 transfer-in conversion."""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    agreements as ag,
    course_changes as cc,
    enrolment_checks as ck,
    enrolment_day as day,
    enrolments as en,
    identity_checks as idc,
    leaver_effects as le,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students,
)

WRITER = {access.ADMISSIONS, access.STUDENTS_MANAGE}
TODAY = _dt.date.today()


@pytest.fixture
def enrol(admdb, sign_in, monkeypatch):
    """admdb plus the other stores these features read and write."""
    from education_system.systems.sixth_form.domain.academics.courses import courses
    from education_system.systems.sixth_form.domain.academics.timetable import timetable
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import store
    from education_system.systems.sixth_form.domain.staff import staff
    from education_system.systems.sixth_form.domains.finance.domain.fees import fees
    from education_system.systems.sixth_form.domains.operations.domain.id_cards import (
        id_cards,
    )
    for mod in (courses, timetable, exam_entries, staff, fees, id_cards):
        monkeypatch.setattr(mod, "DB_PATH", admdb["path"])
        monkeypatch.setattr(mod, "_DB_READY", False)
    monkeypatch.setattr(store, "_READY", set())
    # The exams timetable is not set up in these tests: series end dates.
    monkeypatch.setattr(le, "_paper_dates", lambda season, year: {})
    sign_in("enr1", capabilities=WRITER)
    return admdb


def _year():
    return en.current_academic_year()


def _student(first="Robin", dob="2009-03-01", **over):
    return students.create_student(
        {"first_name": first, "last_name": "Ash", "date_of_birth": dob,
         "status": "Active", "personal_email": f"{first.lower()}@example.com",
         **over}, allow_duplicate=True).student_id


def _enrolment(sid, days_ago=10, **over):
    first, _last = en.academic_year_dates(_year())
    start = max(first, (TODAY - _dt.timedelta(days=days_ago)).isoformat())
    return en.create_enrolment({"student_id": sid, "academic_year": _year(),
                                "year_group": 12, "start_date": start, **over})


def _course(subject, code, cap=2):
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as cg,
    )
    from education_system.systems.sixth_form.domain.academics.courses import courses
    c = courses.create_course({"course_code": code, "subject": subject,
                               "title": subject, "year_group": 12,
                               "academic_year": _year(), "max_students": cap})
    return cg.create_group({"course_id": c.course_id,
                            "group_name": f"12{code[:2]}1"})


def _aim(sid, subject):
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims as la,
    )
    return la.add_aim(sid, {"qualification_type": "A Level",
                            "subject": subject,
                            "start_date": en.current_enrolment(sid).start_date},
                      recorded_by="enr1", reason="test")


def _groups(sid):
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as cg,
    )
    return sorted(g.group_name for g in cg.groups_for_student(sid))


# ── Leaver steps ────────────────────────────────────────────────────

def test_on_left_ends_groups_entries_meals_and_reports_redo(enrol):
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_group_history as hist,
        class_groups as cg,
    )
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as ee,
    )
    from education_system.systems.sixth_form.domains.finance.domain.free_meals import (
        free_meals as fm,
    )
    sid = _student()
    _enrolment(sid)
    g = _course("Mathematics", "MA12")
    cg.add_member(g.group_id, sid)
    future = ee.create_entry({"student_id": sid, "subject": "Mathematics",
                              "exam_board": "AQA", "paper_code": "7357/1",
                              "season": "Summer", "year": TODAY.year + 1})
    past = ee.create_entry({"student_id": sid, "subject": "Mathematics",
                            "exam_board": "AQA", "paper_code": "7357/2",
                            "season": "January", "year": TODAY.year - 1})
    fm.create_entitlement({"student_id": sid,
                           "eligibility_basis": fm.ELIGIBILITY_BASES[0],
                           "start_date": "2025-09-01", "daily_allowance": 2.5})
    day_ = TODAY.isoformat()
    lines = le.on_left(sid, day_)
    text = "\n".join(lines)
    assert _groups(sid) == []
    assert any(e.action == "leave" for e in hist.membership_history(sid))
    assert ee.get_entry(future.entry_id).status == "Withdrawn"
    assert ee.get_entry(past.entry_id).status == "Entered"
    assert "check whether it was sat" in text
    assert fm.list_entitlements(student_id=sid)[0].status == "Ended"
    redo = le.on_returned(sid)
    assert len(redo) == 3 and any("12MA1" in r for r in redo)
    assert le.on_returned(sid) == [
        "No leaver changes are waiting to be re-done"]


def test_one_failing_step_does_not_stop_the_rest(enrol, monkeypatch):
    sid = _student()

    def boom(*_a):
        raise RuntimeError("exams store down")
    steps = tuple((n, boom if n == "Exam entries" else f)
                  for n, f in le._STEPS)
    monkeypatch.setattr(le, "_STEPS", steps)
    lines = le.on_left(sid, TODAY.isoformat())
    assert "Exam entries: not done — exams store down" in lines
    assert any(x.startswith("Free meals") for x in lines)


# ── Course changes ──────────────────────────────────────────────────

def test_change_course_moves_class_groups(enrol):
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as cg,
    )
    sid = _student()
    e = _enrolment(sid)
    phys = _aim(sid, "Physics")
    gp = _course("Physics", "PH12")
    _course("Chemistry", "CH12")
    cg.add_member(gp.group_id, sid)
    w = cc.change_window(e.enrolment_id)
    assert w.is_open and w.days_left > 0
    res = cc.change_course(e.enrolment_id, phys.aim_id, "Chemistry",
                           reason="Prefers chemistry", approved_by="HoSF")
    assert res.ok and not res.problems
    assert _groups(sid) == ["12CH1"]
    log = cc.change_log(_year())
    assert [(r["from"], r["to"]) for r in log] == [
        ("A Level Physics", "A Level Chemistry")]


def test_change_after_cutoff_needs_override(enrol):
    sid = _student()
    e = _enrolment(sid, days_ago=30)
    aim = _aim(sid, "Physics")
    cc.set_setting(cc.CHANGE_CUTOFF_DAYS, 5)
    assert not cc.change_window(e.enrolment_id).is_open
    with pytest.raises(cc.ValidationError, match="override"):
        cc.change_course(e.enrolment_id, aim.aim_id, "Chemistry",
                         reason="late", approved_by="HoSF")
    res = cc.change_course(e.enrolment_id, aim.aim_id, "Chemistry",
                           reason="late", approved_by="HoSF",
                           override_reason="Head agreed")
    assert res.override_used
    assert any("No Chemistry course" in p for p in res.problems)


def test_settings_are_gated(enrol, sign_in):
    sign_in("t1", capabilities={access.STUDENTS_VIEW})
    with pytest.raises(access.AccessDenied):
        cc.set_setting(cc.TUTOR_GROUP_LIMIT, 20)
    assert cc.get_setting(cc.TUTOR_GROUP_LIMIT) == 25


# ── Enrolment checks ────────────────────────────────────────────────

def test_check_enrolment_flags_missing_groups_and_identity(enrol):
    sid = _student()
    _enrolment(sid)
    _aim(sid, "History")
    kinds = {w.kind for w in ck.check_enrolment(sid)}
    assert {"class group missing", "identity", "right to study",
            "tutor group"} <= kinds


def test_full_groups_and_clashes(enrol):
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as cg,
    )
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as tt,
    )
    sid = _student()
    _enrolment(sid)
    _aim(sid, "History")
    _aim(sid, "Physics")
    gh = _course("History", "HI12", cap=1)
    gp = _course("Physics", "PH12")
    other = _student("Other")
    cg.add_member(gh.group_id, other)
    cg.add_member(gp.group_id, sid)
    msgs = [w.message for w in ck.check_enrolment(sid)]
    assert any("every class group is full" in m for m in msgs)
    cg.remove_member(gh.group_id, other)
    cg.add_member(gh.group_id, sid)
    for g in (gh, gp):
        tt.create_slot({"group_id": g.group_id, "day": 2, "period": 3})
    assert any(w.kind == "timetable clash" for w in ck.check_enrolment(sid))
    assert [t.group_name for t in ck.learner_timetable(sid)] == ["12HI1",
                                                                "12PH1"]


# ── Right to study reads ────────────────────────────────────────────

def _visa(sid, days):
    idc.record_id_check(sid, document_type="Passport", document_number="12345678",
                        right_to_study="Yes - visa (check expiry)",
                        visa_type="Student",
                        visa_expiry=(TODAY + _dt.timedelta(days=days)).isoformat())


def test_immigration_reads_are_logged_and_restricted(enrol, sign_in):
    sid = _student()
    _enrolment(sid)
    _visa(sid, 20)
    enrol["sensitive_log"].clear()
    assert idc.get_check(sid).visa_expiry is not None
    assert enrol["sensitive_log"][-1][1] == idc.SENSITIVE_AREA
    assert [r.student_id for r in idc.visa_expiring()] == [sid]
    sign_in("t1", capabilities={access.STUDENTS_VIEW})
    c = idc.get_check(sid)
    assert (c.right_to_study, c.visa_expiry) == (idc.RESTRICTED, idc.RESTRICTED)
    [o] = idc.outstanding_detail()
    assert o.visa == "expiring" and o.visa_expiry is None
    with pytest.raises(access.AccessDenied):
        idc.visa_expiring()
    with pytest.raises(access.AccessDenied):
        idc.id_history(sid)


def test_outstanding_is_current_year_live_only(enrol):
    live = _student("Live")
    _enrolment(live)
    gone = _student("Gone")
    e = _enrolment(gone)
    en.archive_enrolment(e.enrolment_id, reason="test")
    old = _student("Old")
    en.create_enrolment({"student_id": old, "academic_year": "2023/24",
                         "year_group": 12, "start_date": "2023-09-04"})
    assert [r[0] for r in idc.outstanding()] == [live]
    idc.record_id_check(live, document_type="Passport", document_number="9999",
                        right_to_study="Not yet confirmed")
    [o] = idc.outstanding_detail()
    assert o.id_checked and "right to study not confirmed" in o.problems


# ── Agreements ──────────────────────────────────────────────────────

def test_agreements_record_correct_withdraw(enrol):
    sid = _student()
    e = _enrolment(sid)
    st = ag.state(e.enrolment_id)
    assert st.parent_needed and not st.complete
    ag.record(e.enrolment_id, ag.LEARNER, method="Paper")
    with pytest.raises(ag.ValidationError, match="already"):
        ag.record(e.enrolment_id, ag.LEARNER, method="Paper")
    with pytest.raises(ag.ValidationError, match="relationship"):
        ag.record(e.enrolment_id, ag.PARENT, method="Online",
                  signed_name="Sam Ash")
    p = ag.record(e.enrolment_id, ag.PARENT, method="Online",
                  signed_name="Sam Ash", relationship="Mother")
    p2 = ag.correct(p.agreement_id, reason="typo", signed_name="Sam Ashe")
    assert ag.get(p.agreement_id).status == ag.CORRECTED
    assert p2.replaces_id == p.agreement_id and p2.signed_name == "Sam Ashe"
    assert ag.state(e.enrolment_id).complete
    assert ag.outstanding() == []
    ag.withdraw(p2.agreement_id, reason="wrong person")
    assert [r.student_id for r in ag.outstanding()] == [sid]
    actions = [h["action"] for h in ag.history(e.enrolment_id)]
    assert "withdrawn" in actions and "corrected" in actions


def test_adult_needs_no_parent(enrol):
    sid = _student(dob="2000-01-01")
    e = _enrolment(sid)
    assert not ag.state(e.enrolment_id).parent_needed


# ── Board, confirmation, ID card ────────────────────────────────────

def test_board_and_confirmation(enrol, sign_in):
    sid = _student()
    e = _enrolment(sid)
    _aim(sid, "History")
    st = day.learner_status(sid)
    assert st.overall == day.OUTSTANDING
    names = {i.name for i in st.items}
    assert {"Enrolment", "ID check", "Right to study", "Photo on file",
            "Learner agreement", "Class groups placed"} <= names
    assert [r.student_id for r in day.cohort_board()] == [sid]
    text = day.confirmation_text(e.enrolment_id)
    assert "Robin Ash" in text and "A Level History" in text
    assert "COLLEGE EXPECTATIONS" in text and "Parent / guardian" in text
    day.save_template("Be kind and be on time.")
    assert "Be kind and be on time." in day.confirmation_text(e.enrolment_id)
    card = day.id_card_data(sid)
    assert card.valid_until == en.academic_year_dates(_year())[1]
    sign_in("t1", capabilities={access.STUDENTS_VIEW})
    with pytest.raises(access.AccessDenied):
        day.save_template("x")


# ── Visa expiry job ─────────────────────────────────────────────────

def test_visa_job_messages_admissions_staff(enrol, outbox):
    from education_system.systems.sixth_form.domain.staff import staff
    from education_system.systems.sixth_form.infrastructure.scheduler import jobs
    sid = _student()
    _enrolment(sid)
    _visa(sid, 10)
    staff.create_staff({"first_name": "Ann", "last_name": "Admin",
                        "role": "Administrator"})
    staff.create_staff({"first_name": "Tom", "last_name": "Teach",
                        "role": "Teacher"})
    access.set_current(access.Principal(username="", user_id=None, role=""))
    r = jobs.enrolment_visa_expiry()
    assert not r.errors
    assert [m.to_name for m in outbox] == ["Ann Admin"]
    assert sid in outbox[0].body


# ── Year 13 transfer-in ─────────────────────────────────────────────

def test_convert_straight_into_year_13(enrol, sign_in, applicant_payload):
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims as la,
    )
    from education_system.systems.sixth_form.domain.admissions import (
        admissions as adm,
        conversion as conv,
    )
    sign_in("adm1", capabilities=WRITER)
    a = adm.create_applicant(applicant_payload())
    adm.make_offer(a.applicant_id, offer_type="Unconditional", conditions=None)
    adm.accept_offer(a.applicant_id)
    with pytest.raises(conv.ValidationError, match="12 or 13"):
        conv.convert_to_student(a.applicant_id, year_group=11)
    _a, sid = conv.convert_to_student(a.applicant_id, academic_year=_year(),
                                      year_group=13,
                                      override_reason="transfer-in test")
    assert [e.year_group for e in en.list_for_student(sid)] == [13]
    end_year = int(_year()[:4]) + 1
    assert all(x.planned_end_date == f"{end_year}-06-30"
               for x in la.active_aims(sid))
