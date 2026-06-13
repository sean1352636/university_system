"""Domain layer for Paediatric First Aid (Nursery System).

Owns the ``paediatric_first_aid`` table — PFA certificates held by staff. The
EYFS requires at least one PFA-trained person on site at all times (and on
outings); a full PFA certificate is valid for three years. Validity (valid /
expiring soon / expired) is derived from ``expiry_date``.

Saving or removing a certificate re-syncs ``staff.is_paediatric_first_aider``
so the Staff Directory flag reflects whether the person currently holds a valid
(non-expired) certificate.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``first_aid_cli.py``, Tk GUI in ``first_aid_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Paediatric First Aid"
CATEGORY = "Staff & Ratios"

ID_PREFIX = "NPF"
ID_DIGITS = 3

CERTIFICATE_TYPES = (
    "Full PFA (12 hour)", "Emergency PFA (1 day)", "PFA refresher", "Other",
)
# A full PFA certificate lasts three years; flag within this window of expiry.
EXPIRING_WINDOW_DAYS = 90

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid PFA-certificate input."""


@dataclass
class PFACertificate:
    record_id: str
    staff_id: str
    certificate_type: str | None
    awarding_body: str | None
    issue_date: str | None
    expiry_date: str | None
    certificate_ref: str | None
    notes: str | None
    staff_name: str | None = None
    staff_role: str | None = None

    @property
    def validity(self) -> str:
        """Derived state: expired / expiring / valid (or unknown if no date)."""
        if not self.expiry_date:
            return "unknown"
        try:
            exp = _dt.date.fromisoformat(self.expiry_date)
        except ValueError:
            return "unknown"
        today = _dt.date.today()
        if exp < today:
            return "expired"
        if (exp - today).days <= EXPIRING_WINDOW_DAYS:
            return "expiring"
        return "valid"

    @property
    def is_current(self) -> bool:
        return self.validity in ("valid", "expiring", "unknown")


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for PFA")
        raise


_SELECT = """
SELECT f.*,
       TRIM(s.first_name || ' ' || s.last_name) AS staff_name,
       s.role AS staff_role
FROM paediatric_first_aid f
LEFT JOIN staff s ON s.staff_id = f.staff_id
"""


def _row(r: sqlite3.Row) -> PFACertificate:
    keys = r.keys()
    return PFACertificate(
        record_id=r["record_id"],
        staff_id=r["staff_id"],
        certificate_type=r["certificate_type"],
        awarding_body=r["awarding_body"],
        issue_date=r["issue_date"],
        expiry_date=r["expiry_date"],
        certificate_ref=r["certificate_ref"],
        notes=r["notes"],
        staff_name=r["staff_name"] if "staff_name" in keys else None,
        staff_role=r["staff_role"] if "staff_role" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _validate(data: dict[str, Any], *, require_staff: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_staff:
        out["staff_id"] = _require(data.get("staff_id"), "Staff member")
    ctype = (data.get("certificate_type") or "").strip()
    if ctype and ctype not in CERTIFICATE_TYPES:
        raise ValidationError(
            "Certificate type must be one of: " + ", ".join(CERTIFICATE_TYPES))
    out["certificate_type"] = ctype or None
    out["awarding_body"] = _opt(data.get("awarding_body"))
    out["issue_date"] = _opt_date(data.get("issue_date"), "Issue date")
    out["expiry_date"] = _opt_date(data.get("expiry_date"), "Expiry date")
    out["certificate_ref"] = _opt(data.get("certificate_ref"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT record_id FROM paediatric_first_aid").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing PFA ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        rid = f"{ID_PREFIX}{n}"
        if rid not in existing:
            return rid
    raise RuntimeError("Could not allocate a unique PFA id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_certificates(*, staff_id: str | None = None) -> list[PFACertificate]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if staff_id:
        sql += " WHERE f.staff_id = ?"
        params.append(staff_id)
    sql += " ORDER BY f.expiry_date, staff_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_certificates failed")
        raise
    return [_row(r) for r in rows]


def get_certificate(record_id: str) -> PFACertificate | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE f.record_id = ?", (record_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_certificate(%s) failed", record_id)
        raise
    return _row(row) if row else None


def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name, role FROM staff "
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


def summary() -> dict[str, int]:
    """Counts + how many staff currently hold a valid (non-expired) cert."""
    certs = list_certificates()
    valid = sum(1 for c in certs if c.validity == "valid")
    expiring = sum(1 for c in certs if c.validity == "expiring")
    expired = sum(1 for c in certs if c.validity == "expired")
    current_staff = {c.staff_id for c in certs if c.is_current}
    return {"total": len(certs), "valid": valid, "expiring": expiring,
            "expired": expired, "staff_covered": len(current_staff)}


# ── Writes ───────────────────────────────────────────────────────────────────

def _sync_staff_flag(conn: sqlite3.Connection, staff_id: str) -> None:
    """Set ``staff.is_paediatric_first_aider`` from the staff's live certs."""
    rows = conn.execute(
        "SELECT expiry_date FROM paediatric_first_aid WHERE staff_id = ?",
        (staff_id,)).fetchall()
    today = _dt.date.today()
    current = False
    for r in rows:
        exp = r["expiry_date"]
        if not exp:
            current = True
            break
        try:
            if _dt.date.fromisoformat(exp) >= today:
                current = True
                break
        except ValueError:
            continue
    conn.execute("UPDATE staff SET is_paediatric_first_aider = ? WHERE staff_id = ?",
                 (int(current), staff_id))


def create_certificate(data: dict[str, Any]) -> PFACertificate:
    _ensure_schema()
    payload = _validate(data, require_staff=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM staff WHERE staff_id = ?",
                                (payload["staff_id"],)).fetchone():
                raise ValidationError(
                    f"No staff member with id {payload['staff_id']}")
            conn.execute(
                """
                INSERT INTO paediatric_first_aid (
                    record_id, staff_id, certificate_type, awarding_body,
                    issue_date, expiry_date, certificate_ref, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["staff_id"], payload["certificate_type"],
                 payload["awarding_body"], payload["issue_date"],
                 payload["expiry_date"], payload["certificate_ref"],
                 payload["notes"]),
            )
            _sync_staff_flag(conn, payload["staff_id"])
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for PFA id=%s", rid)
        raise ValidationError(f"Could not create certificate — {e}") from e
    cert = get_certificate(rid)
    assert cert is not None
    logger.info("Created PFA certificate %s for staff %s", rid, payload["staff_id"])
    return cert


def update_certificate(record_id: str, data: dict[str, Any]) -> PFACertificate:
    _ensure_schema()
    payload = _validate(data, require_staff=False)
    existing = get_certificate(record_id)
    if existing is None:
        raise ValidationError(f"No PFA certificate with id {record_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE paediatric_first_aid SET
                    certificate_type = ?, awarding_body = ?, issue_date = ?,
                    expiry_date = ?, certificate_ref = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["certificate_type"], payload["awarding_body"],
                 payload["issue_date"], payload["expiry_date"],
                 payload["certificate_ref"], payload["notes"], record_id),
            )
            _sync_staff_flag(conn, existing.staff_id)
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for PFA id=%s", record_id)
        raise ValidationError(f"Could not update certificate — {e}") from e
    cert = get_certificate(record_id)
    assert cert is not None
    logger.info("Updated PFA certificate %s", record_id)
    return cert


def delete_certificate(record_id: str) -> bool:
    _ensure_schema()
    existing = get_certificate(record_id)
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM paediatric_first_aid WHERE record_id = ?",
                (record_id,))
            if existing is not None:
                _sync_staff_flag(conn, existing.staff_id)
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting PFA id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted PFA certificate %s", record_id)
    return deleted
