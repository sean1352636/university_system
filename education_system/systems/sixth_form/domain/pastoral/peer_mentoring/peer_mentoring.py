"""Peer Mentoring data layer for Sixth Form System.

Two tables:
- `peer_mentoring_pairings`: one row per mentor↔mentee pairing
  under a named programme. Both ids FK to `students` with cascade.
- `peer_mentoring_sessions`: per-pairing session log with date,
  duration, attendance flag and notes. Cascade on pairing delete.

Mentor and mentee must be distinct. A student can be in multiple
pairings (e.g. mentee in one programme, mentor in another).
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.systems.sixth_form.infrastructure import paths as _paths

logger = logging.getLogger(__name__)

PROGRAMMES: tuple[str, ...] = (
    "UCAS Buddies",
    "Subject Tutoring",
    "Reading Buddies",
    "Y12-Y13 New Starter",
    "Y11-Y12 Transition",
    "Wellbeing Mentor",
    "EAL Buddy",
    "Study Skills Mentor",
    "Aspirations Mentor",
    "Other",
)
DEFAULT_PROGRAMME = "Subject Tutoring"

FREQUENCIES: tuple[str, ...] = (
    "Weekly", "Fortnightly", "Monthly", "Ad-Hoc",
)
DEFAULT_FREQUENCY = "Weekly"

STATUSES: tuple[str, ...] = (
    "Pending Match",
    "Active",
    "Paused",
    "Completed",
    "Withdrawn",
    "Archived",
)
DEFAULT_STATUS = "Active"


class ValidationError(Exception):
    pass


@dataclass
class Pairing:
    pairing_id: int
    programme: str
    mentor_id: str
    mentee_id: str
    coordinator: str | None
    frequency: str
    start_date: str
    planned_end: str | None
    actual_end: str | None
    sessions_planned: int | None
    location: str | None
    subject_focus: str | None
    goals: str | None
    mentor_feedback: str | None
    mentee_feedback: str | None
    mentor_rating: int | None
    mentee_rating: int | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status in ("Pending Match", "Active", "Paused")

    @property
    def is_active(self) -> bool:
        return self.status == "Active"


@dataclass
class Session:
    session_id: int
    pairing_id: int
    session_date: str
    duration_minutes: int
    focus: str | None
    attended: bool
    notes: str | None
    created_on: str


@dataclass
class PairingSummary:
    total: int = 0
    active: int = 0
    pending: int = 0
    completed: int = 0
    distinct_mentors: int = 0
    distinct_mentees: int = 0
    total_sessions: int = 0
    total_hours: float = 0.0
    average_mentee_rating: float | None = None
    by_programme: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_frequency: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.PEER_MENTORING_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS peer_mentoring_pairings (
                pairing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                programme TEXT NOT NULL,
                mentor_id TEXT NOT NULL,
                mentee_id TEXT NOT NULL,
                coordinator TEXT,
                frequency TEXT NOT NULL,
                start_date TEXT NOT NULL,
                planned_end TEXT,
                actual_end TEXT,
                sessions_planned INTEGER,
                location TEXT,
                subject_focus TEXT,
                goals TEXT,
                mentor_feedback TEXT,
                mentee_feedback TEXT,
                mentor_rating INTEGER,
                mentee_rating INTEGER,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(mentor_id) REFERENCES students(student_id)
                  ON DELETE CASCADE,
                FOREIGN KEY(mentee_id) REFERENCES students(student_id)
                  ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS peer_mentoring_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pairing_id INTEGER NOT NULL,
                session_date TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                focus TEXT,
                attended INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                created_on TEXT NOT NULL,
                FOREIGN KEY(pairing_id)
                  REFERENCES peer_mentoring_pairings(pairing_id)
                  ON DELETE CASCADE
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _student_exists(student_id: str) -> bool:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id=?",
                (student_id,)).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


def _check_rating(label: str, v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        iv = int(v)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be 1-5")
    if iv not in (1, 2, 3, 4, 5):
        raise ValidationError(f"{label} must be 1-5")
    return iv


def _validate_pairing(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["mentor_id"] = (out.get("mentor_id") or "").strip()
    out["mentee_id"] = (out.get("mentee_id") or "").strip()
    if not out["mentor_id"]:
        raise ValidationError("Mentor is required")
    if not out["mentee_id"]:
        raise ValidationError("Mentee is required")
    if out["mentor_id"] == out["mentee_id"]:
        raise ValidationError(
            "Mentor and mentee must be different students")
    if not _student_exists(out["mentor_id"]):
        raise ValidationError(
            f"No student with id {out['mentor_id']}")
    if not _student_exists(out["mentee_id"]):
        raise ValidationError(
            f"No student with id {out['mentee_id']}")

    prog = (out.get("programme") or "").strip()
    if prog not in PROGRAMMES:
        raise ValidationError(
            f"Programme must be one of: {', '.join(PROGRAMMES)}")
    out["programme"] = prog

    freq = (out.get("frequency") or DEFAULT_FREQUENCY).strip()
    if freq not in FREQUENCIES:
        raise ValidationError(
            f"Frequency must be one of: {', '.join(FREQUENCIES)}")
    out["frequency"] = freq

    out["start_date"] = (out.get("start_date") or "").strip()
    if not out["start_date"]:
        raise ValidationError("Start date is required")
    _check_date("Start date",   out["start_date"])
    _check_date("Planned end",  out.get("planned_end"))
    _check_date("Actual end",   out.get("actual_end"))

    if (out.get("planned_end") and out["start_date"]
            and out["planned_end"] < out["start_date"]):
        raise ValidationError(
            "Planned end must be on or after start date")

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("coordinator", "location", "subject_focus", "goals",
               "mentor_feedback", "mentee_feedback", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("planned_end", "actual_end"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v

    sp = out.get("sessions_planned")
    if sp in (None, ""):
        out["sessions_planned"] = None
    else:
        try:
            iv = int(sp)
        except (TypeError, ValueError):
            raise ValidationError("Sessions planned must be integer")
        if iv < 0:
            raise ValidationError("Sessions planned must be >= 0")
        out["sessions_planned"] = iv

    out["mentor_rating"] = _check_rating(
        "Mentor rating", out.get("mentor_rating"))
    out["mentee_rating"] = _check_rating(
        "Mentee rating", out.get("mentee_rating"))
    return out


# ── CRUD ─────────────────────────────────────────────────────────

def _row(r: sqlite3.Row) -> Pairing:
    return Pairing(
        pairing_id=r["pairing_id"],
        programme=r["programme"],
        mentor_id=r["mentor_id"],
        mentee_id=r["mentee_id"],
        coordinator=r["coordinator"],
        frequency=r["frequency"],
        start_date=r["start_date"],
        planned_end=r["planned_end"],
        actual_end=r["actual_end"],
        sessions_planned=r["sessions_planned"],
        location=r["location"],
        subject_focus=r["subject_focus"],
        goals=r["goals"],
        mentor_feedback=r["mentor_feedback"],
        mentee_feedback=r["mentee_feedback"],
        mentor_rating=r["mentor_rating"],
        mentee_rating=r["mentee_rating"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def _row_session(r: sqlite3.Row) -> Session:
    return Session(
        session_id=r["session_id"],
        pairing_id=r["pairing_id"],
        session_date=r["session_date"],
        duration_minutes=r["duration_minutes"],
        focus=r["focus"],
        attended=bool(r["attended"]),
        notes=r["notes"],
        created_on=r["created_on"],
    )


def create_pairing(payload: dict[str, Any]) -> Pairing:
    init_db()
    p = _validate_pairing(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO peer_mentoring_pairings (
              programme, mentor_id, mentee_id, coordinator,
              frequency, start_date, planned_end, actual_end,
              sessions_planned, location, subject_focus, goals,
              mentor_feedback, mentee_feedback,
              mentor_rating, mentee_rating, status, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?)
        """, (
            p["programme"], p["mentor_id"], p["mentee_id"],
            p["coordinator"], p["frequency"], p["start_date"],
            p["planned_end"], p["actual_end"],
            p["sessions_planned"], p["location"],
            p["subject_focus"], p["goals"],
            p["mentor_feedback"], p["mentee_feedback"],
            p["mentor_rating"], p["mentee_rating"],
            p["status"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_pairing(new_id)


def update_pairing(pairing_id: int,
                       payload: dict[str, Any]) -> Pairing:
    init_db()
    if get_pairing(pairing_id) is None:
        raise ValidationError(f"No pairing with id {pairing_id}")
    p = _validate_pairing(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE peer_mentoring_pairings SET
              programme=?, mentor_id=?, mentee_id=?, coordinator=?,
              frequency=?, start_date=?, planned_end=?, actual_end=?,
              sessions_planned=?, location=?, subject_focus=?,
              goals=?, mentor_feedback=?, mentee_feedback=?,
              mentor_rating=?, mentee_rating=?, status=?, notes=?,
              updated_on=?
            WHERE pairing_id=?
        """, (
            p["programme"], p["mentor_id"], p["mentee_id"],
            p["coordinator"], p["frequency"], p["start_date"],
            p["planned_end"], p["actual_end"],
            p["sessions_planned"], p["location"],
            p["subject_focus"], p["goals"],
            p["mentor_feedback"], p["mentee_feedback"],
            p["mentor_rating"], p["mentee_rating"],
            p["status"], p["notes"], now, pairing_id,
        ))
    return get_pairing(pairing_id)


def delete_pairing(pairing_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM peer_mentoring_pairings "
            "WHERE pairing_id=?", (pairing_id,))
        return cur.rowcount > 0


def get_pairing(pairing_id: int) -> Pairing | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM peer_mentoring_pairings "
            "WHERE pairing_id=?", (pairing_id,)).fetchone()
        return _row(r) if r else None


def list_pairings(*,
                      programme: str | None = None,
                      status: str | None = None,
                      mentor_id: str | None = None,
                      mentee_id: str | None = None,
                      either_id: str | None = None,
                      coordinator_like: str | None = None,
                      frequency: str | None = None,
                      open_only: bool = False,
                      active_only: bool = False,
                      ) -> list[Pairing]:
    init_db()
    sql = "SELECT * FROM peer_mentoring_pairings WHERE 1=1"
    params: list[Any] = []
    if programme:
        sql += " AND programme=?"
        params.append(programme)
    if status:
        sql += " AND status=?"
        params.append(status)
    if mentor_id:
        sql += " AND mentor_id=?"
        params.append(mentor_id)
    if mentee_id:
        sql += " AND mentee_id=?"
        params.append(mentee_id)
    if either_id:
        sql += " AND (mentor_id=? OR mentee_id=?)"
        params.extend([either_id, either_id])
    if coordinator_like:
        sql += " AND coordinator LIKE ?"
        params.append(f"%{coordinator_like}%")
    if frequency:
        sql += " AND frequency=?"
        params.append(frequency)
    if open_only:
        sql += (" AND status IN "
                  "('Pending Match','Active','Paused')")
    if active_only:
        sql += " AND status='Active'"
    sql += " ORDER BY start_date DESC, pairing_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def pairings_for_student(student_id: str) -> list[Pairing]:
    return list_pairings(either_id=student_id)


# ── Sessions ──────────────────────────────────────────────────────

def _validate_session(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["session_date"] = (out.get("session_date") or "").strip()
    if not out["session_date"]:
        raise ValidationError("Session date is required")
    _check_date("Session date", out["session_date"])
    try:
        dur = int(out.get("duration_minutes") or 0)
    except (TypeError, ValueError):
        raise ValidationError("Duration must be an integer")
    if dur <= 0:
        raise ValidationError("Duration must be > 0 minutes")
    out["duration_minutes"] = dur
    for k in ("focus", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    out["attended"] = bool(out.get("attended", True))
    return out


def add_session(pairing_id: int,
                    payload: dict[str, Any]) -> Session:
    init_db()
    if get_pairing(pairing_id) is None:
        raise ValidationError(f"No pairing with id {pairing_id}")
    p = _validate_session(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO peer_mentoring_sessions (
              pairing_id, session_date, duration_minutes,
              focus, attended, notes, created_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            pairing_id, p["session_date"], p["duration_minutes"],
            p["focus"], 1 if p["attended"] else 0,
            p["notes"], now,
        ))
        new_id = cur.lastrowid
        r = conn.execute(
            "SELECT * FROM peer_mentoring_sessions "
            "WHERE session_id=?", (new_id,)).fetchone()
    return _row_session(r)


def update_session(session_id: int,
                       payload: dict[str, Any]) -> Session:
    init_db()
    p = _validate_session(payload)
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM peer_mentoring_sessions "
            "WHERE session_id=?", (session_id,)).fetchone()
        if not r:
            raise ValidationError(
                f"No session with id {session_id}")
        conn.execute("""
            UPDATE peer_mentoring_sessions SET
              session_date=?, duration_minutes=?,
              focus=?, attended=?, notes=?
            WHERE session_id=?
        """, (
            p["session_date"], p["duration_minutes"],
            p["focus"], 1 if p["attended"] else 0,
            p["notes"], session_id,
        ))
        r2 = conn.execute(
            "SELECT * FROM peer_mentoring_sessions "
            "WHERE session_id=?", (session_id,)).fetchone()
    return _row_session(r2)


def delete_session(session_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM peer_mentoring_sessions "
            "WHERE session_id=?", (session_id,))
        return cur.rowcount > 0


def list_sessions(pairing_id: int) -> list[Session]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM peer_mentoring_sessions "
            "WHERE pairing_id=? "
            "ORDER BY session_date DESC, session_id DESC",
            (pairing_id,)).fetchall()
    return [_row_session(r) for r in rows]


def pairing_session_stats(pairing_id: int) -> dict[str, Any]:
    rows = list_sessions(pairing_id)
    total = len(rows)
    attended = sum(1 for s in rows if s.attended)
    minutes = sum(s.duration_minutes
                       for s in rows if s.attended)
    return {
        "total": total,
        "attended": attended,
        "missed": total - attended,
        "total_minutes": minutes,
        "total_hours": round(minutes / 60.0, 2),
        "most_recent": rows[0].session_date if rows else None,
    }


# ── Workflow helpers ─────────────────────────────────────────────

def _to_dict(p: Pairing) -> dict[str, Any]:
    return {
        "programme": p.programme,
        "mentor_id": p.mentor_id,
        "mentee_id": p.mentee_id,
        "coordinator": p.coordinator,
        "frequency": p.frequency,
        "start_date": p.start_date,
        "planned_end": p.planned_end,
        "actual_end": p.actual_end,
        "sessions_planned": p.sessions_planned,
        "location": p.location,
        "subject_focus": p.subject_focus,
        "goals": p.goals,
        "mentor_feedback": p.mentor_feedback,
        "mentee_feedback": p.mentee_feedback,
        "mentor_rating": p.mentor_rating,
        "mentee_rating": p.mentee_rating,
        "status": p.status,
        "notes": p.notes,
    }


def activate(pairing_id: int) -> Pairing:
    p = get_pairing(pairing_id)
    if p is None:
        raise ValidationError(f"No pairing with id {pairing_id}")
    return update_pairing(pairing_id,
                              {**_to_dict(p), "status": "Active"})


def pause(pairing_id: int) -> Pairing:
    p = get_pairing(pairing_id)
    if p is None:
        raise ValidationError(f"No pairing with id {pairing_id}")
    return update_pairing(pairing_id,
                              {**_to_dict(p), "status": "Paused"})


def complete(pairing_id: int, *,
                 mentor_feedback: str | None = None,
                 mentee_feedback: str | None = None,
                 mentor_rating: int | None = None,
                 mentee_rating: int | None = None,
                 ended_on: str | None = None) -> Pairing:
    p = get_pairing(pairing_id)
    if p is None:
        raise ValidationError(f"No pairing with id {pairing_id}")
    data = _to_dict(p)
    data["status"] = "Completed"
    data["actual_end"] = (ended_on
                              or _dt.date.today().isoformat())
    if mentor_feedback is not None:
        data["mentor_feedback"] = mentor_feedback
    if mentee_feedback is not None:
        data["mentee_feedback"] = mentee_feedback
    if mentor_rating is not None:
        data["mentor_rating"] = mentor_rating
    if mentee_rating is not None:
        data["mentee_rating"] = mentee_rating
    return update_pairing(pairing_id, data)


def withdraw(pairing_id: int, *,
                 reason: str | None = None) -> Pairing:
    p = get_pairing(pairing_id)
    if p is None:
        raise ValidationError(f"No pairing with id {pairing_id}")
    data = _to_dict(p)
    data["status"] = "Withdrawn"
    data["actual_end"] = _dt.date.today().isoformat()
    if reason:
        existing = data["notes"] or ""
        prefix = (existing + "\n") if existing else ""
        data["notes"] = prefix + f"Withdrawn: {reason}"
    return update_pairing(pairing_id, data)


def set_status(pairing_id: int, new_status: str) -> Pairing:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    p = get_pairing(pairing_id)
    if p is None:
        raise ValidationError(f"No pairing with id {pairing_id}")
    return update_pairing(pairing_id,
                              {**_to_dict(p), "status": new_status})


# ── Summary ───────────────────────────────────────────────────────

def summary() -> PairingSummary:
    pairings = list_pairings()
    out = PairingSummary(total=len(pairings))
    if not pairings:
        return out
    mentors: set[str] = set()
    mentees: set[str] = set()
    mentee_ratings: list[int] = []
    for p in pairings:
        mentors.add(p.mentor_id)
        mentees.add(p.mentee_id)
        if p.status == "Active":
            out.active += 1
        if p.status == "Pending Match":
            out.pending += 1
        if p.status == "Completed":
            out.completed += 1
        if p.mentee_rating is not None:
            mentee_ratings.append(p.mentee_rating)
        out.by_programme[p.programme] = (
            out.by_programme.get(p.programme, 0) + 1)
        out.by_status[p.status] = (
            out.by_status.get(p.status, 0) + 1)
        out.by_frequency[p.frequency] = (
            out.by_frequency.get(p.frequency, 0) + 1)
        stats = pairing_session_stats(p.pairing_id)
        out.total_sessions += stats["attended"]
        out.total_hours += stats["total_hours"]
    out.total_hours = round(out.total_hours, 2)
    out.distinct_mentors = len(mentors)
    out.distinct_mentees = len(mentees)
    if mentee_ratings:
        out.average_mentee_rating = round(
            sum(mentee_ratings) / len(mentee_ratings), 2)
    return out


__all__ = [
    "PROGRAMMES", "DEFAULT_PROGRAMME",
    "FREQUENCIES", "DEFAULT_FREQUENCY",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "Pairing", "Session", "PairingSummary",
    "init_db",
    "create_pairing", "update_pairing", "delete_pairing",
    "get_pairing", "list_pairings", "pairings_for_student",
    "add_session", "update_session", "delete_session",
    "list_sessions", "pairing_session_stats",
    "activate", "pause", "complete", "withdraw", "set_status",
    "summary",
]
