"""The enrolment data check finds drift between the student record,
enrolments, learning aims and tutor groups, and repairs it only through
the domain functions (and only for someone who may change enrolments)."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.qualifications import (
    learning_aims as la,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as en,
    reconcile,
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

PAST = "2024/25"
YEAR = "2025/26"


@pytest.fixture
def staff(admdb, sign_in):
    return sign_in("enr1", capabilities={access.STUDENTS_MANAGE})


def _student(first="Ava", **over):
    data = {"first_name": first, "last_name": "Drift",
            "date_of_birth": "2008-05-06", "status": "Active",
            "subject_1": "Mathematics", "subject_2": "Physics",
            "subject_3": "Chemistry", **over}
    return students.create_student(data, allow_duplicate=True).student_id


def _raw_enrolment(sid, year, year_group, status="Enrolled", tutor=None):
    """Drift is data written outside the rules, so it is set up raw."""
    en.init_db()
    start = en.academic_year_dates(year)[0]
    with en._connect() as conn:
        cur = conn.execute(
            "INSERT INTO enrolments (student_id, academic_year, year_group, "
            "tutor_group, start_date, status) VALUES (?, ?, ?, ?, ?, ?)",
            (sid, year, year_group, tutor, start, status))
        conn.commit()
        return cur.lastrowid


def _set_status_raw(sid, status):
    with students._connect() as conn:
        conn.execute("UPDATE students SET status = ? WHERE student_id = ?",
                     (status, sid))
        conn.commit()


def _kinds(issues, sid):
    return sorted(i.kind for i in issues if i.student_id == sid)


def test_left_student_with_live_enrolments_is_found_and_closed(staff):
    sid = _student()
    _raw_enrolment(sid, en.current_academic_year(), 12)
    _set_status_raw(sid, "Left")
    found = [i for i in reconcile.check() if i.student_id == sid]
    assert [i.kind for i in found] == [reconcile.LEFT_WITH_LIVE]
    assert found[0].fixable

    lines = reconcile.fix(kinds=[reconcile.LEFT_WITH_LIVE])
    assert any("Enrolment withdrawn" in line for line in lines)
    assert not [e for e in en.list_for_student(sid) if e.is_live]
    assert la.active_aims(sid) == []
    assert _kinds(reconcile.check(), sid) == []


def test_two_live_years_completes_the_earlier_year(staff):
    sid = _student()
    first = _raw_enrolment(sid, PAST, 12)
    _raw_enrolment(sid, YEAR, 13)
    issues = [i for i in reconcile.check() if i.student_id == sid]
    assert [i.kind for i in issues] == [reconcile.TWO_LIVE_YEARS]
    assert issues[0].enrolment_id == first

    reconcile.fix([issues[0].issue_id])
    assert en.get_enrolment(first).status == "Completed"
    assert _kinds(reconcile.check(), sid) == []


def test_a_future_later_year_is_left_for_a_person(staff):
    sid = _student()
    current = en.current_academic_year()
    _raw_enrolment(sid, current, 12)
    _raw_enrolment(sid, en.next_academic_year(current), 13)
    issue = next(i for i in reconcile.check() if i.student_id == sid)
    assert issue.kind == reconcile.TWO_LIVE_YEARS
    assert not issue.fixable
    lines = reconcile.fix(kinds=[reconcile.TWO_LIVE_YEARS])
    assert any("skipped" in line for line in lines)
    assert all(e.status == "Enrolled" for e in en.list_for_student(sid))


def test_active_aims_without_a_live_enrolment(staff):
    sid = _student()
    _raw_enrolment(sid, PAST, 12, status="Withdrawn")
    issues = [i for i in reconcile.check() if i.student_id == sid]
    assert {i.kind for i in issues} == {reconcile.AIM_WITHOUT_ENROLMENT}
    assert len(issues) == len(la.active_aims(sid)) == 3

    reconcile.fix(kinds=[reconcile.AIM_WITHOUT_ENROLMENT])
    assert la.active_aims(sid) == []
    assert all(a.status == "Withdrawn" for a in la.list_aims(sid))


def test_tutor_group_text_and_membership_are_synced(staff):
    sid = _student()
    a = tg.create_group({"name": "12A", "year_group": 12})
    b = tg.create_group({"name": "12B", "year_group": 12})
    _raw_enrolment(sid, en.current_academic_year(), 12, tutor="12A")
    tg.assign_student(sid, b.tutor_group_id)
    issue = next(i for i in reconcile.check() if i.student_id == sid)
    assert issue.kind == reconcile.TUTOR_GROUP_MISMATCH

    reconcile.fix([issue.issue_id])
    assert tg.group_for_student(sid).tutor_group_id == a.tutor_group_id


def test_unknown_tutor_group_is_report_only(staff):
    sid = _student()
    tg.create_group({"name": "12A", "year_group": 12})
    _raw_enrolment(sid, en.current_academic_year(), 12, tutor="12Z")
    issue = next(i for i in reconcile.check() if i.student_id == sid)
    assert issue.kind == reconcile.TUTOR_GROUP_MISMATCH
    assert not issue.fixable


def test_fix_needs_an_enrolment_writer(staff, sign_in, monkeypatch):
    sid = _student()
    _raw_enrolment(sid, YEAR, 12)
    _set_status_raw(sid, "Left")
    sign_in("t1", capabilities={access.STUDENTS_VIEW})
    assert reconcile.check()          # reading is open
    with pytest.raises(access.AccessDenied):
        reconcile.fix(kinds=[reconcile.LEFT_WITH_LIVE])
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)
    with pytest.raises(access.AccessDenied):
        reconcile.fix(kinds=[reconcile.LEFT_WITH_LIVE])
