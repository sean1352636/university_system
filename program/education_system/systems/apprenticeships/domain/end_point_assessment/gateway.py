"""Gateway: the checkpoint between training and assessment.

Nobody sits an End-Point Assessment until they pass through gateway.
The provider, employer and apprentice agree the apprentice is ready; the
EPAO then accepts the booking. Every requirement in
``config.GATEWAY_REQUIREMENTS`` must be met first.

Most checks are *automatic* — the system already knows whether the
off-the-job target is met or the portfolio is complete, so it computes
them and refuses to let anyone tick them by hand. The rest are human
judgements an approver records. Keeping that distinction explicit is the
point of this module: an auditor asking "who decided this apprentice was
ready?" gets a real answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

REQUIREMENT_LABELS: dict[str, str] = dict(config.GATEWAY_REQUIREMENTS)

REQUIREMENT_KEYS: tuple[str, ...] = tuple(k for k, _ in config.GATEWAY_REQUIREMENTS)

# Requirements the system derives from data it already holds. These are
# recomputed on every read and cannot be overridden by hand — letting an
# admin tick "off-the-job hours met" when the log says otherwise is
# precisely the failure mode gateway exists to prevent.
AUTOMATIC_REQUIREMENTS: frozenset[str] = frozenset({
    "otj_hours", "english", "maths", "portfolio", "reviews", "minimum_duration",
})

# The one requirement that is a human decision.
MANUAL_REQUIREMENTS: frozenset[str] = frozenset({"employer_sign_off"})


@dataclass
class GatewayCheck:
    """One requirement's state for one apprentice."""

    requirement_key: str
    met: bool
    automatic: bool
    evidence_note: str | None = None
    checked_by: str | None = None
    checked_at: str | None = None
    # Why an automatic check failed, in words a tutor can act on:
    # "38.5 of 240 hours logged".
    detail: str | None = None

    @property
    def label(self) -> str:
        return REQUIREMENT_LABELS.get(self.requirement_key, self.requirement_key)


@dataclass
class GatewayRecord:
    """An apprentice's gateway state and every requirement beneath it."""

    apprentice_id: int
    status: str = "Not Ready"
    gateway_id: int | None = None
    requested_at: str | None = None
    requested_by: str | None = None
    decided_at: str | None = None
    decided_by: str | None = None
    decision_notes: str | None = None
    checks: list[GatewayCheck] = field(default_factory=list)

    @property
    def met_count(self) -> int:
        return sum(1 for c in self.checks if c.met)

    @property
    def total_count(self) -> int:
        return len(self.checks)

    @property
    def outstanding(self) -> list[GatewayCheck]:
        """Requirements still to satisfy, in the published order."""
        return [c for c in self.checks if not c.met]

    @property
    def is_ready(self) -> bool:
        """Every requirement met, so gateway may be requested."""
        return bool(self.checks) and not self.outstanding

    @property
    def percent_complete(self) -> float:
        if not self.checks:
            return 0.0
        return round(self.met_count / len(self.checks) * 100, 1)

    @property
    def is_approved(self) -> bool:
        return self.status == "Approved"

    def summary_line(self) -> str:
        """One-line status for list screens and CLI tables."""
        if self.is_approved:
            return f"Approved {self.decided_at or ''}".strip()
        if self.status == "Rejected":
            return "Rejected — returned to training"
        if self.status == "Requested":
            return f"Awaiting EPAO decision ({self.met_count}/{self.total_count})"
        return f"{self.met_count}/{self.total_count} requirements met"


def evaluate(
    *,
    apprentice_id: int,
    status: str = "Not Ready",
    otj_target: float = 0.0,
    otj_approved: float = 0.0,
    english_status: str | None = None,
    maths_status: str | None = None,
    ksbs_total: int = 0,
    ksbs_competent: int = 0,
    reviews_outstanding: int = 0,
    reviews_held: int = 0,
    start_date: str | None = None,
    employer_signed_off: bool = False,
    employer_note: str | None = None,
    employer_checked_by: str | None = None,
    employer_checked_at: str | None = None,
    as_of: str | None = None,
) -> list[GatewayCheck]:
    """Work out where an apprentice stands against every requirement.

    Pure: the caller gathers the facts, this decides what they mean. The
    ``detail`` on each check is the message the UI shows next to a failed
    requirement, so it names the actual shortfall rather than restating
    the rule.
    """
    today = as_of or date.today().isoformat()
    checks: list[GatewayCheck] = []

    # ── Off-the-job hours ──
    otj_met = otj_target > 0 and otj_approved >= otj_target
    checks.append(GatewayCheck(
        requirement_key="otj_hours",
        met=otj_met,
        automatic=True,
        detail=(
            f"{otj_approved:.1f} of {otj_target:.1f} approved hours"
            if otj_target > 0 else "No target set — check the programme dates"
        ),
    ))

    # ── Functional skills ──
    for key, subject_status in (("english", english_status), ("maths", maths_status)):
        achieved = subject_status in ("Achieved", "Exempt")
        checks.append(GatewayCheck(
            requirement_key=key,
            met=achieved,
            automatic=True,
            detail=subject_status or "Not recorded",
        ))

    # ── Portfolio ──
    portfolio_met = ksbs_total > 0 and ksbs_competent >= ksbs_total
    checks.append(GatewayCheck(
        requirement_key="portfolio",
        met=portfolio_met,
        automatic=True,
        detail=(
            f"{ksbs_competent} of {ksbs_total} KSBs competent"
            if ksbs_total > 0 else "Programme has no KSBs defined"
        ),
    ))

    # ── Progress reviews ──
    # At least one review must have happened, and none may be left
    # unsigned: an unsigned review is not evidence of anything.
    reviews_met = reviews_held > 0 and reviews_outstanding == 0
    if reviews_held == 0:
        review_detail = "No progress reviews held"
    elif reviews_outstanding:
        review_detail = f"{reviews_outstanding} review(s) awaiting signature"
    else:
        review_detail = f"{reviews_held} review(s) complete"
    checks.append(GatewayCheck(
        requirement_key="reviews",
        met=reviews_met,
        automatic=True,
        detail=review_detail,
    ))

    # ── Employer sign-off (the one human judgement) ──
    checks.append(GatewayCheck(
        requirement_key="employer_sign_off",
        met=bool(employer_signed_off),
        automatic=False,
        evidence_note=employer_note,
        checked_by=employer_checked_by,
        checked_at=employer_checked_at,
        detail="Confirmed" if employer_signed_off else "Awaiting employer confirmation",
    ))

    # ── Minimum practical period ──
    days_served = _days_between(start_date, today)
    duration_met = days_served >= config.MINIMUM_PRACTICAL_PERIOD_DAYS
    if start_date is None:
        duration_detail = "No start date recorded"
    elif duration_met:
        duration_detail = f"{days_served} days served"
    else:
        short_by = config.MINIMUM_PRACTICAL_PERIOD_DAYS - days_served
        duration_detail = f"{days_served} days served — {short_by} short of 12 months"
    checks.append(GatewayCheck(
        requirement_key="minimum_duration",
        met=duration_met,
        automatic=True,
        detail=duration_detail,
    ))

    # Return in the published order so every screen lists them the same.
    by_key = {c.requirement_key: c for c in checks}
    return [by_key[k] for k in REQUIREMENT_KEYS if k in by_key]


def require_ready(record: GatewayRecord) -> None:
    """Raise unless every requirement is met.

    The error names what is actually outstanding — an approver who is
    told "3 requirements outstanding" has to go hunting; one told which
    three can fix them.
    """
    if not record.checks:
        raise ValidationError("Gateway requirements have not been evaluated yet")
    outstanding = record.outstanding
    if outstanding:
        lines = "; ".join(
            f"{c.label}" + (f" ({c.detail})" if c.detail else "")
            for c in outstanding
        )
        raise ValidationError(f"Not ready for gateway — outstanding: {lines}")


def require_status(current: str, target: str) -> None:
    """Check a gateway status move is legal."""
    if target not in config.GATEWAY_STATUSES:
        raise ValidationError(f"{target!r} is not a gateway status")
    allowed: dict[str, frozenset[str]] = {
        "Not Ready": frozenset({"Requested"}),
        # An EPAO can send a request back, and a provider can withdraw it.
        "Requested": frozenset({"Approved", "Rejected", "Not Ready"}),
        # Approval is reversible only by rejection — for instance if the
        # apprentice leaves employment between gateway and the EPA date.
        "Approved": frozenset({"Rejected"}),
        # A rejected apprentice goes back to training and re-requests.
        "Rejected": frozenset({"Not Ready", "Requested"}),
    }
    if target not in allowed.get(current, frozenset()):
        options = ", ".join(sorted(allowed.get(current, frozenset()))) or "nothing"
        raise ValidationError(
            f"Cannot move gateway from {current!r} to {target!r}. Allowed: {options}"
        )


def _days_between(from_iso: str | None, to_iso: str) -> int:
    if not from_iso:
        return 0
    try:
        start = date.fromisoformat(from_iso)
        end = date.fromisoformat(to_iso)
    except ValueError:
        return 0
    return max(0, (end - start).days)
