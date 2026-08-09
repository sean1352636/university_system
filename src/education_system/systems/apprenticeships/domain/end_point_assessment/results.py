"""End-Point Assessment: organisations, bookings, results and resits.

The EPA is independent by design — the organisation that trained the
apprentice does not grade them. That independence is the reason the
end-point assessor role exists in this system at all, and why the
provider's formative judgements are deliberately not visible on the
assessor's screens.

A standard is assessed by several *methods* (a professional discussion,
a practical observation, a project report). Each method is booked,
sat and graded separately; the overall grade is derived from all of
them by :func:`overall_grade`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

# Ranked worst to best, so a grade's index is its quality.
_GRADE_ORDER: tuple[str, ...] = config.EPA_GRADES


@dataclass
class EPAO:
    """An End-Point Assessment Organisation."""

    epao_id: int
    name: str
    contact_name: str | None = None
    contact_email: str | None = None
    phone: str | None = None
    standards: str | None = None
    active: bool = True
    created_at: str = ""

    @property
    def standard_list(self) -> list[str]:
        if not self.standards:
            return []
        return [s.strip().upper() for s in self.standards.split(",") if s.strip()]

    def can_assess(self, programme_reference: str | None) -> bool:
        """Is this EPAO approved for a standard?

        An EPAO with no standards listed is treated as able to assess
        anything — that is how a newly added organisation behaves before
        anyone has filled in its approvals, and blocking bookings on
        missing reference data would be worse than permitting them.
        """
        if not self.standard_list:
            return True
        return (programme_reference or "").strip().upper() in self.standard_list


@dataclass
class EPABooking:
    """One assessment method booked for one apprentice."""

    booking_id: int
    apprentice_id: int
    method: str
    epao_id: int | None = None
    scheduled_date: str | None = None
    scheduled_time: str | None = None
    location: str | None = None
    assessor_name: str | None = None
    assessor_username: str | None = None
    status: str = "Requested"
    resit_of: int | None = None
    notes: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_resit(self) -> bool:
        return self.resit_of is not None

    @property
    def is_open(self) -> bool:
        """Still to be graded."""
        return self.status in ("Requested", "Scheduled", "In Progress")

    @property
    def when(self) -> str:
        """Date and time as one display string."""
        if not self.scheduled_date:
            return config.EMPTY_CELL
        if self.scheduled_time:
            return f"{self.scheduled_date} {self.scheduled_time}"
        return self.scheduled_date


@dataclass
class EPAResult:
    """The graded outcome of one sitting."""

    result_id: int
    booking_id: int
    apprentice_id: int
    method: str
    grade: str
    assessed_date: str
    assessor_name: str | None = None
    feedback: str | None = None
    attempt: int = 1
    created_at: str = ""

    @property
    def is_pass(self) -> bool:
        return self.grade in config.PASSING_GRADES


@dataclass
class EPAResit:
    """A request to sit a failed method again."""

    resit_id: int
    apprentice_id: int
    result_id: int
    resit_type: str
    reason: str | None = None
    training_plan: str | None = None
    requested_at: str = ""
    requested_by: str | None = None
    status: str = "Requested"
    booking_id: int | None = None

    @property
    def needs_further_training(self) -> bool:
        """Retakes require more training before re-sitting; resits don't."""
        return self.resit_type == "Retake"


@dataclass
class EPAProgress:
    """An apprentice's whole EPA position across every method."""

    apprentice_id: int
    required_methods: list[str] = field(default_factory=list)
    bookings: list[EPABooking] = field(default_factory=list)
    results: list[EPAResult] = field(default_factory=list)
    resits: list[EPAResit] = field(default_factory=list)

    @property
    def best_results(self) -> dict[str, EPAResult]:
        """The best result per method.

        A resit supersedes the fail that preceded it, so the highest
        grade achieved for each method is what counts — not the latest,
        which would let an administrative re-entry downgrade someone.
        """
        best: dict[str, EPAResult] = {}
        for result in self.results:
            current = best.get(result.method)
            if current is None or _grade_rank(result.grade) > _grade_rank(current.grade):
                best[result.method] = result
        return best

    @property
    def methods_passed(self) -> list[str]:
        return [m for m, r in self.best_results.items() if r.is_pass]

    @property
    def methods_outstanding(self) -> list[str]:
        """Required methods not yet passed, in the standard's order."""
        passed = set(self.methods_passed)
        return [m for m in self.required_methods if m not in passed]

    @property
    def is_complete(self) -> bool:
        """Every required method passed."""
        return bool(self.required_methods) and not self.methods_outstanding

    @property
    def overall(self) -> str | None:
        """The apprenticeship's overall grade, or None while incomplete."""
        if not self.is_complete:
            return None
        return overall_grade([r.grade for r in self.best_results.values()])

    @property
    def attempts_by_method(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in self.results:
            counts[result.method] = counts.get(result.method, 0) + 1
        return counts

    def resits_remaining(self, method: str) -> int:
        """How many further attempts *method* still allows."""
        used = max(0, self.attempts_by_method.get(method, 0) - 1)
        return max(0, config.MAX_RESITS - used)


def overall_grade(grades: list[str]) -> str:
    """Combine per-method grades into the apprenticeship's overall grade.

    The aggregation rule is deliberately pessimistic: the overall grade
    is the *lowest* achieved across the methods. Someone with a
    distinction in the project and a bare pass in the discussion has
    passed, not distinguished — averaging would let a strong showing in
    one method paper over a weak one in another.
    """
    if not grades:
        raise ValidationError("No grades to combine")
    unknown = [g for g in grades if g not in _GRADE_ORDER]
    if unknown:
        raise ValidationError(f"Unrecognised grade(s): {', '.join(sorted(set(unknown)))}")
    if any(g == "Fail" for g in grades):
        return "Fail"
    return min(grades, key=_grade_rank)


def validate_grade(grade: str | None) -> str:
    """Check a grade against the published set."""
    cleaned = (grade or "").strip().title()
    if cleaned not in config.EPA_GRADES:
        allowed = ", ".join(config.EPA_GRADES)
        raise ValidationError(f"Grade must be one of: {allowed}")
    return cleaned


def validate_method(method: str | None) -> str:
    """Check an assessment method against the published set."""
    cleaned = (method or "").strip()
    if not cleaned:
        raise ValidationError("Assessment method is required")
    if cleaned not in config.EPA_METHODS:
        allowed = ", ".join(config.EPA_METHODS)
        raise ValidationError(f"Assessment method must be one of: {allowed}")
    return cleaned


def validate_resit_type(resit_type: str | None) -> str:
    """Check a resit type against the published set."""
    cleaned = (resit_type or "").strip().title()
    if cleaned not in config.RESIT_TYPES:
        allowed = ", ".join(config.RESIT_TYPES)
        raise ValidationError(f"Resit type must be one of: {allowed}")
    return cleaned


def require_booking_status(current: str, target: str) -> None:
    """Check a booking status move is legal."""
    if target not in config.EPA_BOOKING_STATUSES:
        raise ValidationError(f"{target!r} is not a booking status")
    allowed: dict[str, frozenset[str]] = {
        "Requested": frozenset({"Scheduled", "Cancelled"}),
        "Scheduled": frozenset({"In Progress", "Assessed", "Cancelled", "Requested"}),
        "In Progress": frozenset({"Assessed", "Cancelled"}),
        # Grading is final; a correction is a new sitting, not an edit.
        "Assessed": frozenset(),
        "Cancelled": frozenset({"Requested"}),
    }
    if target not in allowed.get(current, frozenset()):
        options = ", ".join(sorted(allowed.get(current, frozenset()))) or "nothing"
        raise ValidationError(
            f"Cannot move booking from {current!r} to {target!r}. Allowed: {options}"
        )


def _grade_rank(grade: str) -> int:
    try:
        return _GRADE_ORDER.index(grade)
    except ValueError:
        return -1
