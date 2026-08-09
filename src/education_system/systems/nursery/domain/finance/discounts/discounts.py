"""Domain layer for Sibling Discounts (Nursery System).

Owns the ``fee_discounts`` table — discount arrangements applied to a child's
fees (sibling, staff, bursary…). A discount is either a percentage *or* a fixed
monthly amount, with an optional active window. The Invoices module records the
applied discount on each invoice; this module is the registry of standing
arrangements.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``discounts_cli.py``, Tk GUI in ``discounts_views.py``.
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

FEATURE_NAME = "Sibling Discounts"
CATEGORY = "Finance"

ID_PREFIX = "NDIS"
ID_DIGITS = 3

DISCOUNT_TYPES = ("Sibling", "Staff", "Bursary", "Funded top-up", "Other")
STATUSES = ("active", "ended")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid discount input."""


@dataclass
class Discount:
    discount_id: str
    pupil_id: str
    discount_type: str | None
    percentage: float | None
    fixed_amount: float | None
    reason: str | None
    start_date: str | None
    end_date: str | None
    status: str
    notes: str | None
    child_name: str | None = None
    room: str | None = None

    @property
    def value_label(self) -> str:
        if self.percentage:
            return f"{self.percentage:g}%"
        if self.fixed_amount:
            return f"£{self.fixed_amount:.2f}"
        return "-"


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for discounts")
        raise


_SELECT = """
SELECT d.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room
FROM fee_discounts d
LEFT JOIN pupils p ON p.pupil_id = d.pupil_id
"""


def _row(r: sqlite3.Row) -> Discount:
    keys = r.keys()
    return Discount(
        discount_id=r["discount_id"],
        pupil_id=r["pupil_id"],
        discount_type=r["discount_type"],
        percentage=r["percentage"],
        fixed_amount=r["fixed_amount"],
        reason=r["reason"],
        start_date=r["start_date"],
        end_date=r["end_date"],
        status=r["status"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
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


def _opt_num(value: Any, label: str, *, max_value: float | None = None) -> float | None:
    raw = str(value if value is not None else "").strip().replace("£", "").replace("%", "").replace(",", "")
    if not raw:
        return None
    try:
        n = float(raw)
    except ValueError as e:
        raise ValidationError(f"{label} must be a number") from e
    if n < 0:
        raise ValidationError(f"{label} cannot be negative")
    if max_value is not None and n > max_value:
        raise ValidationError(f"{label} cannot exceed {max_value:g}")
    return round(n, 2)


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    dtype = (data.get("discount_type") or "").strip()
    if dtype and dtype not in DISCOUNT_TYPES:
        raise ValidationError("Type must be one of: " + ", ".join(DISCOUNT_TYPES))
    out["discount_type"] = dtype or None

    out["percentage"] = _opt_num(data.get("percentage"), "Percentage", max_value=100)
    out["fixed_amount"] = _opt_num(data.get("fixed_amount"), "Fixed amount")
    if out["percentage"] is None and out["fixed_amount"] is None:
        raise ValidationError("Enter either a percentage or a fixed amount")
    if out["percentage"] is not None and out["fixed_amount"] is not None:
        raise ValidationError("Enter a percentage OR a fixed amount, not both")

    out["reason"] = _opt(data.get("reason"))
    out["start_date"] = _opt_date(data.get("start_date"), "Start date")
    out["end_date"] = _opt_date(data.get("end_date"), "End date")
    out["notes"] = _opt(data.get("notes"))

    status = (data.get("status") or "active").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_discount_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT discount_id FROM fee_discounts").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing discount ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        did = f"{ID_PREFIX}{n}"
        if did not in existing:
            return did
    raise RuntimeError("Could not allocate a unique discount id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_discounts(*, pupil_id: str | None = None,
                   active_only: bool = False) -> list[Discount]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if pupil_id:
        clauses.append("d.pupil_id = ?")
        params.append(pupil_id)
    if active_only:
        clauses.append("d.status = 'active'")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY child_name, d.discount_id"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_discounts failed")
        raise
    return [_row(r) for r in rows]


def get_discount(discount_id: str) -> Discount | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE d.discount_id = ?", (discount_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_discount(%s) failed", discount_id)
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
    discounts = list_discounts()
    active = [d for d in discounts if d.status == "active"]
    by_type: dict[str, int] = {}
    for d in active:
        by_type[d.discount_type or "Other"] = by_type.get(
            d.discount_type or "Other", 0) + 1
    return {"count": len(discounts), "active": len(active), "by_type": by_type}


# ── Writes ───────────────────────────────────────────────────────────────────

def create_discount(data: dict[str, Any]) -> Discount:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    did = generate_discount_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO fee_discounts (
                    discount_id, pupil_id, discount_type, percentage,
                    fixed_amount, reason, start_date, end_date, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (did, payload["pupil_id"], payload["discount_type"],
                 payload["percentage"], payload["fixed_amount"],
                 payload["reason"], payload["start_date"], payload["end_date"],
                 payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for discount id=%s", did)
        raise ValidationError(f"Could not create discount — {e}") from e
    discount = get_discount(did)
    assert discount is not None
    logger.info("Created discount %s for pupil %s", did, payload["pupil_id"])
    return discount


def update_discount(discount_id: str, data: dict[str, Any]) -> Discount:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE fee_discounts SET
                    discount_type = ?, percentage = ?, fixed_amount = ?,
                    reason = ?, start_date = ?, end_date = ?, status = ?, notes = ?
                WHERE discount_id = ?
                """,
                (payload["discount_type"], payload["percentage"],
                 payload["fixed_amount"], payload["reason"],
                 payload["start_date"], payload["end_date"], payload["status"],
                 payload["notes"], discount_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No discount with id {discount_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for discount id=%s", discount_id)
        raise ValidationError(f"Could not update discount — {e}") from e
    discount = get_discount(discount_id)
    assert discount is not None
    logger.info("Updated discount %s", discount_id)
    return discount


def delete_discount(discount_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM fee_discounts WHERE discount_id = ?", (discount_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting discount id=%s", discount_id)
        raise
    if deleted:
        logger.info("Deleted discount %s", discount_id)
    return deleted
