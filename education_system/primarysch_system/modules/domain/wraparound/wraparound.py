"""Wraparound care data layer.

Two tables:

* ``wraparound_sessions`` — one row per recurring session (e.g. "Breakfast Club",
  "Maple After School"). A session has a type (breakfast / after_school),
  the days it runs on (comma-separated list), a start/end time and an
  optional capacity and per-session fee.
* ``wraparound_attendance`` — one row per (session, pupil, date). Tracks
  status booked / attended / absent / late.

Fees are stored in pence to avoid float drift.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    Pupil, ValidationError,
    _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

SESSION_TYPES: tuple[str, ...] = ("breakfast", "after_school")
SESSION_TYPE_LABELS: dict[str, str] = {
    "breakfast":    "Breakfast Club",
    "after_school": "After-School Club",
}

DAYS_OF_WEEK: tuple[str, ...] = (
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
)

ATTENDANCE_STATUSES: tuple[str, ...] = ("booked", "attended", "absent", "late")
ATTENDANCE_LABELS: dict[str, str] = {
    "booked":   "Booked (planned)",
    "attended": "Attended",
    "absent":   "Absent (didn't attend)",
    "late":     "Attended (late)",
}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wraparound_sessions (
    session_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    session_type    TEXT NOT NULL,
    days_of_week    TEXT,
    start_time      TEXT,
    end_time        TEXT,
    capacity        INTEGER,
    fee_pence       INTEGER NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_wrap_active ON wraparound_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_wrap_type   ON wraparound_sessions(session_type);

CREATE TABLE IF NOT EXISTS wraparound_attendance (
    attendance_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,
    pupil_id        TEXT NOT NULL,
    date            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'booked',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(session_id, pupil_id, date),
    FOREIGN KEY(session_id) REFERENCES wraparound_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(pupil_id)   REFERENCES pupils(pupil_id)                 ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_wraatt_session ON wraparound_attendance(session_id, date);
CREATE INDEX IF NOT EXISTS idx_wraatt_pupil   ON wraparound_attendance(pupil_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_wraatt_date    ON wraparound_attendance(date DESC);
"""


@dataclass
class Session:
    session_id: int
    name: str
    session_type: str
    days_of_week: str | None
    start_time: str | None
    end_time: str | None
    capacity: int | None
    fee_pence: int
    is_active: bool
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def fee_display(self) -> str:
        if self.fee_pence <= 0:
            return "free"
        pounds = self.fee_pence // 100
        pence = self.fee_pence % 100
        return f"£{pounds}.{pence:02d}"

    @property
    def day_list(self) -> list[str]:
        if not self.days_of_week:
            return []
        return [d.strip() for d in self.days_of_week.split(",") if d.strip()]


@dataclass
class Attendance:
    attendance_id: int
    session_id: int
    pupil_id: str
    date: str
    status: str
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise wraparound tables")
        raise
    logger.info("Primary wraparound tables ready")
    _DB_READY = True


def _row_session(r: sqlite3.Row) -> Session:
    return Session(
        session_id=r["session_id"],
        name=r["name"],
        session_type=r["session_type"],
        days_of_week=r["days_of_week"],
        start_time=r["start_time"],
        end_time=r["end_time"],
        capacity=r["capacity"],
        fee_pence=r["fee_pence"],
        is_active=bool(r["is_active"]),
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _row_att(r: sqlite3.Row) -> Attendance:
    return Attendance(
        attendance_id=r["attendance_id"],
        session_id=r["session_id"],
        pupil_id=r["pupil_id"],
        date=r["date"],
        status=r["status"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate_days(raw: Any) -> str | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, (list, tuple)):
        items = [str(d).strip() for d in raw if str(d).strip()]
    else:
        items = [d.strip() for d in str(raw).split(",") if d.strip()]
    if not items:
        return None
    seen: list[str] = []
    for d in items:
        # Allow short and long forms; canonicalise.
        for full in DAYS_OF_WEEK:
            if d.lower() == full.lower() or d.lower() == full[:3].lower():
                if full not in seen:
                    seen.append(full)
                break
        else:
            raise ValidationError(
                f"Day of week {d!r} must be one of {', '.join(DAYS_OF_WEEK)}")
    return ",".join(seen)


def _validate_session(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Session name is required")
    if len(name) > 80:
        raise ValidationError("Session name must be 80 characters or fewer")
    out["name"] = name
    st = (data.get("session_type") or "").strip().lower()
    if not st:
        raise ValidationError("Session type is required")
    if st not in SESSION_TYPES:
        raise ValidationError(
            f"Session type must be one of {', '.join(SESSION_TYPES)}")
    out["session_type"] = st
    out["days_of_week"] = _validate_days(data.get("days_of_week"))
    for k, label in (("start_time", "Start time"), ("end_time", "End time")):
        v = (data.get(k) or "").strip()
        if v and not _TIME_RE.match(v):
            raise ValidationError(f"{label} must be HH:MM (24-hour)")
        out[k] = v or None
    if out["start_time"] and out["end_time"] and out["end_time"] <= out["start_time"]:
        raise ValidationError("End time must be after start time")
    cap_raw = data.get("capacity")
    if cap_raw in (None, ""):
        out["capacity"] = None
    else:
        try:
            cap = int(cap_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError("Capacity must be an integer") from e
        if cap < 1 or cap > 500:
            raise ValidationError("Capacity must be between 1 and 500")
        out["capacity"] = cap
    fee_raw = data.get("fee_pence")
    if fee_raw in (None, ""):
        # Accept fee_pounds as an alternative for friendly input.
        pounds_raw = data.get("fee_pounds")
        if pounds_raw in (None, ""):
            out["fee_pence"] = 0
        else:
            try:
                pounds = float(pounds_raw)
            except (TypeError, ValueError) as e:
                raise ValidationError("Fee must be a number") from e
            if pounds < 0 or pounds > 200:
                raise ValidationError("Fee must be between £0 and £200")
            out["fee_pence"] = int(round(pounds * 100))
    else:
        try:
            pence = int(fee_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError("Fee (pence) must be an integer") from e
        if pence < 0 or pence > 20000:
            raise ValidationError("Fee must be between 0p and 20000p")
        out["fee_pence"] = pence
    is_active = data.get("is_active")
    out["is_active"] = True if is_active is None else bool(is_active)
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# --- Sessions -------------------------------------------------------------

def create_session(data: dict[str, Any]) -> Session:
    init_db()
    payload = _validate_session(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT session_id FROM wraparound_sessions WHERE name = ?",
                (payload["name"],),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A session named {payload['name']!r} already exists")
            cur = conn.execute(
                """INSERT INTO wraparound_sessions
                       (name, session_type, days_of_week, start_time, end_time,
                        capacity, fee_pence, is_active, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["name"], payload["session_type"],
                 payload["days_of_week"], payload["start_time"],
                 payload["end_time"], payload["capacity"],
                 payload["fee_pence"], 1 if payload["is_active"] else 0,
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create wraparound session")
        raise
    rec = get_session(new_id)
    assert rec is not None
    logger.info("Created wraparound session #%d %s (%s)",
                rec.session_id, rec.name, rec.session_type)
    return rec


def get_session(session_id: int) -> Session | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM wraparound_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_session(%s) failed", session_id)
        raise
    return _row_session(r) if r else None


def list_sessions(*, session_type: str | None = None,
                  active_only: bool = False) -> list[Session]:
    init_db()
    if session_type is not None and session_type not in SESSION_TYPES:
        raise ValidationError(
            f"Type filter must be one of {', '.join(SESSION_TYPES)}")
    where: list[str] = []
    params: list[Any] = []
    if session_type:
        where.append("session_type = ?")
        params.append(session_type)
    if active_only:
        where.append("is_active = 1")
    sql = "SELECT * FROM wraparound_sessions"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY session_type, name COLLATE NOCASE"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_sessions failed")
        raise
    return [_row_session(r) for r in rows]


def update_session(session_id: int, data: dict[str, Any]) -> Session:
    init_db()
    existing = get_session(session_id)
    if existing is None:
        raise ValidationError(f"No session #{session_id}")
    merged = {
        "name":         data.get("name", existing.name),
        "session_type": data.get("session_type", existing.session_type),
        "days_of_week": data.get("days_of_week", existing.days_of_week),
        "start_time":   data.get("start_time", existing.start_time),
        "end_time":     data.get("end_time", existing.end_time),
        "capacity":     data.get("capacity", existing.capacity),
        "fee_pence":    data.get("fee_pence", existing.fee_pence),
        "is_active":    data.get("is_active", existing.is_active),
        "notes":        data.get("notes", existing.notes),
    }
    if "fee_pounds" in data and "fee_pence" not in data:
        merged["fee_pounds"] = data["fee_pounds"]
        merged.pop("fee_pence", None)
    payload = _validate_session(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT session_id FROM wraparound_sessions "
                "WHERE name = ? AND session_id <> ?",
                (payload["name"], session_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A session named {payload['name']!r} already exists")
            conn.execute(
                """UPDATE wraparound_sessions SET
                       name = ?, session_type = ?, days_of_week = ?,
                       start_time = ?, end_time = ?, capacity = ?,
                       fee_pence = ?, is_active = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE session_id = ?""",
                (payload["name"], payload["session_type"],
                 payload["days_of_week"], payload["start_time"],
                 payload["end_time"], payload["capacity"],
                 payload["fee_pence"], 1 if payload["is_active"] else 0,
                 payload["notes"], session_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update session #%d", session_id)
        raise
    rec = get_session(session_id)
    assert rec is not None
    logger.info("Updated wraparound session #%d %s", rec.session_id, rec.name)
    return rec


def toggle_session_active(session_id: int) -> Session:
    init_db()
    existing = get_session(session_id)
    if existing is None:
        raise ValidationError(f"No session #{session_id}")
    new_val = 0 if existing.is_active else 1
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE wraparound_sessions SET is_active = ?, "
                "updated_at = datetime('now') WHERE session_id = ?",
                (new_val, session_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("toggle_session_active(%s) failed", session_id)
        raise
    rec = get_session(session_id)
    assert rec is not None
    logger.info("Session #%d %s -> active=%s",
                rec.session_id, rec.name, rec.is_active)
    return rec


def delete_session(session_id: int) -> bool:
    init_db()
    existing = get_session(session_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM wraparound_sessions WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete session #%d", session_id)
        raise
    if deleted:
        logger.info("Deleted wraparound session #%d %s (attendance cascaded)",
                    session_id, existing.name)
    return deleted


# --- Attendance -----------------------------------------------------------

def _validate_attendance(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    sid = data.get("session_id")
    if sid in (None, ""):
        raise ValidationError("Session is required")
    try:
        out["session_id"] = int(sid)
    except (TypeError, ValueError) as e:
        raise ValidationError("Session ID must be an integer") from e
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    out["pupil_id"] = pid
    dt = (data.get("date") or "").strip()
    if not dt:
        raise ValidationError("Date is required")
    if not _DOB_RE.match(dt):
        raise ValidationError("Date must be YYYY-MM-DD")
    out["date"] = dt
    status = (data.get("status") or "booked").strip().lower() or "booked"
    if status not in ATTENDANCE_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(ATTENDANCE_STATUSES)}")
    out["status"] = status
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def _count_attendees(session_id: int, date: str) -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM wraparound_attendance "
            "WHERE session_id = ? AND date = ? "
            "AND status IN ('booked', 'attended', 'late')",
            (session_id, date),
        ).fetchone()[0]


def book(data: dict[str, Any]) -> Attendance:
    """Book or upsert an attendance row for (session, pupil, date)."""
    init_db()
    payload = _validate_attendance(data)
    sess = get_session(payload["session_id"])
    if sess is None:
        raise ValidationError(f"No session #{payload['session_id']}")
    if not sess.is_active:
        raise ValidationError(f"Session {sess.name!r} is inactive")
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            existing = conn.execute(
                "SELECT * FROM wraparound_attendance "
                "WHERE session_id = ? AND pupil_id = ? AND date = ?",
                (payload["session_id"], payload["pupil_id"], payload["date"]),
            ).fetchone()
            if existing is None:
                if sess.capacity is not None and (
                        _count_attendees(payload["session_id"], payload["date"])
                        >= sess.capacity):
                    raise ValidationError(
                        f"Session {sess.name!r} is full for {payload['date']} "
                        f"(capacity {sess.capacity})")
                cur = conn.execute(
                    """INSERT INTO wraparound_attendance
                           (session_id, pupil_id, date, status, notes)
                       VALUES (?, ?, ?, ?, ?)""",
                    (payload["session_id"], payload["pupil_id"],
                     payload["date"], payload["status"], payload["notes"]),
                )
                new_id = cur.lastrowid
            else:
                conn.execute(
                    "UPDATE wraparound_attendance SET status = ?, "
                    "notes = ?, updated_at = datetime('now') "
                    "WHERE attendance_id = ?",
                    (payload["status"], payload["notes"],
                     existing["attendance_id"]),
                )
                new_id = existing["attendance_id"]
            conn.commit()
    except sqlite3.Error:
        logger.exception("book(session=%s, pupil=%s, date=%s) failed",
                         payload["session_id"], payload["pupil_id"],
                         payload["date"])
        raise
    rec = get_attendance(new_id)
    assert rec is not None
    logger.info("Wraparound: pupil %s session #%d date %s -> %s (#%d)",
                rec.pupil_id, rec.session_id, rec.date, rec.status,
                rec.attendance_id)
    return rec


def set_attendance_status(attendance_id: int, status: str) -> Attendance:
    init_db()
    if status not in ATTENDANCE_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(ATTENDANCE_STATUSES)}")
    existing = get_attendance(attendance_id)
    if existing is None:
        raise ValidationError(f"No attendance #{attendance_id}")
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE wraparound_attendance SET status = ?, "
                "updated_at = datetime('now') WHERE attendance_id = ?",
                (status, attendance_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("set_attendance_status(%s, %s) failed",
                         attendance_id, status)
        raise
    rec = get_attendance(attendance_id)
    assert rec is not None
    logger.info("Wraparound attendance #%d -> %s", attendance_id, status)
    return rec


def get_attendance(attendance_id: int) -> Attendance | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM wraparound_attendance "
                "WHERE attendance_id = ?",
                (attendance_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_attendance(%s) failed", attendance_id)
        raise
    return _row_att(r) if r else None


def delete_attendance(attendance_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM wraparound_attendance WHERE attendance_id = ?",
                (attendance_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("delete_attendance(%s) failed", attendance_id)
        raise
    if deleted:
        logger.info("Deleted wraparound attendance #%d", attendance_id)
    return deleted


def list_attendance(
    *, session_id: int | None = None,
    pupil_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    status: str | None = None,
) -> list[tuple[Attendance, Session | None, Pupil | None]]:
    init_db()
    if status is not None and status not in ATTENDANCE_STATUSES:
        raise ValidationError(
            f"Status filter must be one of {', '.join(ATTENDANCE_STATUSES)}")
    for k, v in (("from_date", from_date), ("to_date", to_date)):
        if v and not _DOB_RE.match(v):
            raise ValidationError(f"{k} must be YYYY-MM-DD")
    where: list[str] = []
    params: list[Any] = []
    if session_id is not None:
        where.append("session_id = ?")
        params.append(session_id)
    if pupil_id:
        where.append("pupil_id = ?")
        params.append(pupil_id.strip())
    if status:
        where.append("status = ?")
        params.append(status)
    if from_date:
        where.append("date >= ?")
        params.append(from_date)
    if to_date:
        where.append("date <= ?")
        params.append(to_date)
    sql = "SELECT * FROM wraparound_attendance"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date DESC, session_id, pupil_id"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_attendance failed")
        raise
    out: list[tuple[Attendance, Session | None, Pupil | None]] = []
    for r in rows:
        a = _row_att(r)
        sess = get_session(a.session_id)
        pupil = pupils_data.get_pupil(a.pupil_id)
        out.append((a, sess, pupil))
    return out


def day_register(session_id: int, date: str
                 ) -> list[tuple[Attendance, Pupil | None]]:
    """Return everyone on the register for ``date``, ordered by pupil name."""
    init_db()
    if not _DOB_RE.match((date or "").strip()):
        raise ValidationError("Date must be YYYY-MM-DD")
    if get_session(session_id) is None:
        raise ValidationError(f"No session #{session_id}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM wraparound_attendance "
                "WHERE session_id = ? AND date = ?",
                (session_id, date),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("day_register(%s, %s) failed", session_id, date)
        raise
    out: list[tuple[Attendance, Pupil | None]] = []
    for r in rows:
        a = _row_att(r)
        out.append((a, pupils_data.get_pupil(a.pupil_id)))
    out.sort(key=lambda t: (t[1].last_name if t[1] else "",
                            t[1].first_name if t[1] else ""))
    return out


def session_summary(session_id: int,
                    *, from_date: str | None = None,
                    to_date: str | None = None) -> dict[str, Any]:
    init_db()
    if get_session(session_id) is None:
        raise ValidationError(f"No session #{session_id}")
    where = "WHERE session_id = ?"
    params: list[Any] = [session_id]
    if from_date:
        if not _DOB_RE.match(from_date):
            raise ValidationError("from_date must be YYYY-MM-DD")
        where += " AND date >= ?"
        params.append(from_date)
    if to_date:
        if not _DOB_RE.match(to_date):
            raise ValidationError("to_date must be YYYY-MM-DD")
        where += " AND date <= ?"
        params.append(to_date)
    try:
        with _connect() as conn:
            counts = {
                r["status"]: r["n"]
                for r in conn.execute(
                    f"SELECT status, COUNT(*) AS n FROM wraparound_attendance "
                    f"{where} GROUP BY status",
                    tuple(params),
                ).fetchall()
            }
            unique_pupils = conn.execute(
                f"SELECT COUNT(DISTINCT pupil_id) FROM wraparound_attendance "
                f"{where}",
                tuple(params),
            ).fetchone()[0]
    except sqlite3.Error:
        logger.exception("session_summary(%s) failed", session_id)
        raise
    total = sum(counts.values())
    return {
        "session_id": session_id,
        "total_rows": total,
        "by_status": {s: counts.get(s, 0) for s in ATTENDANCE_STATUSES},
        "unique_pupils": unique_pupils,
    }


def counts() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            sessions = conn.execute(
                "SELECT COUNT(*) FROM wraparound_sessions").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM wraparound_sessions WHERE is_active = 1"
            ).fetchone()[0]
            att = conn.execute(
                "SELECT COUNT(*) FROM wraparound_attendance").fetchone()[0]
    except sqlite3.Error:
        logger.exception("counts failed")
        raise
    return {"sessions": sessions, "active_sessions": active,
            "attendance_rows": att}
