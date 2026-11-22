"""Funding: the agreed price, who pays it, and when it is drawn down.

Two audiences with very different rights meet here. The provider agrees
prices, claims instalments and reconciles payments; an employer sees the
money attached to their own apprentices and nothing else. So
``funding.manage`` is admin-only, ``funding.view`` reaches the employer,
and every employer read is narrowed to their own organisation before it
touches the database.

The arithmetic — bands, splits, schedules, levy — all lives in
``domain.funding.funding_rules``. This module decides who may ask, what
the live facts are, and what the answer means for the payment schedule.
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
from education_system.systems.apprenticeships.domain.funding import funding_rules
from education_system.systems.apprenticeships.domain.funding.funding_rules import (
    FundingRecord,
    FundingSummary,
    LevyPosition,
    Payment,
    build_schedule,
    determine_model,
    require_payment_status,
    split_contributions,
    validate_price,
)
from education_system.systems.apprenticeships.domain.programmes.models import (
    validate_funding_band,
)
from education_system.systems.apprenticeships.domain.records import audit
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    employer_repository,
    funding_repository,
    programme_repository,
)
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    PermissionDenied,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def get_funding(actor: Actor, apprentice_id: int) -> FundingSummary:
    """One apprenticeship's price, split and instalment plan."""
    require(actor, "funding.view")
    _load(actor, apprentice_id)
    return funding_repository.build_summary(apprentice_id)


def list_funding(
    actor: Actor,
    *,
    funding_model: str | None = None,
    employer_id: int | None = None,
    programme_id: int | None = None,
) -> list[dict[str, Any]]:
    """Funding records in scope, with the labels the funding screen shows."""
    require(actor, "funding.view")
    scope = _employer_scope(actor)
    return funding_repository.list_records(
        funding_model=funding_model,
        employer_id=scope if scope is not None else employer_id,
        programme_id=programme_id,
    )


def list_payments(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    overdue_only: bool = False,
) -> list[Payment]:
    require(actor, "funding.view")
    return funding_repository.list_payments(
        apprentice_id=apprentice_id,
        status=status,
        employer_id=_employer_scope(actor),
        overdue_only=overdue_only,
    )


def levy_position(actor: Actor, employer_id: int) -> LevyPosition:
    """What the apprenticeship levy costs this employer for the year."""
    require(actor, "funding.view")
    if actor.role == config.EMPLOYER and actor.employer_id != employer_id:
        raise PermissionDenied("You may only see your own organisation's levy position")

    employer = employer_repository.get(employer_id)
    if employer is None:
        raise ValidationError(f"No employer with id {employer_id}")
    return funding_rules.levy_position(employer.paybill)


def funding_dashboard(actor: Actor) -> dict[str, Any]:
    """Headline money figures, narrowed to an employer's own apprentices."""
    require(actor, "funding.view")
    scope = _employer_scope(actor)
    overdue = funding_repository.list_payments(employer_id=scope, overdue_only=True)
    return {
        "totals": funding_repository.totals(employer_id=scope),
        "contracted_value": funding_repository.contracted_value(employer_id=scope),
        "overdue_payments": overdue,
        "overdue_count": len(overdue),
        "overdue_value": round(sum(p.amount for p in overdue), 2),
    }


# ═════════════════════════════════════════════════════════════════════
# The funding record
# ═════════════════════════════════════════════════════════════════════

def set_funding(actor: Actor, apprentice_id: int, payload: dict[str, Any]) -> FundingRecord:
    """Agree — or re-negotiate — the price of one apprenticeship.

    The band comes from the standard and the funding route from the
    employer's levy and headcount position, so the only figure anyone
    normally types is the negotiated price. Both can be overridden, but
    the price is still checked against the band cap: above it, the excess
    is simply unfundable.
    """
    require(actor, "funding.manage")
    apprentice = _load(actor, apprentice_id)
    existing = funding_repository.get_record(apprentice_id)
    programme = (
        programme_repository.get(apprentice.programme_id) if apprentice.programme_id else None
    )

    raw_band = payload.get("band") or (programme.funding_band if programme else None)
    if not raw_band and existing:
        raw_band = existing.band
    if not raw_band:
        raise ValidationError(
            "No funding band: set one on the programme, or supply it with the price"
        )
    band = validate_funding_band(raw_band)

    raw_price = payload.get("negotiated_price")
    if raw_price is None and existing:
        raw_price = existing.negotiated_price
    if raw_price is None:
        raise ValidationError("A negotiated price is required")
    price = validate_price(raw_price, band)

    model = _validate_model(payload.get("funding_model"))
    if model is None:
        employer = (
            employer_repository.get(apprentice.employer_id) if apprentice.employer_id else None
        )
        model = determine_model(
            is_levy_payer=bool(employer and employer.is_levy_payer),
            is_small_employer=bool(employer and employer.is_small_employer),
            age_at_start=apprentice.age_at_start,
        )
    employer_share, government_share = split_contributions(price, model)

    additional = _validate_money(
        payload.get("additional_payments", existing.additional_payments if existing else 0.0),
        "Additional payments",
    )
    funding_repository.upsert_record(apprentice_id, {
        "funding_model": model,
        "band": band,
        "negotiated_price": price,
        "employer_contribution": employer_share,
        "government_contribution": government_share,
        "additional_payments": additional,
        "notes": _optional_text(payload.get("notes")),
    })
    instalments = _rebuild_schedule(apprentice, price)
    record = funding_repository.get_record(apprentice_id)
    assert record is not None

    compliance_repository.record(
        action="update" if existing else "create", entity="funding", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=(
            f"{model}, band {band}, {config.CURRENCY_SYMBOL}{price:,.2f} "
            f"over {instalments} instalment(s)"
        ),
        changes=audit.diff(existing, record, fields=(
            "funding_model", "band", "negotiated_price", "employer_contribution",
            "government_contribution", "additional_payments",
        )),
    )
    logger.info(
        "Funding set for apprentice %s: %s band %s at %.2f by %s",
        apprentice_id, model, band, price, actor.username,
    )
    return record


def regenerate_schedule(actor: Actor, apprentice_id: int) -> int:
    """Rebuild the instalment plan after a change of dates.

    Returns how many instalments the apprenticeship now carries.
    """
    require(actor, "funding.manage")
    apprentice = _load(actor, apprentice_id)
    record = funding_repository.get_record(apprentice_id)
    if record is None:
        raise ValidationError("Set the funding for this apprentice before scheduling payments")

    count = _rebuild_schedule(apprentice, record.negotiated_price)
    compliance_repository.record(
        action="update", entity="funding", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Payment schedule rebuilt: {count} instalment(s)",
    )
    logger.info(
        "Payment schedule rebuilt for apprentice %s by %s (%s rows)",
        apprentice_id, actor.username, count,
    )
    return count


# ═════════════════════════════════════════════════════════════════════
# Payments
# ═════════════════════════════════════════════════════════════════════

def claim_payment(actor: Actor, payment_id: int) -> Payment:
    """Submit an instalment for payment."""
    return _set_payment_status(actor, payment_id, "Claimed")


def mark_paid(actor: Actor, payment_id: int) -> Payment:
    """Reconcile an instalment that has actually landed."""
    return _set_payment_status(actor, payment_id, "Paid")


def withhold_payment(actor: Actor, payment_id: int, *, reason: str) -> Payment:
    """Hold an instalment back — a break in learning, or a query on it."""
    if not (reason or "").strip():
        raise ValidationError("A reason is required to withhold a payment")
    return _set_payment_status(actor, payment_id, "Withheld", reason=reason.strip())


def claw_back(actor: Actor, payment_id: int, *, reason: str) -> Payment:
    """Recover money already paid.

    Only reachable from 'Paid', and terminal: money that has moved cannot
    be un-moved, only recovered and recorded as such.
    """
    if not (reason or "").strip():
        raise ValidationError("A reason is required to claw back a payment")
    return _set_payment_status(actor, payment_id, "Clawed Back", reason=reason.strip())


def bulk_claim(actor: Actor, payment_ids: list[int]) -> int:
    """Claim a batch of instalments, returning how many moved.

    Rows that are not still 'Scheduled' are skipped rather than raising:
    a monthly claim run covers hundreds of instalments, and one already
    claimed by somebody else must not strand the rest of the batch.
    """
    require(actor, "funding.manage")
    claimed = 0
    for payment_id in payment_ids:
        payment = funding_repository.get_payment(payment_id)
        if payment is None or payment.status != "Scheduled":
            continue
        _set_payment_status(actor, payment_id, "Claimed")
        claimed += 1

    compliance_repository.record(
        action="update", entity="payment", entity_id=None,
        actor=actor.username, actor_role=actor.role,
        detail=f"Bulk claim: {claimed} of {len(payment_ids)} instalment(s)",
    )
    logger.info("Bulk claim by %s: %s of %s", actor.username, claimed, len(payment_ids))
    return claimed


def release_completion_payment(actor: Actor, apprentice_id: int) -> int:
    """Release the balance held back until the EPA completes.

    Called by the EPA service the moment an apprenticeship completes —
    that withheld fifth is precisely what the provider is paid for
    finishing rather than merely enrolling. Returns how many rows moved,
    which is normally one and zero if it has already been released.
    """
    require(actor, "funding.manage")
    released = 0
    for payment in funding_repository.list_payments(apprentice_id=apprentice_id):
        if payment.payment_type != "Completion" or payment.status not in ("Withheld", "Scheduled"):
            continue
        _set_payment_status(actor, payment.payment_id, "Claimed")
        released += 1

    if released:
        compliance_repository.record(
            action="update", entity="funding", entity_id=apprentice_id,
            actor=actor.username, actor_role=actor.role,
            detail=f"Completion payment released ({released} row(s))",
        )
        logger.info(
            "Completion payment released for apprentice %s by %s", apprentice_id, actor.username
        )
    return released


# ═════════════════════════════════════════════════════════════════════
# Internals
# ═════════════════════════════════════════════════════════════════════

# No autoincrement primary key is ever negative, so this matches nothing.
_IMPOSSIBLE_ID = -1


def _set_payment_status(
    actor: Actor, payment_id: int, target: str, *, reason: str | None = None
) -> Payment:
    """Move one instalment, stamping the dates the move implies."""
    require(actor, "funding.manage")
    payment = funding_repository.get_payment(payment_id)
    if payment is None:
        raise ValidationError(f"No payment with id {payment_id}")
    require_payment_status(payment.status, target)

    today = date.today().isoformat()
    data: dict[str, Any] = {"status": target}
    if target == "Claimed":
        data["claimed_at"] = today
    if target == "Paid":
        data["paid_at"] = today
        # Money reconciled without ever having been claimed leaves a hole
        # in the audit trail, so the claim stamp is backfilled.
        if payment.claimed_at is None:
            data["claimed_at"] = today
    if reason:
        data["notes"] = reason

    funding_repository.update_payment(payment_id, data)
    compliance_repository.record(
        action="update", entity="payment", entity_id=payment_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{payment.status} -> {target}" + (f" ({reason})" if reason else ""),
    )
    logger.info(
        "Payment %s moved %s -> %s by %s", payment_id, payment.status, target, actor.username
    )

    updated = funding_repository.get_payment(payment_id)
    assert updated is not None
    return updated


def _rebuild_schedule(apprentice: Apprentice, price: float) -> int:
    """Install the instalment plan for an apprenticeship.

    ``replace_schedule`` only discards rows that are still 'Scheduled',
    so instalments already claimed or paid survive a re-price — they are
    real financial events, not a projection to be recalculated.
    """
    if not (apprentice.start_date and apprentice.planned_end_date):
        # An applicant with no dates yet has nothing to schedule against;
        # the plan is built when they start.
        return 0
    schedule = build_schedule(
        price=price,
        start_date=apprentice.start_date,
        planned_end_date=apprentice.planned_end_date,
    )
    return funding_repository.replace_schedule(apprentice.apprentice_id, schedule)


def _load(actor: Actor, apprentice_id: int) -> Apprentice:
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)
    return apprentice


def _employer_scope(actor: Actor) -> int | None:
    """The employer id an actor's reads are confined to, if any.

    An employer whose login has not resolved to an organisation gets an
    id that matches nothing, rather than the whole provider's ledger.
    """
    if actor.role != config.EMPLOYER:
        return None
    return actor.employer_id if actor.employer_id is not None else _IMPOSSIBLE_ID


def _validate_model(value: Any) -> str | None:
    model = str(value or "").strip()
    if not model:
        return None
    if model not in config.FUNDING_MODELS:
        allowed = ", ".join(config.FUNDING_MODELS)
        raise ValidationError(f"Funding model must be one of: {allowed}")
    return model


def _validate_money(value: Any, label: str) -> float:
    try:
        amount = float(str(value or 0).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must be a number") from exc
    if amount < 0:
        raise ValidationError(f"{label} cannot be negative")
    return round(amount, 2)


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
