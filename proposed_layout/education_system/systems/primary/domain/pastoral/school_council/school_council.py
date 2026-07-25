"""School Council data layer for Primary School System.

Three tables:
- `school_council_members`: per-student membership with role,
  term-of-office and status. FK cascade on students.
- `school_council_meetings`: free-standing meeting records with
  agenda, minutes, attendees and decisions.
- `school_council_motions`: motions tied to a meeting (FK cascade)
  with proposer/seconder and a vote outcome.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.systems.primary.infrastructure import paths as _paths

logger = logging.getLogger(__name__)

ROLES: tuple[str, ...] = (
    "Chair",
    "Vice Chair",
    "Secretary",
    "Treasurer",
    "Year 12 Rep",
    "Year 13 Rep",
    "Wellbeing Rep",
    "Eco Rep",
    "Charities Rep",
    "Diversity Rep",
    "Sport Rep",
    "Events Rep",
    "Member",
    "Observer",
)
DEFAULT_ROLE = "Member"

MEMBER_STATUSES: tuple[str, ...] = (
    "Active",
    "Resigned",
    "Departed",
    "Suspended",
    "Term Ended",
)
DEFAULT_MEMBER_STATUS = "Active"

MEETING_TYPES: tuple[str, ...] = (
    "Full Council",
    "Executive",
    "Working Group",
    "AGM",
    "EGM",
    "Year Rep Forum",
    "Other",
)
DEFAULT_MEETING_TYPE = "Full Council"

MEETING_STATUSES: tuple[str, ...] = (
    "Scheduled",
    "Confirmed",
    "Completed",
    "Cancelled",
)
DEFAULT_MEETING_STATUS = "Scheduled"

MOTION_OUTCOMES: tuple[str, ...] = (
    "Pending",
    "Passed",
    "Failed",
    "Withdrawn",
    "Deferred",
)
DEFAULT_MOTION_OUTCOME = "Pending"


class ValidationError(Exception):
    pass


@dataclass
class Member:
    member_id: int
    student_id: str
    role: str
    term_start: str
    term_end: str | None
    elected_on: str | None
    status: str
    portfolio: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_active(self) -> bool:
        return self.status == "Active"


@dataclass
class Meeting:
    meeting_id: int
    meeting_date: str
    meeting_time: str | None
    meeting_type: str
    title: str
    location: str | None
    chair: str | None
    secretary: str | None
    attendees: str | None
    apologies: str | None
    agenda: str | None
    minutes: str | None
    decisions: str | None
    actions: str | None
    next_meeting_on: str | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status in ("Scheduled", "Confirmed")


@dataclass
class Motion:
    motion_id: int
    meeting_id: int
    motion_number: int
    title: str
    proposer: str | None
    seconder: str | None
    description: str | None
    votes_for: int
    votes_against: int
    votes_abstain: int
    outcome: str
    decided_on: str | None
    notes: str | None
    created_on: str

    @property
    def is_decided(self) -> bool:
        return self.outcome in ("Passed", "Failed",
                                       "Withdrawn", "Deferred")

    @property
    def total_votes(self) -> int:
        return (self.votes_for + self.votes_against
                  + self.votes_abstain)


@dataclass
class CouncilSummary:
    total_members: int = 0
    active_members: int = 0
    total_meetings: int = 0
    completed_meetings: int = 0
    total_motions: int = 0
    motions_passed: int = 0
    motions_failed: int = 0
    motions_pending: int = 0
    by_role: dict[str, int] = field(default_factory=dict)
    by_meeting_type: dict[str, int] = field(default_factory=dict)
    by_outcome: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.SCHOOL_COUNCIL_DB)
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
            CREATE TABLE IF NOT EXISTS school_council_members (
                member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                role TEXT NOT NULL,
                term_start TEXT NOT NULL,
                term_end TEXT,
                elected_on TEXT,
                status TEXT NOT NULL,
                portfolio TEXT,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(student_id)
                  ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS school_council_meetings (
                meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_date TEXT NOT NULL,
                meeting_time TEXT,
                meeting_type TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT,
                chair TEXT,
                secretary TEXT,
                attendees TEXT,
                apologies TEXT,
                agenda TEXT,
                minutes TEXT,
                decisions TEXT,
                actions TEXT,
                next_meeting_on TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS school_council_motions (
                motion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                motion_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                proposer TEXT,
                seconder TEXT,
                description TEXT,
                votes_for INTEGER NOT NULL DEFAULT 0,
                votes_against INTEGER NOT NULL DEFAULT 0,
                votes_abstain INTEGER NOT NULL DEFAULT 0,
                outcome TEXT NOT NULL,
                decided_on TEXT,
                notes TEXT,
                created_on TEXT NOT NULL,
                FOREIGN KEY(meeting_id)
                  REFERENCES school_council_meetings(meeting_id)
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


def _check_time(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.time.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be HH:MM")


def _student_exists(student_id: str) -> bool:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id=?",
                (student_id,)).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


# ── Members ──────────────────────────────────────────────────────

def _validate_member(p: dict[str, Any], *,
                          existing_id: int | None = None
                          ) -> dict[str, Any]:
    out = dict(p)
    out["student_id"] = (out.get("student_id") or "").strip()
    if not out["student_id"]:
        raise ValidationError("Student is required")
    if not _student_exists(out["student_id"]):
        raise ValidationError(
            f"No student with id {out['student_id']}")
    role = (out.get("role") or "").strip()
    if role not in ROLES:
        raise ValidationError(
            f"Role must be one of: {', '.join(ROLES)}")
    out["role"] = role
    out["term_start"] = (out.get("term_start") or "").strip()
    if not out["term_start"]:
        raise ValidationError("Term start is required")
    _check_date("Term start", out["term_start"])
    _check_date("Term end",   out.get("term_end"))
    _check_date("Elected on", out.get("elected_on"))
    if (out.get("term_end") and out["term_end"]
            < out["term_start"]):
        raise ValidationError(
            "Term end must be on or after term start")
    status = (out.get("status") or DEFAULT_MEMBER_STATUS).strip()
    if status not in MEMBER_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(MEMBER_STATUSES)}")
    out["status"] = status
    for k in ("portfolio", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("term_end", "elected_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v

    # At most one active membership per student in a role-bearing
    # position; allow multiple historical "Term Ended" rows.
    if status == "Active" and role != "Member":
        with _connect() as conn:
            row = conn.execute(
                "SELECT member_id FROM school_council_members "
                "WHERE student_id=? AND status='Active'",
                (out["student_id"],)).fetchone()
        if row and row["member_id"] != existing_id:
            raise ValidationError(
                f"Student {out['student_id']} already has an "
                f"active council role")
    return out


def _row_member(r: sqlite3.Row) -> Member:
    return Member(
        member_id=r["member_id"],
        student_id=r["student_id"],
        role=r["role"],
        term_start=r["term_start"],
        term_end=r["term_end"],
        elected_on=r["elected_on"],
        status=r["status"],
        portfolio=r["portfolio"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_member(payload: dict[str, Any]) -> Member:
    init_db()
    p = _validate_member(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO school_council_members (
              student_id, role, term_start, term_end, elected_on,
              status, portfolio, notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["student_id"], p["role"], p["term_start"],
            p["term_end"], p["elected_on"], p["status"],
            p["portfolio"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_member(new_id)


def update_member(member_id: int,
                      payload: dict[str, Any]) -> Member:
    init_db()
    if get_member(member_id) is None:
        raise ValidationError(f"No member with id {member_id}")
    p = _validate_member(payload, existing_id=member_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE school_council_members SET
              student_id=?, role=?, term_start=?, term_end=?,
              elected_on=?, status=?, portfolio=?, notes=?,
              updated_on=?
            WHERE member_id=?
        """, (
            p["student_id"], p["role"], p["term_start"],
            p["term_end"], p["elected_on"], p["status"],
            p["portfolio"], p["notes"], now, member_id,
        ))
    return get_member(member_id)


def delete_member(member_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM school_council_members "
            "WHERE member_id=?", (member_id,))
        return cur.rowcount > 0


def get_member(member_id: int) -> Member | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM school_council_members "
            "WHERE member_id=?", (member_id,)).fetchone()
        return _row_member(r) if r else None


def list_members(*,
                      student_id: str | None = None,
                      role: str | None = None,
                      status: str | None = None,
                      active_only: bool = False,
                      ) -> list[Member]:
    init_db()
    sql = "SELECT * FROM school_council_members WHERE 1=1"
    params: list[Any] = []
    if student_id:
        sql += " AND student_id=?"
        params.append(student_id)
    if role:
        sql += " AND role=?"
        params.append(role)
    if status:
        sql += " AND status=?"
        params.append(status)
    if active_only:
        sql += " AND status='Active'"
    sql += " ORDER BY term_start DESC, member_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_member(r) for r in rows]


def _to_member_dict(m: Member) -> dict[str, Any]:
    return {
        "student_id": m.student_id,
        "role": m.role,
        "term_start": m.term_start,
        "term_end": m.term_end,
        "elected_on": m.elected_on,
        "status": m.status,
        "portfolio": m.portfolio,
        "notes": m.notes,
    }


def end_term(member_id: int, *,
                 ended_on: str | None = None) -> Member:
    m = get_member(member_id)
    if m is None:
        raise ValidationError(f"No member with id {member_id}")
    data = _to_member_dict(m)
    data["status"] = "Term Ended"
    data["term_end"] = (ended_on
                            or _dt.date.today().isoformat())
    return update_member(member_id, data)


def set_member_status(member_id: int,
                            new_status: str) -> Member:
    if new_status not in MEMBER_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(MEMBER_STATUSES)}")
    m = get_member(member_id)
    if m is None:
        raise ValidationError(f"No member with id {member_id}")
    return update_member(member_id,
                              {**_to_member_dict(m),
                                "status": new_status})


# ── Meetings ─────────────────────────────────────────────────────

def _validate_meeting(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["meeting_date"] = (out.get("meeting_date") or "").strip()
    if not out["meeting_date"]:
        raise ValidationError("Meeting date is required")
    _check_date("Meeting date", out["meeting_date"])
    _check_time("Meeting time", out.get("meeting_time"))
    _check_date("Next meeting", out.get("next_meeting_on"))
    mt = (out.get("meeting_type") or "").strip()
    if mt not in MEETING_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(MEETING_TYPES)}")
    out["meeting_type"] = mt
    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Title is required")
    status = (out.get("status") or DEFAULT_MEETING_STATUS).strip()
    if status not in MEETING_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(MEETING_STATUSES)}")
    out["status"] = status
    for k in ("location", "chair", "secretary", "attendees",
               "apologies", "agenda", "minutes", "decisions",
               "actions", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("meeting_time", "next_meeting_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    return out


def _row_meeting(r: sqlite3.Row) -> Meeting:
    return Meeting(
        meeting_id=r["meeting_id"],
        meeting_date=r["meeting_date"],
        meeting_time=r["meeting_time"],
        meeting_type=r["meeting_type"],
        title=r["title"],
        location=r["location"],
        chair=r["chair"],
        secretary=r["secretary"],
        attendees=r["attendees"],
        apologies=r["apologies"],
        agenda=r["agenda"],
        minutes=r["minutes"],
        decisions=r["decisions"],
        actions=r["actions"],
        next_meeting_on=r["next_meeting_on"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_meeting(payload: dict[str, Any]) -> Meeting:
    init_db()
    p = _validate_meeting(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO school_council_meetings (
              meeting_date, meeting_time, meeting_type, title,
              location, chair, secretary, attendees, apologies,
              agenda, minutes, decisions, actions,
              next_meeting_on, status, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?)
        """, (
            p["meeting_date"], p["meeting_time"],
            p["meeting_type"], p["title"], p["location"],
            p["chair"], p["secretary"], p["attendees"],
            p["apologies"], p["agenda"], p["minutes"],
            p["decisions"], p["actions"], p["next_meeting_on"],
            p["status"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_meeting(new_id)


def update_meeting(meeting_id: int,
                       payload: dict[str, Any]) -> Meeting:
    init_db()
    if get_meeting(meeting_id) is None:
        raise ValidationError(f"No meeting with id {meeting_id}")
    p = _validate_meeting(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE school_council_meetings SET
              meeting_date=?, meeting_time=?, meeting_type=?,
              title=?, location=?, chair=?, secretary=?,
              attendees=?, apologies=?, agenda=?, minutes=?,
              decisions=?, actions=?, next_meeting_on=?,
              status=?, notes=?, updated_on=?
            WHERE meeting_id=?
        """, (
            p["meeting_date"], p["meeting_time"],
            p["meeting_type"], p["title"], p["location"],
            p["chair"], p["secretary"], p["attendees"],
            p["apologies"], p["agenda"], p["minutes"],
            p["decisions"], p["actions"], p["next_meeting_on"],
            p["status"], p["notes"], now, meeting_id,
        ))
    return get_meeting(meeting_id)


def delete_meeting(meeting_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM school_council_meetings "
            "WHERE meeting_id=?", (meeting_id,))
        return cur.rowcount > 0


def get_meeting(meeting_id: int) -> Meeting | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM school_council_meetings "
            "WHERE meeting_id=?", (meeting_id,)).fetchone()
        return _row_meeting(r) if r else None


def list_meetings(*,
                       meeting_type: str | None = None,
                       status: str | None = None,
                       upcoming_only: bool = False,
                       chair_like: str | None = None,
                       date_from: str | None = None,
                       date_to: str | None = None,
                       ) -> list[Meeting]:
    init_db()
    sql = "SELECT * FROM school_council_meetings WHERE 1=1"
    params: list[Any] = []
    if meeting_type:
        sql += " AND meeting_type=?"
        params.append(meeting_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    if upcoming_only:
        today = _dt.date.today().isoformat()
        sql += (" AND meeting_date >= ?"
                  " AND status NOT IN ('Cancelled','Completed')")
        params.append(today)
    if chair_like:
        sql += " AND chair LIKE ?"
        params.append(f"%{chair_like}%")
    if date_from:
        _check_date("From", date_from)
        sql += " AND meeting_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND meeting_date <= ?"
        params.append(date_to)
    sql += (" ORDER BY meeting_date DESC,"
              " meeting_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_meeting(r) for r in rows]


def _to_meeting_dict(m: Meeting) -> dict[str, Any]:
    return {
        "meeting_date": m.meeting_date,
        "meeting_time": m.meeting_time,
        "meeting_type": m.meeting_type,
        "title": m.title,
        "location": m.location,
        "chair": m.chair,
        "secretary": m.secretary,
        "attendees": m.attendees,
        "apologies": m.apologies,
        "agenda": m.agenda,
        "minutes": m.minutes,
        "decisions": m.decisions,
        "actions": m.actions,
        "next_meeting_on": m.next_meeting_on,
        "status": m.status,
        "notes": m.notes,
    }


def confirm_meeting(meeting_id: int) -> Meeting:
    m = get_meeting(meeting_id)
    if m is None:
        raise ValidationError(f"No meeting with id {meeting_id}")
    return update_meeting(meeting_id,
                                {**_to_meeting_dict(m),
                                  "status": "Confirmed"})


def complete_meeting(meeting_id: int, *,
                          minutes: str | None = None,
                          decisions: str | None = None,
                          actions: str | None = None
                          ) -> Meeting:
    m = get_meeting(meeting_id)
    if m is None:
        raise ValidationError(f"No meeting with id {meeting_id}")
    data = _to_meeting_dict(m)
    if minutes is not None:
        data["minutes"] = minutes
    if decisions is not None:
        data["decisions"] = decisions
    if actions is not None:
        data["actions"] = actions
    data["status"] = "Completed"
    return update_meeting(meeting_id, data)


def cancel_meeting(meeting_id: int) -> Meeting:
    m = get_meeting(meeting_id)
    if m is None:
        raise ValidationError(f"No meeting with id {meeting_id}")
    return update_meeting(meeting_id,
                                {**_to_meeting_dict(m),
                                  "status": "Cancelled"})


def set_meeting_status(meeting_id: int,
                            new_status: str) -> Meeting:
    if new_status not in MEETING_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(MEETING_STATUSES)}")
    m = get_meeting(meeting_id)
    if m is None:
        raise ValidationError(f"No meeting with id {meeting_id}")
    return update_meeting(meeting_id,
                                {**_to_meeting_dict(m),
                                  "status": new_status})


# ── Motions ──────────────────────────────────────────────────────

def _next_motion_number(meeting_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT MAX(motion_number) m "
            "FROM school_council_motions WHERE meeting_id=?",
            (meeting_id,)).fetchone()
    return int(row["m"] or 0) + 1


def _validate_motion(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Motion title is required")
    outcome = (out.get("outcome")
                  or DEFAULT_MOTION_OUTCOME).strip()
    if outcome not in MOTION_OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of: "
            f"{', '.join(MOTION_OUTCOMES)}")
    out["outcome"] = outcome
    _check_date("Decided on", out.get("decided_on"))
    for k in ("proposer", "seconder", "description", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("votes_for", "votes_against", "votes_abstain"):
        v = out.get(k, 0)
        if v in (None, ""):
            out[k] = 0
            continue
        try:
            iv = int(v)
        except (TypeError, ValueError):
            raise ValidationError(
                f"{k.replace('_', ' ')} must be an integer")
        if iv < 0:
            raise ValidationError(
                f"{k.replace('_', ' ')} must be >= 0")
        out[k] = iv
    dv = out.get("decided_on")
    if dv in (None, ""):
        out["decided_on"] = None
    elif isinstance(dv, str):
        out["decided_on"] = dv.strip() or None
    else:
        out["decided_on"] = dv
    return out


def _row_motion(r: sqlite3.Row) -> Motion:
    return Motion(
        motion_id=r["motion_id"],
        meeting_id=r["meeting_id"],
        motion_number=r["motion_number"],
        title=r["title"],
        proposer=r["proposer"],
        seconder=r["seconder"],
        description=r["description"],
        votes_for=r["votes_for"],
        votes_against=r["votes_against"],
        votes_abstain=r["votes_abstain"],
        outcome=r["outcome"],
        decided_on=r["decided_on"],
        notes=r["notes"],
        created_on=r["created_on"],
    )


def add_motion(meeting_id: int,
                   payload: dict[str, Any]) -> Motion:
    init_db()
    if get_meeting(meeting_id) is None:
        raise ValidationError(f"No meeting with id {meeting_id}")
    p = _validate_motion(payload)
    number = _next_motion_number(meeting_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO school_council_motions (
              meeting_id, motion_number, title, proposer,
              seconder, description, votes_for, votes_against,
              votes_abstain, outcome, decided_on, notes,
              created_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            meeting_id, number, p["title"], p["proposer"],
            p["seconder"], p["description"],
            p["votes_for"], p["votes_against"],
            p["votes_abstain"], p["outcome"],
            p["decided_on"], p["notes"], now,
        ))
        new_id = cur.lastrowid
    return get_motion(new_id)


def update_motion(motion_id: int,
                       payload: dict[str, Any]) -> Motion:
    init_db()
    if get_motion(motion_id) is None:
        raise ValidationError(f"No motion with id {motion_id}")
    p = _validate_motion(payload)
    with _connect() as conn:
        conn.execute("""
            UPDATE school_council_motions SET
              title=?, proposer=?, seconder=?, description=?,
              votes_for=?, votes_against=?, votes_abstain=?,
              outcome=?, decided_on=?, notes=?
            WHERE motion_id=?
        """, (
            p["title"], p["proposer"], p["seconder"],
            p["description"], p["votes_for"],
            p["votes_against"], p["votes_abstain"],
            p["outcome"], p["decided_on"], p["notes"],
            motion_id,
        ))
    return get_motion(motion_id)


def delete_motion(motion_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM school_council_motions "
            "WHERE motion_id=?", (motion_id,))
        return cur.rowcount > 0


def get_motion(motion_id: int) -> Motion | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM school_council_motions "
            "WHERE motion_id=?", (motion_id,)).fetchone()
        return _row_motion(r) if r else None


def list_motions(*,
                      meeting_id: int | None = None,
                      outcome: str | None = None,
                      pending_only: bool = False,
                      ) -> list[Motion]:
    init_db()
    sql = "SELECT * FROM school_council_motions WHERE 1=1"
    params: list[Any] = []
    if meeting_id is not None:
        sql += " AND meeting_id=?"
        params.append(meeting_id)
    if outcome:
        sql += " AND outcome=?"
        params.append(outcome)
    if pending_only:
        sql += " AND outcome='Pending'"
    sql += " ORDER BY meeting_id DESC, motion_number ASC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_motion(r) for r in rows]


def record_vote(motion_id: int, *,
                    votes_for: int, votes_against: int,
                    votes_abstain: int = 0,
                    decided_on: str | None = None) -> Motion:
    m = get_motion(motion_id)
    if m is None:
        raise ValidationError(f"No motion with id {motion_id}")
    if votes_for < 0 or votes_against < 0 or votes_abstain < 0:
        raise ValidationError("Vote counts must be >= 0")
    payload = {
        "title": m.title,
        "proposer": m.proposer,
        "seconder": m.seconder,
        "description": m.description,
        "votes_for": votes_for,
        "votes_against": votes_against,
        "votes_abstain": votes_abstain,
        "outcome": ("Passed" if votes_for > votes_against
                       else "Failed"),
        "decided_on": (decided_on
                          or _dt.date.today().isoformat()),
        "notes": m.notes,
    }
    return update_motion(motion_id, payload)


# ── Summary ───────────────────────────────────────────────────────

def summary() -> CouncilSummary:
    members = list_members()
    meetings = list_meetings()
    motions = list_motions()
    out = CouncilSummary(
        total_members=len(members),
        active_members=sum(1 for m in members if m.is_active),
        total_meetings=len(meetings),
        completed_meetings=sum(1 for mt in meetings
                                  if mt.status == "Completed"),
        total_motions=len(motions),
        motions_passed=sum(1 for mo in motions
                              if mo.outcome == "Passed"),
        motions_failed=sum(1 for mo in motions
                              if mo.outcome == "Failed"),
        motions_pending=sum(1 for mo in motions
                                if mo.outcome == "Pending"),
    )
    for m in members:
        out.by_role[m.role] = out.by_role.get(m.role, 0) + 1
    for mt in meetings:
        out.by_meeting_type[mt.meeting_type] = (
            out.by_meeting_type.get(mt.meeting_type, 0) + 1)
    for mo in motions:
        out.by_outcome[mo.outcome] = (
            out.by_outcome.get(mo.outcome, 0) + 1)
    return out


__all__ = [
    "ROLES", "DEFAULT_ROLE",
    "MEMBER_STATUSES", "DEFAULT_MEMBER_STATUS",
    "MEETING_TYPES", "DEFAULT_MEETING_TYPE",
    "MEETING_STATUSES", "DEFAULT_MEETING_STATUS",
    "MOTION_OUTCOMES", "DEFAULT_MOTION_OUTCOME",
    "ValidationError",
    "Member", "Meeting", "Motion", "CouncilSummary",
    "init_db",
    "create_member", "update_member", "delete_member",
    "get_member", "list_members",
    "end_term", "set_member_status",
    "create_meeting", "update_meeting", "delete_meeting",
    "get_meeting", "list_meetings",
    "confirm_meeting", "complete_meeting", "cancel_meeting",
    "set_meeting_status",
    "add_motion", "update_motion", "delete_motion",
    "get_motion", "list_motions",
    "record_vote",
    "summary",
]
