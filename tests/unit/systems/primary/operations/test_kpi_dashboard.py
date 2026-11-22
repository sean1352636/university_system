"""KPI Dashboard (systems.primary.domain.operations.reporting.kpi_dashboard.kpi_dashboard).

The button tests check each tile on an empty school and with one pupil;
these check the figures across several pupils and dates.
"""

from __future__ import annotations

import datetime as dt

from education_system.systems.primary.domain.academics.attendance import attendance as ATT
from education_system.systems.primary.domain.finance.dinner_money import dinner_money as DM
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.reporting.kpi_dashboard import (
    kpi_dashboard as K,
)
from education_system.systems.primary.domain.pastoral.behaviour import behaviour as BH
from education_system.systems.primary.domain.staff import staff as ST

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _pupil(first="Ada", last="L", year="3", **kw):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": year,
                           "date_of_birth": "2019-01-01"}, **kw)


def _mark(pupil, days, am, pm=None):
    ATT.record_mark(pupil.pupil_id, _iso(days), "AM", am)
    if pm:
        ATT.record_mark(pupil.pupil_id, _iso(days), "PM", pm)


def _incident(pupil, itype, days=0):
    return BH.log_incident({"pupil_id": pupil.pupil_id, "incident_type": itype,
                            "incident_date": _iso(days), "description": "seen"})


# ── formatting helpers ──

def test_formatters():
    assert (K._fmt_int(1234), K._fmt_int(None), K._fmt_int(1.5)) == ("1,234", "—", "—")
    assert (K._fmt_pct(66.6), K._fmt_pct(None), K._fmt_pct(0)) == ("67%", "—", "0%")
    assert (K._fmt_money(1234.5), K._fmt_money(None), K._fmt_money(0.0)) == \
        ("£1,234.50", "—", "£0.00")


def test_date_window():
    start, end = K._date_window(7)
    assert (start, end) == (_iso(-7), TODAY.isoformat())


def test_safe_returns_default_on_error():
    def boom():
        raise RuntimeError("x")
    assert K._safe(boom, default="d") == "d"
    assert K._safe(lambda: 5) == 5


# ── counts ──

def test_student_count_is_on_roll_only():
    _pupil("A")
    _pupil("B")
    _pupil("C", roll_status="applicant")
    left = _pupil("D")
    P.set_roll_status(left.pupil_id, "left", left_date=_iso(-1))
    tile = K.kpi_student_count()
    assert (tile.label, tile.value, tile.hint) == ("Students", "2", "On roll")


def test_staff_count():
    for i in range(3):
        ST.create_staff({"first_name": f"S{i}", "last_name": "Staff"})
    assert K.kpi_staff_count().value == "3"


# ── attendance ──

def test_today_attendance_excludes_not_required():
    a, b, c = _pupil("A"), _pupil("B"), _pupil("C")
    _mark(a, 0, "P", "L")      # 2 attending
    _mark(b, 0, "I", "O")      # 2 absent
    _mark(c, 0, "X", "P")      # X not possible; 1 attending
    _mark(a, -1, "O", "O")     # yesterday: ignored by today's tile
    tile = K.kpi_today_attendance()
    assert (tile.value, tile.hint) == ("60%", "3/5 present or late")


def test_window_attendance_bounds():
    a = _pupil("A")
    _mark(a, 0, "P", "P")
    _mark(a, -7, "O", "P")          # first day of a 7-day window: counted
    _mark(a, -8, "O", "O")          # outside the window
    tile = K.kpi_window_attendance(7)
    assert (tile.label, tile.value, tile.hint) == ("7d attendance", "75%", "3/4 marks")
    wide = K.kpi_window_attendance(30)
    assert (wide.value, wide.hint) == ("50%", "3/6 marks")


def test_window_attendance_empty():
    tile = K.kpi_window_attendance(14)
    assert (tile.label, tile.value, tile.hint) == ("14d attendance", "—", "No marks in window")


def test_attendance_at_risk_threshold():
    good, edge, poor = _pupil("Good"), _pupil("Edge"), _pupil("Poor")
    for d in range(-4, 1):
        _mark(good, d, "P", "P")                       # 100%
        _mark(poor, d, "O", "P")                       # 50%
    for d in range(-4, 1):
        _mark(edge, d, "P", "P" if d != 0 else "O")    # 9/10 = 90%
    tile = K.kpi_attendance_at_risk(30, 90.0)
    assert (tile.label, tile.value, tile.hint) == \
        ("At-risk attendance", "1", "Below 90% in 30d")
    assert K.kpi_attendance_at_risk(30, 95.0).value == "2"
    assert K.kpi_attendance_at_risk(30, 50.0).value == "0"


def test_attendance_at_risk_ignores_not_required_only_pupils():
    p = _pupil()
    _mark(p, 0, "X", "X")
    assert K.kpi_attendance_at_risk(30, 90.0).value == "0"


# ── behaviour ──

def test_recent_behaviour_counts_window_and_negatives():
    a, b = _pupil("A"), _pupil("B")
    _incident(a, "Achievement")
    _incident(a, "Disruption", days=-3)
    _incident(b, "Bullying", days=-10)
    _incident(b, "Lateness", days=-11)   # outside a 10-day window
    tile = K.kpi_recent_behaviour(10)
    assert (tile.label, tile.value, tile.hint) == ("10d behaviour", "3", "2 negative")
    assert K.kpi_recent_behaviour(1).value == "1"


# ── dinner money ──

def test_dinner_money_owed_sums_debtors_only():
    a, b, c = _pupil("A"), _pupil("B"), _pupil("C")
    DM.charge_meal(a.pupil_id, amount_pounds="2.50")
    DM.charge_meal(a.pupil_id, amount_pounds="2.50")
    DM.charge_meal(b.pupil_id, amount_pounds="2.50")
    DM.credit(b.pupil_id, amount_pounds="1.00")
    DM.credit(c.pupil_id, amount_pounds="10.00")
    tile = K.kpi_dinner_money_owed()
    assert (tile.value, tile.hint) == ("£6.50", "2 pupil(s) in debt")


# ── snapshot ──

def test_snapshot_window_and_threshold_reach_the_tiles():
    p = _pupil()
    _mark(p, -20, "O", "O")
    _mark(p, 0, "P", "P")
    snap = K.snapshot(window_days=7, threshold_pct=60.0)
    assert snap.window_days == 7
    tiles = {t.label: t for t in snap.tiles}
    assert tiles["7d attendance"].value == "100%"
    assert tiles["At-risk attendance"].hint == "Below 60% in 7d"
    assert tiles["At-risk attendance"].value == "0"
    assert tiles["7d behaviour"].value == "0"
    assert dt.datetime.strptime(snap.generated_at, "%Y-%m-%d %H:%M")


def test_snapshot_default_window():
    snap = K.snapshot()
    labels = [t.label for t in snap.tiles]
    assert snap.window_days == K.DEFAULT_WINDOW_DAYS == 30
    assert labels == ["Students", "Staff", "Subjects", "Classes", "Today's attendance",
                      "30d attendance", "At-risk attendance", "30d behaviour",
                      "Dinner money owed", "Pupil Premium", "SEND pupils"]
