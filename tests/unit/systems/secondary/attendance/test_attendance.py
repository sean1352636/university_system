"""Registers and attendance rules (domain.attendance) on a scratch school DB.

"Today" is pinned to Wednesday 14 Oct 2026 so the today-only and no-future
rules don't depend on when the tests run. auth.db and the activity log are
redirected, so nothing touches live data.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

OFFICE = Principal(username="admin2", role="admin")
TEACHER = Principal(username="t1", role="teacher")
PUPIL = Principal(username="kid", role="student")
TODAY = dt.date(2026, 10, 14)          # a Wednesday
MON, TUE = dt.date(2026, 10, 12), dt.date(2026, 10, 13)
SAT = dt.date(2026, 10, 10)


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(AT, "_today", lambda: TODAY)
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(form="8K", admitted="2025-09-01", **extra):
    global _n
    _n += 1
    return P.create_pupil({"legal_first_name": f"P{_n}", "legal_last_name": f"T{_n:03d}",
                           "date_of_birth": "2014-01-15", "gender": "Female", "year_group": 8,
                           "form_group": form, "admission_date": admitted, **extra},
                          actor=OFFICE)


@pytest.fixture
def form():
    FG.create({"name": "8K", "year_group": 8}, actor=OFFICE)
    return [_pupil() for _ in range(3)]


# ── Codes ────────────────────────────────────────────────────────────

def test_codes_are_normalised():
    assert AT.clean_code("/", "PM") == "\\" and AT.clean_code("\\", "AM") == "/"
    assert AT.clean_code(" i ", "AM") == "I" and AT.clean_code("y1", "AM") == "Y1"
    with pytest.raises(AT.ValidationError, match="not an attendance code"):
        AT.clean_code("H", "AM")  # removed from the DfE list in 2024
    assert AT.category_of("V") == AT.AEA and AT.category_of("N") == AT.UNAUTHORISED


# ── Taking a register ────────────────────────────────────────────────

def test_teacher_takes_todays_register(form):
    a, b, c = form
    saved, notes = AT.save_register(TODAY, "AM", {a.pupil_id: "/", b.pupil_id: "n",
                                                  c.pupil_id: ("L", "bus", 10)}, actor=TEACHER)
    assert (saved, notes) == (3, [])
    rows = {r.pupil.pupil_id: r.mark for r in AT.register(TODAY, "AM", form="8k")}
    assert rows[b.pupil_id].code == "N" and rows[c.pupil_id].minutes_late == 10
    (st,) = AT.register_status(TODAY, "AM")
    assert (st.form_group, st.on_roll, st.marked, st.taken_by, st.complete) == (
        "8K", 3, 3, "t1", True)
    assert AT.register_status(TODAY, "PM")[0].complete is False
    day = AT.daily_summary(TODAY)["AM"]
    assert (day["present"], day["unauthorised"], day["unmarked"]) == (2, 1, 0)


def test_partial_register_is_not_taken(form):
    AT.save_register(TODAY, "AM", {form[0].pupil_id: "/"}, actor=TEACHER)
    (st,) = AT.register_status(TODAY, "AM")
    assert (st.marked, st.taken_by) == (1, None)


def test_teachers_only_mark_today_and_only_present_late_absent(form):
    a = form[0]
    with pytest.raises(AT.ValidationError, match="past register"):
        AT.save_register(TUE, "AM", {a.pupil_id: "/"}, actor=TEACHER)
    with pytest.raises(AT.ValidationError, match="Only the attendance office can enter 'I'"):
        AT.record_mark(a.pupil_id, TODAY, "AM", "I", actor=TEACHER)
    _, notes = AT.save_register(TODAY, "AM", {a.pupil_id: "I"}, actor=TEACHER)
    assert "only the office" in notes[0]
    with pytest.raises(AT.PermissionDenied):
        AT.record_mark(a.pupil_id, TODAY, "AM", "/", actor=PUPIL)


def test_teacher_never_overwrites_the_office_reason(form):
    a = form[0]
    AT.record_mark(a.pupil_id, TODAY, "AM", "M", actor=OFFICE, notes="dentist")
    saved, notes = AT.save_register(TODAY, "AM", {a.pupil_id: "N"}, actor=TEACHER)
    assert saved == 0 and "kept the office's 'M'" in notes[0]
    with pytest.raises(AT.ValidationError, match="already recorded 'M'"):
        AT.record_mark(a.pupil_id, TODAY, "AM", "/", actor=TEACHER)
    assert AT.get_for(a.pupil_id, TODAY, "AM").code == "M"


def test_amendments_keep_the_original(form):
    a = form[0]
    AT.record_mark(a.pupil_id, TODAY, "AM", "N", actor=TEACHER)
    AT.record_mark(a.pupil_id, TODAY, "AM", "I", actor=OFFICE)
    h = [(x["action"], x["old"], x["new"], x["actor"]) for x in AT.history(a.pupil_id)]
    assert h == [("change", "N", "I", "admin2"), ("mark", None, "N", "t1")]


@pytest.mark.parametrize("day, msg", [(SAT, "isn't a school day"),
                                      (dt.date(2026, 10, 15), "future")])
def test_no_marks_on_weekends_or_future(form, day, msg):
    with pytest.raises(AT.ValidationError, match=msg):
        AT.record_mark(form[0].pupil_id, day, "AM", "/", actor=OFFICE)


def test_calendar_decides_school_days(form):
    y = AY.create_year("2026/27", actor=OFFICE)
    AY.add_term(y.year_id, {"name": "Autumn 1", "start_date": "2026-09-03",
                            "end_date": "2026-10-23"}, actor=OFFICE)
    AY.add_break(y.year_id, {"name": "Training", "type": "INSET", "start_date": "2026-10-12"},
                 actor=OFFICE)
    with pytest.raises(AT.ValidationError, match="INSET"):
        AT.record_mark(form[0].pupil_id, MON, "AM", "/", actor=OFFICE)
    with pytest.raises(AT.ValidationError, match="between terms"):
        AT.record_mark(form[0].pupil_id, dt.date(2026, 9, 2), "AM", "/", actor=OFFICE)
    assert MON not in AT.school_days(dt.date(2026, 10, 5), TODAY)
    assert len(AT.school_days(dt.date(2026, 10, 5), TODAY)) == 7


def test_only_while_on_roll(form):
    late = _pupil(admitted="2026-10-13")
    with pytest.raises(AT.ValidationError, match="wasn't on roll"):
        AT.record_mark(late.pupil_id, MON, "AM", "/", actor=OFFICE)
    assert late.pupil_id not in {r.pupil.pupil_id for r in AT.register(MON, "AM")}
    assert late.pupil_id in {r.pupil.pupil_id for r in AT.register(TUE, "AM")}


# ── Lateness and longer absences ─────────────────────────────────────

def test_late_arrival_is_l_until_the_register_closes(form):
    a, b = form[0], form[1]
    m = AT.record_late(a.pupil_id, TODAY, "AM", "09:00", actor=TEACHER)
    assert (m.code, m.minutes_late) == ("L", 20)
    with pytest.raises(AT.ValidationError, match="records this as U"):
        AT.record_late(b.pupil_id, TODAY, "AM", "09:30", actor=TEACHER)
    m = AT.record_late(b.pupil_id, TODAY, "AM", "09:30", actor=OFFICE)
    assert (m.code, m.category, m.minutes_late) == ("U", AT.UNAUTHORISED, 50)


def test_absence_over_several_days(form):
    a = form[0]
    AT.record_mark(a.pupil_id, dt.date(2026, 10, 7), "AM", "/", actor=OFFICE)
    AT.record_mark(a.pupil_id, dt.date(2026, 10, 8), "AM", "N", actor=OFFICE)
    # Mon 5 - Sun 11 Oct: 5 school days x 2 sessions, the AM / on the 7th is kept.
    assert AT.record_range(a.pupil_id, "2026-10-05", "2026-10-11", "i",
                           actor=OFFICE) == (9, 1)
    assert AT.get_for(a.pupil_id, dt.date(2026, 10, 8), "AM").code == "I"
    assert AT.record_range(a.pupil_id, "2026-10-07", "2026-10-07", "C", actor=OFFICE,
                           sessions=["AM"], overwrite=True) == (1, 0)
    with pytest.raises(AT.PermissionDenied):
        AT.record_range(a.pupil_id, "2026-10-05", "2026-10-06", "I", actor=TEACHER)
    with pytest.raises(AT.ValidationError, match="future"):
        AT.record_range(a.pupil_id, "2026-10-14", "2026-10-20", "I", actor=OFFICE)


# ── Figures ──────────────────────────────────────────────────────────

def test_summary_counts_offsite_as_present_and_skips_not_counted(form):
    a = form[0]
    for day, am, pm in ((MON, "/", "V"), (TUE, "I", "O"), (TODAY, "Y2", "L")):
        AT.record_mark(a.pupil_id, day, "AM", am, actor=OFFICE)
        AT.record_mark(a.pupil_id, day, "PM", pm, actor=OFFICE)
    s = AT.pupil_summary(a.pupil_id, "2026-10-12", "2026-10-14")
    assert (s.possible, s.present, s.aea, s.authorised, s.unauthorised, s.not_counted,
            s.late, s.unmarked) == (5, 2, 1, 1, 1, 1, 1, 0)
    assert (s.attendance_pct, s.absence_pct, s.band) == (60.0, 40.0, "persistent")


def test_bands_and_report(form):
    good, poor = form[0], form[1]
    for day in (MON, TUE, TODAY):
        for s in AT.SESSIONS:
            AT.record_mark(good.pupil_id, day, s, "/", actor=OFFICE)
            AT.record_mark(poor.pupil_id, day, s, "G" if day != MON else "/", actor=OFFICE)
    rows = AT.summaries("2026-10-12", "2026-10-14")
    assert rows[0][0].pupil_id == poor.pupil_id and rows[0][1].band == "severe"
    assert rows[-1][1].attendance_pct is None and rows[-1][1].unmarked == 6
    assert [p.pupil_id for p, _s in AT.persistent_absentees("2026-10-12", "2026-10-14")] == [
        poor.pupil_id]


def test_export_escapes_formulas(form, tmp_path):
    P.update_pupil(form[0].pupil_id, {"legal_last_name": "=SUM(A1)"}, actor=OFFICE)
    AT.record_mark(form[0].pupil_id, TODAY, "AM", "/", actor=OFFICE)
    path = tmp_path / "a.csv"
    assert AT.export_summaries(path, AT.summaries("2026-10-14", "2026-10-14"),
                               actor=TEACHER) == 3
    rows = list(csv.reader(path.open(encoding="utf-8")))
    assert any(r[1] == "'=SUM(A1)" for r in rows[1:])


def test_calling_list(form):
    a = form[1]
    C.add_contact(a.pupil_id, {"full_name": "Dad", "relationship": "Father", "priority": 2,
                               "phone": "01234 567890"}, actor=OFFICE)
    C.add_contact(a.pupil_id, {"full_name": "Mum", "relationship": "Mother", "priority": 1,
                               "phone": "01234 567891"}, actor=OFFICE)
    AT.save_register(TODAY, "AM", {p.pupil_id: "N" if p is a else "/" for p in form},
                     actor=TEACHER)
    ((p, m, contacts),) = AT.calling_list(TODAY, "AM")
    assert p.pupil_id == a.pupil_id and m.code == "N"
    assert [c.full_name for c in contacts] == ["Mum", "Dad"]


# ── Deleting ─────────────────────────────────────────────────────────

def test_delete_mark_needs_office_and_reason(form):
    m = AT.record_mark(form[0].pupil_id, TODAY, "AM", "/", actor=TEACHER)
    with pytest.raises(AT.PermissionDenied):
        AT.delete_mark(m.mark_id, actor=TEACHER, reason="x")
    with pytest.raises(AT.ValidationError, match="reason"):
        AT.delete_mark(m.mark_id, actor=OFFICE, reason=" ")
    AT.delete_mark(m.mark_id, actor=OFFICE, reason="wrong pupil")
    assert AT.get_for(form[0].pupil_id, TODAY, "AM") is None
    assert AT.history(form[0].pupil_id)[0]["action"] == "delete"


def test_pupil_with_attendance_cannot_be_deleted(form):
    AT.record_mark(form[0].pupil_id, TODAY, "AM", "/", actor=OFFICE)
    with pytest.raises(P.ValidationError, match="mark them as left"):
        P.delete_pupil(form[0].pupil_id, actor=OFFICE, reason="test")
    assert P.get_pupil(form[0].pupil_id) is not None
    P.delete_pupil(form[1].pupil_id, actor=OFFICE, reason="entered in error")


# ── Lesson registers ─────────────────────────────────────────────────

@pytest.fixture
def lesson(form):
    m = S.create({"code": "MATH", "name": "Mathematics"}, actor=OFFICE)
    g = TG.create({"code": "8/Ma1", "subject_id": m.subject_id, "year_group": 8,
                   "teacher_name": "Mr Ahmed"}, actor=OFFICE)
    TG.add_pupils([p.pupil_id for p in form], g.group_id, actor=OFFICE)
    return TT.add_lesson({"group_id": g.group_id, "day": "Wed", "period": 2}, actor=OFFICE)


def test_lesson_register_suggests_from_the_session_register(form, lesson):
    a, b, c = form
    AT.save_register(TODAY, "AM", {a.pupil_id: "/", b.pupil_id: "N"}, actor=TEACHER)
    AT.record_mark(c.pupil_id, TODAY, "AM", "V", actor=OFFICE)
    reg = AT.lesson_register(lesson.lesson_id, TODAY)
    assert reg.session == "AM" and reg.taken_by is None
    assert {r.pupil.pupil_id: r.suggested for r in reg.rows} == {
        a.pupil_id: "P", b.pupil_id: "A", c.pupil_id: "X"}
    (x, taken), = AT.lessons_due(TODAY)[0]
    assert x.lesson_id == lesson.lesson_id and taken is False


def test_save_lesson_register_and_missing_from_lessons(form, lesson):
    a, b, c = form
    AT.save_register(TODAY, "AM", {a.pupil_id: "/", b.pupil_id: "/", c.pupil_id: "N"},
                     actor=TEACHER)
    n = AT.save_lesson_register(lesson.lesson_id, TODAY,
                                {a.pupil_id: "a", b.pupil_id: ("L", None, 5),
                                 c.pupil_id: "A"}, actor=TEACHER)
    assert n == 3
    reg = AT.lesson_register(lesson.lesson_id, TODAY)
    assert reg.taken_by == "t1" and {r.mark for r in reg.rows} == {"A", "L"}
    # a was present for AM but absent from the lesson; c was absent all morning.
    assert [(p.pupil_id, code) for p, _x, code in AT.missing_from_lessons(TODAY)] == [
        (a.pupil_id, "/")]
    assert AT.lessons_due(TODAY)[0][0][1] is True
    assert AT.lesson_summary(a.pupil_id)["A"] == 1


def test_lesson_register_rules(form, lesson):
    outsider = _pupil(form="8P")
    with pytest.raises(AT.ValidationError, match="isn't in 8/Ma1"):
        AT.save_lesson_register(lesson.lesson_id, TODAY, {outsider.pupil_id: "P"},
                                actor=TEACHER)
    with pytest.raises(AT.ValidationError, match="P, L, A or X"):
        AT.save_lesson_register(lesson.lesson_id, TODAY, {form[0].pupil_id: "Q"},
                                actor=TEACHER)
    with pytest.raises(AT.ValidationError, match="has no lesson"):
        AT.lesson_register(lesson.lesson_id, TUE)
    with pytest.raises(AT.ValidationError, match="past lesson register"):
        AT.save_lesson_register(lesson.lesson_id, dt.date(2026, 10, 7),
                                {form[0].pupil_id: "P"}, actor=TEACHER)


# ── Settings ─────────────────────────────────────────────────────────

def test_session_times(form):
    assert AT.session_times() == AT.DEFAULT_TIMES
    assert AT.session_for_period(1) == "AM" and AT.session_for_period(5) == "PM"
    with pytest.raises(AT.ValidationError, match="run in order"):
        AT.set_session_times({"am_close": "08:00"}, actor=OFFICE)
    with pytest.raises(AT.ValidationError, match="HH:MM"):
        AT.set_session_times({"pm_start": "1pm"}, actor=OFFICE)
    with pytest.raises(AT.PermissionDenied):
        AT.set_session_times({"am_close": "09:00"}, actor=TEACHER)
    AT.set_session_times({"am_close": "09:30"}, actor=OFFICE)
    assert AT.record_late(form[0].pupil_id, TODAY, "AM", "09:25", actor=TEACHER).code == "L"
