"""The apprentice lifecycle, as a state machine.

Status is not a free-text field: it decides whether funding is claimable,
whether the apprentice appears on a tutor's caseload, and whether the
EPAO will accept a booking. Every move between states goes through
:func:`require_transition`, so an illegal jump — say straight from
Applicant to Completed, skipping gateway — cannot be stored.
"""

from __future__ import annotations

from dataclasses import dataclass

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

# Moves that need a reason recorded for the audit trail.
REASON_REQUIRED: frozenset[str] = frozenset({
    "Break in Learning", "Withdrawn", "Transferred",
})


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
    from education_system.systems.apprenticeships import config

    allowed = TRANSITIONS.get(current, frozenset())
    return tuple(s for s in config.APPRENTICE_STATUSES if s in allowed)


def can_transition(current: str, target: str) -> bool:
    """May an apprentice move from *current* to *target*?"""
    return target in TRANSITIONS.get(current, frozenset())


def require_transition(current: str, target: str, reason: str | None = None) -> None:
    """Raise unless the move is legal and carries any reason it needs."""
    from education_system.systems.apprenticeships import config

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


def is_funded(status: str) -> bool:
    """Does this status let the provider claim monthly funding?"""
    from education_system.systems.apprenticeships import config

    return status not in config.NON_FUNDED_STATUSES
