"""Cover rules (domain.cover) on a scratch school DB.

Three teacher logins are provisioned in a scratch auth.db; "today" is pinned
to Wednesday 4 Nov 2026. The activity log is redirected, so nothing touches
live data.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import cover as CV
from education_system.systems.secondary.modules.curriculum.domain import lesson_plans as LP
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
AHMED = Principal(username="ahmed", role="teacher")
LEE = Principal(username="lee", role="teacher")
COLE = Principal(username="cole", role="teacher")
TODAY = dt.date(2026, 11, 4)                   # Wednesday
MON, WED = dt.date(2026, 11, 9), dt.date(2026, 11, 11)


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.platform.identity.auth.schema import initialise_auth_db
    from education_system.systems.secondary import SYSTEM_KEY
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    for user, name in (("ahmed", "Mr Ahmed"), ("lee", "Ms Lee"), ("cole", "Dr Cole")):
        UserAuth(db_path=accounts._override).provision_user(
            user, "Teach!ng-Pass-123", display_name=name, email=f"{user}@school.org",
            systems=[(SYSTEM_KEY, "teacher")])
    monkeypatch.setattr(CV, "_today", lambda: TODAY)
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


@pytest.fixture
def school():
    m = S.create({"code": "MATH", "name": "Mathematics"}, actor=ADMIN)
    e = S.create({"code": "ENG", "name": "English"}, actor=ADMIN)
    ma1 = TG.create({"code": "8/Ma1", "subject_id": m.subject_id, "year_group": 8,
                     "teacher_username": "ahmed", "room": "M1"}, actor=ADMIN)
    ma2 = TG.create({"code": "9/Ma2", "subject_id": m.subject_id, "year_group": 9,
                     "teacher_username": "ahmed", "room": "M1"}, actor=ADMIN)
    en1 = TG.create({"code": "8/En1", "subject_id": e.subject_id, "year_group": 8,
                     "teacher_username": "lee", "room": "E1"}, actor=ADMIN)
    for g, day, p in ((ma1, "Mon", 1), (ma2, "Mon", 3), (ma1, "Wed", 2), (en1, "Mon", 1)):
        TT.add_lesson({"group_id": g.group_id, "day": day, "period": p}, actor=ADMIN)
    return {"ma1": ma1, "ma2": ma2, "en1": en1}


def _away(start=MON, end=WED, actor=AHMED, **extra):
    return CV.create_absence({"teacher_username": "ahmed", "start_date": start,
                              "end_date": end, "reason": "Training / CPD", **extra},
                             actor=actor)


def _supply(**extra):
    data = {"full_name": "Sam Supply", "agency_name": "TeachCo", "hourly_rate": "£30",
            "email": "sam@teachco.org", "dbs_cleared": True, "dbs_checked_on": "2026-09-01",
            **extra}
    return CV.create_supply(data, actor=ADMIN)


# ── Absences make cover ──────────────────────────────────────────────

def test_absence_creates_cover_for_each_lesson(school):
    a, n = _away()
    assert (a.teacher_name, a.dates_label, a.periods_label, n) == (
        "Mr Ahmed", "2026-11-09 to 2026-11-11", "all day", 3)
    assert [(c.date, c.period, c.group_code, c.room, c.status) for c in
            CV.list_covers(absence_id=a.absence_id)] == [
        ("2026-11-09", 1, "8/Ma1", "M1", "Pending"), ("2026-11-09", 3, "9/Ma2", "M1", "Pending"),
        ("2026-11-11", 2, "8/Ma1", "M1", "Pending")]


def test_part_day_absence(school):
    _a, n = _away(end=MON, from_period=3, to_period=5)
    assert n == 1 and CV.list_covers()[0].group_code == "9/Ma2"


def test_absence_rules(school):
    with pytest.raises(CV.ValidationError, match="record your own absence"):
        CV.create_absence({"teacher_username": "lee", "start_date": MON,
                           "reason": "Illness"}, actor=AHMED)
    with pytest.raises(CV.ValidationError, match="past absence"):
        _away(start=dt.date(2026, 11, 2), end=dt.date(2026, 11, 2))
    with pytest.raises(CV.ValidationError, match="Reason must be"):
        _away(reason="flu")
    with pytest.raises(CV.ValidationError, match="before the first day"):
        _away(start=WED, end=MON)
    _away()
    with pytest.raises(CV.ValidationError, match="already has an absence"):
        _away(start=WED, end=WED, actor=ADMIN)


def test_changing_an_absence_adds_or_cancels_cover(school):
    a, _ = _away(end=MON)
    _ab, added, cancelled = CV.update_absence(a.absence_id, {"end_date": WED}, actor=AHMED)
    assert (added, cancelled) == (1, 0)
    c = CV.list_covers(absence_id=a.absence_id)[0]
    CV.assign(c.cover_id, actor=ADMIN, username="cole")
    _ab, added, cancelled = CV.update_absence(a.absence_id, {"start_date": WED}, actor=AHMED)
    assert (added, cancelled) == (0, 2)
    assert {x.status for x in CV.list_covers(date=MON)} == {"Cancelled"}
    assert CV.cancel_absence(a.absence_id, actor=AHMED) == 1
    assert CV.list_covers(include_cancelled=False) == []
    with pytest.raises(CV.PermissionDenied):
        b, _ = _away(actor=ADMIN)
        CV.cancel_absence(b.absence_id, actor=LEE)


# ── Assigning ────────────────────────────────────────────────────────

def test_assign_checks_who_is_free(school):
    _away()
    p1, p3, _w = CV.list_covers()
    assert [c.name for c in CV.available(MON, 1, cover_id=p1.cover_id)] == ["Dr Cole"]
    with pytest.raises(CV.ValidationError, match="Ms Lee is teaching 8/En1 then"):
        CV.assign(p1.cover_id, actor=ADMIN, username="lee")
    with pytest.raises(CV.ValidationError, match="is the absent teacher"):
        CV.assign(p1.cover_id, actor=ADMIN, username="ahmed")
    c, warnings = CV.assign(p1.cover_id, actor=ADMIN, username="cole")
    assert (c.status, c.cover_name, c.cover_username, warnings) == (
        "Assigned", "Dr Cole", "cole", [])
    other = CV.create({"date": MON, "period": 1, "group_id": school["en1"].group_id,
                       "absent_name": "Ms Lee"}, actor=ADMIN)
    with pytest.raises(CV.ValidationError, match="already covering 8/Ma1"):
        CV.assign(other.cover_id, actor=ADMIN, username="cole")
    with pytest.raises(CV.PermissionDenied):
        CV.assign(p3.cover_id, actor=LEE, username="lee")


def test_someone_away_cant_cover(school):
    _away()
    CV.create_absence({"teacher_username": "cole", "start_date": MON, "reason": "Illness"},
                      actor=ADMIN)
    p1 = CV.list_covers(date=MON)[0]
    with pytest.raises(CV.ValidationError, match="away"):
        CV.assign(p1.cover_id, actor=ADMIN, username="cole")


def test_weekly_limit_warns(school):
    _away()
    CV.set_weekly_limit(1, actor=ADMIN)
    p1, p3, w2 = CV.list_covers()
    CV.assign(p1.cover_id, actor=ADMIN, username="cole")
    _c, warnings = CV.assign(p3.cover_id, actor=ADMIN, username="cole")
    assert "already has 1 cover(s) that week" in warnings[0]
    over = [c for c in CV.available(WED, 2, cover_id=w2.cover_id) if c.name == "Dr Cole"]
    assert over[0].over_limit and over[0].covers_this_week == 2
    with pytest.raises(CV.PermissionDenied):
        CV.set_weekly_limit(5, actor=COLE)


# ── Supply staff ─────────────────────────────────────────────────────

def test_supply_needs_dbs_and_costs(school):
    _away()
    p1, p3, _w = CV.list_covers()
    unchecked = CV.create_supply({"full_name": "No Check"}, actor=ADMIN)
    with pytest.raises(CV.ValidationError, match="no DBS clearance"):
        CV.assign(p1.cover_id, actor=ADMIN, supply_id=unchecked.supply_id)
    s = _supply()
    assert s.hourly_rate == 30.0
    c, _ = CV.assign(p1.cover_id, actor=ADMIN, supply_id=s.supply_id)
    assert (c.cover_name, c.rate_charged, c.cover_username) == ("Sam Supply", 30.0, None)
    assert [x.name for x in CV.available(MON, 1, cover_id=p1.cover_id)
            if x.kind == "Supply"] == ["Sam Supply"]  # its own booking doesn't block it
    assert [x.name for x in CV.available(MON, 1) if x.kind == "Supply"] == []
    (row,) = CV.supply_report(MON, WED)
    assert (row["periods"], row["minutes"], row["cost"]) == (1, 60, 30.0)
    with pytest.raises(CV.ValidationError, match="make them inactive"):
        CV.delete_supply(s.supply_id, actor=ADMIN)


@pytest.mark.parametrize("data, msg", [
    ({"full_name": ""}, "Name is required"),
    ({"hourly_rate": "lots"}, "Hourly rate"),
    ({"email": "nope"}, "E-mail"),
    ({"dbs_checked_on": None}, "when the DBS check was seen"),
    ({"role": "Chef"}, "Role must be"),
])
def test_bad_supply_refused(data, msg):
    with pytest.raises(CV.ValidationError, match=msg):
        _supply(**data)


def test_turning_supply_off_frees_their_future_cover(school, monkeypatch):
    _away()
    s = _supply()
    p1 = CV.list_covers()[0]
    CV.assign(p1.cover_id, actor=ADMIN, supply_id=s.supply_id)
    assert not CV.toggle_supply(s.supply_id, actor=ADMIN).is_active
    c = CV.get(p1.cover_id)
    assert (c.status, c.cover_name, c.supply_id) == ("Pending", None, None)


# ── Status, work, editing ────────────────────────────────────────────

def test_status_rules(school):
    _away()
    p1, p3, _w = CV.list_covers()
    with pytest.raises(CV.ValidationError, match="Assign someone first"):
        CV.set_status(p1.cover_id, "Confirmed", actor=ADMIN)
    CV.assign(p1.cover_id, actor=ADMIN, username="cole")
    assert CV.set_status(p1.cover_id, "Confirmed", actor=COLE).status == "Confirmed"
    with pytest.raises(CV.ValidationError, match="isn't until 2026-11-09"):
        CV.set_status(p1.cover_id, "Completed", actor=COLE)
    with pytest.raises(CV.PermissionDenied):
        CV.set_status(p1.cover_id, "Cancelled", actor=COLE, note="x")
    with pytest.raises(CV.ValidationError, match="Say why"):
        CV.set_status(p3.cover_id, "Cancelled", actor=ADMIN)
    c = CV.set_status(p3.cover_id, "Cancelled", actor=ADMIN, note="Year 9 on a trip")
    assert c.status == "Cancelled" and "trip" in c.notes
    with pytest.raises(CV.ValidationError, match="cancel it instead"):
        CV.delete(p1.cover_id, actor=ADMIN)
    CV.delete(p3.cover_id, actor=ADMIN)
    assert [h["action"] for h in CV.history(cover_id=p1.cover_id)][:2] == ["status", "assign"]


def test_absent_teacher_sets_the_work_and_sees_the_plan(school):
    _away()
    p1 = CV.list_covers()[0]
    CV.update(p1.cover_id, {"work_set": "Textbook p.42 ex 1-10"}, actor=AHMED)
    with pytest.raises(CV.PermissionDenied):
        CV.update(p1.cover_id, {"room": "Hall"}, actor=AHMED)
    with pytest.raises(CV.PermissionDenied):
        CV.update(p1.cover_id, {"work_set": "x"}, actor=LEE)
    LP.create({"title": "Adding fractions", "group_id": school["ma1"].group_id,
               "planned_date": MON, "period": 1, "objectives": "Add fractions"}, actor=AHMED)
    text = CV.details_text(CV.get(p1.cover_id))
    assert "Textbook p.42" in text and "Lesson plan: Adding fractions" in text
    assert "Room: M1" in text and "Covering for: Mr Ahmed" in text


def test_single_cover_by_hand(school):
    c = CV.create({"date": MON, "period": 1, "group_id": school["en1"].group_id},
                  actor=ADMIN)
    assert (c.absent_name, c.absent_username, c.room, c.lesson_id is not None) == (
        "Ms Lee", "lee", "E1", True)
    with pytest.raises(CV.ValidationError, match="already has cover"):
        CV.create({"date": MON, "period": 1, "group_id": school["en1"].group_id,
                   "absent_name": "Ms Lee"}, actor=ADMIN)
    with pytest.raises(CV.PermissionDenied):
        CV.create({"date": MON, "period": 2, "group_id": school["en1"].group_id},
                  actor=LEE)


# ── Telling people and reports ───────────────────────────────────────

def test_notify_queues_an_email(school):
    _away()
    p1 = CV.list_covers()[0]
    with pytest.raises(CV.ValidationError, match="Assign someone first"):
        CV.notify(p1.cover_id, actor=ADMIN)
    CV.assign(p1.cover_id, actor=ADMIN, username="cole")
    mid = CV.notify(p1.cover_id, actor=ADMIN)
    assert mid and CV.get(p1.cover_id).notified_at
    with database.connect() as conn:
        (addr,) = conn.execute("SELECT address FROM email_recipients WHERE message_id = ?",
                               (mid,)).fetchone()
    assert addr == "cole@school.org"


def test_daily_load_sheet_and_counts(school):
    _away()
    p1, p3, w2 = CV.list_covers()
    CV.assign(p1.cover_id, actor=ADMIN, username="cole")
    CV.assign(w2.cover_id, actor=ADMIN, username="cole")
    load = CV.daily_load(MON)
    assert (load["total"], load["unassigned"], load["by_cover"]) == (2, 1, {"Dr Cole": 1})
    sheet = CV.cover_sheet(MON)
    assert "Monday 09 November 2026" in sheet and "UNASSIGNED" in sheet
    assert CV.cover_counts(MON, WED) == {"Dr Cole": 2}
    assert [c.cover_id for c in CV.my_cover(COLE)] == [p1.cover_id, w2.cover_id]
    assert CV.status_counts()["Assigned"] == 2
