"""The admissions queue: decide on the people who have applied.

An apprentice record starts life at ``Applicant`` — created by hand when
somebody walks in, or by the cross-system adapter when a sixth form, FE
college, secondary school or university hands a learner over. Either way
somebody at the provider has to say yes or no, and that decision is what
this module is for.

Two things happen on each decision, and keeping them together is the
whole point of putting this in a service rather than in the screens:

**The local record moves.** Accepting takes the applicant onto
programme; declining withdraws them, keeping the record and the reason.

**The cross-system transition is closed out.** An applicant who arrived
from another system has an open ``learner_transition`` row. Accepting
completes it — which links the journey slot, closes the source enrolment
and publishes the completion event. Declining cancels it, so the sending
system stops showing the learner as in-flight and can record a different
destination.

The second half is best-effort throughout. A locally created applicant
has no transition at all, and a platform that is unreachable must not
stop a provider deciding on a real person in front of them. Failures are
logged and reported back on the result rather than raised.

Whether the source enrolment closes is not decided here: it comes from
the boundary's :class:`~...handover.HandoverSpec`. ``university ->
apprenticeships`` declares ``creates="concurrent_enrolment"`` because a
degree apprentice stays enrolled at the university, so accepting one
must not close the course they are still studying.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from education_system.systems.apprenticeships.domain.apprentices.models import (
    ApprenticeSummary,
    ValidationError,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    compliance_repository,
)
from education_system.systems.apprenticeships.services import apprentice_service
from education_system.systems.apprenticeships.services.access import Actor, require

logger = logging.getLogger(__name__)

SYSTEM_KEY = "apprenticeships"

#: The status an application sits at until somebody decides.
APPLICANT_STATUS = "Applicant"

#: Where a decline lands. Not a delete: a rejected application is part of
#: the provider's recruitment record and its reason is auditable.
DECLINED_STATUS = "Withdrawn"


@dataclass
class Application:
    """One person awaiting a decision, with where they came from.

    ``source_system`` and ``transition_id`` are ``None`` for a walk-in
    created directly in this system — which is normal, and the only
    difference it makes is that there is no transition to close out.
    """

    summary: ApprenticeSummary
    journey_id: str | None = None
    source_system: str | None = None
    transition_id: str | None = None
    transition_status: str | None = None
    applied_at: str | None = None

    @property
    def apprentice_id(self) -> int:
        return self.summary.apprentice.apprentice_id

    @property
    def full_name(self) -> str:
        return self.summary.full_name

    @property
    def is_cross_system(self) -> bool:
        return self.transition_id is not None

    @property
    def origin_label(self) -> str:
        """Where this application came from, for a list column."""
        if not self.source_system:
            return "Direct application"
        pretty = self.source_system.replace("_", " ").title()
        return f"{pretty} transfer"


@dataclass
class Decision:
    """The outcome of an accept or decline.

    ``platform_error`` is set when the local decision succeeded but the
    cross-system half did not. Screens surface it as a warning, not a
    failure — the provider's decision stands and the transition can be
    reconciled later.
    """

    apprentice_id: int
    full_name: str
    status: str
    transition_closed: bool = False
    source_closed: bool = True
    platform_error: str | None = None


# ═════════════════════════════════════════════════════════════════════
# Cross-system lookups (all best-effort)
# ═════════════════════════════════════════════════════════════════════

def _journey_ids(apprentice_ids: list[int]) -> dict[int, str]:
    """``{apprentice_id: journey_id}`` for the ones that have been linked.

    Read straight from the column rather than through the repository
    mappers: ``journey_id`` is a platform link, not part of the domain
    model, and threading it through every mapper would put a
    cross-system concern into the apprentice dataclass.
    """
    if not apprentice_ids:
        return {}
    from education_system.systems.apprenticeships.infrastructure.persistence.schema import (
        connect,
        init_db,
    )
    init_db()
    placeholders = ", ".join("?" for _ in apprentice_ids)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT apprentice_id, journey_id FROM apprentices "  # noqa: S608
            f"WHERE apprentice_id IN ({placeholders}) AND journey_id IS NOT NULL",
            apprentice_ids,
        ).fetchall()
    return {int(r["apprentice_id"]): r["journey_id"] for r in rows}


def _open_transitions() -> dict[str, dict]:
    """``{journey_id: transition}`` for everything heading into this system.

    Returns ``{}`` if the platform is unreachable, so the queue still
    renders from local records alone.
    """
    try:
        from education_system.platform.cross_system import transitions
        rows = transitions.pending_transitions(SYSTEM_KEY)
    except Exception:
        logger.exception(
            "Could not read pending transitions; the admissions queue will "
            "show local applicants only")
        return {}
    # Newest wins if a learner somehow has two open transitions inbound —
    # the later one is the live application.
    out: dict[str, dict] = {}
    for row in sorted(rows, key=lambda r: r.get("initiated_at") or ""):
        if row.get("journey_id"):
            out[row["journey_id"]] = row
    return out


def _transition_for(apprentice_id: int) -> dict | None:
    """The open inbound transition for one applicant, if any."""
    journey_id = _journey_ids([apprentice_id]).get(apprentice_id)
    if not journey_id:
        return None
    return _open_transitions().get(journey_id)


def _closes_source(source_system: str | None) -> bool:
    """Whether accepting should close the sending system's enrolment.

    Answered by the boundary spec rather than by a rule here, so
    "university and apprenticeships run concurrently" is stated once, as
    data, next to the fields that boundary carries.
    """
    if not source_system:
        return True
    try:
        from education_system.platform.cross_system import handover
        spec = handover.get_spec(source_system, SYSTEM_KEY)
    except Exception:
        logger.exception("Could not read the handover spec for %s -> %s; "
                         "defaulting to closing the source", source_system,
                         SYSTEM_KEY)
        return True
    return not (spec is not None and spec.creates == "concurrent_enrolment")


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def list_applications(actor: Actor) -> list[Application]:
    """Everyone awaiting a decision, oldest application first.

    Scoped like every other cohort read — an employer sees only the
    applicants attached to them.
    """
    require(actor, "admission.view")
    summaries = apprentice_service.list_apprentices(actor, status=APPLICANT_STATUS)
    if not summaries:
        return []

    ids = [s.apprentice.apprentice_id for s in summaries]
    journeys = _journey_ids(ids)
    open_transitions = _open_transitions() if journeys else {}

    applications = []
    for summary in summaries:
        journey_id = journeys.get(summary.apprentice.apprentice_id)
        transition = open_transitions.get(journey_id) if journey_id else None
        applications.append(Application(
            summary=summary,
            journey_id=journey_id,
            source_system=(transition or {}).get("source_system"),
            transition_id=(transition or {}).get("transition_id"),
            transition_status=(transition or {}).get("status"),
            applied_at=(transition or {}).get("initiated_at")
            or summary.apprentice.created_at,
        ))
    applications.sort(key=lambda a: a.applied_at or "")
    return applications


def get_application(actor: Actor, apprentice_id: int) -> Application:
    """One pending application in full."""
    require(actor, "admission.view")
    summary = apprentice_service.get_apprentice(actor, apprentice_id)
    if summary.apprentice.status != APPLICANT_STATUS:
        raise ValidationError(
            f"{summary.full_name} is {summary.apprentice.status}, not an "
            f"applicant — there is no decision left to make")
    transition = _transition_for(apprentice_id)
    return Application(
        summary=summary,
        journey_id=_journey_ids([apprentice_id]).get(apprentice_id),
        source_system=(transition or {}).get("source_system"),
        transition_id=(transition or {}).get("transition_id"),
        transition_status=(transition or {}).get("status"),
        applied_at=(transition or {}).get("initiated_at")
        or summary.apprentice.created_at,
    )


def pending_count(actor: Actor) -> int:
    """How many applications are waiting, for a dashboard tile."""
    try:
        return len(list_applications(actor))
    except Exception:
        logger.debug("pending_count failed", exc_info=True)
        return 0


# ═════════════════════════════════════════════════════════════════════
# Decisions
# ═════════════════════════════════════════════════════════════════════

def accept(
    actor: Actor,
    apprentice_id: int,
    *,
    start_date: str,
    programme_id: int | None = None,
    employer_id: int | None = None,
    workplace_id: int | None = None,
    tutor_id: int | None = None,
    notes: str | None = None,
) -> Decision:
    """Accept an application and take the applicant onto programme.

    An apprenticeship cannot start without an employer and a programme —
    the employer is a signatory to the training plan, and the programme
    is what the off-the-job target and funding band derive from. Both are
    required here rather than left to be filled in later, because an
    apprentice on programme with neither is a funding claim that will not
    survive audit.
    """
    require(actor, "admission.decide")
    existing = repo.get(apprentice_id)
    if existing is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    if existing.status != APPLICANT_STATUS:
        raise ValidationError(
            f"{existing.full_name} is already {existing.status} — only an "
            f"applicant can be accepted")

    # Either supplied now or already on the record from the handover.
    if (employer_id if employer_id is not None else existing.employer_id) is None:
        raise ValidationError(
            "An employer is required to accept an apprentice — they are a "
            "signatory to the training plan")

    patch: dict[str, Any] = {}
    for field, value in (("employer_id", employer_id),
                         ("workplace_id", workplace_id),
                         ("tutor_id", tutor_id)):
        if value is not None:
            patch[field] = value
    if notes:
        patch["notes"] = f"{existing.notes or ''}\nAccepted: {notes}".strip()
    if patch:
        repo.update(apprentice_id, patch)

    # Captured before the status moves, because completing the transition
    # below needs to know where they came from.
    transition = _transition_for(apprentice_id)

    updated = apprentice_service.start_programme(
        actor, apprentice_id, start_date=start_date, programme_id=programme_id,
    )

    decision = Decision(
        apprentice_id=apprentice_id,
        full_name=updated.full_name,
        status=updated.status,
    )
    if transition is not None:
        decision.source_closed = _closes_source(transition.get("source_system"))
        _complete_transition(transition, str(apprentice_id), start_date,
                             decision)

    compliance_repository.record(
        action="admit", entity="apprentice", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"application accepted, on programme from {start_date}"
               + (f" (from {transition.get('source_system')})"
                  if transition else " (direct application)"),
    )
    logger.info("Accepted application for apprentice %s by %s",
                apprentice_id, actor.username)
    return decision


def decline(
    actor: Actor,
    apprentice_id: int,
    *,
    reason: str,
    effective_date: str | None = None,
) -> Decision:
    """Decline an application. The record and the reason are kept.

    A declined applicant is not deleted: the provider has to be able to
    show who applied and why they were turned down, and the sending
    system needs the transition cancelled so it can record a different
    destination for the learner.
    """
    require(actor, "admission.decide")
    if not (reason or "").strip():
        raise ValidationError("A reason is required to decline an application")

    existing = repo.get(apprentice_id)
    if existing is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    if existing.status != APPLICANT_STATUS:
        raise ValidationError(
            f"{existing.full_name} is {existing.status} — only an applicant "
            f"can be declined")

    transition = _transition_for(apprentice_id)
    when = effective_date or date.today().isoformat()

    updated = apprentice_service.change_status(
        actor, apprentice_id, DECLINED_STATUS,
        reason=f"Application declined: {reason}", effective_date=when,
    )

    decision = Decision(
        apprentice_id=apprentice_id,
        full_name=updated.full_name,
        status=updated.status,
    )
    if transition is not None:
        _cancel_transition(transition, reason, decision)

    compliance_repository.record(
        action="update", entity="apprentice", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"application declined: {reason}",
    )
    logger.info("Declined application for apprentice %s by %s (%s)",
                apprentice_id, actor.username, reason)
    return decision


# ═════════════════════════════════════════════════════════════════════
# Cross-system side effects — never fatal to the local decision
# ═════════════════════════════════════════════════════════════════════

def _complete_transition(transition: dict, local_id: str, start_date: str,
                         decision: Decision) -> None:
    """Walk an accepted transition to ``completed``.

    The workflow only moves forward and may jump, so an application that
    never had an explicit offer step goes straight to ``admitted``.
    """
    transition_id = transition["transition_id"]
    try:
        from education_system.platform.cross_system import transitions
        if transition.get("status") != "admitted":
            transitions.admit(transition_id, local_student_id=local_id,
                              start_date=start_date)
        transitions.complete(transition_id, start_date=start_date,
                             close_source=decision.source_closed,
                             source_exit_reason="started an apprenticeship")
        decision.transition_closed = True
        logger.info(
            "Completed transition %s into apprenticeships (source %s %s)",
            transition_id, transition.get("source_system"),
            "closed" if decision.source_closed else "left open — concurrent")
    except Exception as exc:
        decision.platform_error = (
            f"The apprentice is on programme, but the transfer from "
            f"{transition.get('source_system') or 'the sending system'} could "
            f"not be closed off ({exc}). It stays in their queue until it is "
            f"retried.")
        logger.exception("Could not complete transition %s", transition_id)


def _cancel_transition(transition: dict, reason: str,
                       decision: Decision) -> None:
    """Cancel a declined transition so the sender stops waiting."""
    transition_id = transition["transition_id"]
    try:
        from education_system.platform.cross_system import transitions
        transitions.cancel(transition_id,
                           reason=f"Application declined: {reason}")
        decision.transition_closed = True
        logger.info("Cancelled transition %s (application declined)",
                    transition_id)
    except Exception as exc:
        decision.platform_error = (
            f"The application is declined here, but "
            f"{transition.get('source_system') or 'the sending system'} could "
            f"not be told ({exc}). It may still show the learner as "
            f"transferring.")
        logger.exception("Could not cancel transition %s", transition_id)


__all__ = [
    "APPLICANT_STATUS",
    "DECLINED_STATUS",
    "Application",
    "Decision",
    "list_applications",
    "get_application",
    "pending_count",
    "accept",
    "decline",
]
