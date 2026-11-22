"""Data Dashboard (systems.primary.domain.operations.reporting.data_dashboard.data_dashboard).

The button tests check each panel on an empty school and with one pupil;
these check the rows, shares, ordering and totals across several pupils.
"""

from __future__ import annotations

import datetime as dt

from education_system.systems.primary.domain.academics.attendance import attendance as ATT
from education_system.systems.primary.domain.finance.dinner_money import dinner_money as DM
from education_system.systems.primary.domain.finance.pupil_premium import pupil_premium as PP
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.reporting.data_dashboard import (
    data_dashboard as DD,
)
from education_system.systems.primary.domain.pastoral.behaviour import behaviour as BH
from education_system.systems.primary.domain.pastoral.send import send as SEND

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _pupil(first="Ada", year="3", send=None):
    data = {"first_name": first, "last_name": "Test", "year_group": year,
            "date_of_birth": "2019-01-01"}
    if send:
        data["send_status"] = send
    return P.create_pupil(data)


def _rows(panel):
    return [(r.label, r.count, r.extra) for r in panel.rows]


# ── pupils by year group ──

def test_pupils_by_year_group_order_and_send_column():
    _pupil("A", "6")
    _pupil("B", "R", send="yes")
    _pupil("C", "R")
    _pupil("D", "2", send="yes")
    _pupil("E", "2", send="no")
    panel = DD.panel_pupils_by_year_group()
    assert panel.total == 5 and panel.note == ""
    assert _rows(panel) == [("Reception", 2, "1"), ("Year 2", 2, "1"), ("Year 6", 1, "0")]


def test_pupils_by_year_group_leaves_out_off_roll():
    _pupil("A", "1")
    gone = _pupil("B", "1")
    P.set_roll_status(gone.pupil_id, "left")
    assert _rows(DD.panel_pupils_by_year_group()) == [("Year 1", 1, "0")]


# ── attendance status ──

def test_attendance_status_shares_exclude_not_required():
    a, b = _pupil("A"), _pupil("B")
    for d, (am, pm) in {0: ("P", "L"), -1: ("I", "O"), -2: ("E", "X")}.items():
        ATT.record_mark(a.pupil_id, _iso(d), "AM", am)
        ATT.record_mark(a.pupil_id, _iso(d), "PM", pm)
    ATT.record_mark(b.pupil_id, _iso(0), "AM", "/")
    ATT.record_mark(b.pupil_id, _iso(-40), "AM", "O")   # outside 30d
    panel = DD.panel_attendance_status(30)
    assert panel.name == "Attendance status — last 30d"
    assert panel.total == 6
    assert _rows(panel) == [("Present", 2, "33%"), ("Late", 1, "17%"),
                            ("Authorised absence", 1, "17%"),
                            ("Unauthorised absence", 1, "17%"), ("Excluded", 1, "17%")]


def test_attendance_status_empty_window():
    a = _pupil()
    ATT.record_mark(a.pupil_id, _iso(-10), "AM", "P")
    panel = DD.panel_attendance_status(5)
    assert panel.note == "No attendance marks in window." and panel.rows == []


# ── daily attendance ──

def test_attendance_daily_most_recent_first():
    a, b = _pupil("A"), _pupil("B")
    ATT.record_mark(a.pupil_id, _iso(0), "AM", "P")
    ATT.record_mark(b.pupil_id, _iso(0), "AM", "O")
    ATT.record_mark(a.pupil_id, _iso(-1), "AM", "P")
    ATT.record_mark(a.pupil_id, _iso(-1), "PM", "L")
    ATT.record_mark(b.pupil_id, _iso(-1), "AM", "X")
    ATT.record_mark(b.pupil_id, _iso(-3), "AM", "I")
    panel = DD.panel_attendance_daily(7)
    assert panel.total == 5
    assert _rows(panel) == [(_iso(0), 2, "50%"), (_iso(-1), 2, "100%"), (_iso(-3), 1, "0%")]


def test_attendance_daily_only_not_required_marks():
    a = _pupil()
    ATT.record_mark(a.pupil_id, _iso(0), "AM", "X")
    panel = DD.panel_attendance_daily(7)
    assert panel.total == 0 and panel.rows == []


# ── behaviour ──

def test_behaviour_by_type_sorted_with_points():
    a, b = _pupil("A"), _pupil("B")
    for pupil, itype, pts, days in ((a, "Disruption", -2, 0), (b, "Disruption", -1, -1),
                                    (a, "Achievement", 3, 0), (b, "Bullying", -5, -2),
                                    (a, "Achievement", None, -3), (a, "Uniform", -1, -20)):
        BH.log_incident({"pupil_id": pupil.pupil_id, "incident_type": itype, "points": pts,
                         "incident_date": _iso(days), "description": "x"})
    panel = DD.panel_behaviour_by_category(7)
    assert panel.name == "Behaviour by type — last 7d"
    assert panel.total == 5
    assert _rows(panel) == [("Achievement", 2, "4"), ("Disruption", 2, "-3"),
                            ("Bullying", 1, "-5")]


def test_behaviour_empty_window():
    assert DD.panel_behaviour_by_category(7).note == "No behaviour incidents in window."


# ── dinner money ──

def test_dinner_money_groups_and_totals():
    a, b, c, d = _pupil("A"), _pupil("B"), _pupil("C"), _pupil("D")
    DM.charge_meal(a.pupil_id, amount_pence=250)
    DM.charge_meal(b.pupil_id, amount_pence=1000)
    DM.credit(c.pupil_id, amount_pence=500)
    DM.charge_meal(d.pupil_id, amount_pence=200)
    DM.credit(d.pupil_id, amount_pence=200)
    panel = DD.panel_dinner_money()
    assert panel.total == 4
    assert _rows(panel) == [("In debt", 2, "-£12.50"), ("Zero", 1, "£0.00"),
                            ("In credit", 1, "£5.00")]


# ── pupil premium / SEND ──

def test_pupil_premium_by_category():
    for i, cat in enumerate(("Service child", "Ever 6 FSM", "Service child", "Post-LAC")):
        PP.upsert({"pupil_id": _pupil(f"P{i}").pupil_id, "academic_year": "2025/26",
                   "category": cat})
    panel = DD.panel_pupil_premium()
    assert panel.total == 4
    assert [(r.label, r.count) for r in panel.rows] == \
        [("Service child", 2), ("Ever 6 FSM", 1), ("Post-LAC", 1)]


def test_send_by_stage():
    for i, stage in enumerate(("SEN Support", "Monitoring", "SEN Support")):
        SEND.upsert({"pupil_id": _pupil(f"S{i}").pupil_id, "academic_year": "2025/26",
                     "provision_stage": stage})
    panel = DD.panel_send_by_stage()
    assert panel.total == 3
    assert [(r.label, r.count) for r in panel.rows] == [("SEN Support", 2), ("Monitoring", 1)]


# ── snapshot ──

def test_build_panels_passes_window():
    a = _pupil()
    ATT.record_mark(a.pupil_id, _iso(-10), "AM", "P")
    snap = DD.build_panels(window_days=14)
    assert snap.window_days == 14
    names = [p.name for p in snap.panels]
    assert "Attendance status — last 14d" in names and "Daily attendance — last 14d" in names
    daily = next(p for p in snap.panels if p.name.startswith("Daily"))
    assert _rows(daily) == [(_iso(-10), 1, "100%")]
    short = DD.build_panels(window_days=5)
    daily5 = next(p for p in short.panels if p.name.startswith("Daily"))
    assert daily5.note == "No attendance marks in window."
