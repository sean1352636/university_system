"""Employers, their workplaces, and the managers who sign for them.

The employer is a full party to an apprenticeship, not a bystander: they
sign the commitment statement, attend every progress review, confirm
off-the-job hours, and — depending on their pay bill — pay for some or
all of the training. Their size and pay bill therefore change what the
funding screens compute, which is why they live on this record rather
than being asked for at funding time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError


@dataclass
class Employer:
    """An employing organisation the provider has a contract with."""

    employer_id: int
    name: str
    company_number: str | None = None
    sector: str | None = None
    size: str | None = None
    headcount: int | None = None
    paybill: float | None = None
    address: str | None = None
    postcode: str | None = None
    status: str = "Prospect"
    contract_start: str | None = None
    contract_end: str | None = None
    notes: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_levy_payer(self) -> bool:
        """Does this employer pay the apprenticeship levy?

        Liability follows the pay bill alone. An employer who has not
        told us their pay bill is treated as non-levy, which is the safe
        default: it routes them through co-investment, where the
        contribution is calculated and invoiced rather than silently
        drawn from a digital account they may not have.
        """
        return (self.paybill or 0.0) > config.LEVY_THRESHOLD_PAYBILL

    @property
    def is_small_employer(self) -> bool:
        """Under the small-employer headcount threshold?

        Small employers taking on a young apprentice pay nothing towards
        training. Unknown headcount is treated as *not* small, so the
        system never assumes free training it cannot evidence.
        """
        headcount = self.headcount
        return headcount is not None and headcount < config.SMALL_EMPLOYER_HEADCOUNT

    @property
    def contract_is_current(self) -> bool:
        """Is the contract for services live today?"""
        if self.status != "Active":
            return False
        today = date.today().isoformat()
        if self.contract_start and self.contract_start > today:
            return False
        if self.contract_end and self.contract_end < today:
            return False
        return True

    @property
    def default_funding_model(self) -> str:
        """The funding route this employer's apprentices default to."""
        if self.is_levy_payer:
            return "Levy"
        return "Co-investment"


@dataclass
class Workplace:
    """A site where apprentices are actually placed.

    Kept separate from the employer because health and safety vetting is
    per-site: a national employer may have one approved warehouse and
    one that has lapsed, and only the approved one may take apprentices.
    """

    workplace_id: int
    employer_id: int
    name: str
    address: str | None = None
    postcode: str | None = None
    hs_checked_date: str | None = None
    hs_expiry_date: str | None = None
    active: bool = True
    created_at: str = ""

    @property
    def hs_is_current(self) -> bool:
        """Is health and safety vetting in date?"""
        if not self.hs_checked_date:
            return False
        if not self.hs_expiry_date:
            return True
        return self.hs_expiry_date >= date.today().isoformat()

    @property
    def can_host_apprentices(self) -> bool:
        return self.active and self.hs_is_current


@dataclass
class EmployerManager:
    """A named contact at an employer.

    The primary manager is the one who signs progress reviews and the
    commitment statement; ``username`` links them to a login so their
    employer portal shows only their own organisation's apprentices.
    """

    manager_id: int
    employer_id: int
    full_name: str
    job_title: str | None = None
    email: str | None = None
    phone: str | None = None
    is_primary: bool = False
    username: str | None = None
    active: bool = True
    created_at: str = ""
    # config.EMPLOYER_CONTACT_ROLES; None when nobody has said.
    contact_role: str | None = None


@dataclass
class EmployerSummary:
    """An employer with the counts the list and dashboard screens show."""

    employer: Employer
    apprentice_count: int = 0
    active_apprentices: int = 0
    workplace_count: int = 0
    completed_apprentices: int = 0
    withdrawn_apprentices: int = 0
    pending_otj_approvals: int = 0
    reviews_awaiting_signature: int = 0

    @property
    def name(self) -> str:
        return self.employer.name

    @property
    def retention_rate(self) -> float | None:
        """Share of finished apprentices who completed rather than left.

        None while nobody has finished — a brand-new employer showing
        "0% retention" would be actively misleading.
        """
        finished = self.completed_apprentices + self.withdrawn_apprentices
        if finished == 0:
            return None
        return round(self.completed_apprentices / finished * 100, 1)


def validate_size(size: str | None, headcount: int | None = None) -> str | None:
    """Check an employer size band, deriving it from headcount if absent."""
    if size:
        cleaned = size.strip().title()
        if cleaned not in config.EMPLOYER_SIZES:
            allowed = ", ".join(config.EMPLOYER_SIZES)
            raise ValidationError(f"Employer size must be one of: {allowed}")
        return cleaned
    if headcount is None:
        return None
    if headcount < 10:
        return "Micro"
    if headcount < 50:
        return "Small"
    if headcount < 250:
        return "Medium"
    return "Large"


def validate_status(status: str | None) -> str:
    """Check an employer relationship status."""
    cleaned = (status or "Prospect").strip().title()
    if cleaned not in config.EMPLOYER_STATUSES:
        allowed = ", ".join(config.EMPLOYER_STATUSES)
        raise ValidationError(f"Employer status must be one of: {allowed}")
    return cleaned
