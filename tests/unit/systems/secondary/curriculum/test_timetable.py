"""Timetable rules (domain.timetable) on a scratch school DB.

auth.db and the activity log are redirected, so nothing touches live data.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="t1", role="teacher")


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(year=8):
    global _n
    _n += 1
    return P.create_pupil({"legal_first_name": f"P{_n}", "legal_last_name": f"T{_n:03d}",
                           "date_of_birth": f"{2026 - year - 4}-01-15", "gender": "Female",
                           "year_group": year, "admission_date": "2025-09-01"}, actor=ADMIN)


@pytest.fixture
def setup():
    m = S.create({"code": "MATH", "name": "Mathematics"}, actor=ADMIN)
    e = S.create({"code": "ENG", "name": "English"}, actor=ADMIN)
    S.set_lessons(m.subject_id, {8: 3}, actor=ADMIN)
    ma = TG.create({"code": "8/Ma1", "subject_id": m.subject_id, "year_group": 8,
                    "teacher_name": "Mr Ahmed", "room": "M1"}, actor=ADMIN)
    en = TG.create({"code": "8/En1", "subject_id": e.subject_id, "year_group": 8,
                    "teacher_name": "Ms Lee", "room": "E1"}, actor=ADMIN)
    return {"math": m, "eng": e, "ma": ma, "en": en}


def _lesson(group, day="Mon", period=1, **extra):
    return TT.add_lesson({"group_id": group.group_id, "day": day, "period": period, **extra},
                         actor=ADMIN)


# ── Settings ─────────────────────────────────────────────────────────

def test_default_periods_and_saving_new_ones():
    assert [p.label for p in TT.periods()] == ["P1", "P2", "P3", "P4", "P5"]
    TT.set_periods([{"label": "Reg", "start_time": "08:40", "end_time": "09:00"},
                    {"label": "", "start_time": "09:00", "end_time": "10:00"}], actor=ADMIN)
    assert [(p.period, p.label, p.times) for p in TT.periods()] == [
        (1, "Reg", "08:40–09:00"), (2, "P2", "09:00–10:00")]


@pytest.mark.parametrize("rows, msg", [
    ([], "at least one"), ([{"start_time": "9:00", "end_time": "10:00"}], "HH:MM"),
    ([{"start_time": "10:00", "end_time": "09:00"}], "end after"),
    ([{"start_time": "09:00", "end_time": "10:00"},
      {"start_time": "09:30", "end_time": "10:30"}], "before period 1 ends"),
    ([{"start_time": "08:00", "end_time": "08:30"}] * 11, "At most 10"),
])
def test_bad_periods_refused(rows, msg):
    with pytest.raises(TT.ValidationError, match=msg):
        TT.set_periods(rows, actor=ADMIN)


def test_cannot_drop_a_period_with_lessons(setup):
    _lesson(setup["ma"], period=5)
    with pytest.raises(TT.ValidationError, match="Period 5 has lessons"):
        TT.set_periods([{"start_time": "09:00", "end_time": "10:00"}], actor=ADMIN)


def test_cycle_and_week_for(setup):
    assert TT.cycle_weeks() == 1 and TT.week_for(dt.date(2026, 9, 14)) == 1
    TT.set_cycle(2, "year", actor=ADMIN)
    # 1 Sep 2026 is a Tuesday: that week is A, the next B, then A again.
    assert [TT.week_for(dt.date(2026, 9, d)) for d in (1, 4, 7, 14, 21)] == [1, 1, 2, 1, 2]
    _lesson(setup["ma"], week="B")
    with pytest.raises(TT.ValidationError, match="Week B"):
        TT.set_cycle(1, actor=ADMIN)
    with pytest.raises(TT.ValidationError):
        TT.set_cycle(3, actor=ADMIN)


def test_week_restarts_each_term():
    y = AY.create_year("2026/27", actor=ADMIN)
    AY.add_term(y.year_id, {"name": "Autumn 1", "start_date": "2026-09-03",
                            "end_date": "2026-10-23"}, actor=ADMIN)
    AY.add_term(y.year_id, {"name": "Autumn 2", "start_date": "2026-11-02",
                            "end_date": "2026-12-18"}, actor=ADMIN)
    TT.set_cycle(2, "term", actor=ADMIN)
    assert TT.week_for(dt.date(2026, 11, 2)) == 1  # first week of Autumn 2 is A again
    assert TT.week_for(dt.date(2026, 11, 9)) == 2


# ── Lessons ──────────────────────────────────────────────────────────

def test_add_lesson_takes_teacher_and_room_from_group(setup):
    x = _lesson(setup["ma"], day="tue", period="2")
    assert (x.day, x.period, x.week) == (2, 2, 1)
    assert (x.teacher, x.room, x.subject_code) == ("Mr Ahmed", "M1", "MATH")
    assert x.slot_label == "Tuesday P2" and "8/Ma1" in x.cell
    y = _lesson(setup["ma"], day=3, period=1, room="Lab 2", teacher_name="Dr Cole")
    assert (y.teacher, y.room) == ("Dr Cole", "Lab 2")


@pytest.mark.parametrize("extra, msg", [
    ({"day": "Sat"}, "Day"), ({"period": 6}, "Period"), ({"week": "B"}, "Week"),
    ({"group_id": 9999}, "teaching group"), ({"teacher_username": "ghost"}, "staff login"),
])
def test_bad_lessons_refused(setup, extra, msg):
    data = {"group_id": setup["ma"].group_id, "day": "Mon", "period": 1, **extra}
    with pytest.raises(TT.ValidationError, match=msg):
        TT.add_lesson(data, actor=ADMIN)


def test_teacher_can_view_but_not_change(setup):
    x = _lesson(setup["ma"])
    for call in (lambda: TT.add_lesson({"group_id": setup["en"].group_id, "day": 2,
                                        "period": 1}, actor=TEACHER),
                 lambda: TT.update_lesson(x.lesson_id, {"room": "A"}, actor=TEACHER),
                 lambda: TT.delete_lesson(x.lesson_id, actor=TEACHER),
                 lambda: TT.set_periods([{"start_time": "09:00", "end_time": "10:00"}],
                                        actor=TEACHER),
                 lambda: TT.set_cycle(2, actor=TEACHER)):
        with pytest.raises(TT.PermissionDenied):
            call()
    assert len(TT.list_lessons()) == 1


# ── Clashes ──────────────────────────────────────────────────────────

def test_same_group_twice_in_a_slot_is_always_refused(setup):
    _lesson(setup["ma"])
    with pytest.raises(TT.ValidationError, match="already has a lesson"):
        TT.add_lesson({"group_id": setup["ma"].group_id, "day": 1, "period": 1},
                      actor=ADMIN, allow_clash=True)


def test_teacher_room_and_pupil_clashes(setup):
    _lesson(setup["ma"])
    TG.update(setup["en"].group_id, {"teacher_name": "mr ahmed"}, actor=ADMIN)
    assert TT.check({"group_id": setup["en"].group_id, "day": 1, "period": 1}) == [
        "mr ahmed is teaching 8/Ma1 then"]
    found = TT.check({"group_id": setup["en"].group_id, "day": 1, "period": 1,
                      "teacher_name": "Ms Lee", "room": "m1"})
    assert found == ["Room m1 is used by 8/Ma1 then"]
    p = _pupil(8)
    TG.add_pupils([p.pupil_id], setup["ma"].group_id, actor=ADMIN)
    TG.add_pupils([p.pupil_id], setup["en"].group_id, actor=ADMIN)
    found = TT.check({"group_id": setup["en"].group_id, "day": 1, "period": 1,
                      "teacher_name": "Ms Lee"})
    assert found == ["1 pupil(s) in 8/En1 are also in 8/Ma1"]
    with pytest.raises(TT.ValidationError, match="also in"):
        TT.add_lesson({"group_id": setup["en"].group_id, "day": 1, "period": 1,
                       "teacher_name": "Ms Lee"}, actor=ADMIN)
    TT.add_lesson({"group_id": setup["en"].group_id, "day": 1, "period": 1,
                   "teacher_name": "Ms Lee"}, actor=ADMIN, allow_clash=True)
    (a, b, why), = TT.clashes()
    assert {a.group_code, b.group_code} == {"8/Ma1", "8/En1"} and "also in" in why[0]


def test_clash_appears_when_pupils_move_later(setup):
    _lesson(setup["ma"])
    _lesson(setup["en"])  # different teacher and room: fine
    assert TT.clashes() == []
    p = _pupil(8)
    TG.add_pupils([p.pupil_id], setup["ma"].group_id, actor=ADMIN)
    TG.add_pupils([p.pupil_id], setup["en"].group_id, actor=ADMIN)
    assert len(TT.clashes()) == 1


def test_update_and_delete(setup):
    x = _lesson(setup["ma"])
    y = TT.update_lesson(x.lesson_id, {"day": "Fri", "notes": "double"}, actor=ADMIN)
    assert (y.day, y.notes) == (5, "double")
    _lesson(setup["en"], day="Fri", period=2, teacher_name="Mr Ahmed")
    with pytest.raises(TT.ValidationError, match="is teaching"):
        TT.update_lesson(x.lesson_id, {"period": 2}, actor=ADMIN)
    TT.delete_lesson(x.lesson_id, actor=ADMIN)
    with pytest.raises(TT.NotFound):
        TT.get(x.lesson_id)


def test_copy_week(setup):
    with pytest.raises(TT.ValidationError, match="two-week"):
        TT.copy_week(actor=ADMIN)
    TT.set_cycle(2, actor=ADMIN)
    _lesson(setup["ma"])
    _lesson(setup["en"], day=2)
    _lesson(setup["en"], week="B", day=1, period=1, teacher_name="Mr Ahmed")  # blocks one
    n, notes = TT.copy_week(actor=ADMIN)
    assert n == 1 and len(notes) == 1 and "is teaching" in notes[0]
    assert len(TT.list_lessons(week=2)) == 2


# ── Views ────────────────────────────────────────────────────────────

def test_filters(setup):
    p = _pupil(8)
    p9 = _pupil(9)
    TG.add_pupils([p.pupil_id], setup["ma"].group_id, actor=ADMIN)
    P.update_pupil(p.pupil_id, {"form_group": "8K"}, actor=ADMIN)
    _lesson(setup["ma"])
    _lesson(setup["en"], day=2)
    assert len(TT.list_lessons(year_group=8)) == 2 and TT.list_lessons(year_group=9) == []
    assert [x.group_code for x in TT.list_lessons(pupil_id=p.pupil_id)] == ["8/Ma1"]
    assert [x.group_code for x in TT.list_lessons(form="8k")] == ["8/Ma1"]
    assert [x.group_code for x in TT.list_lessons(teacher="ms lee")] == ["8/En1"]
    assert [x.group_code for x in TT.list_lessons(room="M1")] == ["8/Ma1"]
    assert TT.list_lessons(pupil_id=p9.pupil_id) == []
    assert TT.teachers() == ["Mr Ahmed", "Ms Lee"] and TT.rooms() == ["E1", "M1"]


def test_archived_and_past_groups_leave_the_timetable(setup):
    x = _lesson(setup["ma"])
    TG.archive(setup["ma"].group_id, actor=ADMIN)
    assert TT.list_lessons() == []
    with pytest.raises(TT.ValidationError, match="archived"):
        TT.add_lesson({"group_id": setup["ma"].group_id, "day": 2, "period": 1}, actor=ADMIN)
    with database.connect() as conn:
        conn.execute("UPDATE teaching_groups SET academic_year = '2020/21', status = 'active' "
                     "WHERE group_id = ?", (setup["ma"].group_id,))
    with pytest.raises(TT.ValidationError, match="Past years"):
        TT.delete_lesson(x.lesson_id, actor=ADMIN)


def test_requirements(setup):
    TG.update(setup["en"].group_id, {"lessons_per_week": 2}, actor=ADMIN)
    _lesson(setup["ma"])
    _lesson(setup["en"])  # needs 2
    _lesson(setup["en"], day=2)
    by = {r.info.group.code: r for r in TT.requirements()}
    assert (by["8/Ma1"].needed, by["8/Ma1"].scheduled, by["8/Ma1"].status) == (3, 1, "short")
    assert by["8/En1"].status == "ok"
    TT.set_cycle(2, actor=ADMIN)
    assert {r.info.group.code: r.needed for r in TT.requirements()} == {"8/Ma1": 6, "8/En1": 4}


def test_lessons_on_uses_the_calendar(setup):
    _lesson(setup["ma"], day="Mon")
    monday = dt.date(2026, 11, 2)
    lessons, what = TT.lessons_on(monday)  # no calendar recorded: weekdays work
    assert [x.group_code for x in lessons] == ["8/Ma1"] and "No academic calendar" in what
    assert TT.lessons_on(dt.date(2026, 11, 7)) == ([], "Weekend")
    y = AY.create_year("2026/27", actor=ADMIN)
    AY.add_term(y.year_id, {"name": "Autumn 2", "start_date": "2026-11-02",
                            "end_date": "2026-12-18"}, actor=ADMIN)
    AY.add_break(y.year_id, {"name": "INSET", "type": "INSET", "start_date": "2026-11-02"},
                 actor=ADMIN)
    lessons, what = TT.lessons_on(monday)
    assert lessons == [] and "INSET" in what
    lessons, _ = TT.lessons_on(dt.date(2026, 11, 9))
    assert [x.group_code for x in lessons] == ["8/Ma1"]
