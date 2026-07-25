"""Domain layer for the Attendance Report + register (Nursery System).

Owns reads/aggregation over the ``attendance_records`` table — the daily
register (one row per child per session). It can also take/amend the register
via an UPSERT keyed on the unique ``(pupil_id, attend_date, session)`` index,
and aggregates the rows into attendance rates by child, room and date range.

Follows the 4-layer pattern: validation + aggregation + SQLite access here,
CLI in ``attendance_report_cli.py``, Tk GUI in ``attendance_report_views.py``.
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
import random
import re
import sqlite3
from pathlib import Path
from typing import Any

from education_system.systems.nursery.infrastructure import paths
from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Attendance Report"
CATEGORY = "Compliance & Reports"

STATUSES = ("present", "absent", "late", "sick", "holiday")
SESSIONS = ("all-day", "am", "pm")

ID_PREFIX = "NATT"
ID_DIGITS = 4

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid attendance input."""


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for attendance report")
        raise


def default_range() -> tuple[str, str]:
    """Default reporting window: (today - 30 days, today), inclusive."""
    today = _dt.date.today()
    start = today - _dt.timedelta(days=30)
    return start.isoformat(), today.isoformat()


# ── Validation ───────────────────────────────────────────────────────────────

def _check_date(value: str | None, label: str) -> str:
    v = (value or "").strip()
    if not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v


def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT record_id FROM attendance_records").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing attendance ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        rid = f"{ID_PREFIX}{n}"
        if rid not in existing:
            return rid
    raise RuntimeError("Could not allocate a unique attendance id")


# ── Reads ────────────────────────────────────────────────────────────────────

def active_children() -> list[tuple[str, str, str | None]]:
    """Return ``(pupil_id, display_name, room)`` for active children."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("active_children failed")
        raise
    return [
        (r["pupil_id"], f"{r['first_name']} {r['last_name']}", r["room"])
        for r in rows
    ]


def list_for_date(attend_date: str) -> list[dict[str, Any]]:
    """Register rows for a date, joined with the child's name."""
    _ensure_schema()
    d = _check_date(attend_date, "Date")
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT a.record_id, a.pupil_id, "
                "TRIM(p.first_name || ' ' || p.last_name) AS name, "
                "a.room, a.session, a.status, a.arrival_time, a.departure_time, "
                "a.absence_reason, a.notes "
                "FROM attendance_records a "
                "LEFT JOIN pupils p ON p.pupil_id = a.pupil_id "
                "WHERE a.attend_date = ? "
                "ORDER BY name, a.session", (d,)).fetchall()
    except sqlite3.Error:
        logger.exception("list_for_date(%s) failed", attend_date)
        raise
    return [dict(r) for r in rows]


# ── Writes (take register) ────────────────────────────────────────────────────

def mark_attendance(pupil_id: str, attend_date: str, status: str, *,
                    session: str = "all-day", arrival_time: str | None = None,
                    departure_time: str | None = None,
                    absence_reason: str | None = None,
                    notes: str | None = None, room: str | None = None) -> None:
    """UPSERT one register row for a child-date-session."""
    _ensure_schema()
    pid = (pupil_id or "").strip()
    if not pid:
        raise ValidationError("Child (pupil ID) is required")
    d = _check_date(attend_date, "Date")
    st = (status or "").strip().lower()
    if st not in STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(STATUSES))
    ses = (session or "all-day").strip().lower()
    if ses not in SESSIONS:
        raise ValidationError("Session must be one of: " + ", ".join(SESSIONS))
    rid = generate_record_id()
    try:
        with connect() as conn:
            pupil = conn.execute(
                "SELECT room FROM pupils WHERE pupil_id = ?", (pid,)).fetchone()
            if pupil is None:
                raise ValidationError(f"No child on roll with id {pid}")
            use_room = _opt(room) if room is not None else pupil["room"]
            conn.execute(
                """
                INSERT INTO attendance_records (
                    record_id, pupil_id, attend_date, room, session, status,
                    arrival_time, departure_time, absence_reason, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pupil_id, attend_date, session) DO UPDATE SET
                    room = excluded.room,
                    status = excluded.status,
                    arrival_time = excluded.arrival_time,
                    departure_time = excluded.departure_time,
                    absence_reason = excluded.absence_reason,
                    notes = excluded.notes
                """,
                (rid, pid, d, use_room, ses, st, _opt(arrival_time),
                 _opt(departure_time), _opt(absence_reason), _opt(notes)),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("mark_attendance failed for pupil=%s date=%s", pid, d)
        raise ValidationError(f"Could not save register row — {e}") from e
    logger.info("Marked %s as %s on %s (%s)", pid, st, d, ses)


# ── Aggregation / report ──────────────────────────────────────────────────────

def report(date_from: str, date_to: str, *,
           room: str | None = None) -> dict[str, Any]:
    """Aggregate the register over a date range into attendance rates."""
    _ensure_schema()
    lo = _check_date(date_from, "From date")
    hi = _check_date(date_to, "To date")
    rm = _opt(room)
    sql = (
        "SELECT a.pupil_id, "
        "TRIM(p.first_name || ' ' || p.last_name) AS name, "
        "a.room AS room, a.status AS status "
        "FROM attendance_records a "
        "LEFT JOIN pupils p ON p.pupil_id = a.pupil_id "
        "WHERE a.attend_date BETWEEN ? AND ?"
    )
    params: list[Any] = [lo, hi]
    if rm:
        sql += " AND a.room = ?"
        params.append(rm)
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("report(%s, %s) failed", lo, hi)
        raise

    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    per_child: dict[str, dict[str, Any]] = {}
    per_room: dict[str, dict[str, Any]] = {}
    total = 0
    for r in rows:
        st = r["status"]
        if st not in by_status:
            by_status[st] = 0
        by_status[st] += 1
        total += 1

        pid = r["pupil_id"]
        c = per_child.setdefault(pid, {
            "pupil_id": pid, "name": r["name"] or pid,
            "room": r["room"], **{s: 0 for s in STATUSES}, "total": 0})
        c[st] = c.get(st, 0) + 1
        c["total"] += 1

        rm_key = r["room"] or "(unassigned)"
        rr = per_room.setdefault(rm_key, {
            "room": rm_key, **{s: 0 for s in STATUSES}, "total": 0})
        rr[st] = rr.get(st, 0) + 1
        rr["total"] += 1

    def _rate(present: int, late: int, tot: int) -> float | None:
        return round((present + late) / tot * 100, 1) if tot else None

    attended = by_status.get("present", 0) + by_status.get("late", 0)
    absences = by_status.get("absent", 0) + by_status.get("sick", 0)
    for c in per_child.values():
        c["rate"] = _rate(c["present"], c["late"], c["total"])
    for rr in per_room.values():
        rr["rate"] = _rate(rr["present"], rr["late"], rr["total"])

    return {
        "date_from": lo,
        "date_to": hi,
        "by_status": by_status,
        "total": total,
        "attended": attended,
        "attendance_rate": round(attended / total * 100, 1) if total else None,
        "absence_rate": round(absences / total * 100, 1) if total else None,
        "per_child": sorted(per_child.values(), key=lambda c: c["name"]),
        "per_room": sorted(per_room.values(), key=lambda r: r["room"]),
    }


# ── Export ───────────────────────────────────────────────────────────────────

def export_csv(date_from: str, date_to: str, *, room: str | None = None,
               path: str | Path | None = None) -> dict[str, Any]:
    """Write the per-child breakdown to CSV; return path + row count."""
    rep = report(date_from, date_to, room=room)
    if path is None:
        paths.ensure_directories()
        path = paths.DATA_DIR / (
            f"attendance_report_{rep['date_from']}_to_{rep['date_to']}.csv")
    path = Path(path)
    headers = ["pupil_id", "name", "room", "present", "late", "absent",
               "sick", "holiday", "total", "rate"]
    rows = rep["per_child"]
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for c in rows:
                w.writerow([
                    c["pupil_id"], c["name"], c["room"] or "", c["present"],
                    c["late"], c["absent"], c["sick"], c["holiday"], c["total"],
                    "" if c["rate"] is None else c["rate"],
                ])
    except OSError as e:
        logger.exception("Could not write attendance CSV to %s", path)
        raise OSError(f"Could not write report — {e}") from e
    return {"path": str(path), "row_count": len(rows)}
