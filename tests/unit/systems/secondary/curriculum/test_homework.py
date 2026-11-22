"""Homework rules (domain.homework) on a scratch school DB.

Two teacher logins are provisioned in a scratch auth.db and "today" is pinned
(Wednesday 4 Nov 2026, moved on where a test needs the due date to pass).
The activity log is redirected, so nothing touches live data.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import homework as HW
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
AHMED = Principal(username="ahmed", role="teacher")
LEE = Principal(username="lee", role="teacher")
TODAY = dt.date(2026, 11, 4)                   # Wednesday
FRI, MON = "2026-11-06", dt.date(2026, 11, 9)


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.platform.identity.auth.schema import initialise_auth_db
    from education_system.systems.secondary import SYSTEM_KEY
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    for user, name in (("ahmed", "Mr Ahmed"), ("lee", "Ms Lee")):
        UserAuth(db_path=accounts._override).provision_user(
            user, "Teach!ng-Pass-123", display_name=name, email=f"{user}@school.org",
            systems=[(SYSTEM_KEY, "teacher")])
    monkeypatch.setattr(HW, "_today", lambda: TODAY)
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _move_to(monkeypatch, day: dt.date) -> None:
    monkeypatch.setattr(HW, "_today", lambda: day)


@pytest.fixture
def school():
    m = S.create({"code": "MATH", "name": "Mathematics"}, actor=ADMIN)
    ma1 = TG.create({"code": "8/Ma1", "subject_id": m.subject_id, "year_group": 8,
                     "teacher_username": "ahmed"}, actor=ADMIN)
    pupils = [P.create_pupil({"legal_first_name": name, "legal_last_name": "Test",
                              "date_of_birth": "2014-01-15", "gender": "Female",
                              "year_group": 8, "admission_date": "2025-09-01"}, actor=ADMIN)
              for name in ("Ava", "Ben", "Cat")]
    TG.add_pupils([p.pupil_id for p in pupils], ma1.group_id, actor=ADMIN)
    return {"maths": m, "ma1": ma1, "pupils": [p.pupil_id for p in pupils]}


def _set(school, **extra):
    data = {"title": "Fractions", "group_id": school["ma1"].group_id, "due_date": FRI,
            "points": 20, "instructions": "Exercise 4", "status": "Set", **extra}
    return HW.create(data, actor=AHMED)


# ── Setting homework ─────────────────────────────────────────────────

def test_new_homework_takes_the_group_and_teacher(school):
    t, warnings = HW.create({"title": "Fractions", "group_id": school["ma1"].group_id,
                             "due_date": FRI}, actor=AHMED)
    assert (t.status, t.for_label, t.year_group, t.subject_code, t.set_by_name,
            t.set_date, warnings) == ("Draft", "8/Ma1", 8, "MATH", "Mr Ahmed",
                                      "2026-11-04", [])
    assert HW.list_work(t.task_id) == []


def test_setting_adds_the_class(school):
    t, _ = HW.create({"title": "Fractions", "group_id": school["ma1"].group_id,
                      "due_date": FRI}, actor=AHMED)
    with pytest.raises(HW.ValidationError, match="Write the instructions"):
        HW.set_task(t.task_id, actor=AHMED)
    HW.update(t.task_id, {"instructions": "Exercise 4"}, actor=AHMED)
    t, _ = HW.set_task(t.task_id, actor=AHMED)
    assert t.status == "Set"
    assert {w.status for w in HW.list_work(t.task_id)} == {"Pending"}
    assert len(HW.list_work(t.task_id)) == 3
    assert HW.seed(t.task_id, actor=AHMED) == 0          # old "Seed" is idempotent


def test_seed_adds_pupils_who_joined_later(school):
    t, _ = _set(school)
    new = P.create_pupil({"legal_first_name": "Dan", "legal_last_name": "Test",
                          "date_of_birth": "2014-02-01", "gender": "Male", "year_group": 8,
                          "admission_date": "2026-11-01"}, actor=ADMIN)
    TG.add_pupils([new.pupil_id], school["ma1"].group_id, actor=ADMIN)
    assert HW.seed(t.task_id, actor=AHMED) == 1


@pytest.mark.parametrize("data, msg", [
    ({"title": ""}, "Give the homework a title"),
    ({"due_date": "2026-11-01", "set_date": "2026-11-04"}, "can't be before the set date"),
    ({"due_date": "soon"}, "Due date must be a date"),
    ({"points": "0"}, "Points must be"),
    ({"est_minutes": "600"}, "Expected time"),
    ({"group_id": None}, "Choose a teaching group, or a subject and year group"),
])
def test_bad_homework_refused(school, data, msg):
    base = {"title": "Fractions", "group_id": school["ma1"].group_id, "due_date": FRI}
    with pytest.raises(HW.ValidationError, match=msg):
        HW.create({**base, **data}, actor=AHMED)


def test_whole_year_homework_old_style(school):
    t, _ = HW.create({"title": "Times tables", "subject_id": school["maths"].subject_id,
                      "year_group": 8, "due_date": FRI, "instructions": "Learn 7s",
                      "status": "Set"}, actor=ADMIN)
    assert (t.for_label, t.group_id) == ("Year 8", None)
    assert len(HW.list_work(t.task_id)) == 3
    with pytest.raises(HW.ValidationError, match="isn't taught in Year 12|Year group must"):
        HW.create({"title": "x", "subject_id": school["maths"].subject_id, "year_group": 12,
                   "due_date": FRI}, actor=ADMIN)


def test_cant_set_homework_already_due(school):
    with pytest.raises(HW.ValidationError, match="has passed"):
        _set(school, set_date="2026-11-01", due_date="2026-11-02")


def test_load_and_school_day_warnings(school):
    _set(school, title="One")
    _set(school, title="Two")
    _t, warnings = _set(school, title="Three")
    assert warnings == ["3 pupil(s) already have 2 or more homework(s) due on Fri 06 Nov"]
    _t, warnings = _set(school, title="Weekend", due_date="2026-11-07")
    assert "Sat 07 Nov isn't a school day" in warnings[0]


# ── Who may change it ───────────────────────────────────────────────

def test_only_the_teacher_or_an_editor_changes_it(school):
    t, _ = _set(school)
    with pytest.raises(HW.PermissionDenied):
        HW.update(t.task_id, {"title": "Mine now"}, actor=LEE)
    with pytest.raises(HW.PermissionDenied):
        HW.record(t.task_id, school["pupils"][0], {"status": "Submitted"}, actor=LEE)
    assert HW.update(t.task_id, {"title": "Fractions 2"}, actor=ADMIN)[0].title == "Fractions 2"
    with pytest.raises(HW.PermissionDenied):
        HW.create({"title": "x", "group_id": school["ma1"].group_id, "due_date": FRI},
                  actor=Principal(username="kid", role="student"))


def test_set_homework_cant_move_class(school):
    t, _ = _set(school)
    with pytest.raises(HW.ValidationError, match="copy it instead"):
        HW.update(t.task_id, {"group_id": None, "subject_id": school["maths"].subject_id,
                              "year_group": 8}, actor=AHMED)


# ── Pupils' work ─────────────────────────────────────────────────────

def test_hand_in_mark_and_late(school, monkeypatch):
    t, _ = _set(school)
    ava, ben, _cat = school["pupils"]
    w = HW.record(t.task_id, ava, {"status": "Submitted"}, actor=AHMED)
    assert (w.status, w.handed_in) == ("Submitted", "2026-11-04")
    w = HW.record(t.task_id, ava, {"mark": "15"}, actor=AHMED)
    assert (w.status, w.mark_label, w.mark_pct) == ("Graded", "15/20", 75.0)
    with pytest.raises(HW.ValidationError, match="Mark must be from 0 to 20"):
        HW.record(t.task_id, ava, {"mark": 25}, actor=AHMED)
    with pytest.raises(HW.ValidationError, match="future date"):
        HW.record(t.task_id, ben, {"status": "Submitted", "handed_in": "2026-11-05"},
                  actor=AHMED)
    _move_to(monkeypatch, MON)
    w = HW.record(t.task_id, ben, {"status": "Submitted"}, actor=AHMED)
    assert (w.status, w.late) == ("Late", True)


def test_status_rules_for_work(school, monkeypatch):
    t, _ = _set(school)
    ava, ben, cat = school["pupils"]
    with pytest.raises(HW.ValidationError, match="isn't missing yet"):
        HW.record(t.task_id, ava, {"status": "Missing"}, actor=AHMED)
    with pytest.raises(HW.ValidationError, match="Only work that's been handed in"):
        HW.record(t.task_id, ava, {"mark": 10}, actor=AHMED)
    with pytest.raises(HW.ValidationError, match="Say why"):
        HW.record(t.task_id, ava, {"status": "Excused"}, actor=AHMED)
    with pytest.raises(HW.ValidationError, match="Give a mark or a grade"):
        HW.record(t.task_id, ava, {"status": "Graded"}, actor=AHMED)
    w = HW.record(t.task_id, ben, {"status": "Excused", "excuse_reason": "In hospital"},
                  actor=AHMED)
    assert (w.status, w.excuse_reason) == ("Excused", "In hospital")
    _move_to(monkeypatch, dt.date(2026, 11, 6))          # the due date itself
    assert HW.record(t.task_id, cat, {"status": "Missing"}, actor=AHMED).status == "Missing"


def test_pupil_must_be_in_the_class(school):
    t, _ = _set(school)
    other = P.create_pupil({"legal_first_name": "Zed", "legal_last_name": "Other",
                            "date_of_birth": "2013-01-15", "gender": "Male", "year_group": 9,
                            "admission_date": "2025-09-01"}, actor=ADMIN)
    with pytest.raises(HW.ValidationError, match="isn't in 8/Ma1"):
        HW.record(t.task_id, other.pupil_id, {"status": "Submitted"}, actor=AHMED)


def test_draft_homework_takes_no_work(school):
    t, _ = HW.create({"title": "x", "group_id": school["ma1"].group_id, "due_date": FRI},
                     actor=AHMED)
    with pytest.raises(HW.ValidationError, match="Set the homework first"):
        HW.record(t.task_id, school["pupils"][0], {"status": "Submitted"}, actor=AHMED)


def test_tick_off_several(school):
    t, _ = _set(school)
    n, problems = HW.record_many(t.task_id, school["pupils"], "Submitted", actor=AHMED)
    assert (n, problems) == (3, [])
    n, problems = HW.record_many(t.task_id, school["pupils"][:1], "Missing", actor=AHMED)
    assert n == 0 and "isn't missing yet" in problems[0]


def test_removing_a_pupils_row(school):
    t, _ = _set(school)
    ava, ben, _cat = school["pupils"]
    HW.record(t.task_id, ava, {"status": "Submitted"}, actor=AHMED)
    with pytest.raises(HW.ValidationError, match="set them Excused instead"):
        HW.delete_work(t.task_id, ava, actor=AHMED)
    HW.delete_work(t.task_id, ben, actor=AHMED)
    HW.delete_work(t.task_id, ava, actor=ADMIN)
    assert len(HW.list_work(t.task_id)) == 1


# ── Status of the homework ──────────────────────────────────────────

def test_close_makes_pending_missing(school, monkeypatch):
    t, _ = _set(school)
    ava = school["pupils"][0]
    HW.record(t.task_id, ava, {"status": "Submitted"}, actor=AHMED)
    with pytest.raises(HW.ValidationError, match="isn't due until"):
        HW.close(t.task_id, actor=AHMED)
    _move_to(monkeypatch, MON)
    t, warnings = HW.set_status(t.task_id, "Closed", actor=AHMED)
    assert t.status == "Closed" and warnings == ["2 pupil(s) hadn't handed it in - now Missing"]
    s = HW.summary(t.task_id)
    assert (s["by_status"]["Missing"], s["handed_in"], s["completion_pct"], s["to_mark"]) == (
        2, 1, 33.3, 1)
    with pytest.raises(HW.ValidationError, match="can't go back to Draft"):
        HW.set_status(t.task_id, "Draft", actor=AHMED)
    assert HW.set_status(t.task_id, "Set", actor=AHMED)[0].status == "Set"   # reopen


def test_back_to_draft_while_nothing_handed_in(school):
    t, _ = _set(school)
    t = HW.to_draft(t.task_id, actor=AHMED)
    assert t.status == "Draft" and HW.list_work(t.task_id) == []


def test_delete_rules(school):
    t, _ = _set(school)
    HW.record(t.task_id, school["pupils"][0], {"status": "Submitted"}, actor=AHMED)
    with pytest.raises(HW.ValidationError, match="it's a record now"):
        HW.delete(t.task_id, actor=AHMED)
    HW.delete(t.task_id, actor=ADMIN)
    with pytest.raises(HW.NotFound):
        HW.get(t.task_id)
    d, _ = HW.create({"title": "Draft", "group_id": school["ma1"].group_id, "due_date": FRI},
                     actor=AHMED)
    HW.delete(d.task_id, actor=AHMED)


def test_copy_is_a_new_draft(school):
    t, _ = _set(school)
    c, _ = HW.copy(t.task_id, actor=AHMED, due_date="2026-11-13")
    assert (c.status, c.title, c.group_id, c.instructions, c.points) == (
        "Draft", "Fractions", school["ma1"].group_id, "Exercise 4", 20)
    with pytest.raises(HW.ValidationError, match="due date"):
        HW.copy(t.task_id, actor=AHMED)


# ── Reports ──────────────────────────────────────────────────────────

def test_reports(school, monkeypatch):
    t, _ = _set(school, est_minutes=30)
    ava, ben, cat = school["pupils"]
    HW.record(t.task_id, ava, {"status": "Graded", "mark": 10}, actor=AHMED)
    assert [x[0].task_id for x in HW.to_mark(AHMED)] == []
    _move_to(monkeypatch, MON)
    HW.record(t.task_id, ben, {"status": "Submitted"}, actor=AHMED)
    HW.close(t.task_id, actor=AHMED)
    assert [(x[0].task_id, x[1]) for x in HW.to_mark(AHMED)] == [(t.task_id, 1)]
    assert HW.to_mark(LEE) == [] and len(HW.to_mark(LEE, everyone=True)) == 1
    report = HW.missing_report()
    assert [(r["pupil_id"], r["missing"], r["late"]) for r in report] == [
        (cat, 1, 0), (ben, 0, 1)]
    s = HW.pupil_summary(ava)
    assert (s.set, s.handed_in, s.missing, s.average_pct, s.completion_pct) == (
        1, 1, 0, 50.0, 100.0)
    assert HW.pupil_summary(cat).missing == 1
    cal = HW.due_calendar("2026-11-02", "2026-11-08")
    assert list(cal) == [FRI] and cal[FRI][0].est_minutes == 30
    (row,) = HW.completion_by_group()
    assert (row["for"], row["tasks"], row["handed_in"], row["completion_pct"]) == (
        "8/Ma1", 1, 2, 66.7)


def test_export_marks_is_formula_safe(school, tmp_path):
    t, _ = _set(school)
    HW.record(t.task_id, school["pupils"][0], {"status": "Graded", "mark": 18,
                                               "feedback": "=HYPERLINK(1)"}, actor=AHMED)
    path = tmp_path / "marks.csv"
    assert HW.export_marks(t.task_id, path, actor=AHMED) == 3
    rows = list(csv.reader(path.open(encoding="utf-8")))
    ava = next(r for r in rows if r[1] == "Test, Ava")
    assert ava[3:] == ["Graded", "2026-11-04", "", "18.0", "20", "90.0", "",
                       "'=HYPERLINK(1)"]


def test_email_parents_of_missing_pupils(school, monkeypatch):
    t, _ = _set(school)
    ava, _ben, cat = school["pupils"]
    C.add_contact(cat, {"full_name": "Cat's Mum", "relationship": "Mother",
                        "email": "mum@example.org", "receives_email": True,
                        "parental_responsibility": True}, actor=ADMIN)
    with pytest.raises(HW.ValidationError, match="Nobody's homework is missing"):
        HW.notify_parents(t.task_id, actor=AHMED)
    HW.record(t.task_id, ava, {"status": "Submitted"}, actor=AHMED)
    _move_to(monkeypatch, MON)
    HW.close(t.task_id, actor=AHMED)
    with pytest.raises(HW.ValidationError, match="aren't marked Missing"):
        HW.notify_parents(t.task_id, actor=AHMED, pupil_ids=[ava])
    result = HW.notify_parents(t.task_id, actor=AHMED)
    assert result.recipients == 1
    assert [p.legal_first_name for p in result.pupils_without_email] == ["Ben"]
    with database.connect() as conn:
        (body,) = conn.execute("SELECT body FROM email_recipients WHERE message_id = ?",
                               (result.message_id,)).fetchone()
    assert body.startswith("Dear Cat's Mum") and "Cat hasn't handed in" in body


def test_daily_limit_setting(school):
    assert HW.daily_limit() == 2
    assert HW.set_daily_limit("3", actor=ADMIN) == 3
    with pytest.raises(HW.PermissionDenied):
        HW.set_daily_limit(1, actor=AHMED)
    with pytest.raises(HW.ValidationError):
        HW.set_daily_limit(0, actor=ADMIN)
