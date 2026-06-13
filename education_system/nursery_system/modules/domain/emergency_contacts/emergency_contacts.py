"""Domain layer for Emergency Contacts (Nursery System).

Owns the ``emergency_contacts`` table — the back-up people called when a
parent can't be reached. Each row records who to call, their relationship to
the child, contact numbers, call priority and whether they are authorised to
collect the child.

Follows the 4-layer pattern used across the other systems: validation +
SQLite access here, CLI in ``emergency_contacts_cli.py``, Tk GUI in
``emergency_contacts_views.py``.
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

FEATURE_NAME = "Emergency Contacts"
CATEGORY = "Parents & Communication"

ID_PREFIX = "NEC"
ID_DIGITS = 3

RELATIONSHIPS = (
    "Grandparent", "Aunt/Uncle", "Sibling", "Family friend",
    "Neighbour", "Childminder", "Other",
)

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")


class ValidationError(ValueError):
    """Raised for invalid emergency-contact input."""


@dataclass
class EmergencyContact:
    contact_id: str
    pupil_id: str
    full_name: str
    relationship: str | None
    phone_primary: str | None
    phone_alt: str | None
    priority: int
    can_collect: bool
    notes: str | None
    child_name: str | None = None
    room: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for emergency contacts")
        raise


_SELECT = """
SELECT ec.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room
FROM emergency_contacts ec
LEFT JOIN pupils p ON p.pupil_id = ec.pupil_id
"""


def _row(r: sqlite3.Row) -> EmergencyContact:
    keys = r.keys()
    return EmergencyContact(
        contact_id=r["contact_id"],
        pupil_id=r["pupil_id"],
        full_name=r["full_name"],
        relationship=r["relationship"],
        phone_primary=r["phone_primary"],
        phone_alt=r["phone_alt"],
        priority=r["priority"],
        can_collect=bool(r["can_collect"]),
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _as_bool(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "y", "yes", "true", "on") else 0
    return 1 if value else 0


def _opt_int_priority(value: Any) -> int:
    """Parse priority: blank defaults to 1; must be a positive integer."""
    raw = str(value if value is not None else "").strip()
    if not raw:
        return 1
    try:
        n = int(raw)
    except ValueError as e:
        raise ValidationError("Priority must be a whole number") from e
    if n < 1:
        raise ValidationError("Priority must be at least 1")
    return n


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    name = (data.get("full_name") or "").strip()
    if not name:
        raise ValidationError("Contact name is required")
    out["full_name"] = name

    rel = (data.get("relationship") or "").strip()
    if rel and rel not in RELATIONSHIPS:
        raise ValidationError(
            "Relationship must be one of: " + ", ".join(RELATIONSHIPS))
    out["relationship"] = rel or None

    phone_primary = (data.get("phone_primary") or "").strip()
    if phone_primary and not _PHONE_RE.match(phone_primary):
        raise ValidationError("Primary phone contains invalid characters")
    out["phone_primary"] = phone_primary or None

    phone_alt = (data.get("phone_alt") or "").strip()
    if phone_alt and not _PHONE_RE.match(phone_alt):
        raise ValidationError("Alternative phone contains invalid characters")
    out["phone_alt"] = phone_alt or None

    out["priority"] = _opt_int_priority(data.get("priority"))
    out["can_collect"] = _as_bool(data.get("can_collect"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_contact_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT contact_id FROM emergency_contacts").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing emergency-contact ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        cid = f"{ID_PREFIX}{n}"
        if cid not in existing:
            return cid
    raise RuntimeError("Could not allocate a unique emergency-contact id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_contacts(*, pupil_id: str | None = None) -> list[EmergencyContact]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE ec.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY ec.pupil_id, ec.priority, ec.full_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_contacts failed")
        raise
    return [_row(r) for r in rows]


def get_contact(contact_id: str) -> EmergencyContact | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE ec.contact_id = ?", (contact_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_contact(%s) failed", contact_id)
        raise
    return _row(row) if row else None


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


# ── Writes ───────────────────────────────────────────────────────────────────

def create_contact(data: dict[str, Any]) -> EmergencyContact:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    cid = generate_contact_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO emergency_contacts (
                    contact_id, pupil_id, full_name, relationship,
                    phone_primary, phone_alt, priority, can_collect, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, payload["pupil_id"], payload["full_name"],
                 payload["relationship"], payload["phone_primary"],
                 payload["phone_alt"], payload["priority"],
                 payload["can_collect"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for emergency-contact id=%s", cid)
        raise ValidationError(f"Could not create contact — {e}") from e
    c = get_contact(cid)
    assert c is not None
    logger.info("Created emergency contact %s for pupil %s", cid, payload["pupil_id"])
    return c


def update_contact(contact_id: str, data: dict[str, Any]) -> EmergencyContact:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_contact(contact_id)
    if existing is None:
        raise ValidationError(f"No emergency contact with id {contact_id}")
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE emergency_contacts SET
                    full_name = ?, relationship = ?, phone_primary = ?,
                    phone_alt = ?, priority = ?, can_collect = ?, notes = ?
                WHERE contact_id = ?
                """,
                (payload["full_name"], payload["relationship"],
                 payload["phone_primary"], payload["phone_alt"],
                 payload["priority"], payload["can_collect"],
                 payload["notes"], contact_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No emergency contact with id {contact_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for emergency-contact id=%s", contact_id)
        raise ValidationError(f"Could not update contact — {e}") from e
    c = get_contact(contact_id)
    assert c is not None
    logger.info("Updated emergency contact %s", contact_id)
    return c


def delete_contact(contact_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM emergency_contacts WHERE contact_id = ?", (contact_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting emergency-contact id=%s", contact_id)
        raise
    if deleted:
        logger.info("Deleted emergency contact %s", contact_id)
    return deleted
