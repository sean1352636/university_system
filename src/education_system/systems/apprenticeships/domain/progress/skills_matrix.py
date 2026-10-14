"""The skills matrix: where an apprentice stands on every KSB.

A read-only lens over the portfolio. The coverage level per KSB comes
from ``portfolio.evidence.roll_up_coverage`` — the same rule the gateway
check reads — so this screen can never call an apprentice competent on a
KSB the portfolio does not. What this module adds is shape: the KSBs
grouped Knowledge / Skill / Behaviour, a summary per group, and the
cohort view that lines apprentices up against each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.portfolio.evidence import PortfolioSummary
from education_system.systems.apprenticeships.domain.programmes.models import KSBCoverage

_LEVELS: tuple[str, ...] = config.KSB_COVERAGE_LEVELS


def level_fraction(level: str) -> float:
    """How far along the coverage scale *level* is: 0 for the first, 1 for the last."""
    try:
        rank = _LEVELS.index(level)
    except ValueError:
        return 0.0
    return rank / (len(_LEVELS) - 1) if len(_LEVELS) > 1 else 1.0


def level_bar(level: str, *, width: int = config.SKILLS_MATRIX_BAR_WIDTH) -> str:
    """A fixed-width text bar for one KSB's level, shared by the GUI and CLI.

    Text rather than a widget so a column of them lines up in a table
    cell and reads the same in a terminal.
    """
    filled = round(level_fraction(level) * width)
    return "█" * filled + "░" * (width - filled)


@dataclass
class TypeSummary:
    """Coverage totals for one KSB type."""

    ksb_type: str
    total: int = 0
    competent: int = 0
    developing: int = 0
    not_started: int = 0

    @property
    def percent_competent(self) -> float | None:
        """None when the standard has no KSBs of this type — not 0%, which
        would read as an apprentice who has done nothing."""
        if not self.total:
            return None
        return round(self.competent / self.total * 100, 1)


def summarise(coverage: list[KSBCoverage], ksb_type: str) -> TypeSummary:
    items = [c for c in coverage if c.ksb.ksb_type == ksb_type]
    return TypeSummary(
        ksb_type=ksb_type,
        total=len(items),
        competent=sum(1 for c in items if c.coverage == "Competent"),
        developing=sum(1 for c in items if c.coverage == "Developing"),
        not_started=sum(1 for c in items if c.coverage == "Not started"),
    )


@dataclass
class SkillsMatrix:
    """One apprentice's KSBs, each with its coverage level."""

    apprentice_id: int
    apprentice_name: str = ""
    programme_title: str | None = None
    coverage: list[KSBCoverage] = field(default_factory=list)

    def by_type(self) -> dict[str, list[KSBCoverage]]:
        """Grouped Knowledge / Skill / Behaviour, each in K1, K2 … K10 order."""
        return PortfolioSummary(self.apprentice_id, coverage=self.coverage).by_type()

    def summaries(self) -> list[TypeSummary]:
        return [summarise(self.coverage, t) for t in config.KSB_TYPES]

    @property
    def total(self) -> int:
        return len(self.coverage)

    @property
    def competent(self) -> int:
        return sum(1 for c in self.coverage if c.is_competent)

    @property
    def percent_competent(self) -> float:
        return PortfolioSummary(self.apprentice_id, coverage=self.coverage).percent_competent


@dataclass
class CohortRow:
    """One apprentice's line in the cohort view."""

    apprentice_id: int
    apprentice_name: str
    programme_title: str | None = None
    employer_name: str | None = None
    status: str | None = None
    coverage: list[KSBCoverage] = field(default_factory=list)

    def summary(self, ksb_type: str) -> TypeSummary:
        return summarise(self.coverage, ksb_type)

    def percent(self, ksb_type: str) -> float | None:
        return self.summary(ksb_type).percent_competent

    @property
    def percent_overall(self) -> float | None:
        if not self.coverage:
            return None
        competent = sum(1 for c in self.coverage if c.is_competent)
        return round(competent / len(self.coverage) * 100, 1)


def average_percent(rows: list[CohortRow], ksb_type: str | None = None) -> float | None:
    """The cohort's mean % competent for one KSB type, or overall.

    Apprentices whose standard has no KSBs of the type are left out of
    the mean rather than counted as 0%.
    """
    values = [
        r.percent_overall if ksb_type is None else r.percent(ksb_type) for r in rows
    ]
    known = [v for v in values if v is not None]
    if not known:
        return None
    return round(sum(known) / len(known), 1)
