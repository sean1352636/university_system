"""Domain layer for Sleep Log (Nursery System).

Owns the ``sleep_log`` table — one row per nap. Captures when a child slept,
where (cot / sleep mat / buggy …), how many safer-sleep checks were carried
out, which member of staff supervised, and any notes. Where both a start and
end time are given the nap ``duration_minutes`` is derived automatically.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``sleep_log_cli.py``, Tk GUI in ``sleep_log_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Sleep Log"
CATEGORY = "Daily Care & Routines"

ID_PREFIX = "NSL"
ID_DIGITS = 3

LOCATIONS = ("Cot", "Sleep mat", "Buggy", "Pram", "Other")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid sleep-log input."""


@dataclass
class SleepRecord:
    sleep_id: str
    pupil_id: str
    sleep_date: str
    start_time: str | None
    end_time: str | None
    duration_minutes: int | None
    location: str | None
    checks: int
    staff_id: str | None
    notes: str | None
    child_name: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for sleep log")
        raise


_SELECT = """
SELECT s.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       TRIM(st.first_name || ' ' || st.last_name) AS staff_name
FROM sleep_log s
LEFT JOIN pupils p ON p.pupil_id = s.pupil_id
LEFT JOIN staff st ON st.staff_id = s.staff_id
"""


def _row(r: sqlite3.Row) -> SleepRecord:
    keys = r.keys()
    return SleepRecord(
        sleep_id=r["sleep_id"],
        pupil_id=r["pupil_id"],
        sleep_date=r["sleep_date"],
        start_time=r["start_time"],
        end_time=r["end_time"],
        duration_minutes=r["duration_minutes"],
        location=r["location"],
        checks=r["checks"],
        staff_id=r["staff_id"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        staff_name=r["staff_name"] if "staff_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _minutes_between(start: str, end: str) -> int:
    """Whole minutes from ``start`` to ``end`` (both ``HH:MM``).

    A negative span (end before start) is treated as 0 — naps do not cross
    midnight in a nursery setting, so an inverted pair is most likely a typo
    and should not silently produce a "negative nap".
    """
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    diff = (eh * 60 + em) - (sh * 60 + sm)
    return diff if diff > 0 else 0


def _opt_time(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if not v:
        return None
    if not _TIME_RE.match(v):
        raise ValidationError(f"{label} must be HH:MM (24-hour)")
    hh, mm = (int(x) for x in v.split(":"))
    if hh > 23 or mm > 59:
        raise ValidationError(f"{label} is not a valid time")
    return v


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    sleep_date = (data.get("sleep_date") or "").strip()
    if not sleep_date:
        sleep_date = _dt.date.today().isoformat()
    if not _DATE_RE.match(sleep_date):
        raise ValidationError("Sleep date must be YYYY-MM-DD")
    out["sleep_date"] = sleep_date

    start = _opt_time(data.get("start_time"), "Start time")
    end = _opt_time(data.get("end_time"), "End time")
    out["start_time"] = start
    out["end_time"] = end

    duration_raw = str(data.get("duration_minutes")
                       if data.get("duration_minutes") is not None else "").strip()
    if duration_raw:
        try:
            duration = int(float(duration_raw))
        except ValueError as e:
            raise ValidationError("Duration (minutes) must be a whole number") from e
        if duration < 0:
            raise ValidationError("Duration (minutes) cannot be negative")
        out["duration_minutes"] = duration
    elif start and end:
        out["duration_minutes"] = _minutes_between(start, end)
    else:
        out["duration_minutes"] = None

    checks_raw = str(data.get("checks") if data.get("checks") is not None else "").strip()
    if not checks_raw:
        checks = 0
    else:
        try:
            checks = int(float(checks_raw))
        except ValueError as e:
            raise ValidationError("Checks must be a whole number") from e
    if checks < 0:
        raise ValidationError("Checks cannot be negative")
    out["checks"] = checks

    out["location"] = _opt(data.get("location"))
    out["staff_id"] = _opt(data.get("staff_id"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT sleep_id FROM sleep_log").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing sleep-log ids")
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
    raise RuntimeError("Could not allocate a unique sleep-log id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, sleep_date: str | None = None,
                 pupil_id: str | None = None) -> list[SleepRecord]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if sleep_date:
        clauses.append("s.sleep_date = ?")
        params.append(sleep_date.strip())
    if pupil_id:
        clauses.append("s.pupil_id = ?")
        params.append(pupil_id.strip())
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY s.sleep_date DESC, s.start_time DESC, s.sleep_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(sleep_id: str) -> SleepRecord | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE s.sleep_id = ?", (sleep_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", sleep_id)
        raise
    return _row(row) if row else None


def list_pupil_choices() -> list[tuple[str, str]]:
    """Return ``(pupil_id, "Name (id) — room")`` pairs for child pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


def list_staff_choices() -> list[tuple[str, str]]:
    """Return ``(staff_id, "Name (id)")`` pairs for currently-employed staff."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name FROM staff "
                "WHERE employment_status != 'Left' "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
            for r in rows]


def summary(sleep_date: str) -> dict[str, Any]:
    """Total naps + total slept minutes for ``sleep_date``."""
    records = list_records(sleep_date=sleep_date)
    total_minutes = sum(r.duration_minutes or 0 for r in records)
    return {"sleep_date": sleep_date, "naps": len(records),
            "total_minutes": total_minutes}


# ── Writes ───────────────────────────────────────────────────────────────────

def create_record(data: dict[str, Any]) -> SleepRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO sleep_log (
                    sleep_id, pupil_id, sleep_date, start_time, end_time,
                    duration_minutes, location, checks, staff_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["sleep_date"],
                 payload["start_time"], payload["end_time"],
                 payload["duration_minutes"], payload["location"],
                 payload["checks"], payload["staff_id"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for sleep-log id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created sleep-log record %s for pupil %s",
                rid, payload["pupil_id"])
    return rec


def update_record(sleep_id: str, data: dict[str, Any]) -> SleepRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_record(sleep_id)
    if existing is None:
        raise ValidationError(f"No sleep-log record with id {sleep_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE sleep_log SET
                    sleep_date = ?, start_time = ?, end_time = ?,
                    duration_minutes = ?, location = ?, checks = ?,
                    staff_id = ?, notes = ?
                WHERE sleep_id = ?
                """,
                (payload["sleep_date"], payload["start_time"],
                 payload["end_time"], payload["duration_minutes"],
                 payload["location"], payload["checks"], payload["staff_id"],
                 payload["notes"], sleep_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for sleep-log id=%s", sleep_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(sleep_id)
    assert rec is not None
    logger.info("Updated sleep-log record %s", sleep_id)
    return rec


def delete_record(sleep_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM sleep_log WHERE sleep_id = ?", (sleep_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting sleep-log id=%s", sleep_id)
        raise
    if deleted:
        logger.info("Deleted sleep-log record %s", sleep_id)
    return deleted
