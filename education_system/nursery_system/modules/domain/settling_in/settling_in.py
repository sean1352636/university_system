"""Domain layer for Settling-In (Nursery System).

Owns the ``settling_in`` table — the EYFS settling-in sessions logged when a
child first joins (home visit, taster session, first sessions, reviews). Each
row records the session type, who led it (the key person), how long it lasted
and how the child settled, so the key person can track a child's progress to
"Settled".

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``settling_in_cli.py``, Tk GUI in ``settling_in_views.py``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Settling-In"
CATEGORY = "Children & Admissions"

ID_PREFIX = "NSI"
ID_DIGITS = 3

SESSION_TYPES = (
    "Home visit", "Taster session", "Stay & play", "First session",
    "Settling review",
)
RATINGS = ("Unsettled", "Settling", "Settled")
_RATING_RANK = {r: i for i, r in enumerate(RATINGS)}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid settling-in input."""


@dataclass
class SettlingSession:
    session_id: str
    pupil_id: str
    session_date: str | None
    session_type: str | None
    duration_minutes: int | None
    key_person: str | None
    settled_rating: str | None
    notes: str | None
    child_name: str | None = None
    room: str | None = None
    key_person_name: str | None = None


@dataclass
class ChildSettling:
    pupil_id: str
    child_name: str
    room: str | None
    session_count: int
    latest_rating: str | None
    latest_date: str | None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for settling-in")
        raise


_SELECT = """
SELECT si.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS key_person_name
FROM settling_in si
LEFT JOIN pupils p ON p.pupil_id = si.pupil_id
LEFT JOIN staff s ON s.staff_id = si.key_person
"""


def _row(r: sqlite3.Row) -> SettlingSession:
    keys = r.keys()
    return SettlingSession(
        session_id=r["session_id"],
        pupil_id=r["pupil_id"],
        session_date=r["session_date"],
        session_type=r["session_type"],
        duration_minutes=r["duration_minutes"],
        key_person=r["key_person"],
        settled_rating=r["settled_rating"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        key_person_name=(r["key_person_name"] or None) if "key_person_name" in keys
        else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _opt_int(value: Any, label: str) -> int | None:
    raw = str(value if value is not None else "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError as e:
        raise ValidationError(f"{label} must be a whole number") from e
    if n < 0:
        raise ValidationError(f"{label} cannot be negative")
    return n


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    out["session_date"] = _opt_date(data.get("session_date"), "Session date")

    stype = (data.get("session_type") or "").strip()
    if stype and stype not in SESSION_TYPES:
        raise ValidationError(
            "Session type must be one of: " + ", ".join(SESSION_TYPES))
    out["session_type"] = stype or None

    out["duration_minutes"] = _opt_int(data.get("duration_minutes"),
                                       "Duration (minutes)")
    out["key_person"] = _opt(data.get("key_person"))

    rating = (data.get("settled_rating") or "").strip()
    if rating and rating not in RATINGS:
        raise ValidationError("Settled rating must be one of: " + ", ".join(RATINGS))
    out["settled_rating"] = rating or None

    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_session_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT session_id FROM settling_in").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing settling-in ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        sid = f"{ID_PREFIX}{n}"
        if sid not in existing:
            return sid
    raise RuntimeError("Could not allocate a unique settling-in id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_sessions(*, pupil_id: str | None = None) -> list[SettlingSession]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE si.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY si.session_date DESC, si.session_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_sessions failed")
        raise
    return [_row(r) for r in rows]


def get_session(session_id: str) -> SettlingSession | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE si.session_id = ?", (session_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_session(%s) failed", session_id)
        raise
    return _row(row) if row else None


def list_by_child() -> list[ChildSettling]:
    """Per active child: session count + most-recent settled rating."""
    _ensure_schema()
    sessions = list_sessions()
    try:
        with connect() as conn:
            pupils = conn.execute(
                "SELECT pupil_id, TRIM(first_name || ' ' || last_name) AS name, "
                "room FROM pupils WHERE status = 'active' "
                "ORDER BY room, name").fetchall()
    except sqlite3.Error:
        logger.exception("list_by_child failed")
        raise
    by_pupil: dict[str, list[SettlingSession]] = {}
    for s in sessions:
        by_pupil.setdefault(s.pupil_id, []).append(s)
    out: list[ChildSettling] = []
    for p in pupils:
        ss = by_pupil.get(p["pupil_id"], [])
        # sessions already date-desc; first with a rating is the latest rating
        latest = next((x for x in ss if x.settled_rating), ss[0] if ss else None)
        out.append(ChildSettling(
            pupil_id=p["pupil_id"], child_name=p["name"], room=p["room"],
            session_count=len(ss),
            latest_rating=latest.settled_rating if latest else None,
            latest_date=ss[0].session_date if ss else None,
        ))
    return out


def list_pupil_choices() -> list[tuple[str, str]]:
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
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name FROM staff "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
            for r in rows]


# ── Writes ───────────────────────────────────────────────────────────────────

def create_session(data: dict[str, Any]) -> SettlingSession:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    sid = generate_session_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO settling_in (
                    session_id, pupil_id, session_date, session_type,
                    duration_minutes, key_person, settled_rating, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sid, payload["pupil_id"], payload["session_date"],
                 payload["session_type"], payload["duration_minutes"],
                 payload["key_person"], payload["settled_rating"],
                 payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for settling-in id=%s", sid)
        raise ValidationError(f"Could not create session — {e}") from e
    s = get_session(sid)
    assert s is not None
    logger.info("Created settling-in session %s for pupil %s",
                sid, payload["pupil_id"])
    return s


def update_session(session_id: str, data: dict[str, Any]) -> SettlingSession:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE settling_in SET
                    session_date = ?, session_type = ?, duration_minutes = ?,
                    key_person = ?, settled_rating = ?, notes = ?
                WHERE session_id = ?
                """,
                (payload["session_date"], payload["session_type"],
                 payload["duration_minutes"], payload["key_person"],
                 payload["settled_rating"], payload["notes"], session_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No settling-in session with id {session_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for settling-in id=%s", session_id)
        raise ValidationError(f"Could not update session — {e}") from e
    s = get_session(session_id)
    assert s is not None
    logger.info("Updated settling-in session %s", session_id)
    return s


def delete_session(session_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM settling_in WHERE session_id = ?", (session_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting settling-in id=%s", session_id)
        raise
    if deleted:
        logger.info("Deleted settling-in session %s", session_id)
    return deleted
