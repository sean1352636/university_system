"""Domain layer for Child Directory (Nursery System).

Owns the children-on-roll records, which live in the ``pupils`` table of the
shared nursery DB (``nursery_system/data/nursery.db`` — see
``core/database.py``). The cross-system superadmin dashboard counts the same
``pupils`` table, so this module reads and writes it directly rather than
creating its own.

Follows the 4-layer pattern used across the other systems: validation +
SQLite access here, CLI in ``children_cli.py``, Tk GUI in ``children_views.py``.

Every public function initialises the schema (idempotent), logs at the
appropriate level and raises :class:`ValidationError` for bad form input so
the interface layers can show a friendly message.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Child Directory"
CATEGORY = "Children & Admissions"

ID_PREFIX = "NCH"
ID_DIGITS = 3

# Early Years settings group children into age-banded rooms. These are the
# defaults offered in the UI; the field accepts free text so a setting can use
# its own room names.
ROOMS = ("Baby Room", "Toddler Room", "Preschool Room")

# Funded-hours entitlements a UK nursery handles (15/30 hours, 2-year-old
# funding) plus an unfunded/private option. Empty = not yet recorded.
FUNDED_HOURS_OPTIONS = (
    "",
    "15 hours",
    "30 hours",
    "2-year-old funding",
    "Private (unfunded)",
)

STATUSES = ("active", "left")

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DOB_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid child-form input."""


@dataclass
class Child:
    pupil_id: str
    first_name: str
    last_name: str
    date_of_birth: str | None
    room: str | None
    key_person: str | None
    funded_hours: str | None
    start_date: str | None
    parent_name: str | None
    parent_phone: str | None
    parent_email: str | None
    allergies: str | None
    medical_notes: str | None
    status: str
    # Resolved display name of the key person (joined from ``staff``); not a
    # stored column, populated only by reads that ask for it.
    key_person_name: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


def _ensure_schema() -> None:
    """Create (and demo-seed) the nursery tables if needed. Idempotent."""
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for child directory")
        raise


def _row(r: sqlite3.Row) -> Child:
    keys = r.keys()
    return Child(
        pupil_id=r["pupil_id"],
        first_name=r["first_name"],
        last_name=r["last_name"],
        date_of_birth=r["date_of_birth"],
        room=r["room"],
        key_person=r["key_person"],
        funded_hours=r["funded_hours"],
        start_date=r["start_date"],
        parent_name=r["parent_name"],
        parent_phone=r["parent_phone"],
        parent_email=r["parent_email"],
        allergies=r["allergies"],
        medical_notes=r["medical_notes"],
        status=r["status"],
        key_person_name=r["key_person_name"] if "key_person_name" in keys else None,
    )


# Read query that joins the key person's name for display. Kept in one place so
# list/get/search all present the same shape.
_SELECT = """
SELECT p.*,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS key_person_name
FROM pupils p
LEFT JOIN staff s ON s.staff_id = p.key_person
"""


# ── Validation ───────────────────────────────────────────────────────────────

def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["first_name"] = _require(data.get("first_name"), "First name")
    out["last_name"] = _require(data.get("last_name"), "Last name")

    dob = (data.get("date_of_birth") or "").strip()
    if dob and not _DOB_RE.match(dob):
        raise ValidationError("Date of birth must be YYYY-MM-DD")
    out["date_of_birth"] = dob or None

    out["room"] = _opt(data.get("room"))
    out["key_person"] = _opt(data.get("key_person"))

    funded = (data.get("funded_hours") or "").strip()
    if funded and funded not in FUNDED_HOURS_OPTIONS:
        raise ValidationError(
            "Funded hours must be one of: "
            + ", ".join(o for o in FUNDED_HOURS_OPTIONS if o)
        )
    out["funded_hours"] = funded or None

    start = (data.get("start_date") or "").strip()
    if start and not _DOB_RE.match(start):
        raise ValidationError("Start date must be YYYY-MM-DD")
    out["start_date"] = start or None

    out["parent_name"] = _opt(data.get("parent_name"))

    pphone = (data.get("parent_phone") or "").strip()
    if pphone and not _PHONE_RE.match(pphone):
        raise ValidationError("Parent phone contains invalid characters")
    out["parent_phone"] = pphone or None

    pemail = (data.get("parent_email") or "").strip()
    if pemail and not _EMAIL_RE.match(pemail):
        raise ValidationError("Parent email is not a valid address")
    out["parent_email"] = pemail or None

    out["allergies"] = _opt(data.get("allergies"))
    out["medical_notes"] = _opt(data.get("medical_notes"))

    status = (data.get("status") or "active").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_child_id() -> str:
    """Allocate a unique ``NCH###`` id, widening past the demo range if full."""
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {
                r[0] for r in conn.execute("SELECT pupil_id FROM pupils").fetchall()
            }
    except sqlite3.Error:
        logger.exception("Could not read existing child ids")
        raise

    # Prefer the next sequential id (NCH001, NCH002, …) for tidy demo data.
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"

    # Sequential range exhausted — fall back to random allocation.
    for attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        cid = f"{ID_PREFIX}{n}"
        if cid not in existing:
            logger.info("Allocated child id %s after sequential range full", cid)
            return cid
    logger.error("Exhausted attempts allocating a unique child id")
    raise RuntimeError("Could not allocate a unique child id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_children(*, include_left: bool = False) -> list[Child]:
    _ensure_schema()
    sql = _SELECT
    params: tuple[Any, ...] = ()
    if not include_left:
        sql += " WHERE p.status = ?"
        params = ("active",)
    sql += " ORDER BY p.room, p.last_name, p.first_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_children failed")
        raise
    logger.debug("list_children(include_left=%s) -> %d row(s)",
                 include_left, len(rows))
    return [_row(r) for r in rows]


def get_child(pupil_id: str) -> Child | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE p.pupil_id = ?", (pupil_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_child(%s) failed", pupil_id)
        raise
    if row is None:
        logger.debug("get_child(%s) -> miss", pupil_id)
        return None
    return _row(row)


def search_children(query: str, *, include_left: bool = True) -> list[Child]:
    _ensure_schema()
    raw = (query or "").strip()
    like = f"%{raw}%"
    sql = _SELECT + """
        WHERE (p.pupil_id LIKE ?
            OR p.first_name LIKE ?
            OR p.last_name LIKE ?
            OR p.room LIKE ?
            OR p.parent_name LIKE ?
            OR p.parent_email LIKE ?)
    """
    params: list[Any] = [like, like, like, like, like, like]
    if not include_left:
        sql += " AND p.status = ?"
        params.append("active")
    sql += " ORDER BY p.room, p.last_name, p.first_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("search_children(query_len=%d) failed", len(raw))
        raise
    logger.debug("search_children(query_len=%d) -> %d match(es)", len(raw), len(rows))
    return [_row(r) for r in rows]


def list_key_person_choices() -> list[tuple[str, str]]:
    """Return ``(staff_id, "Name (id)")`` pairs for key-person pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name FROM staff "
                "ORDER BY last_name, first_name"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_key_person_choices failed")
        raise
    return [
        (r["staff_id"],
         f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
        for r in rows
    ]


# ── Writes ───────────────────────────────────────────────────────────────────

def create_child(data: dict[str, Any]) -> Child:
    _ensure_schema()
    logger.debug("create_child called with fields: %s",
                 sorted(k for k, v in data.items() if v not in (None, "")))
    try:
        payload = _validate(data)
    except ValidationError as e:
        logger.warning("create_child validation failed: %s", e)
        raise
    cid = generate_child_id()
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO pupils (
                    pupil_id, first_name, last_name, date_of_birth, room,
                    key_person, funded_hours, start_date, parent_name,
                    parent_phone, parent_email, allergies, medical_notes, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, payload["first_name"], payload["last_name"],
                 payload["date_of_birth"], payload["room"],
                 payload["key_person"], payload["funded_hours"],
                 payload["start_date"], payload["parent_name"],
                 payload["parent_phone"], payload["parent_email"],
                 payload["allergies"], payload["medical_notes"],
                 payload["status"]),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("INSERT failed for new child id=%s", cid)
        raise ValidationError(f"Could not create child — {e}") from e
    except sqlite3.Error:
        logger.exception("Database error creating child id=%s", cid)
        raise
    child = get_child(cid)
    assert child is not None
    logger.info("Created child %s (%s, room %s)",
                child.pupil_id, child.full_name, child.room or "-")
    # Register into the canonical cross-system identity registry so the
    # child has a stable journey_id from day one (best-effort).
    try:
        from education_system.platform.cross_system import person, progression
        jid = progression.register_local_student(
            "nursery", student_id=child.pupil_id,
            first_name=child.first_name, last_name=child.last_name,
            date_of_birth=child.date_of_birth)
        if jid:
            person.link_local_record("nursery", child.pupil_id, jid)
    except Exception:
        logger.debug("Journey registration skipped for child %s",
                     child.pupil_id, exc_info=True)
    return child


def update_child(pupil_id: str, data: dict[str, Any]) -> Child:
    _ensure_schema()
    logger.debug("update_child(%s) called with fields: %s", pupil_id,
                 sorted(k for k, v in data.items() if v not in (None, "")))
    try:
        payload = _validate(data)
    except ValidationError as e:
        logger.warning("update_child(%s) validation failed: %s", pupil_id, e)
        raise
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE pupils SET
                    first_name = ?, last_name = ?, date_of_birth = ?, room = ?,
                    key_person = ?, funded_hours = ?, start_date = ?,
                    parent_name = ?, parent_phone = ?, parent_email = ?,
                    allergies = ?, medical_notes = ?, status = ?
                WHERE pupil_id = ?
                """,
                (payload["first_name"], payload["last_name"],
                 payload["date_of_birth"], payload["room"],
                 payload["key_person"], payload["funded_hours"],
                 payload["start_date"], payload["parent_name"],
                 payload["parent_phone"], payload["parent_email"],
                 payload["allergies"], payload["medical_notes"],
                 payload["status"], pupil_id),
            )
            if cur.rowcount == 0:
                logger.warning("update_child called for unknown id %s", pupil_id)
                raise ValidationError(f"No child with id {pupil_id}")
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("UPDATE failed for child id=%s", pupil_id)
        raise ValidationError(f"Could not update child — {e}") from e
    except sqlite3.Error:
        logger.exception("Database error updating child id=%s", pupil_id)
        raise
    child = get_child(pupil_id)
    assert child is not None
    logger.info("Updated child %s (%s)", pupil_id, child.full_name)
    return child


def delete_child(pupil_id: str) -> bool:
    _ensure_schema()
    snapshot = get_child(pupil_id)
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM pupils WHERE pupil_id = ?", (pupil_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting child id=%s", pupil_id)
        raise
    if deleted:
        who = snapshot.full_name if snapshot else "(no snapshot — race?)"
        logger.info("Deleted child %s (%s)", pupil_id, who)
    else:
        logger.warning("delete_child called for unknown id %s", pupil_id)
    return deleted


def set_status(pupil_id: str, status: str) -> Child:
    """Mark a child active/left without re-validating the whole record."""
    _ensure_schema()
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE pupils SET status = ? WHERE pupil_id = ?",
                (status, pupil_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No child with id {pupil_id}")
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error setting status for child id=%s", pupil_id)
        raise
    child = get_child(pupil_id)
    assert child is not None
    logger.info("Set child %s status -> %s", pupil_id, status)
    return child
