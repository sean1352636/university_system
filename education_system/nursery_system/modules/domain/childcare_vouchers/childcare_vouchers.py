"""Domain layer for Tax-Free Childcare / Vouchers (Nursery System).

Owns the ``childcare_vouchers`` table — the standing voucher / Tax-Free
Childcare arrangements registered against each child's account (scheme,
provider, account reference, expected monthly amount). Actual money received via
these schemes is logged in the Payments module with the matching method; this
module is the registry of arrangements.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``childcare_vouchers_cli.py``, Tk GUI in ``childcare_vouchers_views.py``.
"""

from __future__ import annotations

import logging
import random
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Tax-Free Childcare / Vouchers"
CATEGORY = "Finance"

ID_PREFIX = "NVCH"
ID_DIGITS = 3

SCHEMES = (
    "Tax-Free Childcare", "Childcare voucher (employer)",
    "Universal Credit childcare", "Other",
)
STATUSES = ("active", "inactive")


class ValidationError(ValueError):
    """Raised for invalid voucher-arrangement input."""


@dataclass
class Voucher:
    voucher_id: str
    pupil_id: str
    scheme: str | None
    provider: str | None
    account_ref: str | None
    expected_amount: float | None
    status: str
    notes: str | None
    child_name: str | None = None
    room: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for vouchers")
        raise


_SELECT = """
SELECT v.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room
FROM childcare_vouchers v
LEFT JOIN pupils p ON p.pupil_id = v.pupil_id
"""


def _row(r: sqlite3.Row) -> Voucher:
    keys = r.keys()
    return Voucher(
        voucher_id=r["voucher_id"],
        pupil_id=r["pupil_id"],
        scheme=r["scheme"],
        provider=r["provider"],
        account_ref=r["account_ref"],
        expected_amount=r["expected_amount"],
        status=r["status"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_money(value: Any, label: str) -> float | None:
    raw = str(value if value is not None else "").strip().replace("£", "").replace(",", "")
    if not raw:
        return None
    try:
        n = float(raw)
    except ValueError as e:
        raise ValidationError(f"{label} must be a number") from e
    if n < 0:
        raise ValidationError(f"{label} cannot be negative")
    return round(n, 2)


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid
    scheme = (data.get("scheme") or "").strip()
    if scheme and scheme not in SCHEMES:
        raise ValidationError("Scheme must be one of: " + ", ".join(SCHEMES))
    out["scheme"] = scheme or None
    out["provider"] = _opt(data.get("provider"))
    out["account_ref"] = _opt(data.get("account_ref"))
    out["expected_amount"] = _opt_money(data.get("expected_amount"),
                                        "Expected amount")
    out["notes"] = _opt(data.get("notes"))
    status = (data.get("status") or "active").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_voucher_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT voucher_id FROM childcare_vouchers").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing voucher ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        vid = f"{ID_PREFIX}{n}"
        if vid not in existing:
            return vid
    raise RuntimeError("Could not allocate a unique voucher id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_vouchers(*, pupil_id: str | None = None,
                  active_only: bool = False) -> list[Voucher]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if pupil_id:
        clauses.append("v.pupil_id = ?")
        params.append(pupil_id)
    if active_only:
        clauses.append("v.status = 'active'")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY child_name, v.voucher_id"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_vouchers failed")
        raise
    return [_row(r) for r in rows]


def get_voucher(voucher_id: str) -> Voucher | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE v.voucher_id = ?", (voucher_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_voucher(%s) failed", voucher_id)
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


def summary() -> dict[str, Any]:
    vouchers = list_vouchers()
    active = [v for v in vouchers if v.status == "active"]
    by_scheme: dict[str, int] = {}
    for v in active:
        by_scheme[v.scheme or "Unspecified"] = by_scheme.get(
            v.scheme or "Unspecified", 0) + 1
    expected = sum(v.expected_amount or 0.0 for v in active)
    return {"count": len(vouchers), "active": len(active),
            "expected_monthly": round(expected, 2), "by_scheme": by_scheme}


# ── Writes ───────────────────────────────────────────────────────────────────

def create_voucher(data: dict[str, Any]) -> Voucher:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    vid = generate_voucher_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO childcare_vouchers (
                    voucher_id, pupil_id, scheme, provider, account_ref,
                    expected_amount, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (vid, payload["pupil_id"], payload["scheme"], payload["provider"],
                 payload["account_ref"], payload["expected_amount"],
                 payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for voucher id=%s", vid)
        raise ValidationError(f"Could not create arrangement — {e}") from e
    voucher = get_voucher(vid)
    assert voucher is not None
    logger.info("Created voucher arrangement %s for pupil %s",
                vid, payload["pupil_id"])
    return voucher


def update_voucher(voucher_id: str, data: dict[str, Any]) -> Voucher:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE childcare_vouchers SET
                    scheme = ?, provider = ?, account_ref = ?,
                    expected_amount = ?, status = ?, notes = ?
                WHERE voucher_id = ?
                """,
                (payload["scheme"], payload["provider"], payload["account_ref"],
                 payload["expected_amount"], payload["status"], payload["notes"],
                 voucher_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No arrangement with id {voucher_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for voucher id=%s", voucher_id)
        raise ValidationError(f"Could not update arrangement — {e}") from e
    voucher = get_voucher(voucher_id)
    assert voucher is not None
    logger.info("Updated voucher arrangement %s", voucher_id)
    return voucher


def delete_voucher(voucher_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM childcare_vouchers WHERE voucher_id = ?",
                (voucher_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting voucher id=%s", voucher_id)
        raise
    if deleted:
        logger.info("Deleted voucher arrangement %s", voucher_id)
    return deleted
