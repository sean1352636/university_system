"""Domain layer for Sign In / Sign Out (Nursery System).

Owns the ``sign_in_out_log`` table — the timestamped record of arrivals and
collections. One row per in/out event, capturing the time, who dropped off or
collected the child (and their relationship — collectors should be on the
authorised list) and the staff member who recorded it. This is the legal record
of who had the child and when, distinct from the daily present/absent register.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``sign_in_out_cli.py``, Tk GUI in ``sign_in_out_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Sign In / Sign Out"
CATEGORY = "Daily Care & Routines"

ID_PREFIX = "NSO"
ID_DIGITS = 3

DIRECTIONS = ("in", "out")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid sign in / out input."""


@dataclass
class SignEvent:
    event_id: str
    pupil_id: str
    event_date: str
    event_time: str | None
    direction: str
    person_name: str | None
    relationship: str | None
    recorded_by: str | None
    notes: str | None
    child_name: str | None = None
    recorded_by_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for sign in / out")
        raise


_SELECT = """
SELECT s.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       TRIM(st.first_name || ' ' || st.last_name) AS recorded_by_name
FROM sign_in_out_log s
LEFT JOIN pupils p ON p.pupil_id = s.pupil_id
LEFT JOIN staff st ON st.staff_id = s.recorded_by
"""


def _row(r: sqlite3.Row) -> SignEvent:
    keys = r.keys()
    return SignEvent(
        event_id=r["event_id"],
        pupil_id=r["pupil_id"],
        event_date=r["event_date"],
        event_time=r["event_time"],
        direction=r["direction"],
        person_name=r["person_name"],
        relationship=r["relationship"],
        recorded_by=r["recorded_by"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        recorded_by_name=(
            r["recorded_by_name"] if "recorded_by_name" in keys else None),
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _today() -> str:
    return _dt.date.today().isoformat()


def _now() -> str:
    return _dt.datetime.now().strftime("%H:%M")


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    direction = (data.get("direction") or "in").strip().lower()
    if direction not in DIRECTIONS:
        raise ValidationError(
            "Direction must be one of: " + ", ".join(DIRECTIONS))
    out["direction"] = direction

    event_date = (data.get("event_date") or "").strip() or _today()
    if not _DATE_RE.match(event_date):
        raise ValidationError("Event date must be YYYY-MM-DD")
    out["event_date"] = event_date

    event_time = (data.get("event_time") or "").strip()
    if event_time and not _TIME_RE.match(event_time):
        raise ValidationError("Event time must be HH:MM")
    out["event_time"] = event_time or None

    out["person_name"] = _opt(data.get("person_name"))
    out["relationship"] = _opt(data.get("relationship"))
    out["notes"] = _opt(data.get("notes"))
    out["recorded_by"] = _opt(data.get("recorded_by"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_event_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT event_id FROM sign_in_out_log").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing sign in / out ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        eid = f"{ID_PREFIX}{n}"
        if eid not in existing:
            return eid
    raise RuntimeError("Could not allocate a unique sign in / out id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_events(*, event_date: str | None = None,
                direction: str | None = None) -> list[SignEvent]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if event_date:
        clauses.append("s.event_date = ?")
        params.append(event_date)
    if direction:
        clauses.append("s.direction = ?")
        params.append(direction)
    sql = _SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY s.event_date DESC, s.event_time DESC, s.event_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_events failed")
        raise
    return [_row(r) for r in rows]


def get_event(event_id: str) -> SignEvent | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE s.event_id = ?", (event_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_event(%s) failed", event_id)
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
    """Return ``(staff_id, "Name (id) — role")`` pairs for staff pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name, role FROM staff "
                "WHERE end_date IS NULL OR end_date = '' "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    out = []
    for r in rows:
        role = f" — {r['role']}" if r["role"] else ""
        out.append((r["staff_id"],
                    f"{r['first_name']} {r['last_name']} ({r['staff_id']}){role}"))
    return out


def currently_in(event_date: str) -> list[SignEvent]:
    """Active children with an 'in' event but no later 'out' that date.

    Returns the latest 'in' event per such child, so callers can show who is
    currently on the premises.
    """
    events = list_events(event_date=event_date)
    # events are newest-first; the first row per child is their latest event.
    latest: dict[str, SignEvent] = {}
    for ev in events:
        if ev.pupil_id not in latest:
            latest[ev.pupil_id] = ev
    active = {pid for pid, _l in list_pupil_choices()}
    return [ev for pid, ev in latest.items()
            if ev.direction == "in" and pid in active]


# ── Writes ───────────────────────────────────────────────────────────────────

def create_event(data: dict[str, Any]) -> SignEvent:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    eid = generate_event_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO sign_in_out_log (
                    event_id, pupil_id, event_date, event_time, direction,
                    person_name, relationship, recorded_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (eid, payload["pupil_id"], payload["event_date"],
                 payload["event_time"], payload["direction"],
                 payload["person_name"], payload["relationship"],
                 payload["recorded_by"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for sign in / out id=%s", eid)
        raise ValidationError(f"Could not create event — {e}") from e
    ev = get_event(eid)
    assert ev is not None
    logger.info("Created sign-%s event %s for pupil %s",
                payload["direction"], eid, payload["pupil_id"])
    return ev


def delete_event(event_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM sign_in_out_log WHERE event_id = ?", (event_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting sign in / out id=%s", event_id)
        raise
    if deleted:
        logger.info("Deleted sign in / out event %s", event_id)
    return deleted


# ── Convenience ──────────────────────────────────────────────────────────────

def sign_in(data: dict[str, Any]) -> SignEvent:
    payload = dict(data)
    payload["direction"] = "in"
    return create_event(payload)


def sign_out(data: dict[str, Any]) -> SignEvent:
    payload = dict(data)
    payload["direction"] = "out"
    return create_event(payload)
