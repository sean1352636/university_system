"""Cover (lesson reassignments) data layer for the Primary School System.

When a teacher is absent, the school needs to cover their timetabled
lessons. Each ``cover_arrangements`` row records:

* the date and period being covered
* the absent teacher and the cover teacher
* which class is being covered (year_group / form_group)
* the subject of the lesson
* status workflow: Pending → Assigned → Confirmed → Cancelled / Completed

Validation:
* cover teacher cannot be the same as the absent teacher
* the cover teacher cannot already be scheduled on the same day+period
  (timetable clash) or already covering a different lesson at the same
  time
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

STATUSES: tuple[str, ...] = (
    "Pending", "Assigned", "Confirmed", "Completed", "Cancelled")
DEFAULT_STATUS: str = "Pending"

MIN_PERIOD = 1
MAX_PERIOD = 8

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cover_arrangements (
    cover_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,
    period          INTEGER NOT NULL,
    absent_teacher  TEXT NOT NULL,
    cover_teacher   TEXT,
    year_group      TEXT,
    form_group      TEXT,
    subject_id      INTEGER,
    room            TEXT,
    status          TEXT NOT NULL DEFAULT 'Pending',
    reason          TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE INDEX IF NOT EXISTS idx_cover_date
    ON cover_arrangements(date, period);
CREATE INDEX IF NOT EXISTS idx_cover_absent
    ON cover_arrangements(absent_teacher);
CREATE INDEX IF NOT EXISTS idx_cover_cover
    ON cover_arrangements(cover_teacher);
"""


@dataclass
class CoverArrangement:
    cover_id: int
    date: str
    period: int
    absent_teacher: str
    cover_teacher: str | None
    year_group: str | None
    form_group: str | None
    subject_id: int | None
    room: str | None
    status: str
    reason: str | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.primary.domain.academics.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise cover_arrangements table")
        raise
    logger.info("Secondary cover_arrangements table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> CoverArrangement:
    keys = r.keys()
    return CoverArrangement(
        cover_id=r["cover_id"], date=r["date"], period=r["period"],
        absent_teacher=r["absent_teacher"],
        cover_teacher=r["cover_teacher"],
        year_group=r["year_group"], form_group=r["form_group"],
        subject_id=r["subject_id"],
        room=r["room"], status=r["status"],
        reason=r["reason"], notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str = "Date") -> str:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["date"] = _validate_date(data.get("date"))

    period = data.get("period")
    if period in (None, ""):
        raise ValidationError("Period is required")
    try:
        period = int(period)
    except (TypeError, ValueError):
        raise ValidationError("Period must be a number") from None
    if not (MIN_PERIOD <= period <= MAX_PERIOD):
        raise ValidationError(
            f"Period must be between {MIN_PERIOD} and {MAX_PERIOD}")
    out["period"] = period

    absent = (data.get("absent_teacher") or "").strip()
    if not absent:
        raise ValidationError("Absent teacher is required")
    out["absent_teacher"] = absent
    cover = (data.get("cover_teacher") or "").strip() or None
    if cover and cover.lower() == absent.lower():
        raise ValidationError(
            "Cover teacher cannot be the same as the absent teacher")
    out["cover_teacher"] = cover

    yg = (data.get("year_group") or "").strip() or None
    if yg and yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg
    out["form_group"] = (data.get("form_group") or "").strip() or None

    sid_raw = data.get("subject_id")
    if sid_raw in (None, ""):
        out["subject_id"] = None
    else:
        try:
            sid = int(sid_raw)
        except (TypeError, ValueError):
            raise ValidationError("Subject ID must be a number") from None
        from education_system.systems.primary.domain.academics.subjects import (
            subjects as subjects_data,
        )
        if subjects_data.get(sid) is None:
            raise ValidationError(f"No subject #{sid}")
        out["subject_id"] = sid

    out["room"] = (data.get("room") or "").strip() or None

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status

    out["reason"] = (data.get("reason") or "").strip() or None
    out["notes"]  = (data.get("notes") or "").strip() or None
    return out


def _check_cover_clash(conn: sqlite3.Connection,
                       payload: dict[str, Any],
                       exclude_id: int | None = None) -> None:
    """Make sure the cover teacher isn't already scheduled on the same
    date+period (existing cover OR scheduled timetable lesson)."""
    cover = payload["cover_teacher"]
    if not cover or payload["status"] == "Cancelled":
        return
    # Other cover arrangements at the same slot
    sql = ("SELECT cover_id FROM cover_arrangements "
           "WHERE cover_teacher = ? AND date = ? AND period = ? "
           "AND status NOT IN ('Cancelled')")
    params: list[Any] = [cover, payload["date"], payload["period"]]
    if exclude_id is not None:
        sql += " AND cover_id <> ?"
        params.append(exclude_id)
    row = conn.execute(sql, tuple(params)).fetchone()
    if row:
        raise ValidationError(
            f"Cover clash: {cover} already covers period {payload['period']} "
            f"on {payload['date']} (cover #{row['cover_id']})")
    # Timetabled lesson clash (only matters for weekdays)
    try:
        d = _dt.date.fromisoformat(payload["date"])
        weekday = ("Mon", "Tue", "Wed", "Thu", "Fri",
                   "Sat", "Sun")[d.weekday()]
    except ValueError:
        return
    if weekday in ("Sat", "Sun"):
        return
    row_tt = conn.execute(
        "SELECT slot_id FROM timetable_slots "
        "WHERE teacher = ? AND day_of_week = ? AND period = ?",
        (cover, weekday, payload["period"]),
    ).fetchone()
    if row_tt:
        raise ValidationError(
            f"Cover clash: {cover} already teaches period "
            f"{payload['period']} on {weekday} (timetable slot "
            f"#{row_tt['slot_id']})")


def create(data: dict[str, Any]) -> CoverArrangement:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            _check_cover_clash(conn, payload)
            cur = conn.execute(
                """INSERT INTO cover_arrangements
                       (date, period, absent_teacher, cover_teacher,
                        year_group, form_group, subject_id, room,
                        status, reason, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["date"], payload["period"],
                 payload["absent_teacher"], payload["cover_teacher"],
                 payload["year_group"], payload["form_group"],
                 payload["subject_id"], payload["room"],
                 payload["status"], payload["reason"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create cover arrangement")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created cover #%d %s P%d absent=%s cover=%s status=%s",
                rec.cover_id, rec.date, rec.period,
                rec.absent_teacher, rec.cover_teacher or "-", rec.status)
    return rec


def get(cover_id: int) -> CoverArrangement | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT c.*, s.code AS subject_code, s.name AS subject_name
                   FROM cover_arrangements c
                   LEFT JOIN subjects s ON s.subject_id = c.subject_id
                   WHERE c.cover_id = ?""",
                (cover_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", cover_id)
        raise
    return _row(r) if r else None


def list_arrangements(*, date: str | None = None,
                      date_from: str | None = None,
                      date_to: str | None = None,
                      teacher: str | None = None,
                      cover_teacher: str | None = None,
                      status: str | None = None
                      ) -> list[CoverArrangement]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if date:
        where.append("c.date = ?")
        params.append(_validate_date(date))
    if date_from:
        where.append("c.date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("c.date <= ?")
        params.append(_validate_date(date_to, "To date"))
    if teacher:
        where.append("c.absent_teacher = ?")
        params.append(teacher.strip())
    if cover_teacher:
        where.append("c.cover_teacher = ?")
        params.append(cover_teacher.strip())
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status filter must be one of {', '.join(STATUSES)}")
        where.append("c.status = ?")
        params.append(status)
    sql = ("""SELECT c.*, s.code AS subject_code, s.name AS subject_name
              FROM cover_arrangements c
              LEFT JOIN subjects s ON s.subject_id = c.subject_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.date DESC, c.period, c.cover_id DESC"
    try:
        with _connect() as conn:
            return [_row(r) for r in conn.execute(sql,
                                                    tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_arrangements failed")
        raise


def update(cover_id: int, data: dict[str, Any]) -> CoverArrangement:
    init_db()
    existing = get(cover_id)
    if existing is None:
        raise ValidationError(f"No cover arrangement #{cover_id}")
    merged = {
        "date":           data.get("date", existing.date),
        "period":         data.get("period", existing.period),
        "absent_teacher": data.get("absent_teacher",
                                    existing.absent_teacher),
        "cover_teacher":  data.get("cover_teacher",
                                    existing.cover_teacher),
        "year_group":     data.get("year_group", existing.year_group),
        "form_group":     data.get("form_group", existing.form_group),
        "subject_id":     data.get("subject_id", existing.subject_id),
        "room":           data.get("room", existing.room),
        "status":         data.get("status", existing.status),
        "reason":         data.get("reason", existing.reason),
        "notes":          data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    try:
        with _connect() as conn:
            _check_cover_clash(conn, payload, exclude_id=cover_id)
            conn.execute(
                """UPDATE cover_arrangements SET
                       date = ?, period = ?, absent_teacher = ?,
                       cover_teacher = ?, year_group = ?, form_group = ?,
                       subject_id = ?, room = ?, status = ?,
                       reason = ?, notes = ?, updated_at = datetime('now')
                   WHERE cover_id = ?""",
                (payload["date"], payload["period"],
                 payload["absent_teacher"], payload["cover_teacher"],
                 payload["year_group"], payload["form_group"],
                 payload["subject_id"], payload["room"],
                 payload["status"], payload["reason"], payload["notes"],
                 cover_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update cover arrangement #%d", cover_id)
        raise
    rec = get(cover_id)
    assert rec is not None
    logger.info("Updated cover #%d (status %s, cover=%s)",
                cover_id, rec.status, rec.cover_teacher or "-")
    return rec


def assign(cover_id: int, cover_teacher: str) -> CoverArrangement:
    """Convenience: set cover_teacher and move to Assigned."""
    teacher = (cover_teacher or "").strip()
    if not teacher:
        raise ValidationError("Cover teacher is required")
    return update(cover_id,
                  {"cover_teacher": teacher, "status": "Assigned"})


def set_status(cover_id: int, new_status: str) -> CoverArrangement:
    return update(cover_id, {"status": new_status})


def delete(cover_id: int) -> bool:
    init_db()
    existing = get(cover_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM cover_arrangements WHERE cover_id = ?",
                (cover_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete cover arrangement #%d", cover_id)
        raise
    if deleted:
        logger.info("Deleted cover #%d (%s P%d absent=%s)",
                    cover_id, existing.date, existing.period,
                    existing.absent_teacher)
    return deleted


def status_counts(*, date_from: str | None = None,
                  date_to: str | None = None) -> dict[str, int]:
    rows = list_arrangements(date_from=date_from, date_to=date_to)
    counter: Counter = Counter()
    for r in rows:
        counter[r.status] += 1
    return {s: counter.get(s, 0) for s in STATUSES}


def daily_load(date_iso: str) -> dict[str, Any]:
    """Cover stats for one day."""
    rows = list_arrangements(date=date_iso)
    by_status = Counter(r.status for r in rows)
    unassigned = [r for r in rows
                  if not r.cover_teacher and r.status != "Cancelled"]
    by_cover: Counter = Counter()
    for r in rows:
        if r.cover_teacher and r.status not in ("Cancelled",):
            by_cover[r.cover_teacher] += 1
    return {
        "date":         _validate_date(date_iso),
        "total":        len(rows),
        "by_status":    {s: by_status.get(s, 0) for s in STATUSES},
        "unassigned":   len(unassigned),
        "by_cover":     dict(by_cover),
        "records":      rows,
    }
