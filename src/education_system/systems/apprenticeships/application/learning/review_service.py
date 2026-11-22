"""Tripartite progress reviews: scheduling, recording, signing, targets.

A progress review is a meeting between the provider, the apprentice and
the employer, and the record of it is worth nothing as funding evidence
until all three have signed. That single rule shapes the whole module:
signing is the completion condition rather than a formality, and an
actor may only ever sign the line belonging to the party they actually
are.

The targets agreed at a review are the apprentice's action plan. Each
has an owner, a priority and a due date, and anything still open when
the next review begins is carried onto it: the meeting starts with the
outstanding actions in front of it rather than an empty list. The
owner-facing side of the plan — listing, status moves by the people who
own the actions, progress notes — is ``action_plan_service``.

Every function takes ``actor`` first. Reads are scoped to what the actor
may see — an employer's review list is their own organisation's and
nobody else's — and writes are refused outright.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.reviews import action_plans as action_rules
from education_system.systems.apprenticeships.domain.reviews.progress_reviews import (
    EmployerFeedback,
    Review,
    ReviewTarget,
    next_review_date,
    require_review_status,
    validate_rating,
    validate_satisfaction,
    validate_signatory,
    validate_target_status,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    review_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
)
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
    require_any,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)

# Which line of the review each role signs. A lookup rather than a
# caller-supplied argument on purpose: the party you sign as follows
# from who you are, and is not something a form may choose.
_SIGNATORY_FOR_ROLE: dict[str, str] = {
    config.ADMIN: "provider",
    config.STAFF: "provider",
    config.APPRENTICE: "apprentice",
    config.EMPLOYER: "employer",
}


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def list_reviews(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    overdue_only: bool = False,
    with_children: bool = False,
) -> list[Review]:
    """Reviews *actor* may see, with any extra filters applied.

    The actor's own scope is applied last and wins, so an employer
    passing another organisation's ``apprentice_id`` widens nothing.
    """
    require(actor, "review.view")
    filters: dict[str, Any] = {
        "apprentice_id": apprentice_id,
        "status": status,
        "overdue_only": overdue_only,
        "with_children": with_children,
    }
    filters.update(apprentice_filters(actor))
    return repo.list_reviews(**filters)


def get_review(actor: Actor, review_id: int) -> Review:
    """One review with its targets and signatures."""
    require(actor, "review.view")
    return _load(actor, review_id)


def review_queue(actor: Actor) -> dict[str, list[Review]]:
    """What needs attention, scoped to *actor*: the review dashboard."""
    require(actor, "review.view")
    overdue = list_reviews(actor, overdue_only=True, with_children=True)
    awaiting = list_reviews(actor, status="Awaiting Signatures", with_children=True)
    upcoming = [r for r in list_reviews(actor, status="Scheduled") if not r.is_overdue]
    upcoming.sort(key=lambda r: r.scheduled_date)
    return {"overdue": overdue, "awaiting_signature": awaiting, "upcoming": upcoming}


# ═════════════════════════════════════════════════════════════════════
# Scheduling
# ═════════════════════════════════════════════════════════════════════

def schedule_review(
    actor: Actor,
    apprentice_id: int,
    *,
    scheduled_date: str,
    conducted_by: int | None = None,
) -> Review:
    """Put a review in the diary.

    Outstanding actions are not carried onto it yet: they are carried
    when it starts, so that until then they stay on the review that set
    them, where the plan for the current period is read from.
    """
    require(actor, "review.conduct")
    apprentice = _apprentice(actor, apprentice_id)

    when = _validate_date(scheduled_date, "Scheduled date")
    if when is None:
        raise ValidationError("A scheduled date is required")

    review_id = repo.create({
        "apprentice_id": apprentice_id,
        "scheduled_date": when,
        "status": "Scheduled",
        # A tutor scheduling their own review is the overwhelming case,
        # so their staff id is stamped unless somebody else is named.
        "conducted_by": conducted_by if conducted_by is not None else actor.staff_id,
    })
    compliance_repository.record(
        action="create", entity="review", entity_id=review_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Scheduled {when} for {apprentice.full_name}",
    )
    logger.info(
        "Review %s scheduled for apprentice %s on %s by %s",
        review_id, apprentice_id, when, actor.username,
    )
    return _load(actor, review_id)


def schedule_next(actor: Actor, apprentice_id: int) -> Review:
    """Book the following review, one review interval on.

    Counted from the last meeting that actually happened rather than the
    last one booked: a review that slipped by three weeks moves the whole
    cycle with it, which is what the funding rules expect.
    """
    require(actor, "review.conduct")
    _apprentice(actor, apprentice_id)

    held = [r.held_date for r in repo.list_reviews(apprentice_id=apprentice_id) if r.held_date]
    return schedule_review(
        actor, apprentice_id, scheduled_date=next_review_date(max(held) if held else None)
    )


# ═════════════════════════════════════════════════════════════════════
# Conducting
# ═════════════════════════════════════════════════════════════════════

def start_review(actor: Actor, review_id: int) -> Review:
    """Open a scheduled review: the meeting is under way.

    Every action still open from the apprentice's earlier reviews is
    carried onto this one as it starts, so the meeting judges them.
    """
    require(actor, "review.conduct")
    review = _load(actor, review_id)
    require_review_status(review.status, "In Progress")

    repo.update(review_id, {"status": "In Progress"})
    compliance_repository.record(
        action="update", entity="review", entity_id=review_id,
        actor=actor.username, actor_role=actor.role, detail="Review started",
    )
    logger.info("Review %s started by %s", review_id, actor.username)
    _carry_outstanding(actor, review_id)
    return _load(actor, review_id)


def record_review(actor: Actor, review_id: int, payload: dict[str, Any]) -> Review:
    """Write up the meeting and send it out for signature."""
    require(actor, "review.conduct")
    review = _load(actor, review_id)

    if review.status == "Scheduled":
        # Writing up an outcome means the meeting happened, so a review
        # nobody remembered to start is stepped through In Progress
        # rather than refused for a missed button press.
        require_review_status(review.status, "In Progress")
        repo.update(review_id, {"status": "In Progress"})
        review.status = "In Progress"
    require_review_status(review.status, "Awaiting Signatures")

    data = _validate_review(payload)
    # Carried here as well as on start: a review started before carrying
    # existed, or stepped through In Progress just above, still gets the
    # outstanding actions. Idempotent, so a second pass carries nothing.
    _carry_outstanding(actor, review_id)
    held = data.get("held_date") or review.held_date or date.today().isoformat()
    data["held_date"] = held
    if not data.get("next_review_date"):
        data["next_review_date"] = review.next_review_date or next_review_date(held)
    if data.get("conducted_by") is None and review.conducted_by is None:
        data["conducted_by"] = actor.staff_id
    data["status"] = "Awaiting Signatures"

    repo.update(review_id, data)
    compliance_repository.record(
        action="update", entity="review", entity_id=review_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Held {held}, rating {data.get('progress_rating') or 'not given'}",
    )
    logger.info("Review %s recorded by %s, awaiting signatures", review_id, actor.username)
    return _load(actor, review_id)


def mark_missed(actor: Actor, review_id: int, *, reason: str) -> Review:
    """Record that the meeting did not happen."""
    require(actor, "review.conduct")
    review = _load(actor, review_id)
    require_review_status(review.status, "Missed")

    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to mark a review as missed")

    # There is no dedicated column for this, and a missed review has no
    # write-up to overwrite, so the reason goes in the summary.
    repo.update(review_id, {"status": "Missed", "summary": f"Missed: {note}"})
    compliance_repository.record(
        action="update", entity="review", entity_id=review_id,
        actor=actor.username, actor_role=actor.role, detail=f"Missed: {note}",
    )
    logger.info("Review %s marked missed by %s: %s", review_id, actor.username, note)
    return _load(actor, review_id)


# ═════════════════════════════════════════════════════════════════════
# Signatures
# ═════════════════════════════════════════════════════════════════════

def sign_review(actor: Actor, review_id: int, signatory: str | None = None) -> Review:
    """Add *actor*'s signature to a held review."""
    require(actor, "review.sign")
    review = _load(actor, review_id)

    expected = _SIGNATORY_FOR_ROLE.get(actor.role)
    if expected is None:
        raise PermissionDenied("Your role is not a party to the review and cannot sign it")
    chosen = validate_signatory(signatory) if signatory else expected
    if chosen != expected:
        # The value of a tripartite signature is that three different
        # people gave it. An employer signing the apprentice's line would
        # make the record a lie, so this is refused for every role,
        # administrators included — their remedy is unsign_review.
        raise PermissionDenied(f"You may sign only as {expected}, not as {chosen}")

    if not review.can_sign(chosen):
        if chosen in review.signed_by:
            raise ValidationError(f"The {chosen} has already signed this review")
        raise ValidationError(
            f"A review that is {review.status!r} cannot be signed — hold it first"
        )

    repo.add_signature(review_id, chosen, actor.username)
    compliance_repository.record(
        action="sign", entity="review", entity_id=review_id,
        actor=actor.username, actor_role=actor.role, detail=f"Signed as {chosen}",
    )
    logger.info("Review %s signed as %s by %s", review_id, chosen, actor.username)

    signed = repo.get(review_id)
    assert signed is not None
    if signed.is_fully_signed and signed.status == "Awaiting Signatures":
        # A review is not evidence until all three have signed, so the
        # third signature completes it here rather than leaving a fully
        # signed record waiting on somebody to press another button.
        require_review_status(signed.status, "Complete")
        repo.update(review_id, {"status": "Complete"})
        compliance_repository.record(
            action="approve", entity="review", entity_id=review_id,
            actor=actor.username, actor_role=actor.role,
            detail="All three signatures present — review complete",
        )
        logger.info("Review %s complete: signed by all three parties", review_id)
        signed = repo.get(review_id)
        assert signed is not None
    return signed


def unsign_review(actor: Actor, review_id: int, signatory: str) -> Review:
    """Remove a signature added in error. Administrators only.

    Not a route out of Complete: a completed review is signed evidence,
    and correcting one means holding another rather than editing history.
    """
    if not actor.is_admin:
        raise PermissionDenied("Only an administrator may remove a signature")
    review = repo.get(review_id, with_children=True)
    if review is None:
        raise ValidationError(f"No review with id {review_id}")
    if review.is_complete:
        raise ValidationError(
            "This review is complete and stands as evidence. Hold a further review "
            "rather than unpicking a signed one."
        )

    who = validate_signatory(signatory)
    if who not in review.signed_by:
        raise ValidationError(f"The {who} has not signed this review")

    repo.remove_signature(review_id, who)
    compliance_repository.record(
        action="update", entity="review", entity_id=review_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Removed {who} signature",
    )
    logger.warning(
        "Signature %s removed from review %s by %s", who, review_id, actor.username
    )
    return _load(actor, review_id)


# ═════════════════════════════════════════════════════════════════════
# Targets — the action plan
# ═════════════════════════════════════════════════════════════════════

def list_targets(
    actor: Actor,
    *,
    review_id: int | None = None,
    apprentice_id: int | None = None,
    open_only: bool = False,
) -> list[ReviewTarget]:
    """Targets set at reviews *actor* may see.

    The actor's own scope is applied last and wins, exactly as for
    reviews; the richer action-plan filters are in
    ``action_plan_service.list_actions``.
    """
    require(actor, "review.view")
    if review_id is not None:
        _load(actor, review_id)
        return repo.list_targets(review_id, open_only=open_only)
    if apprentice_id is not None:
        _apprentice(actor, apprentice_id)
    filters: dict[str, Any] = {"apprentice_id": apprentice_id, "open_only": open_only}
    filters.update(apprentice_filters(actor))
    return repo.list_targets(**filters)


def add_target(actor: Actor, review_id: int, payload: dict[str, Any]) -> ReviewTarget:
    """Agree a SMART target — an action — at a review."""
    require(actor, "review.conduct")
    review = _load(actor, review_id)
    if review.is_complete:
        raise ValidationError("A complete review cannot take new targets")

    data = _validate_target(payload, existing=None)
    # A new action starts open whatever the form posted: settling or
    # carrying one is a separate, audited step.
    data.update(review_id=review_id, status="Open", completed_at=None)
    target_id = repo.create_target(data)
    compliance_repository.record(
        action="create", entity="review_target", entity_id=target_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Review {review_id}: {data['description'][:80]} "
               f"({data['owner']}, {data['priority']})",
    )
    logger.info("Target %s added to review %s by %s", target_id, review_id, actor.username)

    created = repo.get_target(target_id)
    assert created is not None
    return created


def update_target(actor: Actor, target_id: int, payload: dict[str, Any]) -> ReviewTarget:
    """Edit a target's wording, owner, priority, due date or KSB mapping."""
    require(actor, "review.conduct")
    target = _load_target(actor, target_id)

    data = _validate_target(payload, existing=target)
    if "status" in data:
        if data["status"] == target.status:
            data.pop("status")
        else:
            action_rules.require_action_status_move(target.status, data["status"])
            data["completed_at"] = action_rules.completed_at_after(
                target.status, data["status"], target.completed_at, _now()
            )
    repo.update_target(target_id, data)
    compliance_repository.record(
        action="update", entity="review_target", entity_id=target_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
    )

    updated = repo.get_target(target_id)
    assert updated is not None
    return updated


def close_target(
    actor: Actor, target_id: int, *, status: str, note: str | None = None
) -> ReviewTarget:
    """Record how a target turned out.

    "Carried Forward" is honoured by actually carrying it: a copy opens on
    the apprentice's next review and this one is closed pointing at it.
    With no later review to carry it onto, the request is refused rather
    than leaving an action marked carried with nowhere to go.
    """
    require(actor, "review.conduct")
    target = _load_target(actor, target_id)

    outcome = validate_target_status(status)
    if outcome == "Open":
        raise ValidationError("Closing a target needs an outcome, not 'Open'")
    if outcome == action_rules.CARRIED_FORWARD:
        return _carry_one(actor, target, note)

    action_rules.require_action_status_move(target.status, outcome)
    repo.update_target(target_id, {
        "status": outcome,
        "outcome_note": _optional_text(note),
        "completed_at": action_rules.completed_at_after(
            target.status, outcome, target.completed_at, _now()
        ),
    })
    compliance_repository.record(
        action="update", entity="review_target", entity_id=target_id,
        actor=actor.username, actor_role=actor.role, detail=f"Closed as {outcome}",
    )
    logger.info("Target %s closed as %s by %s", target_id, outcome, actor.username)

    closed = repo.get_target(target_id)
    assert closed is not None
    return closed


def carry_forward(actor: Actor, review_id: int) -> list[ReviewTarget]:
    """Bring every open action from earlier reviews onto this one, now.

    Starting a review does this on its own. This is for the tutor who
    wants the outstanding actions on a review before the meeting opens,
    or for a review that was already under way when carrying began.
    Returns the new copies.
    """
    require(actor, "review.conduct")
    review = _load(actor, review_id)
    if review.status in ("Complete", "Missed"):
        raise ValidationError(
            f"A {review.status.lower()} review cannot take actions. Carry them onto the "
            "next review instead."
        )
    pairs = _carry_outstanding(actor, review_id)
    new_ids = {new for _, new in pairs}
    return [t for t in repo.list_targets(review_id) if t.target_id in new_ids]


def delete_target(actor: Actor, target_id: int) -> None:
    """Remove a target added in error."""
    require(actor, "review.conduct")
    target = _load_target(actor, target_id)

    repo.delete_target(target_id)
    compliance_repository.record(
        action="delete", entity="review_target", entity_id=target_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted from review {target.review_id}: {target.description[:80]}",
    )
    logger.info("Target %s deleted by %s", target_id, actor.username)


def _carry_outstanding(actor: Actor, review_id: int) -> list[tuple[int, int]]:
    """Carry open actions from earlier reviews onto *review_id*, audited."""
    review = repo.get(review_id, with_children=False)
    if review is None:
        return []
    when = review.held_date or review.scheduled_date
    pairs = repo.carry_forward_into(
        review_id, note=f"Carried forward to the review of {when}"
    )
    for old_id, new_id in pairs:
        compliance_repository.record(
            action="update", entity="review_target", entity_id=old_id,
            actor=actor.username, actor_role=actor.role,
            detail=f"Carried forward to review {review_id} as target {new_id}",
        )
    if pairs:
        logger.info(
            "%s outstanding action(s) carried onto review %s by %s",
            len(pairs), review_id, actor.username,
        )
    return pairs


def _carry_one(actor: Actor, target: ReviewTarget, note: str | None) -> ReviewTarget:
    if target.status == action_rules.CARRIED_FORWARD:
        raise ValidationError("This action has already been carried forward")
    if not target.is_open:
        raise ValidationError(
            f"Only an open action can be carried forward; this one is {target.status}"
        )
    destination = repo.next_review_after(target.review_id)
    if destination is None:
        raise ValidationError(
            "There is no later review to carry this action onto. Schedule the next "
            "review: open actions are carried onto it automatically when it starts."
        )
    when = destination.held_date or destination.scheduled_date
    reason = _optional_text(note)
    new_id = repo.carry_target(
        target.target_id, destination.review_id,
        note=f"Carried forward to the review of {when}" + (f": {reason}" if reason else ""),
    )
    if new_id is None:
        raise ValidationError("This action is no longer open")
    compliance_repository.record(
        action="update", entity="review_target", entity_id=target.target_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Carried forward to review {destination.review_id} as target {new_id}",
    )
    logger.info(
        "Target %s carried to review %s as %s by %s",
        target.target_id, destination.review_id, new_id, actor.username,
    )
    carried = repo.get_target(target.target_id)
    assert carried is not None
    return carried


# ═════════════════════════════════════════════════════════════════════
# Employer feedback
# ═════════════════════════════════════════════════════════════════════

def submit_feedback(actor: Actor, payload: dict[str, Any]) -> EmployerFeedback:
    """Record an employer's satisfaction rating."""
    require(actor, "review.feedback")
    satisfaction = validate_satisfaction(payload.get("satisfaction"))

    employer_id = _validate_id(payload.get("employer_id"), "Employer")
    if actor.role == config.EMPLOYER:
        # An employer rates their own experience. Whatever the form
        # posted is discarded, so nobody can file feedback against
        # another organisation's name.
        employer_id = actor.employer_id
    if employer_id is None:
        raise ValidationError("An employer is required to submit feedback")

    apprentice_id = _validate_id(payload.get("apprentice_id"), "Apprentice")
    if apprentice_id is not None:
        _apprentice(actor, apprentice_id)
    review_id = _validate_id(payload.get("review_id"), "Review")
    if review_id is not None:
        _load(actor, review_id)

    feedback_id = repo.add_feedback({
        "employer_id": employer_id,
        "apprentice_id": apprentice_id,
        "review_id": review_id,
        "satisfaction": satisfaction,
        "comments": _optional_text(payload.get("comments")),
        "submitted_by": actor.username,
    })
    compliance_repository.record(
        action="create", entity="employer_feedback", entity_id=feedback_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Employer {employer_id}: {satisfaction}",
    )
    logger.info("Feedback %s submitted by %s", feedback_id, actor.username)

    created = next(
        (f for f in repo.list_feedback(employer_id=employer_id)
         if f.feedback_id == feedback_id),
        None,
    )
    assert created is not None
    return created


def list_feedback(
    actor: Actor, *, employer_id: int | None = None, apprentice_id: int | None = None
) -> list[EmployerFeedback]:
    """Satisfaction ratings within *actor*'s scope."""
    require_any(actor, "review.view", "review.feedback")
    if actor.role == config.EMPLOYER:
        employer_id = actor.employer_id or _NO_MATCH
    elif actor.role == config.APPRENTICE:
        apprentice_id = actor.apprentice_id or _NO_MATCH
    return repo.list_feedback(employer_id=employer_id, apprentice_id=apprentice_id)


def satisfaction_average(actor: Actor, *, employer_id: int | None = None) -> float | None:
    """Mean satisfaction score out of five, or None when nobody has rated."""
    require_any(actor, "report.view", "review.feedback")
    if actor.role == config.EMPLOYER:
        employer_id = actor.employer_id or _NO_MATCH
    return repo.average_satisfaction(employer_id=employer_id)


# ═════════════════════════════════════════════════════════════════════
# Validation
# ═════════════════════════════════════════════════════════════════════

# No primary key is ever negative, so this matches nothing — an actor
# whose scope did not resolve sees an empty list, not everybody's.
_NO_MATCH = -1


def _load(actor: Actor, review_id: int) -> Review:
    """Fetch a review with its children, checked against *actor*'s scope."""
    review = repo.get(review_id, with_children=True)
    if review is None:
        raise ValidationError(f"No review with id {review_id}")
    require_apprentice_access(actor, apprentice_repository.get(review.apprentice_id))
    return review


def _load_target(actor: Actor, target_id: int) -> ReviewTarget:
    """A target, access checked through the review it belongs to."""
    target = repo.get_target(target_id)
    if target is None:
        raise ValidationError(f"No target with id {target_id}")
    _load(actor, target.review_id)
    return target


def _apprentice(actor: Actor, apprentice_id: int) -> Any:
    record = apprentice_repository.get(apprentice_id)
    if record is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, record)
    return record


def _validate_review(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalise a review write-up.

    Only keys actually present are returned, so recording a rating does
    not blank the comments somebody typed a moment earlier.
    """
    data: dict[str, Any] = {}
    if "held_date" in payload:
        data["held_date"] = _validate_date(payload.get("held_date"), "Held date")
    if "progress_rating" in payload:
        data["progress_rating"] = validate_rating(payload.get("progress_rating"))
    if "otj_on_track" in payload:
        data["otj_on_track"] = _validate_tristate(payload.get("otj_on_track"))
    for key in ("summary", "apprentice_comments", "employer_comments"):
        if key in payload:
            data[key] = _optional_text(payload.get(key))
    if "next_review_date" in payload:
        data["next_review_date"] = _validate_date(
            payload.get("next_review_date"), "Next review date"
        )
    if "conducted_by" in payload:
        data["conducted_by"] = _validate_id(payload.get("conducted_by"), "Conducted by")
    return data


def _validate_target(payload: dict[str, Any], *, existing: ReviewTarget | None) -> dict[str, Any]:
    """Normalise a target payload.

    On create, owner and priority take their defaults when absent; on an
    edit, only keys actually present are returned.
    """
    data: dict[str, Any] = {}
    if existing is None or "description" in payload:
        data["description"] = _require_text(payload.get("description"), "Target", limit=500)
    if "due_date" in payload:
        data["due_date"] = _validate_date(payload.get("due_date"), "Due date")
    if "ksb_codes" in payload:
        data["ksb_codes"] = _optional_text(payload.get("ksb_codes"))
    if existing is None or "owner" in payload:
        data["owner"] = action_rules.validate_owner(payload.get("owner"))
    if existing is None or "priority" in payload:
        data["priority"] = action_rules.validate_priority(payload.get("priority"))
    if "status" in payload:
        data["status"] = validate_target_status(payload.get("status"))
    if "outcome_note" in payload:
        data["outcome_note"] = _optional_text(payload.get("outcome_note"))
    return data


def _validate_tristate(value: Any) -> int | None:
    """Yes, no, or not yet judged.

    NULL is meaningful on this column — it means the reviewer made no
    judgement — so a blank must not collapse into "behind".
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "true", "yes", "y", "on") else 0
    return 1 if value else 0


def _require_text(value: Any, label: str, *, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{label} is required")
    if len(text) > limit:
        raise ValidationError(f"{label} must be {limit} characters or fewer")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _validate_date(value: Any, label: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{label} must be a date in YYYY-MM-DD format") from exc


def _validate_id(value: Any, label: str) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} is not valid") from exc


def _now() -> str:
    """A timestamp in the format SQLite's ``datetime('now')`` writes, so
    service-set stamps sort against repository-set ones."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
