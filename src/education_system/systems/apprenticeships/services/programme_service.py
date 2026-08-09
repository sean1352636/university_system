"""Apprenticeship standards: the catalogue, their KSBs and their duties.

A standard is the specification everything else is judged against —
portfolio evidence maps to its KSBs, gateway requires them all covered,
and the EPAO assesses against the methods named in its assessment plan.
Changing one therefore reaches much further than a catalogue entry
suggests, which is why publication and withdrawal are guarded
transitions here rather than an editable status field.

Every function takes ``actor`` first. The catalogue is readable by every
role — an apprentice needs to see the standard they are working towards
— but only the provider may change it.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.programmes import models
from education_system.systems.apprenticeships.domain.programmes.models import (
    KSB,
    OccupationalDuty,
    Programme,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    programme_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    compliance_repository,
)
from education_system.systems.apprenticeships.services.access import Actor, require

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def list_programmes(
    actor: Actor,
    *,
    status: str | None = None,
    level: int | None = None,
    search: str | None = None,
    active_only: bool = False,
) -> list[Programme]:
    """The standards catalogue, filtered as the list screen asks."""
    require(actor, "programme.view")
    return repo.list_all(status=status, level=level, search=search, active_only=active_only)


def get_programme(actor: Actor, programme_id: int) -> Programme:
    """One standard, or raise if there is no such id."""
    require(actor, "programme.view")
    programme = repo.get(programme_id)
    if programme is None:
        raise ValidationError(f"No programme with id {programme_id}")
    return programme


def list_ksbs(actor: Actor, programme_id: int, *, ksb_type: str | None = None) -> list[KSB]:
    """The standard's knowledge, skill and behaviour statements."""
    get_programme(actor, programme_id)
    return repo.list_ksbs(programme_id, ksb_type=_validate_ksb_type(ksb_type))


def ksb_breakdown(actor: Actor, programme_id: int) -> dict[str, int]:
    """How many KSBs of each type the standard carries.

    Every type is present in the result even at zero, so a chart or
    summary line does not have to special-case the missing key.
    """
    counts = {ksb_type: 0 for ksb_type in config.KSB_TYPES}
    for ksb in list_ksbs(actor, programme_id):
        if ksb.ksb_type in counts:
            counts[ksb.ksb_type] += 1
    return counts


def list_duties(actor: Actor, programme_id: int) -> list[OccupationalDuty]:
    """The occupational duties the standard's KSBs are grouped under."""
    get_programme(actor, programme_id)
    return repo.list_duties(programme_id)


# ═════════════════════════════════════════════════════════════════════
# Writes
# ═════════════════════════════════════════════════════════════════════

def create_programme(actor: Actor, payload: dict[str, Any]) -> Programme:
    """Add a standard to the catalogue.

    New standards always start as ``Draft``. A standard is only usable
    once its KSBs and assessment methods are in place, and
    :func:`activate_programme` is where that is checked — creating one
    ready to enrol on would route around the check entirely.
    """
    require(actor, "programme.manage")
    data = _validate(payload, existing=None)
    data["status"] = "Draft"

    programme_id = repo.create(data)
    compliance_repository.record(
        action="create", entity="programme", entity_id=programme_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Created {data.get('reference')} {data.get('title')}",
    )
    logger.info("Programme %s created by %s", programme_id, actor.username)

    created = repo.get(programme_id)
    assert created is not None
    return created


def update_programme(actor: Actor, programme_id: int, payload: dict[str, Any]) -> Programme:
    """Edit a standard's details.

    Status is deliberately not editable here — it moves through
    :func:`activate_programme` and :func:`withdraw_programme`, which
    enforce the conditions each transition depends on.
    """
    require(actor, "programme.manage")
    existing = repo.get(programme_id)
    if existing is None:
        raise ValidationError(f"No programme with id {programme_id}")

    data = _validate(payload, existing=existing)
    repo.update(programme_id, data)
    compliance_repository.record(
        action="update", entity="programme", entity_id=programme_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
    )

    updated = repo.get(programme_id)
    assert updated is not None
    return updated


def activate_programme(actor: Actor, programme_id: int) -> Programme:
    """Publish a standard so apprentices may be enrolled on it."""
    require(actor, "programme.manage")
    existing = repo.get(programme_id)
    if existing is None:
        raise ValidationError(f"No programme with id {programme_id}")

    # Both checks guard the same failure mode: an apprentice enrolled on
    # an incomplete standard can never reach gateway. Portfolio evidence
    # maps to KSBs and gateway requires every one of them covered, so a
    # standard with none is unassessable; and with no EPA method named,
    # the EPAO has nothing to book them in for.
    if repo.count_ksbs(programme_id) == 0:
        raise ValidationError(
            "This standard has no KSBs, so there is nothing for portfolio evidence to "
            "map to and nothing for the EPA to assess. An apprentice enrolled on it "
            "could never reach gateway. Add at least one knowledge, skill or behaviour "
            "before activating it."
        )
    if not existing.epa_methods:
        raise ValidationError(
            "This standard names no end-point assessment methods, so the EPAO has "
            "nothing to book an apprentice in for and gateway approval would lead "
            "nowhere. Record at least one EPA method before activating it."
        )

    repo.update(programme_id, {"status": "Active"})
    compliance_repository.record(
        action="approve", entity="programme", entity_id=programme_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Activated {existing.reference} {existing.title}",
    )
    logger.info("Programme %s activated by %s", programme_id, actor.username)

    updated = repo.get(programme_id)
    assert updated is not None
    return updated


def withdraw_programme(actor: Actor, programme_id: int, *, reason: str) -> Programme:
    """Close a standard to new enrolments."""
    require(actor, "programme.manage")
    if not (reason or "").strip():
        raise ValidationError("A reason is required to withdraw a standard")

    existing = repo.get(programme_id)
    if existing is None:
        raise ValidationError(f"No programme with id {programme_id}")

    enrolled = repo.count_apprentices(programme_id)
    if enrolled:
        raise ValidationError(
            f"{enrolled} apprentice(s) are still on {existing.reference}. Withdrawing "
            "the standard would leave them training towards something the provider no "
            "longer delivers — transfer or withdraw them first."
        )

    repo.update(programme_id, {"status": "Withdrawn"})
    compliance_repository.record(
        action="withdraw", entity="programme", entity_id=programme_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Withdrew {existing.reference}: {reason}",
    )
    logger.info(
        "Programme %s (%s) withdrawn by %s: %s",
        programme_id, existing.reference, actor.username, reason,
    )

    updated = repo.get(programme_id)
    assert updated is not None
    return updated


def delete_programme(actor: Actor, programme_id: int, *, reason: str) -> None:
    """Erase a standard along with its KSBs and duties.

    Admin only, and genuinely destructive: it exists for removing a
    standard entered in error. One the provider has stopped delivering
    is a withdrawal — that keeps the record the funding audit reads.
    """
    if not actor.is_admin:
        raise ValidationError(
            "Only an administrator may delete a standard. To stop delivering it, "
            "withdraw the standard instead."
        )
    if not (reason or "").strip():
        raise ValidationError("A reason is required to delete a standard")

    existing = repo.get(programme_id)
    if existing is None:
        raise ValidationError(f"No programme with id {programme_id}")

    enrolled = repo.count_apprentices(programme_id)
    if enrolled:
        raise ValidationError(
            f"{enrolled} apprentice record(s) reference {existing.reference}. Deleting "
            "it would strip the standard from their record and with it the KSBs their "
            "portfolio is mapped to."
        )

    compliance_repository.record(
        action="delete", entity="programme", entity_id=programme_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {existing.reference} {existing.title}: {reason}",
    )
    repo.delete(programme_id)
    logger.warning(
        "Programme %s (%s) deleted by %s: %s",
        programme_id, existing.reference, actor.username, reason,
    )


def add_ksb(actor: Actor, programme_id: int, payload: dict[str, Any]) -> KSB:
    """Add a knowledge, skill or behaviour statement to a standard."""
    require(actor, "programme.manage")
    programme = repo.get(programme_id)
    if programme is None:
        raise ValidationError(f"No programme with id {programme_id}")

    data = _validate_ksb(payload, programme_id=programme_id, existing=None)
    data["programme_id"] = programme_id

    ksb_id = repo.create_ksb(data)
    compliance_repository.record(
        action="create", entity="ksb", entity_id=ksb_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['code']} added to {programme.reference}",
    )
    logger.info("KSB %s added to programme %s by %s", ksb_id, programme_id, actor.username)

    created = repo.get_ksb(ksb_id)
    assert created is not None
    return created


def update_ksb(actor: Actor, ksb_id: int, payload: dict[str, Any]) -> KSB:
    """Edit a KSB statement."""
    require(actor, "programme.manage")
    existing = repo.get_ksb(ksb_id)
    if existing is None:
        raise ValidationError(f"No KSB with id {ksb_id}")

    data = _validate_ksb(payload, programme_id=existing.programme_id, existing=existing)
    repo.update_ksb(ksb_id, data)
    compliance_repository.record(
        action="update", entity="ksb", entity_id=ksb_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{existing.code}: " + (", ".join(sorted(data)) or "no change"),
    )

    updated = repo.get_ksb(ksb_id)
    assert updated is not None
    return updated


def delete_ksb(actor: Actor, ksb_id: int, *, reason: str | None = None) -> None:
    """Remove a KSB from a standard.

    The evidence mapped to it survives, having simply lost one of the
    things it covered, so an apprentice's portfolio is not silently
    emptied by a catalogue tidy-up.
    """
    require(actor, "programme.manage")
    existing = repo.get_ksb(ksb_id)
    if existing is None:
        raise ValidationError(f"No KSB with id {ksb_id}")

    compliance_repository.record(
        action="delete", entity="ksb", entity_id=ksb_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {existing.code}" + (f": {reason}" if reason else ""),
    )
    repo.delete_ksb(ksb_id)
    logger.info("KSB %s (%s) deleted by %s", ksb_id, existing.code, actor.username)


def add_duty(actor: Actor, programme_id: int, payload: dict[str, Any]) -> OccupationalDuty:
    """Add an occupational duty to a standard."""
    require(actor, "programme.manage")
    programme = repo.get(programme_id)
    if programme is None:
        raise ValidationError(f"No programme with id {programme_id}")

    data = _validate_duty(payload, programme_id=programme_id, existing=None)
    data["programme_id"] = programme_id

    duty_id = repo.create_duty(data)
    compliance_repository.record(
        action="create", entity="duty", entity_id=duty_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['code']} added to {programme.reference}",
    )
    logger.info("Duty %s added to programme %s by %s", duty_id, programme_id, actor.username)

    created = next((d for d in repo.list_duties(programme_id) if d.duty_id == duty_id), None)
    assert created is not None
    return created


def update_duty(actor: Actor, duty_id: int, payload: dict[str, Any]) -> None:
    """Edit an occupational duty.

    Returns nothing: the repository offers no lookup by ``duty_id``
    alone, so re-reading the row would mean a scan of a programme this
    function has not been told the id of.
    """
    require(actor, "programme.manage")
    data = _validate_duty(payload, programme_id=None, existing=None)
    if not data:
        return

    repo.update_duty(duty_id, data)
    compliance_repository.record(
        action="update", entity="duty", entity_id=duty_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)),
    )


def delete_duty(actor: Actor, duty_id: int) -> None:
    """Remove an occupational duty.

    KSBs pointing at it by ``duty_ref`` keep the text they were given —
    the reference is a label on the standard, not a foreign key.
    """
    require(actor, "programme.manage")
    compliance_repository.record(
        action="delete", entity="duty", entity_id=duty_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted duty {duty_id}",
    )
    repo.delete_duty(duty_id)
    logger.info("Duty %s deleted by %s", duty_id, actor.username)


# ═════════════════════════════════════════════════════════════════════
# Validation
# ═════════════════════════════════════════════════════════════════════

def _validate(payload: dict[str, Any], *, existing: Programme | None) -> dict[str, Any]:
    """Normalise and check a programme payload.

    Only keys actually present are validated and returned, so a partial
    edit from a form showing three fields does not blank the rest.
    """
    data: dict[str, Any] = {}

    if existing is None or "reference" in payload:
        reference = models.validate_reference(payload.get("reference"))
        clash = repo.get_by_reference(reference)
        if clash and (existing is None or clash.programme_id != existing.programme_id):
            raise ValidationError(f"Reference {reference} already belongs to {clash.title}")
        data["reference"] = reference

    if existing is None or "title" in payload:
        data["title"] = _require_text(payload.get("title"), "Title")
    if existing is None or "level" in payload:
        data["level"] = models.validate_level(payload.get("level"))
    if existing is None or "funding_band" in payload:
        data["funding_band"] = models.validate_funding_band(payload.get("funding_band"))
    if existing is None or "duration_months" in payload:
        data["duration_months"] = _validate_duration(payload.get("duration_months"))

    if "epa_methods" in payload:
        data["epa_methods"] = models.validate_epa_methods(payload.get("epa_methods"))
    for key in ("sector", "description"):
        if key in payload:
            data[key] = _optional_text(payload.get(key))

    return data


def _validate_ksb(
    payload: dict[str, Any],
    *,
    programme_id: int,
    existing: KSB | None,
) -> dict[str, Any]:
    """Normalise and check a KSB payload."""
    data: dict[str, Any] = {}

    if existing is None or "code" in payload:
        # The type is implied by the code's letter, so it is derived
        # rather than asked for: a K-coded statement filed as a Behaviour
        # would sort and group wrongly everywhere it appears.
        code, ksb_type = models.validate_ksb_code(payload.get("code"))
        clash = next(
            (k for k in repo.list_ksbs(programme_id) if k.code == code), None
        )
        if clash and (existing is None or clash.ksb_id != existing.ksb_id):
            raise ValidationError(f"{code} is already defined on this standard")
        data["code"] = code
        data["ksb_type"] = ksb_type

    if existing is None or "description" in payload:
        data["description"] = _require_text(
            payload.get("description"), "KSB description", limit=1000
        )

    if "duty_ref" in payload:
        ref = _optional_text(payload.get("duty_ref"))
        if ref:
            ref = ref.upper()
            codes = {duty.code.upper() for duty in repo.list_duties(programme_id)}
            # Only enforced once the standard has duties recorded:
            # providers routinely enter the KSB list first, and rejecting
            # every duty_ref until then would just teach them to leave it
            # blank.
            if codes and ref not in codes:
                allowed = ", ".join(sorted(codes))
                raise ValidationError(
                    f"{ref} is not a duty on this standard. Choose from: {allowed}"
                )
        data["duty_ref"] = ref

    return data


def _validate_duty(
    payload: dict[str, Any],
    *,
    programme_id: int | None,
    existing: OccupationalDuty | None,
) -> dict[str, Any]:
    """Normalise and check an occupational duty payload.

    ``programme_id`` is None when editing in place. The repository offers
    no lookup by duty id alone, so there is no standard to check a
    duplicate code against and nothing that can be treated as required —
    only the keys the caller actually sent are validated.
    """
    creating = programme_id is not None and existing is None
    data: dict[str, Any] = {}

    if creating or "code" in payload:
        code = _require_text(payload.get("code"), "Duty code", limit=20).upper()
        if programme_id is not None:
            clash = next(
                (d for d in repo.list_duties(programme_id) if d.code.upper() == code), None
            )
            if clash and (existing is None or clash.duty_id != existing.duty_id):
                raise ValidationError(f"{code} is already a duty on this standard")
        data["code"] = code

    if creating or "description" in payload:
        data["description"] = _require_text(
            payload.get("description"), "Duty description", limit=1000
        )

    return data


def _validate_ksb_type(value: Any) -> str | None:
    text = str(value or "").strip().title()
    if not text:
        return None
    if text not in config.KSB_TYPES:
        allowed = ", ".join(config.KSB_TYPES)
        raise ValidationError(f"KSB type must be one of: {allowed}")
    return text


def _validate_duration(value: Any) -> int:
    try:
        months = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("Duration must be a whole number of months") from exc
    # The funding rules require a practical period of at least twelve
    # months, so a shorter standard could never be claimed for.
    minimum = config.MINIMUM_PRACTICAL_PERIOD_DAYS // 30
    if months < minimum:
        raise ValidationError(
            f"Duration must be at least {minimum} months — a shorter apprenticeship "
            "does not meet the minimum practical period and cannot be funded"
        )
    if months > 84:
        raise ValidationError("Duration cannot exceed 84 months")
    return months


def _require_text(value: Any, label: str, *, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{label} is required")
    if len(text) > limit:
        raise ValidationError(f"{label} must be {limit} characters or fewer")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
