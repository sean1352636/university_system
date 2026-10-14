"""Appeals.

``types`` and ``exclude_types`` are how the service keeps EPA-result
appeals away from the provider: the routing rule becomes part of the
query, so the rows the provider must not see are never read at all.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.quality.appeals import (
    OPEN_APPEAL_STATUSES,
    Appeal,
    appeal_reference,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
)

_FIELDS = (
    "apprentice_id", "raised_by", "appeal_type", "decision_ref_id", "decision_ref",
    "decision_date", "grounds", "lodged_at", "deadline", "status", "decided_by",
    "decided_at", "decision",
)

_SELECT = """
    SELECT p.*,
           (a.given_name || ' ' || a.family_name) AS apprentice_name
      FROM appeals p
      JOIN apprentices a ON a.apprentice_id = p.apprentice_id
"""

# Literal SQL built from a constant, never from input.
_OPEN_SQL = "(" + ", ".join(f"'{s}'" for s in sorted(OPEN_APPEAL_STATUSES)) + ")"


def _map(row: Any) -> Appeal:
    return Appeal(
        appeal_id=row["appeal_id"],
        reference=col(row, "reference") or appeal_reference(row["appeal_id"]),
        apprentice_id=row["apprentice_id"],
        raised_by=row["raised_by"],
        appeal_type=row["appeal_type"],
        decision_date=row["decision_date"],
        grounds=row["grounds"],
        lodged_at=row["lodged_at"],
        deadline=row["deadline"],
        status=col(row, "status", "Lodged"),
        decision_ref_id=col(row, "decision_ref_id"),
        decision_ref=col(row, "decision_ref"),
        decided_by=col(row, "decided_by"),
        decided_at=col(row, "decided_at"),
        decision=col(row, "decision"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
        apprentice_name=col(row, "apprentice_name"),
    )


def list_appeals(
    *,
    status: str | None = None,
    statuses: list[str] | None = None,
    apprentice_id: int | None = None,
    raised_by: str | None = None,
    appeal_type: str | None = None,
    types: list[str] | tuple[str, ...] | None = None,
    exclude_types: list[str] | tuple[str, ...] | None = None,
    decision_ref_id: int | None = None,
    open_only: bool = False,
    overdue_on: str | None = None,
    due_before: str | None = None,
    limit: int | None = None,
) -> list[Appeal]:
    """Appeals matching every filter given; open ones first, soonest deadline first.

    ``overdue_on`` takes today's date and finds open appeals past their
    deadline; ``due_before`` finds open ones due on or before a date.
    """
    init_db()
    qb = QueryBuilder()
    qb.add_if(status, "p.status = ?", status)
    qb.add_in("p.status", statuses)
    qb.add_if(apprentice_id, "p.apprentice_id = ?", apprentice_id)
    qb.add_if(raised_by, "LOWER(p.raised_by) = LOWER(?)", raised_by)
    qb.add_if(appeal_type, "p.appeal_type = ?", appeal_type)
    qb.add_in("p.appeal_type", types)
    if exclude_types:
        placeholders = ", ".join("?" for _ in exclude_types)
        qb.add(f"p.appeal_type NOT IN ({placeholders})", *exclude_types)
    qb.add_if(decision_ref_id, "p.decision_ref_id = ?", decision_ref_id)
    qb.add_if(open_only, f"p.status IN {_OPEN_SQL}")
    qb.add_if(overdue_on, f"p.status IN {_OPEN_SQL} AND p.deadline < ?", overdue_on)
    qb.add_if(due_before, f"p.status IN {_OPEN_SQL} AND p.deadline <= ?", due_before)
    sql = (
        f"{_SELECT} {qb.where} "
        f"ORDER BY CASE WHEN p.status IN {_OPEN_SQL} THEN 0 ELSE 1 END, "
        "p.deadline, p.appeal_id"
    )
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_map(r) for r in rows]


def get(appeal_id: int) -> Appeal | None:
    init_db()
    with connect() as conn:
        row = conn.execute(f"{_SELECT} WHERE p.appeal_id = ?", (appeal_id,)).fetchone()
    return _map(row) if row else None


def create(payload: dict[str, Any]) -> int:
    """Insert an appeal and stamp its reference in the same transaction."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO appeals ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        appeal_id = int(cur.lastrowid)
        conn.execute(
            "UPDATE appeals SET reference = ? WHERE appeal_id = ?",
            (appeal_reference(appeal_id), appeal_id),
        )
        return appeal_id


def update(appeal_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE appeals SET {assignments}, updated_at = datetime('now') "
            "WHERE appeal_id = ?",
            [*(payload[c] for c in columns), appeal_id],
        )


def count_by_status(*, exclude_types: list[str] | tuple[str, ...] | None = None) -> dict[str, int]:
    init_db()
    qb = QueryBuilder()
    if exclude_types:
        placeholders = ", ".join("?" for _ in exclude_types)
        qb.add(f"appeal_type NOT IN ({placeholders})", *exclude_types)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT status, COUNT(*) AS n FROM appeals {qb.where} GROUP BY status", qb.args
        ).fetchall()
    return {r["status"]: int(r["n"]) for r in rows}
