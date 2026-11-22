"""Enrolment writes are gated; delete archives (and restores the same
row); withdrawal records an ILR reason and ends the learning aims;
rollover skips learners who are not on roll."""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as en,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students,
)

YEAR = "2025/26"


@pytest.fixture
def staff(admdb, sign_in):
    return sign_in("enr1", capabilities={access.STUDENTS_MANAGE})


def _student(first="Ava", **over):
    data = {"first_name": first, "last_name": "Rollover",
            "date_of_birth": "2009-05-06", "status": "Active",
            "personal_email": f"{first.lower()}@example.com", **over}
    return students.create_student(data, allow_duplicate=True).student_id


def _enrol(sid, year_group=12, year=YEAR, **over):
    return en.create_enrolment({"student_id": sid, "academic_year": year,
                                "year_group": year_group, "tutor_group":
                                f"{year_group}A", "start_date": "2025-09-03",
                                **over})


def test_writes_need_admissions_or_students_manage(staff, sign_in):
    e = _enrol(_student())
    assert e.recorded_by == "enr1"
    sign_in("t1", capabilities={access.STUDENTS_VIEW})
    with pytest.raises(access.AccessDenied):
        en.update_enrolment(e.enrolment_id, {"academic_year": YEAR,
                                             "year_group": 13})
    with pytest.raises(access.AccessDenied):
        en.delete_enrolment(e.enrolment_id)
    # reads stay open
    assert en.get_enrolment(e.enrolment_id) is not None
    assert en.list_for_student(e.student_id)


def test_delete_archives_and_restore_brings_back_same_row(staff):
    sid = _student()
    e = _enrol(sid)
    assert en.delete_enrolment(e.enrolment_id, reason="typed in error")
    assert en.list_for_student(sid) == []
    assert en.current_enrolment(sid) is None
    archived = en.get_enrolment(e.enrolment_id)
    assert archived.is_archived and archived.archived_by == "enr1"
    assert [x.enrolment_id for x in en.list_enrolments(archived_only=True)] \
        == [e.enrolment_id]
    with pytest.raises(en.ValidationError, match="restore"):
        _enrol(sid)
    back = en.restore_enrolment(e.enrolment_id)
    assert back.enrolment_id == e.enrolment_id and not back.is_archived
    assert en.current_enrolment(sid).enrolment_id == e.enrolment_id


def test_withdrawal_records_reason_and_ends_aims(staff):
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims,
    )
    sid = _student(subject_1="Mathematics")
    e = _enrol(sid)
    before = learning_aims.active_aims(sid)
    day = _dt.date.today().isoformat()
    with pytest.raises(en.ValidationError, match="ILR"):
        en.withdraw_enrolment(e.enrolment_id, withdrawal_date=day,
                              reason="bored")
    res = en.withdraw_enrolment(e.enrolment_id, withdrawal_date=day,
                                reason="44", detail="moved away")
    assert res.enrolment.status == "Withdrawn"
    assert res.enrolment.withdrawal_date == day
    assert res.enrolment.withdrawal_reason_label == "44 — Other personal reasons"
    assert len(res.aims_ended) + len(res.aim_problems) == len(before)
    assert learning_aims.active_aims(sid) == [
        a for a in learning_aims.active_aims(sid) if a.start_date > day]
    with pytest.raises(en.ValidationError, match="already withdrawn"):
        en.withdraw_enrolment(e.enrolment_id, withdrawal_date=day, reason="44")


def test_rollover_skips_learners_not_on_roll(staff):
    keep = _student("Bea")
    left = _student("Cal")
    gone = _student("Dee")
    leaver = _student("Eve")
    _enrol(keep)
    _enrol(left)
    w = _enrol(gone)
    _enrol(leaver, year_group=13)
    # Status row only: withdraw_student would also withdraw the enrolment.
    students._set_status_row(left, "Left")
    en.withdraw_enrolment(w.enrolment_id, withdrawal_date="2025-10-01",
                          reason="2")
    dry = en.rollover(YEAR, dry_run=True)
    assert en.list_enrolments(academic_year="2026/27") == []
    res = en.rollover(YEAR)
    assert res.to_year == "2026/27"
    assert keep in res.progressed and leaver in res.completed
    skipped = dict(res.skipped)
    assert "withdrawn" in skipped[gone]
    assert "not on roll" in skipped[left]
    assert gone not in res.progressed
    assert dry.progressed == res.progressed
    new = en.list_enrolments(academic_year="2026/27", student_id=keep)[0]
    assert (new.year_group, new.tutor_group) == (13, "13A")
    # the Year 12 row is completed once they move up, so a second run
    # leaves them alone
    old = en.list_enrolments(academic_year=YEAR, student_id=keep)[0]
    assert old.status == "Completed"
    again = en.rollover(YEAR)
    assert keep not in again.progressed and not again.failed
