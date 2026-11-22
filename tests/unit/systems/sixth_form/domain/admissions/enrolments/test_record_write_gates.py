"""Student records, learning aims, tutor groups, class lists, prior
attainment, study programme hours and onboarding refuse writes from
nobody signed in and from staff without the capability; reads stay open;
work with nobody signed in runs as a named system actor."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_membership as cgm,
)
from education_system.systems.sixth_form.domain.academics.qualifications import (
    learning_aims as la,
    prior_attainment as pa,
    study_programme as sp,
)
from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as en,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as ob,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students,
    transfers,
)
from education_system.systems.sixth_form.domain.learners.students.system_actor import (
    unless_signed_in,
)
from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
    tutor_groups as tg,
)

DATA = {"first_name": "Gale", "last_name": "Gate", "date_of_birth": "2009-02-03",
        "subject_1": "Mathematics", "subject_2": "Physics",
        "subject_3": "Chemistry"}


@pytest.fixture
def manager(admdb, sign_in):
    return sign_in("mgr1", capabilities={access.STUDENTS_MANAGE})


@pytest.fixture
def sid(manager):
    return students.create_student(DATA).student_id


def _anonymous(monkeypatch):
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)


def test_nobody_signed_in_is_refused_everywhere(sid, monkeypatch):
    _anonymous(monkeypatch)
    calls = [
        lambda: students.create_student(DATA, allow_duplicate=True),
        lambda: students.update_student(sid, {"phone": "01234 567890"}),
        lambda: students.set_identifiers(sid, candidate_number="1234"),
        lambda: students.withdraw_student(sid, reason="Moved away"),
        lambda: students.delete_student(sid),
        lambda: transfers.mark_transferred(sid),
        lambda: la.add_aim(sid, {"qualification_type": "A Level",
                                 "subject": "Biology",
                                 "start_date": "2025-09-03"}),
        lambda: tg.create_group({"name": "12A", "year_group": 12}),
        lambda: tg.unassign_student(sid),
        lambda: cgm.add_members_bulk(1, [sid]),
        lambda: pa.add_result(sid, {"subject": "English Language",
                                    "grade": "5"}),
        lambda: sp.set_non_qual_hours(sid, "2025/26",
                                      sp.NON_QUAL_CATEGORIES[0], 10),
        lambda: ob.create_checklist({"student_id": sid}),
    ]
    for call in calls:
        with pytest.raises(access.AccessDenied):
            call()
    # reads stay open
    assert students.get_student(sid) is not None
    assert la.active_aims(sid)


def test_a_teacher_may_change_class_lists_but_not_records(sid, sign_in):
    aim = la.active_aims(sid)[0]
    sign_in("t1", capabilities={access.STUDENTS_VIEW, access.TEACHING})
    with pytest.raises(access.AccessDenied):
        students.update_student(sid, {"phone": "01234 567890"})
    with pytest.raises(access.AccessDenied):
        la.withdraw_aim(aim.aim_id, effective_date=aim.start_date,
                        reason="Dropped", approved_by="HoD")
    with pytest.raises(access.AccessDenied):
        tg.create_group({"name": "12A", "year_group": 12})
    # the class-list gate lets a teacher through (the group then doesn't exist)
    with pytest.raises(cgm.ValidationError):
        cgm.add_members_bulk(987654, [sid])


def test_pastoral_staff_run_tutor_groups(sid, manager, sign_in):
    sign_in("hoy", capabilities={access.PASTORAL})
    g = tg.create_group({"name": "12A", "year_group": 12})
    tg.assign_student(sid, g.tutor_group_id)
    assert tg.group_for_student(sid).name == "12A"
    with pytest.raises(access.AccessDenied):
        students.create_student(DATA, allow_duplicate=True)


def test_admissions_may_change_status_but_not_create(sid, sign_in):
    sign_in("adm", capabilities={access.ADMISSIONS})
    with pytest.raises(access.AccessDenied):
        students.create_student(DATA, allow_duplicate=True)
    assert students.set_status(sid, "Inactive").status == "Inactive"


def test_system_actor_runs_without_a_person(admdb, monkeypatch):
    _anonymous(monkeypatch)
    with _guard.system_actor("test-intake", (access.STUDENTS_MANAGE,)):
        st = students.create_student(DATA, allow_duplicate=True)
    assert st.student_id
    with unless_signed_in("test-adapter"):
        students.update_student(st.student_id, {"phone": "07700 900123"})
    assert access.current() is access.ANONYMOUS


def test_unless_signed_in_never_widens_a_signed_in_user(sid, sign_in):
    sign_in("t1", capabilities={access.STUDENTS_VIEW})
    with unless_signed_in("test-adapter"):
        with pytest.raises(access.AccessDenied):
            students.update_student(sid, {"phone": "07700 900123"})


def test_year_13_list_ignores_archived_and_old_rows(manager):
    year = en.current_academic_year()
    live = students.create_student({**DATA, "first_name": "Lia"},
                                   allow_duplicate=True).student_id
    gone = students.create_student({**DATA, "first_name": "Arc"},
                                   allow_duplicate=True).student_id
    first = en.academic_year_dates(year)[0]
    en.create_enrolment({"student_id": live, "academic_year": year,
                         "year_group": 13, "start_date": first})
    e = en.create_enrolment({"student_id": gone, "academic_year": year,
                             "year_group": 13, "start_date": first})
    en.archive_enrolment(e.enrolment_id, reason="entered in error")
    ids = {s.student_id for s in students.list_year_13_students()}
    assert live in ids and gone not in ids
