"""Compliance: eligibility, documents, functional skills, audit, retention.

Funding is conditional on paperwork. An apprentice who was never
eligible, or whose training plan was never signed, generates a clawback
at audit however good the training was — so this module is where the
evidence gets recorded, checked and, at the end, assembled into the pack
an auditor asks for.

Two permissions gate it: ``compliance.view`` to read a position and
``compliance.manage`` to change one. The audit trail and the retention
report sit above both — they are administrator-only, because a log that
records everyone's actions must not be readable by the people it
records.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.compliance.eligibility import (
    AuditEntry,
    ComplianceDocument,
    ComplianceStatus,
    EligibilityCheck,
    FunctionalSkill,
    retention_expiry,
    validate_check_key,
    validate_doc_key,
    validate_doc_status,
    validate_fs_status,
    validate_subject,
)
from education_system.systems.apprenticeships.domain.training.off_the_job_hours import target_hours
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    compliance_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    epa_repository,
    review_repository,
    training_repository,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Status
# ═════════════════════════════════════════════════════════════════════

def get_status(actor: Actor, apprentice_id: int) -> ComplianceStatus:
    """One apprentice's whole compliance position."""
    _apprentice(actor, apprentice_id)
    require(actor, "compliance.view")
    return repo.build_status(apprentice_id)


# ═════════════════════════════════════════════════════════════════════
# Eligibility
# ═════════════════════════════════════════════════════════════════════

def set_eligibility_check(
    actor: Actor,
    apprentice_id: int,
    check_key: str,
    *,
    passed: bool,
    evidence: str | None = None,
) -> EligibilityCheck:
    """Record the outcome of one eligibility criterion.

    Who checked it and when are stamped from the actor rather than taken
    from the caller: at audit the question is who attested to this, and
    a self-declared name would not answer it.
    """
    require(actor, "compliance.manage")
    _apprentice(actor, apprentice_id)
    key = validate_check_key(check_key)

    repo.set_eligibility(
        apprentice_id,
        key,
        passed=bool(passed),
        evidence=_optional_text(evidence),
        checked_by=actor.username,
        checked_at=date.today().isoformat(),
    )
    repo.record(
        action="approve" if passed else "reject", entity="eligibility_check",
        entity_id=f"{apprentice_id}:{key}",
        actor=actor.username, actor_role=actor.role,
        detail=f"{key} {'passed' if passed else 'not passed'}",
    )
    logger.info(
        "Eligibility %s for apprentice %s set to %s by %s",
        key, apprentice_id, bool(passed), actor.username,
    )

    check = next(c for c in repo.list_eligibility(apprentice_id) if c.check_key == key)
    return check


# ═════════════════════════════════════════════════════════════════════
# Documents
# ═════════════════════════════════════════════════════════════════════

def set_document(
    actor: Actor,
    apprentice_id: int,
    doc_key: str,
    *,
    status: str,
    issued_date: str | None = None,
    signed_date: str | None = None,
    expiry_date: str | None = None,
    notes: str | None = None,
) -> ComplianceDocument:
    """Record where a compliance document has got to."""
    require(actor, "compliance.manage")
    _apprentice(actor, apprentice_id)
    key = validate_doc_key(doc_key)
    state = validate_doc_status(status)

    signed = _validate_date(signed_date, "Signed date")
    if state == "Signed" and not signed:
        signed = date.today().isoformat()

    existing = next((d for d in repo.list_documents(apprentice_id) if d.doc_key == key), None)
    repo.set_document(
        apprentice_id,
        key,
        status=state,
        issued_date=_validate_date(issued_date, "Issued date"),
        signed_date=signed,
        expiry_date=_validate_date(expiry_date, "Expiry date"),
        # The upsert rewrites every column and there is no file argument
        # here, so the stored file name is carried forward rather than
        # blanked by an unrelated status change.
        file_name=existing.file_name if existing else None,
        notes=_optional_text(notes),
    )
    repo.record(
        action="update", entity="compliance_document", entity_id=f"{apprentice_id}:{key}",
        actor=actor.username, actor_role=actor.role, detail=f"{key} -> {state}",
    )
    logger.info(
        "Document %s for apprentice %s set to %s by %s",
        key, apprentice_id, state, actor.username,
    )

    document = next(d for d in repo.list_documents(apprentice_id) if d.doc_key == key)
    return document


# ═════════════════════════════════════════════════════════════════════
# Functional skills
# ═════════════════════════════════════════════════════════════════════

def set_functional_skill(
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
    """Record an apprentice's position in English or Maths.

    Achieved and Exempt both satisfy the gateway check, so both have to
    carry their evidence: a level for an achievement, a recognised reason
    for an exemption. Without that an unevidenced click on either would
    let somebody through gateway on nothing.
    """
    require(actor, "compliance.manage")
    _apprentice(actor, apprentice_id)
    subject_name = validate_subject(subject)
    state = validate_fs_status(status)

    achieved = _validate_date(achieved_date, "Achieved date")
    reason = _optional_text(exemption_reason)
    skill_level = _optional_text(level)

    if state == "Exempt":
        if not reason:
            raise ValidationError("An exemption needs a reason")
        if reason not in config.EXEMPTION_REASONS:
            allowed = ", ".join(config.EXEMPTION_REASONS)
            raise ValidationError(f"Exemption reason must be one of: {allowed}")
    if state == "Achieved":
        if not skill_level:
            raise ValidationError("An achieved functional skill needs a level")
        if skill_level not in config.FUNCTIONAL_SKILL_LEVELS:
            allowed = ", ".join(config.FUNCTIONAL_SKILL_LEVELS)
            raise ValidationError(f"Level must be one of: {allowed}")
        achieved = achieved or date.today().isoformat()

    repo.set_functional_skill(
        apprentice_id,
        subject_name,
        status=state,
        level=skill_level,
        achieved_date=achieved,
        exemption_reason=reason,
        notes=_optional_text(notes),
    )
    repo.record(
        action="update", entity="functional_skill",
        entity_id=f"{apprentice_id}:{subject_name}",
        actor=actor.username, actor_role=actor.role,
        detail=f"{subject_name} -> {state}" + (f" ({skill_level})" if skill_level else ""),
    )
    logger.info(
        "Functional skill %s for apprentice %s set to %s by %s",
        subject_name, apprentice_id, state, actor.username,
    )

    skill = repo.get_functional_skill(apprentice_id, subject_name)
    assert skill is not None
    return skill


def functional_skills_summary(actor: Actor, apprentice_id: int) -> dict[str, Any]:
    """English and Maths at a glance, plus whether gateway is satisfied."""
    _apprentice(actor, apprentice_id)
    require(actor, "compliance.view")

    skills = repo.list_functional_skills(apprentice_id)
    return {
        "apprentice_id": apprentice_id,
        "subjects": {
            skill.subject: {
                "status": skill.status,
                "level": skill.level,
                "achieved_date": skill.achieved_date,
                "exemption_reason": skill.exemption_reason,
                "notes": skill.notes,
                "is_satisfied": skill.is_satisfied,
            }
            for skill in skills
        },
        "outstanding": [s.subject for s in skills if not s.is_satisfied],
        "all_satisfied": bool(skills) and all(s.is_satisfied for s in skills),
    }


# ═════════════════════════════════════════════════════════════════════
# Dashboard
# ═════════════════════════════════════════════════════════════════════

def compliance_dashboard(actor: Actor) -> dict[str, Any]:
    """Red / amber / green across the cohort *actor* is responsible for."""
    require(actor, "compliance.view")
    scope = _cohort_scope(actor)
    flagged = repo.flagged_apprentices(**scope)

    # Mirrors the status filter inside flagged_apprentices: the two counts
    # are subtracted from each other below, so they must cover the same
    # population or green comes out wrong.
    cohort = [
        s for s in apprentice_repository.list_summaries(**scope)
        if s.apprentice.status not in ("Withdrawn", "Transferred")
    ]
    red = sum(1 for row in flagged if row.get("rag") == "Red")
    amber = sum(1 for row in flagged if row.get("rag") == "Amber")
    return {
        "total": len(cohort),
        "red": red,
        "amber": amber,
        "green": max(0, len(cohort) - len(flagged)),
        "flagged": flagged,
    }


# ═════════════════════════════════════════════════════════════════════
# Audit and retention
# ═════════════════════════════════════════════════════════════════════

def audit_trail(
    actor: Actor,
    *,
    entity: str | None = None,
    entity_id: str | int | None = None,
    actor_username: str | None = None,
    action: str | None = None,
    since: str | None = None,
    until: str | None = None,
    changes_only: bool = False,
    limit: int = 200,
) -> list[AuditEntry]:
    """The audit log. Administrators only.

    Deliberately not scoped-and-shared: the log records what every user
    did, so letting a tutor read their own slice would also show them who
    else touched those records. It is an administrator's tool.

    Each entry is an ``AuditRecord`` — an ``AuditEntry`` that also
    carries the ``field: before → after`` changes an edit recorded.
    *since* and *until* are inclusive ``YYYY-MM-DD`` dates.
    """
    _require_admin(actor, "the audit trail")
    return repo.list_audit(
        entity=entity or None, entity_id=entity_id, actor=actor_username or None,
        action=action or None,
        since=_validate_date(since, "From date"), until=_validate_date(until, "To date"),
        changes_only=changes_only, limit=_validate_limit(limit),
    )


def audit_filter_options(actor: Actor) -> dict[str, list[str]]:
    """Entities, actors and actions to offer as audit-log filters."""
    _require_admin(actor, "the audit trail")
    values = repo.audit_filter_values()
    return {**values, "actions": list(config.AUDIT_ACTIONS)}


def _validate_limit(value: Any) -> int:
    """At least one row, at most a few thousand — the screen is not an export."""
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("The row limit must be a whole number") from exc
    return max(1, min(limit, 5000))


def retention_report(actor: Actor) -> list[dict[str, Any]]:
    """Records held past their retention period. Administrators only."""
    _require_admin(actor, "the retention report")
    return [
        {**row, "retention_expiry": retention_expiry(row.get("actual_end_date"))}
        for row in repo.retention_due(date.today().isoformat())
    ]


# ═════════════════════════════════════════════════════════════════════
# Evidence pack
# ═════════════════════════════════════════════════════════════════════

def evidence_pack(actor: Actor, apprentice_id: int) -> dict[str, Any]:
    """Everything a funding audit asks for about one apprentice.

    Returned as plain data rather than domain objects so the report and
    export screens can render it without reaching back into the domain.
    """
    if not actor.is_provider:
        raise PermissionDenied("The funding evidence pack is for provider staff only")
    require(actor, "compliance.view")

    summary = apprentice_repository.get_summary(apprentice_id)
    if summary is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, summary)
    apprentice = summary.apprentice

    status = repo.build_status(apprentice_id)
    totals = training_repository.hour_totals(apprentice_id)
    target = target_hours(
        apprentice.start_date, apprentice.planned_end_date, apprentice.weekly_hours
    )
    approved = float(totals.get("approved", 0.0))
    gateway = epa_repository.get_gateway_row(apprentice_id) or {}
    results = epa_repository.list_results(apprentice_id=apprentice_id)

    repo.record(
        action="export", entity="evidence_pack", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Evidence pack for {apprentice.full_name}",
    )
    logger.info("Evidence pack for apprentice %s assembled by %s", apprentice_id, actor.username)

    return {
        "generated_at": date.today().isoformat(),
        "generated_by": actor.username,
        "apprentice": {
            "apprentice_id": apprentice_id,
            "name": apprentice.full_name,
            "uln": apprentice.uln,
            "date_of_birth": apprentice.date_of_birth,
            "status": apprentice.status,
            "programme": summary.programme_title,
            "programme_reference": summary.programme_reference,
            "level": summary.programme_level,
            "employer": summary.employer_name,
            "tutor": summary.tutor_name,
            "funding_model": apprentice.funding_model,
            "weekly_hours": apprentice.weekly_hours,
            "start_date": apprentice.start_date,
            "planned_end_date": apprentice.planned_end_date,
            "actual_end_date": apprentice.actual_end_date,
        },
        "compliance": {
            "rag": status.rag_rating,
            "is_eligible": status.is_eligible,
            "is_audit_ready": status.is_audit_ready,
            "eligibility_passed": status.eligibility_passed,
            "eligibility_total": len(status.eligibility),
            "failed_checks": [c.label for c in status.failed_checks],
            "documents_signed": status.documents_signed,
            "documents_total": len(status.documents),
            "missing_documents": [d.label for d in status.missing_documents],
            "missing_pre_start": [d.label for d in status.missing_pre_start],
            "expired_documents": [d.label for d in status.expired_documents],
        },
        "functional_skills": [
            {
                "subject": s.subject,
                "status": s.status,
                "level": s.level,
                "achieved_date": s.achieved_date,
                "exemption_reason": s.exemption_reason,
                "is_satisfied": s.is_satisfied,
            }
            for s in status.functional_skills
        ],
        "reviews": {
            "signed": review_repository.held_review_count(apprentice_id),
            "outstanding": review_repository.unsigned_review_count(apprentice_id),
        },
        "off_the_job": {
            "target_hours": target,
            "approved_hours": approved,
            "pending_hours": float(totals.get("pending", 0.0)),
            "shortfall_hours": round(max(0.0, target - approved), 2),
            "target_met": target > 0 and approved >= target,
            "entry_count": int(totals.get("count", 0)),
        },
        "gateway": {
            "status": gateway.get("status") or "Not Ready",
            "requested_at": gateway.get("requested_at"),
            "requested_by": gateway.get("requested_by"),
            "decided_at": gateway.get("decided_at"),
            "decided_by": gateway.get("decided_by"),
            "decision_notes": gateway.get("decision_notes"),
        },
        "epa": {
            "results": [
                {
                    "method": r.method,
                    "grade": r.grade,
                    "assessed_date": r.assessed_date,
                    "attempt": r.attempt,
                    "is_pass": r.is_pass,
                }
                for r in results
            ],
            "all_passed": bool(results) and all(r.is_pass for r in results),
        },
        "retention_expiry": retention_expiry(apprentice.actual_end_date),
    }


# ═════════════════════════════════════════════════════════════════════
# Validation
# ═════════════════════════════════════════════════════════════════════

# No primary key is ever negative, so this matches nothing — an actor
# whose scope did not resolve sees an empty cohort, not everybody's.
_NO_MATCH = -1


def _require_admin(actor: Actor, what: str) -> None:
    if not actor.is_admin:
        raise PermissionDenied(f"Only an administrator may read {what}")


def _apprentice(actor: Actor, apprentice_id: int) -> Any:
    """Load an apprentice and refuse if *actor* may not see them."""
    record = apprentice_repository.get(apprentice_id)
    if record is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, record)
    return record


def _cohort_scope(actor: Actor) -> dict[str, Any]:
    """Repository filters restricting the dashboard to *actor*'s cohort."""
    if actor.is_admin:
        return {}
    if actor.role == config.STAFF:
        return {"tutor_id": actor.staff_id or _NO_MATCH}
    if actor.role == config.EMPLOYER:
        return {"employer_id": actor.employer_id or _NO_MATCH}
    return {"tutor_id": _NO_MATCH}


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _validate_date(value: Any, label: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{label} must be a date in YYYY-MM-DD format") from exc
