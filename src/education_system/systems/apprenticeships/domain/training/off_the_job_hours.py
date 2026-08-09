"""Off-the-job training hours.

Off-the-job training is learning that happens within paid working hours
but away from the day job. It is the single most audited number in the
whole apprenticeship: fall short and the funding is clawed back, so the
target is computed from the programme dates rather than stored, and the
running total only counts hours an approver has actually signed off.

The statutory minimum is six hours a week averaged across the practical
period. This module turns that rule into a target, a running total, and
the "are they on track?" judgement every dashboard leans on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

# Weeks an apprentice is not expected to train: statutory leave plus
# bank holidays, spread across a year. Excluding them stops the target
# implying someone should have logged hours over Christmas.
NON_TRAINING_WEEKS_PER_YEAR: float = 6.0

WEEKS_PER_YEAR: float = 52.0

# How far behind the elapsed-time pace counts as off track, in
# percentage points. Roughly one week's slippage on a year-long
# programme — enough to ignore normal noise, tight enough to catch drift
# while there is still time to fix it.
DRIFT_TOLERANCE_PERCENT: float = 5.0


@dataclass
class OTJEntry:
    """One logged off-the-job training activity."""

    entry_id: int
    apprentice_id: int
    activity_date: str
    hours: float
    activity_type: str
    description: str
    ksb_codes: str | None = None
    status: str = "Draft"
    session_id: int | None = None
    submitted_at: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    decision_note: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def counts_towards_target(self) -> bool:
        """Only approved hours count.

        Draft and submitted hours are shown to the apprentice so they can
        see their own effort, but an auditor only accepts hours a tutor
        or employer has signed, so those are the ones that move the
        total.
        """
        return self.status == "Approved"

    @property
    def is_editable(self) -> bool:
        """Approved hours are locked; rejected ones can be reworked."""
        return self.status in ("Draft", "Rejected")

    @property
    def ksb_list(self) -> list[str]:
        if not self.ksb_codes:
            return []
        return [c.strip().upper() for c in self.ksb_codes.split(",") if c.strip()]


@dataclass
class OTJSummary:
    """An apprentice's off-the-job position at a point in time."""

    apprentice_id: int
    target_hours: float
    approved_hours: float
    pending_hours: float
    draft_hours: float
    entry_count: int
    # Hours the target implies they should have logged by today.
    expected_to_date: float
    weeks_elapsed: float
    weeks_total: float

    @property
    def remaining_hours(self) -> float:
        return max(0.0, round(self.target_hours - self.approved_hours, 2))

    @property
    def percent_complete(self) -> float:
        if self.target_hours <= 0:
            return 0.0
        return min(100.0, round(self.approved_hours / self.target_hours * 100, 1))

    @property
    def expected_percent(self) -> float:
        if self.target_hours <= 0:
            return 0.0
        return min(100.0, round(self.expected_to_date / self.target_hours * 100, 1))

    @property
    def hours_behind(self) -> float:
        """How many approved hours short of today's pace they are."""
        return max(0.0, round(self.expected_to_date - self.approved_hours, 2))

    @property
    def is_on_track(self) -> bool:
        return self.percent_complete + DRIFT_TOLERANCE_PERCENT >= self.expected_percent

    @property
    def target_met(self) -> bool:
        """Enough approved hours to pass the gateway check."""
        return self.target_hours > 0 and self.approved_hours >= self.target_hours

    @property
    def rag_rating(self) -> str:
        """Traffic light for the dashboards.

        Green once the target is met or the pace is being held; red once
        they are more than twice the tolerance behind, because that is no
        longer recoverable by a good fortnight.
        """
        if self.target_met or self.is_on_track:
            return "Green"
        if self.percent_complete + (DRIFT_TOLERANCE_PERCENT * 2) >= self.expected_percent:
            return "Amber"
        return "Red"

    @property
    def weekly_hours_needed(self) -> float:
        """Average weekly hours needed from now to hit the target.

        What a tutor actually says out loud in a review: "you need four
        hours a week from here."
        """
        weeks_left = max(0.0, self.weeks_total - self.weeks_elapsed)
        if weeks_left <= 0:
            return self.remaining_hours
        return round(self.remaining_hours / weeks_left, 1)


def training_weeks(start_iso: str | None, end_iso: str | None) -> float:
    """Trainable weeks between two dates, net of leave.

    Returns 0 for missing or reversed dates rather than raising: the
    dashboards call this for every apprentice including applicants who
    have no start date yet, and a zero target reads correctly there.
    """
    if not start_iso or not end_iso:
        return 0.0
    try:
        start = date.fromisoformat(start_iso)
        end = date.fromisoformat(end_iso)
    except ValueError:
        return 0.0
    days = (end - start).days
    if days <= 0:
        return 0.0
    weeks = days / 7.0
    leave = (weeks / WEEKS_PER_YEAR) * NON_TRAINING_WEEKS_PER_YEAR
    return max(0.0, round(weeks - leave, 2))


def target_hours(
    start_iso: str | None,
    end_iso: str | None,
    weekly_hours: float = config.OTJ_STANDARD_WEEKLY_HOURS,
) -> float:
    """The off-the-job hours an apprenticeship must deliver.

    Six hours a week at full time, pro-rated for part-timers. Note the
    pro-rating cuts the weekly requirement but the planned end date was
    already extended to compensate (see ``models.planned_end_for``), so
    the total lands in much the same place — a part-timer trains at a
    slower rate for longer, not less overall.
    """
    weeks = training_weeks(start_iso, end_iso)
    if weeks <= 0:
        return 0.0
    rate = config.OTJ_MINIMUM_HOURS_PER_WEEK
    if 0 < weekly_hours < config.OTJ_STANDARD_WEEKLY_HOURS:
        rate = rate * weekly_hours / config.OTJ_STANDARD_WEEKLY_HOURS
    return round(weeks * rate, 1)


def build_summary(
    apprentice_id: int,
    *,
    start_iso: str | None,
    end_iso: str | None,
    weekly_hours: float,
    approved: float,
    pending: float,
    draft: float,
    entry_count: int,
    as_of: str | None = None,
) -> OTJSummary:
    """Assemble the summary from totals the repository has already added up.

    Taking the sums as arguments keeps this function pure and lets the
    repository do the aggregation in one SQL pass instead of loading
    every entry into Python.
    """
    total_weeks = training_weeks(start_iso, end_iso)
    today = as_of or date.today().isoformat()
    elapsed_weeks = min(total_weeks, training_weeks(start_iso, today))
    target = target_hours(start_iso, end_iso, weekly_hours)
    expected = round(target * (elapsed_weeks / total_weeks), 1) if total_weeks > 0 else 0.0
    return OTJSummary(
        apprentice_id=apprentice_id,
        target_hours=target,
        approved_hours=round(approved, 2),
        pending_hours=round(pending, 2),
        draft_hours=round(draft, 2),
        entry_count=entry_count,
        expected_to_date=expected,
        weeks_elapsed=elapsed_weeks,
        weeks_total=total_weeks,
    )


def validate_hours(value: object) -> float:
    """Check a single entry's hours.

    Capped at 24 because the value is hours, not days — a typo that
    turns 7 into 70 would otherwise silently satisfy a gateway check.
    """
    try:
        hours = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("Hours must be a number") from exc
    if hours <= 0:
        raise ValidationError("Hours must be greater than zero")
    if hours > 24:
        raise ValidationError("A single activity cannot exceed 24 hours")
    return round(hours, 2)


def validate_activity_type(value: str | None) -> str:
    """Check an activity type against the recognised list."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError("Activity type is required")
    if cleaned not in config.OTJ_ACTIVITY_TYPES:
        allowed = ", ".join(config.OTJ_ACTIVITY_TYPES)
        raise ValidationError(f"Activity type must be one of: {allowed}")
    return cleaned
