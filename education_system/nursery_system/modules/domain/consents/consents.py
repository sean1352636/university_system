"""Domain layer for Permissions & Consents (Nursery System).

Owns the ``consents`` table — the parental-consent register tracking which
permissions have been granted or refused for each child (photographs, outings,
sun cream, emergency treatment, etc.).

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``consents_cli.py``, Tk GUI in ``consents_views.py``.
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

FEATURE_NAME = "Permissions & Consents"
CATEGORY = "Parents & Communication"

ID_PREFIX = "NCO"
ID_DIGITS = 3

CONSENT_TYPES = (
    "Photographs",
    "Local outings",
    "Sun cream application",
    "Emergency medical treatment",
    "Nappy changing",
    "Face painting",
    "Social media",
    "Sharing with other professionals",
    "Off-site trips",
    "Use of plasters",
)

STATUSES = ("granted", "refused", "pending")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid consent input."""


@dataclass
class Consent:
    consent_id: str
    pupil_id: str
    consent_type: str
    status: str
    date_recorded: str | None
    expiry_date: str | None
    recorded_by: str | None
    notes: str | None
    created_at: str | None = None
    child_name: str | None = None
    room: str | None = None
    recorded_by_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for consents")
        raise


_SELECT = """
SELECT c.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS recorded_by_name
FROM consents c
LEFT JOIN pupils p ON p.pupil_id = c.pupil_id
LEFT JOIN staff s ON s.staff_id = c.recorded_by
"""


def _row(r: sqlite3.Row) -> Consent:
    keys = r.keys()
    return Consent(
        consent_id=r["consent_id"],
        pupil_id=r["pupil_id"],
        consent_type=r["consent_type"],
        status=r["status"],
        date_recorded=r["date_recorded"],
        expiry_date=r["expiry_date"],
        recorded_by=r["recorded_by"],
        notes=r["notes"],
        created_at=r["created_at"] if "created_at" in keys else None,
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        recorded_by_name=(r["recorded_by_name"] or None)
        if "recorded_by_name" in keys else None,
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


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    ctype = (data.get("consent_type") or "").strip()
    if not ctype:
        raise ValidationError("Consent type is required")
    if ctype not in CONSENT_TYPES:
        raise ValidationError(
            "Consent type must be one of: " + ", ".join(CONSENT_TYPES))
    out["consent_type"] = ctype

    status = (data.get("status") or "granted").strip()
    if status not in STATUSES:
        raise ValidationError(
            "Status must be one of: " + ", ".join(STATUSES))
    out["status"] = status

    out["date_recorded"] = _opt_date(data.get("date_recorded"), "Date recorded")
    out["expiry_date"] = _opt_date(data.get("expiry_date"), "Expiry date")
    out["recorded_by"] = _opt(data.get("recorded_by"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_consent_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT consent_id FROM consents").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing consent ids")
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
    raise RuntimeError("Could not allocate a unique consent id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_consents(*, pupil_id: str | None = None) -> list[Consent]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE c.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY c.pupil_id, c.consent_type"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_consents failed")
        raise
    return [_row(r) for r in rows]


def get_consent(consent_id: str) -> Consent | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE c.consent_id = ?", (consent_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_consent(%s) failed", consent_id)
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

def create_consent(data: dict[str, Any]) -> Consent:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    cid = generate_consent_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO consents (
                    consent_id, pupil_id, consent_type, status,
                    date_recorded, expiry_date, recorded_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, payload["pupil_id"], payload["consent_type"],
                 payload["status"], payload["date_recorded"],
                 payload["expiry_date"], payload["recorded_by"],
                 payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for consent id=%s", cid)
        raise ValidationError(f"Could not create consent — {e}") from e
    c = get_consent(cid)
    assert c is not None
    logger.info("Created consent %s for pupil %s", cid, payload["pupil_id"])
    return c


def update_consent(consent_id: str, data: dict[str, Any]) -> Consent:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE consents SET
                    consent_type = ?, status = ?, date_recorded = ?,
                    expiry_date = ?, recorded_by = ?, notes = ?
                WHERE consent_id = ?
                """,
                (payload["consent_type"], payload["status"],
                 payload["date_recorded"], payload["expiry_date"],
                 payload["recorded_by"], payload["notes"], consent_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No consent with id {consent_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for consent id=%s", consent_id)
        raise ValidationError(f"Could not update consent — {e}") from e
    c = get_consent(consent_id)
    assert c is not None
    logger.info("Updated consent %s", consent_id)
    return c


def delete_consent(consent_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM consents WHERE consent_id = ?", (consent_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting consent id=%s", consent_id)
        raise
    if deleted:
        logger.info("Deleted consent %s", consent_id)
    return deleted
