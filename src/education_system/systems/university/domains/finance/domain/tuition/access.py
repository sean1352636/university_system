"""Who may do what in student tuition finance, the area audit trail and the
small row helpers the tuition modules share.

Named capabilities (``CAPABILITIES``):

* ``finance.hold_override`` - let a student register although a finance
  hold is active (reason required, audited);
* ``finance.fee_status`` - record and decide fee-status assessments;
* ``finance.tuition`` - set programme tuition rates, the fee-liability
  schedule and charge / adjust tuition;
* ``finance.sponsors`` - sponsors, agreements, invoices and payments.

Admins (and the registrar) hold every capability. Finance staff (role
``staff``) hold the three day-to-day ones; ``finance.hold_override`` must be
granted to a named member of staff by an admin. Grants live in
``finance_capability_grants`` and every grant / revoke is audited.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime

from education_system.systems.university.infrastructure.database.schemas import (
    student_fees_schema as schema,
)

HOLD_OVERRIDE = "finance.hold_override"
FEE_STATUS = "finance.fee_status"
TUITION = "finance.tuition"
SPONSORS = "finance.sponsors"
CAPABILITIES = {
    HOLD_OVERRIDE: "Override a finance hold at registration",
    FEE_STATUS: "Assess and decide fee status",
    TUITION: "Tuition rates, liability schedule and tuition charges",
    SPONSORS: "Sponsors, agreements, invoices and payments",
}
ADMIN_ROLES = frozenset({"admin", "administrator", "superadmin", "super_admin", "registrar"})
STAFF_DEFAULTS = frozenset({FEE_STATUS, TUITION, SPONSORS})


def ensure(conn) -> None:
    schema.apply_to_connection(conn)


# ── rows ────────────────────────────────────────────────────────────────


def dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def one(cur) -> dict | None:
    rows = dicts(cur)
    return rows[0] if rows else None


def has_table(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today() -> str:
    return date.today().isoformat()


def money(value, label="Amount", *, allow_zero=True) -> float:
    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number") from None
    if amount < 0 or (amount == 0 and not allow_zero):
        raise ValueError(f"{label} must be more than zero" if not allow_zero
                         else f"{label} cannot be negative")
    return amount


def text(value, label, required=False) -> str | None:
    cleaned = str(value or "").strip()
    if required and not cleaned:
        raise ValueError(f"{label} is required")
    return cleaned or None


def year_start(value) -> int:
    """'2026/27', '2026-2027', '2026' -> 2026."""
    match = re.match(r"\s*(\d{4})", str(value or ""))
    if not match:
        raise ValueError("Academic year looks like 2026/27")
    return int(match.group(1))


def year_label(value) -> str:
    """Normalise an academic year to '2026/27'."""
    start = year_start(value)
    return f"{start}/{str(start + 1)[-2:]}"


def year_of(day: str | None) -> str:
    """The academic year (September start) a date falls in."""
    try:
        d = date.fromisoformat(str(day or "")[:10])
    except ValueError:
        d = date.today()
    start = d.year if d.month >= 9 else d.year - 1
    return year_label(start)


# ── who ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Actor:
    username: str
    role: str = ""
    student_id: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES

    @property
    def is_student(self) -> bool:
        return self.role == "student"


def actor_from_user(user) -> Actor | None:
    """An :class:`Actor` from an auth ``current_user`` dict (or None)."""
    if not user:
        return None
    if not isinstance(user, dict):
        user = getattr(user, "__dict__", {}) or {}
    username = str(user.get("username") or user.get("user_id") or user.get("id") or "").strip()
    if not username:
        return None
    return Actor(username=username, role=str(user.get("role") or "").lower(),
                 student_id=user.get("student_id"))


def holds(conn, who: Actor | None, capability: str) -> bool:
    if who is None or who.is_student:
        return False
    if who.is_admin:
        return True
    if who.role == "staff" and capability in STAFF_DEFAULTS:
        return True
    ensure(conn)
    return conn.execute("SELECT 1 FROM finance_capability_grants WHERE username = ? AND "
                        "capability = ?", (who.username, capability)).fetchone() is not None


def require(conn, who: Actor | None, capability: str) -> None:
    if not holds(conn, who, capability):
        raise PermissionError(f"You need the '{CAPABILITIES.get(capability, capability)}' "
                              "capability for this")


def require_self_or(conn, who: Actor | None, student_id, capability: str) -> None:
    if who is not None and who.is_student and str(who.student_id or who.username) == \
            str(student_id):
        return
    require(conn, who, capability)


def grants(conn) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT * FROM finance_capability_grants ORDER BY capability, "
                              "username"))


def grant(conn, who: Actor, username, capability) -> None:
    ensure(conn)
    if not (who and who.is_admin):
        raise PermissionError("Only an admin can grant finance capabilities")
    if capability not in CAPABILITIES:
        raise ValueError("Unknown capability: " + ", ".join(CAPABILITIES))
    username = text(username, "Username", True)
    conn.execute("INSERT OR IGNORE INTO finance_capability_grants (username, capability, "
                 "granted_by) VALUES (?, ?, ?)", (username, capability, who.username))
    audit(conn, who.username, "capability.granted", "capability", capability,
          detail={"username": username})


def revoke(conn, who: Actor, username, capability) -> None:
    ensure(conn)
    if not (who and who.is_admin):
        raise PermissionError("Only an admin can revoke finance capabilities")
    conn.execute("DELETE FROM finance_capability_grants WHERE username = ? AND capability = ?",
                 (username, capability))
    audit(conn, who.username, "capability.revoked", "capability", capability,
          detail={"username": username})


# ── audit ───────────────────────────────────────────────────────────────


def audit(conn, actor, action, entity, entity_id=None, *, student_id=None, detail=None) -> None:
    """One row in ``tuition_audit`` and the same in Finance's ``audit_log``
    (what the Finance window's Audit Log shows), in the caller's
    transaction."""
    ensure(conn)
    body = json.dumps(detail or {}, default=str, sort_keys=True)
    actor = str(actor or "system")
    conn.execute("INSERT INTO tuition_audit (actor, action, entity, entity_id, student_id, "
                 "detail_json) VALUES (?, ?, ?, ?, ?, ?)",
                 (actor, action, entity, None if entity_id is None else str(entity_id),
                  None if student_id is None else str(student_id), body))
    if has_table(conn, "audit_log"):
        conn.execute("INSERT INTO audit_log (user_id, action, table_name, record_id, new_values, "
                     "timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                     (actor, action, entity, None if entity_id is None else str(entity_id),
                      body, now()))


def audit_trail(conn, *, student_id=None, entity=None, limit=200) -> list[dict]:
    ensure(conn)
    where, params = [], []
    if student_id:
        where.append("student_id = ?")
        params.append(str(student_id))
    if entity:
        where.append("entity = ?")
        params.append(entity)
    sql = "SELECT * FROM tuition_audit"
    if where:
        sql += " WHERE " + " AND ".join(where)
    params.append(int(limit))
    return dicts(conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?", params))


def student_row(conn, student_id) -> dict:
    row = one(conn.execute(
        "SELECT student_id, TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) "
        "AS name, status, course, mode_of_study, fee_status, nationality, email_address "
        "FROM students WHERE student_id = ?", (str(student_id),)))
    if not row:
        raise ValueError(f"No student {student_id}")
    return row
