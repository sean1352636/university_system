"""Welfare concerns and their case notes.

Restricted data. This layer does not know that — it runs whatever query
it is asked — which is why nothing but ``welfare_service`` imports it.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.learner_support.welfare import (
    WelfareConcern,
    WelfareNote,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
)

_FIELDS = (
    "apprentice_id", "category", "severity", "description", "status", "raised_by",
    "assigned_to", "escalated_to", "escalated_at", "closed_at", "outcome",
)

_SELECT = """
    SELECT w.*,
           (a.given_name || ' ' || a.family_name) AS apprentice_name,
           s.full_name AS assigned_name
      FROM welfare_concerns w
      JOIN apprentices a ON a.apprentice_id = w.apprentice_id
      LEFT JOIN staff  s ON s.staff_id      = w.assigned_to
"""


def _map(row: Any) -> WelfareConcern:
    return WelfareConcern(
        concern_id=row["concern_id"],
        apprentice_id=row["apprentice_id"],
        category=row["category"],
        severity=row["severity"],
        description=row["description"],
        status=col(row, "status", "Open"),
        raised_by=col(row, "raised_by", ""),
        raised_at=col(row, "raised_at", ""),
        assigned_to=col(row, "assigned_to"),
        escalated_to=col(row, "escalated_to"),
        escalated_at=col(row, "escalated_at"),
        closed_at=col(row, "closed_at"),
        outcome=col(row, "outcome"),
        updated_at=col(row, "updated_at", ""),
        apprentice_name=col(row, "apprentice_name", "") or "",
        assigned_name=col(row, "assigned_name"),
    )


def _map_note(row: Any) -> WelfareNote:
    return WelfareNote(
        note_id=row["note_id"],
        concern_id=row["concern_id"],
        author=row["author"],
        author_role=row["author_role"],
        note=row["note"],
        created_at=col(row, "created_at", ""),
    )


# ── Concerns ────────────────────────────────────────────────────────

def list_concerns(
    *,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    tutor_id: int | None = None,
    assigned_to: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    open_only: bool = False,
    severity: str | None = None,
    category: str | None = None,
    raised_since: str | None = None,
) -> list[WelfareConcern]:
    """Live concerns first, most severe first, newest first within that."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "w.apprentice_id = ?", apprentice_id)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(assigned_to, "w.assigned_to = ?", assigned_to)
    qb.add_if(status, "w.status = ?", status)
    qb.add_in("w.status", statuses)
    qb.add_if(open_only, "w.status <> 'Closed'")
    qb.add_if(severity, "w.severity = ?", severity)
    qb.add_if(category, "w.category = ?", category)
    qb.add_if(raised_since, "w.raised_at >= ?", raised_since)
    with connect() as conn:
        rows = conn.execute(
            f"""{_SELECT} {qb.where}
                 ORDER BY CASE WHEN w.status = 'Closed' THEN 1 ELSE 0 END,
                          CASE w.severity WHEN 'Critical' THEN 0 WHEN 'High' THEN 1
                                          WHEN 'Medium' THEN 2 ELSE 3 END,
                          w.raised_at DESC, w.concern_id DESC""",
            qb.args,
        ).fetchall()
    return [_map(r) for r in rows]


def get_concern(concern_id: int, *, with_notes: bool = False) -> WelfareConcern | None:
    init_db()
    with connect() as conn:
        row = conn.execute(f"{_SELECT} WHERE w.concern_id = ?", (concern_id,)).fetchone()
        if row is None:
            return None
        concern = _map(row)
        if with_notes:
            concern.notes = [
                _map_note(r) for r in conn.execute(
                    "SELECT * FROM welfare_notes WHERE concern_id = ? "
                    "ORDER BY created_at, note_id",
                    (concern_id,),
                ).fetchall()
            ]
    return concern


def create_concern(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO welfare_concerns ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update_concern(
    concern_id: int,
    payload: dict[str, Any],
    *,
    note: dict[str, str] | None = None,
) -> None:
    """Update the supplied fields and, optionally, add a case note — together.

    A status change and the note recording it are one transaction, so the
    case history can never show a concern closed with no note saying so.
    *note* carries ``author``, ``author_role`` and ``note``.
    """
    init_db()
    columns = [f for f in _FIELDS if f in payload and f not in ("apprentice_id", "raised_by")]
    with connect() as conn:
        if columns:
            assignments = ", ".join(f"{c} = ?" for c in columns)
            conn.execute(
                f"UPDATE welfare_concerns SET {assignments}, updated_at = datetime('now') "
                "WHERE concern_id = ?",
                [*(payload[c] for c in columns), concern_id],
            )
        if note:
            _insert_note(conn, concern_id, note)


# ── Case notes ──────────────────────────────────────────────────────

def add_note(concern_id: int, *, author: str, author_role: str, note: str) -> int:
    init_db()
    with connect() as conn:
        conn.execute(
            "UPDATE welfare_concerns SET updated_at = datetime('now') WHERE concern_id = ?",
            (concern_id,),
        )
        return _insert_note(
            conn, concern_id, {"author": author, "author_role": author_role, "note": note}
        )


def list_notes(concern_id: int) -> list[WelfareNote]:
    """Oldest first, so a case reads in the order it happened."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM welfare_notes WHERE concern_id = ? ORDER BY created_at, note_id",
            (concern_id,),
        ).fetchall()
    return [_map_note(r) for r in rows]


def _insert_note(conn: Any, concern_id: int, note: dict[str, str]) -> int:
    cur = conn.execute(
        "INSERT INTO welfare_notes (concern_id, author, author_role, note) VALUES (?, ?, ?, ?)",
        (concern_id, note["author"], note["author_role"], note["note"]),
    )
    return int(cur.lastrowid)
