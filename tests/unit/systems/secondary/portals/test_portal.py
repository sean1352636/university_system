"""Pupil/parent portal reads (domain.portal), hand-in and staff My Day."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.secondary import SYSTEM_KEY
from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import homework as HW
from education_system.systems.secondary.modules.curriculum.domain import options as OPT
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.portals.domain import my_day as MD
from education_system.systems.secondary.modules.portals.domain import portal as PT
from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
from education_system.systems.secondary.modules.pupils.domain import pupil_accounts as PAC
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="pt_teach", role="teacher")
MUM = Principal(username="mum.portal", role="parent")
TODAY = dt.date.today()


@pytest.fixture
def env(tmp_path):
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    UserAuth(db_path=str(tmp_path / "auth.db")).provision_user(
        "pt_teach", "Teach!ng-Pass-123", display_name="Ms Maths", email="maths@school.org",
        systems=[(SYSTEM_KEY, "teacher")])
    ava, ben = (P.create_pupil({
        "legal_first_name": n, "legal_last_name": "Portal", "date_of_birth": "2013-01-15",
        "gender": "Female", "year_group": 9, "admission_date": "2023-09-01"}, actor=ADMIN)
        for n in ("Ava", "Ben"))
    acct = PAC.create_for_pupil(ava.pupil_id, actor=ADMIN, send_welcome=False)
    C.add_contact(ava.pupil_id, {"full_name": "Mum Portal", "relationship": "Mother",
                                 "email": "mum@home.org"}, actor=ADMIN)
    maths = S.create({"code": "MATH", "name": "Maths", "is_core": True}, actor=ADMIN)
    g = TG.create({"code": "9x/Ma1", "subject_id": maths.subject_id, "year_group": 9,
                   "teacher_username": "pt_teach"}, actor=ADMIN)
    TG.add_pupils([ava.pupil_id, ben.pupil_id], g.group_id, actor=ADMIN)
    yield {"ava": ava, "ben": ben, "maths": maths, "group": g,
           "student": Principal(acct.account.username, "student")}
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _task(env):
    task, _ = HW.create({"title": "Fractions", "subject_id": env["maths"].subject_id,
                         "group_id": env["group"].group_id, "set_date": TODAY.isoformat(),
                         "due_date": (TODAY + dt.timedelta(days=3)).isoformat(),
                         "instructions": "Do page 4", "est_minutes": 30}, actor=TEACHER)
    HW.set_task(task.task_id, actor=TEACHER)
    return task


def test_each_login_sees_only_its_own_pupil(env):
    stu = env["student"]
    assert [p.pupil_id for p in PT.pupils(stu)] == [env["ava"].pupil_id]
    assert [p.pupil_id for p in PT.pupils(MUM)] == [env["ava"].pupil_id]
    for who in (stu, MUM):
        with pytest.raises(PA.PermissionDenied):
            PT.home(who, env["ben"].pupil_id)
        with pytest.raises(PA.PermissionDenied):
            PT.grades(who, env["ben"].pupil_id)


def test_every_section_reads_and_contacts_only_for_parents(env):
    funcs = {"Home": PT.home, "Timetable": PT.timetable, "Homework": PT.homework,
             "Attendance": PT.attendance, "Behaviour": PT.behaviour, "Grades": PT.grades,
             "Reports": PT.reports,
             "Exams": PT.exams, "Library": PT.library, "Clubs": PT.clubs,
             "Options": PT.options, "Sixth Form": PT.sixth_form,
             "Calendar": PT.calendar, "My details": PT.details}
    assert set(funcs) == set(PT.SECTIONS)
    for who in (env["student"], MUM):
        for fn in funcs.values():
            fn(who, env["ava"].pupil_id)
    assert "contacts" in PT.details(MUM, env["ava"].pupil_id)
    assert "contacts" not in PT.details(env["student"], env["ava"].pupil_id)


def test_hand_in_rules(env):
    task = _task(env)
    stu = env["student"]
    assert [t.title for t, _ in PT.homework(stu, env["ava"].pupil_id)["due"]] == ["Fractions"]
    work = HW.hand_in(task.task_id, actor=stu, note="done it")
    assert work.status == "Submitted" and "done it" in (work.feedback or "")
    with pytest.raises(HW.ValidationError):  # already handed in
        HW.hand_in(task.task_id, actor=stu)
    with pytest.raises((HW.PermissionDenied, HW.ValidationError)):
        HW.hand_in(task.task_id, actor=MUM)
    with pytest.raises((HW.PermissionDenied, HW.ValidationError)):
        HW.hand_in(task.task_id, actor=TEACHER)
    assert [(t.title, n) for t, n in HW.to_mark(TEACHER)] == [("Fractions", 1)]


def test_reports_hide_unreleased_mocks(env):
    ava = env["ava"]
    TGR.upsert({"pupil_id": ava.pupil_id, "subject_id": env["maths"].subject_id,
                "target_grade": "6"}, actor=ADMIN)
    s = MX.create_series({"name": "Y9 mocks", "year_group": 9,
                          "start_date": (TODAY - dt.timedelta(days=10)).isoformat(),
                          "end_date": (TODAY - dt.timedelta(days=5)).isoformat()}, actor=ADMIN)
    p = MX.create_paper({"series_id": s.series_id, "subject_id": env["maths"].subject_id,
                         "paper_name": "P1", "paper_date": (TODAY - dt.timedelta(days=8)).isoformat(),
                         "max_marks": 80, "tier": "N/A",
                         "grade_boundaries": "9=72, 8=64, 7=56, 6=46, 5=36, 4=26, 3=18, 2=10, 1=5"},
                        actor=ADMIN)
    MX.set_series_status(s.series_id, "InProgress", actor=ADMIN)
    MX.save_sheet(p.paper_id, {ava.pupil_id: {"marks_awarded": "60"},
                                  env["ben"].pupil_id: {"absent": "Y"}}, actor=ADMIN)
    MX.set_series_status(s.series_id, "Complete", actor=ADMIN)
    r = PT.reports(env["student"], ava.pupil_id)
    assert not r["mocks"] and all(x["current"] is None for x in r["targets"])
    MX.release_results(s.series_id, actor=ADMIN)
    r = PT.reports(env["student"], ava.pupil_id)
    assert [x["grade"] for x in r["mocks"]["subjects"]] == ["7"]
    assert [x["current"] for x in r["targets"]] == ["7"]


def test_parent_chooses_options_for_own_child_only(env):
    rnd = OPT.create_round({"name": "Y9 options", "year_group": 9, "choices_required": 2,
                            "reserves_required": 0,
                            "closes_on": (TODAY + dt.timedelta(days=10)).isoformat()}, actor=ADMIN)
    subs = [S.create({"code": c, "name": n}, actor=ADMIN)
            for c, n in (("ART", "Art"), ("GEO", "Geography"))]
    for s in subs:
        OPT.add_round_subject(rnd.round_id, s.subject_id, actor=ADMIN)
    OPT.set_status(rnd.round_id, "Open", actor=ADMIN)
    ids = [s.subject_id for s in subs]
    assert PT.options(MUM, env["ava"].pupil_id)[0]["can_choose"]
    assert PT.submit_options(MUM, env["ava"].pupil_id, rnd.round_id, ids, []).submitted_by
    with pytest.raises(PA.PermissionDenied):
        PT.submit_options(MUM, env["ben"].pupil_id, rnd.round_id, ids, [])
    with pytest.raises(PA.PermissionDenied):
        OPT.submit_choices(rnd.round_id, env["ben"].pupil_id, ids, actor=MUM)


def test_my_day(env):
    TT.set_periods([{"period": 1, "label": "P1", "start_time": "08:50", "end_time": "09:50"}],
                   actor=ADMIN)
    _task(env)
    FG.create({"name": "9A", "year_group": 9, "tutor_name": "Ms Maths",
               "tutor_email": "maths@school.org"}, actor=ADMIN)
    PA.link_login("pt_teach", env["ben"].pupil_id, "parent", actor=ADMIN)
    d = MD.day(TEACHER)
    assert [f.name for f in d["forms"]] == ["9A"]
    assert [t.title for t in d["homework_set"]] == ["Fractions"]
    assert [p.display_name for p in d["children"]] == ["Ben Portal"]
    assert set(d["marking"]) >= {"homework", "gradebook", "points", "mocks"}
