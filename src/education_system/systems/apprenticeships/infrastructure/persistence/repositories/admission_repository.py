"""Admissions stages: where each applicant has got to.

An applicant with no row is at Application — the row is only written
once somebody makes an offer or records an enrolment.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from education_system.systems.apprenticeships.domain.admissions.stages import AdmissionStage
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
)

_FIELDS = ("stage", "offer_date", "offer_conditions", "enrolment_date", "updated_by")


def _map(row: Any) -> AdmissionStage:
    return AdmissionStage(
        apprentice_id=row["apprentice_id"],
        stage=col(row, "stage", "Application"),
        offer_date=col(row, "offer_date"),
        offer_conditions=col(row, "offer_conditions"),
        enrolment_date=col(row, "enrolment_date"),
        updated_by=col(row, "updated_by"),
        updated_at=col(row, "updated_at", ""),
    )


def get(apprentice_id: int) -> AdmissionStage | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM admission_stages WHERE apprentice_id = ?", (apprentice_id,)
        ).fetchone()
    return _map(row) if row else None


def stages_for(apprentice_ids: Iterable[int]) -> dict[int, AdmissionStage]:
    """``{apprentice_id: stage}`` for a queue in one query; missing ids have no row."""
    ids = sorted(set(apprentice_ids))
    if not ids:
        return {}
    init_db()
    qb = QueryBuilder()
    qb.add_in("apprentice_id", ids)
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM admission_stages {qb.where}", qb.args).fetchall()
    return {int(r["apprentice_id"]): _map(r) for r in rows}


def list_stages(
    *,
    stage: str | None = None,
    offer_from: str | None = None,
    offer_to: str | None = None,
    enrolment_from: str | None = None,
    enrolment_to: str | None = None,
) -> list[AdmissionStage]:
    """Stage rows filtered by stage and by offer / enrolment date."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(stage, "stage = ?", stage)
    qb.add_if(offer_from, "offer_date >= ?", offer_from)
    qb.add_if(offer_to, "offer_date <= ?", offer_to)
    qb.add_if(enrolment_from, "enrolment_date >= ?", enrolment_from)
    qb.add_if(enrolment_to, "enrolment_date <= ?", enrolment_to)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM admission_stages {qb.where} ORDER BY updated_at DESC", qb.args
        ).fetchall()
    return [_map(r) for r in rows]


def save(apprentice_id: int, payload: dict[str, Any]) -> None:
    """Create the row or update the supplied fields of it."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    if not columns:
        return
    values = [payload[c] for c in columns]
    updates = ", ".join(f"{c} = excluded.{c}" for c in columns)
    with connect() as conn:
        conn.execute(
            f"INSERT INTO admission_stages (apprentice_id, {', '.join(columns)}) "
            f"VALUES (?, {', '.join('?' for _ in columns)}) "
            f"ON CONFLICT(apprentice_id) DO UPDATE SET {updates}, "
            "updated_at = datetime('now')",
            [apprentice_id, *values],
        )
