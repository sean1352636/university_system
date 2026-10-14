"""Qualifications and achievements.

Provider staff record them (``qualification.manage``); the apprentice
and their employer read them (``qualification.view``). A tutor sees and
records for their own caseload, an employer for their own apprentices,
an apprentice only their own, and an administrator everyone — the same
scope every other apprentice record follows.

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
from education_system.systems.apprenticeships.domain.learner_support import (
    qualifications as rules,
)
from education_system.systems.apprenticeships.domain.learner_support.qualifications import (
    Qualification,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    qualification_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    apprentice_filters,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)

_TEXT_LIMITS = {
    "title": 200, "awarding_body": 120, "reference": 40, "grade": 40,
    "certificate_ref": 80, "notes": 2000,
}


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def list_qualifications(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    relevant_prior_learning: bool | None = None,
    awaiting_certificate: bool = False,
) -> list[Qualification]:
    """Qualifications for one apprentice, or across everyone *actor* may see."""
    require(actor, "qualification.view")
    if apprentice_id is not None:
        _require_apprentice(actor, apprentice_id)
        scope: dict[str, Any] = {"apprentice_id": apprentice_id}
    else:
        scope = apprentice_filters(actor)
    return repo.list_qualifications(
        **scope,
        status=rules.validate_status(status) if status else None,
        relevant_prior_learning=relevant_prior_learning,
        awaiting_certificate=awaiting_certificate,
    )


def get_qualification(actor: Actor, qualification_id: int) -> Qualification:
    require(actor, "qualification.view")
    return _require_qualification(actor, qualification_id)


# ═════════════════════════════════════════════════════════════════════
# Writes
# ═════════════════════════════════════════════════════════════════════

def add_qualification(
    actor: Actor, apprentice_id: int, payload: dict[str, Any]
) -> Qualification:
    require(actor, "qualification.manage")
    _require_apprentice(actor, apprentice_id)

    data = _validate(payload, existing=None)
    data.update(apprentice_id=apprentice_id, recorded_by=actor.username)
    qualification_id = repo.create_qualification(data)
    compliance_repository.record(
        action="create", entity="qualification", entity_id=qualification_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['title']} ({data['status']}) for apprentice {apprentice_id}",
    )
    logger.info("Qualification %s recorded for apprentice %s by %s",
                qualification_id, apprentice_id, actor.username)

    created = repo.get_qualification(qualification_id)
    assert created is not None
    return created


def update_qualification(
    actor: Actor, qualification_id: int, payload: dict[str, Any]
) -> Qualification:
    """Change a qualification. Only the fields supplied change."""
    require(actor, "qualification.manage")
    existing = _require_qualification(actor, qualification_id)

    data = _validate(payload, existing=existing)
    repo.update_qualification(qualification_id, data)
    status_note = (
        f"{existing.status} -> {data['status']}"
        if data.get("status") and data["status"] != existing.status else ""
    )
    compliance_repository.record(
        action="update", entity="qualification", entity_id=qualification_id,
        actor=actor.username, actor_role=actor.role,
        detail=status_note or ", ".join(sorted(payload)) or "no change",
    )

    updated = repo.get_qualification(qualification_id)
    assert updated is not None
    return updated


def delete_qualification(actor: Actor, qualification_id: int, *, reason: str) -> None:
    """Remove a qualification recorded by mistake. A reason is required."""
    require(actor, "qualification.manage")
    existing = _require_qualification(actor, qualification_id)
    if not (reason or "").strip():
        raise ValidationError("A reason is required to delete a qualification")

    compliance_repository.record(
        action="delete", entity="qualification", entity_id=qualification_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {existing.title} from apprentice {existing.apprentice_id}: {reason}",
    )
    repo.delete_qualification(qualification_id)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _require_apprentice(actor: Actor, apprentice_id: int) -> Apprentice:
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)
    return apprentice


def _require_qualification(actor: Actor, qualification_id: int) -> Qualification:
    qualification = repo.get_qualification(qualification_id)
    if qualification is None:
        raise ValidationError(f"No qualification with id {qualification_id}")
    _require_apprentice(actor, qualification.apprentice_id)
    return qualification


def _validate(payload: dict[str, Any], *, existing: Qualification | None) -> dict[str, Any]:
    """Normalise and check a qualification payload.

    Simple fields are validated only when present, so a partial edit
    does not blank the rest. Status, dates and the prior-learning flag
    depend on each other, so they are judged on the record as it will
    stand after the edit and always written back together.
    """
    data: dict[str, Any] = {}
    if existing is None or "title" in payload:
        data["title"] = _text(payload.get("title"), "title", required=True)
    for key in ("awarding_body", "reference", "grade", "certificate_ref", "notes"):
        if key in payload:
            data[key] = _text(payload.get(key), key)
    if "level" in payload:
        data["level"] = rules.validate_level(payload.get("level"))
    if "start_date" in payload:
        data["start_date"] = _validate_date(payload.get("start_date"), "Start date")
    if "achieved_date" in payload:
        data["achieved_date"] = _validate_date(payload.get("achieved_date"), "Achieved date")

    def merged(key: str, default: Any = None) -> Any:
        if key in data:
            return data[key]
        return getattr(existing, key, default) if existing is not None else default

    status = (
        rules.validate_status(payload.get("status"))
        if existing is None or "status" in payload else existing.status
    )
    prior = (
        _flag(payload.get("relevant_prior_learning"))
        if "relevant_prior_learning" in payload
        else bool(getattr(existing, "relevant_prior_learning", False))
    )
    rules.check_prior_learning(status, prior)
    data.update(
        status=status,
        relevant_prior_learning=prior,
        achieved_date=rules.settle_dates(
            status, merged("start_date"), merged("achieved_date"), date.today()
        ),
    )
    return data


def _text(value: Any, key: str, *, required: bool = False) -> str | None:
    text = str(value or "").strip()
    label = key.replace("_", " ").capitalize()
    if not text:
        if required:
            raise ValidationError(f"A qualification needs a {label.lower()}")
        return None
    limit = _TEXT_LIMITS.get(key, 200)
    if len(text) > limit:
        raise ValidationError(f"{label} must be {limit} characters or fewer")
    return text


def _flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(value)


def _validate_date(value: Any, label: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{label} must be a date in YYYY-MM-DD format") from exc
