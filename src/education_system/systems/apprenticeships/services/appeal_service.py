"""Appeals: lodged by the apprentice, decided by whoever made the call.

Routing by type is the heart of this module. An appeal against an EPA
result is visible to, and decided by, the End-Point Assessment
Organisation alone; every other appeal is decided by the provider's
administrator. Both roles hold ``appeal.decide``, so the permission
check is not enough on its own — :func:`_require_decider` narrows it by
type, and the list query leaves out the rows an actor may not see
rather than filtering them afterwards.

The provider admin not even *seeing* an EPA-result appeal is deliberate
and matches ``config.EPAO_EXCLUSIVE``: the provider is not a party to
the EPAO's own appeals process, and a queue it could watch is a queue it
could lean on.

Apprentices lodge appeals only about themselves, only within
``config.APPEAL_WINDOW_DAYS`` of the decision, and may withdraw their
own while it is still open.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.end_point_assessment.results import (
    EPAResult,
)
from education_system.systems.apprenticeships.domain.quality import appeals as rules
from education_system.systems.apprenticeships.domain.quality.appeals import Appeal
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    appeal_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    epa_repository,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    require,
    require_any,
)

logger = logging.getLogger(__name__)

_DECISION_REF_MAX_LENGTH = 300

# No autoincrement id is negative: an unlinked apprentice login matches nothing.
_IMPOSSIBLE_ID = -1


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def list_appeals(
    actor: Actor,
    *,
    status: str | None = None,
    appeal_type: str | None = None,
    apprentice_id: int | None = None,
    raised_by: str | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    due_before: str | None = None,
    today: date | None = None,
) -> list[Appeal]:
    """The appeals *actor* may see, narrowed by any filters given.

    An apprentice sees their own; the EPAO sees EPA-result appeals; the
    provider admin sees every other type. ``overdue_only`` judges the
    decision deadline against *today* (default: the real today).
    """
    require_any(actor, "appeal.raise", "appeal.decide")
    scope = _scope(actor)
    if "apprentice_id" in scope:
        apprentice_id = scope.pop("apprentice_id")
    as_of = (today or date.today()).isoformat()
    return repo.list_appeals(
        status=status or None,
        appeal_type=appeal_type or None,
        apprentice_id=apprentice_id,
        raised_by=raised_by or None,
        open_only=open_only,
        overdue_on=as_of if overdue_only else None,
        due_before=due_before or None,
        **scope,
    )


def get_appeal(actor: Actor, appeal_id: int) -> Appeal:
    require_any(actor, "appeal.raise", "appeal.decide")
    return _require_visible(actor, appeal_id)


def appealable_epa_results(actor: Actor, *, today: date | None = None) -> list[EPAResult]:
    """The apprentice's own EPA results still inside the appeal window.

    Read straight from the EPA records, so the apprentice picks the
    result rather than describing it — the EPAO then knows exactly which
    sitting is being challenged.
    """
    require(actor, "appeal.raise")
    apprentice_id = _own_apprentice_id(actor)
    as_of = today or date.today()
    return [
        r for r in epa_repository.list_results(apprentice_id=apprentice_id)
        if _in_window(r.assessed_date, as_of)
    ]


def may_decide(actor: Actor, appeal: Appeal) -> bool:
    """Whether *actor* is the one who hears this appeal — for greying out buttons."""
    return actor.can("appeal.decide") and actor.role == rules.decider_role(appeal.appeal_type)


# ═════════════════════════════════════════════════════════════════════
# Lodging and withdrawing
# ═════════════════════════════════════════════════════════════════════

def lodge(actor: Actor, payload: dict[str, Any], *, today: date | None = None) -> Appeal:
    """Lodge an appeal on the apprentice's own behalf.

    For an EPA result the apprentice names the result (``result_id``) and
    its date comes from the record. For anything else they describe the
    decision (``decision_ref``) and give its date (``decision_date``).
    Either way the window is checked against that date.
    """
    require(actor, "appeal.raise")
    apprentice_id = _own_apprentice_id(actor)
    requested = payload.get("apprentice_id")
    if requested not in (None, "") and _to_int(requested, "Apprentice") != apprentice_id:
        raise PermissionDenied("You can only appeal decisions made about you")

    as_of = today or date.today()
    appeal_type = rules.validate_type(payload.get("appeal_type"))
    grounds = _text(payload.get("grounds"), "Your grounds for appeal",
                    max_length=config.COMPLAINT_MAX_LENGTH)

    decision_ref_id: int | None = None
    if rules.is_epa_result(appeal_type):
        result = _own_result(apprentice_id, payload.get("result_id") or payload.get(
            "decision_ref_id"))
        decision_ref_id = result.result_id
        decision_date = _parse_date(result.assessed_date, "Assessment date")
        decision_ref = (
            f"{result.method}: {result.grade} (attempt {result.attempt}, "
            f"assessed {result.assessed_date})"
        )
        already = repo.list_appeals(
            apprentice_id=apprentice_id, decision_ref_id=result.result_id,
            appeal_type=appeal_type, open_only=True,
        )
        if already:
            raise ValidationError(
                f"You already have an open appeal against this result ({already[0].reference})"
            )
    else:
        decision_ref = _text(payload.get("decision_ref"), "The decision you are appealing",
                             max_length=_DECISION_REF_MAX_LENGTH)
        decision_date = _parse_date(payload.get("decision_date"), "The decision date")

    rules.check_window(decision_date, as_of)

    appeal_id = repo.create({
        "apprentice_id": apprentice_id,
        "raised_by": actor.username,
        "appeal_type": appeal_type,
        "decision_ref_id": decision_ref_id,
        "decision_ref": decision_ref,
        "decision_date": decision_date.isoformat(),
        "grounds": grounds,
        "lodged_at": as_of.isoformat(),
        "deadline": rules.decision_deadline(as_of),
        "status": "Lodged",
    })
    compliance_repository.record(
        action="create", entity="appeal", entity_id=appeal_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{rules.appeal_reference(appeal_id)} ({appeal_type}) against: {decision_ref}",
    )
    logger.info("Appeal %s lodged by %s", appeal_id, actor.username)
    return _reload(appeal_id)


def withdraw(actor: Actor, appeal_id: int, *, reason: str | None = None) -> Appeal:
    """The apprentice withdraws their own appeal while it is still open."""
    require(actor, "appeal.raise")
    appeal = _require_visible(actor, appeal_id)
    if appeal.apprentice_id != actor.apprentice_id:
        raise PermissionDenied("Only the apprentice who lodged an appeal may withdraw it")
    rules.require_transition(appeal.status, "Withdrawn")
    note = (reason or "").strip() or "Withdrawn by the apprentice"
    repo.update(appeal_id, {
        "status": "Withdrawn",
        "decided_at": date.today().isoformat(),
        "decision": note,
    })
    compliance_repository.record(
        action="withdraw", entity="appeal", entity_id=appeal_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{appeal.reference}: {note}",
    )
    return _reload(appeal_id)


# ═════════════════════════════════════════════════════════════════════
# Deciding
# ═════════════════════════════════════════════════════════════════════

def start_review(actor: Actor, appeal_id: int) -> Appeal:
    """Tell the apprentice their appeal is being looked at."""
    appeal = _require_decider(actor, appeal_id)
    rules.require_transition(appeal.status, "Under review")
    repo.update(appeal_id, {"status": "Under review"})
    compliance_repository.record(
        action="update", entity="appeal", entity_id=appeal_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{appeal.reference}: under review",
    )
    return _reload(appeal_id)


def decide(
    actor: Actor, appeal_id: int, *, outcome: str, decision: str, today: date | None = None
) -> Appeal:
    """Record the ruling: upheld, partially upheld or rejected, with reasons.

    The reasons are required. An apprentice told only "rejected" has no
    way to tell whether their grounds were even read.
    """
    appeal = _require_decider(actor, appeal_id)
    result = rules.validate_decision_status(outcome)
    rules.require_transition(appeal.status, result)
    reasons = _text(decision, "The reasons for the decision",
                    max_length=config.COMPLAINT_MAX_LENGTH)
    repo.update(appeal_id, {
        "status": result,
        "decided_by": actor.username,
        "decided_at": (today or date.today()).isoformat(),
        "decision": reasons,
    })
    compliance_repository.record(
        action="reject" if result == "Rejected" else "approve",
        entity="appeal", entity_id=appeal_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{appeal.reference} ({appeal.appeal_type}): {result}",
    )
    logger.info("Appeal %s decided %s by %s", appeal_id, result, actor.username)
    return _reload(appeal_id)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _scope(actor: Actor) -> dict[str, Any]:
    """Repository filters for the appeals *actor* may see."""
    if actor.role == config.APPRENTICE:
        return {"apprentice_id": actor.apprentice_id or _IMPOSSIBLE_ID}
    if actor.role == config.END_POINT_ASSESSOR:
        return {"types": [config.EPA_RESULT_APPEAL]}
    if actor.role == config.ADMIN:
        return {"exclude_types": [config.EPA_RESULT_APPEAL]}
    return {"apprentice_id": _IMPOSSIBLE_ID}


def _may_see(actor: Actor, appeal: Appeal) -> bool:
    if actor.role == config.APPRENTICE:
        return actor.apprentice_id is not None and appeal.apprentice_id == actor.apprentice_id
    if actor.role in (config.END_POINT_ASSESSOR, config.ADMIN):
        return actor.role == rules.decider_role(appeal.appeal_type)
    return False


def _require_visible(actor: Actor, appeal_id: int) -> Appeal:
    """The appeal, if *actor* may see it.

    The refusal does not confirm the appeal exists — to the provider an
    EPA-result appeal should be indistinguishable from no appeal at all.
    """
    appeal = repo.get(appeal_id)
    if appeal is not None and _may_see(actor, appeal):
        return appeal
    raise PermissionDenied("You do not have access to this appeal")


def _require_decider(actor: Actor, appeal_id: int) -> Appeal:
    """The appeal, if *actor* is the one who decides its type."""
    require(actor, "appeal.decide")
    appeal = repo.get(appeal_id)
    if appeal is None:
        raise PermissionDenied("You do not have access to this appeal")
    if actor.role != rules.decider_role(appeal.appeal_type):
        if appeal.is_epa_result:
            raise PermissionDenied(
                "Appeals against an EPA result are decided by the End-Point Assessment "
                "Organisation, not the training provider"
            )
        raise PermissionDenied(
            "The end-point assessor decides only appeals against EPA results; the "
            "training provider decides this one"
        )
    return appeal


def _own_apprentice_id(actor: Actor) -> int:
    if actor.apprentice_id is None:
        raise ValidationError(
            "Your sign-in is not linked to an apprentice record, so there is nothing to appeal"
        )
    if apprentice_repository.get(actor.apprentice_id) is None:
        raise ValidationError(f"No apprentice with id {actor.apprentice_id}")
    return actor.apprentice_id


def _own_result(apprentice_id: int, value: Any) -> EPAResult:
    if value in (None, ""):
        raise ValidationError("Choose the EPA result you are appealing")
    result = epa_repository.get_result(_to_int(value, "EPA result"))
    if result is None or result.apprentice_id != apprentice_id:
        # Not "no such result": another apprentice's result is none of
        # this apprentice's business, including whether it exists.
        raise PermissionDenied("That EPA result is not one of yours")
    return result


def _in_window(decision_iso: str | None, today: date) -> bool:
    try:
        decided = date.fromisoformat(str(decision_iso)[:10])
    except ValueError:
        return False
    return decided <= today <= rules.window_closes(decided)


def _reload(appeal_id: int) -> Appeal:
    appeal = repo.get(appeal_id)
    assert appeal is not None
    return appeal


def _text(value: Any, label: str, *, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{label} is required")
    if len(text) > max_length:
        raise ValidationError(f"{label} must be {max_length} characters or fewer")
    return text


def _parse_date(value: Any, label: str) -> date:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{label} is required")
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValidationError(f"{label} must be a date in YYYY-MM-DD format") from exc


def _to_int(value: Any, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must be a number") from exc
