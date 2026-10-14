"""Initial and diagnostic skills assessments.

The current English and Maths position is compliance's
``functional_skills`` table, read through ``compliance_repository``.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.learner_support.skills_assessments import (
    SkillsAssessment,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
)

_FIELDS = (
    "apprentice_id", "subject", "kind", "assessed_on", "level", "score", "notes",
    "assessed_by",
)


def _map(row: Any) -> SkillsAssessment:
    score = col(row, "score")
    return SkillsAssessment(
        assessment_id=row["assessment_id"],
        apprentice_id=row["apprentice_id"],
        subject=row["subject"],
        kind=row["kind"],
        assessed_on=row["assessed_on"],
        level=col(row, "level"),
        score=None if score is None else float(score),
        notes=col(row, "notes"),
        assessed_by=col(row, "assessed_by"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def list_assessments(
    *,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    tutor_id: int | None = None,
    subject: str | None = None,
    kind: str | None = None,
    assessed_from: str | None = None,
    assessed_to: str | None = None,
    limit: int | None = None,
) -> list[SkillsAssessment]:
    """Newest first. The scope filters join through the apprentice."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "s.apprentice_id = ?", apprentice_id)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(subject, "s.subject = ?", subject)
    qb.add_if(kind, "s.kind = ?", kind)
    qb.add_if(assessed_from, "s.assessed_on >= ?", assessed_from)
    qb.add_if(assessed_to, "s.assessed_on <= ?", assessed_to)
    sql = (
        "SELECT s.* FROM skills_assessments s "
        "JOIN apprentices a ON a.apprentice_id = s.apprentice_id "
        f"{qb.where} ORDER BY s.assessed_on DESC, s.assessment_id DESC"
    )
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_map(r) for r in rows]


def get_assessment(assessment_id: int) -> SkillsAssessment | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM skills_assessments WHERE assessment_id = ?", (assessment_id,)
        ).fetchone()
    return _map(row) if row else None


def create_assessment(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO skills_assessments ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update_assessment(assessment_id: int, payload: dict[str, Any]) -> None:
    """Update the supplied fields only; anything absent is untouched."""
    init_db()
    columns = [f for f in _FIELDS if f in payload and f != "apprentice_id"]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE skills_assessments SET {assignments}, updated_at = datetime('now') "
            "WHERE assessment_id = ?",
            [*(payload[c] for c in columns), assessment_id],
        )


def delete_assessment(assessment_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM skills_assessments WHERE assessment_id = ?", (assessment_id,))
