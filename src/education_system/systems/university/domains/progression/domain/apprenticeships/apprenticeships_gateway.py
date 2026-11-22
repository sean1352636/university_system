"""Read-only boundary onto apprenticeships-owned data.

The mirror image of ``apprenticeships.integrations.university_gateway``,
which reads university records without mutating them. This reads the
apprenticeships system's employers and programmes so the university can
*show* what is on offer, while the apprenticeships system remains the only
owner of those records — creating or editing an employer or a programme
happens there, not here.

The connection is opened ``mode=ro`` for the same reason the university
gateway does: a read-only boundary that cannot write is worth more than a
convention that says it shouldn't.
"""

from __future__ import annotations

import logging
from education_system.systems.university.domains.progression.infrastructure import (
    apprenticeships_db,
)
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)


class ApprenticeshipsGatewayError(RuntimeError):
    """The apprenticeships system's data cannot be read."""


@dataclass(frozen=True)
class EmployerSummary:
    employer_id: int
    name: str
    sector: str | None
    status: str | None
    postcode: str | None
    contact_name: str | None
    contact_email: str | None


@dataclass(frozen=True)
class ProgrammeSummary:
    programme_id: int
    reference: str | None
    title: str
    level: int | None
    duration_months: int | None
    funding_band: float | None
    sector: str | None
    status: str | None


class ApprenticeshipsGateway:
    """Queries the apprenticeships database without mutating it."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or paths.APPRENTICESHIPS_DB)

    # -- connection ------------------------------------------------------
    def _connect(self):
        if not self.db_path.exists():
            raise ApprenticeshipsGatewayError(
                f"Apprenticeships database not found at {self.db_path}"
            )
        return apprenticeships_db.open_readonly(self.db_path)

    def available(self) -> bool:
        """True when the apprenticeships system's data can be read."""
        try:
            self._connect().close()
            return True
        except Exception as exc:
            logger.debug("apprenticeships gateway unavailable: %s", exc)
            return False

    # -- reads -----------------------------------------------------------
    def list_employers(self, *, active_only: bool = False) -> list[EmployerSummary]:
        """Employers on the apprenticeships system, with their primary contact."""
        sql = """
            SELECT e.employer_id, e.name, e.sector, e.status, e.postcode,
                   m.full_name AS contact_name, m.email AS contact_email
              FROM employers e
              LEFT JOIN employer_managers m
                     ON m.employer_id = e.employer_id
                    AND COALESCE(m.is_primary, 0) = 1
                    AND COALESCE(m.active, 1) = 1
        """
        if active_only:
            sql += " WHERE COALESCE(e.status, 'Active') = 'Active'"
        sql += " ORDER BY e.name"

        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [
            EmployerSummary(
                employer_id=row["employer_id"],
                name=row["name"],
                sector=row["sector"],
                status=row["status"],
                postcode=row["postcode"],
                contact_name=row["contact_name"],
                contact_email=row["contact_email"],
            )
            for row in rows
        ]

    def list_programmes(self, *, open_only: bool = False) -> list[ProgrammeSummary]:
        """Apprenticeship programmes (the standards a learner can train on)."""
        sql = """
            SELECT programme_id, reference, title, level, duration_months,
                   funding_band, sector, status
              FROM programmes
        """
        if open_only:
            sql += " WHERE COALESCE(status, 'Active') IN ('Active', 'Open')"
        sql += " ORDER BY title"

        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [
            ProgrammeSummary(
                programme_id=row["programme_id"],
                reference=row["reference"],
                title=row["title"],
                level=row["level"],
                duration_months=row["duration_months"],
                funding_band=row["funding_band"],
                sector=row["sector"],
                status=row["status"],
            )
            for row in rows
        ]

    def employer_contact(self, employer_id: int) -> dict[str, Any] | None:
        """Who an application for this employer should reach.

        Prefers the employer's primary manager, falls back to any active
        manager. ``None`` when the employer has nobody recorded — the caller
        must then route the application somewhere a human will see it rather
        than dropping it.
        """
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT m.full_name, m.email, m.job_title, e.name AS employer_name
                  FROM employer_managers m
                  JOIN employers e ON e.employer_id = m.employer_id
                 WHERE m.employer_id = ?
                   AND COALESCE(m.active, 1) = 1
                   AND TRIM(COALESCE(m.email, '')) <> ''
                 ORDER BY COALESCE(m.is_primary, 0) DESC, m.manager_id
                 LIMIT 1
                """,
                (employer_id,),
            ).fetchone()
        return dict(row) if row else None
