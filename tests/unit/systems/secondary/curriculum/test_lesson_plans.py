"""Lesson plan and scheme-of-work rules (domain.lesson_plans) on a scratch DB.

"Today" is pinned to Wednesday 4 Nov 2026 for the Delivered rule. auth.db and
the activity log are redirected, so nothing touches live data.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import lesson_plans as LP
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
T1 = Principal(username="t1", role="teacher")
T2 = Principal(username="t2", role="teacher")
PUPIL = Principal(username="kid", role="student")
TODAY = dt.date(2026, 11, 4)   # Wednesday
MON = "2026-11-02"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(LP, "_today", lambda: TODAY)
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


@pytest.fixture
def setup():
    m = S.create({"code": "MATH", "name": "Mathematics"}, actor=ADMIN)
    e = S.create({"code": "ENG", "name": "English"}, actor=ADMIN)
    g = TG.create({"code": "8/Ma1", "subject_id": m.subject_id, "year_group": 8,
                   "teacher_name": "Mr Ahmed"}, actor=ADMIN)
    TT.add_lesson({"group_id": g.group_id, "day": "Mon", "period": 1}, actor=ADMIN)
    TT.add_lesson({"group_id": g.group_id, "day": "Wed", "period": 3}, actor=ADMIN)
    u = LP.create_unit({"subject_id": m.subject_id, "year_group": 8, "title": "Fractions",
                        "term": "autumn", "lessons": 6}, actor=ADMIN)
    return {"math": m, "eng": e, "group": g, "unit": u}


def _plan(setup, actor=T1, **extra):
    data = {"title": "Adding fractions", "group_id": setup["group"].group_id,
            "planned_date": MON, "period": 1, **extra}
    return LP.create(data, actor=actor)[0]


# ── Plans ────────────────────────────────────────────────────────────

def test_group_plan_takes_subject_year_teacher_and_lesson(setup):
    p, warnings = LP.create({"title": "Adding fractions", "group_id": setup["group"].group_id,
                             "planned_date": MON, "period": "1",
                             "unit_id": setup["unit"].unit_id}, actor=T1)
    assert warnings == []
    assert (p.subject_code, p.year_group, p.group_code, p.teacher_name) == (
        "MATH", 8, "8/Ma1", "Mr Ahmed")
    assert p.lesson_id is not None and p.duration_min == 60 and p.status == "Draft"
    assert (p.unit_title, p.created_by, p.when) == ("Fractions", "t1", "Mon 02 Nov 2026 P1")


def test_untimetabled_slot_is_saved_with_a_warning(setup):
    p, warnings = LP.create({"title": "Extra", "group_id": setup["group"].group_id,
                             "planned_date": "2026-11-03", "period": 2}, actor=T1)
    assert p.lesson_id is None and "no timetabled lesson" in warnings[0]


def test_shared_plan_needs_subject_and_year_not_a_date(setup):
    p, _ = LP.create({"title": "Bank", "subject_id": setup["math"].subject_id,
                      "year_group": 9}, actor=T1)
    assert p.is_shared and p.when == "Shared plan" and p.planned_date is None
    assert [x.plan_id for x in LP.list_plans(shared=True)] == [p.plan_id]


@pytest.mark.parametrize("data, msg", [
    ({"title": ""}, "title"),
    ({"group_id": None, "subject_id": None}, "subject and year"),
    ({"planned_date": None}, "needs the lesson's date"),
    ({"planned_date": "4/11/2026"}, "YYYY-MM-DD"),
    ({"period": 9}, "Period must be from 1 to 5"),
    ({"teacher_username": "ghost"}, "staff login"),
    ({"bogus": 1}, "Unknown field"),
])
def test_bad_plans_refused(setup, data, msg):
    base = {"title": "x", "group_id": setup["group"].group_id, "planned_date": MON,
            "period": 1, **data}
    with pytest.raises(LP.ValidationError, match=msg):
        LP.create(base, actor=T1)


def test_unit_must_match_subject_and_year(setup):
    other = LP.create_unit({"subject_id": setup["eng"].subject_id, "year_group": 8,
                            "title": "Poetry"}, actor=ADMIN)
    with pytest.raises(LP.ValidationError, match="another subject or year"):
        _plan(setup, unit_id=other.unit_id)
    LP.archive_unit(setup["unit"].unit_id, actor=ADMIN)
    with pytest.raises(LP.ValidationError, match="archived"):
        _plan(setup, unit_id=setup["unit"].unit_id)


def test_one_plan_per_lesson(setup):
    _plan(setup)
    with pytest.raises(LP.ValidationError, match="already has a plan for that lesson"):
        _plan(setup, title="Second")
    other = _plan(setup, title="Wednesday", planned_date="2026-11-04", period=3)
    with pytest.raises(LP.ValidationError, match="already has a plan"):
        LP.update(other.plan_id, {"planned_date": MON, "period": 1}, actor=T1)


def test_old_groups_cant_be_planned(setup):
    with database.connect() as conn:
        conn.execute("UPDATE teaching_groups SET academic_year = '2020/21' WHERE group_id = ?",
                     (setup["group"].group_id,))
    with pytest.raises(LP.ValidationError, match="this year's open groups"):
        _plan(setup)


def test_only_the_teacher_writer_or_editor_changes_a_plan(setup):
    p = _plan(setup)
    assert LP.can_change(T1, p) and LP.can_change(ADMIN, p) and not LP.can_change(T2, p)
    with pytest.raises(LP.PermissionDenied):
        LP.update(p.plan_id, {"title": "mine now"}, actor=T2)
    with pytest.raises(LP.PermissionDenied):
        LP.create({"title": "x", "subject_id": setup["math"].subject_id, "year_group": 8},
                  actor=PUPIL)
    q, _ = LP.update(p.plan_id, {"activities": "starter"}, actor=ADMIN)
    assert q.activities == "starter" and q.updated_by == "admin2"
    assert [h["action"] for h in LP.history(p.plan_id)] == ["update", "create"]


# ── Status ───────────────────────────────────────────────────────────

def test_status_rules(setup):
    p = _plan(setup)
    with pytest.raises(LP.ValidationError, match="objectives and activities"):
        LP.set_status(p.plan_id, "Ready", actor=T1)
    LP.update(p.plan_id, {"objectives": "add fractions", "activities": "worked examples"},
              actor=T1)
    assert LP.set_status(p.plan_id, "ready", actor=T1).status == "Ready"
    future = _plan(setup, title="Next week", planned_date="2026-11-09",
                   objectives="o", activities="a")
    with pytest.raises(LP.ValidationError, match="isn't until 2026-11-09"):
        LP.set_status(future.plan_id, "Delivered", actor=T1)
    assert LP.set_status(p.plan_id, "Delivered", actor=T1).status == "Delivered"
    with pytest.raises(LP.ValidationError, match="evaluation"):
        LP.set_status(p.plan_id, "Reviewed", actor=T1)
    r = LP.set_status(p.plan_id, "Reviewed", actor=T1, evaluation="Went well; recap LCM")
    assert (r.status, r.evaluation) == ("Reviewed", "Went well; recap LCM")


def test_reviewed_and_delivered_plans_are_records(setup):
    p = _plan(setup, objectives="o", activities="a")
    LP.set_status(p.plan_id, "Reviewed", actor=T1, evaluation="ok")
    with pytest.raises(LP.ValidationError, match="only its evaluation and notes"):
        LP.update(p.plan_id, {"title": "rewritten"}, actor=T1)
    LP.update(p.plan_id, {"notes": "share with dept"}, actor=T1)
    with pytest.raises(LP.ValidationError, match="only an editor can reopen"):
        LP.set_status(p.plan_id, "Draft", actor=T1)
    with pytest.raises(LP.ValidationError, match="ask an editor"):
        LP.delete(p.plan_id, actor=T1)
    LP.delete(p.plan_id, actor=ADMIN)
    with pytest.raises(LP.NotFound):
        LP.get(p.plan_id)


def test_shared_plans_are_not_delivered(setup):
    p, _ = LP.create({"title": "Bank", "subject_id": setup["math"].subject_id,
                      "year_group": 8, "objectives": "o", "activities": "a"}, actor=T1)
    assert LP.set_status(p.plan_id, "Ready", actor=T1).status == "Ready"
    with pytest.raises(LP.ValidationError, match="copy it to a group"):
        LP.set_status(p.plan_id, "Delivered", actor=T1)


# ── Copy and planning from the timetable ─────────────────────────────

def test_copy(setup):
    p = _plan(setup, objectives="o", activities="a", evaluation="secret")
    LP.set_status(p.plan_id, "Reviewed", actor=T1)
    shared, _ = LP.copy(p.plan_id, actor=T2, shared=True)
    assert shared.is_shared and shared.status == "Draft" and shared.evaluation is None
    assert (shared.objectives, shared.created_by) == ("o", "t2")
    again, _ = LP.copy(shared.plan_id, actor=T1, group_id=setup["group"].group_id,
                       planned_date="2026-11-04", period=3)
    assert again.group_code == "8/Ma1" and again.lesson_id is not None
    eng = TG.create({"code": "8/En1", "subject_id": setup["eng"].subject_id,
                     "year_group": 8}, actor=ADMIN)
    with pytest.raises(LP.ValidationError, match="different subject"):
        LP.copy(p.plan_id, actor=T1, group_id=eng.group_id, planned_date=MON, period=2)


def test_plan_from_timetable(setup):
    g, u = setup["group"], setup["unit"]
    _plan(setup, unit_id=u.unit_id)
    created, skipped = LP.plan_from_timetable(g.group_id, MON, "2026-11-11", actor=ADMIN,
                                              unit_id=u.unit_id)
    assert skipped == 1
    assert [(p.planned_date, p.period, p.title) for p in created] == [
        ("2026-11-04", 3, "Fractions - lesson 2"), ("2026-11-09", 1, "Fractions - lesson 3"),
        ("2026-11-11", 3, "Fractions - lesson 4")]
    with pytest.raises(LP.PermissionDenied, match="teacher can plan"):
        LP.plan_from_timetable(g.group_id, MON, "2026-11-11", actor=T1)
    with pytest.raises(LP.ValidationError, match="At most"):
        LP.plan_from_timetable(g.group_id, MON, "2027-11-11", actor=ADMIN)


def test_coverage_shows_unplanned_lessons(setup):
    _plan(setup)
    rows = LP.coverage(MON, "2026-11-06")
    assert [(d.isoformat(), x.period, p.title if p else None) for d, x, p in rows] == [
        (MON, 1, "Adding fractions"), ("2026-11-04", 3, None)]


# ── Units ────────────────────────────────────────────────────────────

def test_units(setup):
    u = setup["unit"]
    assert (u.term, u.label) == ("Autumn", "1. Fractions")
    with pytest.raises(LP.ValidationError, match="already has a unit called"):
        LP.create_unit({"subject_id": setup["math"].subject_id, "year_group": 8,
                        "title": "fractions"}, actor=ADMIN)
    k3 = S.create({"code": "CIT", "name": "Citizenship", "key_stage": "KS3",
                   "qualification": "KS3"}, actor=ADMIN)
    with pytest.raises(LP.ValidationError, match="isn't taught in Year 10"):
        LP.create_unit({"subject_id": k3.subject_id, "year_group": 10, "title": "x"},
                       actor=ADMIN)
    with pytest.raises(LP.PermissionDenied):
        LP.create_unit({"subject_id": setup["math"].subject_id, "year_group": 8,
                        "title": "Algebra"}, actor=T1)
    p = _plan(setup, unit_id=u.unit_id, objectives="o", activities="a")
    LP.set_status(p.plan_id, "Delivered", actor=T1)
    (prog,) = LP.unit_progress(u.unit_id)
    assert (prog.group_code, prog.planned, prog.delivered) == ("8/Ma1", 1, 1)
    with pytest.raises(LP.ValidationError, match="subject and year can't change"):
        LP.update_unit(u.unit_id, {"year_group": 9}, actor=ADMIN)
    with pytest.raises(LP.ValidationError, match="archive it instead"):
        LP.delete_unit(u.unit_id, actor=ADMIN)
    spare = LP.create_unit({"subject_id": setup["math"].subject_id, "year_group": 8,
                            "title": "Algebra", "sequence": 2}, actor=ADMIN)
    LP.delete_unit(spare.unit_id, actor=ADMIN)
    assert [x.title for x in LP.list_units(subject_id=setup["math"].subject_id)] == [
        "Fractions"]


def test_subject_with_plans_cant_be_deleted(setup):
    _plan(setup)
    with pytest.raises(S.ValidationError, match="lesson plan"):
        S.delete(setup["math"].subject_id, actor=ADMIN)


# ── Reading and export ───────────────────────────────────────────────

def test_filters_and_counts(setup):
    a = _plan(setup, objectives="equivalent fractions")
    _plan(setup, title="Decimals", planned_date="2026-11-04", period=3, actor=ADMIN,
          teacher_name="Ms Cover")
    assert [p.plan_id for p in LP.list_plans(search="equivalent")] == [a.plan_id]
    assert [p.title for p in LP.list_plans(teacher="ms cover")] == ["Decimals"]
    assert [p.title for p in LP.list_plans(teacher="t1")] == ["Adding fractions"]
    assert [p.title for p in LP.list_plans(date_from="2026-11-03")] == ["Decimals"]
    assert LP.status_counts() == {"Draft": 2, "Ready": 0, "Delivered": 0, "Reviewed": 0}
    with pytest.raises(LP.ValidationError, match="Status must be"):
        LP.list_plans(status="Done")


def test_export_text(setup, tmp_path):
    p = _plan(setup, objectives="Add fractions", homework="Sheet 4")
    path = tmp_path / "plan.txt"
    LP.export_text(p.plan_id, path, actor=T2)
    text = path.read_text(encoding="utf-8")
    assert "Adding fractions" in text and "Learning objectives" in text and "Sheet 4" in text
    assert "Evaluation" not in text
