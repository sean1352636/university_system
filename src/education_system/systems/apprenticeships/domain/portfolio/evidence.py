"""Portfolio evidence and its mapping to KSBs.

The portfolio is the apprentice's proof that they can do the job. Each
piece of evidence — a work product, a witness statement, an observation
record — is mapped to the Knowledge, Skills and Behaviours it
demonstrates, and an assessor judges how far it takes each one.

The mapping is many-to-many on purpose: one good project report can
evidence a dozen KSBs, and one hard KSB usually needs several pieces
before an assessor will call it competent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.programmes.models import KSB, KSBCoverage

# Ranked weakest to strongest, so a coverage level's index is its value.
_COVERAGE_ORDER: tuple[str, ...] = config.KSB_COVERAGE_LEVELS


@dataclass
class Evidence:
    """One item in an apprentice's portfolio."""

    evidence_id: int
    apprentice_id: int
    title: str
    evidence_type: str
    description: str | None = None
    file_name: str | None = None
    status: str = "Draft"
    submitted_at: str | None = None
    assessor_id: int | None = None
    assessed_at: str | None = None
    feedback: str | None = None
    created_at: str = ""
    updated_at: str = ""
    # Filled in by the repository when the caller asked for mappings.
    mappings: list[EvidenceMapping] = field(default_factory=list)

    @property
    def is_editable(self) -> bool:
        """The apprentice may still change it.

        Referred evidence is editable again by design — being sent back
        for more work is the normal path, not a failure state.
        """
        return self.status in ("Draft", "Referred")

    @property
    def is_assessed(self) -> bool:
        return self.status in ("Accepted", "Referred", "Rejected")

    @property
    def counts_towards_competence(self) -> bool:
        """Only accepted evidence moves a KSB forward."""
        return self.status == "Accepted"

    @property
    def has_file(self) -> bool:
        return bool(self.file_name)

    @property
    def ksb_codes(self) -> list[str]:
        return [m.ksb_code for m in self.mappings]


@dataclass
class EvidenceMapping:
    """A link between one piece of evidence and one KSB."""

    map_id: int
    evidence_id: int
    ksb_id: int
    coverage: str = "Developing"
    assessor_note: str | None = None
    created_at: str = ""
    # Denormalised from the KSB for display, filled by the join.
    ksb_code: str = ""
    ksb_type: str = ""
    ksb_description: str = ""


@dataclass
class PortfolioSummary:
    """An apprentice's whole portfolio position.

    ``coverage`` holds one entry per KSB on the programme — including the
    ones with no evidence at all, since the gaps are the point of the
    screen.
    """

    apprentice_id: int
    evidence: list[Evidence] = field(default_factory=list)
    coverage: list[KSBCoverage] = field(default_factory=list)

    @property
    def total_ksbs(self) -> int:
        return len(self.coverage)

    @property
    def competent_ksbs(self) -> int:
        return sum(1 for c in self.coverage if c.is_competent)

    @property
    def developing_ksbs(self) -> int:
        return sum(1 for c in self.coverage if c.coverage == "Developing")

    @property
    def not_started_ksbs(self) -> int:
        return sum(1 for c in self.coverage if c.coverage == "Not started")

    @property
    def percent_competent(self) -> float:
        if not self.coverage:
            return 0.0
        return round(self.competent_ksbs / len(self.coverage) * 100, 1)

    @property
    def is_complete(self) -> bool:
        """Every KSB competent — the portfolio gateway requirement."""
        return bool(self.coverage) and self.competent_ksbs == len(self.coverage)

    @property
    def gaps(self) -> list[KSBCoverage]:
        """KSBs not yet competent, worst first.

        Sorted not-started before developing so the apprentice sees what
        they have not touched at all above what merely needs finishing.
        """
        outstanding = [c for c in self.coverage if not c.is_competent]
        return sorted(outstanding, key=lambda c: (_coverage_rank(c.coverage), c.ksb.sort_key))

    @property
    def awaiting_assessment(self) -> list[Evidence]:
        return [e for e in self.evidence if e.status == "Submitted"]

    @property
    def accepted_count(self) -> int:
        return sum(1 for e in self.evidence if e.status == "Accepted")

    def by_type(self) -> dict[str, list[KSBCoverage]]:
        """Coverage grouped Knowledge / Skill / Behaviour for the grid."""
        grouped: dict[str, list[KSBCoverage]] = {t: [] for t in config.KSB_TYPES}
        for item in self.coverage:
            grouped.setdefault(item.ksb.ksb_type, []).append(item)
        for items in grouped.values():
            items.sort(key=lambda c: c.ksb.sort_key)
        return grouped


def roll_up_coverage(
    ksbs: list[KSB],
    mappings: list[tuple[int, str, bool]],
) -> list[KSBCoverage]:
    """Reduce every mapping down to one coverage level per KSB.

    *mappings* is ``(ksb_id, coverage, evidence_accepted)``. A KSB takes
    the best level any *accepted* evidence gave it: one assessor saying
    "competent" settles it, and a later piece of evidence that only
    reached "developing" does not undo that judgement.

    Mappings on evidence that has not been accepted are counted towards
    ``evidence_count`` but ignored for the level, so an apprentice can
    see work in flight without it inflating their progress.
    """
    best: dict[int, str] = {}
    counts: dict[int, int] = {}
    for ksb_id, coverage, accepted in mappings:
        counts[ksb_id] = counts.get(ksb_id, 0) + 1
        if not accepted:
            continue
        current = best.get(ksb_id, "Not started")
        if _coverage_rank(coverage) > _coverage_rank(current):
            best[ksb_id] = coverage

    result = [
        KSBCoverage(
            ksb=ksb,
            coverage=best.get(ksb.ksb_id, "Not started"),
            evidence_count=counts.get(ksb.ksb_id, 0),
        )
        for ksb in ksbs
    ]
    result.sort(key=lambda c: c.ksb.sort_key)
    return result


def validate_evidence_type(value: str | None) -> str:
    """Check an evidence type against the recognised list."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError("Evidence type is required")
    if cleaned not in config.EVIDENCE_TYPES:
        allowed = ", ".join(config.EVIDENCE_TYPES)
        raise ValidationError(f"Evidence type must be one of: {allowed}")
    return cleaned


def validate_coverage(value: str | None) -> str:
    """Check a KSB coverage judgement."""
    cleaned = (value or "").strip()
    if cleaned not in config.KSB_COVERAGE_LEVELS:
        allowed = ", ".join(config.KSB_COVERAGE_LEVELS)
        raise ValidationError(f"Coverage must be one of: {allowed}")
    return cleaned


def require_evidence_status(current: str, target: str) -> None:
    """Check an evidence status move is legal."""
    if target not in config.EVIDENCE_STATUSES:
        raise ValidationError(f"{target!r} is not an evidence status")
    allowed: dict[str, frozenset[str]] = {
        "Draft": frozenset({"Submitted"}),
        "Submitted": frozenset({"Accepted", "Referred", "Rejected", "Draft"}),
        # An assessor may reopen their own decision; the apprentice can't.
        "Accepted": frozenset({"Referred", "Rejected"}),
        "Referred": frozenset({"Submitted", "Draft"}),
        "Rejected": frozenset({"Draft"}),
    }
    if target not in allowed.get(current, frozenset()):
        options = ", ".join(sorted(allowed.get(current, frozenset()))) or "nothing"
        raise ValidationError(
            f"Cannot move evidence from {current!r} to {target!r}. Allowed: {options}"
        )


def _coverage_rank(coverage: str) -> int:
    try:
        return _COVERAGE_ORDER.index(coverage)
    except ValueError:
        return 0
