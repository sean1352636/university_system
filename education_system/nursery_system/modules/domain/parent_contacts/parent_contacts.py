"""Domain layer for Parent Contacts (Nursery System).

Owns the ``parent_contacts`` table — the parents / carers attached to each
child. Tracks who holds parental responsibility, who is on the authorised
collection list and who is the primary day-to-day contact (the one the setting
calls first). The back-up people called only when a parent can't be reached are
held separately in :mod:`emergency_contacts`.

Follows the 4-layer pattern used across the other systems: validation +
SQLite access here, CLI in ``parent_contacts_cli.py``, Tk GUI in
``parent_contacts_views.py``.
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

FEATURE_NAME = "Parent Contacts"
CATEGORY = "Parents & Communication"

ID_PREFIX = "NPC"
ID_DIGITS = 3

RELATIONSHIPS = (
    "Mother", "Father", "Step-parent", "Grandparent", "Foster carer",
    "Guardian", "Other",
)

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(ValueError):
    """Raised for invalid parent-contact input."""


@dataclass
class ParentContact:
    contact_id: str
    pupil_id: str
    full_name: str
    relationship: str | None
    phone: str | None
    email: str | None
    address: str | None
    is_primary: bool
    parental_responsibility: bool
    can_collect: bool
    notes: str | None
    child_name: str | None = None
    room: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for parent contacts")
        raise


_SELECT = """
SELECT pc.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room
FROM parent_contacts pc
LEFT JOIN pupils p ON p.pupil_id = pc.pupil_id
"""


def _row(r: sqlite3.Row) -> ParentContact:
    keys = r.keys()
    return ParentContact(
        contact_id=r["contact_id"],
        pupil_id=r["pupil_id"],
        full_name=r["full_name"],
        relationship=r["relationship"],
        phone=r["phone"],
        email=r["email"],
        address=r["address"],
        is_primary=bool(r["is_primary"]),
        parental_responsibility=bool(r["parental_responsibility"]),
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

    phone = (data.get("phone") or "").strip()
    if phone and not _PHONE_RE.match(phone):
        raise ValidationError("Phone contains invalid characters")
    out["phone"] = phone or None

    email = (data.get("email") or "").strip()
    if email and not _EMAIL_RE.match(email):
        raise ValidationError("Email is not a valid address")
    out["email"] = email or None

    out["address"] = _opt(data.get("address"))
    out["is_primary"] = _as_bool(data.get("is_primary"))
    out["parental_responsibility"] = _as_bool(data.get("parental_responsibility"))
    out["can_collect"] = _as_bool(data.get("can_collect"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_contact_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT contact_id FROM parent_contacts").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing parent-contact ids")
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
    raise RuntimeError("Could not allocate a unique parent-contact id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_contacts(*, pupil_id: str | None = None) -> list[ParentContact]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE pc.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY pc.pupil_id, pc.is_primary DESC, pc.full_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_contacts failed")
        raise
    return [_row(r) for r in rows]


def get_contact(contact_id: str) -> ParentContact | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE pc.contact_id = ?", (contact_id,)).fetchone()
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

def create_contact(data: dict[str, Any]) -> ParentContact:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    cid = generate_contact_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            if payload["is_primary"]:
                conn.execute(
                    "UPDATE parent_contacts SET is_primary = 0 WHERE pupil_id = ?",
                    (payload["pupil_id"],))
            conn.execute(
                """
                INSERT INTO parent_contacts (
                    contact_id, pupil_id, full_name, relationship, phone, email,
                    address, is_primary, parental_responsibility, can_collect, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, payload["pupil_id"], payload["full_name"],
                 payload["relationship"], payload["phone"], payload["email"],
                 payload["address"], payload["is_primary"],
                 payload["parental_responsibility"], payload["can_collect"],
                 payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for parent-contact id=%s", cid)
        raise ValidationError(f"Could not create contact — {e}") from e
    c = get_contact(cid)
    assert c is not None
    logger.info("Created parent contact %s for pupil %s", cid, payload["pupil_id"])
    return c


def update_contact(contact_id: str, data: dict[str, Any]) -> ParentContact:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_contact(contact_id)
    if existing is None:
        raise ValidationError(f"No parent contact with id {contact_id}")
    try:
        with connect() as conn:
            if payload["is_primary"]:
                conn.execute(
                    "UPDATE parent_contacts SET is_primary = 0 "
                    "WHERE pupil_id = ? AND contact_id != ?",
                    (existing.pupil_id, contact_id))
            cur = conn.execute(
                """
                UPDATE parent_contacts SET
                    full_name = ?, relationship = ?, phone = ?, email = ?,
                    address = ?, is_primary = ?, parental_responsibility = ?,
                    can_collect = ?, notes = ?
                WHERE contact_id = ?
                """,
                (payload["full_name"], payload["relationship"], payload["phone"],
                 payload["email"], payload["address"], payload["is_primary"],
                 payload["parental_responsibility"], payload["can_collect"],
                 payload["notes"], contact_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No parent contact with id {contact_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for parent-contact id=%s", contact_id)
        raise ValidationError(f"Could not update contact — {e}") from e
    c = get_contact(contact_id)
    assert c is not None
    logger.info("Updated parent contact %s", contact_id)
    return c


def delete_contact(contact_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM parent_contacts WHERE contact_id = ?", (contact_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting parent-contact id=%s", contact_id)
        raise
    if deleted:
        logger.info("Deleted parent contact %s", contact_id)
    return deleted
