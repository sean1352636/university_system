"""The apprentice lifecycle, as a state machine.

Status is not a free-text field: it decides whether funding is claimable,
whether the apprentice appears on a tutor's caseload, and whether the
EPAO will accept a booking. Every move between states goes through
:func:`require_transition`, so an illegal jump — say straight from
Applicant to Completed, skipping gateway — cannot be stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

# Which statuses may follow which. Everything reachable from a state is
# listed explicitly; an empty set is a terminal state.
TRANSITIONS: dict[str, frozenset[str]] = {
    "Applicant": frozenset({"On Programme", "Withdrawn"}),
    "On Programme": frozenset({
        "Break in Learning", "Gateway", "Withdrawn", "Transferred",
    }),
    # A break preserves the record; the apprentice returns to training.
    "Break in Learning": frozenset({"On Programme", "Withdrawn", "Transferred"}),
    # Gateway can be rejected, sending them back to finish the training.
    "Gateway": frozenset({"EPA", "On Programme", "Withdrawn"}),
    # A failed EPA returns them to gateway for a retake, not to training.
    "EPA": frozenset({"Completed", "Gateway", "Withdrawn"}),
    "Completed": frozenset(),
    "Withdrawn": frozenset({"On Programme"}),   # reinstatement after appeal
    "Transferred": frozenset(),
}

# Derived rather than listed, so the two cannot disagree.
TERMINAL_STATUSES: frozenset[str] = frozenset(s for s, nxt in TRANSITIONS.items() if not nxt)

# Moves that end the programme and stamp an actual end date.
ENDING_STATUSES: frozenset[str] = frozenset({"Completed", "Withdrawn", "Transferred"})

# Moves that need a reason recorded for the audit trail.
REASON_REQUIRED: frozenset[str] = frozenset({
    "Break in Learning", "Withdrawn", "Transferred",
})

# Moves whose reason comes from a closed list, so breaks and withdrawals
# can be reported on by reason. Both lists end in "Other".
REASON_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Break in Learning": config.BREAK_REASONS,
    "Withdrawn": config.WITHDRAWAL_REASONS,
}
OTHER_REASON = "Other"


@dataclass
class StatusChange:
    """One recorded move between statuses."""

    history_id: int
    apprentice_id: int
    from_status: str | None
    to_status: str
    reason: str | None
    effective_date: str
    actor: str | None
    created_at: str


def next_statuses(current: str) -> tuple[str, ...]:
    """Statuses reachable from *current*, in lifecycle order.

    Interfaces use this to populate the status dropdown, which is why
    the ordering follows ``config.APPRENTICE_STATUSES`` rather than the
    arbitrary order of a set.
    """
    allowed = TRANSITIONS.get(current, frozenset())
    return tuple(s for s in config.APPRENTICE_STATUSES if s in allowed)


def can_transition(current: str, target: str) -> bool:
    """May an apprentice move from *current* to *target*?"""
    return target in TRANSITIONS.get(current, frozenset())


def require_transition(current: str, target: str, reason: str | None = None) -> None:
    """Raise unless the move is legal and carries any reason it needs."""
    if target not in config.APPRENTICE_STATUSES:
        raise ValidationError(f"{target!r} is not an apprentice status")
    if current == target:
        raise ValidationError(f"Apprentice is already {target!r}")
    if not can_transition(current, target):
        allowed = next_statuses(current)
        options = ", ".join(allowed) if allowed else "nothing — this is a final status"
        raise ValidationError(
            f"Cannot move from {current!r} to {target!r}. Allowed from here: {options}"
        )
    if target in REASON_REQUIRED and not (reason or "").strip():
        raise ValidationError(f"A reason is required when moving to {target!r}")


def is_terminal(status: str) -> bool:
    """Is there nowhere left to move from *status*?"""
    return status in TERMINAL_STATUSES


def is_funded(status: str) -> bool:
    """Does this status let the provider claim monthly funding?"""
    return status not in config.NON_FUNDED_STATUSES


def end_date_change(current: str, target: str) -> Literal["set", "clear"] | None:
    """What a move does to the apprentice's actual end date.

    Moving into an ending status stamps it. Moving out of one — today
    only reinstatement from Withdrawn — clears it: an apprentice back on
    programme has not ended, and a stale end date would keep driving the
    record-retention clock and the funding return.
    """
    if target in ENDING_STATUSES:
        return "set"
    if current in ENDING_STATUSES:
        return "clear"
    return None


def reason_options(target: str) -> tuple[str, ...]:
    """The closed list of reasons for a move to *target*, if it has one."""
    return REASON_CATEGORIES.get(target, ())


def split_reason(
    target: str, reason: str | None, notes: str | None = None
) -> tuple[str, str | None]:
    """Turn a stated reason into ``(category, detail)`` for the record.

    For a move with a closed list, a reason matching a listed category
    (ignoring case) is that category and *notes* is the detail. Anything
    else is kept rather than refused — admissions records "Application
    declined: ..." as a withdrawal reason, for one — as ``Other``, with
    the text leading the detail. ``Other`` on its own says nothing, so it
    needs a detail. A move without a list returns the reason as given.
    """
    text = (reason or "").strip()
    extra = (notes or "").strip() or None
    options = reason_options(target)
    if not options:
        return text, extra
    for option in options:
        if option.casefold() == text.casefold():
            category = option
            break
    else:
        category, extra = OTHER_REASON, "; ".join(p for p in (text, extra) if p) or None
    if category == OTHER_REASON and not extra:
        raise ValidationError(f"Say what the reason was when choosing {OTHER_REASON!r}")
    return category, extra
