"""Shared case workflow for regulated university case types."""

from __future__ import annotations

import json
import uuid
from typing import Any

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

CASE_TYPES = frozenset(
    {"appeal", "complaint", "misconduct", "fitness_to_practise", "mitigating_circumstances"}
)


def open_case(
    case_type: str, subject_id: str, summary: str, *, opened_by: str,
    confidentiality: str = "restricted", owner_id: str | None = None,
) -> str:
    with transaction() as conn:
        return open_case_on(conn, case_type, subject_id, summary, opened_by=opened_by,
                            confidentiality=confidentiality, owner_id=owner_id)


def open_case_on(
    conn, case_type: str, subject_id: str, summary: str, *, opened_by: str,
    confidentiality: str = "restricted", owner_id: str | None = None,
) -> str:
    """:func:`open_case` on the caller's open connection (no commit), so a
    procedure can open the case and its own record in one transaction."""
    if case_type not in CASE_TYPES or not summary.strip():
        raise ValueError("A supported case type and summary are required")
    case_id = str(uuid.uuid4())
    cursor = conn.execute(
        """INSERT INTO institutional_cases
             (case_id, case_type, subject_id, summary, owner_id,
              confidentiality, opened_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(case_type, subject_id, summary) DO NOTHING""",
        (case_id, case_type, subject_id, summary, owner_id, confidentiality, opened_by),
    )
    if cursor.rowcount == 0:
        return str(conn.execute(
            "SELECT case_id FROM institutional_cases "
            "WHERE case_type=? AND subject_id=? AND summary=?",
            (case_type, subject_id, summary),
        ).fetchone()[0])
    conn.execute(
        """INSERT INTO institutional_case_events
             (case_id, event_type, payload_json, actor_id)
           VALUES (?, 'opened', '{}', ?)""",
        (case_id, opened_by),
    )
    return case_id


STATUSES = ("open", "triage", "investigation", "hearing", "decision", "review", "closed")


def transition_case(
    case_id: str, status: str, *, actor_id: str, reason: str,
    details: dict[str, Any] | None = None,
) -> None:
    with transaction() as conn:
        transition_case_on(conn, case_id, status, actor_id=actor_id, reason=reason,
                           details=details)


def transition_case_on(
    conn, case_id: str, status: str, *, actor_id: str, reason: str,
    details: dict[str, Any] | None = None,
) -> None:
    """:func:`transition_case` on the caller's open connection (no commit)."""
    if status not in STATUSES or not reason.strip():
        raise ValueError("A supported status and reason are required")
    row = conn.execute(
        "SELECT status FROM institutional_cases WHERE case_id=?", (case_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Case {case_id} does not exist")
    conn.execute(
        "UPDATE institutional_cases SET status=?, "
        "closed_at=CASE WHEN ?='closed' THEN CURRENT_TIMESTAMP END WHERE case_id=?",
        (status, status, case_id),
    )
    conn.execute(
        """INSERT INTO institutional_case_events
             (case_id, event_type, payload_json, actor_id)
           VALUES (?, ?, ?, ?)""",
        (
            case_id, f"transition:{status}",
            json.dumps({"from": row[0], "reason": reason, **(details or {})}),
            actor_id,
        ),
    )


def record_event_on(conn, case_id: str, event_type: str, *, actor_id: str,
                    details: dict[str, Any] | None = None) -> None:
    """Append a non-status event (assignment, action, letter) to a case's history."""
    conn.execute(
        """INSERT INTO institutional_case_events
             (case_id, event_type, payload_json, actor_id)
           VALUES (?, ?, ?, ?)""",
        (case_id, event_type, json.dumps(details or {}, default=str), actor_id),
    )


def case_record(case_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        case = conn.execute(
            "SELECT * FROM institutional_cases WHERE case_id=?", (case_id,)
        ).fetchone()
        if case is None:
            raise ValueError(f"Case {case_id} does not exist")
        result = dict(case)
        result["events"] = [
            dict(row) for row in conn.execute(
                "SELECT * FROM institutional_case_events WHERE case_id=? ORDER BY event_id",
                (case_id,),
            ).fetchall()
        ]
        return result


def list_cases(
    *, case_type: str | None = None, status: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    """Newest-first register view, optionally narrowed by type and status."""
    clauses: list[str] = []
    params: list[Any] = []
    if case_type:
        clauses.append("case_type=?")
        params.append(case_type)
    if status:
        clauses.append("status=?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(int(limit))
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT case_id, case_type, subject_id, status, summary, owner_id, "
            "confidentiality, opened_by, opened_at, closed_at FROM institutional_cases "
            f"{where} ORDER BY opened_at DESC LIMIT ?",  # noqa: S608 - fixed fragments
            params,
        ).fetchall()
    return [dict(row) for row in rows]


__all__ = ["CASE_TYPES", "STATUSES", "case_record", "list_cases", "open_case", "open_case_on",
           "record_event_on", "transition_case", "transition_case_on"]
