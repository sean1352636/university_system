"""The portfolio: evidence, its KSB mapping, assessment and IQA sampling.

The portfolio is the apprentice's proof that they can do the job, and
the three parties touching it want different things. The apprentice
gathers evidence and claims which KSBs it shows. The assessor judges
those claims. The internal quality assurer samples the assessor. This
module keeps the three apart — an apprentice cannot mark themselves
competent, and an assessor cannot rewrite the evidence they are judging.

Every function takes ``actor`` first. That is not decoration — reads are
scoped to what the actor may see, and writes are refused outright.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ValidationError,
)
from education_system.systems.apprenticeships.domain.portfolio.evidence import (
    Evidence,
    EvidenceMapping,
    PortfolioSummary,
    require_evidence_status,
    validate_coverage,
    validate_evidence_type,
)
from education_system.systems.apprenticeships.domain.programmes.models import KSBCoverage
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    portfolio_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    programme_repository,
)
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
    require_any,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)

# Where an assessment decision may land. The other two evidence statuses
# belong to the apprentice, not the assessor.
_ASSESSMENT_OUTCOMES: tuple[str, ...] = ("Accepted", "Referred", "Rejected")


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def get_portfolio(actor: Actor, apprentice_id: int) -> PortfolioSummary:
    """Everything in one apprentice's portfolio, plus every KSB's coverage."""
    require(actor, "portfolio.view")
    apprentice = _require_apprentice(actor, apprentice_id)
    if apprentice.programme_id is None:
        raise ValidationError(
            "This apprentice is not on a programme yet, so there are no KSBs to "
            "evidence against"
        )
    return repo.build_summary(apprentice_id, apprentice.programme_id)


def list_evidence(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    evidence_type: str | None = None,
) -> list[Evidence]:
    """The evidence *actor* may see, with any extra filters applied.

    An employer passing another organisation's ``apprentice_id`` does not
    widen anything: their own scope is applied last and wins.
    """
    require(actor, "portfolio.view")
    filters: dict[str, Any] = {
        "apprentice_id": apprentice_id,
        "status": status,
        "evidence_type": evidence_type,
        "with_mappings": True,
    }
    filters.update(apprentice_filters(actor))
    return repo.list_evidence(**filters)


def get_evidence(actor: Actor, evidence_id: int) -> Evidence:
    require(actor, "portfolio.view")
    return _require_evidence(actor, evidence_id)


def assessment_queue(actor: Actor) -> list[Evidence]:
    """Submitted work waiting on this assessor, and nobody else's."""
    require(actor, "portfolio.assess")
    filters: dict[str, Any] = {"status": "Submitted", "with_mappings": True}
    filters.update(apprentice_filters(actor))
    return repo.list_evidence(**filters)


def coverage_gaps(actor: Actor, apprentice_id: int) -> list[KSBCoverage]:
    """KSBs still to be evidenced, worst first."""
    return get_portfolio(actor, apprentice_id).gaps


def list_verifications(actor: Actor, evidence_id: int) -> list[dict[str, Any]]:
    """The IQA sampling history on one piece of evidence."""
    require(actor, "portfolio.view")
    _require_evidence(actor, evidence_id)
    return repo.list_verifications(evidence_id)


# ═════════════════════════════════════════════════════════════════════
# Evidence
# ═════════════════════════════════════════════════════════════════════

def add_evidence(actor: Actor, payload: dict[str, Any]) -> Evidence:
    """Put a new item in a portfolio.

    Evidence starts as ``Draft``: it is the apprentice's until they say
    it is ready, and nothing counts towards a KSB before an assessor has
    accepted it.
    """
    require(actor, "portfolio.upload")
    data = _validate(payload, existing=None)
    if actor.role == config.APPRENTICE:
        # An apprentice adds to their own portfolio whatever the form
        # posted.
        if actor.apprentice_id is None:
            raise ValidationError("Your login is not linked to an apprentice record")
        data["apprentice_id"] = actor.apprentice_id
    if data.get("apprentice_id") is None:
        raise ValidationError("An apprentice is required")
    _require_apprentice(actor, data["apprentice_id"])
    data["status"] = "Draft"

    evidence_id = repo.create_evidence(data)
    compliance_repository.record(
        action="create", entity="evidence", entity_id=evidence_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data.get('evidence_type')}: {data.get('title')}",
    )
    logger.info(
        "Evidence %s added to apprentice %s by %s",
        evidence_id, data["apprentice_id"], actor.username,
    )

    created = repo.get_evidence(evidence_id)
    assert created is not None
    return created


def update_evidence(actor: Actor, evidence_id: int, payload: dict[str, Any]) -> Evidence:
    require(actor, "portfolio.upload")
    existing = _require_evidence(actor, evidence_id)
    _require_editable(existing)

    data = _validate(payload, existing=existing)
    # Moving an item to another portfolio is not an edit.
    data.pop("apprentice_id", None)
    repo.update_evidence(evidence_id, data)
    compliance_repository.record(
        action="update", entity="evidence", entity_id=evidence_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
    )

    updated = repo.get_evidence(evidence_id)
    assert updated is not None
    return updated


def delete_evidence(actor: Actor, evidence_id: int) -> None:
    require(actor, "portfolio.upload")
    existing = _require_evidence(actor, evidence_id)
    _require_editable(existing)

    compliance_repository.record(
        action="delete", entity="evidence", entity_id=evidence_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {existing.title} from apprentice {existing.apprentice_id}'s portfolio",
    )
    repo.delete_evidence(evidence_id)
    logger.info("Evidence %s deleted by %s", evidence_id, actor.username)


def submit_evidence(actor: Actor, evidence_id: int) -> Evidence:
    """Hand a piece of evidence to an assessor."""
    existing = _require_evidence(actor, evidence_id)
    if not actor.is_admin and not (
        actor.role == config.APPRENTICE and existing.apprentice_id == actor.apprentice_id
    ):
        raise PermissionDenied("Only the apprentice whose portfolio this is may submit evidence")
    require_evidence_status(existing.status, "Submitted")

    repo.set_evidence_status(evidence_id, "Submitted", submitted_at=_now())
    compliance_repository.record(
        action="update", entity="evidence", entity_id=evidence_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Submitted for assessment: {existing.title}",
    )
    logger.info("Evidence %s submitted by %s", evidence_id, actor.username)

    updated = repo.get_evidence(evidence_id)
    assert updated is not None
    return updated


def assess_evidence(
    actor: Actor,
    evidence_id: int,
    *,
    outcome: str,
    feedback: str | None = None,
) -> Evidence:
    """Record an assessor's judgement on a piece of evidence."""
    require(actor, "portfolio.assess")
    existing = _require_evidence(actor, evidence_id)

    decision = (outcome or "").strip().title()
    if decision not in _ASSESSMENT_OUTCOMES:
        allowed = ", ".join(_ASSESSMENT_OUTCOMES)
        raise ValidationError(f"Assessment outcome must be one of: {allowed}")
    require_evidence_status(existing.status, decision)

    note = _optional_text(feedback)
    if decision in ("Referred", "Rejected") and not note:
        raise ValidationError(
            "Feedback is required when referring or rejecting evidence: the work goes "
            "back to the apprentice, and they cannot fix what they were not told about."
        )

    repo.set_evidence_status(
        evidence_id, decision,
        assessor_id=actor.staff_id, assessed_at=_now(), feedback=note,
    )
    compliance_repository.record(
        action="approve" if decision == "Accepted" else "reject",
        entity="evidence", entity_id=evidence_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{decision}: {existing.title}" + (f" ({note})" if note else ""),
    )
    logger.info("Evidence %s assessed %s by %s", evidence_id, decision, actor.username)

    updated = repo.get_evidence(evidence_id)
    assert updated is not None
    return updated


def verify_evidence(
    actor: Actor,
    evidence_id: int,
    *,
    outcome: str,
    comments: str | None = None,
) -> dict[str, Any]:
    """Record an IQA sampling decision on assessed evidence.

    Verifications accumulate rather than replace: the sampling history is
    what the external quality assurer asks to see.
    """
    require(actor, "portfolio.verify")
    existing = _require_evidence(actor, evidence_id)
    decision = _require_text(outcome, "Verification outcome")
    if not existing.is_assessed:
        raise ValidationError(
            "There is no assessment decision to sample yet — this evidence is "
            f"{existing.status.lower()}"
        )

    verification_id = repo.add_verification(
        evidence_id,
        verifier_id=actor.staff_id,
        outcome=decision,
        comments=_optional_text(comments),
    )
    compliance_repository.record(
        action="sign", entity="portfolio_verification", entity_id=verification_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Sampled evidence {evidence_id}: {decision}",
    )
    logger.info("Evidence %s verified %s by %s", evidence_id, decision, actor.username)

    return next(
        (
            record
            for record in repo.list_verifications(evidence_id)
            if record.get("verification_id") == verification_id
        ),
        {},
    )


# ═════════════════════════════════════════════════════════════════════
# KSB mapping
# ═════════════════════════════════════════════════════════════════════

def map_to_ksb(
    actor: Actor,
    evidence_id: int,
    ksb_id: int,
    *,
    coverage: str,
    note: str | None = None,
) -> EvidenceMapping:
    """Claim that a piece of evidence shows a particular KSB."""
    require_any(actor, "portfolio.upload", "portfolio.assess")
    existing = _require_evidence(actor, evidence_id)
    level = _validate_claim(actor, coverage)

    ksb = programme_repository.get_ksb(ksb_id)
    if ksb is None:
        raise ValidationError(f"No KSB with id {ksb_id}")
    apprentice = apprentice_repository.get(existing.apprentice_id)
    # A KSB from another standard would never appear in the coverage
    # roll-up, so the mapping would silently do nothing.
    if apprentice and apprentice.programme_id and ksb.programme_id != apprentice.programme_id:
        raise ValidationError(f"KSB {ksb.code} belongs to a different programme")

    map_id = repo.add_mapping(
        evidence_id, ksb_id, coverage=level, assessor_note=_optional_text(note)
    )
    compliance_repository.record(
        action="update", entity="evidence_ksb_map", entity_id=map_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Evidence {evidence_id} mapped to {ksb.code} at {level}",
    )
    logger.info(
        "Evidence %s mapped to KSB %s at %s by %s",
        evidence_id, ksb.code, level, actor.username,
    )

    return _find_mapping(evidence_id, map_id)


def update_mapping(
    actor: Actor,
    map_id: int,
    *,
    coverage: str | None = None,
    note: str | None = None,
) -> EvidenceMapping:
    """Re-judge a mapping, or annotate it."""
    require_any(actor, "portfolio.upload", "portfolio.assess")
    existing = _require_mapping(actor, map_id)

    level = _validate_claim(actor, coverage) if coverage is not None else None
    repo.update_mapping(map_id, coverage=level, assessor_note=_optional_text(note))
    compliance_repository.record(
        action="update", entity="evidence_ksb_map", entity_id=map_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{existing.ksb_code} set to {level}" if level else f"{existing.ksb_code} annotated",
    )

    return _find_mapping(existing.evidence_id, map_id)


def unmap_ksb(actor: Actor, map_id: int) -> None:
    """Withdraw a claim that a piece of evidence shows a KSB."""
    require_any(actor, "portfolio.upload", "portfolio.assess")
    existing = _require_mapping(actor, map_id)

    compliance_repository.record(
        action="delete", entity="evidence_ksb_map", entity_id=map_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Evidence {existing.evidence_id} unmapped from {existing.ksb_code}",
    )
    repo.remove_mapping(map_id)
    logger.info("KSB mapping %s removed by %s", map_id, actor.username)


def _validate_claim(actor: Actor, coverage: str | None) -> str:
    """Check a coverage judgement *actor* is entitled to make.

    Mapping evidence to a KSB is the apprentice's claim — "this is where
    I show it". Deciding that the claim lands at Competent is the
    assessor's judgement, and it is the judgement the gateway check
    reads, so an apprentice may map at Not started or Developing and no
    higher. Otherwise a portfolio could declare itself complete and walk
    an apprentice into an end-point assessment nobody has verified them
    ready for.
    """
    level = validate_coverage(coverage)
    if level == "Competent" and not actor.can("portfolio.assess"):
        raise PermissionDenied(
            "Only an assessor may record a KSB as Competent. Map the evidence at "
            "'Developing' and your assessor will judge it."
        )
    return level


# ═════════════════════════════════════════════════════════════════════
# Loading and validation
# ═════════════════════════════════════════════════════════════════════

def _require_apprentice(actor: Actor, apprentice_id: int) -> Apprentice:
    """Load an apprentice, refusing if *actor* may not see them."""
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)
    return apprentice


def _require_evidence(actor: Actor, evidence_id: int) -> Evidence:
    existing = repo.get_evidence(evidence_id)
    if existing is None:
        raise ValidationError(f"No evidence with id {evidence_id}")
    _require_apprentice(actor, existing.apprentice_id)
    return existing


def _require_mapping(actor: Actor, map_id: int) -> EvidenceMapping:
    """Find a mapping within *actor*'s own scope.

    The repository fetches mappings by evidence, never by mapping id, so
    the search runs over the evidence this actor may already see. A
    mapping on somebody else's portfolio therefore reads as missing
    rather than refused — the same non-disclosure the apprentice lookups
    give.
    """
    for item in list_evidence(actor):
        for mapping in item.mappings:
            if mapping.map_id == map_id:
                return mapping
    raise ValidationError(f"No KSB mapping with id {map_id}")


def _find_mapping(evidence_id: int, map_id: int) -> EvidenceMapping:
    """Re-read a mapping after writing it, for the denormalised KSB labels."""
    for mapping in repo.list_mappings(evidence_id):
        if mapping.map_id == map_id:
            return mapping
    raise ValidationError(f"No KSB mapping with id {map_id}")


def _require_editable(existing: Evidence) -> None:
    if not existing.is_editable:
        raise ValidationError(
            f"This evidence is {existing.status.lower()} and can no longer be changed. "
            "Submitted work is with the assessor, and accepted work is locked because "
            "the KSBs it covers depend on it."
        )


def _validate(payload: dict[str, Any], *, existing: Evidence | None) -> dict[str, Any]:
    """Normalise and check an evidence payload.

    Only keys actually present are validated and returned, so a partial
    edit does not blank the fields the form did not show.

    Status, assessor and the assessment stamps are deliberately not read
    from the payload: they are the assessor's decision, written by
    :func:`assess_evidence`, and a form able to set them could accept its
    own evidence.
    """
    data: dict[str, Any] = {}

    if "apprentice_id" in payload:
        data["apprentice_id"] = _validate_fk(
            payload.get("apprentice_id"), apprentice_repository.get, "apprentice"
        )
    if existing is None or "title" in payload:
        data["title"] = _require_text(payload.get("title"), "Title")
    if existing is None or "evidence_type" in payload:
        data["evidence_type"] = validate_evidence_type(payload.get("evidence_type"))
    if "description" in payload:
        data["description"] = _optional_text(payload.get("description"))
    if "file_name" in payload:
        data["file_name"] = _optional_text(payload.get("file_name"))

    return data


def _require_text(value: Any, label: str, *, max_length: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{label} is required")
    if len(text) > max_length:
        raise ValidationError(f"{label} must be {max_length} characters or fewer")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _validate_fk(value: Any, lookup: Any, label: str) -> int | None:
    """Check a foreign key points at something that exists."""
    if value in (None, "", 0, "0"):
        return None
    try:
        key = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label.capitalize()} is not valid") from exc
    if lookup(key) is None:
        raise ValidationError(f"No {label} with id {key}")
    return key


def _now() -> str:
    """A timestamp in the format SQLite's ``datetime('now')`` writes.

    The stamps this module sets sit in the same rows as repository-set
    columns, so they have to sort against them.
    """
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
