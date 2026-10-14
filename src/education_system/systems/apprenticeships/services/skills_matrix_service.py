"""The skills matrix: KSB coverage per apprentice, and across a cohort.

Reads only. Every level shown comes from the portfolio's own coverage
rule — ``portfolio_repository.coverage_for`` for one apprentice, and the
same domain reduction over a batch load for a cohort — so the matrix and
the gateway's "all KSBs competent" check can never disagree.

Access follows ``portfolio.view``, scoped as the portfolio is: an
apprentice sees their own matrix, a tutor their caseload, an employer
their own apprentices. The cohort view is for the people managing a
group — provider staff, administrators and employers. An apprentice has
no cohort to compare, and the end-point assessor, though they may open
any one apprentice's matrix as they may their portfolio, is not handed
a league table of the provider's cohort.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.progress.skills_matrix import (
    CohortRow,
    SkillsMatrix,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    portfolio_repository,
    skills_matrix_repository,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)

_COHORT_ROLES: frozenset[str] = frozenset({config.ADMIN, config.STAFF, config.EMPLOYER})


def apprentice_matrix(actor: Actor, apprentice_id: int) -> SkillsMatrix:
    """One apprentice's KSBs, each with its coverage level."""
    require(actor, "portfolio.view")
    summary = apprentice_repository.get_summary(apprentice_id)
    if summary is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, summary)
    programme_id = summary.apprentice.programme_id
    if programme_id is None:
        raise ValidationError(
            "This apprentice is not on a programme yet, so there are no KSBs to show"
        )
    return SkillsMatrix(
        apprentice_id=apprentice_id,
        apprentice_name=summary.full_name,
        programme_title=summary.programme_title,
        coverage=portfolio_repository.coverage_for(apprentice_id, programme_id),
    )


def my_matrix(actor: Actor) -> SkillsMatrix | None:
    """The signed-in apprentice's own matrix; None when the login is not linked."""
    if actor.apprentice_id is None:
        return None
    return apprentice_matrix(actor, actor.apprentice_id)


def cohort_matrix(
    actor: Actor,
    *,
    programme_id: int | None = None,
    employer_id: int | None = None,
    active_only: bool = True,
) -> list[CohortRow]:
    """Every apprentice in scope, with their coverage, for the cohort grid.

    Apprentices not yet on a programme are left out — they have no KSBs
    to be measured against. The actor's own scope is applied last and
    wins, so an employer's ``employer_id`` cannot be widened.
    """
    require(actor, "portfolio.view")
    if actor.role not in _COHORT_ROLES:
        raise PermissionDenied("The cohort skills matrix is not available to your role")
    filters: dict[str, Any] = {
        "programme_id": programme_id,
        "employer_id": employer_id,
        "active_only": active_only,
    }
    filters.update(apprentice_filters(actor))
    summaries = [
        s for s in apprentice_repository.list_summaries(**filters)
        if s.apprentice.programme_id is not None
    ]
    coverage = skills_matrix_repository.cohort_coverage({
        s.apprentice.apprentice_id: s.apprentice.programme_id for s in summaries
    })
    return [
        CohortRow(
            apprentice_id=s.apprentice.apprentice_id,
            apprentice_name=s.full_name,
            programme_title=s.programme_title,
            employer_name=s.employer_name,
            status=s.apprentice.status,
            coverage=coverage.get(s.apprentice.apprentice_id, []),
        )
        for s in summaries
    ]
