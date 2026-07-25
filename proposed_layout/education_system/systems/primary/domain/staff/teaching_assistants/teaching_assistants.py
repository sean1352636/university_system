"""Teaching assistants data layer.

Person-records for TAs working in the school. This is distinct from
``class_teachers`` (per-class assignments per academic year) — a TA can
have one record here describing who they are, their TA role and
contract details, and may also appear in multiple class assignments.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, _connect as _pupils_connect, _DOB_RE, _PHONE_RE,
)

logger = logging.getLogger(__name__)

ROLES: tuple[str, ...] = (
    "HLTA",         # Higher Level Teaching Assistant
    "TA",           # Standard teaching assistant
    "LSA",          # Learning Support Assistant
    "SEND TA",      # 1:1 / SEND support
    "EYFS TA",      # Early Years TA
    "Cover Supervisor",
    "Apprentice",
    "Other",
)
ROLE_LABELS: dict[str, str] = {
    "HLTA":             "Higher Level Teaching Assistant",
    "TA":               "Teaching Assistant",
    "LSA":              "Learning Support Assistant",
    "SEND TA":          "1:1 / SEND Support",
    "EYFS TA":          "Early Years TA",
    "Cover Supervisor": "Cover Supervisor",
    "Apprentice":       "Apprentice TA",
    "Other":            "Other",
}

EMPLOYMENT_TYPES: tuple[str, ...] = (
    "permanent", "fixed_term", "casual", "agency", "volunteer",
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS teaching_assistants (
    ta_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name       TEXT NOT NULL,
    last_name        TEXT NOT NULL,
    email            TEXT UNIQUE,
    phone            TEXT,
    role             TEXT NOT NULL DEFAULT 'TA',
    employment_type  TEXT NOT NULL DEFAULT 'permanent',
    assigned_class   TEXT,
    hours_per_week   REAL,
    start_date       TEXT,
    end_date         TEXT,
    dbs_checked      INTEGER NOT NULL DEFAULT 0,
    safeguarding_trained INTEGER NOT NULL DEFAULT 0,
    is_active        INTEGER NOT NULL DEFAULT 1,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ta_active   ON teaching_assistants(is_active);
CREATE INDEX IF NOT EXISTS idx_ta_role     ON teaching_assistants(role);
CREATE INDEX IF NOT EXISTS idx_ta_lastname ON teaching_assistants(last_name COLLATE NOCASE);
"""


@dataclass
class TeachingAssistant:
    ta_id: int
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    role: str
    employment_type: str
    assigned_class: str | None
    hours_per_week: float | None
    start_date: str | None
    end_date: str | None
    dbs_checked: bool
    safeguarding_trained: bool
    is_active: bool
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise teaching_assistants table")
        raise
    logger.info("Primary teaching_assistants table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> TeachingAssistant:
    return TeachingAssistant(
        ta_id=r["ta_id"],
        first_name=r["first_name"],
        last_name=r["last_name"],
        email=r["email"],
        phone=r["phone"],
        role=r["role"],
        employment_type=r["employment_type"],
        assigned_class=r["assigned_class"],
        hours_per_week=r["hours_per_week"],
        start_date=r["start_date"],
        end_date=r["end_date"],
        dbs_checked=bool(r["dbs_checked"]),
        safeguarding_trained=bool(r["safeguarding_trained"]),
        is_active=bool(r["is_active"]),
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    fn = (data.get("first_name") or "").strip()
    ln = (data.get("last_name") or "").strip()
    if not fn:
        raise ValidationError("First name is required")
    if not ln:
        raise ValidationError("Last name is required")
    if len(fn) > 60 or len(ln) > 60:
        raise ValidationError("Names must be 60 characters or fewer")
    out["first_name"] = fn
    out["last_name"]  = ln
    em = (data.get("email") or "").strip()
    if em and not _EMAIL_RE.match(em):
        raise ValidationError("Email is not a valid address")
    out["email"] = em or None
    ph = (data.get("phone") or "").strip()
    if ph and not _PHONE_RE.match(ph):
        raise ValidationError("Phone contains invalid characters")
    out["phone"] = ph or None
    role = (data.get("role") or "TA").strip() or "TA"
    if role not in ROLES:
        raise ValidationError(f"Role must be one of {', '.join(ROLES)}")
    out["role"] = role
    emp = (data.get("employment_type") or "permanent").strip().lower() or "permanent"
    if emp not in EMPLOYMENT_TYPES:
        raise ValidationError(
            f"Employment type must be one of {', '.join(EMPLOYMENT_TYPES)}")
    out["employment_type"] = emp
    out["assigned_class"] = (data.get("assigned_class") or "").strip() or None
    hpw_raw = data.get("hours_per_week")
    if hpw_raw in (None, ""):
        out["hours_per_week"] = None
    else:
        try:
            hpw = float(hpw_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError("Hours per week must be a number") from e
        if hpw < 0 or hpw > 60:
            raise ValidationError("Hours per week must be between 0 and 60")
        out["hours_per_week"] = hpw
    sd = (data.get("start_date") or "").strip()
    if sd and not _DOB_RE.match(sd):
        raise ValidationError("Start date must be YYYY-MM-DD")
    ed = (data.get("end_date") or "").strip()
    if ed and not _DOB_RE.match(ed):
        raise ValidationError("End date must be YYYY-MM-DD")
    if sd and ed and ed < sd:
        raise ValidationError("End date cannot be before start date")
    out["start_date"] = sd or None
    out["end_date"]   = ed or None
    out["dbs_checked"] = bool(data.get("dbs_checked"))
    out["safeguarding_trained"] = bool(data.get("safeguarding_trained"))
    is_active = data.get("is_active")
    out["is_active"] = True if is_active is None else bool(is_active)
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> TeachingAssistant:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            if payload["email"]:
                dup = conn.execute(
                    "SELECT ta_id FROM teaching_assistants WHERE email = ?",
                    (payload["email"],),
                ).fetchone()
                if dup:
                    raise ValidationError(
                        f"A TA with email {payload['email']!r} already exists "
                        f"(#{dup['ta_id']})")
            cur = conn.execute(
                """INSERT INTO teaching_assistants
                       (first_name, last_name, email, phone, role,
                        employment_type, assigned_class, hours_per_week,
                        start_date, end_date, dbs_checked,
                        safeguarding_trained, is_active, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["first_name"], payload["last_name"], payload["email"],
                 payload["phone"], payload["role"], payload["employment_type"],
                 payload["assigned_class"], payload["hours_per_week"],
                 payload["start_date"], payload["end_date"],
                 1 if payload["dbs_checked"] else 0,
                 1 if payload["safeguarding_trained"] else 0,
                 1 if payload["is_active"] else 0, payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        logger.exception("Integrity error creating TA")
        raise ValidationError(f"Could not create TA — {e}") from e
    except sqlite3.Error:
        logger.exception("Failed to create TA")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created TA #%d %s (%s)", rec.ta_id, rec.full_name, rec.role)
    return rec


def get(ta_id: int) -> TeachingAssistant | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM teaching_assistants WHERE ta_id = ?",
                (ta_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get TA(%s) failed", ta_id)
        raise
    return _row(r) if r else None


def update(ta_id: int, data: dict[str, Any]) -> TeachingAssistant:
    init_db()
    existing = get(ta_id)
    if existing is None:
        raise ValidationError(f"No TA #{ta_id}")
    merged = {
        "first_name":           data.get("first_name", existing.first_name),
        "last_name":            data.get("last_name", existing.last_name),
        "email":                data.get("email", existing.email),
        "phone":                data.get("phone", existing.phone),
        "role":                 data.get("role", existing.role),
        "employment_type":      data.get("employment_type",
                                        existing.employment_type),
        "assigned_class":       data.get("assigned_class",
                                        existing.assigned_class),
        "hours_per_week":       data.get("hours_per_week",
                                        existing.hours_per_week),
        "start_date":           data.get("start_date", existing.start_date),
        "end_date":             data.get("end_date", existing.end_date),
        "dbs_checked":          data.get("dbs_checked", existing.dbs_checked),
        "safeguarding_trained": data.get("safeguarding_trained",
                                        existing.safeguarding_trained),
        "is_active":            data.get("is_active", existing.is_active),
        "notes":                data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    try:
        with _connect() as conn:
            if payload["email"]:
                dup = conn.execute(
                    "SELECT ta_id FROM teaching_assistants "
                    "WHERE email = ? AND ta_id <> ?",
                    (payload["email"], ta_id),
                ).fetchone()
                if dup:
                    raise ValidationError(
                        f"Another TA with email {payload['email']!r} exists "
                        f"(#{dup['ta_id']})")
            conn.execute(
                """UPDATE teaching_assistants SET
                       first_name = ?, last_name = ?, email = ?, phone = ?,
                       role = ?, employment_type = ?, assigned_class = ?,
                       hours_per_week = ?, start_date = ?, end_date = ?,
                       dbs_checked = ?, safeguarding_trained = ?,
                       is_active = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE ta_id = ?""",
                (payload["first_name"], payload["last_name"], payload["email"],
                 payload["phone"], payload["role"], payload["employment_type"],
                 payload["assigned_class"], payload["hours_per_week"],
                 payload["start_date"], payload["end_date"],
                 1 if payload["dbs_checked"] else 0,
                 1 if payload["safeguarding_trained"] else 0,
                 1 if payload["is_active"] else 0,
                 payload["notes"], ta_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("Integrity error updating TA #%d", ta_id)
        raise ValidationError(f"Could not update TA — {e}") from e
    except sqlite3.Error:
        logger.exception("Failed to update TA #%d", ta_id)
        raise
    rec = get(ta_id)
    assert rec is not None
    logger.info("Updated TA #%d %s", rec.ta_id, rec.full_name)
    return rec


def toggle_active(ta_id: int) -> TeachingAssistant:
    init_db()
    existing = get(ta_id)
    if existing is None:
        raise ValidationError(f"No TA #{ta_id}")
    new_val = 0 if existing.is_active else 1
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE teaching_assistants SET is_active = ?, "
                "updated_at = datetime('now') WHERE ta_id = ?",
                (new_val, ta_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("toggle_active(%s) failed", ta_id)
        raise
    rec = get(ta_id)
    assert rec is not None
    logger.info("TA #%d %s -> active=%s",
                rec.ta_id, rec.full_name, rec.is_active)
    return rec


def delete(ta_id: int) -> bool:
    init_db()
    existing = get(ta_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM teaching_assistants WHERE ta_id = ?", (ta_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete TA #%d", ta_id)
        raise
    if deleted:
        logger.info("Deleted TA #%d %s", ta_id, existing.full_name)
    return deleted


def list_all(
    *, role: str | None = None,
    active_only: bool = False,
    search: str | None = None,
    needs_dbs: bool | None = None,
    needs_safeguarding: bool | None = None,
) -> list[TeachingAssistant]:
    init_db()
    if role is not None and role not in ROLES:
        raise ValidationError(
            f"Role filter must be one of {', '.join(ROLES)}")
    where: list[str] = []
    params: list[Any] = []
    if role:
        where.append("role = ?")
        params.append(role)
    if active_only:
        where.append("is_active = 1")
    if search:
        q = f"%{search.strip()}%"
        where.append("(first_name LIKE ? OR last_name LIKE ? "
                     "OR email LIKE ? OR assigned_class LIKE ?)")
        params.extend([q, q, q, q])
    if needs_dbs is True:
        where.append("dbs_checked = 0")
    elif needs_dbs is False:
        where.append("dbs_checked = 1")
    if needs_safeguarding is True:
        where.append("safeguarding_trained = 0")
    elif needs_safeguarding is False:
        where.append("safeguarding_trained = 1")
    sql = "SELECT * FROM teaching_assistants"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list TAs failed")
        raise
    return [_row(r) for r in rows]


def summary() -> dict[str, Any]:
    init_db()
    try:
        with _connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM teaching_assistants").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM teaching_assistants WHERE is_active = 1"
            ).fetchone()[0]
            no_dbs = conn.execute(
                "SELECT COUNT(*) FROM teaching_assistants "
                "WHERE is_active = 1 AND dbs_checked = 0"
            ).fetchone()[0]
            no_sg = conn.execute(
                "SELECT COUNT(*) FROM teaching_assistants "
                "WHERE is_active = 1 AND safeguarding_trained = 0"
            ).fetchone()[0]
            hours = conn.execute(
                "SELECT COALESCE(SUM(hours_per_week), 0) "
                "FROM teaching_assistants WHERE is_active = 1"
            ).fetchone()[0] or 0.0
            by_role = {
                r["role"]: r["n"]
                for r in conn.execute(
                    "SELECT role, COUNT(*) AS n FROM teaching_assistants "
                    "WHERE is_active = 1 GROUP BY role"
                ).fetchall()
            }
    except sqlite3.Error:
        logger.exception("TA summary failed")
        raise
    return {
        "total": total,
        "active": active,
        "needs_dbs": no_dbs,
        "needs_safeguarding": no_sg,
        "total_hours_per_week": float(hours),
        "by_role": {r: by_role.get(r, 0) for r in ROLES},
    }
