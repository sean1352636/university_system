"""Access control for the Equality & Diversity module (features 37–42).

Roles (case-insensitive, read from ``auth.current_user['role']``):

- ``student``                  — "My Data" tab only
- ``staff``/``Standard``       — records view + own incident reporting
- ``auditor``                  — read-only across all tabs
- ``administrator``/``admin``/``superadmin`` — full access
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from education_system.university_system.modules.domain.student_affairs.equality_diversity.schema import (
    get_connection,
)


ADMIN_ROLES = {"admin", "administrator", "superadmin", "super_admin", "staff_admin"}
AUDITOR_ROLES = {"auditor", "compliance_auditor"}
STUDENT_ROLES = {"student", "learner"}

# feature 38 — sensitive fields masked for anyone below Administrator/Auditor
SENSITIVE_FIELDS = {"sexual_orientation", "religion", "disability"}

# feature 39 — idle session timeout in seconds
IDLE_TIMEOUT_SECONDS = 15 * 60


@dataclass
class Principal:
    username: str
    role: str                    # canonical role: student/standard/auditor/administrator
    is_admin: bool
    is_auditor: bool
    is_student: bool
    user_id: Any = None
    email: str = ""
    last_activity: float = field(default_factory=time.time)

    # --- feature 37 — which tabs does this principal see ---------------------
    def tabs(self) -> list[str]:
        if self.is_student:
            return ["My Data", "Reports"]
        if self.is_auditor:
            return ["Dashboard", "Records", "Incidents", "Reports", "Admin"]
        if self.is_admin:
            return ["Dashboard", "Records", "Add Record", "Incidents",
                    "Reports", "Admin"]
        # standard staff
        return ["Dashboard", "Records", "Add Record", "Incidents", "Reports"]

    # --- feature 37 — per-capability gates -----------------------------------
    def can(self, capability: str) -> bool:
        write_caps = {
            "add_record", "edit_record", "delete_record", "bulk_import",
            "add_incident", "update_incident", "assign_incident",
            "add_note", "upload_attachment", "merge_records", "issue_token",
            "manage_schedules", "self_update",
        }
        admin_only = {
            "delete_record", "merge_records", "manage_schedules",
            "hard_delete", "issue_token", "manage_consent", "approve_deletion",
            "view_audit_log",
        }
        if capability in admin_only:
            return self.is_admin
        if self.is_admin:
            return True
        if self.is_auditor:
            return capability.startswith("view_") or capability in {"export_csv", "export_pdf"}
        if self.is_student:
            return capability in {"self_update", "view_own"}
        # standard staff
        return capability in write_caps - admin_only or capability.startswith("view_")

    # --- feature 38 — field-level masking ------------------------------------
    def mask(self, field_name: str, value: str) -> str:
        if value is None:
            return ""
        if field_name in SENSITIVE_FIELDS and not (self.is_admin or self.is_auditor):
            return "••••"
        return value

    # --- feature 39 — idle timeout -------------------------------------------
    def touch(self) -> None:
        self.last_activity = time.time()

    def is_idle(self) -> bool:
        return (time.time() - self.last_activity) > IDLE_TIMEOUT_SECONDS


def principal_from_auth(auth_manager) -> Principal | None:
    user = getattr(auth_manager, "current_user", None) or {}
    if not user:
        return None
    raw_role = (user.get("role") or "").strip().lower()
    return Principal(
        username=user.get("username") or user.get("email") or "unknown",
        role=raw_role,
        is_admin=raw_role in ADMIN_ROLES,
        is_auditor=raw_role in AUDITOR_ROLES,
        is_student=raw_role in STUDENT_ROLES,
        user_id=user.get("id"),
        email=user.get("email", ""),
    )


# ---------------------------------------------------------------- feature 40
def request_deletion(entity: str, entity_id: int, snapshot_json: str,
                     requested_by: str) -> int:
    """Queue a deletion for two-person approval. Returns the queue row id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO ed_deletions (entity, entity_id, snapshot, requested_by, "
            "requested_at, status) VALUES (?, ?, ?, ?, ?, 'pending_approval')",
            (entity, entity_id, snapshot_json, requested_by,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def approve_deletion(queue_id: int, approver: str) -> tuple[str, int, str] | None:
    """Second admin approves a deletion.

    Returns ``(entity, entity_id, snapshot_json)`` if approval took effect, or
    ``None`` if already approved / self-approval attempted.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT entity, entity_id, snapshot, requested_by, status "
            "FROM ed_deletions WHERE id=?",
            (queue_id,),
        ).fetchone()
        if not row:
            return None
        entity, entity_id, snap, requester, status = row
        if status != "pending_approval" or requester == approver:
            return None
        conn.execute(
            "UPDATE ed_deletions SET approved_by=?, approved_at=?, status='approved' "
            "WHERE id=?",
            (approver, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), queue_id),
        )
        conn.commit()
        return entity, int(entity_id), snap
    finally:
        conn.close()


def list_pending_deletions() -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, entity, entity_id, requested_by, requested_at "
            "FROM ed_deletions WHERE status='pending_approval' ORDER BY requested_at"
        ).fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------- feature 42
def record_view(entity: str, entity_id: int, viewer: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO ed_view_log (entity, entity_id, viewer, viewed_at) "
            "VALUES (?, ?, ?, ?)",
            (entity, entity_id, viewer, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
    finally:
        conn.close()


def views_of(entity: str, entity_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT viewer, viewed_at FROM ed_view_log "
            "WHERE entity=? AND entity_id=? ORDER BY viewed_at DESC",
            (entity, entity_id),
        ).fetchall()
    finally:
        conn.close()
