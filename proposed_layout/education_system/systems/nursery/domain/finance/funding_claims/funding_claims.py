"""Domain layer for Funded Hours Claims (Nursery System).

Owns the ``funding_claims`` table — claims to the local authority for funded
entitlement hours (15/30-hour, 2-year-old). The ``claim_amount`` is computed as
``funded_hours/week × weeks × hourly_rate``. Each claim moves through
draft → submitted → paid. This complements the (child-facing) Funded Hours
module, which tracks each child's entitlement; this module is the money claim.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``funding_claims_cli.py``, Tk GUI in ``funding_claims_views.py``.
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

FEATURE_NAME = "Funded Hours Claims"
CATEGORY = "Finance"

ID_PREFIX = "NFC"
ID_DIGITS = 3

ENTITLEMENTS = ("15 hours", "30 hours", "2-year-old funding")
STATUSES = ("draft", "submitted", "paid")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid funding-claim input."""


@dataclass
class FundingClaim:
    claim_id: str
    pupil_id: str | None
    funding_period: str | None
    entitlement: str | None
    funded_hours: float | None
    weeks: float | None
    hourly_rate: float | None
    claim_amount: float
    headcount_date: str | None
    status: str
    submitted_date: str | None
    notes: str | None
    child_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for funding claims")
        raise


_SELECT = """
SELECT c.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name
FROM funding_claims c
LEFT JOIN pupils p ON p.pupil_id = c.pupil_id
"""


def _row(r: sqlite3.Row) -> FundingClaim:
    keys = r.keys()
    return FundingClaim(
        claim_id=r["claim_id"],
        pupil_id=r["pupil_id"],
        funding_period=r["funding_period"],
        entitlement=r["entitlement"],
        funded_hours=r["funded_hours"],
        weeks=r["weeks"],
        hourly_rate=r["hourly_rate"],
        claim_amount=r["claim_amount"],
        headcount_date=r["headcount_date"],
        status=r["status"],
        submitted_date=r["submitted_date"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
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


def _opt_num(value: Any, label: str) -> float | None:
    raw = str(value if value is not None else "").strip().replace("£", "").replace(",", "")
    if not raw:
        return None
    try:
        n = float(raw)
    except ValueError as e:
        raise ValidationError(f"{label} must be a number") from e
    if n < 0:
        raise ValidationError(f"{label} cannot be negative")
    return n


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["pupil_id"] = _opt(data.get("pupil_id"))

    entitlement = (data.get("entitlement") or "").strip()
    if entitlement and entitlement not in ENTITLEMENTS:
        raise ValidationError("Entitlement must be one of: " + ", ".join(ENTITLEMENTS))
    out["entitlement"] = entitlement or None

    out["funding_period"] = _opt(data.get("funding_period"))
    out["funded_hours"] = _opt_num(data.get("funded_hours"), "Funded hours/week")
    out["weeks"] = _opt_num(data.get("weeks"), "Weeks")
    out["hourly_rate"] = _opt_num(data.get("hourly_rate"), "Hourly rate")
    out["claim_amount"] = round(
        (out["funded_hours"] or 0.0) * (out["weeks"] or 0.0)
        * (out["hourly_rate"] or 0.0), 2)
    out["headcount_date"] = _opt_date(data.get("headcount_date"), "Headcount date")
    out["submitted_date"] = _opt_date(data.get("submitted_date"), "Submitted date")
    out["notes"] = _opt(data.get("notes"))

    status = (data.get("status") or "draft").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_claim_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT claim_id FROM funding_claims").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing claim ids")
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
    raise RuntimeError("Could not allocate a unique claim id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_claims(*, status: str | None = None) -> list[FundingClaim]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if status:
        sql += " WHERE c.status = ?"
        params.append(status)
    sql += " ORDER BY c.funding_period DESC, c.claim_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_claims failed")
        raise
    return [_row(r) for r in rows]


def get_claim(claim_id: str) -> FundingClaim | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE c.claim_id = ?", (claim_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_claim(%s) failed", claim_id)
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


def summary() -> dict[str, float]:
    claims = list_claims()
    total = sum(c.claim_amount for c in claims)
    submitted = sum(c.claim_amount for c in claims if c.status == "submitted")
    paid = sum(c.claim_amount for c in claims if c.status == "paid")
    return {"count": float(len(claims)), "total": round(total, 2),
            "submitted": round(submitted, 2), "paid": round(paid, 2)}


# ── Writes ───────────────────────────────────────────────────────────────────

def create_claim(data: dict[str, Any]) -> FundingClaim:
    _ensure_schema()
    payload = _validate(data)
    cid = generate_claim_id()
    try:
        with connect() as conn:
            if payload["pupil_id"] and not conn.execute(
                    "SELECT 1 FROM pupils WHERE pupil_id = ?",
                    (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO funding_claims (
                    claim_id, pupil_id, funding_period, entitlement,
                    funded_hours, weeks, hourly_rate, claim_amount,
                    headcount_date, status, submitted_date, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, payload["pupil_id"], payload["funding_period"],
                 payload["entitlement"], payload["funded_hours"],
                 payload["weeks"], payload["hourly_rate"], payload["claim_amount"],
                 payload["headcount_date"], payload["status"],
                 payload["submitted_date"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for claim id=%s", cid)
        raise ValidationError(f"Could not create claim — {e}") from e
    claim = get_claim(cid)
    assert claim is not None
    logger.info("Created funding claim %s (£%.2f)", cid, payload["claim_amount"])
    return claim


def update_claim(claim_id: str, data: dict[str, Any]) -> FundingClaim:
    _ensure_schema()
    payload = _validate(data)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE funding_claims SET
                    pupil_id = ?, funding_period = ?, entitlement = ?,
                    funded_hours = ?, weeks = ?, hourly_rate = ?,
                    claim_amount = ?, headcount_date = ?, status = ?,
                    submitted_date = ?, notes = ?
                WHERE claim_id = ?
                """,
                (payload["pupil_id"], payload["funding_period"],
                 payload["entitlement"], payload["funded_hours"],
                 payload["weeks"], payload["hourly_rate"], payload["claim_amount"],
                 payload["headcount_date"], payload["status"],
                 payload["submitted_date"], payload["notes"], claim_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No funding claim with id {claim_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for claim id=%s", claim_id)
        raise ValidationError(f"Could not update claim — {e}") from e
    claim = get_claim(claim_id)
    assert claim is not None
    logger.info("Updated funding claim %s", claim_id)
    return claim


def delete_claim(claim_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM funding_claims WHERE claim_id = ?", (claim_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting claim id=%s", claim_id)
        raise
    if deleted:
        logger.info("Deleted funding claim %s", claim_id)
    return deleted


def set_status(claim_id: str, status: str) -> FundingClaim:
    _ensure_schema()
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE funding_claims SET status = ? WHERE claim_id = ?",
                (status, claim_id))
            if cur.rowcount == 0:
                raise ValidationError(f"No funding claim with id {claim_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error setting status for claim %s", claim_id)
        raise
    claim = get_claim(claim_id)
    assert claim is not None
    return claim
