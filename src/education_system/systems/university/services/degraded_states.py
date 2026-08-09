"""Persistent operational degradation registry and alert boundary."""

from __future__ import annotations

import json
import logging
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.operations import OperationalIssue

logger = logging.getLogger(__name__)


def record_degraded_state(
    component: str,
    issue: OperationalIssue,
    *,
    severity: str = "warning",
    correlation_id: str | None = None,
) -> int:
    """Open or increment a degraded state and emit an operator alert."""
    if severity not in {"warning", "error", "critical"}:
        raise ValueError("severity must be warning, error or critical")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO operational_degraded_states
                   (component, code, severity, message, retryable,
                    correlation_id, details_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(component, code, status) DO UPDATE SET
                   severity = excluded.severity,
                   message = excluded.message,
                   retryable = excluded.retryable,
                   correlation_id = excluded.correlation_id,
                   details_json = excluded.details_json,
                   occurrence_count = occurrence_count + 1,
                   last_seen_at = CURRENT_TIMESTAMP""",
            (
                component,
                issue.code,
                severity,
                issue.message,
                int(issue.retryable),
                correlation_id,
                json.dumps(dict(issue.details), default=str),
            ),
        )
        row = conn.execute(
            """SELECT state_id, occurrence_count
                 FROM operational_degraded_states
                WHERE component = ? AND code = ? AND status = 'open'""",
            (component, issue.code),
        ).fetchone()
    assert row is not None
    log = logger.critical if severity == "critical" else logger.error
    log(
        "Operational degradation component=%s code=%s occurrences=%s: %s",
        component,
        issue.code,
        row["occurrence_count"],
        issue.message,
    )
    return int(row["state_id"])


def list_degraded_states(*, status: str = "open") -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM operational_degraded_states
                WHERE status = ? ORDER BY severity DESC, last_seen_at DESC""",
            (status,),
        ).fetchall()
    return [
        {
            **dict(row),
            "details": json.loads(row["details_json"] or "{}"),
        }
        for row in rows
    ]


def resolve_degraded_state(
    state_id: int, *, resolved_by: str, notes: str
) -> bool:
    if not resolved_by.strip() or not notes.strip():
        raise ValueError("resolved_by and notes are required")
    with transaction() as conn:
        cursor = conn.execute(
            """UPDATE operational_degraded_states
                  SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP,
                      resolved_by = ?, resolution_notes = ?
                WHERE state_id = ? AND status = 'open'""",
            (resolved_by, notes, state_id),
        )
        return cursor.rowcount == 1


__all__ = [
    "list_degraded_states",
    "record_degraded_state",
    "resolve_degraded_state",
]
