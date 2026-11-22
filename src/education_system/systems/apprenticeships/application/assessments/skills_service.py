"""Functional skills: the current position, and the assessments behind it.

Two records meet here. The current English and Maths position — the
one gateway checks — belongs to compliance, and changing it goes
through ``compliance_service.set_functional_skill``, which holders of
``compliance.manage`` may do. Initial and diagnostic assessments belong
to this module: ``skills.assess`` records them, ``skills.view`` reads
them.

Reading the current position is gated on ``skills.view`` rather than
``compliance.view``: the apprentice and their employer need to see where
English and Maths stand, and neither holds the compliance permission —
which also opens the funding paperwork. So the position is read straight
from ``compliance_repository`` after this module's own scope check.

Every function takes ``actor`` first. Reads are scoped to what the actor
may see, and writes are refused outright.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ValidationError,
)
from education_system.systems.apprenticeships.domain.compliance.eligibility import (
    FunctionalSkill,
)
from education_system.systems.apprenticeships.domain.learner_support import (
    skills_assessments as rules,
)
from education_system.systems.apprenticeships.domain.learner_support.skills_assessments import (
    SkillsAssessment,
    SkillsProfile,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    skills_assessment_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
)
from education_system.systems.apprenticeships.application.compliance import compliance_service
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    apprentice_filters,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def get_profile(actor: Actor, apprentice_id: int) -> SkillsProfile:
    """One apprentice's functional-skills position and assessment history."""
    require(actor, "skills.view")
    _require_apprentice(actor, apprentice_id)
    return SkillsProfile(
        apprentice_id=apprentice_id,
        skills=compliance_repository.list_functional_skills(apprentice_id),
        assessments=repo.list_assessments(apprentice_id=apprentice_id),
    )


def list_assessments(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    subject: str | None = None,
    kind: str | None = None,
    assessed_from: str | None = None,
    assessed_to: str | None = None,
) -> list[SkillsAssessment]:
    """Assessments across everyone *actor* may see, newest first."""
    require(actor, "skills.view")
    if apprentice_id is not None:
        _require_apprentice(actor, apprentice_id)
        scope: dict[str, Any] = {"apprentice_id": apprentice_id}
    else:
        scope = apprentice_filters(actor)
    return repo.list_assessments(
        **scope, subject=subject, kind=kind,
        assessed_from=assessed_from, assessed_to=assessed_to,
    )


def can_change_status(actor: Actor) -> bool:
    """May *actor* change the English / Maths position (including exemptions)?"""
    return actor.can("compliance.manage")


# ═════════════════════════════════════════════════════════════════════
# The current position — owned by compliance
# ═════════════════════════════════════════════════════════════════════

def set_status(
    actor: Actor,
    apprentice_id: int,
    subject: str,
    *,
    status: str,
    level: str | None = None,
    achieved_date: str | None = None,
    exemption_reason: str | None = None,
    notes: str | None = None,
) -> FunctionalSkill:
    """Change an apprentice's English or Maths status, or record an exemption.

    Straight through to compliance, which owns the record, its evidence
    rules and its audit entry. Kept here so the functional-skills screens
    talk to one service.
    """
    return compliance_service.set_functional_skill(
        actor, apprentice_id, subject,
        status=status, level=level, achieved_date=achieved_date,
        exemption_reason=exemption_reason, notes=notes,
    )


# ═════════════════════════════════════════════════════════════════════
# Assessments
# ═════════════════════════════════════════════════════════════════════

def record_assessment(
    actor: Actor, apprentice_id: int, payload: dict[str, Any]
) -> SkillsAssessment:
    """Record an initial or diagnostic assessment.

    Who assessed is stamped from the actor: at audit the question is who
    attested to the starting point, and a typed-in name would not answer it.
    """
    require(actor, "skills.assess")
    _require_apprentice(actor, apprentice_id)

    data = _validate(payload, existing=None)
    data.update(apprentice_id=apprentice_id, assessed_by=actor.username)
    assessment_id = repo.create_assessment(data)
    compliance_repository.record(
        action="create", entity="skills_assessment", entity_id=assessment_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['kind']} {data['subject']} assessment for apprentice {apprentice_id}: "
               f"{data.get('level') or '—'}",
    )
    logger.info("%s %s assessment %s recorded for apprentice %s by %s",
                data["kind"], data["subject"], assessment_id, apprentice_id, actor.username)

    created = repo.get_assessment(assessment_id)
    assert created is not None
    return created


def update_assessment(
    actor: Actor, assessment_id: int, payload: dict[str, Any]
) -> SkillsAssessment:
    """Correct an assessment. Only the fields supplied change."""
    require(actor, "skills.assess")
    existing = _require_assessment(actor, assessment_id)

    data = _validate(payload, existing=existing)
    repo.update_assessment(assessment_id, data)
    compliance_repository.record(
        action="update", entity="skills_assessment", entity_id=assessment_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
    )

    updated = repo.get_assessment(assessment_id)
    assert updated is not None
    return updated


def delete_assessment(actor: Actor, assessment_id: int, *, reason: str) -> None:
    """Remove an assessment recorded by mistake. A reason is required."""
    require(actor, "skills.assess")
    existing = _require_assessment(actor, assessment_id)
    if not (reason or "").strip():
        raise ValidationError("A reason is required to delete an assessment")

    compliance_repository.record(
        action="delete", entity="skills_assessment", entity_id=assessment_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {existing.kind} {existing.subject} assessment of "
               f"{existing.assessed_on} for apprentice {existing.apprentice_id}: {reason}",
    )
    repo.delete_assessment(assessment_id)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _require_apprentice(actor: Actor, apprentice_id: int) -> Apprentice:
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)
    return apprentice


def _require_assessment(actor: Actor, assessment_id: int) -> SkillsAssessment:
    assessment = repo.get_assessment(assessment_id)
    if assessment is None:
        raise ValidationError(f"No assessment with id {assessment_id}")
    _require_apprentice(actor, assessment.apprentice_id)
    return assessment


def _validate(payload: dict[str, Any], *, existing: SkillsAssessment | None) -> dict[str, Any]:
    """Normalise and check an assessment payload.

    Only keys actually present are validated and returned, so a partial
    edit does not blank the rest. Whether the result still has a level
    or a score is judged on the record as it will be after the edit.
    """
    data: dict[str, Any] = {}
    if existing is None or "subject" in payload:
        data["subject"] = rules.validate_subject(payload.get("subject"))
    if existing is None or "kind" in payload:
        data["kind"] = rules.validate_kind(payload.get("kind"))
    if existing is None or "assessed_on" in payload:
        data["assessed_on"] = rules.validate_assessed_on(payload.get("assessed_on"), date.today())
    if "level" in payload:
        data["level"] = rules.validate_level(payload.get("level"))
    if "score" in payload:
        data["score"] = rules.validate_score(payload.get("score"))
    if "notes" in payload:
        text = str(payload.get("notes") or "").strip()
        data["notes"] = text or None

    rules.require_result(
        data["level"] if "level" in data else getattr(existing, "level", None),
        data["score"] if "score" in data else getattr(existing, "score", None),
    )
    return data
