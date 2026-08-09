"""Portfolio evidence, its KSB mappings and the IQA verifications on it."""

from __future__ import annotations

import sqlite3
from typing import Any

from education_system.systems.apprenticeships.domain.portfolio.evidence import (
    Evidence,
    EvidenceMapping,
    PortfolioSummary,
    roll_up_coverage,
)
from education_system.systems.apprenticeships.domain.programmes.models import KSB, KSBCoverage
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_int,
)

# The apprentice join is unconditional: the foreign key is NOT NULL and
# cascades, so it can never drop a row, and one SQL shape beats two.
_EVIDENCE_SELECT = """
    SELECT e.*
      FROM portfolio_evidence e
      JOIN apprentices a ON a.apprentice_id = e.apprentice_id
"""

_MAPPING_SELECT = """
    SELECT m.*,
           k.code        AS ksb_code,
           k.ksb_type    AS ksb_type,
           k.description AS ksb_description
      FROM evidence_ksb_map m
      JOIN programme_ksbs k ON k.ksb_id = m.ksb_id
"""

# LENGTH before the code itself, so K10 sorts after K9 rather than
# between K1 and K2 the way a plain string sort would put it.
_MAPPING_ORDER = "ORDER BY k.ksb_type, LENGTH(k.code), k.code"

_EVIDENCE_FIELDS = (
    "apprentice_id", "title", "evidence_type", "description", "file_name",
    "status", "submitted_at", "assessor_id", "assessed_at", "feedback",
)


def _map_evidence(row: Any) -> Evidence:
    return Evidence(
        evidence_id=row["evidence_id"],
        apprentice_id=row["apprentice_id"],
        title=row["title"],
        evidence_type=col(row, "evidence_type", ""),
        description=col(row, "description"),
        file_name=col(row, "file_name"),
        status=col(row, "status", "Draft"),
        submitted_at=col(row, "submitted_at"),
        assessor_id=col(row, "assessor_id"),
        assessed_at=col(row, "assessed_at"),
        feedback=col(row, "feedback"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def _map_mapping(row: Any) -> EvidenceMapping:
    return EvidenceMapping(
        map_id=row["map_id"],
        evidence_id=row["evidence_id"],
        ksb_id=row["ksb_id"],
        coverage=col(row, "coverage", "Developing"),
        assessor_note=col(row, "assessor_note"),
        created_at=col(row, "created_at", ""),
        ksb_code=col(row, "ksb_code", ""),
        ksb_type=col(row, "ksb_type", ""),
        ksb_description=col(row, "ksb_description", ""),
    )


def _map_ksb(row: Any) -> KSB:
    return KSB(
        ksb_id=row["ksb_id"],
        programme_id=row["programme_id"],
        code=row["code"],
        ksb_type=col(row, "ksb_type", ""),
        description=col(row, "description", ""),
        duty_ref=col(row, "duty_ref"),
        created_at=col(row, "created_at", ""),
    )


def _mappings_by_evidence(
    conn: sqlite3.Connection, evidence_ids: list[int]
) -> dict[int, list[EvidenceMapping]]:
    """Every mapping for a batch of evidence, keyed by evidence id.

    One query for the whole page: mapping a portfolio item to a dozen
    KSBs is normal, so fetching them per item would turn one list screen
    into a hundred round trips.
    """
    if not evidence_ids:
        return {}
    placeholders = ", ".join("?" for _ in evidence_ids)
    rows = conn.execute(
        f"{_MAPPING_SELECT} WHERE m.evidence_id IN ({placeholders}) {_MAPPING_ORDER}",
        evidence_ids,
    ).fetchall()
    grouped: dict[int, list[EvidenceMapping]] = {}
    for row in rows:
        grouped.setdefault(row["evidence_id"], []).append(_map_mapping(row))
    return grouped


# ── Evidence ────────────────────────────────────────────────────────

def get_evidence(evidence_id: int, *, with_mappings: bool = True) -> Evidence | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"{_EVIDENCE_SELECT} WHERE e.evidence_id = ?", (evidence_id,)
        ).fetchone()
        if not row:
            return None
        evidence = _map_evidence(row)
        if with_mappings:
            evidence.mappings = _mappings_by_evidence(conn, [evidence.evidence_id]).get(
                evidence.evidence_id, []
            )
    return evidence


def list_evidence(
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    evidence_type: str | None = None,
    assessor_id: int | None = None,
    tutor_id: int | None = None,
    employer_id: int | None = None,
    with_mappings: bool = False,
    limit: int | None = None,
) -> list[Evidence]:
    """Portfolio list, filtered as the apprentice and assessor views need.

    ``tutor_id`` and ``employer_id`` scope through the apprentice, while
    ``assessor_id`` is the assessor named on the evidence itself — a
    tutor's caseload and an assessor's marking pile are different piles.
    """
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "e.apprentice_id = ?", apprentice_id)
    qb.add_if(status, "e.status = ?", status)
    qb.add_in("e.status", statuses)
    qb.add_if(evidence_type, "e.evidence_type = ?", evidence_type)
    qb.add_if(assessor_id, "e.assessor_id = ?", assessor_id)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    sql = f"{_EVIDENCE_SELECT} {qb.where} ORDER BY e.created_at DESC, e.evidence_id DESC"
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
        items = [_map_evidence(r) for r in rows]
        if with_mappings:
            grouped = _mappings_by_evidence(conn, [i.evidence_id for i in items])
            for item in items:
                item.mappings = grouped.get(item.evidence_id, [])
    return items


def create_evidence(payload: dict[str, Any]) -> int:
    """Insert a piece of evidence and return the new id."""
    init_db()
    columns = [f for f in _EVIDENCE_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO portfolio_evidence ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def update_evidence(evidence_id: int, payload: dict[str, Any]) -> None:
    """Update the supplied fields only; anything absent is untouched."""
    init_db()
    columns = [f for f in _EVIDENCE_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        conn.execute(
            f"UPDATE portfolio_evidence SET {assignments}, updated_at = datetime('now') "
            "WHERE evidence_id = ?",
            [*values, evidence_id],
        )


def delete_evidence(evidence_id: int) -> None:
    """Remove a piece of evidence, its KSB mappings and its verifications."""
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM portfolio_evidence WHERE evidence_id = ?", (evidence_id,))


def set_evidence_status(
    evidence_id: int,
    status: str,
    *,
    assessor_id: int | None = None,
    assessed_at: str | None = None,
    feedback: str | None = None,
    submitted_at: str | None = None,
) -> None:
    """Move a piece of evidence's status, writing only the stamps supplied.

    Omitted stamps keep their existing value, so resubmitting referred
    work does not erase who assessed it the first time.
    """
    init_db()
    assignments = ["status = ?"]
    values: list[Any] = [status]
    for column, value in (
        ("submitted_at", submitted_at),
        ("assessor_id", assessor_id),
        ("assessed_at", assessed_at),
        ("feedback", feedback),
    ):
        if value is not None:
            assignments.append(f"{column} = ?")
            values.append(value)
    with connect() as conn:
        conn.execute(
            f"UPDATE portfolio_evidence SET {', '.join(assignments)}, "
            "updated_at = datetime('now') WHERE evidence_id = ?",
            [*values, evidence_id],
        )


def pending_assessment_count(
    *, tutor_id: int | None = None, assessor_id: int | None = None
) -> int:
    """How much evidence is waiting to be assessed, for the queue badges."""
    init_db()
    qb = QueryBuilder()
    qb.add("e.status = 'Submitted'")
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(assessor_id, "e.assessor_id = ?", assessor_id)
    with connect() as conn:
        row = conn.execute(
            f"""SELECT COUNT(*) AS n
                  FROM portfolio_evidence e
                  JOIN apprentices a ON a.apprentice_id = e.apprentice_id
                  {qb.where}""",
            qb.args,
        ).fetchone()
    return to_int(col(row, "n"))


# ── KSB mappings ────────────────────────────────────────────────────

def list_mappings(evidence_id: int) -> list[EvidenceMapping]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            f"{_MAPPING_SELECT} WHERE m.evidence_id = ? {_MAPPING_ORDER}",
            (evidence_id,),
        ).fetchall()
    return [_map_mapping(r) for r in rows]


def add_mapping(
    evidence_id: int,
    ksb_id: int,
    *,
    coverage: str,
    assessor_note: str | None = None,
) -> int:
    """Map evidence to a KSB, or re-judge the mapping if it exists.

    Leans on the ``(evidence_id, ksb_id)`` unique constraint: an assessor
    revisiting a KSB is changing their judgement, not adding a second
    one.
    """
    init_db()
    with connect() as conn:
        conn.execute(
            """INSERT INTO evidence_ksb_map (evidence_id, ksb_id, coverage, assessor_note)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(evidence_id, ksb_id) DO UPDATE SET
                   coverage      = excluded.coverage,
                   assessor_note = excluded.assessor_note""",
            (evidence_id, ksb_id, coverage, assessor_note),
        )
        # lastrowid is only meaningful when the INSERT branch ran, so the
        # id is read back rather than assumed.
        row = conn.execute(
            "SELECT map_id FROM evidence_ksb_map WHERE evidence_id = ? AND ksb_id = ?",
            (evidence_id, ksb_id),
        ).fetchone()
    return int(row["map_id"])


def update_mapping(
    map_id: int, *, coverage: str | None = None, assessor_note: str | None = None
) -> None:
    init_db()
    assignments: list[str] = []
    values: list[Any] = []
    for column, value in (("coverage", coverage), ("assessor_note", assessor_note)):
        if value is not None:
            assignments.append(f"{column} = ?")
            values.append(value)
    if not assignments:
        return
    with connect() as conn:
        conn.execute(
            f"UPDATE evidence_ksb_map SET {', '.join(assignments)} WHERE map_id = ?",
            [*values, map_id],
        )


def remove_mapping(map_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM evidence_ksb_map WHERE map_id = ?", (map_id,))


# ── Coverage ────────────────────────────────────────────────────────

def coverage_for(apprentice_id: int, programme_id: int) -> list[KSBCoverage]:
    """Where this apprentice stands on every KSB of their programme.

    Both halves are loaded raw and handed to the domain to reduce:
    which judgement wins, and whether unaccepted evidence counts, are
    rules that belong with the portfolio model, not in SQL.
    """
    init_db()
    with connect() as conn:
        ksb_rows = conn.execute(
            "SELECT * FROM programme_ksbs WHERE programme_id = ?", (programme_id,)
        ).fetchall()
        map_rows = conn.execute(
            """SELECT m.ksb_id, m.coverage, e.status
                 FROM evidence_ksb_map m
                 JOIN portfolio_evidence e ON e.evidence_id = m.evidence_id
                WHERE e.apprentice_id = ?""",
            (apprentice_id,),
        ).fetchall()
    mappings = [
        (to_int(r["ksb_id"]), r["coverage"], r["status"] == "Accepted") for r in map_rows
    ]
    return roll_up_coverage([_map_ksb(r) for r in ksb_rows], mappings)


def build_summary(apprentice_id: int, programme_id: int) -> PortfolioSummary:
    """The whole portfolio position: every item plus every KSB's coverage."""
    init_db()
    return PortfolioSummary(
        apprentice_id=apprentice_id,
        evidence=list_evidence(apprentice_id=apprentice_id, with_mappings=True),
        coverage=coverage_for(apprentice_id, programme_id),
    )


# ── Verifications ───────────────────────────────────────────────────

def list_verifications(evidence_id: int) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """SELECT v.*, s.full_name AS verifier_name
                 FROM portfolio_verifications v
                 LEFT JOIN staff s ON s.staff_id = v.verifier_id
                WHERE v.evidence_id = ?
                ORDER BY v.verified_at DESC, v.verification_id DESC""",
            (evidence_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_verification(
    evidence_id: int,
    *,
    verifier_id: int | None,
    outcome: str,
    comments: str | None = None,
) -> int:
    """Record an IQA sampling decision.

    Verifications accumulate rather than replace: the sampling history is
    the audit trail, so a second look at the same evidence adds a row.
    """
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO portfolio_verifications
                   (evidence_id, verifier_id, outcome, comments)
               VALUES (?, ?, ?, ?)""",
            (evidence_id, verifier_id, outcome, comments),
        )
        return int(cur.lastrowid)
