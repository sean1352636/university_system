"""Purpose-bound field authorization and independently reviewed break-glass."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable

from education_system.platform.identity.auth.db import connect
from education_system.platform.kernel.core.correlation import get_correlation_id

ALLOWED_PURPOSES = {
    "direct_care",
    "safeguarding_casework",
    "legal_obligation",
    "student_request",
    "quality_audit",
}

FIELD_POLICIES = {
    "health": {
        "student": {"appointments", "care_plan", "consents"},
        "clinician": {"*"},
        "health_admin": {"appointments", "contact", "consents"},
        "superadmin": {"*"},
    },
    "safeguarding": {
        "student": {"own_submission_status"},
        "dsl": {"*"},
        "safeguarding": {"*"},
        "superadmin": {"*"},
    },
}


@dataclass(frozen=True, slots=True)
class AccessDecision:
    allowed: bool
    reason: str
    grant_id: str | None = None


def authorize_sensitive_fields(
    *,
    actor_id: str,
    actor_role: str,
    domain: str,
    subject_id: str | None,
    fields: Iterable[str],
    purpose: str,
    db_path: str | None = None,
) -> AccessDecision:
    requested = frozenset(fields)
    role = actor_role.lower()
    allowed_fields = FIELD_POLICIES.get(domain, {}).get(role, set())
    allowed = (
        purpose in ALLOWED_PURPOSES
        and bool(requested)
        and ("*" in allowed_fields or requested <= allowed_fields)
    )
    reason = "allowed by field and purpose policy" if allowed else "denied by field or purpose policy"
    grant_id = None
    if not allowed:
        grant_id = _active_break_glass(
            actor_id, domain, subject_id, purpose, db_path=db_path
        )
        if grant_id:
            allowed, reason = True, "allowed by active break-glass grant"
    _audit(
        actor_id=actor_id,
        actor_role=actor_role,
        domain=domain,
        subject_id=subject_id,
        fields=requested,
        purpose=purpose,
        decision="allowed" if allowed else "denied",
        reason=reason,
        db_path=db_path,
    )
    return AccessDecision(allowed, reason, grant_id)


def request_break_glass(
    *,
    actor_id: str,
    domain: str,
    subject_id: str | None,
    purpose: str,
    reason: str,
    minutes: int = 30,
    db_path: str | None = None,
) -> str:
    if not reason.strip() or purpose not in ALLOWED_PURPOSES:
        raise ValueError("A valid purpose and reason are required")
    if minutes < 5 or minutes > 120:
        raise ValueError("Break-glass duration must be 5 to 120 minutes")
    grant_id = str(uuid.uuid4())
    expires = datetime.now(UTC) + timedelta(minutes=minutes)
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO break_glass_grants
                 (grant_id, actor_id, domain, subject_id, purpose, reason,
                  expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                grant_id, actor_id, domain, subject_id, purpose,
                reason.strip(), expires.isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return grant_id


def approve_break_glass(
    grant_id: str,
    *,
    approved_by: str,
    db_path: str | None = None,
) -> bool:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT actor_id FROM break_glass_grants WHERE grant_id = ?",
            (grant_id,),
        ).fetchone()
        if row is None:
            return False
        if str(row["actor_id"]) == approved_by:
            raise ValueError("Break-glass access requires independent approval")
        cursor = conn.execute(
            """UPDATE break_glass_grants SET status = 'approved',
                      approved_by = ?, approved_at = datetime('now')
                WHERE grant_id = ? AND status = 'pending'
                  AND datetime(expires_at) > datetime('now')""",
            (approved_by, grant_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def review_break_glass(
    grant_id: str,
    *,
    reviewed_by: str,
    outcome: str,
    db_path: str | None = None,
) -> bool:
    if outcome not in {"appropriate", "inappropriate", "investigate"}:
        raise ValueError("Invalid review outcome")
    conn = connect(db_path)
    try:
        cursor = conn.execute(
            """UPDATE break_glass_grants
                  SET reviewed_by = ?, reviewed_at = datetime('now'),
                      review_outcome = ?, status = 'reviewed'
                WHERE grant_id = ? AND approved_by IS NOT NULL
                  AND actor_id <> ?""",
            (reviewed_by, outcome, grant_id, reviewed_by),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def _active_break_glass(
    actor_id: str,
    domain: str,
    subject_id: str | None,
    purpose: str,
    *,
    db_path: str | None,
) -> str | None:
    conn = connect(db_path)
    try:
        row = conn.execute(
            """SELECT grant_id FROM break_glass_grants
                WHERE actor_id = ? AND domain = ? AND purpose = ?
                  AND (subject_id IS NULL OR subject_id = ?)
                  AND status = 'approved'
                  AND datetime(expires_at) > datetime('now')
                ORDER BY approved_at DESC LIMIT 1""",
            (actor_id, domain, purpose, subject_id),
        ).fetchone()
        return str(row["grant_id"]) if row else None
    finally:
        conn.close()


def _audit(
    *,
    actor_id: str,
    actor_role: str,
    domain: str,
    subject_id: str | None,
    fields: Iterable[str],
    purpose: str,
    decision: str,
    reason: str,
    db_path: str | None,
) -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO sensitive_access_audit
                 (audit_id, actor_id, actor_role, domain, subject_id,
                  fields_json, purpose, decision, reason, correlation_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), actor_id, actor_role, domain, subject_id,
                json.dumps(sorted(fields)), purpose, decision, reason,
                get_correlation_id() or None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


__all__ = [
    "AccessDecision",
    "approve_break_glass",
    "authorize_sensitive_fields",
    "request_break_glass",
    "review_break_glass",
]
