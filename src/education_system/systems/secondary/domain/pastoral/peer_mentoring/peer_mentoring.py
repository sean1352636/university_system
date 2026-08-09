"""Peer-mentoring data layer for the Secondary School System.

Two tables:

* ``mentoring_pairings`` — one row per mentor↔mentee pairing in a
                            given academic year. Captures focus,
                            frequency, coordinator, status workflow
                            (Proposed → Active → Paused → Ended).
* ``mentoring_sessions`` — one row per individual session attached to
                            a pairing. Attendance, agenda, outcome.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

PAIRING_STATUSES: tuple[str, ...] = (
    "Proposed", "Active", "Paused", "Ended", "Withdrawn")
DEFAULT_PAIRING_STATUS: str = "Proposed"

FOCUS_AREAS: tuple[str, ...] = (
    "Academic", "Behaviour", "Confidence", "Friendships",
    "Transition", "Wellbeing", "Study skills",
    "Reading", "Anti-bullying", "Other")
DEFAULT_FOCUS: str = "Academic"

FREQUENCIES: tuple[str, ...] = (
    "Daily", "Twice weekly", "Weekly", "Fortnightly",
    "Monthly", "One-off", "Other")
DEFAULT_FREQUENCY: str = "Weekly"

SESSION_OUTCOMES: tuple[str, ...] = (
    "Attended", "Mentee absent", "Mentor absent",
    "Both absent", "Cancelled", "Productive", "Concerns raised")
DEFAULT_OUTCOME: str = "Attended"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AY_RE = re.compile(r"^\d{4}/\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mentoring_pairings (
    pairing_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    mentor_id       TEXT NOT NULL,
    mentee_id       TEXT NOT NULL,
    academic_year   TEXT NOT NULL,
    focus           TEXT NOT NULL DEFAULT 'Academic',
    frequency       TEXT NOT NULL DEFAULT 'Weekly',
    coordinator     TEXT,
    start_date      TEXT NOT NULL DEFAULT (date('now')),
    end_date        TEXT,
    status          TEXT NOT NULL DEFAULT 'Proposed',
    goals           TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE (mentor_id, mentee_id, academic_year),
    CHECK (mentor_id <> mentee_id)
);

CREATE TABLE IF NOT EXISTS mentoring_sessions (
    session_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pairing_id      INTEGER NOT NULL,
    session_date    TEXT NOT NULL DEFAULT (date('now')),
    session_time    TEXT,
    duration_min    INTEGER,
    location        TEXT,
    agenda          TEXT,
    notes           TEXT,
    outcome         TEXT NOT NULL DEFAULT 'Attended',
    concerns_flag   INTEGER NOT NULL DEFAULT 0,
    follow_up       TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pairing_id) REFERENCES mentoring_pairings(pairing_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mp_mentor
    ON mentoring_pairings(mentor_id);
CREATE INDEX IF NOT EXISTS idx_mp_mentee
    ON mentoring_pairings(mentee_id);
CREATE INDEX IF NOT EXISTS idx_mp_status
    ON mentoring_pairings(status);
CREATE INDEX IF NOT EXISTS idx_ms_pairing
    ON mentoring_sessions(pairing_id);
"""


@dataclass
class Pairing:
    pairing_id: int
    mentor_id: str
    mentee_id: str
    academic_year: str
    focus: str
    frequency: str
    coordinator: str | None
    start_date: str
    end_date: str | None
    status: str
    goals: str | None
    notes: str | None
    mentor_name: str | None = None
    mentee_name: str | None = None
    mentor_year: str | None = None
    mentee_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Session:
    session_id: int
    pairing_id: int
    session_date: str
    session_time: str | None
    duration_min: int | None
    location: str | None
    agenda: str | None
    notes: str | None
    outcome: str
    concerns_flag: bool
    follow_up: str | None
    created_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise peer_mentoring tables")
        raise
    logger.info("Secondary peer_mentoring tables ready")
    _DB_READY = True


def _row_pairing(r: sqlite3.Row) -> Pairing:
    keys = r.keys()
    return Pairing(
        pairing_id=r["pairing_id"], mentor_id=r["mentor_id"],
        mentee_id=r["mentee_id"],
        academic_year=r["academic_year"],
        focus=r["focus"], frequency=r["frequency"],
        coordinator=r["coordinator"],
        start_date=r["start_date"], end_date=r["end_date"],
        status=r["status"], goals=r["goals"], notes=r["notes"],
        mentor_name=r["mentor_name"] if "mentor_name" in keys else None,
        mentee_name=r["mentee_name"] if "mentee_name" in keys else None,
        mentor_year=r["mentor_year"] if "mentor_year" in keys else None,
        mentee_year=r["mentee_year"] if "mentee_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_session(r: sqlite3.Row) -> Session:
    return Session(
        session_id=r["session_id"], pairing_id=r["pairing_id"],
        session_date=r["session_date"],
        session_time=r["session_time"],
        duration_min=r["duration_min"], location=r["location"],
        agenda=r["agenda"], notes=r["notes"],
        outcome=r["outcome"],
        concerns_flag=bool(r["concerns_flag"]),
        follow_up=r["follow_up"], created_at=r["created_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            return _dt.date.today().isoformat()
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_pairing(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    mentor = (data.get("mentor_id") or "").strip()
    if not mentor:
        raise ValidationError("Mentor ID is required")
    mentee = (data.get("mentee_id") or "").strip()
    if not mentee:
        raise ValidationError("Mentee ID is required")
    if mentor == mentee:
        raise ValidationError("Mentor and mentee must be different pupils")
    from education_system.systems.secondary.domain.learners.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(mentor) is None:
        raise ValidationError(f"No pupil with id {mentor} (mentor)")
    if pupils_data.get_pupil(mentee) is None:
        raise ValidationError(f"No pupil with id {mentee} (mentee)")
    out["mentor_id"] = mentor
    out["mentee_id"] = mentee

    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025/26)")
    if not _AY_RE.match(ay):
        raise ValidationError(
            "Academic year must be in form YYYY/YY (e.g. 2025/26)")
    out["academic_year"] = ay

    focus = (data.get("focus") or DEFAULT_FOCUS).strip()
    if focus not in FOCUS_AREAS:
        raise ValidationError(
            f"Focus must be one of {', '.join(FOCUS_AREAS)}")
    out["focus"] = focus

    freq = (data.get("frequency") or DEFAULT_FREQUENCY).strip()
    if freq not in FREQUENCIES:
        raise ValidationError(
            f"Frequency must be one of {', '.join(FREQUENCIES)}")
    out["frequency"] = freq

    out["coordinator"] = (data.get("coordinator") or "").strip() or None
    out["start_date"]  = _validate_date(data.get("start_date"),
                                          "Start date")
    out["end_date"]    = _validate_date(data.get("end_date"),
                                          "End date", required=False)
    if out["end_date"] and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    status = (data.get("status") or DEFAULT_PAIRING_STATUS).strip()
    if status not in PAIRING_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(PAIRING_STATUSES)}")
    out["status"] = status

    out["goals"] = (data.get("goals") or "").strip() or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def _validate_session(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid_raw = data.get("pairing_id")
    if pid_raw in (None, ""):
        raise ValidationError("Pairing ID is required")
    try:
        out["pairing_id"] = int(pid_raw)
    except (TypeError, ValueError):
        raise ValidationError(
            "Pairing ID must be a number") from None

    out["session_date"] = _validate_date(data.get("session_date"),
                                           "Session date")
    t = (data.get("session_time") or "").strip()
    if t:
        if not _TIME_RE.match(t):
            raise ValidationError(
                "Session time must be HH:MM (24-hour)")
    out["session_time"] = t or None

    dur = data.get("duration_min")
    if dur in (None, "") or (isinstance(dur, str) and not dur.strip()):
        out["duration_min"] = None
    else:
        try:
            d = int(dur)
        except (TypeError, ValueError):
            raise ValidationError(
                "Duration must be a whole number") from None
        if d < 1 or d > 240:
            raise ValidationError(
                "Duration must be between 1 and 240 minutes")
        out["duration_min"] = d

    out["location"]  = (data.get("location") or "").strip() or None
    out["agenda"]    = (data.get("agenda") or "").strip() or None
    out["notes"]     = (data.get("notes") or "").strip() or None

    outcome = (data.get("outcome") or DEFAULT_OUTCOME).strip()
    if outcome not in SESSION_OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of {', '.join(SESSION_OUTCOMES)}")
    out["outcome"] = outcome

    out["concerns_flag"] = bool(data.get("concerns_flag"))
    out["follow_up"]     = (data.get("follow_up") or "").strip() or None

    if out["concerns_flag"] and not out["follow_up"]:
        raise ValidationError(
            "Follow-up is required when concerns_flag is set")
    return out


# ── Pairing CRUD ────────────────────────────────────────────────

def create_pairing(data: dict[str, Any]) -> Pairing:
    init_db()
    payload = _validate_pairing(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT pairing_id FROM mentoring_pairings "
                "WHERE mentor_id = ? AND mentee_id = ? "
                "  AND academic_year = ?",
                (payload["mentor_id"], payload["mentee_id"],
                 payload["academic_year"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"{payload['mentor_id']} → {payload['mentee_id']} "
                    f"pairing already exists for "
                    f"{payload['academic_year']}")
            cur = conn.execute(
                """INSERT INTO mentoring_pairings
                       (mentor_id, mentee_id, academic_year,
                        focus, frequency, coordinator,
                        start_date, end_date, status, goals, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["mentor_id"], payload["mentee_id"],
                 payload["academic_year"], payload["focus"],
                 payload["frequency"], payload["coordinator"],
                 payload["start_date"], payload["end_date"],
                 payload["status"], payload["goals"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        # Catches CHECK (mentor_id <> mentee_id) too.
        logger.exception("Mentoring pairing constraint failure")
        raise ValidationError(str(e)) from e
    except sqlite3.Error:
        logger.exception("Failed to create mentoring pairing")
        raise
    rec = get_pairing(new_id)
    assert rec is not None
    logger.info(
        "Created mentoring pairing #%d mentor=%s mentee=%s year=%s "
        "focus=%s freq=%s status=%s",
        rec.pairing_id, rec.mentor_id, rec.mentee_id,
        rec.academic_year, rec.focus, rec.frequency, rec.status)
    return rec


def get_pairing(pairing_id: int) -> Pairing | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT mp.*,
                          (m.first_name || ' ' || m.last_name) AS mentor_name,
                          m.year_group AS mentor_year,
                          (e.first_name || ' ' || e.last_name) AS mentee_name,
                          e.year_group AS mentee_year
                   FROM mentoring_pairings mp
                   LEFT JOIN pupils m ON m.pupil_id = mp.mentor_id
                   LEFT JOIN pupils e ON e.pupil_id = mp.mentee_id
                   WHERE mp.pairing_id = ?""",
                (pairing_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_pairing(%s) failed", pairing_id)
        raise
    return _row_pairing(r) if r else None


def list_pairings(*, mentor_id: str | None = None,
                  mentee_id: str | None = None,
                  academic_year: str | None = None,
                  status: str | None = None,
                  focus: str | None = None,
                  coordinator: str | None = None) -> list[Pairing]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if mentor_id:
        where.append("mp.mentor_id = ?")
        params.append(mentor_id.strip())
    if mentee_id:
        where.append("mp.mentee_id = ?")
        params.append(mentee_id.strip())
    if academic_year:
        where.append("mp.academic_year = ?")
        params.append(academic_year.strip())
    if status:
        if status not in PAIRING_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(PAIRING_STATUSES)}")
        where.append("mp.status = ?")
        params.append(status)
    if focus:
        if focus not in FOCUS_AREAS:
            raise ValidationError(
                f"Focus filter must be one of "
                f"{', '.join(FOCUS_AREAS)}")
        where.append("mp.focus = ?")
        params.append(focus)
    if coordinator:
        where.append("mp.coordinator = ?")
        params.append(coordinator.strip())
    sql = ("""SELECT mp.*,
                     (m.first_name || ' ' || m.last_name) AS mentor_name,
                     m.year_group AS mentor_year,
                     (e.first_name || ' ' || e.last_name) AS mentee_name,
                     e.year_group AS mentee_year
              FROM mentoring_pairings mp
              LEFT JOIN pupils m ON m.pupil_id = mp.mentor_id
              LEFT JOIN pupils e ON e.pupil_id = mp.mentee_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY mp.academic_year DESC, mp.start_date DESC"
    try:
        with _connect() as conn:
            return [_row_pairing(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_pairings failed")
        raise


def update_pairing(pairing_id: int,
                    data: dict[str, Any]) -> Pairing:
    init_db()
    existing = get_pairing(pairing_id)
    if existing is None:
        raise ValidationError(
            f"No mentoring pairing #{pairing_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("mentor_id", "mentee_id", "academic_year",
                         "focus", "frequency", "coordinator",
                         "start_date", "end_date", "status",
                         "goals", "notes")}
    payload = _validate_pairing(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT pairing_id FROM mentoring_pairings "
                "WHERE mentor_id = ? AND mentee_id = ? "
                "  AND academic_year = ? AND pairing_id <> ?",
                (payload["mentor_id"], payload["mentee_id"],
                 payload["academic_year"], pairing_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    "Another pairing already exists for the same "
                    "mentor/mentee/academic year")
            conn.execute(
                """UPDATE mentoring_pairings SET
                       mentor_id = ?, mentee_id = ?,
                       academic_year = ?, focus = ?, frequency = ?,
                       coordinator = ?, start_date = ?, end_date = ?,
                       status = ?, goals = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE pairing_id = ?""",
                (payload["mentor_id"], payload["mentee_id"],
                 payload["academic_year"], payload["focus"],
                 payload["frequency"], payload["coordinator"],
                 payload["start_date"], payload["end_date"],
                 payload["status"], payload["goals"],
                 payload["notes"], pairing_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update pairing #%d", pairing_id)
        raise
    rec = get_pairing(pairing_id)
    assert rec is not None
    logger.info("Updated mentoring pairing #%d (status %s)",
                rec.pairing_id, rec.status)
    return rec


def set_status(pairing_id: int, status: str) -> Pairing:
    return update_pairing(pairing_id, {"status": status})


def end_pairing(pairing_id: int,
                 end_date: str | None = None) -> Pairing:
    return update_pairing(pairing_id, {
        "status": "Ended",
        "end_date": end_date or _dt.date.today().isoformat(),
    })


def delete_pairing(pairing_id: int) -> bool:
    init_db()
    existing = get_pairing(pairing_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM mentoring_pairings WHERE pairing_id = ?",
                (pairing_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete pairing #%d", pairing_id)
        raise
    if deleted:
        logger.info("Deleted mentoring pairing #%d (cascade: sessions)",
                    pairing_id)
    return deleted


# ── Sessions ────────────────────────────────────────────────────

def log_session(data: dict[str, Any]) -> Session:
    init_db()
    payload = _validate_session(data)
    if get_pairing(payload["pairing_id"]) is None:
        raise ValidationError(
            f"No mentoring pairing #{payload['pairing_id']}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO mentoring_sessions
                       (pairing_id, session_date, session_time,
                        duration_min, location, agenda, notes,
                        outcome, concerns_flag, follow_up)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pairing_id"], payload["session_date"],
                 payload["session_time"], payload["duration_min"],
                 payload["location"], payload["agenda"],
                 payload["notes"], payload["outcome"],
                 1 if payload["concerns_flag"] else 0,
                 payload["follow_up"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception(
            "Failed to log session for pairing %d",
            payload["pairing_id"])
        raise
    logger.info(
        "Logged mentoring session #%d for pairing #%d "
        "(%s, outcome=%s, concerns=%s)",
        new_id, payload["pairing_id"], payload["session_date"],
        payload["outcome"], payload["concerns_flag"])
    rec = get_session(new_id)
    assert rec is not None
    return rec


def get_session(session_id: int) -> Session | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM mentoring_sessions "
                "WHERE session_id = ?", (session_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_session(%s) failed", session_id)
        raise
    return _row_session(r) if r else None


def list_sessions(pairing_id: int) -> list[Session]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_session(r) for r in conn.execute(
                "SELECT * FROM mentoring_sessions WHERE pairing_id = ? "
                "ORDER BY session_date DESC, session_id DESC",
                (pairing_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_sessions(%s) failed", pairing_id)
        raise


def delete_session(session_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM mentoring_sessions "
                "WHERE session_id = ?", (session_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete session #%d", session_id)
        raise
    if deleted:
        logger.info("Deleted mentoring session #%d", session_id)
    return deleted


def pairing_summary(pairing_id: int) -> dict[str, Any]:
    init_db()
    rec = get_pairing(pairing_id)
    if rec is None:
        raise ValidationError(f"No mentoring pairing #{pairing_id}")
    sessions = list_sessions(pairing_id)
    attended = sum(1 for s in sessions
                    if s.outcome in ("Attended", "Productive"))
    missed = sum(1 for s in sessions
                  if s.outcome in ("Mentee absent",
                                     "Mentor absent",
                                     "Both absent",
                                     "Cancelled"))
    concerns = sum(1 for s in sessions if s.concerns_flag)
    return {
        "pairing":     rec,
        "sessions":    sessions,
        "session_count": len(sessions),
        "attended":    attended,
        "missed":      missed,
        "concerns":    concerns,
        "by_outcome":  dict(Counter(s.outcome for s in sessions)),
    }


def cohort_summary(*, academic_year: str | None = None) -> dict[str, Any]:
    rows = list_pairings(academic_year=academic_year)
    return {
        "total":      len(rows),
        "by_status":  dict(Counter(r.status for r in rows)),
        "by_focus":   dict(Counter(r.focus for r in rows)),
        "active":     sum(1 for r in rows if r.status == "Active"),
        "mentors":    len({r.mentor_id for r in rows}),
        "mentees":    len({r.mentee_id for r in rows}),
    }
