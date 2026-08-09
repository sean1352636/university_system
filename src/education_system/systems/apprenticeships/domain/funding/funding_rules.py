"""Who pays for an apprenticeship, and when.

Three routes, decided by the employer's pay bill, headcount and the
apprentice's age at start:

* **Levy** — a large employer has already paid the levy and draws the
  cost down from their digital account. Nothing further to collect.
* **Fully funded** — a small employer taking on a young apprentice pays
  nothing; the government covers the lot.
* **Co-investment** — everyone else. The government pays the standard
  share and the employer is invoiced the rest.

The provider is then paid monthly across the practical period, with a
fifth of the price withheld until the EPA completes. That withholding is
what makes completion — rather than enrolment — the thing the provider
is paid for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError


@dataclass
class FundingRecord:
    """The agreed price and split for one apprenticeship."""

    funding_id: int
    apprentice_id: int
    funding_model: str
    band: int
    negotiated_price: float
    employer_contribution: float = 0.0
    government_contribution: float = 0.0
    additional_payments: float = 0.0
    notes: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def band_maximum(self) -> float:
        return config.FUNDING_BANDS.get(self.band, 0.0)

    @property
    def headroom(self) -> float:
        """How far below the band cap the negotiated price sits."""
        return round(self.band_maximum - self.negotiated_price, 2)

    @property
    def total_value(self) -> float:
        return round(self.negotiated_price + self.additional_payments, 2)


@dataclass
class Payment:
    """One scheduled or settled instalment."""

    payment_id: int
    apprentice_id: int
    due_date: str
    amount: float
    payment_type: str = "Monthly"
    status: str = "Scheduled"
    claimed_at: str | None = None
    paid_at: str | None = None
    notes: str | None = None
    created_at: str = ""

    @property
    def is_settled(self) -> bool:
        return self.status == "Paid"

    @property
    def is_overdue(self) -> bool:
        """Past its due date and still unclaimed."""
        return self.status == "Scheduled" and self.due_date < date.today().isoformat()


@dataclass
class FundingSummary:
    """An apprenticeship's money position, for the funding screens."""

    record: FundingRecord | None
    payments: list[Payment] = field(default_factory=list)

    @property
    def scheduled_total(self) -> float:
        return round(sum(p.amount for p in self.payments), 2)

    @property
    def paid_total(self) -> float:
        return round(sum(p.amount for p in self.payments if p.status == "Paid"), 2)

    @property
    def claimed_total(self) -> float:
        return round(sum(p.amount for p in self.payments if p.status == "Claimed"), 2)

    @property
    def withheld_total(self) -> float:
        return round(
            sum(p.amount for p in self.payments if p.status in ("Withheld", "Clawed Back")), 2
        )

    @property
    def outstanding_total(self) -> float:
        return round(self.scheduled_total - self.paid_total, 2)

    @property
    def overdue_payments(self) -> list[Payment]:
        return [p for p in self.payments if p.is_overdue]


@dataclass
class LevyPosition:
    """An employer's levy liability for a year."""

    paybill: float
    levy_due: float
    allowance_used: float
    is_levy_payer: bool

    @property
    def monthly_levy(self) -> float:
        return round(self.levy_due / 12, 2)


def levy_position(paybill: float | None) -> LevyPosition:
    """Work out an employer's annual levy from their pay bill.

    Half a percent of the pay bill, less a fixed allowance. The allowance
    is why the levy only bites above the threshold: below it the
    allowance cancels the charge entirely.
    """
    bill = float(paybill or 0.0)
    if bill < 0:
        raise ValidationError("Pay bill cannot be negative")
    gross = bill * config.LEVY_RATE
    due = max(0.0, gross - config.LEVY_ALLOWANCE)
    return LevyPosition(
        paybill=round(bill, 2),
        levy_due=round(due, 2),
        allowance_used=round(min(gross, config.LEVY_ALLOWANCE), 2),
        is_levy_payer=bill > config.LEVY_THRESHOLD_PAYBILL,
    )


def determine_model(
    *,
    is_levy_payer: bool,
    is_small_employer: bool,
    age_at_start: int | None,
) -> str:
    """Which of the three funding routes applies.

    Levy status wins outright — a large employer draws from their account
    whatever the apprentice's age. Below that, a small employer with a
    young apprentice pays nothing; everyone else co-invests.
    """
    if is_levy_payer:
        return "Levy"
    young = age_at_start is not None and age_at_start <= config.SMALL_EMPLOYER_FULL_FUNDING_MAX_AGE
    if is_small_employer and young:
        return "Fully funded"
    return "Co-investment"


def split_contributions(price: float, funding_model: str) -> tuple[float, float]:
    """Split a negotiated price into (employer, government) shares."""
    if price < 0:
        raise ValidationError("Negotiated price cannot be negative")
    if funding_model == "Levy":
        # Drawn wholly from the employer's digital account. It is the
        # employer's own levy money, so it counts as their contribution.
        return round(price, 2), 0.0
    if funding_model == "Fully funded":
        return 0.0, round(price, 2)
    if funding_model == "Co-investment":
        government = round(price * config.CO_INVESTMENT_GOVERNMENT_SHARE, 2)
        return round(price - government, 2), government
    allowed = ", ".join(config.FUNDING_MODELS)
    raise ValidationError(f"Funding model must be one of: {allowed}")


def validate_price(price: object, band: int) -> float:
    """Check a negotiated price against its funding band.

    A price above the band cap is not merely unusual, it is unfundable —
    the excess would have to be paid by the employer outside the system
    entirely, so the service refuses it rather than storing a figure that
    will never be honoured.
    """
    try:
        value = float(str(price).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("Negotiated price must be a number") from exc
    if value < 0:
        raise ValidationError("Negotiated price cannot be negative")
    cap = config.FUNDING_BANDS.get(band)
    if cap is None:
        raise ValidationError(f"Unknown funding band {band}")
    if value > cap:
        raise ValidationError(
            f"Negotiated price {config.CURRENCY_SYMBOL}{value:,.2f} exceeds the band "
            f"{band} maximum of {config.CURRENCY_SYMBOL}{cap:,.2f}"
        )
    return round(value, 2)


def build_schedule(
    *,
    price: float,
    start_date: str,
    planned_end_date: str,
) -> list[tuple[str, float, str]]:
    """The instalment plan for one apprenticeship.

    Returns ``(due_date, amount, payment_type)`` tuples: monthly
    instalments across the practical period, then the withheld
    completion balance on the planned end date. Rounding differences are
    absorbed by the completion payment so the instalments stay tidy and
    the total is exact.
    """
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(planned_end_date)
    except ValueError as exc:
        raise ValidationError("Start and planned end dates must be YYYY-MM-DD") from exc
    if end <= start:
        raise ValidationError("Planned end date must be after the start date")
    if price <= 0:
        return []

    months = max(1, (end.year - start.year) * 12 + (end.month - start.month))
    completion = round(price * config.COMPLETION_PAYMENT_SHARE, 2)
    monthly_pot = price - completion
    instalment = round(monthly_pot / months, 2)

    schedule: list[tuple[str, float, str]] = []
    for index in range(months):
        total_month = start.month - 1 + index + 1
        year = start.year + total_month // 12
        month = total_month % 12 + 1
        # Bill on the 1st: the funding month is a calendar month, and
        # anchoring on the start day would create 29th-of-February gaps.
        schedule.append((date(year, month, 1).isoformat(), instalment, "Monthly"))

    # Give the completion payment whatever rounding left behind, so the
    # schedule always sums to the negotiated price exactly.
    drift = round(price - (instalment * months) - completion, 2)
    schedule.append((end.isoformat(), round(completion + drift, 2), "Completion"))
    return schedule


def require_payment_status(current: str, target: str) -> None:
    """Check a payment status move is legal."""
    if target not in config.PAYMENT_STATUSES:
        raise ValidationError(f"{target!r} is not a payment status")
    allowed: dict[str, frozenset[str]] = {
        "Scheduled": frozenset({"Claimed", "Withheld"}),
        "Claimed": frozenset({"Paid", "Withheld", "Scheduled"}),
        # Money already paid can only be recovered, not un-paid.
        "Paid": frozenset({"Clawed Back"}),
        "Withheld": frozenset({"Scheduled", "Claimed"}),
        "Clawed Back": frozenset(),
    }
    if target not in allowed.get(current, frozenset()):
        options = ", ".join(sorted(allowed.get(current, frozenset()))) or "nothing"
        raise ValidationError(
            f"Cannot move payment from {current!r} to {target!r}. Allowed: {options}"
        )
