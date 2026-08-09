"""Apprentice records.

An apprentice is a person who is simultaneously an employee and a
learner. That dual identity drives the shape of this record: it carries
both education fields (programme, tutor, off-the-job target) and
employment fields (employer, workplace, contracted hours), and a change
to either side can invalidate the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.apprenticeships import config


class ValidationError(ValueError):
    """Input the domain refuses to store.

    A plain ``ValueError`` subclass so callers that only care that
    something went wrong can catch the builtin, while interfaces catch
    this specifically and show the message to the user verbatim.
    """


@dataclass
class Apprentice:
    """One apprentice's core record, as stored."""

    apprentice_id: int
    uln: str | None
    given_name: str
    family_name: str
    date_of_birth: str | None
    email: str | None
    phone: str | None
    username: str | None
    programme_id: int | None
    employer_id: int | None
    workplace_id: int | None
    tutor_id: int | None
    status: str
    start_date: str | None
    planned_end_date: str | None
    actual_end_date: str | None
    weekly_hours: float
    funding_model: str | None
    prior_learning: str | None
    support_needs: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}".strip()

    @property
    def is_active(self) -> bool:
        return self.status in config.ACTIVE_STATUSES

    @property
    def age(self) -> int | None:
        """Age in whole years today, or None if no date of birth."""
        return years_between(self.date_of_birth, date.today().isoformat())

    @property
    def age_at_start(self) -> int | None:
        """Age when the programme began — what funding bands key off."""
        return years_between(self.date_of_birth, self.start_date)


@dataclass
class ApprenticeSummary:
    """An apprentice joined to the labels every list screen shows.

    Built by a single joined query rather than N+1 lookups, because the
    cohort screens routinely render several hundred rows.
    """

    apprentice: Apprentice
    programme_title: str | None = None
    programme_reference: str | None = None
    programme_level: int | None = None
    employer_name: str | None = None
    workplace_name: str | None = None
    tutor_name: str | None = None
    # Progress, all derived — never stored, so they cannot go stale.
    otj_hours_logged: float = 0.0
    otj_hours_target: float = 0.0
    ksbs_total: int = 0
    ksbs_competent: int = 0
    open_reviews: int = 0
    gateway_status: str = "Not Ready"

    @property
    def full_name(self) -> str:
        return self.apprentice.full_name

    @property
    def otj_percent(self) -> float:
        if self.otj_hours_target <= 0:
            return 0.0
        return min(100.0, round(self.otj_hours_logged / self.otj_hours_target * 100, 1))

    @property
    def ksb_percent(self) -> float:
        if self.ksbs_total <= 0:
            return 0.0
        return round(self.ksbs_competent / self.ksbs_total * 100, 1)

    @property
    def progress_percent(self) -> float:
        """How far through the programme they are by elapsed time.

        Time-based rather than achievement-based on purpose: comparing
        this against ``otj_percent`` is exactly how a tutor spots someone
        drifting behind.
        """
        start, end = self.apprentice.start_date, self.apprentice.planned_end_date
        if not start or not end:
            return 0.0
        try:
            d_start = date.fromisoformat(start)
            d_end = date.fromisoformat(end)
        except ValueError:
            return 0.0
        span = (d_end - d_start).days
        if span <= 0:
            return 100.0
        elapsed = (date.today() - d_start).days
        return max(0.0, min(100.0, round(elapsed / span * 100, 1)))

    @property
    def is_behind(self) -> bool:
        """Logged fewer off-the-job hours than elapsed time implies.

        A 5-point tolerance stops a normal week's lag being flagged.
        """
        return self.otj_percent + 5 < self.progress_percent


def years_between(from_iso: str | None, to_iso: str | None) -> int | None:
    """Whole years between two ISO dates, or None if either is missing."""
    if not from_iso or not to_iso:
        return None
    try:
        d_from = date.fromisoformat(from_iso)
        d_to = date.fromisoformat(to_iso)
    except ValueError:
        return None
    years = d_to.year - d_from.year
    if (d_to.month, d_to.day) < (d_from.month, d_from.day):
        years -= 1
    return years


def planned_end_for(start_iso: str, duration_months: int, weekly_hours: float) -> str:
    """When a programme starting *start_iso* should finish.

    Part-time apprentices get a proportionally longer practical period:
    the off-the-job requirement is expressed per week at full time, so
    someone working 15 hours needs twice as many weeks to accumulate the
    same training. Below the 30-hour norm the duration is scaled up,
    never down — working extra hours does not shorten an apprenticeship.
    """
    try:
        start = date.fromisoformat(start_iso)
    except ValueError as exc:
        raise ValidationError(f"Start date must be YYYY-MM-DD, got {start_iso!r}") from exc
    if duration_months <= 0:
        raise ValidationError("Programme duration must be at least one month")

    months = duration_months
    if 0 < weekly_hours < config.OTJ_STANDARD_WEEKLY_HOURS:
        months = round(months * config.OTJ_STANDARD_WEEKLY_HOURS / weekly_hours)

    # Calendar-month arithmetic without a dateutil dependency.
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, _days_in_month(year, month))
    end = date(year, month, day)

    # The statutory minimum practical period is 12 months regardless.
    floor = start + timedelta(days=config.MINIMUM_PRACTICAL_PERIOD_DAYS)
    return max(end, floor).isoformat()


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def validate_uln(uln: str | None) -> str | None:
    """Check a Unique Learner Number.

    A ULN is exactly 10 digits. It is optional on an applicant record —
    providers routinely enrol before the number comes back — but once
    supplied it must be well formed, because it is the key every
    external funding return is matched on.
    """
    if uln is None or not uln.strip():
        return None
    cleaned = uln.strip().replace(" ", "")
    if not cleaned.isdigit() or len(cleaned) != 10:
        raise ValidationError("ULN must be exactly 10 digits")
    return cleaned
