"""Enrolment lifecycle rules (2026-10-27): status moves only through the
proper actions, withdrawal and the student record stay in step both
ways, reinstatement reopens the aims a withdrawal ended, rollover
completes Year 12 and can be undone, transfers are one step, and the
withdrawal detail is hidden from readers who don't manage enrolments."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.qualifications import (
    learning_aims,
)
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
NEXT = "2026/27"


@pytest.fixture
def staff(admdb, sign_in):
    return sign_in("enr1", capabilities={access.STUDENTS_MANAGE})


def _student(first="Ava", **over):
    data = {"first_name": first, "last_name": "Rules",
            "date_of_birth": "2009-05-06", "status": "Active",
            "personal_email": f"{first.lower()}@example.com", **over}
    return students.create_student(data, allow_duplicate=True).student_id


def _enrol(sid, year_group=12, year=YEAR, start="2025-09-03", **over):
    return en.create_enrolment({"student_id": sid, "academic_year": year,
                                "year_group": year_group,
                                "start_date": start, **over})


def _aim(sid, subject="Applied Science", start="2025-09-03", end="2027-06-30",
         qtype="BTEC Extended Certificate"):
    # Not an A level: those are checked against the subject catalogue,
    # which these tests don't set up.
    return learning_aims.add_aim(sid, {
        "qualification_type": qtype, "subject": subject,
        "start_date": start, "planned_end_date": end})


def _payload(e, **over):
    return {"academic_year": e.academic_year, "year_group": e.year_group,
            "tutor_group": e.tutor_group, "start_date": e.start_date,
            "status": e.status, "notes": e.notes, **over}


# ── Validation ──────────────────────────────────────────────────────

def test_create_checks_year_dates_roll_and_order(staff):
    sid = _student()
    with pytest.raises(en.ValidationError, match="look like"):
        _enrol(sid, year="2025/27")
    with pytest.raises(en.ValidationError, match="outside"):
        _enrol(sid, start="2026-09-01")
    with pytest.raises(en.ValidationError, match="can't start as"):
        _enrol(sid, status="Withdrawn")
    _enrol(sid, year_group=13, year=NEXT, start="2026-09-02")
    with pytest.raises(en.ValidationError, match="after their Year 13"):
        _enrol(sid, year_group=12, year="2027/28", start="2027-09-02")
    gone = _student("Bo")
    students._set_status_row(gone, "Left")
    with pytest.raises(en.ValidationError, match="not on roll"):
        _enrol(gone)


def test_recorded_by_is_the_signed_in_user(staff):
    e = _enrol(_student(), recorded_by="someone-else")
    assert e.recorded_by == "enr1"


def test_status_moves_go_through_the_proper_actions(staff):
    e = _enrol(_student())
    assert en.allowed_statuses(e) == ("Enrolled", "Pending")
    with pytest.raises(en.ValidationError, match="use Withdraw"):
        en.update_enrolment(e.enrolment_id, _payload(e, status="Withdrawn"))
    with pytest.raises(en.ValidationError, match="Can't change"):
        en.update_enrolment(e.enrolment_id, _payload(e, status="Completed"))
    pending = en.update_enrolment(e.enrolment_id, _payload(e, status="Pending"))
    assert pending.status == "Pending"


def test_tutor_group_must_be_real_once_groups_exist(staff):
    from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
        tutor_groups,
    )
    sid = _student()
    e = _enrol(sid, tutor_group="Anything")     # no groups yet: free text
    tutor_groups.create_group({"name": "12A", "year_group": 12})
    tutor_groups.create_group({"name": "13A", "year_group": 13})
    with pytest.raises(en.ValidationError, match="no tutor group"):
        en.update_enrolment(e.enrolment_id, _payload(e, tutor_group="12Z"))
    with pytest.raises(en.ValidationError, match="Year 13 group"):
        en.update_enrolment(e.enrolment_id, _payload(e, tutor_group="13A"))
    en.update_enrolment(e.enrolment_id, _payload(e, tutor_group="12A"))
    assert tutor_groups.group_for_student(sid).name == "12A"


# ── Withdraw ↔ student record ───────────────────────────────────────

def test_last_withdrawal_marks_student_left_and_reinstate_undoes_it(staff):
    sid = _student()
    e = _enrol(sid)
    aim = _aim(sid)
    res = en.withdraw_enrolment(e.enrolment_id, withdrawal_date="2025-11-01",
                                reason="44", detail="moved away")
    assert res.student_left
    assert students.get_student(sid).status == "Left"
    assert learning_aims.get_aim(aim.aim_id).status == "Withdrawn"

    back = en.reinstate_enrolment(e.enrolment_id, reason="came back")
    assert back.enrolment.status == "Enrolled"
    assert back.enrolment.withdrawal_date is None
    assert back.student_reinstated
    assert students.get_student(sid).status in students.ON_ROLL_STATUSES
    assert learning_aims.get_aim(aim.aim_id).status == "Active"
    actions = [h["action"] for h in en.enrolment_history(
        enrolment_id=e.enrolment_id)]
    assert actions[:2] == ["Reinstated", "Withdrawn"]


def test_withdrawing_one_year_keeps_aims_of_a_later_live_year(staff):
    sid = _student()
    y12 = _enrol(sid)
    _enrol(sid, year_group=13, year=NEXT, start="2026-09-02")
    two_year = _aim(sid)                       # runs into Year 13
    res = en.withdraw_enrolment(y12.enrolment_id, withdrawal_date="2026-06-01",
                                reason="97")
    assert not res.student_left and res.student_notes
    assert learning_aims.get_aim(two_year.aim_id).status == "Active"


def test_leaving_through_the_student_record_does_a_real_withdrawal(staff):
    sid = _student()
    e = _enrol(sid)
    aim = _aim(sid)
    students.withdraw_student(sid, reason="Moved area", leaving_date="2025-12-01",
                              withdrawal_reason="44")
    got = en.get_enrolment(e.enrolment_id)
    assert (got.status, got.withdrawal_reason, got.withdrawal_date) == \
        ("Withdrawn", "44", "2025-12-01")
    assert learning_aims.get_aim(aim.aim_id).status == "Withdrawn"


def test_year13_leaving_in_summer_term_completes(staff):
    sid = _student()
    e = _enrol(sid, year_group=13)
    students.withdraw_student(sid, reason="Finished", leaving_date="2026-06-20")
    assert en.get_enrolment(e.enrolment_id).status == "Completed"


def test_withdrawal_detail_hidden_from_readers_without_rights(staff, sign_in):
    e = _enrol(_student())
    en.withdraw_enrolment(e.enrolment_id, withdrawal_date="2025-10-10",
                          reason="3", detail="hospital stay",
                          update_student=False)
    assert en.get_enrolment(e.enrolment_id).withdrawal_detail == "hospital stay"
    sign_in("t1", capabilities={access.STUDENTS_VIEW})
    assert en.get_enrolment(e.enrolment_id).withdrawal_detail == en.RESTRICTED
    assert en.list_enrolments(student_id=e.student_id)[0].withdrawal_detail \
        == en.RESTRICTED


# ── Reopen, transfer ────────────────────────────────────────────────

def test_reopen_completed(staff):
    e = _enrol(_student(), year_group=13)
    done, _problems = en.complete_enrolment(e.enrolment_id)
    assert done.status == "Completed"
    with pytest.raises(en.ValidationError, match="reason"):
        en.reopen_enrolment(e.enrolment_id, reason=" ")
    assert en.reopen_enrolment(e.enrolment_id, reason="too early").status \
        == "Enrolled"


def test_transfer_moves_the_row_and_its_aims_in_one_step(staff):
    wrong, right = _student("Wes"), _student("Rae")
    e = _enrol(wrong)
    aim = _aim(wrong)
    out = en.transfer_enrolment(e.enrolment_id, right, reason="typed wrong id")
    assert out.enrolment.enrolment_id == e.enrolment_id
    assert out.enrolment.student_id == right and out.aims_moved == 1
    assert learning_aims.get_aim(aim.aim_id).student_id == right
    other = _enrol(_student("Ola"))
    with pytest.raises(en.ValidationError, match="already has"):
        en.transfer_enrolment(other.enrolment_id, right, reason="x")


# ── Rollover ────────────────────────────────────────────────────────

def test_rollover_intentions_one_year_programmes_and_undo(staff):
    up, stay, short, y13 = (_student(n) for n in ("Up", "Stay", "Short", "Thr"))
    e_up, e_stay, e_short = _enrol(up), _enrol(stay), _enrol(short)
    e13 = _enrol(y13, year_group=13)
    _aim(up)
    _aim(short, subject="Mathematics", qtype="GCSE", end="2026-06-30")
    en.set_return_intention(e_up.enrolment_id, "Returning")
    en.set_return_intention(e_stay.enrolment_id, "Not returning")
    assert en.reintention_summary(YEAR)["Returning"] == 1

    res = en.rollover(YEAR)
    assert res.run_id
    assert up in res.progressed
    assert short in res.completed and y13 in res.completed
    assert "not returning" in dict(res.skipped)[stay]
    assert en.get_enrolment(e_up.enrolment_id).status == "Completed"
    assert en.get_enrolment(e13.enrolment_id).status == "Completed"

    undo = en.undo_rollover(res.run_id)
    assert undo.reverted >= 3
    assert en.get_enrolment(e_up.enrolment_id).status == "Enrolled"
    assert en.list_enrolments(academic_year=NEXT, student_id=up) == []
    assert en.get_enrolment(e_short.enrolment_id).status == "Enrolled"
    with pytest.raises(en.ValidationError, match="already undone"):
        en.undo_rollover(res.run_id)

    again = en.rollover(YEAR)
    assert up in again.progressed and not again.failed
    assert len(en.list_enrolments(academic_year=NEXT, student_id=up)) == 1


def test_rollover_can_require_confirmation(staff):
    sid = _student()
    _enrol(sid)
    res = en.rollover(YEAR, require_intention=True, dry_run=True)
    assert "not confirmed" in dict(res.skipped)[sid]
