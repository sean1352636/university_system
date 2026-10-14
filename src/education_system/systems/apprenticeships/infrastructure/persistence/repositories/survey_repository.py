"""Surveys, their responses, and the counts behind a response rate.

Anonymity is enforced here as well as in the service: the query that
feeds the results (:func:`list_answers`) does not select the
respondent, so no screen built on it can show a name by accident.
"""

from __future__ import annotations

import json
from typing import Any

from education_system.systems.apprenticeships.domain.quality.surveys import Survey
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_int,
)

_FIELDS = ("title", "audience", "kind", "status", "opens_on", "closes_on", "created_by")


def _map(row: Any) -> Survey:
    return Survey(
        survey_id=row["survey_id"],
        title=row["title"],
        audience=row["audience"],
        kind=row["kind"],
        status=col(row, "status", "Draft"),
        opens_on=col(row, "opens_on"),
        closes_on=col(row, "closes_on"),
        created_by=col(row, "created_by"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


# ── Surveys ─────────────────────────────────────────────────────────

def list_surveys(
    *,
    status: str | None = None,
    statuses: list[str] | None = None,
    audience: str | None = None,
    kind: str | None = None,
    open_on: str | None = None,
    closes_before: str | None = None,
) -> list[Survey]:
    """Surveys matching every filter; newest first.

    ``open_on`` finds surveys that are Open and accepting on that date;
    ``closes_before`` finds Open surveys closing on or before it.
    """
    init_db()
    qb = QueryBuilder()
    qb.add_if(status, "status = ?", status)
    qb.add_in("status", statuses)
    qb.add_if(audience, "audience = ?", audience)
    qb.add_if(kind, "kind = ?", kind)
    qb.add_if(
        open_on,
        "status = 'Open' AND (opens_on IS NULL OR opens_on <= ?) "
        "AND (closes_on IS NULL OR closes_on >= ?)",
        open_on, open_on,
    )
    qb.add_if(
        closes_before, "status = 'Open' AND closes_on IS NOT NULL AND closes_on <= ?",
        closes_before,
    )
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM surveys {qb.where} ORDER BY created_at DESC, survey_id DESC",
            qb.args,
        ).fetchall()
    return [_map(r) for r in rows]


def get(survey_id: int) -> Survey | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM surveys WHERE survey_id = ?", (survey_id,)).fetchone()
    return _map(row) if row else None


def create(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO surveys ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update(survey_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE surveys SET {assignments}, updated_at = datetime('now') "
            "WHERE survey_id = ?",
            [*(payload[c] for c in columns), survey_id],
        )


# ── Responses ───────────────────────────────────────────────────────

def add_response(
    *,
    survey_id: int,
    respondent: str,
    respondent_role: str,
    apprentice_id: int | None,
    employer_id: int | None,
    answers: dict[str, int],
    comment: str | None,
) -> int:
    """Store one response. A second from the same login raises IntegrityError."""
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO survey_responses
                   (survey_id, respondent, respondent_role, apprentice_id, employer_id,
                    answers, comment)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (survey_id, respondent, respondent_role, apprentice_id, employer_id,
             json.dumps(answers), comment),
        )
        return int(cur.lastrowid)


def has_responded(survey_id: int, respondent: str) -> bool:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM survey_responses WHERE survey_id = ? AND LOWER(respondent) = LOWER(?)",
            (survey_id, respondent),
        ).fetchone()
    return row is not None


def responded_survey_ids(respondent: str) -> set[int]:
    """Every survey this login has answered, for marking a list in one query."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT survey_id FROM survey_responses WHERE LOWER(respondent) = LOWER(?)",
            (respondent,),
        ).fetchall()
    return {int(r["survey_id"]) for r in rows}


def list_answers(survey_id: int) -> list[tuple[dict[str, int], str | None]]:
    """``(answers, comment)`` for every response — and deliberately nothing else."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT answers, comment FROM survey_responses WHERE survey_id = ?", (survey_id,)
        ).fetchall()
    out: list[tuple[dict[str, int], str | None]] = []
    for row in rows:
        try:
            raw = json.loads(row["answers"] or "{}")
        except (TypeError, ValueError):
            raw = {}
        answers = {str(k): to_int(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
        out.append((answers, row["comment"]))
    return out


def responded_count(survey_id: int, *, by: str) -> int:
    """Distinct apprentices (``by="apprentice"``) or employers who answered.

    Counted by record rather than by login, so two managers at one
    employer both answering do not push the rate past 100%.
    """
    column = {"apprentice": "apprentice_id", "employer": "employer_id"}[by]
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"SELECT COUNT(DISTINCT {column}) AS n FROM survey_responses "
            f"WHERE survey_id = ? AND {column} IS NOT NULL",
            (survey_id,),
        ).fetchone()
    return to_int(row["n"])


def response_count(survey_id: int) -> int:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM survey_responses WHERE survey_id = ?", (survey_id,)
        ).fetchone()
    return to_int(row["n"])


# ── The eligible audience ───────────────────────────────────────────

def count_apprentices(statuses: list[str] | tuple[str, ...] | frozenset[str]) -> int:
    init_db()
    qb = QueryBuilder()
    qb.add_in("status", sorted(statuses))
    with connect() as conn:
        row = conn.execute(f"SELECT COUNT(*) AS n FROM apprentices {qb.where}", qb.args).fetchone()
    return to_int(row["n"])


def count_employers_with_apprentices(
    statuses: list[str] | tuple[str, ...] | frozenset[str],
) -> int:
    """Employers with at least one apprentice in *statuses*.

    An employer survey is about the apprentices they have, so an
    organisation with nobody on programme is not part of its audience.
    """
    init_db()
    qb = QueryBuilder()
    qb.add("employer_id IS NOT NULL")
    qb.add_in("status", sorted(statuses))
    with connect() as conn:
        row = conn.execute(
            f"SELECT COUNT(DISTINCT employer_id) AS n FROM apprentices {qb.where}", qb.args
        ).fetchone()
    return to_int(row["n"])
