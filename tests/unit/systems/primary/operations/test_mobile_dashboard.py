"""Mobile Dashboard
(systems.primary.domain.operations.reporting.mobile_dashboard.mobile_dashboard).

The button tests check the feeds on an empty school and with one pupil;
these check tile severities, feed ordering, limits and field mapping.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.academics.attendance import attendance as ATT
from education_system.systems.primary.domain.academics.calendar import calendar as CAL
from education_system.systems.primary.domain.assessment.early_warning import (
    early_warning as EW,
)
from education_system.systems.primary.domain.assessment.progress import progress as PG
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.communications.announcements import (
    announcements as AN,
)
from education_system.systems.primary.domain.operations.reporting.mobile_dashboard import (
    mobile_dashboard as MD,
)

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _pupil(first="Ada", last="Lovelace"):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": "3",
                           "date_of_birth": "2019-01-01"})


def _review(pupil, risk="Low", days=0, **extra):
    return PG.create_review({"student_id": pupil.pupil_id, "review_date": _iso(days),
                             "risk_level": risk, **extra})


def _tiles(d):
    return {t.key: t for t in d.tiles}


# ── attendance tile ──

def _attendance(attending: int, absent: int):
    for i in range(attending + absent):
        p = _pupil(f"P{i}", "Reg")
        ATT.record_mark(p.pupil_id, _iso(0), "AM", "P" if i < attending else "O")


@pytest.mark.parametrize("attending,absent,value,severity", [
    (19, 1, "95.0%", "ok"),
    (17, 3, "85.0%", "warn"),
    (5, 1, "83.3%", "alert"),
])
def test_attendance_tile_severity_bands(attending, absent, value, severity):
    _attendance(attending, absent)
    tile = _tiles(MD.build_dashboard())["attendance"]
    assert (tile.value, tile.severity) == (value, severity)
    assert tile.subtitle == f"{attending}/{attending + absent} attending"


def test_today_attendance_ignores_not_required_and_other_days():
    a, b = _pupil("A"), _pupil("B")
    ATT.record_mark(a.pupil_id, _iso(0), "AM", "L")
    ATT.record_mark(a.pupil_id, _iso(0), "PM", "X")
    ATT.record_mark(b.pupil_id, _iso(0), "AM", "I")
    ATT.record_mark(b.pupil_id, _iso(-1), "AM", "P")
    assert MD._today_attendance() == (2, 1, 50.0)


def test_attendance_tile_without_register():
    tile = _tiles(MD.build_dashboard())["attendance"]
    assert (tile.value, tile.subtitle, tile.severity) == ("—", "no register today", "info")


# ── student / progress tiles ──

def test_student_and_progress_tiles():
    a, b, c = _pupil("A"), _pupil("B"), _pupil("C")
    r1 = _review(a, "High")
    _review(b, "Critical")
    _review(c, "High", status="Archived")
    PG.add_target(r1.review_id, {"description": "Times tables", "due_date": _iso(-2)})
    PG.add_target(r1.review_id, {"description": "Reading", "due_date": _iso(5)})
    PG.add_target(r1.review_id, {"description": "Done", "due_date": _iso(-5),
                                 "status": "Met"})
    t = _tiles(MD.build_dashboard())
    assert (t["students"].value, t["students"].subtitle) == ("3", "in cohort")
    assert (t["open_targets"].value, t["open_targets"].subtitle,
            t["open_targets"].severity) == ("2", "1 overdue", "alert")
    assert (t["high_risk"].value, t["high_risk"].severity) == ("2", "alert")


def test_progress_tiles_ok_when_nothing_outstanding():
    t = _tiles(MD.build_dashboard())
    assert (t["open_targets"].value, t["open_targets"].severity) == ("0", "ok")
    assert (t["high_risk"].value, t["high_risk"].severity) == ("0", "ok")


# ── events ──

def test_today_and_upcoming_events():
    CAL.create_event({"title": "Sports day", "start_date": _iso(0), "location": "Field"})
    CAL.create_event({"title": "Trip week", "start_date": _iso(-1), "end_date": _iso(1)})
    CAL.create_event({"title": "Nativity", "start_date": _iso(3)})
    CAL.create_event({"title": "Far off", "start_date": _iso(20)})
    d = MD.build_dashboard()
    assert sorted(e.title for e in d.today_events) == ["Sports day", "Trip week"]
    sports = next(e for e in d.today_events if e.title == "Sports day")
    assert (sports.kind, sports.when, sports.detail) == ("event", _iso(0), "Field")
    assert sorted(e.title for e in d.upcoming_events) == ["Nativity", "Trip week"]
    tile = _tiles(d)["today_events"]
    assert (tile.value, tile.subtitle) == ("2", "2 in next 7 days")


# ── feeds ──

def test_high_risk_feed_uses_latest_review_and_orders_critical_first():
    a, b, c, d = _pupil("Amy", "A"), _pupil("Bob", "B"), _pupil("Cat", "C"), _pupil("Dan", "D")
    _review(a, "High", days=-30)
    _review(a, "Low", days=-1)               # latest is Low: not listed
    _review(b, "High", days=-5)
    _review(c, "Critical", days=-2, overall="4 — Inadequate")
    _review(d, "High", days=-9)
    feed = MD._high_risk_feed()
    assert [f.title for f in feed] == [f"Cat C ({c.pupil_id})", f"Dan D ({d.pupil_id})",
                                       f"Bob B ({b.pupil_id})"]
    assert (feed[0].kind, feed[0].severity, feed[0].when) == ("review", "alert", _iso(-2))
    assert feed[0].detail == "Critical risk · 4 — Inadequate"
    assert feed[1].severity == "warn"


def test_high_risk_feed_limit():
    for i in range(4):
        _review(_pupil(f"P{i}"), "High", days=-i)
    assert len(MD._high_risk_feed(limit=2)) == 2


def test_overdue_target_feed():
    a = _pupil("Amy", "Able")
    r = _review(a)
    PG.add_target(r.review_id, {"area": "Reading", "description": "Read nightly",
                                "due_date": _iso(-3)})
    PG.add_target(r.review_id, {"area": "Phonics", "description": "Phase 5",
                                "due_date": _iso(0)})          # due today: not overdue
    PG.add_target(r.review_id, {"area": "Behaviour", "description": "Met it",
                                "due_date": _iso(-3), "status": "Met"})
    feed = MD._overdue_target_feed()
    assert [(f.kind, f.title, f.detail, f.when, f.severity) for f in feed] == \
        [("target", "Amy Able — Reading", "Read nightly", _iso(-3), "warn")]


def test_announcement_feed_published_only_with_severity():
    AN.create_announcement({"title": "Snow day", "status": "Published", "priority": 5,
                            "body": "x" * 200, "published_on": _iso(0)})
    AN.create_announcement({"title": "Bake sale", "status": "Published", "priority": 2,
                            "published_on": _iso(-1)})
    AN.create_announcement({"title": "Draft", "status": "Draft"})
    feed = MD._announcement_feed()
    by_title = {f.title: f for f in feed}
    assert set(by_title) == {"Snow day", "Bake sale"}
    assert (by_title["Snow day"].severity, len(by_title["Snow day"].detail)) == ("alert", 140)
    assert (by_title["Bake sale"].severity, by_title["Bake sale"].detail) == ("info", "")
    assert len(MD._announcement_feed(limit=1)) == 1


def test_announcement_feed_carries_the_published_date():
    AN.create_announcement({"title": "Snow day", "status": "Published",
                            "published_on": _iso(-1)})
    (item,) = MD._announcement_feed()
    assert item.when == _iso(-1)


def test_open_alerts_feed_lists_open_alerts():
    p = _pupil()
    EW.create({"pupil_id": p.pupil_id, "title": "Attendance falling",
               "raised_date": _iso(-2)})
    EW.create({"pupil_id": p.pupil_id, "title": "Closed one", "raised_date": _iso(-2),
               "status": "Dismissed", "resolution": "fine"})
    feed = MD._open_alerts_feed()
    assert [(f.kind, f.title, f.severity) for f in feed] == \
        [("alert", "Attendance falling", "alert")]


def test_open_alerts_feed_shows_details_and_raised_date():
    p = _pupil()
    EW.create({"pupil_id": p.pupil_id, "title": "Attendance falling",
               "details": "Down to 88% this half term", "raised_date": _iso(-2)})
    (item,) = MD._open_alerts_feed()
    assert item.detail == "Down to 88% this half term"
    assert item.when == _iso(-2)


# ── build_dashboard ──

def test_build_dashboard_empty_school():
    d = MD.build_dashboard()
    assert d.generated_on == TODAY.isoformat()
    assert [t.key for t in d.tiles] == ["students", "attendance", "open_targets",
                                        "high_risk", "today_events"]
    assert _tiles(d)["students"].value == "0"
    assert d.announcements == d.overdue_targets == d.high_risk_students == d.open_alerts == []


def test_safe_swallows_errors():
    def boom():
        raise RuntimeError("down")
    assert MD._safe(boom) is None
