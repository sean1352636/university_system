"""Weekly timetable data layer for the Primary School System.

A timetable slot pairs a year group (and optionally a specific form
group) with a subject, room, and teacher, on a day-of-week / period.
Clash detection enforces that the same (year_group, form_group, day,
period) tuple cannot be double-booked.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

DAYS_OF_WEEK: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri")
MIN_PERIOD = 1
MAX_PERIOD = 8

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS timetable_slots (
    slot_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    year_group     TEXT NOT NULL,
    form_group     TEXT,
    subject_id     INTEGER NOT NULL,
    day_of_week    TEXT NOT NULL,
    period         INTEGER NOT NULL,
    start_time     TEXT,
    end_time       TEXT,
    room           TEXT,
    teacher        TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE INDEX IF NOT EXISTS idx_tt_year_day
    ON timetable_slots(year_group, day_of_week, period);
CREATE INDEX IF NOT EXISTS idx_tt_form
    ON timetable_slots(form_group);
CREATE INDEX IF NOT EXISTS idx_tt_teacher
    ON timetable_slots(teacher);
"""


@dataclass
class TimetableSlot:
    slot_id: int
    year_group: str
    form_group: str | None
    subject_id: int
    day_of_week: str
    period: int
    start_time: str | None
    end_time: str | None
    room: str | None
    teacher: str | None
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
    # Ensure subjects table exists first for the FK
    from education_system.primarysch_system.modules.domain.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise timetable_slots table")
        raise
    logger.info("Secondary timetable_slots table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> TimetableSlot:
    return TimetableSlot(
        slot_id=r["slot_id"],
        year_group=r["year_group"],
        form_group=r["form_group"],
        subject_id=r["subject_id"],
        day_of_week=r["day_of_week"],
        period=r["period"],
        start_time=r["start_time"],
        end_time=r["end_time"],
        room=r["room"],
        teacher=r["teacher"],
        notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in r.keys() else None,
        subject_name=r["subject_name"] if "subject_name" in r.keys() else None,
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    yg = (data.get("year_group") or "").strip()
    if not yg:
        raise ValidationError("Year group is required")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg
    out["form_group"] = (data.get("form_group") or "").strip() or None

    sid = data.get("subject_id")
    if sid in (None, ""):
        raise ValidationError("Subject is required")
    try:
        out["subject_id"] = int(sid)
    except (TypeError, ValueError):
        raise ValidationError("Subject ID must be a number") from None
    from education_system.primarysch_system.modules.domain.subjects import (
        subjects as subjects_data,
    )
    subj = subjects_data.get(out["subject_id"])
    if subj is None:
        raise ValidationError(f"No subject #{out['subject_id']}")
    if not subj.is_active:
        raise ValidationError(
            f"Subject {subj.code} is inactive — activate it first")

    day = (data.get("day_of_week") or "").strip()
    # Accept full names too — normalise to 3-letter form.
    if day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
        day = day[:3]
    if day not in DAYS_OF_WEEK:
        raise ValidationError(
            f"Day must be one of {', '.join(DAYS_OF_WEEK)}")
    out["day_of_week"] = day

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

    def _time(value: Any, label: str) -> str | None:
        if value in (None, "") or (isinstance(value, str)
                                    and not value.strip()):
            return None
        s = str(value).strip()
        if not _TIME_RE.match(s):
            raise ValidationError(f"{label} must be HH:MM (24-hour)")
        return s

    out["start_time"] = _time(data.get("start_time"), "Start time")
    out["end_time"]   = _time(data.get("end_time"), "End time")
    if (out["start_time"] and out["end_time"]
            and out["end_time"] <= out["start_time"]):
        raise ValidationError("End time must be after start time")

    out["room"]    = (data.get("room") or "").strip() or None
    out["teacher"] = (data.get("teacher") or "").strip() or None
    out["notes"]   = (data.get("notes") or "").strip() or None
    return out


def _check_clash(conn: sqlite3.Connection, payload: dict[str, Any],
                 exclude_id: int | None = None) -> None:
    """Raise if a slot already exists for the same year+form+day+period
    or for the same teacher at the same day+period."""
    # Year+form+day+period clash
    sql = ("SELECT slot_id FROM timetable_slots "
           "WHERE year_group = ? AND day_of_week = ? AND period = ? "
           "AND ((form_group IS NULL AND ? IS NULL) "
           "  OR form_group = ?)")
    params: list[Any] = [payload["year_group"], payload["day_of_week"],
                         payload["period"], payload["form_group"],
                         payload["form_group"]]
    if exclude_id is not None:
        sql += " AND slot_id <> ?"
        params.append(exclude_id)
    row = conn.execute(sql, tuple(params)).fetchone()
    if row:
        raise ValidationError(
            f"Slot clash: Year {payload['year_group']}"
            + (f"/{payload['form_group']}" if payload["form_group"] else "")
            + f" already has a lesson on {payload['day_of_week']} P"
            f"{payload['period']} (slot #{row['slot_id']})")
    # Teacher clash (same teacher, same day/period)
    if payload["teacher"]:
        sql_t = ("SELECT slot_id FROM timetable_slots "
                 "WHERE teacher = ? AND day_of_week = ? AND period = ?")
        params_t: list[Any] = [payload["teacher"], payload["day_of_week"],
                                payload["period"]]
        if exclude_id is not None:
            sql_t += " AND slot_id <> ?"
            params_t.append(exclude_id)
        row_t = conn.execute(sql_t, tuple(params_t)).fetchone()
        if row_t:
            raise ValidationError(
                f"Teacher clash: {payload['teacher']} is already "
                f"scheduled on {payload['day_of_week']} P"
                f"{payload['period']} (slot #{row_t['slot_id']})")


def create_slot(data: dict[str, Any]) -> TimetableSlot:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            _check_clash(conn, payload)
            cur = conn.execute(
                """INSERT INTO timetable_slots
                       (year_group, form_group, subject_id,
                        day_of_week, period, start_time, end_time,
                        room, teacher, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["year_group"], payload["form_group"],
                 payload["subject_id"], payload["day_of_week"],
                 payload["period"], payload["start_time"],
                 payload["end_time"], payload["room"],
                 payload["teacher"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create timetable slot")
        raise
    rec = get_slot(new_id)
    assert rec is not None
    logger.info("Created timetable slot #%d Yr%s/%s %s P%d subject=%s",
                rec.slot_id, rec.year_group, rec.form_group or "-",
                rec.day_of_week, rec.period, rec.subject_code)
    return rec


def get_slot(slot_id: int) -> TimetableSlot | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT t.*, s.code AS subject_code, s.name AS subject_name
                   FROM timetable_slots t
                   LEFT JOIN subjects s ON s.subject_id = t.subject_id
                   WHERE t.slot_id = ?""",
                (slot_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_slot(%s) failed", slot_id)
        raise
    return _row(r) if r else None


def list_slots(*, year_group: str | None = None,
               form_group: str | None = None,
               day_of_week: str | None = None,
               teacher: str | None = None
               ) -> list[TimetableSlot]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("t.year_group = ?")
        params.append(year_group)
    if form_group:
        where.append("t.form_group = ?")
        params.append(form_group.strip())
    if day_of_week:
        day = day_of_week.strip()
        if day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
            day = day[:3]
        if day not in DAYS_OF_WEEK:
            raise ValidationError(
                f"Day filter must be one of {', '.join(DAYS_OF_WEEK)}")
        where.append("t.day_of_week = ?")
        params.append(day)
    if teacher:
        where.append("t.teacher = ?")
        params.append(teacher.strip())
    sql = ("""SELECT t.*, s.code AS subject_code, s.name AS subject_name
              FROM timetable_slots t
              LEFT JOIN subjects s ON s.subject_id = t.subject_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    # Sort by day order then period.
    sql += (" ORDER BY "
            " CASE t.day_of_week "
            "   WHEN 'Mon' THEN 1 WHEN 'Tue' THEN 2 "
            "   WHEN 'Wed' THEN 3 WHEN 'Thu' THEN 4 "
            "   WHEN 'Fri' THEN 5 END, "
            " t.period, t.year_group, t.form_group")
    try:
        with _connect() as conn:
            return [_row(r) for r in conn.execute(sql,
                                                    tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_slots failed")
        raise


def update_slot(slot_id: int, data: dict[str, Any]) -> TimetableSlot:
    init_db()
    existing = get_slot(slot_id)
    if existing is None:
        raise ValidationError(f"No timetable slot #{slot_id}")
    merged = {
        "year_group":  data.get("year_group", existing.year_group),
        "form_group":  data.get("form_group", existing.form_group),
        "subject_id":  data.get("subject_id", existing.subject_id),
        "day_of_week": data.get("day_of_week", existing.day_of_week),
        "period":      data.get("period", existing.period),
        "start_time":  data.get("start_time", existing.start_time),
        "end_time":    data.get("end_time", existing.end_time),
        "room":        data.get("room", existing.room),
        "teacher":     data.get("teacher", existing.teacher),
        "notes":       data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    try:
        with _connect() as conn:
            _check_clash(conn, payload, exclude_id=slot_id)
            conn.execute(
                """UPDATE timetable_slots SET
                       year_group = ?, form_group = ?, subject_id = ?,
                       day_of_week = ?, period = ?,
                       start_time = ?, end_time = ?,
                       room = ?, teacher = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE slot_id = ?""",
                (payload["year_group"], payload["form_group"],
                 payload["subject_id"], payload["day_of_week"],
                 payload["period"], payload["start_time"],
                 payload["end_time"], payload["room"],
                 payload["teacher"], payload["notes"], slot_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update timetable slot #%d", slot_id)
        raise
    rec = get_slot(slot_id)
    assert rec is not None
    logger.info("Updated timetable slot #%d", rec.slot_id)
    return rec


def delete_slot(slot_id: int) -> bool:
    init_db()
    existing = get_slot(slot_id)
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM timetable_slots WHERE slot_id = ?", (slot_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete timetable slot #%d", slot_id)
        raise
    if deleted and existing:
        logger.info("Deleted timetable slot #%d (Yr%s %s P%d)",
                    slot_id, existing.year_group,
                    existing.day_of_week, existing.period)
    return deleted


def weekly_grid(*, year_group: str | None = None,
                form_group: str | None = None,
                teacher: str | None = None
                ) -> dict[tuple[str, int], list[TimetableSlot]]:
    """Return ``{(day, period): [slots]}`` for the given filter."""
    slots = list_slots(year_group=year_group, form_group=form_group,
                       teacher=teacher)
    grid: dict[tuple[str, int], list[TimetableSlot]] = {}
    for s in slots:
        grid.setdefault((s.day_of_week, s.period), []).append(s)
    return grid


def counts() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM timetable_slots").fetchone()[0]
            distinct_teachers = conn.execute(
                "SELECT COUNT(DISTINCT teacher) FROM timetable_slots "
                "WHERE teacher IS NOT NULL").fetchone()[0]
    except sqlite3.Error:
        logger.exception("timetable counts failed")
        raise
    return {"total": total, "teachers": distinct_teachers}
