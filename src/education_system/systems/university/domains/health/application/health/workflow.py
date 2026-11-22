"""Health record archiving (soft delete) and the clinic workflow schema.

A health record is never hard-deleted from a screen: it is *archived* —
``health_records.archived = 1`` with who, when and why — by a clinician
only, and the archive is audited in the same transaction. Archived records
drop out of every list (:data:`LIVE`) but stay in the table for the
retention policy (``application/health/retention``) to remove in its time.
"""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.domains.health.application.health import access
from education_system.systems.university.domains.health.infrastructure.health import (
    workflow_schema,
)

#: SQL condition for records that are not archived (``health_records`` alias-free).
LIVE = "COALESCE(archived, 0) = 0"


def ensure_schema(conn) -> None:
    """The wave-2 clinic tables and columns (migration ``c2f4a6b8d0e3``),
    applied once per database for callers that may run before it."""
    workflow_schema.apply_to_connection(conn)


def archive_health_record(conn, who, record_id, reason: str) -> dict:
    """Archive one health record. Clinicians only; ``reason`` required;
    audited in ``conn``'s transaction (an audit failure raises and the
    caller rolls back). Does not commit. Returns the record's
    ``student_id`` / ``record_type`` / ``record_date``."""
    access.require_clinician(who, "archive health records")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Give a reason for archiving the record")
    ensure_schema(conn)
    row = conn.execute("SELECT student_id, record_type, record_date, COALESCE(archived, 0) "
                       "FROM health_records WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise LookupError(f"Health record {record_id} not found")
    if row[3]:
        raise ValueError(f"Health record {record_id} is already archived")
    conn.execute("UPDATE health_records SET archived = 1, archived_at = ?, archived_by = ?, "
                 "archive_reason = ? WHERE id = ?",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), who.username, reason,
                  record_id))
    from education_system.systems.university.domains.health.domain.health.records.db.audit import (
        log_audit_event,
    )
    log_audit_event(who.username, "ARCHIVE", "health_record", record_id,
                    {"student_id": row[0], "record_type": row[1]}, conn=conn, reason=reason)
    return {"student_id": row[0], "record_type": row[1], "record_date": row[2]}
