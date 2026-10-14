"""Employer risk: which employers are putting their apprenticeships at risk.

For each employer this gathers what the system already records —
apprentice counts, attendance on the registers, off-the-job progress,
progress reviews, the employer's commitments and their satisfaction
feedback — and hands the figures to :func:`domain.employers.risk.assess`,
which turns them into Low / Medium / High with the reasons.

The whole cohort is read in a handful of queries, not per employer, so
the table of every employer costs the same as one row.

Reading it needs ``report.view`` and ``employer.view``. An admin sees
every employer; a member of staff only the employers of their own
caseload, with figures from their caseload alone.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import (
    ApprenticeSummary,
    ValidationError,
)
from education_system.systems.apprenticeships.domain.employers.risk import (
    EmployerRisk,
    EmployerRiskMetrics,
    assess,
)
from education_system.systems.apprenticeships.domain.training import attendance
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    employer_repository,
    review_repository,
    training_repository,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
)
from education_system.systems.apprenticeships.services.employer_contact_service import (
    visible_employer_ids,
)

logger = logging.getLogger(__name__)


def assess_employers(actor: Actor) -> list[EmployerRisk]:
    """Every employer in scope, highest risk first."""
    _require(actor)
    scope = visible_employer_ids(actor)
    employers = [
        s for s in employer_repository.list_summaries()
        if scope is None or s.employer.employer_id in scope
    ]
    if not employers:
        return []

    cohort = apprentice_repository.list_summaries(**apprentice_filters(actor))
    by_employer: dict[int, list[ApprenticeSummary]] = defaultdict(list)
    employer_of: dict[int, int] = {}
    for summary in cohort:
        employer_id = summary.apprentice.employer_id
        if employer_id is not None:
            by_employer[employer_id].append(summary)
            employer_of[summary.apprentice.apprentice_id] = employer_id

    active_ids = [
        s.apprentice.apprentice_id for s in cohort
        if s.apprentice.status in config.ACTIVE_STATUSES
    ]
    marks = training_repository.attendance_by_apprentice(active_ids)
    reviews = review_repository.list_reviews(**apprentice_filters(actor))
    today = date.today()
    commitments = employer_repository.list_commitments(
        employer_ids={s.employer.employer_id for s in employers}, outstanding_only=True
    )
    feedback = review_repository.list_feedback()

    results = []
    for employer in employers:
        employer_id = employer.employer.employer_id
        people = by_employer.get(employer_id, [])
        active = [s for s in people if s.apprentice.status in config.ACTIVE_STATUSES]
        metrics = EmployerRiskMetrics(
            employer_id=employer_id,
            employer_name=employer.name,
            employer_status=employer.employer.status,
            apprentices=len(people),
            active_apprentices=len(active),
            otj_on_track=sum(1 for s in active if not s.is_behind),
        )
        for summary in active:
            record = attendance.summarise(
                summary.apprentice.apprentice_id,
                marks.get(summary.apprentice.apprentice_id, []),
            )
            metrics.sessions_attended += record.present + record.late
            metrics.sessions_countable += record.present + record.late + record.absent

        active_set = {s.apprentice.apprentice_id for s in active}
        for review in reviews:
            if employer_of.get(review.apprentice_id) != employer_id:
                continue
            if review.status == "Complete":
                metrics.reviews_completed += 1
            elif review.is_overdue and review.apprentice_id in active_set:
                metrics.reviews_overdue += 1

        for commitment in commitments:
            if commitment.employer_id != employer_id:
                continue
            metrics.commitments_outstanding += 1
            if commitment.is_overdue(today):
                metrics.commitments_overdue += 1
            metrics.highest_escalation = max(
                metrics.highest_escalation, commitment.escalation_level
            )

        scores = [f.score for f in feedback if f.employer_id == employer_id and f.score]
        if scores:
            metrics.satisfaction = round(sum(scores) / len(scores), 2)
            metrics.feedback_count = len(scores)

        results.append(assess(metrics))

    results.sort(key=lambda r: r.sort_key)
    return results


def assess_employer(actor: Actor, employer_id: int) -> EmployerRisk:
    """One employer's rating and reasons."""
    _require(actor)
    scope = visible_employer_ids(actor)
    if scope is not None and employer_id not in scope:
        raise PermissionDenied("You do not have access to this employer's records")
    match = next((r for r in assess_employers(actor) if r.employer_id == employer_id), None)
    if match is None:
        raise ValidationError(f"No employer with id {employer_id}")
    return match


def risk_counts(actor: Actor) -> dict[str, int]:
    """How many employers sit at each level, for a dashboard tile."""
    counts = {level: 0 for level in config.EMPLOYER_RISK_LEVELS}
    for result in assess_employers(actor):
        counts[result.level] += 1
    return counts


def _require(actor: Actor) -> None:
    require(actor, "report.view")
    require(actor, "employer.view")
    if actor.role not in config.PROVIDER_ROLES:
        # Report and employer permissions together are provider-only today;
        # this keeps a future grant from exposing other employers' ratings.
        raise PermissionDenied("Employer risk ratings are for provider staff")
