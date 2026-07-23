"""Access control for the Equality & Diversity module (features 37–42).

Roles (case-insensitive, read from ``auth.current_user['role']``):

- ``student``                  — "My Data" tab only
- ``staff``/``Standard``       — records view + own incident reporting
- ``auditor``                  — read-only across all tabs
- ``administrator``/``admin``/``superadmin`` — full access
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity import (
    integrations,
)
from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity.schema import (
    DEMOGRAPHIC_FIELDS,
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


# ============================================================================
# Records (ed_people) — list / read / create / edit helpers.
#
# These mirror the raw SQL the Records/Add-Record GUI tabs run inline, so the
# CLI and GUI operate on the same rows and emit the same audit trail. Kept
# here (rather than a services/ dir) to match the module layout.
# ============================================================================

# fields the GUI RecordEditor / Add-Record form allow writing
RECORD_EDITABLE_FIELDS = (
    "department", "age_group", "gender", "ethnicity", "disability",
    "religion", "sexual_orientation", "nationality", "salary", "accommodations",
)


def _table_columns(conn, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def list_records(search: str = "", filters: dict | None = None,
                 include_deleted: bool = False, limit: int = 200) -> list[dict]:
    """List monitoring records (ed_people) as dicts. Mirrors the GUI Records tab."""
    clauses = [] if include_deleted else ["deleted_at IS NULL"]
    params: list = []
    if search:
        clauses.append("(ref_code LIKE ? OR department LIKE ? "
                       "OR person_type LIKE ? OR ethnicity LIKE ?)")
        like = f"%{search}%"
        params += [like, like, like, like]
    for f, v in (filters or {}).items():
        if f in DEMOGRAPHIC_FIELDS and v:
            clauses.append(f"{f} = ?")
            params.append(v)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    conn = get_connection()
    try:
        cols = _table_columns(conn, "ed_people")
        rows = conn.execute(
            f"SELECT * FROM ed_people{where} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    finally:
        conn.close()
    return [dict(zip(cols, r)) for r in rows]


def get_record(record_id: int) -> dict | None:
    conn = get_connection()
    try:
        cols = _table_columns(conn, "ed_people")
        row = conn.execute(
            "SELECT * FROM ed_people WHERE id=?", (record_id,)
        ).fetchone()
    finally:
        conn.close()
    return dict(zip(cols, row)) if row else None


def create_record(ref_code: str, person_type: str, *, department: str | None = None,
                  age_group: str | None = None, gender: str | None = None,
                  ethnicity: str | None = None, disability: str | None = None,
                  religion: str | None = None, sexual_orientation: str | None = None,
                  nationality: str | None = None, salary: float | None = None,
                  accommodations: str | None = None,
                  created_by: str = "cli-user") -> int:
    """Insert a monitoring record. Raises on duplicate ref_code (UNIQUE)."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO ed_people (ref_code, person_type, department, age_group, "
            "gender, ethnicity, disability, religion, sexual_orientation, "
            "nationality, salary, accommodations, date_added) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ref_code, person_type, department, age_group, gender, ethnicity,
             disability, religion, sexual_orientation, nationality, salary,
             accommodations, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        new_id = int(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()
    integrations.audit(created_by, "create", "person", new_id, {"ref_code": ref_code})
    return new_id


def update_record(record_id: int, updates: dict, updated_by: str = "cli-user") -> bool:
    """Update editable demographic fields on a record. Returns True if a row changed."""
    fields = {k: v for k, v in updates.items() if k in RECORD_EDITABLE_FIELDS}
    if not fields:
        return False
    sets = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?, updated_by=?"
    conn = get_connection()
    try:
        cur = conn.execute(
            f"UPDATE ed_people SET {sets} WHERE id=?",
            (*fields.values(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             updated_by, record_id),
        )
        conn.commit()
        changed = cur.rowcount > 0
    finally:
        conn.close()
    if changed:
        integrations.audit(updated_by, "update", "person", record_id, fields)
    return changed


def soft_delete_record(record_id: int, requested_by: str = "cli-user") -> int | None:
    """Soft-delete a record and queue it for two-person approval.

    Mirrors the GUI 'Request Delete' action. Returns the deletion-queue id, or
    ``None`` if there is no such record.
    """
    conn = get_connection()
    try:
        cols = _table_columns(conn, "ed_people")
        row = conn.execute(
            "SELECT * FROM ed_people WHERE id=?", (record_id,)
        ).fetchone()
        if not row:
            return None
        snapshot = json.dumps(dict(zip(cols, row)), default=str)
        conn.execute(
            "UPDATE ed_people SET deleted_at=?, deleted_by=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), requested_by, record_id),
        )
        conn.commit()
    finally:
        conn.close()
    qid = request_deletion("person", record_id, snapshot, requested_by)
    integrations.audit(requested_by, "soft_delete", "person", record_id,
                       {"queue_id": qid})
    return qid


# ============================================================================
# Incidents (ed_incidents) — list / read / submit / status / assign helpers.
# ============================================================================

# severity → SLA window (days); mirrors gui/_constants.SLA_DAYS
INCIDENT_SLA_DAYS = {"Low": 30, "Medium": 14, "High": 5, "Critical": 1}


def list_incidents(status: str | None = None, limit: int = 200) -> list[dict]:
    conn = get_connection()
    try:
        cols = _table_columns(conn, "ed_incidents")
        if status:
            rows = conn.execute(
                "SELECT * FROM ed_incidents WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ed_incidents ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    finally:
        conn.close()
    return [dict(zip(cols, r)) for r in rows]


def get_incident(incident_id: int) -> dict | None:
    conn = get_connection()
    try:
        cols = _table_columns(conn, "ed_incidents")
        row = conn.execute(
            "SELECT * FROM ed_incidents WHERE id=?", (incident_id,)
        ).fetchone()
    finally:
        conn.close()
    return dict(zip(cols, row)) if row else None


def create_incident(category: str, *, department: str | None = None,
                    description: str = "", severity: str = "Medium",
                    reported_by: str = "cli-user", respondent: str | None = None,
                    witnesses: str | None = None, anonymous: bool = False) -> int:
    """Submit an incident. SLA deadline is derived from the severity."""
    sla_due = (datetime.now() + timedelta(
        days=INCIDENT_SLA_DAYS.get(severity, 14))).strftime("%Y-%m-%d %H:%M")
    reporter = "anonymous" if anonymous else reported_by
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO ed_incidents (date_reported, category, department, "
            "description, status, reported_by, severity, sla_deadline, "
            "respondent, witnesses, anonymous) "
            "VALUES (?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), category, department,
             description, reporter, severity, sla_due, respondent, witnesses,
             int(bool(anonymous))),
        )
        inc_id = int(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()
    integrations.audit(reporter, "create", "incident", inc_id,
                       {"category": category, "severity": severity})
    return inc_id


def update_incident_status(incident_id: int, status: str,
                           actor: str = "cli-user") -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE ed_incidents SET status=? WHERE id=?", (status, incident_id))
        conn.commit()
        changed = cur.rowcount > 0
    finally:
        conn.close()
    if changed:
        integrations.audit(actor, "status_change", "incident", incident_id,
                           {"status": status})
    return changed


def assign_incident(incident_id: int, assignee: str,
                    actor: str = "cli-user") -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE ed_incidents SET assigned_to=? WHERE id=?",
            (assignee, incident_id))
        conn.commit()
        changed = cur.rowcount > 0
    finally:
        conn.close()
    if changed:
        integrations.audit(actor, "assign", "incident", incident_id,
                           {"assignee": assignee})
    return changed
