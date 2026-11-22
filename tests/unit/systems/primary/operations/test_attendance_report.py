"""Attendance reporting
(systems.primary.domain.operations.reporting.attendance_report.attendance_report)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.primary.domain.academics.attendance import attendance as ATT
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.reporting.attendance_report import (
    attendance_report as AR,
)

MON, TUE, WED, THU, FRI = (f"2030-01-{d:02d}" for d in range(7, 12))


def _pupil(first, last, year):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": year,
                           "date_of_birth": "2020-01-01"})


def _marks(pupil, marks):
    """marks: {date: (am, pm)}"""
    for date, (am, pm) in marks.items():
        if am:
            ATT.record_mark(pupil.pupil_id, date, "AM", am)
        if pm:
            ATT.record_mark(pupil.pupil_id, date, "PM", pm)


def _school():
    """Three pupils, hand-computed:

    * Ann (Y3): P L / I O        -> 2 of 4 present-or-late = 50%
    * Ben (Y3): / \\ P P P P      -> 6 of 6 = 100%
    * Cal (Y5): nine P + one O   -> 9 of 10 = 90% (on the threshold, not persistent)
    """
    ann = _pupil("Ann", "Absent", "3")
    ben = _pupil("Ben", "Better", "3")
    cal = _pupil("Cal", "Close", "5")
    _marks(ann, {MON: ("P", "L"), TUE: ("I", "O")})
    _marks(ben, {MON: ("/", "\\"), TUE: ("P", "P"), WED: ("P", "P")})
    _marks(cal, {MON: ("P", "P"), TUE: ("P", "P"), WED: ("P", "P"), THU: ("P", "P"),
                 FRI: ("P", "O")})
    return ann, ben, cal


# ── PupilAttendance ──

def test_pupil_attendance_properties():
    row = AR.PupilAttendance("X", "X Y", "3", total_sessions=8, present=5, late=1,
                             authorised_absent=1, unauthorised_absent=1, other=0)
    assert (row.attendance_pct, row.absence_pct, row.is_persistent_absentee) == (75.0, 25.0, True)
    empty = AR.PupilAttendance("X", "X Y", "3", 0, 0, 0, 0, 0, 0)
    assert (empty.attendance_pct, empty.is_persistent_absentee) == (0.0, False)


# ── cohort ──

def test_cohort_summary_whole_school():
    _school()
    s = AR.cohort_summary()
    assert s == {"from_date": None, "to_date": None, "year_group": None, "sessions": 20,
                 "present": 16, "late": 1, "auth_absent": 1, "unauth_absent": 2, "other": 0,
                 "attendance_pct": 85.0, "unique_pupils": 3}


def test_cohort_summary_year_group_and_range():
    _school()
    y3 = AR.cohort_summary(year_group="3")
    assert (y3["sessions"], y3["present"], y3["late"], y3["attendance_pct"],
            y3["unique_pupils"]) == (10, 7, 1, 80.0, 2)
    tue = AR.cohort_summary(from_date=TUE, to_date=TUE)
    assert (tue["sessions"], tue["present"], tue["auth_absent"], tue["unauth_absent"],
            tue["attendance_pct"]) == (6, 4, 1, 1, 66.67)


def test_cohort_summary_empty():
    s = AR.cohort_summary()
    assert (s["sessions"], s["attendance_pct"], s["unique_pupils"]) == (0, 0.0, 0)


def test_by_year_group_has_every_year():
    _school()
    rows = AR.by_year_group()
    assert [r["year_group"] for r in rows] == list(P.YEAR_GROUPS)
    pct = {r["year_group"]: r["attendance_pct"] for r in rows}
    assert (pct["3"], pct["5"], pct["R"]) == (80.0, 90.0, 0.0)
    assert sum(r["sessions"] for r in rows) == 20


def test_excluded_counts_as_other():
    p = _pupil("Ed", "Ex", "4")
    _marks(p, {MON: ("P", "E")})
    s = AR.cohort_summary()
    assert (s["present"], s["other"], s["attendance_pct"]) == (1, 1, 50.0)


def test_not_required_sessions_are_not_possible_sessions():
    # DfE: code X (not required to attend) is not a possible session, so it
    # must not drag the attendance figure down.
    p = _pupil("Xena", "Nonreq", "R")
    _marks(p, {MON: ("P", "X")})
    assert AR.pupil_attendance()[0].attendance_pct == 100.0


# ── per pupil ──

def test_pupil_attendance_rollup_sorted_worst_first():
    ann, ben, cal = _school()
    rows = AR.pupil_attendance()
    assert [r.pupil_id for r in rows] == [ann.pupil_id, cal.pupil_id, ben.pupil_id]
    a = rows[0]
    assert (a.full_name, a.year_group, a.total_sessions, a.present, a.late,
            a.authorised_absent, a.unauthorised_absent, a.other) == \
        ("Ann Absent", "3", 4, 1, 1, 1, 1, 0)
    assert [r.attendance_pct for r in rows] == [50.0, 90.0, 100.0]


def test_pupil_attendance_filters():
    ann, ben, cal = _school()
    only = AR.pupil_attendance(pupil_id=cal.pupil_id)
    assert [(r.pupil_id, r.total_sessions) for r in only] == [(cal.pupil_id, 10)]
    y3 = AR.pupil_attendance(year_group="3")
    assert {r.pupil_id for r in y3} == {ann.pupil_id, ben.pupil_id}
    mon = AR.pupil_attendance(from_date=MON, to_date=MON)
    assert all(r.total_sessions == 2 for r in mon) and len(mon) == 3
    with pytest.raises(AR.ValidationError, match="No pupil with id NOPE"):
        AR.pupil_attendance(pupil_id="NOPE")


def test_persistent_absentees_threshold():
    ann, ben, cal = _school()
    assert [r.pupil_id for r in AR.persistent_absentees()] == [ann.pupil_id]
    assert [r.pupil_id for r in AR.persistent_absentees(threshold_pct=95)] == \
        [ann.pupil_id, cal.pupil_id]
    assert AR.persistent_absentees(threshold_pct=0) == []
    with pytest.raises(AR.ValidationError, match="threshold_pct must be between 0 and 100"):
        AR.persistent_absentees(threshold_pct=101)
    with pytest.raises(AR.ValidationError, match="threshold_pct must be between 0 and 100"):
        AR.persistent_absentees(threshold_pct=-1)


# ── daily ──

def test_daily_breakdown():
    _school()
    rows = AR.daily_breakdown(from_date=MON, to_date=FRI)
    assert [(r["date"], r["sessions"], r["attendance_pct"]) for r in rows] == [
        (MON, 6, 100.0), (TUE, 6, 66.67), (WED, 4, 100.0), (THU, 2, 100.0), (FRI, 2, 50.0)]
    assert (rows[0]["present"], rows[0]["late"]) == (5, 1)
    assert (rows[1]["auth_absent"], rows[1]["unauth_absent"]) == (1, 1)
    y5 = AR.daily_breakdown(from_date=TUE, to_date=WED, year_group="5")
    assert [(r["date"], r["sessions"]) for r in y5] == [(TUE, 2), (WED, 2)]


def test_daily_breakdown_needs_both_dates():
    with pytest.raises(AR.ValidationError, match="Both from_date and to_date are required"):
        AR.daily_breakdown(from_date=MON, to_date="")


# ── validation ──

def test_range_validation():
    with pytest.raises(AR.ValidationError, match="to_date cannot be earlier than from_date"):
        AR.cohort_summary(from_date=TUE, to_date=MON)
    with pytest.raises(AR.ValidationError, match="From date must be YYYY-MM-DD"):
        AR.cohort_summary(from_date="7/1/2030")
    with pytest.raises(AR.ValidationError, match="To date is not a real date"):
        AR.by_year_group(to_date="2030-02-30")


def test_year_group_filter_must_be_known():
    with pytest.raises(AR.ValidationError, match="Year filter must be one of"):
        AR.cohort_summary(year_group="7")


# ── export ──

def test_export_csv(tmp_path):
    ann, ben, cal = _school()
    rows = AR.pupil_attendance()
    out = tmp_path / "nested" / "attendance.csv"
    assert AR.export_csv(out, rows) == 3
    with out.open(newline="", encoding="utf-8") as fh:
        data = list(csv.DictReader(fh))
    assert [d["pupil_id"] for d in data] == [ann.pupil_id, cal.pupil_id, ben.pupil_id]
    first = data[0]
    assert (first["full_name"], first["total_sessions"], first["late"],
            first["attendance_pct"], first["absence_pct"], first["persistent_absentee"]) == \
        ("Ann Absent", "4", "1", "50.00", "50.00", "yes")
    assert (data[1]["attendance_pct"], data[1]["persistent_absentee"]) == ("90.00", "no")


def test_export_csv_empty_writes_header_only(tmp_path):
    out = tmp_path / "empty.csv"
    assert AR.export_csv(out, []) == 0
    assert out.read_text(encoding="utf-8").splitlines() == [
        "pupil_id,full_name,year_group,total_sessions,present,late,authorised_absent,"
        "unauthorised_absent,other,attendance_pct,absence_pct,persistent_absentee"]


def test_export_csv_unwritable_path(tmp_path):
    folder = tmp_path / "a_folder"
    folder.mkdir()
    with pytest.raises(AR.ValidationError, match="Could not write CSV"):
        AR.export_csv(folder, [])


def test_default_term_range_is_last_30_days():
    start, end = AR.default_term_range()
    assert dt.date.fromisoformat(end) - dt.date.fromisoformat(start) == dt.timedelta(days=30)
    assert end == dt.date.today().isoformat()
