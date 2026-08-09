"""Learning aims — how a course appears on the ESFA funding return.

Every enrolment a college claims funding for is reported as a *learning aim*
with a Learning Aim Reference (LARS code), a funding model and a set of dates.
The rules that decide what a college may claim live here so the funding report
and the enrolment screen apply the same test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    parse_date,
)

# ESFA funding models, by the number they're reported under.
FUNDING_MODELS = {
    25: "Adult Skills",
    35: "16-19 Study Programme",
    36: "Apprenticeship (from May 2017)",
    81: "Other Adult",
    99: "Non-funded",
}

AIM_TYPES = ("Programme aim", "Component aim", "Core aim")

# Completion status codes as reported on the Individualised Learner Record.
COMPLETION_STATUSES = {
    1: "Continuing",
    2: "Completed",
    3: "Withdrawn",
    6: "Temporarily withdrawn",
}

OUTCOMES = {
    1: "Achieved",
    2: "Partial achievement",
    3: "No achievement",
    8: "Learning activities complete, outcome not known",
}

# Minimum days on programme before a college may claim funding. Withdrawing
# inside this window means the enrolment is not fundable at all.
QUALIFYING_PERIOD_DAYS = 42


@dataclass
class LearningAim:
    """One fundable learning aim attached to an enrolment."""

    aim_id: int | None
    enrolment_id: int
    lars_code: str
    aim_type: str = "Programme aim"
    funding_model: int = 35
    start_date: date | None = None
    planned_end_date: date | None = None
    actual_end_date: date | None = None
    completion_status: int = 1
    outcome: int | None = None
    funding_value: float = 0.0

    @property
    def funding_model_label(self) -> str:
        return FUNDING_MODELS.get(self.funding_model, f"Unknown ({self.funding_model})")

    @property
    def completion_label(self) -> str:
        return COMPLETION_STATUSES.get(self.completion_status, "Unknown")

    @property
    def outcome_label(self) -> str:
        return OUTCOMES.get(self.outcome, "") if self.outcome is not None else ""

    def days_on_programme(self, on: date | None = None) -> int | None:
        """Days between start and end (or today), or None without a start."""
        if self.start_date is None:
            return None
        end = self.actual_end_date or on or date.today()
        return (end - self.start_date).days

    def is_fundable(self, on: date | None = None) -> bool:
        """Whether this aim may be claimed for funding.

        Non-funded aims never are; a withdrawal inside the 42-day qualifying
        period never is; everything else is.
        """
        if self.funding_model == 99:
            return False
        if self.completion_status == 3:
            days = self.days_on_programme(on)
            return days is not None and days >= QUALIFYING_PERIOD_DAYS
        return True

    def validate(self) -> None:
        if not self.lars_code.strip():
            raise ValidationError("Learning aim needs a LARS reference")
        if self.aim_type not in AIM_TYPES:
            raise ValidationError(f"Unknown aim type '{self.aim_type}'")
        if self.funding_model not in FUNDING_MODELS:
            raise ValidationError(f"Unknown funding model '{self.funding_model}'")
        if self.completion_status not in COMPLETION_STATUSES:
            raise ValidationError(f"Unknown completion status '{self.completion_status}'")
        if self.outcome is not None and self.outcome not in OUTCOMES:
            raise ValidationError(f"Unknown outcome '{self.outcome}'")
        if self.funding_value < 0:
            raise ValidationError("Funding value cannot be negative")
        if self.start_date and self.planned_end_date and self.planned_end_date < self.start_date:
            raise ValidationError("Planned end date cannot be before the start date")
        if self.start_date and self.actual_end_date and self.actual_end_date < self.start_date:
            raise ValidationError("Actual end date cannot be before the start date")
        if self.completion_status in (2, 3) and self.actual_end_date is None:
            raise ValidationError(
                f"A {self.completion_label.lower()} aim must record an actual end date"
            )

    def to_row(self) -> dict:
        return {
            "enrolment_id": int(self.enrolment_id),
            "lars_code": self.lars_code.strip(),
            "aim_type": self.aim_type,
            "funding_model": int(self.funding_model),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "planned_end_date": (
                self.planned_end_date.isoformat() if self.planned_end_date else None
            ),
            "actual_end_date": (
                self.actual_end_date.isoformat() if self.actual_end_date else None
            ),
            "completion_status": int(self.completion_status),
            "outcome": self.outcome,
            "funding_value": float(self.funding_value),
        }

    @classmethod
    def from_row(cls, row) -> "LearningAim":
        d = dict(row)
        return cls(
            aim_id=d.get("aim_id"),
            enrolment_id=int(d.get("enrolment_id") or 0),
            lars_code=d.get("lars_code") or "",
            aim_type=d.get("aim_type") or "Programme aim",
            funding_model=int(d.get("funding_model") or 35),
            start_date=parse_date(d.get("start_date")),
            planned_end_date=parse_date(d.get("planned_end_date")),
            actual_end_date=parse_date(d.get("actual_end_date")),
            completion_status=int(d.get("completion_status") or 1),
            outcome=d.get("outcome"),
            funding_value=float(d.get("funding_value") or 0),
        )


__all__ = [
    "AIM_TYPES",
    "COMPLETION_STATUSES",
    "FUNDING_MODELS",
    "OUTCOMES",
    "QUALIFYING_PERIOD_DAYS",
    "LearningAim",
]
