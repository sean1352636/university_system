"""Gateway: the checkpoint between training and end-point assessment.

Gateway is where the provider, the employer and the apprentice agree that
training is finished and the apprentice is ready to be assessed
independently — and where the EPAO either accepts that or sends them
back. Nothing gets booked with an assessor until it is passed.

The rules themselves live in ``domain.end_point_assessment.gateway``.
This module gathers the facts they judge, applies the permission and
scope checks, and records the decisions.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ValidationError,
)
from education_system.systems.apprenticeships.domain.end_point_assessment import gateway
from education_system.systems.apprenticeships.domain.end_point_assessment.gateway import (
    GatewayRecord,
)
from education_system.systems.apprenticeships.domain.training import off_the_job_hours
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    epa_repository,
    portfolio_repository,
    programme_repository,
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
# Evaluation
# ═════════════════════════════════════════════════════════════════════

def evaluate_gateway(actor: Actor, apprentice_id: int) -> GatewayRecord:
    """Where this apprentice stands against every gateway requirement.

    The central read of this module: every screen, and every decision
    below, goes through it.
    """
    require(actor, "gateway.view")
    apprentice = _load(actor, apprentice_id)
    return _build_record(apprentice)


def _build_record(apprentice: Apprentice) -> GatewayRecord:
    """Assemble the live gateway position for one apprentice.

    Only the stored row and the employer's sign-off are read from the
    gateway tables. The automatic checks are recomputed from the hour
    log, the functional skills, the portfolio and the reviews on every
    call rather than being stored, so they cannot go stale: a hand-back
    of approved hours or a KSB reopened for more evidence takes the
    requirement with it, which is exactly what gateway exists to catch.
    """
    apprentice_id = apprentice.apprentice_id
    row = epa_repository.get_gateway_row(apprentice_id) or {}

    hours = training_repository.hour_totals(apprentice_id)
    skills = compliance_repository.functional_skill_statuses(apprentice_id)
    ksbs_total = 0
    ksbs_competent = 0
    if apprentice.programme_id:
        ksbs_total = programme_repository.count_ksbs(apprentice.programme_id)
        coverage = portfolio_repository.coverage_for(apprentice_id, apprentice.programme_id)
        ksbs_competent = sum(1 for c in coverage if c.is_competent)
    sign_off = epa_repository.get_manual_check(apprentice_id, "employer_sign_off") or {}

    checks = gateway.evaluate(
        apprentice_id=apprentice_id,
        otj_target=off_the_job_hours.target_hours(
            apprentice.start_date, apprentice.planned_end_date, apprentice.weekly_hours
        ),
        otj_approved=hours["approved"],
        english_status=skills.get("English"),
        maths_status=skills.get("Maths"),
        ksbs_total=ksbs_total,
        ksbs_competent=ksbs_competent,
        reviews_outstanding=review_repository.unsigned_review_count(apprentice_id),
        reviews_held=review_repository.held_review_count(apprentice_id),
        start_date=apprentice.start_date,
        employer_signed_off=bool(sign_off.get("met")),
        employer_note=sign_off.get("evidence_note"),
        employer_checked_by=sign_off.get("checked_by"),
        employer_checked_at=sign_off.get("checked_at"),
    )
    return GatewayRecord(
        apprentice_id=apprentice_id,
        status=row.get("status") or "Not Ready",
        gateway_id=row.get("gateway_id"),
        requested_at=row.get("requested_at"),
        requested_by=row.get("requested_by"),
        decided_at=row.get("decided_at"),
        decided_by=row.get("decided_by"),
        decision_notes=row.get("decision_notes"),
        checks=checks,
    )


# ═════════════════════════════════════════════════════════════════════
# Decisions
# ═════════════════════════════════════════════════════════════════════

def set_employer_sign_off(
    actor: Actor,
    apprentice_id: int,
    *,
    confirmed: bool,
    note: str | None = None,
) -> GatewayRecord:
    """Record the employer's confirmation that the apprentice is ready.

    The one requirement no system can derive. The employer themselves may
    record it, and so may the provider staff who hold ``gateway.request``
    — a sign-off given verbally in a review still has to be recorded by
    somebody, and the ``checked_by`` stamp keeps the attribution honest.
    """
    apprentice = _load(actor, apprentice_id)
    if not (actor.can("gateway.request") or _is_employer_for(actor, apprentice)):
        raise PermissionDenied("Only the employer or the provider may record this sign-off")

    epa_repository.set_manual_check(
        apprentice_id,
        "employer_sign_off",
        met=bool(confirmed),
        evidence_note=_optional_text(note),
        checked_by=actor.username,
        checked_at=date.today().isoformat(),
    )
    compliance_repository.record(
        action="sign", entity="gateway", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Employer sign-off {'confirmed' if confirmed else 'withdrawn'}",
    )
    logger.info(
        "Gateway employer sign-off for apprentice %s set to %s by %s",
        apprentice_id, bool(confirmed), actor.username,
    )
    return _build_record(apprentice)


def request_gateway(actor: Actor, apprentice_id: int, *, note: str | None = None) -> GatewayRecord:
    """Put an apprentice forward to the EPAO.

    Refused unless every requirement is met — the error names the ones
    that are not. The apprentice moves to the ``Gateway`` status at the
    same time so the funding and caseload screens stop treating them as
    still in training.
    """
    require(actor, "gateway.request")
    apprentice = _load(actor, apprentice_id)
    record = _build_record(apprentice)
    gateway.require_ready(record)
    gateway.require_status(record.status, "Requested")

    # ``decision_notes`` belongs to the EPAO's answer, not the request, so
    # a requester's note goes to the audit trail instead of overwriting it.
    epa_repository.set_gateway_status(
        apprentice_id,
        "Requested",
        requested_at=date.today().isoformat(),
        requested_by=actor.username,
    )
    compliance_repository.record(
        action="update", entity="gateway", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail="Gateway requested" + (f": {note}" if note else ""),
    )
    logger.info("Gateway requested for apprentice %s by %s", apprentice_id, actor.username)

    if apprentice.status == "On Programme":
        _move_status(actor, apprentice_id, "Gateway", reason="Gateway requested")
    return _build_record(apprentice)


def approve_gateway(actor: Actor, apprentice_id: int, *, note: str | None = None) -> GatewayRecord:
    """Accept a gateway request. EPAO only — that is the independence."""
    require(actor, "gateway.approve")
    apprentice = _load(actor, apprentice_id)
    record = _build_record(apprentice)
    gateway.require_status(record.status, "Approved")

    epa_repository.set_gateway_status(
        apprentice_id,
        "Approved",
        decided_at=date.today().isoformat(),
        decided_by=actor.username,
        decision_notes=_optional_text(note),
    )
    compliance_repository.record(
        action="approve", entity="gateway", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail="Gateway approved" + (f": {note}" if note else ""),
    )
    logger.info("Gateway approved for apprentice %s by %s", apprentice_id, actor.username)
    return _build_record(apprentice)


def reject_gateway(actor: Actor, apprentice_id: int, *, reason: str) -> GatewayRecord:
    """Send a gateway request back, with the reason it failed.

    The apprentice returns to training rather than sitting in limbo:
    whatever the EPAO found is something the provider has to put right
    before re-requesting.
    """
    require(actor, "gateway.approve")
    if not (reason or "").strip():
        raise ValidationError("A reason is required to reject a gateway request")

    apprentice = _load(actor, apprentice_id)
    record = _build_record(apprentice)
    gateway.require_status(record.status, "Rejected")

    epa_repository.set_gateway_status(
        apprentice_id,
        "Rejected",
        decided_at=date.today().isoformat(),
        decided_by=actor.username,
        decision_notes=reason.strip(),
    )
    compliance_repository.record(
        action="reject", entity="gateway", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Gateway rejected: {reason.strip()}",
    )
    logger.info(
        "Gateway rejected for apprentice %s by %s: %s",
        apprentice_id, actor.username, reason.strip(),
    )

    if apprentice.status == "Gateway":
        _move_status(
            actor, apprentice_id, "On Programme",
            reason=f"Gateway rejected: {reason.strip()}",
        )
    return _build_record(apprentice)


# ═════════════════════════════════════════════════════════════════════
# Queues and reporting
# ═════════════════════════════════════════════════════════════════════

def gateway_queue(actor: Actor, *, status: str | None = None) -> list[dict[str, Any]]:
    """Apprentices at or approaching gateway, scoped to *actor*."""
    require(actor, "gateway.view")
    tutor_id: int | None = None
    if actor.role == config.STAFF:
        tutor_id = actor.staff_id if actor.staff_id is not None else _IMPOSSIBLE_ID

    rows = epa_repository.list_gateway_queue(status=status, tutor_id=tutor_id)
    if actor.role in (config.EMPLOYER, config.APPRENTICE):
        # The queue query carries employer *names*, not ids, so the
        # employer and apprentice scopes are applied against the cohort
        # they are already allowed to list.
        visible = _visible_apprentice_ids(actor)
        rows = [r for r in rows if r["apprentice_id"] in visible]
    return rows


def readiness_report(actor: Actor) -> list[dict[str, Any]]:
    """Every active apprentice in scope with what is still outstanding.

    The screen a programme manager runs before a monthly EPA planning
    meeting: who could go to gateway now, and what is holding the rest up.
    """
    require(actor, "gateway.view")
    from education_system.systems.apprenticeships.services import apprentice_service

    report: list[dict[str, Any]] = []
    for summary in apprentice_service.list_apprentices(actor, active_only=True):
        record = _build_record(summary.apprentice)
        report.append({
            "apprentice": summary,
            "met": record.met_count,
            "total": record.total_count,
            "outstanding_labels": [c.label for c in record.outstanding],
            "is_ready": record.is_ready,
        })
    return report


# ═════════════════════════════════════════════════════════════════════
# Internals
# ═════════════════════════════════════════════════════════════════════

# No autoincrement primary key is ever negative, so this matches nothing.
_IMPOSSIBLE_ID = -1


def _load(actor: Actor, apprentice_id: int) -> Apprentice:
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)
    return apprentice


def _is_employer_for(actor: Actor, apprentice: Apprentice) -> bool:
    return (
        actor.role == config.EMPLOYER
        and actor.employer_id is not None
        and apprentice.employer_id == actor.employer_id
    )


def _visible_apprentice_ids(actor: Actor) -> set[int]:
    from education_system.systems.apprenticeships.services import apprentice_service

    return {s.apprentice.apprentice_id for s in apprentice_service.list_apprentices(actor)}


def _move_status(actor: Actor, apprentice_id: int, new_status: str, *, reason: str) -> None:
    """Apply the lifecycle move a gateway decision implies.

    Requesting or deciding gateway is not the same capability as managing
    an apprentice: a tutor holds ``gateway.request`` without
    ``apprentice.manage``, and the EPAO holds neither. The status move is
    a consequence of a decision they were entitled to make, so it runs
    with provider rights while still being audited under their username.
    """
    from education_system.systems.apprenticeships.services import apprentice_service

    apprentice_service.change_status(
        Actor(username=actor.username, role=config.ADMIN, display_name=actor.display_name),
        apprentice_id,
        new_status,
        reason=reason,
    )


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
