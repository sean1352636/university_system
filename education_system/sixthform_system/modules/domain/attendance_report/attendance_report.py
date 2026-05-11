"""Attendance reporting for the Sixth Form System.

This is a **read-only reporting layer** on top of the
``attendance_records`` table. No new schema — every function here is
an aggregation/projection of what's already stored.

Reports it produces:

* ``cohort_report``       — totals + percentage across all students
                            (optionally filtered by group, date).
* ``per_student_report``  — totals + breakdown by status, by
                            day-of-week, and a trend over time.
* ``per_group_report``    — per-student attendance for one class
                            group, sorted by lowest percentage.
* ``daily_breakdown``     — present/late/absent counts per date.
* ``by_dow_breakdown``    — percentages by day-of-week (cohort-wide).
* ``risk_report``         — students below a configurable attendance
                            threshold over a window.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.sixthform_system.modules.domain.attendance import attendance as _att
from education_system.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.ATTENDANCE_DB

STATUSES: tuple[str, ...] = ("Present", "Late", "Absent", "Authorised")
ATTENDING_STATUSES: tuple[str, ...] = ("Present", "Late")

DOW_NAMES: tuple[str, ...] = (
    "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── DB access ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    _att.init_db()


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _validate_date(v: Any, label: str, *,
                    required: bool = False) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _date_window(window_days: int) -> tuple[str, str]:
    today = _dt.date.today()
    start = today - _dt.timedelta(days=window_days)
    return start.isoformat(), today.isoformat()


def _resolve_window(date_from: str | None,
                      date_to: str | None,
                      window_days: int) -> tuple[str, str]:
    df = _validate_date(date_from, "date_from")
    dt = _validate_date(date_to, "date_to")
    if df is None or dt is None:
        ws, we = _date_window(window_days)
        df = df or ws
        dt = dt or we
    if df > dt:
        raise ValidationError("date_from cannot be after date_to")
    return df, dt


# ── Result types ─────────────────────────────────────────────────

@dataclass
class StatusBreakdown:
    present:    int = 0
    late:       int = 0
    absent:     int = 0
    authorised: int = 0

    @property
    def total(self) -> int:
        return self.present + self.late + self.absent + self.authorised

    @property
    def attending(self) -> int:
        return self.present + self.late

    @property
    def percentage(self) -> float | None:
        if self.total == 0:
            return None
        return round(100.0 * self.attending / self.total, 1)


@dataclass
class CohortReport:
    date_from: str
    date_to: str
    breakdown: StatusBreakdown
    student_count: int
    sessions: int
    students_below_threshold: int
    threshold_pct: float


@dataclass
class StudentRow:
    student_id: str
    full_name: str
    breakdown: StatusBreakdown


@dataclass
class GroupReport:
    group_id: int
    group_name: str
    date_from: str
    date_to: str
    total_members: int
    breakdown: StatusBreakdown
    rows: list[StudentRow]


@dataclass
class StudentReport:
    student_id: str
    full_name: str
    date_from: str
    date_to: str
    breakdown: StatusBreakdown
    by_dow: dict[str, StatusBreakdown]
    daily_trend: list[tuple[str, StatusBreakdown]]
    recent_lates: int
    recent_absences: int


@dataclass
class DailyRow:
    date: str
    breakdown: StatusBreakdown


@dataclass
class DowRow:
    dow: str
    breakdown: StatusBreakdown


@dataclass
class RiskRow:
    student_id: str
    full_name: str
    breakdown: StatusBreakdown
    reasons: list[str] = field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────────

def _count_to_breakdown(rows: list[sqlite3.Row]) -> StatusBreakdown:
    b = StatusBreakdown()
    for r in rows:
        n = r["n"]
        st = r["status"]
        if st == "Present":
            b.present += n
        elif st == "Late":
            b.late += n
        elif st == "Absent":
            b.absent += n
        elif st == "Authorised":
            b.authorised += n
    return b


def _group_clause(group_id: int | None) -> tuple[str, list[Any]]:
    if group_id is None:
        return "", []
    return (
        " AND slot_id IN (SELECT slot_id FROM timetable_slots "
        "                  WHERE group_id = ?)",
        [group_id],
    )


# ── Cohort report ───────────────────────────────────────────────

def cohort_report(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    window_days: int = 28,
    group_id: int | None = None,
    threshold_pct: float = 90.0,
) -> CohortReport:
    init_db()
    df, dt = _resolve_window(date_from, date_to, window_days)
    gc, ga = _group_clause(group_id)

    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT status, COUNT(*) AS n
                  FROM attendance_records
                 WHERE date >= ? AND date <= ?{gc}
                 GROUP BY status""",
            [df, dt] + ga,
        ).fetchall()
        breakdown = _count_to_breakdown(rows)

        sc = conn.execute(
            f"""SELECT COUNT(DISTINCT student_id) AS n
                  FROM attendance_records
                 WHERE date >= ? AND date <= ?{gc}""",
            [df, dt] + ga,
        ).fetchone()
        students = sc["n"] or 0

        sess = conn.execute(
            f"""SELECT COUNT(DISTINCT (slot_id || '|' || date)) AS n
                  FROM attendance_records
                 WHERE date >= ? AND date <= ?{gc}""",
            [df, dt] + ga,
        ).fetchone()
        sessions = sess["n"] or 0

    # Below-threshold count.
    below = 0
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT student_id, status, COUNT(*) AS n
                  FROM attendance_records
                 WHERE date >= ? AND date <= ?{gc}
                 GROUP BY student_id, status""",
            [df, dt] + ga,
        ).fetchall()
    by_student: dict[str, StatusBreakdown] = {}
    for r in rows:
        b = by_student.setdefault(r["student_id"], StatusBreakdown())
        if r["status"] == "Present":
            b.present = r["n"]
        elif r["status"] == "Late":
            b.late = r["n"]
        elif r["status"] == "Absent":
            b.absent = r["n"]
        elif r["status"] == "Authorised":
            b.authorised = r["n"]
    for sid, b in by_student.items():
        pct = b.percentage
        if pct is not None and pct < threshold_pct:
            below += 1

    return CohortReport(
        date_from=df, date_to=dt,
        breakdown=breakdown,
        student_count=students,
        sessions=sessions,
        students_below_threshold=below,
        threshold_pct=threshold_pct,
    )


# ── Per-student report ─────────────────────────────────────────

def per_student_report(
    student_id: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    window_days: int = 84,
) -> StudentReport:
    init_db()
    from education_system.sixthform_system.modules.domain.students import students as _students
    student = _students.get_student(student_id)
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    df, dt = _resolve_window(date_from, date_to, window_days)

    with _connect() as conn:
        rows = conn.execute(
            """SELECT status, COUNT(*) AS n
                  FROM attendance_records
                 WHERE student_id = ?
                   AND date >= ? AND date <= ?
                 GROUP BY status""",
            (student_id, df, dt)).fetchall()
        breakdown = _count_to_breakdown(rows)

        date_rows = conn.execute(
            """SELECT date, status, COUNT(*) AS n
                  FROM attendance_records
                 WHERE student_id = ?
                   AND date >= ? AND date <= ?
                 GROUP BY date, status
                 ORDER BY date""",
            (student_id, df, dt)).fetchall()

    by_dow: dict[str, StatusBreakdown] = {d: StatusBreakdown()
                                              for d in DOW_NAMES}
    daily: dict[str, StatusBreakdown] = {}
    for r in date_rows:
        d = r["date"]
        st = r["status"]
        n = r["n"]
        try:
            dow_idx = _dt.date.fromisoformat(d).weekday()
            dow = DOW_NAMES[dow_idx]
        except (ValueError, TypeError):
            continue
        bb = by_dow[dow]
        if st == "Present":   bb.present    += n
        elif st == "Late":    bb.late       += n
        elif st == "Absent":  bb.absent     += n
        elif st == "Authorised": bb.authorised += n

        db = daily.setdefault(d, StatusBreakdown())
        if st == "Present":   db.present    += n
        elif st == "Late":    db.late       += n
        elif st == "Absent":  db.absent     += n
        elif st == "Authorised": db.authorised += n

    daily_trend = sorted(daily.items())

    # Recent (last 28 days) lates/absences are useful at-a-glance.
    today = _dt.date.fromisoformat(dt)
    recent_start = (today - _dt.timedelta(days=28)).isoformat()
    rec_lates = sum(b.late for d, b in daily.items() if d >= recent_start)
    rec_abs   = sum(b.absent for d, b in daily.items() if d >= recent_start)

    return StudentReport(
        student_id=student.student_id,
        full_name=student.full_name,
        date_from=df, date_to=dt,
        breakdown=breakdown,
        by_dow=by_dow,
        daily_trend=daily_trend,
        recent_lates=rec_lates,
        recent_absences=rec_abs,
    )


# ── Per-group report ────────────────────────────────────────────

def per_group_report(
    group_id: int,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    window_days: int = 28,
) -> GroupReport:
    init_db()
    from education_system.sixthform_system.modules.domain.class_groups import class_groups as _cg
    group = _cg.get_group(group_id)
    if group is None:
        raise ValidationError(f"No group with id {group_id}")
    df, dt = _resolve_window(date_from, date_to, window_days)

    member_ids = list(_cg.list_members(group_id))
    if not member_ids:
        return GroupReport(
            group_id=group.group_id, group_name=group.group_name,
            date_from=df, date_to=dt,
            total_members=0,
            breakdown=StatusBreakdown(),
            rows=[])

    placeholders = ",".join("?" * len(member_ids))
    with _connect() as conn:
        gc, ga = _group_clause(group_id)
        rows = conn.execute(
            f"""SELECT status, COUNT(*) AS n
                  FROM attendance_records
                 WHERE date >= ? AND date <= ?{gc}
                 GROUP BY status""",
            [df, dt] + ga,
        ).fetchall()
        breakdown = _count_to_breakdown(rows)

        per_student_rows = conn.execute(
            f"""SELECT student_id, status, COUNT(*) AS n
                  FROM attendance_records
                 WHERE date >= ? AND date <= ?{gc}
                   AND student_id IN ({placeholders})
                 GROUP BY student_id, status""",
            [df, dt] + ga + member_ids,
        ).fetchall()
        from education_system.sixthform_system.modules.domain.students import students as _students
    name_map = {s.student_id: s.full_name
                 for s in _students.list_students()}

    by_student: dict[str, StatusBreakdown] = {sid: StatusBreakdown()
                                                  for sid in member_ids}
    for r in per_student_rows:
        b = by_student.setdefault(r["student_id"], StatusBreakdown())
        if r["status"] == "Present":     b.present    = r["n"]
        elif r["status"] == "Late":      b.late       = r["n"]
        elif r["status"] == "Absent":    b.absent     = r["n"]
        elif r["status"] == "Authorised": b.authorised = r["n"]

    student_rows = [
        StudentRow(student_id=sid,
                     full_name=name_map.get(sid, sid),
                     breakdown=b)
        for sid, b in by_student.items()
    ]
    student_rows.sort(key=lambda r: (
        # No data first (worst), then by ascending percentage.
        0 if r.breakdown.total == 0 else 1,
        r.breakdown.percentage if r.breakdown.percentage is not None else 0,
        r.full_name.lower(),
    ))

    return GroupReport(
        group_id=group.group_id, group_name=group.group_name,
        date_from=df, date_to=dt,
        total_members=len(member_ids),
        breakdown=breakdown,
        rows=student_rows,
    )


# ── Daily breakdown ─────────────────────────────────────────────

def daily_breakdown(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    window_days: int = 28,
    group_id: int | None = None,
) -> list[DailyRow]:
    init_db()
    df, dt = _resolve_window(date_from, date_to, window_days)
    gc, ga = _group_clause(group_id)
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT date, status, COUNT(*) AS n
                  FROM attendance_records
                 WHERE date >= ? AND date <= ?{gc}
                 GROUP BY date, status
                 ORDER BY date""",
            [df, dt] + ga,
        ).fetchall()
    daily: dict[str, StatusBreakdown] = {}
    for r in rows:
        b = daily.setdefault(r["date"], StatusBreakdown())
        st = r["status"]
        n = r["n"]
        if st == "Present":      b.present    += n
        elif st == "Late":       b.late       += n
        elif st == "Absent":     b.absent     += n
        elif st == "Authorised": b.authorised += n
    return [DailyRow(date=d, breakdown=b)
             for d, b in sorted(daily.items())]


# ── Day-of-week breakdown ──────────────────────────────────────

def by_dow_breakdown(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    window_days: int = 84,
    group_id: int | None = None,
) -> list[DowRow]:
    init_db()
    df, dt = _resolve_window(date_from, date_to, window_days)
    gc, ga = _group_clause(group_id)
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT date, status, COUNT(*) AS n
                  FROM attendance_records
                 WHERE date >= ? AND date <= ?{gc}
                 GROUP BY date, status""",
            [df, dt] + ga,
        ).fetchall()
    by_dow: dict[str, StatusBreakdown] = {d: StatusBreakdown()
                                              for d in DOW_NAMES}
    for r in rows:
        try:
            dow_idx = _dt.date.fromisoformat(r["date"]).weekday()
            dow = DOW_NAMES[dow_idx]
        except (ValueError, TypeError):
            continue
        b = by_dow[dow]
        st = r["status"]
        n = r["n"]
        if st == "Present":      b.present    += n
        elif st == "Late":       b.late       += n
        elif st == "Absent":     b.absent     += n
        elif st == "Authorised": b.authorised += n
    return [DowRow(dow=d, breakdown=by_dow[d]) for d in DOW_NAMES]


# ── Risk report ─────────────────────────────────────────────────

def risk_report(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    window_days: int = 28,
    threshold_pct: float = 90.0,
    max_lates: int = 5,
    max_absences: int = 3,
) -> list[RiskRow]:
    init_db()
    df, dt = _resolve_window(date_from, date_to, window_days)
    with _connect() as conn:
        rows = conn.execute(
            """SELECT student_id, status, COUNT(*) AS n
                  FROM attendance_records
                 WHERE date >= ? AND date <= ?
                 GROUP BY student_id, status""",
            (df, dt)).fetchall()
    by_student: dict[str, StatusBreakdown] = {}
    for r in rows:
        b = by_student.setdefault(r["student_id"], StatusBreakdown())
        st = r["status"]
        n = r["n"]
        if st == "Present":      b.present    = n
        elif st == "Late":       b.late       = n
        elif st == "Absent":     b.absent     = n
        elif st == "Authorised": b.authorised = n
        from education_system.sixthform_system.modules.domain.students import students as _students
    names = {s.student_id: s.full_name
              for s in _students.list_students()}

    out: list[RiskRow] = []
    for sid, b in by_student.items():
        reasons: list[str] = []
        pct = b.percentage
        if pct is not None and pct < threshold_pct:
            reasons.append(f"Attendance {pct}% < {threshold_pct}%")
        if b.late > max_lates:
            reasons.append(f"{b.late} lates (>{max_lates})")
        if b.absent > max_absences:
            reasons.append(f"{b.absent} absences (>{max_absences})")
        if reasons:
            out.append(RiskRow(
                student_id=sid,
                full_name=names.get(sid, sid),
                breakdown=b,
                reasons=reasons,
            ))
    out.sort(key=lambda r: (r.breakdown.percentage
                              if r.breakdown.percentage is not None
                              else 0))
    return out
