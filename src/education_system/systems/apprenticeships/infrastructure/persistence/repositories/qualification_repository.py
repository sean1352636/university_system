"""Qualifications held, in progress and achieved."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.learner_support.qualifications import (
    Qualification,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_bool,
)

_FIELDS = (
    "apprentice_id", "title", "level", "awarding_body", "reference", "status", "grade",
    "start_date", "achieved_date", "certificate_ref", "relevant_prior_learning", "notes",
    "recorded_by",
)


def _map(row: Any) -> Qualification:
    return Qualification(
        qualification_id=row["qualification_id"],
        apprentice_id=row["apprentice_id"],
        title=row["title"],
        level=col(row, "level"),
        awarding_body=col(row, "awarding_body"),
        reference=col(row, "reference"),
        status=col(row, "status", "In progress"),
        grade=col(row, "grade"),
        start_date=col(row, "start_date"),
        achieved_date=col(row, "achieved_date"),
        certificate_ref=col(row, "certificate_ref"),
        relevant_prior_learning=to_bool(col(row, "relevant_prior_learning")),
        notes=col(row, "notes"),
        recorded_by=col(row, "recorded_by"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def list_qualifications(
    *,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    tutor_id: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    relevant_prior_learning: bool | None = None,
    awaiting_certificate: bool = False,
) -> list[Qualification]:
    """In progress first, then achieved and prior, most recent first within each."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "q.apprentice_id = ?", apprentice_id)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(status, "q.status = ?", status)
    qb.add_in("q.status", statuses)
    if relevant_prior_learning is not None:
        qb.add("q.relevant_prior_learning = ?", 1 if relevant_prior_learning else 0)
    if awaiting_certificate:
        qb.add("q.status = 'Achieved' AND COALESCE(q.certificate_ref, '') = ''")
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT q.* FROM qualifications q
                  JOIN apprentices a ON a.apprentice_id = q.apprentice_id
                  {qb.where}
                 ORDER BY CASE q.status WHEN 'In progress' THEN 0
                                        WHEN 'Achieved' THEN 1 ELSE 2 END,
                          COALESCE(q.achieved_date, q.start_date, q.created_at) DESC,
                          q.qualification_id DESC""",
            qb.args,
        ).fetchall()
    return [_map(r) for r in rows]


def get_qualification(qualification_id: int) -> Qualification | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM qualifications WHERE qualification_id = ?", (qualification_id,)
        ).fetchone()
    return _map(row) if row else None


def create_qualification(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO qualifications ({', '.join(columns)}) VALUES ({placeholders})",
            [_value(c, payload[c]) for c in columns],
        )
        return int(cur.lastrowid)


def update_qualification(qualification_id: int, payload: dict[str, Any]) -> None:
    """Update the supplied fields only; anything absent is untouched."""
    init_db()
    columns = [f for f in _FIELDS if f in payload and f != "apprentice_id"]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE qualifications SET {assignments}, updated_at = datetime('now') "
            "WHERE qualification_id = ?",
            [*(_value(c, payload[c]) for c in columns), qualification_id],
        )


def delete_qualification(qualification_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            "DELETE FROM qualifications WHERE qualification_id = ?", (qualification_id,)
        )


def _value(column: str, value: Any) -> Any:
    if column == "relevant_prior_learning":
        return 1 if value else 0
    return value
