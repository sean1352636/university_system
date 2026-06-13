"""Domain layer for Safeguarding / Child Protection (Nursery System).

Owns the ``safeguarding_concerns`` table — child-protection concerns raised
about a child, reviewed by the Designated Safeguarding Lead, with a severity and
an open → monitoring → referred → closed workflow. The table is created on
demand (``CREATE TABLE IF NOT EXISTS``) inside the shared nursery DB, so this
module is self-contained.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``safeguarding_cli.py``, Tk GUI in ``safeguarding_views.py``.
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

FEATURE_NAME = "Safeguarding / Child Protection"
CATEGORY = "Safeguarding & Welfare"

ID_PREFIX = "NSG"
ID_DIGITS = 3

CATEGORIES = (
    "Neglect", "Physical abuse", "Emotional abuse", "Sexual abuse",
    "Child sexual exploitation", "FGM", "Domestic abuse", "Online safety",
    "Other",
)
SEVERITIES = ("low", "medium", "high")
STATUSES = ("open", "monitoring", "referred", "closed")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS safeguarding_concerns (
    concern_id    TEXT PRIMARY KEY,
    pupil_id      TEXT,
    category      TEXT,
    date_raised   TEXT,
    raised_by     TEXT,
    description   TEXT,
    severity      TEXT NOT NULL DEFAULT 'medium',
    dsl_reviewer  TEXT,
    action_taken  TEXT,
    referral_made INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'open',
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE SET NULL,
    FOREIGN KEY (dsl_reviewer) REFERENCES staff(staff_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_safeguarding_status ON safeguarding_concerns(status);
"""


class ValidationError(ValueError):
    """Raised for invalid safeguarding-concern input."""


@dataclass
class Concern:
    concern_id: str
    pupil_id: str | None
    category: str | None
    date_raised: str | None
    raised_by: str | None
    description: str | None
    severity: str
    dsl_reviewer: str | None
    action_taken: str | None
    referral_made: bool
    status: str
    notes: str | None
    child_name: str | None = None
    dsl_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
        with connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to initialise schema for safeguarding")
        raise


_SELECT = """
SELECT c.*,
       TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, '')) AS child_name,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) AS dsl_name
FROM safeguarding_concerns c
LEFT JOIN pupils p ON p.pupil_id = c.pupil_id
LEFT JOIN staff s ON s.staff_id = c.dsl_reviewer
"""


def _row(r: sqlite3.Row) -> Concern:
    keys = r.keys()
    return Concern(
        concern_id=r["concern_id"],
        pupil_id=r["pupil_id"],
        category=r["category"],
        date_raised=r["date_raised"],
        raised_by=r["raised_by"],
        description=r["description"],
        severity=r["severity"],
        dsl_reviewer=r["dsl_reviewer"],
        action_taken=r["action_taken"],
        referral_made=bool(r["referral_made"]),
        status=r["status"],
        notes=r["notes"],
        child_name=(r["child_name"] or None) if "child_name" in keys else None,
        dsl_name=(r["dsl_name"] or None) if "dsl_name" in keys else None,
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


def _as_bool(value: Any) -> int:
    if isinstance(value, (bool, int)):
        return int(bool(value))
    return int(str(value or "").strip().lower() in ("1", "y", "yes", "true", "on"))


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["pupil_id"] = _opt(data.get("pupil_id"))
    category = (data.get("category") or "").strip()
    if category and category not in CATEGORIES:
        raise ValidationError("Category must be one of: " + ", ".join(CATEGORIES))
    out["category"] = category or None
    out["date_raised"] = _opt_date(data.get("date_raised"), "Date raised")
    out["raised_by"] = _opt(data.get("raised_by"))
    out["description"] = _opt(data.get("description"))
    severity = (data.get("severity") or "medium").strip().lower()
    if severity not in SEVERITIES:
        raise ValidationError(f"Severity must be one of {', '.join(SEVERITIES)}")
    out["severity"] = severity
    out["dsl_reviewer"] = _opt(data.get("dsl_reviewer"))
    out["action_taken"] = _opt(data.get("action_taken"))
    out["referral_made"] = _as_bool(data.get("referral_made"))
    out["notes"] = _opt(data.get("notes"))
    status = (data.get("status") or "open").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_concern_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT concern_id FROM safeguarding_concerns").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing safeguarding ids")
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
    raise RuntimeError("Could not allocate a unique concern id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_concerns(*, status: str | None = None) -> list[Concern]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if status:
        sql += " WHERE c.status = ?"
        params.append(status)
    sql += " ORDER BY c.date_raised DESC, c.concern_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_concerns failed")
        raise
    return [_row(r) for r in rows]


def get_concern(concern_id: str) -> Concern | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE c.concern_id = ?", (concern_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_concern(%s) failed", concern_id)
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


def summary() -> dict[str, int]:
    concerns = list_concerns()
    open_n = sum(1 for c in concerns if c.status in ("open", "monitoring"))
    referred = sum(1 for c in concerns if c.referral_made)
    high = sum(1 for c in concerns if c.severity == "high"
               and c.status != "closed")
    return {"total": len(concerns), "open": open_n, "referred": referred,
            "high_open": high}


# ── Writes ───────────────────────────────────────────────────────────────────

def create_concern(data: dict[str, Any]) -> Concern:
    _ensure_schema()
    payload = _validate(data)
    cid = generate_concern_id()
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO safeguarding_concerns (
                    concern_id, pupil_id, category, date_raised, raised_by,
                    description, severity, dsl_reviewer, action_taken,
                    referral_made, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, payload["pupil_id"], payload["category"],
                 payload["date_raised"], payload["raised_by"],
                 payload["description"], payload["severity"],
                 payload["dsl_reviewer"], payload["action_taken"],
                 payload["referral_made"], payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("INSERT failed for safeguarding id=%s", cid)
        raise ValidationError(f"Could not create concern — {e}") from e
    concern = get_concern(cid)
    assert concern is not None
    logger.info("Created safeguarding concern %s (severity %s)",
                cid, payload["severity"])
    # Mirror onto the cross-system safeguarding register so the flag
    # follows the child between systems (best-effort; never blocks).
    try:
        from education_system.shared.safeguarding import alert_service
        alert_service.raise_flag_for_local_concern(
            "nursery", concern.pupil_id, category=concern.category,
            severity=concern.severity, summary=concern.category,
            source_ref=cid, raised_by=payload.get("raised_by"))
    except Exception:
        logger.debug("Cross-system safeguarding publish skipped for %s",
                     cid, exc_info=True)
    return concern


def update_concern(concern_id: str, data: dict[str, Any]) -> Concern:
    _ensure_schema()
    payload = _validate(data)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE safeguarding_concerns SET
                    pupil_id = ?, category = ?, date_raised = ?, raised_by = ?,
                    description = ?, severity = ?, dsl_reviewer = ?,
                    action_taken = ?, referral_made = ?, status = ?, notes = ?
                WHERE concern_id = ?
                """,
                (payload["pupil_id"], payload["category"], payload["date_raised"],
                 payload["raised_by"], payload["description"], payload["severity"],
                 payload["dsl_reviewer"], payload["action_taken"],
                 payload["referral_made"], payload["status"], payload["notes"],
                 concern_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No concern with id {concern_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for safeguarding id=%s", concern_id)
        raise ValidationError(f"Could not update concern — {e}") from e
    concern = get_concern(concern_id)
    assert concern is not None
    logger.info("Updated safeguarding concern %s", concern_id)
    return concern


def delete_concern(concern_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM safeguarding_concerns WHERE concern_id = ?",
                (concern_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting safeguarding id=%s", concern_id)
        raise
    if deleted:
        logger.info("Deleted safeguarding concern %s", concern_id)
    return deleted
