"""KSB coverage for many apprentices at once, for the cohort skills matrix.

``portfolio_repository.coverage_for`` answers the question for one
apprentice in two queries. Calling it per row would make a cohort of a
few hundred a few hundred round trips, so this loads the KSBs for every
programme involved and the mappings for every apprentice involved in
one query each, then hands each apprentice's slice to the same domain
reduction (``roll_up_coverage``) the portfolio uses. The SQL is new; the
rule for which judgement wins is not duplicated.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from education_system.systems.apprenticeships.domain.portfolio.evidence import roll_up_coverage
from education_system.systems.apprenticeships.domain.programmes.models import KSB, KSBCoverage
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    col,
    connect,
    init_db,
    to_int,
)

# Kept under SQLite's historical 999 bound-parameter limit.
_CHUNK = 900


def _chunks(values: list[int]) -> Iterable[list[int]]:
    for start in range(0, len(values), _CHUNK):
        yield values[start:start + _CHUNK]


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


def cohort_coverage(programme_by_apprentice: dict[int, int]) -> dict[int, list[KSBCoverage]]:
    """``{apprentice_id: coverage}`` for every apprentice given.

    *programme_by_apprentice* maps each apprentice to the programme whose
    KSBs they are measured against. Apprentices with no programme should
    be left out by the caller: they have nothing to be measured against.
    """
    if not programme_by_apprentice:
        return {}
    init_db()
    programme_ids = sorted(set(programme_by_apprentice.values()))
    apprentice_ids = sorted(programme_by_apprentice)

    ksbs_by_programme: dict[int, list[KSB]] = {pid: [] for pid in programme_ids}
    mappings: dict[int, list[tuple[int, str, bool]]] = {aid: [] for aid in apprentice_ids}
    with connect() as conn:
        for chunk in _chunks(programme_ids):
            placeholders = ", ".join("?" for _ in chunk)
            for row in conn.execute(
                f"SELECT * FROM programme_ksbs WHERE programme_id IN ({placeholders})", chunk
            ).fetchall():
                ksbs_by_programme[row["programme_id"]].append(_map_ksb(row))
        for chunk in _chunks(apprentice_ids):
            placeholders = ", ".join("?" for _ in chunk)
            for row in conn.execute(
                f"""SELECT e.apprentice_id, m.ksb_id, m.coverage, e.status
                      FROM evidence_ksb_map m
                      JOIN portfolio_evidence e ON e.evidence_id = m.evidence_id
                     WHERE e.apprentice_id IN ({placeholders})""",
                chunk,
            ).fetchall():
                mappings[row["apprentice_id"]].append(
                    (to_int(row["ksb_id"]), row["coverage"], row["status"] == "Accepted")
                )

    return {
        aid: roll_up_coverage(ksbs_by_programme.get(programme_by_apprentice[aid], []),
                              mappings.get(aid, []))
        for aid in apprentice_ids
    }
