"""Funding allocations and the income a college earns against them.

The two numbers a principal asks for: what were we allocated, and what have we
actually earned? Earned income depends on retention — a learner who withdraws
after the qualifying period earns a proportion, not the full rate — so the
calculation is here rather than approximated in a report.
"""

from __future__ import annotations

from dataclasses import dataclass

from education_system.systems.fe_college.config import FUNDING_SOURCES
from education_system.systems.fe_college.domain.students.models import ValidationError

# Indicative national funding rates per full-time learner per year.
BAND_RATES = {
    "Band 1 (540+ hours)": 4642.00,
    "Band 2 (450-539 hours)": 3865.00,
    "Band 3 (360-449 hours)": 3090.00,
    "Band 4 (280-359 hours)": 2408.00,
    "Band 5 (below 280 hours)": 1600.00,
}

# Share of the rate earned on enrolment ("on-programme"), with the remainder
# earned on completion. This is what makes retention a financial issue as well
# as a quality one.
ON_PROGRAMME_SHARE = 0.80
COMPLETION_SHARE = 0.20


def band_for_hours(guided_learning_hours: int) -> str:
    """The funding band a course's planned hours fall into."""
    if guided_learning_hours >= 540:
        return "Band 1 (540+ hours)"
    if guided_learning_hours >= 450:
        return "Band 2 (450-539 hours)"
    if guided_learning_hours >= 360:
        return "Band 3 (360-449 hours)"
    if guided_learning_hours >= 280:
        return "Band 4 (280-359 hours)"
    return "Band 5 (below 280 hours)"


def earned_income(band: str, *, retained: bool, completed: bool) -> float:
    """Income earned for one learner on one aim.

    A learner who withdrew before the qualifying period earns nothing; one who
    was retained earns the on-programme share; one who also completed earns the
    completion element on top.
    """
    rate = BAND_RATES.get(band, 0.0)
    if not retained:
        return 0.0
    earned = rate * ON_PROGRAMME_SHARE
    if completed:
        earned += rate * COMPLETION_SHARE
    return round(earned, 2)


@dataclass
class FundingAllocation:
    """One funding stream's allocation for an academic year."""

    allocation_id: int | None
    funding_source: str
    academic_year: str
    allocated: float = 0.0
    earned: float = 0.0
    learner_count: int = 0
    notes: str = ""

    @property
    def variance(self) -> float:
        """Earned minus allocated; negative means under-delivery (clawback)."""
        return round(self.earned - self.allocated, 2)

    @property
    def delivery_pct(self) -> float | None:
        if self.allocated <= 0:
            return None
        return round(self.earned / self.allocated * 100, 1)

    @property
    def status(self) -> str:
        """Delivery position against allocation.

        Colleges are held to a tolerance band around allocation: under-deliver
        and funding is clawed back, over-deliver and the excess is unfunded.
        """
        pct = self.delivery_pct
        if pct is None:
            return "no allocation set"
        if pct < 97:
            return f"under-delivering ({pct}%) — clawback risk"
        if pct > 103:
            return f"over-delivering ({pct}%) — unfunded delivery"
        return f"on plan ({pct}%)"

    def validate(self) -> None:
        if self.funding_source not in FUNDING_SOURCES:
            raise ValidationError(f"Unknown funding source '{self.funding_source}'")
        if not self.academic_year.strip():
            raise ValidationError("A funding allocation needs an academic year")
        if self.allocated < 0:
            raise ValidationError("Allocation cannot be negative")
        if self.earned < 0:
            raise ValidationError("Earned income cannot be negative")
        if self.learner_count < 0:
            raise ValidationError("Learner count cannot be negative")

    def to_row(self) -> dict:
        return {
            "funding_source": self.funding_source,
            "academic_year": self.academic_year.strip(),
            "allocated": round(float(self.allocated), 2),
            "earned": round(float(self.earned), 2),
            "learner_count": int(self.learner_count),
            "notes": self.notes.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "FundingAllocation":
        d = dict(row)
        return cls(
            allocation_id=d.get("allocation_id"),
            funding_source=d.get("funding_source") or FUNDING_SOURCES[0],
            academic_year=d.get("academic_year") or "",
            allocated=float(d.get("allocated") or 0),
            earned=float(d.get("earned") or 0),
            learner_count=int(d.get("learner_count") or 0),
            notes=d.get("notes") or "",
        )


__all__ = [
    "BAND_RATES",
    "COMPLETION_SHARE",
    "ON_PROGRAMME_SHARE",
    "FundingAllocation",
    "band_for_hours",
    "earned_income",
]
