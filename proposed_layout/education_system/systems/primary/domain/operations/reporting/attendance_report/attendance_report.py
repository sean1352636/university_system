"""Attendance reporting — read-only aggregations over ``attendance``.

This module owns no data; it reads ``attendance_records`` (via the
existing ``attendance`` module) and rolls the data into the kinds of
summary a Head or DSL asks for:

* Cohort attendance % for a date range, optionally per year group
* Persistent absentees (overall attendance below a threshold)
* Per-pupil detailed breakdown
* Day-by-day register summaries
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from education_system.systems.primary.domain.academics.attendance import (
    attendance as att_data,
)
from education_system.systems.primary.domain.academics.attendance.attendance import (
    AUTH_ABSENT_LIKE, MARK_CODES, PRESENT_LIKE, UNAUTH_ABSENT_LIKE,
)
from education_system.systems.primary.domain.learners.pupils import (
    pupils as pupils_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)

# DfE threshold for "persistent absentee" status.
PERSISTENT_ABSENCE_THRESHOLD_PCT = 90.0


@dataclass
class PupilAttendance:
    pupil_id: str
    full_name: str
    year_group: str
    total_sessions: int
    present: int
    late: int
    authorised_absent: int
    unauthorised_absent: int
    other: int

    @property
    def attendance_pct(self) -> float:
        if self.total_sessions == 0:
            return 0.0
        return round(100.0 * (self.present + self.late) / self.total_sessions, 2)

    @property
    def absence_pct(self) -> float:
        return round(100.0 - self.attendance_pct, 2)

    @property
    def is_persistent_absentee(self) -> bool:
        return (self.total_sessions > 0
                and self.attendance_pct < PERSISTENT_ABSENCE_THRESHOLD_PCT)


def _validate_range(from_date: str | None,
                    to_date: str | None) -> tuple[str | None, str | None]:
    if from_date:
        att_data._validate_date(from_date, "From date")
    if to_date:
        att_data._validate_date(to_date, "To date")
    if from_date and to_date and to_date < from_date:
        raise ValidationError("to_date cannot be earlier than from_date")
    return from_date, to_date


def _category_counts(records: Iterable[Any]) -> dict[str, int]:
    counts = {"present": 0, "late": 0, "auth_absent": 0,
              "unauth_absent": 0, "other": 0}
    for r in records:
        cat = MARK_CODES.get(r.mark, (None, None))[1]
        if cat == "late":
            counts["late"] += 1
        elif cat in PRESENT_LIKE:
            counts["present"] += 1
        elif cat in AUTH_ABSENT_LIKE:
            counts["auth_absent"] += 1
        elif cat in UNAUTH_ABSENT_LIKE:
            counts["unauth_absent"] += 1
        else:
            counts["other"] += 1
    return counts


def _query_records(*, from_date: str | None = None,
                   to_date: str | None = None,
                   pupil_ids: list[str] | None = None,
                   year_group: str | None = None) -> list[Any]:
    """Pull raw rows from ``attendance_records`` for the given filter.

    Uses the attendance module's connection helper so we stay on the
    same database file.
    """
    att_data.init_db()
    where: list[str] = []
    params: list[Any] = []
    if from_date:
        where.append("date >= ?")
        params.append(from_date)
    if to_date:
        where.append("date <= ?")
        params.append(to_date)
    if pupil_ids:
        placeholders = ",".join("?" for _ in pupil_ids)
        where.append(f"pupil_id IN ({placeholders})")
        params.extend(pupil_ids)
    sql = "SELECT * FROM attendance_records"
    if where:
        sql += " WHERE " + " AND ".join(where)
    try:
        with att_data._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("attendance_report query failed")
        raise
    records = [att_data._row(r) for r in rows]
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        keep_ids = {p.pupil_id for p in pupils_data.list_pupils()
                    if p.year_group == year_group}
        records = [r for r in records if r.pupil_id in keep_ids]
    return records


def cohort_summary(*, from_date: str | None = None,
                   to_date: str | None = None,
                   year_group: str | None = None) -> dict[str, Any]:
    """Total counts across every pupil in the filter."""
    _validate_range(from_date, to_date)
    records = _query_records(from_date=from_date, to_date=to_date,
                             year_group=year_group)
    counts = _category_counts(records)
    total = sum(counts.values())
    present_or_late = counts["present"] + counts["late"]
    pct = round(100.0 * present_or_late / total, 2) if total else 0.0
    return {
        "from_date": from_date,
        "to_date": to_date,
        "year_group": year_group,
        "sessions": total,
        **counts,
        "attendance_pct": pct,
        "unique_pupils": len({r.pupil_id for r in records}),
    }


def by_year_group(*, from_date: str | None = None,
                  to_date: str | None = None) -> list[dict[str, Any]]:
    """One row per year group with attendance stats for the range."""
    _validate_range(from_date, to_date)
    out: list[dict[str, Any]] = []
    for yg in YEAR_GROUPS:
        out.append(cohort_summary(
            from_date=from_date, to_date=to_date, year_group=yg))
    return out


def pupil_attendance(*, from_date: str | None = None,
                     to_date: str | None = None,
                     year_group: str | None = None,
                     pupil_id: str | None = None) -> list[PupilAttendance]:
    """Per-pupil rollup."""
    _validate_range(from_date, to_date)
    pupil_ids: list[str] | None = None
    if pupil_id:
        if pupils_data.get_pupil(pupil_id) is None:
            raise ValidationError(f"No pupil with id {pupil_id}")
        pupil_ids = [pupil_id.strip()]
    records = _query_records(from_date=from_date, to_date=to_date,
                             pupil_ids=pupil_ids, year_group=year_group)
    by_pupil: dict[str, list[Any]] = {}
    for r in records:
        by_pupil.setdefault(r.pupil_id, []).append(r)
    rollups: list[PupilAttendance] = []
    for pid, recs in by_pupil.items():
        p = pupils_data.get_pupil(pid)
        if p is None:
            continue
        counts = _category_counts(recs)
        rollups.append(PupilAttendance(
            pupil_id=p.pupil_id,
            full_name=p.full_name,
            year_group=p.year_group,
            total_sessions=sum(counts.values()),
            present=counts["present"],
            late=counts["late"],
            authorised_absent=counts["auth_absent"],
            unauthorised_absent=counts["unauth_absent"],
            other=counts["other"],
        ))
    rollups.sort(key=lambda r: (r.attendance_pct, r.year_group,
                                r.full_name))
    return rollups


def persistent_absentees(*, from_date: str | None = None,
                         to_date: str | None = None,
                         year_group: str | None = None,
                         threshold_pct: float = PERSISTENT_ABSENCE_THRESHOLD_PCT,
                         ) -> list[PupilAttendance]:
    if not (0.0 <= threshold_pct <= 100.0):
        raise ValidationError("threshold_pct must be between 0 and 100")
    rows = pupil_attendance(from_date=from_date, to_date=to_date,
                            year_group=year_group)
    return [r for r in rows
            if r.total_sessions > 0 and r.attendance_pct < threshold_pct]


def daily_breakdown(*, from_date: str,
                    to_date: str,
                    year_group: str | None = None) -> list[dict[str, Any]]:
    """One row per date in the range."""
    _validate_range(from_date, to_date)
    if not from_date or not to_date:
        raise ValidationError("Both from_date and to_date are required")
    records = _query_records(from_date=from_date, to_date=to_date,
                             year_group=year_group)
    by_date: dict[str, list[Any]] = {}
    for r in records:
        by_date.setdefault(r.date, []).append(r)
    out: list[dict[str, Any]] = []
    for date in sorted(by_date):
        recs = by_date[date]
        counts = _category_counts(recs)
        total = sum(counts.values())
        pct = (100.0 * (counts["present"] + counts["late"]) / total
               if total else 0.0)
        out.append({
            "date": date,
            "sessions": total,
            **counts,
            "attendance_pct": round(pct, 2),
        })
    return out


def export_csv(path: str | Path, rows: list[PupilAttendance]) -> int:
    """Write per-pupil rollup to CSV. Returns rows written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "pupil_id", "full_name", "year_group", "total_sessions",
        "present", "late", "authorised_absent", "unauthorised_absent",
        "other", "attendance_pct", "absence_pct", "persistent_absentee",
    ]
    try:
        with p.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for r in rows:
                writer.writerow([
                    r.pupil_id, r.full_name, r.year_group,
                    r.total_sessions, r.present, r.late,
                    r.authorised_absent, r.unauthorised_absent, r.other,
                    f"{r.attendance_pct:.2f}", f"{r.absence_pct:.2f}",
                    "yes" if r.is_persistent_absentee else "no",
                ])
    except OSError as e:
        logger.exception("export_csv failed writing %s", p)
        raise ValidationError(f"Could not write CSV: {e}") from e
    logger.info("Attendance export wrote %d row(s) to %s", len(rows), p)
    return len(rows)


def default_term_range() -> tuple[str, str]:
    """Return a sensible default range — the last 30 days."""
    today = _dt.date.today()
    return (today - _dt.timedelta(days=30)).isoformat(), today.isoformat()
