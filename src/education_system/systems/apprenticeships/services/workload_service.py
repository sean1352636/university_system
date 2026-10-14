"""Staff workload: what is on each tutor's plate, beyond caseload size.

A caseload count says how many apprentices someone has; it does not say
that eleven of them have reviews due this week and forty hours of
evidence are waiting to be assessed. This puts the open work next to the
headcount, so an administrator can rebalance before something slips.

An administrator sees every active member of staff; a tutor sees their
own. Nobody else holds ``staff.view``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.training import attendance as attendance_rules
from education_system.systems.apprenticeships.domain.workspace.items import Workload
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    assignment_repository,
    document_repository,
    learning_plan_repository,
    portfolio_repository,
    review_repository,
    staff_repository,
    support_repository,
    training_repository,
    welfare_repository,
)
from education_system.systems.apprenticeships.services.access import Actor, require

logger = logging.getLogger(__name__)

def _welfare_open(staff_id: int, today: date) -> int:
    return len(welfare_repository.list_concerns(tutor_id=staff_id, open_only=True))


def _support_reviews_due(staff_id: int, today: date) -> int:
    horizon = (today + timedelta(days=config.TASK_HORIZON_DAYS)).isoformat()
    return len(support_repository.list_arrangements(
        tutor_id=staff_id, in_force_only=True, review_due_by=horizon,
    ))


def _assignments_to_mark(staff_id: int, today: date) -> int:
    return assignment_repository.count_assignments(tutor_id=staff_id, status="Submitted")


def _actions_overdue(staff_id: int, today: date) -> int:
    return review_repository.count_targets(
        tutor_id=staff_id, open_only=True, overdue_on=today.isoformat(),
    )


def _documents_to_approve(staff_id: int, today: date) -> int:
    return len(document_repository.list_documents(tutor_id=staff_id, approval_status="Pending"))


# Extra counts reported by other features, as (label, function of staff
# id and today). Each is best-effort, like the task providers.
_OTHER_COUNTS: tuple[tuple[str, Callable[[int, date], int]], ...] = (
    ("Assignments to mark", _assignments_to_mark),
    ("Actions overdue", _actions_overdue),
    ("Documents to approve", _documents_to_approve),
    ("Welfare", _welfare_open),
    ("Support reviews", _support_reviews_due),
)


def list_workloads(actor: Actor, *, today: date | None = None) -> list[Workload]:
    """Workloads *actor* may see, heaviest first."""
    require(actor, "staff.view")
    today = today or date.today()
    if actor.role == config.ADMIN:
        members = staff_repository.list_all(active_only=True)
    elif actor.role == config.STAFF and actor.staff_id is not None:
        member = staff_repository.get(actor.staff_id)
        members = [member] if member else []
    else:
        members = []
    loads = [_build(member, today) for member in members]
    return sorted(loads, key=lambda w: (-w.open_items, -w.active, w.name))


def _build(member: Any, today: date) -> Workload:
    staff_id = member.staff_id
    summaries = apprentice_repository.list_summaries(tutor_id=staff_id, active_only=True)
    horizon = (today + timedelta(days=config.TASK_HORIZON_DAYS)).isoformat()
    reviews = review_repository.list_reviews(
        tutor_id=staff_id, statuses=["Scheduled", "In Progress"], date_to=horizon,
    )
    overdue = sum(1 for r in reviews if r.scheduled_date < today.isoformat())

    marks = training_repository.attendance_by_apprentice(
        s.apprentice.apprentice_id for s in summaries
    )
    concerns = sum(
        1 for aid, records in marks.items()
        if attendance_rules.summarise(aid, records).is_concern
    )
    objectives_overdue = sum(
        1
        for s in summaries
        for objective in learning_plan_repository.list_objectives(s.apprentice.apprentice_id)
        if objective.is_overdue(today)
    )

    other: dict[str, int] = {}
    for label, count in _OTHER_COUNTS:
        try:
            value = count(staff_id, today)
        except Exception:
            logger.exception("Workload count %r failed for staff %s", label, staff_id)
            continue
        if value:
            other[label] = value

    return Workload(
        staff_id=staff_id,
        name=member.full_name,
        staff_role=getattr(member, "staff_role", None),
        active=len(summaries),
        reviews_overdue=overdue,
        reviews_due_soon=len(reviews) - overdue,
        evidence_to_assess=portfolio_repository.pending_assessment_count(tutor_id=staff_id),
        hours_to_approve=training_repository.pending_count(tutor_id=staff_id),
        attendance_concerns=concerns,
        objectives_overdue=objectives_overdue,
        other=other,
    )
