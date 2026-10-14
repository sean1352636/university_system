"""Individual learning plans: objectives and the comments on them.

The activities under an objective are training plan items and live in
``training_repository``.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.training.learning_plan import (
    LearningObjective,
    PlanComment,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_int,
)

_OBJECTIVE_FIELDS = (
    "apprentice_id", "title", "description", "ksb_codes", "target_date",
    "status", "progress", "achieved_at", "created_by",
)


def _map_objective(row: Any) -> LearningObjective:
    return LearningObjective(
        objective_id=row["objective_id"],
        apprentice_id=row["apprentice_id"],
        title=row["title"],
        description=col(row, "description"),
        ksb_codes=col(row, "ksb_codes"),
        target_date=col(row, "target_date"),
        status=col(row, "status", "Not started"),
        progress=to_int(col(row, "progress")),
        achieved_at=col(row, "achieved_at"),
        created_by=col(row, "created_by"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def _map_comment(row: Any) -> PlanComment:
    progress = col(row, "progress")
    return PlanComment(
        comment_id=row["comment_id"],
        apprentice_id=row["apprentice_id"],
        author=row["author"],
        author_role=row["author_role"],
        body=row["body"],
        objective_id=col(row, "objective_id"),
        progress=None if progress is None else to_int(progress),
        created_at=col(row, "created_at", ""),
    )


# ── Objectives ──────────────────────────────────────────────────────

def list_objectives(apprentice_id: int) -> list[LearningObjective]:
    """Open objectives first, soonest target first; finished ones last."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """SELECT * FROM ilp_objectives
                WHERE apprentice_id = ?
                ORDER BY CASE WHEN status IN ('Achieved', 'Withdrawn') THEN 1 ELSE 0 END,
                         COALESCE(target_date, '9999-12-31'), objective_id""",
            (apprentice_id,),
        ).fetchall()
    return [_map_objective(r) for r in rows]


def get_objective(objective_id: int) -> LearningObjective | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ilp_objectives WHERE objective_id = ?", (objective_id,)
        ).fetchone()
    return _map_objective(row) if row else None


def create_objective(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _OBJECTIVE_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO ilp_objectives ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update_objective(objective_id: int, payload: dict[str, Any]) -> None:
    """Update the supplied fields only; anything absent is untouched."""
    init_db()
    columns = [f for f in _OBJECTIVE_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE ilp_objectives SET {assignments}, updated_at = datetime('now') "
            "WHERE objective_id = ?",
            [*(payload[c] for c in columns), objective_id],
        )


def delete_objective(objective_id: int) -> None:
    """Remove an objective. Its activities and comments stay on the plan."""
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM ilp_objectives WHERE objective_id = ?", (objective_id,))


def record_progress(
    objective_id: int,
    *,
    status: str,
    progress: int,
    achieved_at: str | None,
    apprentice_id: int,
    author: str,
    author_role: str,
    body: str,
) -> int:
    """Move an objective's progress and log the move as a comment, together.

    One transaction, so the objective's figure and the history explaining
    it cannot disagree.
    """
    init_db()
    with connect() as conn:
        conn.execute(
            """UPDATE ilp_objectives
                  SET status = ?, progress = ?, achieved_at = ?, updated_at = datetime('now')
                WHERE objective_id = ?""",
            (status, progress, achieved_at, objective_id),
        )
        cur = conn.execute(
            """INSERT INTO ilp_comments
                   (apprentice_id, objective_id, author, author_role, body, progress)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (apprentice_id, objective_id, author, author_role, body, progress),
        )
        return int(cur.lastrowid)


# ── Comments ────────────────────────────────────────────────────────

def list_comments(
    apprentice_id: int, *, objective_id: int | None = None, limit: int | None = None
) -> list[PlanComment]:
    """Newest first."""
    init_db()
    qb = QueryBuilder()
    qb.add("apprentice_id = ?", apprentice_id)
    qb.add_if(objective_id, "objective_id = ?", objective_id)
    sql = f"SELECT * FROM ilp_comments {qb.where} ORDER BY created_at DESC, comment_id DESC"
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_map_comment(r) for r in rows]


def add_comment(
    *,
    apprentice_id: int,
    author: str,
    author_role: str,
    body: str,
    objective_id: int | None = None,
) -> int:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO ilp_comments (apprentice_id, objective_id, author, author_role, body)
               VALUES (?, ?, ?, ?, ?)""",
            (apprentice_id, objective_id, author, author_role, body),
        )
        return int(cur.lastrowid)


def get_comment(comment_id: int) -> PlanComment | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ilp_comments WHERE comment_id = ?", (comment_id,)
        ).fetchone()
    return _map_comment(row) if row else None
