"""Action plans: every action in scope, and moving them along.

The actions are progress-review targets (see ``review_service``, which
sets, edits, closes and carries them). This module is the side of the
plan the people doing the work use: a list across all of an actor's
apprentices with the filters a to-do list needs, status moves by the
owner of an action, and progress notes.

Who may move what:

* provider staff and administrators — any action in their scope;
* an apprentice — their own actions owned by "Apprentice";
* an employer — the "Employer" actions of their own apprentices.

Reading follows ``review.view``, which the end-point assessor does not
hold: the action plan is formative, and EPA is independent of it.

Every function takes ``actor`` first. Reads are scoped to what the actor
may see, and writes are refused outright.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.reviews import action_plans as rules
from education_system.systems.apprenticeships.domain.reviews.action_plans import ActionNote
from education_system.systems.apprenticeships.domain.reviews.progress_reviews import (
    Review,
    ReviewTarget,
    validate_target_status,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    review_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
)
from education_system.systems.apprenticeships.application.learning import review_service
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)

# The owner a provider user answers for when they ask for "my actions".
_PROVIDER_OWNER = "Tutor"


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def list_actions(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    review_id: int | None = None,
    status: str | None = None,
    owner: str | None = None,
    priority: str | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    due_within_days: int | None = None,
    mine_only: bool = False,
) -> list[ReviewTarget]:
    """Every action *actor* may see, soonest due first.

    ``due_within_days`` keeps open actions due by that many days from
    today, overdue ones included — "what is due or overdue". The actor's
    scope is applied last and wins.
    """
    require(actor, "review.view")
    today = date.today()
    filters: dict[str, Any] = {
        "apprentice_id": apprentice_id,
        "review_id": review_id,
        "status": validate_target_status(status) if status else None,
        "owner": rules.validate_owner(owner) if owner else None,
        "priority": rules.validate_priority(priority) if priority else None,
        "open_only": open_only,
    }
    if apprentice_id is not None:
        _require_apprentice(actor, apprentice_id)
    if review_id is not None:
        review_service.get_review(actor, review_id)
    if overdue_only:
        filters["overdue_on"] = today.isoformat()
    if due_within_days is not None:
        filters["open_only"] = True
        filters["due_before"] = (today + timedelta(days=int(due_within_days))).isoformat()
    if mine_only:
        filters["owner"] = owner_for(actor)
    filters.update(apprentice_filters(actor))
    return repo.list_targets(**filters)


def action_summary(actor: Actor) -> dict[str, int]:
    """Headline counts over the open actions in scope, for a KPI row."""
    today = date.today()
    open_actions = list_actions(actor, open_only=True)
    mine = owner_for(actor)
    return {
        "open": len(open_actions),
        "overdue": sum(1 for a in open_actions if a.overdue_on(today)),
        "due_soon": sum(1 for a in open_actions if a.is_due_soon(today)),
        "mine": sum(1 for a in open_actions if a.owner == mine),
        "carried": sum(1 for a in open_actions if a.is_carried),
    }


def get_action(actor: Actor, target_id: int) -> ReviewTarget:
    require(actor, "review.view")
    return _load(actor, target_id)


def history(actor: Actor, target_id: int) -> list[ActionNote]:
    """Notes and status moves on this action and every copy it was carried
    from, newest first — the action's whole life, across reviews."""
    require(actor, "review.view")
    _load(actor, target_id)
    return repo.list_notes(repo.carry_chain(target_id))


def reviews_taking_actions(actor: Actor, *, apprentice_id: int | None = None) -> list[Review]:
    """Reviews an action may be added to: in scope, not complete and not missed."""
    require(actor, "review.conduct")
    return [
        r for r in review_service.list_reviews(actor, apprentice_id=apprentice_id)
        if r.status not in ("Complete", "Missed")
    ]


def owner_for(actor: Actor) -> str | None:
    """The action owner *actor* answers for, if any."""
    if actor.role in config.PROVIDER_ROLES:
        return _PROVIDER_OWNER
    return rules.OWNER_FOR_ROLE.get(actor.role)


def may_update(actor: Actor, target: ReviewTarget) -> bool:
    """Would :func:`update_status` let *actor* move this action? For buttons."""
    return (
        actor.can("action.update")
        and target.status != rules.CARRIED_FORWARD
        and rules.may_move(actor.role, target.owner)
    )


# ═════════════════════════════════════════════════════════════════════
# Writes
# ═════════════════════════════════════════════════════════════════════

def add_action(actor: Actor, review_id: int, payload: dict[str, Any]) -> ReviewTarget:
    """Add an action to a review. Provider staff only (``review.conduct``)."""
    return review_service.add_target(actor, review_id, payload)


def update_status(
    actor: Actor, target_id: int, *, status: str, note: str | None = None
) -> ReviewTarget:
    """Move an action along, keeping the move in its history.

    The move is written as a note carrying the old and new status, so the
    plan shows who moved an action and when — not just where it stands.
    """
    require(actor, "action.update")
    target = _load(actor, target_id)
    _require_owner(actor, target)

    new_status = validate_target_status(status)
    rules.require_action_status_move(target.status, new_status)
    body = rules.validate_note(
        (note or "").strip() or f"Status changed from {target.status} to {new_status}"
    )
    repo.record_status(
        target_id,
        status=new_status,
        completed_at=rules.completed_at_after(
            target.status, new_status, target.completed_at, _now()
        ),
        from_status=target.status,
        author=actor.username,
        author_role=actor.role,
        body=body,
    )
    compliance_repository.record(
        action="update", entity="review_target", entity_id=target_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Action {target.status} -> {new_status}",
    )
    logger.info("Action %s moved %s -> %s by %s",
                target_id, target.status, new_status, actor.username)

    updated = repo.get_target(target_id)
    assert updated is not None
    return updated


def add_note(actor: Actor, target_id: int, body: str) -> ActionNote:
    """Record progress on an action without moving its status."""
    require(actor, "action.update")
    target = _load(actor, target_id)
    _require_owner(actor, target)
    if target.status == rules.CARRIED_FORWARD:
        raise ValidationError(
            "This action was carried forward to a later review. Add the note to the "
            "copy on that review."
        )

    text = rules.validate_note(body)
    note_id = repo.add_note(
        target_id, author=actor.username, author_role=actor.role, body=text
    )
    compliance_repository.record(
        action="create", entity="action_note", entity_id=note_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Progress note on action {target_id}",
    )
    return next(n for n in repo.list_notes([target_id]) if n.note_id == note_id)


def carry_to_next_review(actor: Actor, target_id: int, *, note: str | None = None) -> ReviewTarget:
    """Carry one open action onto the apprentice's next review now.

    Provider staff only — it changes what the next meeting will judge.
    """
    return review_service.close_target(
        actor, target_id, status=rules.CARRIED_FORWARD, note=note
    )


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _require_apprentice(actor: Actor, apprentice_id: int) -> None:
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)


def _load(actor: Actor, target_id: int) -> ReviewTarget:
    """An action, checked against *actor*'s scope through its apprentice.

    The same message for "not yours" as for any other refusal of an
    apprentice's record, so ids cannot be probed.
    """
    target = repo.get_target(target_id)
    if target is None:
        raise ValidationError(f"No action with id {target_id}")
    require_apprentice_access(actor, apprentice_repository.get(target.apprentice_id or 0))
    return target


def _require_owner(actor: Actor, target: ReviewTarget) -> None:
    if not rules.may_move(actor.role, target.owner):
        raise PermissionDenied(
            f"This action is the {target.owner.lower()}'s to do. Only its owner or the "
            "training provider may update it."
        )


def _now() -> str:
    """A timestamp in the format SQLite's ``datetime('now')`` writes."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
