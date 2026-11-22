"""Individual learning plans: objectives, progress and the conversation.

Provider staff build the plan and move its progress (``training.manage``);
the apprentice, their employer and provider staff can all comment on it
(``plan.comment``). Reading it follows ``training.view``, which the
end-point assessor deliberately does not hold — the plan is formative,
and EPA is independent of it.

The activities under an objective are training plan items, maintained
through ``training_service``.

Every function takes ``actor`` first. Reads are scoped to what the actor
may see, and writes are refused outright.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ValidationError,
)
from education_system.systems.apprenticeships.domain.records import audit
from education_system.systems.apprenticeships.domain.records.signatures import (
    LEARNING_PLAN,
    Signature,
    SignOff,
)
from education_system.systems.apprenticeships.domain.reviews.progress_reviews import Review
from education_system.systems.apprenticeships.domain.training import learning_plan as rules
from education_system.systems.apprenticeships.domain.training.learning_plan import (
    LearningObjective,
    LearningPlan,
    PlanComment,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    learning_plan_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    review_repository,
    training_repository,
)
from education_system.systems.apprenticeships.application.records import signature_service
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def get_plan(actor: Actor, apprentice_id: int) -> LearningPlan:
    """One apprentice's whole plan."""
    require(actor, "training.view")
    _require_apprentice(actor, apprentice_id)
    return LearningPlan(
        apprentice_id=apprentice_id,
        objectives=repo.list_objectives(apprentice_id),
        activities=training_repository.list_plan_items(apprentice_id),
        comments=repo.list_comments(apprentice_id),
    )


def review_history(actor: Actor, apprentice_id: int, *, limit: int = 10) -> list[Review]:
    """The apprentice's progress reviews, most recent first.

    Shown beside the plan because reviews are where it is revisited: the
    targets set there are what the next stretch of the plan is for.
    """
    require(actor, "review.view")
    _require_apprentice(actor, apprentice_id)
    reviews = review_repository.list_reviews(apprentice_id=apprentice_id, with_children=True)
    reviews.sort(key=lambda r: r.held_date or r.scheduled_date, reverse=True)
    return reviews[:limit]


# ═════════════════════════════════════════════════════════════════════
# Objectives
# ═════════════════════════════════════════════════════════════════════

def add_objective(actor: Actor, apprentice_id: int, payload: dict[str, Any]) -> LearningObjective:
    require(actor, "training.manage")
    _require_apprentice(actor, apprentice_id)

    data = _validate_objective(payload, existing=None)
    status, progress = rules.settle(
        data.get("status", "Not started"), data.get("progress", 0)
    )
    data.update(
        apprentice_id=apprentice_id,
        status=status,
        progress=progress,
        achieved_at=date.today().isoformat() if status == "Achieved" else None,
        created_by=actor.username,
    )
    objective_id = repo.create_objective(data)
    compliance_repository.record(
        action="create", entity="ilp_objective", entity_id=objective_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['title']} for apprentice {apprentice_id}",
    )
    logger.info("Objective %s added for apprentice %s by %s",
                objective_id, apprentice_id, actor.username)

    created = repo.get_objective(objective_id)
    assert created is not None
    return created


def update_objective(
    actor: Actor, objective_id: int, payload: dict[str, Any]
) -> LearningObjective:
    require(actor, "training.manage")
    existing = _require_objective(actor, objective_id)

    data = _validate_objective(payload, existing=existing)
    requested = data.get("status")
    status, progress = rules.status_after_progress(
        existing.status,
        data.get("progress", existing.progress),
        requested if requested and requested != existing.status else None,
    )
    data.update(
        status=status,
        progress=progress,
        achieved_at=_achieved_at(existing, status),
    )
    repo.update_objective(objective_id, data)
    updated = repo.get_objective(objective_id)
    assert updated is not None
    compliance_repository.record(
        action="update", entity="ilp_objective", entity_id=objective_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(payload)) or "no change",
        changes=audit.diff(existing, updated, fields=sorted(data)),
    )
    return updated


def record_progress(
    actor: Actor,
    objective_id: int,
    *,
    progress: Any,
    comment: str | None = None,
    status: str | None = None,
) -> LearningObjective:
    """Move an objective's progress, keeping the move in the plan's history.

    The update is written as a comment carrying the new figure, so the
    plan shows how progress moved and who moved it — not just where it
    stands now.
    """
    require(actor, "training.manage")
    existing = _require_objective(actor, objective_id)

    figure = rules.validate_progress(progress)
    requested = rules.validate_objective_status(status) if status else None
    new_status, figure = rules.status_after_progress(existing.status, figure, requested)
    body = (comment or "").strip() or f"Progress updated to {figure}%"
    body = rules.validate_comment(body)

    repo.record_progress(
        objective_id,
        status=new_status,
        progress=figure,
        achieved_at=_achieved_at(existing, new_status),
        apprentice_id=existing.apprentice_id,
        author=actor.username,
        author_role=actor.role,
        body=body,
    )
    updated = repo.get_objective(objective_id)
    assert updated is not None
    compliance_repository.record(
        action="update", entity="ilp_objective", entity_id=objective_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Progress {existing.progress}% -> {figure}% ({existing.status} -> {new_status})",
        changes=audit.diff(existing, updated, fields=("status", "progress", "achieved_at")),
    )
    return updated


def delete_objective(actor: Actor, objective_id: int, *, reason: str) -> None:
    """Remove an objective set by mistake.

    Its activities and comments stay on the plan. An objective that was
    real but no longer applies should be Withdrawn instead, which keeps it
    visible.
    """
    require(actor, "training.manage")
    existing = _require_objective(actor, objective_id)
    if not (reason or "").strip():
        raise ValidationError("A reason is required to delete an objective")

    compliance_repository.record(
        action="delete", entity="ilp_objective", entity_id=objective_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {existing.title} from apprentice {existing.apprentice_id}'s plan: "
               f"{reason}",
    )
    repo.delete_objective(objective_id)
    logger.info("Objective %s deleted by %s: %s", objective_id, actor.username, reason)


# ═════════════════════════════════════════════════════════════════════
# Comments
# ═════════════════════════════════════════════════════════════════════

def add_comment(
    actor: Actor, apprentice_id: int, body: str, *, objective_id: int | None = None
) -> PlanComment:
    """Add to the conversation on a plan, about one objective or the whole."""
    require(actor, "plan.comment")
    _require_apprentice(actor, apprentice_id)
    text = rules.validate_comment(body)
    if objective_id is not None:
        objective = repo.get_objective(objective_id)
        if objective is None or objective.apprentice_id != apprentice_id:
            raise ValidationError("That objective is not on this apprentice's plan")

    comment_id = repo.add_comment(
        apprentice_id=apprentice_id,
        author=actor.username,
        author_role=actor.role,
        body=text,
        objective_id=objective_id,
    )
    compliance_repository.record(
        action="create", entity="ilp_comment", entity_id=comment_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Comment on apprentice {apprentice_id}'s learning plan",
    )

    created = repo.get_comment(comment_id)
    assert created is not None
    return created


# ═════════════════════════════════════════════════════════════════════
# Sign-off
# ═════════════════════════════════════════════════════════════════════
#
# The apprentice, their employer and the provider each sign the plan.
# A signature covers the objectives and activities as they stood when
# it was given (what, how and by when — not progress), so changing any
# of them afterwards lapses every signature and the plan needs signing
# again. The mechanics live in signature_service; these are the plan's
# own entry points to it.

def plan_signatures(actor: Actor, apprentice_id: int) -> SignOff:
    """Who has signed this plan's current content, and who still must."""
    return signature_service.signoff(actor, LEARNING_PLAN, apprentice_id)


def sign_plan(actor: Actor, apprentice_id: int, *, statement: str | None = None) -> Signature:
    """Sign the plan as the actor's signatory: Apprentice, Employer or Provider."""
    return signature_service.sign(actor, LEARNING_PLAN, apprentice_id, statement=statement)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _require_apprentice(actor: Actor, apprentice_id: int) -> Apprentice:
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)
    return apprentice


def _require_objective(actor: Actor, objective_id: int) -> LearningObjective:
    objective = repo.get_objective(objective_id)
    if objective is None:
        raise ValidationError(f"No objective with id {objective_id}")
    _require_apprentice(actor, objective.apprentice_id)
    return objective


def _achieved_at(existing: LearningObjective, new_status: str) -> str | None:
    """Stamped when an objective becomes achieved, kept while it stays so."""
    if new_status != "Achieved":
        return None
    if existing.status == "Achieved" and existing.achieved_at:
        return existing.achieved_at
    return date.today().isoformat()


def _validate_objective(
    payload: dict[str, Any], *, existing: LearningObjective | None
) -> dict[str, Any]:
    """Normalise and check an objective payload.

    Only keys actually present are validated and returned, so a partial
    edit does not blank the rest.
    """
    data: dict[str, Any] = {}
    if existing is None or "title" in payload:
        title = str(payload.get("title") or "").strip()
        if not title:
            raise ValidationError("An objective needs a title")
        if len(title) > 200:
            raise ValidationError("An objective title must be 200 characters or fewer")
        data["title"] = title
    for key in ("description", "ksb_codes"):
        if key in payload:
            data[key] = str(payload.get(key) or "").strip() or None
    if "target_date" in payload:
        data["target_date"] = _validate_date(payload.get("target_date"), "Target date")
    if "status" in payload:
        data["status"] = rules.validate_objective_status(payload.get("status"))
    if "progress" in payload:
        data["progress"] = rules.validate_progress(payload.get("progress"))
    return data


def _validate_date(value: Any, label: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{label} must be a date in YYYY-MM-DD format") from exc
