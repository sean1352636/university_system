"""Appeals: an apprentice challenging a decision made about them.

Who decides an appeal depends on what is being appealed. An appeal
against an EPA result goes to the End-Point Assessment Organisation and
to nobody else: the provider trained the apprentice and is paid when
they complete, so letting it overturn an independent grade would undo
the independence ``config.EPAO_EXCLUSIVE`` exists to protect. Every
other appeal — against an assessment decision, a gateway decision, a
withdrawal — is about something the provider decided, and the
provider's administrator hears it.

Appeals are time-limited both ways: the apprentice has a window after
the decision to lodge one, and the decider has a deadline to answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

REFERENCE_PREFIX = "APL"

OPEN_APPEAL_STATUSES: frozenset[str] = frozenset({"Lodged", "Under review"})

# The outcomes a decider may record. Withdrawn is the apprentice's, not a
# decision.
DECISION_STATUSES: tuple[str, ...] = ("Upheld", "Partially upheld", "Rejected")

# A decider may rule straight from Lodged; Under review is for saying
# "we have it" when the ruling will take a while.
APPEAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "Lodged": frozenset({"Under review", *DECISION_STATUSES, "Withdrawn"}),
    "Under review": frozenset({*DECISION_STATUSES, "Withdrawn"}),
    "Upheld": frozenset(),
    "Partially upheld": frozenset(),
    "Rejected": frozenset(),
    "Withdrawn": frozenset(),
}

_DUE_SOON_DAYS = 3


@dataclass
class Appeal:
    """One appeal and where it stands."""

    appeal_id: int
    reference: str
    apprentice_id: int
    raised_by: str
    appeal_type: str
    decision_date: str
    grounds: str
    lodged_at: str
    deadline: str
    status: str = "Lodged"
    decision_ref_id: int | None = None
    decision_ref: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None
    decision: str | None = None
    created_at: str = ""
    updated_at: str = ""
    # Joined label, for display only.
    apprentice_name: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_APPEAL_STATUSES

    @property
    def is_epa_result(self) -> bool:
        return is_epa_result(self.appeal_type)

    @property
    def decider_label(self) -> str:
        return config.ROLE_LABELS[decider_role(self.appeal_type)]

    def is_overdue(self, today: date) -> bool:
        due = _parse(self.deadline)
        return self.is_open and due is not None and today > due

    def rag(self, today: date) -> str | None:
        if not self.is_open:
            return None
        if self.is_overdue(today):
            return "Red"
        due = _parse(self.deadline)
        if due is not None and due <= today + timedelta(days=_DUE_SOON_DAYS):
            return "Amber"
        return None


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def appeal_reference(appeal_id: int) -> str:
    return f"{REFERENCE_PREFIX}-{int(appeal_id):04d}"


def is_epa_result(appeal_type: str | None) -> bool:
    return appeal_type == config.EPA_RESULT_APPEAL


def decider_role(appeal_type: str | None) -> str:
    """The one role that hears an appeal of this type."""
    return config.END_POINT_ASSESSOR if is_epa_result(appeal_type) else config.ADMIN


def validate_type(value: str | None) -> str:
    return _match(value, config.APPEAL_TYPES, "Appeal type")


def validate_status(value: str | None) -> str:
    return _match(value, config.APPEAL_STATUSES, "Appeal status")


def validate_decision_status(value: str | None) -> str:
    """One of the outcomes a decider may record."""
    return _match(value, DECISION_STATUSES, "Decision")


def require_transition(current: str, new: str) -> None:
    allowed = APPEAL_TRANSITIONS.get(current, frozenset())
    if new in allowed:
        return
    if not allowed:
        raise ValidationError(f"This appeal is already {current.lower()} and cannot change")
    options = ", ".join(s for s in config.APPEAL_STATUSES if s in allowed)
    raise ValidationError(f"An appeal cannot go from {current} to {new}; next it may be: {options}")


def check_window(decision_date: date, today: date) -> None:
    """Raise unless an appeal against a decision made on *decision_date* is in time."""
    if decision_date > today:
        raise ValidationError("The decision date cannot be in the future")
    last_day = decision_date + timedelta(days=config.APPEAL_WINDOW_DAYS)
    if today > last_day:
        raise ValidationError(
            f"Appeals must be lodged within {config.APPEAL_WINDOW_DAYS} days of the "
            f"decision; the window for a decision on {decision_date.isoformat()} "
            f"closed on {last_day.isoformat()}"
        )


def window_closes(decision_date: date) -> date:
    return decision_date + timedelta(days=config.APPEAL_WINDOW_DAYS)


def decision_deadline(lodged: date) -> str:
    return (lodged + timedelta(days=config.APPEAL_DECISION_DAYS)).isoformat()


def _match(value: str | None, allowed: tuple[str, ...], label: str) -> str:
    cleaned = (value or "").strip()
    match = next((s for s in allowed if s.casefold() == cleaned.casefold()), None)
    if match is None:
        raise ValidationError(f"{label} must be one of: {', '.join(allowed)}")
    return match


def _parse(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None
