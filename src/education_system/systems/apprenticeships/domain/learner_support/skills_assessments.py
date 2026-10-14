"""Initial and diagnostic skills assessments.

Before an apprentice starts, the provider has to know where they are in
English, Maths and Digital: it decides whether functional-skills study
goes into the plan, and a funding auditor asks for the evidence. An
initial assessment records that starting point; a diagnostic, later,
finds the specific gaps. Both are kept as history rather than
overwritten, because the question at audit is "what did you know when
you planned this", not "what is true now".

The *current* English and Maths position — Not started, In progress,
Achieved, Exempt — lives on the functional-skills record owned by
compliance. This module only reads it alongside.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.compliance.eligibility import (
    FunctionalSkill,
)


@dataclass
class SkillsAssessment:
    """One initial or diagnostic assessment in one subject."""

    assessment_id: int
    apprentice_id: int
    subject: str
    kind: str
    assessed_on: str
    level: str | None = None
    score: float | None = None
    notes: str | None = None
    assessed_by: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_below_target(self) -> bool:
        """Placed below the gateway level in English or Maths.

        Digital has no gateway level, and an assessment with only a score
        has not placed anyone anywhere, so neither is judged.
        """
        if self.subject not in config.FUNCTIONAL_SKILLS:
            return False
        return is_below(self.level, config.SKILLS_TARGET_LEVEL)


@dataclass
class SkillsProfile:
    """An apprentice's functional-skills position and the assessments behind it."""

    apprentice_id: int
    # English and Maths as compliance records them, in config order.
    skills: list[FunctionalSkill] = field(default_factory=list)
    # Newest first.
    assessments: list[SkillsAssessment] = field(default_factory=list)

    @property
    def gateway_satisfied(self) -> bool:
        return bool(self.skills) and all(s.is_satisfied for s in self.skills)

    @property
    def outstanding(self) -> list[str]:
        return [s.subject for s in self.skills if not s.is_satisfied]

    def latest(self, subject: str, kind: str | None = None) -> SkillsAssessment | None:
        """The most recent assessment in *subject*, optionally of one kind."""
        for assessment in self.assessments:
            if assessment.subject == subject and (kind is None or assessment.kind == kind):
                return assessment
        return None

    def starting_points(self) -> dict[str, str | None]:
        """Each subject's level at its latest initial assessment."""
        points: dict[str, str | None] = {}
        for subject in config.SKILLS_ASSESSMENT_SUBJECTS:
            found = self.latest(subject, "Initial")
            points[subject] = found.level if found else None
        return points

    @property
    def needs_study(self) -> list[str]:
        """Subjects still to be satisfied whose latest assessment is below target.

        What goes into the learning plan as functional-skills study. An
        achieved or exempt subject is never in it, however an old
        assessment placed them.
        """
        satisfied = {s.subject for s in self.skills if s.is_satisfied}
        needs = []
        for subject in config.FUNCTIONAL_SKILLS:
            latest = self.latest(subject)
            if subject not in satisfied and latest is not None and latest.is_below_target:
                needs.append(subject)
        return needs

    @property
    def unassessed(self) -> list[str]:
        """Subjects with no initial assessment on record — an audit gap."""
        return [s for s in config.SKILLS_ASSESSMENT_SUBJECTS if self.latest(s, "Initial") is None]


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def is_below(level: str | None, target: str) -> bool:
    """Is *level* lower than *target* on the assessment scale?

    An unknown or missing level is not "below": refusing to guess is
    safer than flagging someone for study on a typo.
    """
    order = config.SKILLS_ASSESSMENT_LEVELS
    if level not in order or target not in order:
        return False
    return order.index(level) < order.index(target)


def validate_subject(value: str | None) -> str:
    return _one_of(value, config.SKILLS_ASSESSMENT_SUBJECTS, "Subject")


def validate_kind(value: str | None) -> str:
    return _one_of(value or "Initial", config.SKILLS_ASSESSMENT_KINDS, "Assessment type")


def validate_level(value: str | None) -> str | None:
    if not (value or "").strip():
        return None
    return _one_of(value, config.SKILLS_ASSESSMENT_LEVELS, "Level")


def validate_score(value: object) -> float | None:
    """A score as a percentage from 0 to 100, or None when not given."""
    text = str(value if value is not None else "").strip().rstrip("%")
    if not text:
        return None
    try:
        score = float(text)
    except ValueError as exc:
        raise ValidationError("Score must be a number from 0 to 100") from exc
    if not 0 <= score <= 100:
        raise ValidationError("Score must be from 0 to 100")
    return round(score, 1)


def validate_assessed_on(value: object, today: date) -> str:
    """The date the assessment was taken: required, and not in the future."""
    text = str(value or "").strip()
    if not text:
        raise ValidationError("An assessment needs the date it was taken")
    try:
        taken = date.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError("Assessment date must be a date in YYYY-MM-DD format") from exc
    if taken > today:
        raise ValidationError("An assessment cannot be dated in the future")
    return taken.isoformat()


def require_result(level: str | None, score: float | None) -> None:
    """An assessment has to have found something: a level, a score, or both."""
    if level is None and score is None:
        raise ValidationError("Record the level the assessment found, its score, or both")


def _one_of(value: str | None, allowed: tuple[str, ...], label: str) -> str:
    cleaned = (value or "").strip()
    match = next((a for a in allowed if a.casefold() == cleaned.casefold()), None)
    if match is None:
        raise ValidationError(f"{label} must be one of: {', '.join(allowed)}")
    return match
