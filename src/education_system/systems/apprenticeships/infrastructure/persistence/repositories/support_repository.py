"""Reasonable adjustments, support arrangements and their history."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from education_system.systems.apprenticeships.domain.learner_support.support_arrangements import (
    SupportArrangement,
    SupportNote,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_bool,
)

_FIELDS = (
    "apprentice_id", "need_category", "adjustment", "arrangements", "responsible_staff_id",
    "review_date", "status", "share_with_employer", "created_by",
)

_SELECT = """
    SELECT sa.*,
           (a.given_name || ' ' || a.family_name) AS apprentice_name,
           s.full_name AS responsible_staff_name
      FROM support_arrangements sa
      JOIN apprentices a ON a.apprentice_id = sa.apprentice_id
      LEFT JOIN staff  s ON s.staff_id      = sa.responsible_staff_id
"""


def _map(row: Any) -> SupportArrangement:
    return SupportArrangement(
        arrangement_id=row["arrangement_id"],
        apprentice_id=row["apprentice_id"],
        need_category=row["need_category"],
        adjustment=row["adjustment"],
        arrangements=col(row, "arrangements"),
        responsible_staff_id=col(row, "responsible_staff_id"),
        review_date=col(row, "review_date"),
        status=col(row, "status", "Active"),
        share_with_employer=to_bool(col(row, "share_with_employer")),
        created_by=col(row, "created_by"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
        apprentice_name=col(row, "apprentice_name", "") or "",
        responsible_staff_name=col(row, "responsible_staff_name"),
    )


def _map_note(row: Any) -> SupportNote:
    return SupportNote(
        note_id=row["note_id"],
        arrangement_id=row["arrangement_id"],
        author=row["author"],
        author_role=row["author_role"],
        body=row["body"],
        created_at=col(row, "created_at", ""),
    )


# ── Arrangements ────────────────────────────────────────────────────

def list_arrangements(
    *,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    tutor_id: int | None = None,
    responsible_staff_id: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    in_force_only: bool = False,
    shared_only: bool = False,
    review_due_by: str | None = None,
    overdue_as_of: str | None = None,
) -> list[SupportArrangement]:
    """Arrangements matching the filters, soonest review first; ended ones last.

    ``review_due_by`` finds arrangements in force whose review falls on
    or before a date; ``overdue_as_of`` those whose review date is
    already before it. The caller passes the date rather than the query
    reading ``date('now')``, so "today" means the same thing to the
    service, its tests and whatever builds a calendar from this later.
    """
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "sa.apprentice_id = ?", apprentice_id)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(responsible_staff_id, "sa.responsible_staff_id = ?", responsible_staff_id)
    qb.add_if(status, "sa.status = ?", status)
    qb.add_in("sa.status", statuses)
    qb.add_if(in_force_only, "sa.status <> 'Ended'")
    qb.add_if(shared_only, "sa.share_with_employer = 1")
    if review_due_by:
        qb.add("sa.status <> 'Ended' AND sa.review_date IS NOT NULL AND sa.review_date <= ?",
               review_due_by)
    if overdue_as_of:
        qb.add("sa.status <> 'Ended' AND sa.review_date IS NOT NULL AND sa.review_date < ?",
               overdue_as_of)
    with connect() as conn:
        rows = conn.execute(
            f"""{_SELECT} {qb.where}
                 ORDER BY CASE WHEN sa.status = 'Ended' THEN 1 ELSE 0 END,
                          COALESCE(sa.review_date, '9999-12-31'), sa.arrangement_id""",
            qb.args,
        ).fetchall()
    return [_map(r) for r in rows]


def get_arrangement(arrangement_id: int) -> SupportArrangement | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"{_SELECT} WHERE sa.arrangement_id = ?", (arrangement_id,)
        ).fetchone()
    return _map(row) if row else None


def create_arrangement(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO support_arrangements ({', '.join(columns)}) VALUES ({placeholders})",
            [_value(c, payload[c]) for c in columns],
        )
        return int(cur.lastrowid)


def update_arrangement(
    arrangement_id: int,
    payload: dict[str, Any],
    *,
    note: dict[str, str] | None = None,
) -> None:
    """Update the supplied fields and, optionally, log why — together.

    One transaction, so an arrangement's current state and the history
    explaining how it got there cannot disagree. *note* carries
    ``author``, ``author_role`` and ``body``.
    """
    init_db()
    columns = [f for f in _FIELDS if f in payload and f not in ("apprentice_id", "created_by")]
    with connect() as conn:
        if columns:
            assignments = ", ".join(f"{c} = ?" for c in columns)
            conn.execute(
                f"UPDATE support_arrangements SET {assignments}, updated_at = datetime('now') "
                "WHERE arrangement_id = ?",
                [*(_value(c, payload[c]) for c in columns), arrangement_id],
            )
        if note:
            _insert_note(conn, arrangement_id, note)


def delete_arrangement(arrangement_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            "DELETE FROM support_arrangements WHERE arrangement_id = ?", (arrangement_id,)
        )


# ── History ─────────────────────────────────────────────────────────

def add_note(arrangement_id: int, *, author: str, author_role: str, body: str) -> int:
    init_db()
    with connect() as conn:
        return _insert_note(
            conn, arrangement_id, {"author": author, "author_role": author_role, "body": body}
        )


def list_notes(arrangement_ids: Iterable[int]) -> dict[int, list[SupportNote]]:
    """Each arrangement's history, newest first — one query for many."""
    ids = sorted(set(arrangement_ids))
    if not ids:
        return {}
    init_db()
    qb = QueryBuilder()
    qb.add_in("arrangement_id", ids)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM support_notes {qb.where} ORDER BY created_at DESC, note_id DESC",
            qb.args,
        ).fetchall()
    grouped: dict[int, list[SupportNote]] = {i: [] for i in ids}
    for row in rows:
        grouped[row["arrangement_id"]].append(_map_note(row))
    return grouped


def _insert_note(conn: Any, arrangement_id: int, note: dict[str, str]) -> int:
    cur = conn.execute(
        "INSERT INTO support_notes (arrangement_id, author, author_role, body) "
        "VALUES (?, ?, ?, ?)",
        (arrangement_id, note["author"], note["author_role"], note["body"]),
    )
    return int(cur.lastrowid)


def _value(column: str, value: Any) -> Any:
    if column == "share_with_employer":
        return 1 if value else 0
    return value
