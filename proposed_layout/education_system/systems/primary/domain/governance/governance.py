"""Governance register for the Primary School System.

Two related tables:

* ``governors`` — members of the governing body / trust board, with
  role, term dates, contact info and current status.
* ``governance_meetings`` — scheduled and held meetings, with kind
  (Full board / Committee / EGM / AGM), date, attendees count, minutes
  pointer and decisions/notes.

Cascades: meetings are independent of governors. Deleting a governor
leaves historical meeting attendance counts intact (they're stored as
integers, not as join rows).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.GOVERNANCE_DB

GOVERNOR_ROLES: tuple[str, ...] = (
    "Chair", "Vice-chair", "Trustee", "Parent governor",
    "Staff governor", "Co-opted", "Local authority", "Observer",
)
DEFAULT_GOVERNOR_ROLE: str = "Trustee"

GOVERNOR_STATUSES: tuple[str, ...] = ("Active", "On leave", "Resigned", "Ended")
DEFAULT_GOVERNOR_STATUS: str = "Active"

MEETING_KINDS: tuple[str, ...] = (
    "Full board", "Committee", "EGM", "AGM", "Other",
)
DEFAULT_MEETING_KIND: str = "Full board"

MEETING_STATUSES: tuple[str, ...] = ("Scheduled", "Held", "Cancelled")
DEFAULT_MEETING_STATUS: str = "Scheduled"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS governors (
    governor_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name    TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT 'Trustee',
    email        TEXT,
    phone        TEXT,
    term_start   TEXT,
    term_end     TEXT,
    status       TEXT NOT NULL DEFAULT 'Active',
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gov_status ON governors(status);
CREATE INDEX IF NOT EXISTS idx_gov_role   ON governors(role);

CREATE TABLE IF NOT EXISTS governance_meetings (
    meeting_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_date TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'Full board',
    title        TEXT NOT NULL,
    chair        TEXT,
    attendees    INTEGER NOT NULL DEFAULT 0,
    minutes_ref  TEXT,
    decisions    TEXT,
    status       TEXT NOT NULL DEFAULT 'Scheduled',
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gm_date   ON governance_meetings(meeting_date);
CREATE INDEX IF NOT EXISTS idx_gm_status ON governance_meetings(status);
"""


# ── Result types ───────────────────────────────────────────────────

@dataclass
class Governor:
    governor_id: int
    full_name: str
    role: str
    email: str | None
    phone: str | None
    term_start: str | None
    term_end: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Meeting:
    meeting_id: int
    meeting_date: str
    kind: str
    title: str
    chair: str | None
    attendees: int
    minutes_ref: str | None
    decisions: str | None
    status: str
    created_at: str
    updated_at: str


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Governance schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_g(r: sqlite3.Row) -> Governor:
    return Governor(
        governor_id=r["governor_id"], full_name=r["full_name"],
        role=r["role"], email=r["email"], phone=r["phone"],
        term_start=r["term_start"], term_end=r["term_end"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_m(r: sqlite3.Row) -> Meeting:
    return Meeting(
        meeting_id=r["meeting_id"], meeting_date=r["meeting_date"],
        kind=r["kind"], title=r["title"], chair=r["chair"],
        attendees=r["attendees"], minutes_ref=r["minutes_ref"],
        decisions=r["decisions"], status=r["status"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ─────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _validate_date(v: Any, label: str, *, required: bool = False) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_in(v: Any, options: tuple[str, ...], label: str) -> str:
    s = (v or "").strip()
    if s not in options:
        raise ValidationError(f"{label} must be one of: {', '.join(options)}")
    return s


def _validate_governor(data: dict[str, Any], *, partial: bool = False
                         ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "full_name" in data or not partial:
        name = (data.get("full_name") or "").strip()
        if not name:
            raise ValidationError("Full name is required")
        if len(name) > 100:
            raise ValidationError("Full name must be 100 chars or fewer")
        out["full_name"] = name
    if "role" in data or not partial:
        out["role"] = _validate_in(
            data.get("role") or DEFAULT_GOVERNOR_ROLE,
            GOVERNOR_ROLES, "Role")
    if "email" in data:
        out["email"] = (data.get("email") or "").strip() or None
    if "phone" in data:
        out["phone"] = (data.get("phone") or "").strip() or None
    if "term_start" in data:
        out["term_start"] = _validate_date(data.get("term_start"), "Term start")
    if "term_end" in data:
        out["term_end"] = _validate_date(data.get("term_end"), "Term end")
    if "status" in data or not partial:
        out["status"] = _validate_in(
            data.get("status") or DEFAULT_GOVERNOR_STATUS,
            GOVERNOR_STATUSES, "Status")
    if "notes" in data:
        n = (data.get("notes") or "").strip() or None
        if n and len(n) > 1000:
            raise ValidationError("Notes must be 1000 chars or fewer")
        out["notes"] = n
    # Sanity: term_start ≤ term_end
    ts = out.get("term_start")
    te = out.get("term_end")
    if ts and te and ts > te:
        raise ValidationError("Term start cannot be after term end")
    return out


def _validate_meeting(data: dict[str, Any], *, partial: bool = False
                        ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "meeting_date" in data or not partial:
        out["meeting_date"] = _validate_date(
            data.get("meeting_date"), "Meeting date", required=True)
    if "kind" in data or not partial:
        out["kind"] = _validate_in(
            data.get("kind") or DEFAULT_MEETING_KIND,
            MEETING_KINDS, "Kind")
    if "title" in data or not partial:
        t = (data.get("title") or "").strip()
        if not t:
            raise ValidationError("Title is required")
        if len(t) > 200:
            raise ValidationError("Title must be 200 chars or fewer")
        out["title"] = t
    if "chair" in data:
        out["chair"] = (data.get("chair") or "").strip() or None
    if "attendees" in data:
        raw = data.get("attendees")
        if raw in (None, ""):
            out["attendees"] = 0
        else:
            try:
                n = int(raw)
            except (TypeError, ValueError):
                raise ValidationError("Attendees must be a whole number") from None
            if n < 0 or n > 1000:
                raise ValidationError("Attendees must be 0..1000")
            out["attendees"] = n
    if "minutes_ref" in data:
        out["minutes_ref"] = (data.get("minutes_ref") or "").strip() or None
    if "decisions" in data:
        d = (data.get("decisions") or "").strip() or None
        if d and len(d) > 4000:
            raise ValidationError("Decisions must be 4000 chars or fewer")
        out["decisions"] = d
    if "status" in data or not partial:
        out["status"] = _validate_in(
            data.get("status") or DEFAULT_MEETING_STATUS,
            MEETING_STATUSES, "Status")
    return out


# ── Governor CRUD ──────────────────────────────────────────────────

def create_governor(data: dict[str, Any]) -> Governor:
    init_db()
    cleaned = _validate_governor(data, partial=False)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO governors
                (full_name, role, email, phone, term_start, term_end,
                 status, notes)
               VALUES (:full_name, :role, :email, :phone, :term_start,
                       :term_end, :status, :notes)""",
            {
                "full_name": cleaned["full_name"], "role": cleaned["role"],
                "email": cleaned.get("email"), "phone": cleaned.get("phone"),
                "term_start": cleaned.get("term_start"),
                "term_end": cleaned.get("term_end"),
                "status": cleaned["status"], "notes": cleaned.get("notes"),
            })
        gid = cur.lastrowid
        conn.commit()
    out = get_governor(gid)
    assert out is not None
    logger.info("Created governor #%d (%s)", gid, cleaned["full_name"])
    return out


def get_governor(governor_id: int) -> Governor | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM governors WHERE governor_id = ?",
            (governor_id,)).fetchone()
        return _row_g(r) if r else None


def list_governors(
    *,
    status: str | None = None,
    role: str | None = None,
    query: str | None = None,
) -> list[Governor]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("status = ?")
        args.append(_validate_in(status, GOVERNOR_STATUSES, "Status"))
    if role:
        clauses.append("role = ?")
        args.append(_validate_in(role, GOVERNOR_ROLES, "Role"))
    if query:
        like = f"%{query.strip()}%"
        clauses.append("(full_name LIKE ? OR email LIKE ? OR notes LIKE ?)")
        args.extend([like, like, like])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM governors {where} "
           "ORDER BY status, role, full_name")
    with _connect() as conn:
        return [_row_g(r) for r in conn.execute(sql, args).fetchall()]


def update_governor(governor_id: int, data: dict[str, Any]) -> Governor:
    init_db()
    if get_governor(governor_id) is None:
        raise ValidationError(f"No governor #{governor_id}")
    cleaned = _validate_governor(data, partial=True)
    if not cleaned:
        out = get_governor(governor_id)
        assert out is not None
        return out
    sets = ", ".join(f"{k} = :{k}" for k in cleaned)
    cleaned["governor_id"] = governor_id
    with _connect() as conn:
        conn.execute(
            f"UPDATE governors SET {sets}, "
            "updated_at = datetime('now') WHERE governor_id = :governor_id",
            cleaned)
        conn.commit()
    out = get_governor(governor_id)
    assert out is not None
    logger.info("Updated governor #%d", governor_id)
    return out


def delete_governor(governor_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM governors WHERE governor_id = ?",
            (governor_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted governor #%d", governor_id)
            return True
        return False


# ── Meeting CRUD ───────────────────────────────────────────────────

def create_meeting(data: dict[str, Any]) -> Meeting:
    init_db()
    cleaned = _validate_meeting(data, partial=False)
    cleaned.setdefault("attendees", 0)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO governance_meetings
                (meeting_date, kind, title, chair, attendees,
                 minutes_ref, decisions, status)
               VALUES (:meeting_date, :kind, :title, :chair, :attendees,
                       :minutes_ref, :decisions, :status)""",
            {
                "meeting_date": cleaned["meeting_date"], "kind": cleaned["kind"],
                "title": cleaned["title"], "chair": cleaned.get("chair"),
                "attendees": cleaned.get("attendees", 0),
                "minutes_ref": cleaned.get("minutes_ref"),
                "decisions": cleaned.get("decisions"),
                "status": cleaned["status"],
            })
        mid = cur.lastrowid
        conn.commit()
    out = get_meeting(mid)
    assert out is not None
    logger.info("Created meeting #%d (%s)", mid, cleaned["title"])
    return out


def get_meeting(meeting_id: int) -> Meeting | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM governance_meetings WHERE meeting_id = ?",
            (meeting_id,)).fetchone()
        return _row_m(r) if r else None


def list_meetings(
    *,
    status: str | None = None,
    kind: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    query: str | None = None,
) -> list[Meeting]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("status = ?")
        args.append(_validate_in(status, MEETING_STATUSES, "Status"))
    if kind:
        clauses.append("kind = ?")
        args.append(_validate_in(kind, MEETING_KINDS, "Kind"))
    if date_from:
        clauses.append("meeting_date >= ?")
        args.append(_validate_date(date_from, "date_from", required=True))
    if date_to:
        clauses.append("meeting_date <= ?")
        args.append(_validate_date(date_to, "date_to", required=True))
    if query:
        like = f"%{query.strip()}%"
        clauses.append("(title LIKE ? OR decisions LIKE ? OR chair LIKE ?)")
        args.extend([like, like, like])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM governance_meetings {where} "
           "ORDER BY meeting_date DESC, meeting_id DESC")
    with _connect() as conn:
        return [_row_m(r) for r in conn.execute(sql, args).fetchall()]


def update_meeting(meeting_id: int, data: dict[str, Any]) -> Meeting:
    init_db()
    if get_meeting(meeting_id) is None:
        raise ValidationError(f"No meeting #{meeting_id}")
    cleaned = _validate_meeting(data, partial=True)
    if not cleaned:
        out = get_meeting(meeting_id)
        assert out is not None
        return out
    sets = ", ".join(f"{k} = :{k}" for k in cleaned)
    cleaned["meeting_id"] = meeting_id
    with _connect() as conn:
        conn.execute(
            f"UPDATE governance_meetings SET {sets}, "
            "updated_at = datetime('now') WHERE meeting_id = :meeting_id",
            cleaned)
        conn.commit()
    out = get_meeting(meeting_id)
    assert out is not None
    logger.info("Updated meeting #%d", meeting_id)
    return out


def delete_meeting(meeting_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM governance_meetings WHERE meeting_id = ?",
            (meeting_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted meeting #%d", meeting_id)
            return True
        return False


def mark_held(meeting_id: int, *, attendees: int | None = None,
               decisions: str | None = None,
               minutes_ref: str | None = None) -> Meeting:
    """Flip a meeting from 'Scheduled' to 'Held' and stamp attendance,
    minutes ref and decisions in one shot."""
    init_db()
    existing = get_meeting(meeting_id)
    if existing is None:
        raise ValidationError(f"No meeting #{meeting_id}")
    payload: dict[str, Any] = {"status": "Held"}
    if attendees is not None:
        payload["attendees"] = attendees
    if decisions is not None:
        payload["decisions"] = decisions
    if minutes_ref is not None:
        payload["minutes_ref"] = minutes_ref
    return update_meeting(meeting_id, payload)


# ── Summaries ──────────────────────────────────────────────────────

@dataclass
class Summary:
    governors_total: int
    governors_active: int
    governors_by_role: dict[str, int]
    governors_by_status: dict[str, int]
    term_expiring_90d: int

    meetings_total: int
    meetings_scheduled: int
    meetings_held: int
    meetings_cancelled: int
    next_meeting: Meeting | None
    last_held: Meeting | None


def summary() -> Summary:
    init_db()
    today = _dt.date.today()
    soon = (today + _dt.timedelta(days=90)).isoformat()
    today_s = today.isoformat()

    governors = list_governors()
    by_role: dict[str, int] = {r: 0 for r in GOVERNOR_ROLES}
    by_status: dict[str, int] = {s: 0 for s in GOVERNOR_STATUSES}
    expiring = 0
    for g in governors:
        by_role[g.role] = by_role.get(g.role, 0) + 1
        by_status[g.status] = by_status.get(g.status, 0) + 1
        if g.status == "Active" and g.term_end and today_s <= g.term_end <= soon:
            expiring += 1

    meetings = list_meetings()
    by_mstatus = {s: 0 for s in MEETING_STATUSES}
    for m in meetings:
        by_mstatus[m.status] = by_mstatus.get(m.status, 0) + 1

    upcoming = [m for m in meetings
                if m.status == "Scheduled" and m.meeting_date >= today_s]
    upcoming.sort(key=lambda m: m.meeting_date)
    next_meeting = upcoming[0] if upcoming else None

    held = [m for m in meetings if m.status == "Held"]
    held.sort(key=lambda m: m.meeting_date, reverse=True)
    last_held = held[0] if held else None

    return Summary(
        governors_total=len(governors),
        governors_active=by_status.get("Active", 0),
        governors_by_role=by_role,
        governors_by_status=by_status,
        term_expiring_90d=expiring,
        meetings_total=len(meetings),
        meetings_scheduled=by_mstatus.get("Scheduled", 0),
        meetings_held=by_mstatus.get("Held", 0),
        meetings_cancelled=by_mstatus.get("Cancelled", 0),
        next_meeting=next_meeting,
        last_held=last_held,
    )
