"""Complaints and the running record under each one.

The list filters are shaped for "what is waiting on me": open, overdue
for acknowledgement or response, due before a date, raised by a login,
handled by a login, or about an apprentice.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.quality.complaints import (
    OPEN_COMPLAINT_STATUSES,
    Complaint,
    ComplaintUpdate,
    complaint_reference,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_bool,
)

_FIELDS = (
    "raised_by", "raised_role", "apprentice_id", "employer_id", "category", "subject",
    "description", "received_at", "status", "handler", "acknowledged_at", "ack_due_on",
    "response_due_on", "outcome", "closed_at", "escalated_to", "satisfied",
)

_SELECT = """
    SELECT c.*,
           (a.given_name || ' ' || a.family_name) AS apprentice_name,
           e.name AS employer_name
      FROM complaints c
      LEFT JOIN apprentices a ON a.apprentice_id = c.apprentice_id
      LEFT JOIN employers   e ON e.employer_id   = c.employer_id
"""

# Literal SQL built from a constant, never from input.
_OPEN_SQL = "(" + ", ".join(f"'{s}'" for s in sorted(OPEN_COMPLAINT_STATUSES)) + ")"


def _map(row: Any) -> Complaint:
    satisfied = col(row, "satisfied")
    return Complaint(
        complaint_id=row["complaint_id"],
        reference=col(row, "reference") or complaint_reference(row["complaint_id"]),
        raised_by=row["raised_by"],
        raised_role=row["raised_role"],
        category=row["category"],
        subject=row["subject"],
        description=row["description"],
        received_at=row["received_at"],
        ack_due_on=row["ack_due_on"],
        response_due_on=row["response_due_on"],
        status=col(row, "status", "Received"),
        apprentice_id=col(row, "apprentice_id"),
        employer_id=col(row, "employer_id"),
        handler=col(row, "handler"),
        acknowledged_at=col(row, "acknowledged_at"),
        outcome=col(row, "outcome"),
        closed_at=col(row, "closed_at"),
        escalated_to=col(row, "escalated_to"),
        satisfied=None if satisfied is None else to_bool(satisfied),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
        apprentice_name=col(row, "apprentice_name"),
        employer_name=col(row, "employer_name"),
    )


def _map_update(row: Any) -> ComplaintUpdate:
    return ComplaintUpdate(
        update_id=row["update_id"],
        complaint_id=row["complaint_id"],
        note=row["note"],
        author=row["author"],
        author_role=row["author_role"],
        visible_to_complainant=to_bool(col(row, "visible_to_complainant")),
        created_at=col(row, "created_at", ""),
    )


# ── Complaints ──────────────────────────────────────────────────────

def list_complaints(
    *,
    status: str | None = None,
    statuses: list[str] | None = None,
    raised_by: str | None = None,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    handler: str | None = None,
    category: str | None = None,
    open_only: bool = False,
    ack_overdue_on: str | None = None,
    response_overdue_on: str | None = None,
    overdue_on: str | None = None,
    due_before: str | None = None,
    limit: int | None = None,
) -> list[Complaint]:
    """Complaints matching every filter given; open ones first, soonest due first.

    The ``*_on`` filters take today's date: ``ack_overdue_on`` finds
    complaints still unacknowledged past their acknowledgement date,
    ``response_overdue_on`` open ones past their response date, and
    ``overdue_on`` either. ``due_before`` finds open complaints whose
    response falls due on or before a date.
    """
    init_db()
    qb = QueryBuilder()
    qb.add_if(status, "c.status = ?", status)
    qb.add_in("c.status", statuses)
    qb.add_if(raised_by, "LOWER(c.raised_by) = LOWER(?)", raised_by)
    qb.add_if(apprentice_id, "c.apprentice_id = ?", apprentice_id)
    qb.add_if(employer_id, "c.employer_id = ?", employer_id)
    qb.add_if(handler, "LOWER(c.handler) = LOWER(?)", handler)
    qb.add_if(category, "c.category = ?", category)
    qb.add_if(open_only, f"c.status IN {_OPEN_SQL}")
    qb.add_if(ack_overdue_on, "c.status = 'Received' AND c.ack_due_on < ?", ack_overdue_on)
    qb.add_if(
        response_overdue_on,
        f"c.status IN {_OPEN_SQL} AND c.response_due_on < ?", response_overdue_on,
    )
    qb.add_if(
        overdue_on,
        f"((c.status = 'Received' AND c.ack_due_on < ?) "
        f"OR (c.status IN {_OPEN_SQL} AND c.response_due_on < ?))",
        overdue_on, overdue_on,
    )
    qb.add_if(due_before, f"c.status IN {_OPEN_SQL} AND c.response_due_on <= ?", due_before)
    sql = (
        f"{_SELECT} {qb.where} "
        f"ORDER BY CASE WHEN c.status IN {_OPEN_SQL} THEN 0 ELSE 1 END, "
        "c.response_due_on, c.complaint_id"
    )
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_map(r) for r in rows]


def get(complaint_id: int) -> Complaint | None:
    init_db()
    with connect() as conn:
        row = conn.execute(f"{_SELECT} WHERE c.complaint_id = ?", (complaint_id,)).fetchone()
    return _map(row) if row else None


def create(payload: dict[str, Any], *, first_note: str | None = None) -> int:
    """Insert a complaint, stamp its reference, and open its record.

    One transaction, so there is never a complaint without a reference
    or a record that starts partway through.
    """
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO complaints ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        complaint_id = int(cur.lastrowid)
        conn.execute(
            "UPDATE complaints SET reference = ? WHERE complaint_id = ?",
            (complaint_reference(complaint_id), complaint_id),
        )
        if first_note:
            conn.execute(
                """INSERT INTO complaint_updates
                       (complaint_id, note, author, author_role, visible_to_complainant)
                   VALUES (?, ?, ?, ?, 1)""",
                (complaint_id, first_note, payload["raised_by"], payload["raised_role"]),
            )
        return complaint_id


def update(
    complaint_id: int,
    payload: dict[str, Any],
    *,
    note: str | None = None,
    author: str | None = None,
    author_role: str | None = None,
    visible: bool = True,
) -> None:
    """Update the supplied fields and, optionally, log why — together."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    with connect() as conn:
        if columns:
            assignments = ", ".join(f"{c} = ?" for c in columns)
            conn.execute(
                f"UPDATE complaints SET {assignments}, updated_at = datetime('now') "
                "WHERE complaint_id = ?",
                [*(payload[c] for c in columns), complaint_id],
            )
        if note:
            conn.execute(
                """INSERT INTO complaint_updates
                       (complaint_id, note, author, author_role, visible_to_complainant)
                   VALUES (?, ?, ?, ?, ?)""",
                (complaint_id, note, author or "", author_role or "", 1 if visible else 0),
            )


def count_by_status() -> dict[str, int]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM complaints GROUP BY status"
        ).fetchall()
    return {r["status"]: int(r["n"]) for r in rows}


# ── Updates ─────────────────────────────────────────────────────────

def add_update(
    complaint_id: int, *, note: str, author: str, author_role: str, visible: bool
) -> int:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO complaint_updates
                   (complaint_id, note, author, author_role, visible_to_complainant)
               VALUES (?, ?, ?, ?, ?)""",
            (complaint_id, note, author, author_role, 1 if visible else 0),
        )
        return int(cur.lastrowid)


def list_updates(complaint_id: int, *, visible_only: bool = False) -> list[ComplaintUpdate]:
    """Oldest first: a record reads top to bottom."""
    init_db()
    qb = QueryBuilder()
    qb.add("complaint_id = ?", complaint_id)
    qb.add_if(visible_only, "visible_to_complainant = 1")
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM complaint_updates {qb.where} ORDER BY created_at, update_id",
            qb.args,
        ).fetchall()
    return [_map_update(r) for r in rows]
