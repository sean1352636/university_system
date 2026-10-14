"""Action plans: the targets agreed at progress reviews, as things to do.

A target set at a review used to sit on that review until the next one
judged it. That left two gaps. Nobody but the provider could move it,
though many are the employer's or the apprentice's to do; and a target
still outstanding when the next review came round simply stopped being
looked at, because the next review started with an empty list.

So each target now carries an owner, a priority and a due date. Its
owner can move it along and leave progress notes, and anything still
open when the next review begins is carried onto that review — the old
row is closed as "Carried Forward" and a copy pointing back at it opens
on the new one, so the history of the action survives the move.

The rows are still ``review_targets`` and the dataclass is still
:class:`~.progress_reviews.ReviewTarget`. "Action" is the name the
people doing the work use, not a second table to keep in step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

CARRIED_FORWARD = "Carried Forward"

# The outcomes that settle an action. Completion is stamped on either:
# "when was this dealt with" is the question the stamp answers, and a
# Not Met is dealt with as surely as a Met.
SETTLED_STATUSES: frozenset[str] = frozenset({"Met", "Not Met"})

# Which owner an outsider role answers for. Provider roles are absent on
# purpose: they may move any action in their scope, whoever owns it.
OWNER_FOR_ROLE: dict[str, str] = {
    config.APPRENTICE: "Apprentice",
    config.EMPLOYER: "Employer",
}


@dataclass
class ActionNote:
    """One entry in an action's history: a progress note or a status move."""

    note_id: int
    target_id: int
    author: str
    author_role: str
    body: str
    from_status: str | None = None
    to_status: str | None = None
    created_at: str = ""

    @property
    def is_status_change(self) -> bool:
        return self.to_status is not None

    @property
    def author_label(self) -> str:
        return f"{self.author} ({config.ROLE_LABELS.get(self.author_role, self.author_role)})"


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def validate_owner(value: str | None) -> str:
    """An owner from the list, matched ignoring case; blank takes the default."""
    return _match(value, config.ACTION_OWNERS, config.ACTION_DEFAULT_OWNER, "Action owner")


def validate_priority(value: str | None) -> str:
    return _match(value, config.ACTION_PRIORITIES, config.ACTION_DEFAULT_PRIORITY, "Priority")


def validate_note(body: str | None) -> str:
    text = (body or "").strip()
    if not text:
        raise ValidationError("A progress note cannot be empty")
    if len(text) > config.ACTION_NOTE_MAX_LENGTH:
        raise ValidationError(
            f"A progress note must be {config.ACTION_NOTE_MAX_LENGTH} characters or fewer"
        )
    return text


def may_move(role: str, owner: str) -> bool:
    """May someone in *role* move an action owned by *owner*?

    Provider staff may move anything in their scope — they run the plan.
    An apprentice or employer may move only the actions that are theirs
    to do: an apprentice ticking off their employer's action would make
    the plan say something nobody responsible has said.
    """
    if role in config.PROVIDER_ROLES:
        return True
    return OWNER_FOR_ROLE.get(role) == owner


def require_action_status_move(current: str, target: str) -> None:
    """Check a hand-made status move on an action is legal.

    "Carried Forward" is never set by hand — carrying is what moves the
    action onto the next review, and a status that said "carried" with no
    copy on the next review would be the lapse it exists to prevent. A
    carried-forward action is finished with; the live copy is on the
    later review.
    """
    if target not in config.TARGET_STATUSES:
        allowed = ", ".join(config.TARGET_STATUSES)
        raise ValidationError(f"Action status must be one of: {allowed}")
    if current == CARRIED_FORWARD:
        raise ValidationError(
            "This action was carried forward to a later review. Update the copy "
            "on that review instead."
        )
    if target == CARRIED_FORWARD:
        raise ValidationError(
            "An action is carried forward onto the next review, not marked as carried "
            "by hand. Leave it open: it moves across when that review starts."
        )
    if target == current:
        raise ValidationError(f"This action is already {current}")


def completed_at_after(
    previous_status: str, new_status: str, previous_completed_at: str | None, now: str
) -> str | None:
    """The completion stamp once an action's status changes.

    Stamped when it is settled, kept when it moves from one settled
    outcome to the other (it was dealt with then, not now), and cleared
    when it is reopened or carried.
    """
    if new_status not in SETTLED_STATUSES:
        return None
    if previous_status in SETTLED_STATUSES and previous_completed_at:
        return previous_completed_at
    return now


def carry_payload(target: Any, to_review_id: int) -> dict[str, Any]:
    """The copy of *target* that opens on the later review.

    Keeps what was agreed — wording, owner, priority, due date, KSBs —
    and counts how many times the action has now been carried, so a plan
    can show which actions keep slipping.
    """
    return {
        "review_id": to_review_id,
        "description": target.description,
        "due_date": target.due_date,
        "ksb_codes": target.ksb_codes,
        "owner": target.owner,
        "priority": target.priority,
        "status": "Open",
        "carried_from": target.target_id,
        "carry_count": int(target.carry_count or 0) + 1,
    }


def _match(value: str | None, options: tuple[str, ...], default: str, label: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return default
    found = next((o for o in options if o.casefold() == cleaned.casefold()), None)
    if found is None:
        raise ValidationError(f"{label} must be one of: {', '.join(options)}")
    return found
