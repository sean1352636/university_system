"""Welfare concerns, their case notes, and the risk profile.

A welfare concern is something a tutor has noticed that could stop an
apprentice finishing, or harm them: money trouble, housing, their mental
health, a safeguarding worry. It is restricted information — provider
staff only, and a tutor only for their own caseload — and it keeps its
whole history in case notes, because when a concern is escalated the
question asked is what was known, and when.

The risk profile is separate from any one concern. It reads warning
signs the system already holds — attendance, off-the-job hours, overdue
reviews and learning-plan targets — alongside the open concerns, and
turns them into a Low / Medium / High rating with the reasons spelled
out. The reasons matter more than the rating: "High" alone tells a tutor
to worry, the reasons tell them what to do.

This is not the platform's safeguarding module
(``platform/governance/safeguarding``). A safeguarding concern recorded
here is the tutor's working record; any formal referral still goes
through the designated safeguarding lead's process.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

CLOSED = "Closed"
ESCALATED = "Escalated"


@dataclass
class WelfareNote:
    """One case note on a concern."""

    note_id: int
    concern_id: int
    author: str
    author_role: str
    note: str
    created_at: str = ""

    @property
    def author_label(self) -> str:
        return f"{self.author} ({config.ROLE_LABELS.get(self.author_role, self.author_role)})"


@dataclass
class WelfareConcern:
    """One welfare concern about one apprentice."""

    concern_id: int
    apprentice_id: int
    category: str
    severity: str
    description: str
    status: str = "Open"
    raised_by: str = ""
    raised_at: str = ""
    assigned_to: int | None = None
    escalated_to: str | None = None
    escalated_at: str | None = None
    closed_at: str | None = None
    outcome: str | None = None
    updated_at: str = ""
    # Denormalised by the list query.
    apprentice_name: str = ""
    assigned_name: str | None = None
    # Oldest first, so a case reads as it happened.
    notes: list[WelfareNote] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return self.status in config.WELFARE_OPEN_STATUSES

    @property
    def severity_rank(self) -> int:
        order = config.WELFARE_SEVERITIES
        return order.index(self.severity) if self.severity in order else -1

    @property
    def rag(self) -> str | None:
        """Colour for list screens: the severity of a live concern."""
        if not self.is_open:
            return None
        return {"Critical": "Red", "High": "Red", "Medium": "Amber"}.get(self.severity, "Green")


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def validate_category(value: str | None) -> str:
    return _one_of(value, config.WELFARE_CATEGORIES, "Category")


def validate_severity(value: str | None) -> str:
    return _one_of(value, config.WELFARE_SEVERITIES, "Severity")


def validate_status(value: str | None) -> str:
    return _one_of(value, config.WELFARE_STATUSES, "Status")


def validate_text(value: object, label: str, *, required: bool = True) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise ValidationError(f"{label} cannot be empty")
        return None
    limit = config.LEARNER_SUPPORT_NOTE_MAX_LENGTH
    if len(text) > limit:
        raise ValidationError(f"{label} must be {limit} characters or fewer")
    return text


def check_transition(
    current: str,
    new: str,
    *,
    escalated_to: str | None,
    outcome: str | None,
) -> None:
    """What moving a concern to *new* has to carry with it.

    Escalating says who to — "escalated" to nobody is not escalated.
    Closing says how it ended, because a closed concern with no outcome
    reads, later, as one that was dropped. Any status may be reached
    from any other, including reopening a closed concern: things come
    back, and a new concern would split the history in two.
    """
    if new == current:
        raise ValidationError(f"The concern is already {current}")
    if new == ESCALATED and not escalated_to:
        raise ValidationError("Say who the concern is being escalated to")
    if new == CLOSED and not outcome:
        raise ValidationError("Record the outcome before closing a concern")


# ═════════════════════════════════════════════════════════════════════
# Risk profile
# ═════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RiskFactor:
    """One warning sign and the points it adds."""

    key: str
    points: int
    reason: str


@dataclass
class RiskProfile:
    """How worried to be about one apprentice, and why."""

    apprentice_id: int
    apprentice_name: str = ""
    tutor_name: str | None = None
    factors: list[RiskFactor] = field(default_factory=list)

    @property
    def score(self) -> int:
        return sum(f.points for f in self.factors)

    @property
    def level(self) -> str:
        return risk_level(self.score)

    @property
    def reasons(self) -> list[str]:
        return [f.reason for f in self.factors]

    @property
    def rag(self) -> str:
        return {"High": "Red", "Medium": "Amber"}.get(self.level, "Green")

    @property
    def is_at_risk(self) -> bool:
        return self.level != "Low"


def risk_level(score: int) -> str:
    if score >= config.RISK_HIGH_SCORE:
        return "High"
    if score >= config.RISK_MEDIUM_SCORE:
        return "Medium"
    return "Low"


def assess_risk(
    apprentice_id: int,
    *,
    apprentice_name: str = "",
    tutor_name: str | None = None,
    attendance_concern: str | None = None,
    otj_behind: bool = False,
    otj_detail: str = "",
    overdue_reviews: int = 0,
    overdue_objectives: int = 0,
    open_concerns: list[WelfareConcern] | None = None,
) -> RiskProfile:
    """Combine the warning signs into a profile.

    Pure: the caller gathers the signs from wherever they live, so the
    rule that turns them into a rating can be tested on its own and
    changed in one place. *attendance_concern* is the attendance
    summary's own reason, or None when attendance is not a concern.
    """
    factors: list[RiskFactor] = []
    if attendance_concern:
        factors.append(RiskFactor(
            "attendance", config.RISK_POINTS_ATTENDANCE, attendance_concern,
        ))
    if otj_behind:
        factors.append(RiskFactor(
            "otj", config.RISK_POINTS_OTJ_BEHIND,
            "Behind on off-the-job hours" + (f" ({otj_detail})" if otj_detail else ""),
        ))
    if overdue_reviews > 0:
        plural = "review" if overdue_reviews == 1 else "reviews"
        factors.append(RiskFactor(
            "reviews", config.RISK_POINTS_OVERDUE_REVIEW,
            f"{overdue_reviews} progress {plural} overdue",
        ))
    if overdue_objectives >= config.RISK_OVERDUE_OBJECTIVES_MIN:
        factors.append(RiskFactor(
            "objectives", config.RISK_POINTS_OVERDUE_OBJECTIVES,
            f"{overdue_objectives} learning-plan objectives overdue",
        ))
    live = [c for c in (open_concerns or []) if c.is_open]
    if live:
        worst = max(live, key=lambda c: c.severity_rank)
        plural = "concern" if len(live) == 1 else "concerns"
        factors.append(RiskFactor(
            "welfare", config.RISK_POINTS_WELFARE.get(worst.severity, 1),
            f"{len(live)} open welfare {plural}, worst {worst.severity} ({worst.category})",
        ))
    return RiskProfile(
        apprentice_id=apprentice_id,
        apprentice_name=apprentice_name,
        tutor_name=tutor_name,
        factors=factors,
    )


def _one_of(value: str | None, allowed: tuple[str, ...], label: str) -> str:
    cleaned = (value or "").strip()
    match = next((a for a in allowed if a.casefold() == cleaned.casefold()), None)
    if match is None:
        raise ValidationError(f"{label} must be one of: {', '.join(allowed)}")
    return match
