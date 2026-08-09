"""Apprenticeship standards and the KSBs that make them up.

A *standard* describes an occupation: what someone doing that job must
know, be able to do, and how they must behave. Those are the Knowledge,
Skills and Behaviours — KSBs — and they are the spine of the whole
system. Portfolio evidence maps to them, gateway requires them all
covered, and the EPA assesses against them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

# Standards published by IfATE are referenced as ST followed by four
# digits. Providers also run legacy frameworks, so a plain alphanumeric
# code is accepted too.
_REFERENCE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-/]{1,19}$")

# KSB codes are a type letter and a number: K1, S12, B3.
_KSB_CODE_RE = re.compile(r"^([KSB])(\d{1,3})$")

_KSB_TYPE_BY_LETTER = {"K": "Knowledge", "S": "Skill", "B": "Behaviour"}


@dataclass
class Programme:
    """One apprenticeship standard the provider delivers."""

    programme_id: int
    reference: str
    title: str
    level: int
    funding_band: int
    duration_months: int
    epa_methods: list[str] = field(default_factory=list)
    sector: str | None = None
    description: str | None = None
    status: str = "Draft"
    created_at: str = ""
    updated_at: str = ""

    @property
    def level_label(self) -> str:
        return config.LEVEL_LABELS.get(self.level, f"Level {self.level}")

    @property
    def pathway(self) -> str:
        """Which pathway rule-set governs this programme."""
        return config.pathway_for_level(self.level)

    @property
    def band_maximum(self) -> float:
        """The most that may be funded for this standard."""
        return config.FUNDING_BANDS.get(self.funding_band, 0.0)

    @property
    def is_degree_apprenticeship(self) -> bool:
        """Level 6+ programmes carry an integrated degree.

        These are the ones that need the university gateway — the
        academic award is validated by a partner HEI, so credit tracking
        runs alongside the apprenticeship record.
        """
        return self.level >= 6


@dataclass
class KSB:
    """One knowledge, skill or behaviour statement within a standard."""

    ksb_id: int
    programme_id: int
    code: str
    ksb_type: str
    description: str
    duty_ref: str | None = None
    created_at: str = ""

    @property
    def sort_key(self) -> tuple[int, int]:
        """Order K1, K2 … K10 numerically, not as strings.

        Plain string ordering would put K10 before K2, which reads as a
        bug to anyone scanning a portfolio mapping grid.
        """
        match = _KSB_CODE_RE.match(self.code.upper())
        if not match:
            return (99, 0)
        letter, number = match.groups()
        return ("KSB".index(letter), int(number))


@dataclass
class OccupationalDuty:
    """A duty from the standard, which KSBs are grouped under."""

    duty_id: int
    programme_id: int
    code: str
    description: str
    created_at: str = ""


@dataclass
class KSBCoverage:
    """How far one apprentice has got with one KSB.

    ``coverage`` is the best judgement across all the evidence mapped to
    this KSB — an apprentice is competent as soon as one piece of
    accepted evidence says so, not once every piece does.
    """

    ksb: KSB
    coverage: str = "Not started"
    evidence_count: int = 0

    @property
    def is_competent(self) -> bool:
        return self.coverage == "Competent"


def validate_reference(reference: str) -> str:
    """Normalise and check a standard reference such as ``ST0119``."""
    cleaned = (reference or "").strip().upper()
    if not cleaned:
        raise ValidationError("Programme reference is required")
    if not _REFERENCE_RE.match(cleaned):
        raise ValidationError(
            "Programme reference must be 2-20 characters of letters, digits, "
            "hyphens or slashes (e.g. ST0119)"
        )
    return cleaned


def validate_level(level: object) -> int:
    """Check an apprenticeship level against the published set."""
    try:
        value = int(str(level).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("Level must be a whole number") from exc
    if value not in config.PROGRAMME_LEVELS:
        allowed = ", ".join(str(v) for v in config.PROGRAMME_LEVELS)
        raise ValidationError(f"Level must be one of: {allowed}")
    return value


def validate_funding_band(band: object) -> int:
    """Check a funding band index against the published bands."""
    try:
        value = int(str(band).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("Funding band must be a whole number") from exc
    if value not in config.FUNDING_BANDS:
        raise ValidationError(
            f"Funding band must be between 1 and {max(config.FUNDING_BANDS)}"
        )
    return value


def validate_ksb_code(code: str) -> tuple[str, str]:
    """Normalise a KSB code and derive its type.

    Returns ``(code, ksb_type)`` — the type is implied by the letter, so
    storing it separately is redundant but makes the mapping grid's
    grouping query trivial.
    """
    cleaned = (code or "").strip().upper().replace(" ", "")
    match = _KSB_CODE_RE.match(cleaned)
    if not match:
        raise ValidationError(
            "KSB code must be K, S or B followed by a number (e.g. K1, S12, B3)"
        )
    letter, number = match.groups()
    return f"{letter}{int(number)}", _KSB_TYPE_BY_LETTER[letter]


def validate_epa_methods(methods: object) -> list[str]:
    """Check the assessment methods named in a standard's EPA plan."""
    if not methods:
        return []
    if isinstance(methods, str):
        candidates = [m.strip() for m in methods.split(",")]
    else:
        candidates = [str(m).strip() for m in methods]
    cleaned: list[str] = []
    for method in candidates:
        if not method:
            continue
        if method not in config.EPA_METHODS:
            allowed = ", ".join(config.EPA_METHODS)
            raise ValidationError(f"{method!r} is not an EPA method. Choose from: {allowed}")
        if method not in cleaned:
            cleaned.append(method)
    return cleaned
