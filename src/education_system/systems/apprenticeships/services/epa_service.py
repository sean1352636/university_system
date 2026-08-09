"""End-Point Assessment: organisations, bookings, results and resits.

The EPA is independent by design. The organisation that delivered the
training does not grade the apprentice — an approved EPAO does — and
that single rule shapes this module: ``epa.grade`` is held by the
end-point assessor role and by nobody else, including the provider
admin who can otherwise do everything.

Everything downstream of a result is a consequence rather than a
separate decision: passing the last required method completes the
apprenticeship, which is what releases the withheld completion payment.
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
from education_system.systems.apprenticeships.domain.end_point_assessment.results import (
    EPAO,
    EPABooking,
    EPAProgress,
    EPAResit,
    EPAResult,
    require_booking_status,
    validate_grade,
    validate_method,
    validate_resit_type,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    epa_repository,
    programme_repository,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# End-Point Assessment Organisations
# ═════════════════════════════════════════════════════════════════════

def list_epaos(actor: Actor, *, active_only: bool = False) -> list[EPAO]:
    """The EPAO directory. Everyone who can see EPA can see who assesses."""
    require(actor, "epa.view")
    return epa_repository.list_epaos(active_only=active_only)


def get_epao(actor: Actor, epao_id: int) -> EPAO:
    require(actor, "epa.view")
    epao = epa_repository.get_epao(epao_id)
    if epao is None:
        raise ValidationError(f"No EPAO with id {epao_id}")
    return epao


def create_epao(actor: Actor, payload: dict[str, Any]) -> EPAO:
    _require_admin(actor)
    data = _validate_epao(payload, existing=None)
    epao_id = epa_repository.create_epao(data)
    compliance_repository.record(
        action="create", entity="epao", entity_id=epao_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Added EPAO {data.get('name')}",
    )
    logger.info("EPAO %s created by %s", epao_id, actor.username)
    return get_epao(actor, epao_id)


def update_epao(actor: Actor, epao_id: int, payload: dict[str, Any]) -> EPAO:
    _require_admin(actor)
    existing = epa_repository.get_epao(epao_id)
    if existing is None:
        raise ValidationError(f"No EPAO with id {epao_id}")

    data = _validate_epao(payload, existing=existing)
    epa_repository.update_epao(epao_id, data)
    compliance_repository.record(
        action="update", entity="epao", entity_id=epao_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
    )
    return get_epao(actor, epao_id)


def deactivate_epao(actor: Actor, epao_id: int) -> EPAO:
    """Retire an EPAO without deleting it.

    Bookings already placed with them stay attached and readable — an
    assessment history that loses the name of the organisation that
    graded it is worthless to an auditor.
    """
    _require_admin(actor)
    existing = epa_repository.get_epao(epao_id)
    if existing is None:
        raise ValidationError(f"No EPAO with id {epao_id}")

    epa_repository.update_epao(epao_id, {"active": 0})
    compliance_repository.record(
        action="update", entity="epao", entity_id=epao_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deactivated EPAO {existing.name}",
    )
    logger.info("EPAO %s deactivated by %s", epao_id, actor.username)
    return get_epao(actor, epao_id)


# ═════════════════════════════════════════════════════════════════════
# Bookings
# ═════════════════════════════════════════════════════════════════════

def list_bookings(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    method: str | None = None,
    open_only: bool = False,
    mine_only: bool = False,
) -> list[dict[str, Any]]:
    """Bookings *actor* may see, with any extra filters applied."""
    require(actor, "epa.view")
    filters: dict[str, Any] = {
        "apprentice_id": apprentice_id,
        "status": status,
        "method": method,
        "open_only": open_only,
    }
    if mine_only and actor.role == config.END_POINT_ASSESSOR:
        filters["assessor_username"] = actor.username

    rows = epa_repository.list_bookings(**filters)
    if actor.role in (config.STAFF, config.EMPLOYER, config.APPRENTICE):
        visible = _visible_apprentice_ids(actor)
        rows = [r for r in rows if r["apprentice_id"] in visible]
    return rows


def get_booking(actor: Actor, booking_id: int) -> dict[str, Any]:
    require(actor, "epa.view")
    row = epa_repository.get_booking_row(booking_id)
    if row is None:
        raise ValidationError(f"No booking with id {booking_id}")
    _load_apprentice(actor, row["apprentice_id"])
    return row


def book_assessment(actor: Actor, apprentice_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Book one assessment method for an apprentice.

    Only ever after gateway approval, and only against a method the
    standard's EPA plan actually lists — booking a knowledge test for a
    standard assessed by observation would produce a grade nobody can use.
    """
    require(actor, "epa.book")
    apprentice = _load_apprentice(actor, apprentice_id)

    from education_system.systems.apprenticeships.services import gateway_service

    record = gateway_service.evaluate_gateway(actor, apprentice_id)
    if not record.is_approved:
        raise ValidationError(
            f"Gateway is {record.status!r} for this apprentice. An assessment cannot be "
            "booked until the EPAO has approved gateway — request and approve it first."
        )

    data = _validate_booking(payload, existing=None)
    programme = (
        programme_repository.get(apprentice.programme_id) if apprentice.programme_id else None
    )
    if programme and programme.epa_methods and data["method"] not in programme.epa_methods:
        plan = ", ".join(programme.epa_methods)
        raise ValidationError(
            f"{data['method']!r} is not in the EPA plan for {programme.title}. Plan: {plan}"
        )

    first_booking = not epa_repository.list_bookings(apprentice_id=apprentice_id)
    booking_id = epa_repository.create_booking({
        **data, "apprentice_id": apprentice_id, "status": "Requested",
    })
    compliance_repository.record(
        action="create", entity="epa_booking", entity_id=booking_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['method']} booked for apprentice {apprentice_id}",
    )
    logger.info(
        "EPA booking %s (%s) created for apprentice %s by %s",
        booking_id, data["method"], apprentice_id, actor.username,
    )

    if first_booking and apprentice.status == "Gateway":
        _move_status(actor, apprentice_id, "EPA", reason=f"{data['method']} booked")
    return get_booking(actor, booking_id)


def schedule_assessment(
    actor: Actor,
    booking_id: int,
    *,
    scheduled_date: str,
    scheduled_time: str | None = None,
    location: str | None = None,
    assessor_name: str | None = None,
    assessor_username: str | None = None,
) -> dict[str, Any]:
    """Fix the date, place and assessor for a requested booking."""
    require(actor, "epa.book")
    booking = _load_booking(actor, booking_id)
    require_booking_status(booking.status, "Scheduled")

    when = _validate_date(scheduled_date, "Scheduled date")
    if when is None:
        raise ValidationError("A scheduled date is required")

    epa_repository.update_booking(booking_id, {
        "status": "Scheduled",
        "scheduled_date": when,
        "scheduled_time": _optional_text(scheduled_time),
        "location": _optional_text(location),
        "assessor_name": _optional_text(assessor_name),
        "assessor_username": _optional_text(assessor_username),
    })
    compliance_repository.record(
        action="update", entity="epa_booking", entity_id=booking_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Scheduled for {when}",
    )
    logger.info("EPA booking %s scheduled for %s by %s", booking_id, when, actor.username)
    return get_booking(actor, booking_id)


def update_booking(actor: Actor, booking_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Edit a booking's details.

    Status is not editable here: it moves through
    :func:`schedule_assessment`, :func:`cancel_booking` and
    :func:`record_result`, each of which checks the transition.
    """
    require(actor, "epa.book")
    booking = _load_booking(actor, booking_id)
    if booking.status == "Assessed":
        raise ValidationError("A graded booking cannot be edited — record a resit instead")

    data = _validate_booking(payload, existing=booking)
    epa_repository.update_booking(booking_id, data)
    compliance_repository.record(
        action="update", entity="epa_booking", entity_id=booking_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
    )
    return get_booking(actor, booking_id)


def cancel_booking(actor: Actor, booking_id: int, *, reason: str) -> dict[str, Any]:
    require(actor, "epa.book")
    if not (reason or "").strip():
        raise ValidationError("A reason is required to cancel a booking")

    booking = _load_booking(actor, booking_id)
    require_booking_status(booking.status, "Cancelled")

    note = "\n".join(filter(None, [booking.notes, f"Cancelled: {reason.strip()}"]))
    epa_repository.update_booking(booking_id, {"status": "Cancelled", "notes": note})
    compliance_repository.record(
        action="update", entity="epa_booking", entity_id=booking_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Cancelled: {reason.strip()}",
    )
    logger.info(
        "EPA booking %s cancelled by %s: %s", booking_id, actor.username, reason.strip()
    )
    return get_booking(actor, booking_id)


# ═════════════════════════════════════════════════════════════════════
# Results
# ═════════════════════════════════════════════════════════════════════

def record_result(
    actor: Actor,
    booking_id: int,
    *,
    grade: str,
    assessed_date: str | None = None,
    feedback: str | None = None,
) -> EPAResult:
    """Grade a sitting.

    ``epa.grade`` belongs to the end-point assessor alone — the provider
    admin deliberately does not hold it. A training provider grading the
    apprentices it trained, and is paid for completing, is exactly what
    independent end-point assessment exists to prevent.
    """
    require(actor, "epa.grade")
    booking = epa_repository.get_booking(booking_id)
    if booking is None:
        raise ValidationError(f"No booking with id {booking_id}")
    require_booking_status(booking.status, "Assessed")

    cleaned = validate_grade(grade)
    when = _validate_date(assessed_date, "Assessed date") or date.today().isoformat()
    attempt = epa_repository.attempt_count(booking.apprentice_id, booking.method) + 1

    result_id = epa_repository.record_result(
        booking_id=booking_id,
        apprentice_id=booking.apprentice_id,
        method=booking.method,
        grade=cleaned,
        assessed_date=when,
        assessor_name=booking.assessor_name or actor.name,
        feedback=_optional_text(feedback),
        attempt=attempt,
    )
    compliance_repository.record(
        action="grade", entity="epa_result", entity_id=result_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{booking.method}: {cleaned} (attempt {attempt})",
    )
    logger.info(
        "EPA result %s recorded for apprentice %s: %s %s (attempt %s) by %s",
        result_id, booking.apprentice_id, booking.method, cleaned, attempt, actor.username,
    )

    _maybe_complete(actor, booking.apprentice_id)

    result = epa_repository.get_result(result_id)
    assert result is not None
    return result


def epa_progress(actor: Actor, apprentice_id: int) -> EPAProgress:
    """An apprentice's position across every required assessment method."""
    require(actor, "epa.view")
    _load_apprentice(actor, apprentice_id)
    return _progress(apprentice_id)


def _maybe_complete(actor: Actor, apprentice_id: int) -> None:
    """Complete the apprenticeship if the last required method has passed.

    The withheld completion payment is released here rather than by a
    separate admin action, because completion is the event the provider
    is paid for.
    """
    progress = _progress(apprentice_id)
    if not progress.is_complete:
        return
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None or apprentice.status == "Completed":
        return

    try:
        _move_status(actor, apprentice_id, "Completed", reason=f"EPA passed — {progress.overall}")
    except ValidationError:
        # The grade is recorded and final. A lifecycle that will not accept
        # the move — an apprentice graded without ever being taken to 'EPA'
        # — is a record to correct, not a reason to fail the result.
        logger.warning(
            "Apprentice %s passed EPA from status %s and could not be completed",
            apprentice_id, apprentice.status, exc_info=True,
        )
        return
    logger.info(
        "Apprentice %s completed with overall grade %s", apprentice_id, progress.overall
    )

    from education_system.systems.apprenticeships.services import funding_service

    try:
        funding_service.release_completion_payment(_provider_actor(actor), apprentice_id)
    except Exception:
        # A funding problem must not undo a completion the assessor has
        # already awarded. The payment stays withheld and the funding
        # screen still shows it as releasable.
        logger.warning(
            "Could not release the completion payment for apprentice %s",
            apprentice_id, exc_info=True,
        )


# ═════════════════════════════════════════════════════════════════════
# Resits
# ═════════════════════════════════════════════════════════════════════

def request_resit(
    actor: Actor,
    apprentice_id: int,
    result_id: int,
    *,
    resit_type: str,
    reason: str | None = None,
    training_plan: str | None = None,
) -> EPAResit:
    """Ask to sit a failed method again.

    A resit goes straight back to assessment; a retake requires further
    training first, which is why it cannot be requested without a plan
    for that training.
    """
    require(actor, "epa.resit")
    _load_apprentice(actor, apprentice_id)

    result = epa_repository.get_result(result_id)
    if result is None or result.apprentice_id != apprentice_id:
        raise ValidationError(f"No result with id {result_id} for this apprentice")
    if result.is_pass:
        raise ValidationError(
            f"{result.method} was already achieved at {result.grade} — nothing to resit"
        )

    kind = validate_resit_type(resit_type)
    progress = _progress(apprentice_id)
    if progress.resits_remaining(result.method) <= 0:
        used = progress.attempts_by_method.get(result.method, 0)
        raise ValidationError(
            f"No further attempts at {result.method}: {used} of "
            f"{config.MAX_RESITS + 1} permitted sittings used"
        )
    if kind == "Retake" and not (training_plan or "").strip():
        raise ValidationError("A retake needs a training plan — describe the training first")

    resit_id = epa_repository.create_resit({
        "apprentice_id": apprentice_id,
        "result_id": result_id,
        "resit_type": kind,
        "reason": _optional_text(reason),
        "training_plan": _optional_text(training_plan),
        "requested_by": actor.username,
        "status": "Requested",
    })
    compliance_repository.record(
        action="create", entity="epa_resit", entity_id=resit_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{kind} requested for {result.method}",
    )
    logger.info(
        "%s requested for apprentice %s on %s by %s",
        kind, apprentice_id, result.method, actor.username,
    )

    resit = epa_repository.get_resit(resit_id)
    assert resit is not None
    return resit


def list_resits(
    actor: Actor, *, apprentice_id: int | None = None, status: str | None = None
) -> list[EPAResit]:
    require(actor, "epa.view")
    resits = epa_repository.list_resits(apprentice_id=apprentice_id, status=status)
    if actor.role in (config.STAFF, config.EMPLOYER, config.APPRENTICE):
        visible = _visible_apprentice_ids(actor)
        resits = [r for r in resits if r.apprentice_id in visible]
    return resits


def book_resit(actor: Actor, resit_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Turn an approved resit request into a booking.

    The new booking carries ``resit_of``, so the result chain can be
    followed back to the sitting it replaces.
    """
    require(actor, "epa.book")
    resit = epa_repository.get_resit(resit_id)
    if resit is None:
        raise ValidationError(f"No resit with id {resit_id}")
    if resit.booking_id:
        raise ValidationError(f"That resit is already booked (booking {resit.booking_id})")

    result = epa_repository.get_result(resit.result_id)
    if result is None:
        raise ValidationError("The result this resit refers to no longer exists")

    row = book_assessment(actor, resit.apprentice_id, {
        **payload,
        "method": payload.get("method") or result.method,
        "resit_of": result.result_id,
    })
    epa_repository.update_resit(resit_id, {"status": "Booked", "booking_id": row["booking_id"]})
    compliance_repository.record(
        action="update", entity="epa_resit", entity_id=resit_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Booked as booking {row['booking_id']}",
    )
    return row


# ═════════════════════════════════════════════════════════════════════
# Assessor diary
# ═════════════════════════════════════════════════════════════════════

def assessor_schedule(
    actor: Actor, *, date_from: str | None = None, date_to: str | None = None
) -> list[dict[str, Any]]:
    """The signed-in assessor's own upcoming sittings."""
    require(actor, "epa.view")
    return epa_repository.list_bookings(
        assessor_username=actor.username,
        date_from=_validate_date(date_from, "From date"),
        date_to=_validate_date(date_to, "To date"),
        open_only=True,
    )


# ═════════════════════════════════════════════════════════════════════
# Internals
# ═════════════════════════════════════════════════════════════════════

def _progress(apprentice_id: int) -> EPAProgress:
    """Build the whole EPA position from the standard's required methods."""
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    programme = (
        programme_repository.get(apprentice.programme_id) if apprentice.programme_id else None
    )
    return EPAProgress(
        apprentice_id=apprentice_id,
        required_methods=list(programme.epa_methods) if programme else [],
        bookings=epa_repository.list_bookings_typed(apprentice_id=apprentice_id),
        results=epa_repository.list_results(apprentice_id=apprentice_id),
        resits=epa_repository.list_resits(apprentice_id=apprentice_id),
    )


def _load_apprentice(actor: Actor, apprentice_id: int) -> Apprentice:
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)
    return apprentice


def _load_booking(actor: Actor, booking_id: int) -> EPABooking:
    booking = epa_repository.get_booking(booking_id)
    if booking is None:
        raise ValidationError(f"No booking with id {booking_id}")
    _load_apprentice(actor, booking.apprentice_id)
    return booking


def _visible_apprentice_ids(actor: Actor) -> set[int]:
    from education_system.systems.apprenticeships.services import apprentice_service

    return {s.apprentice.apprentice_id for s in apprentice_service.list_apprentices(actor)}


def _provider_actor(actor: Actor) -> Actor:
    """Provider rights for the knock-on writes an EPA decision triggers.

    An end-point assessor holds neither ``apprentice.manage`` nor
    ``funding.manage``, and should not: they assess, they do not
    administer the provider. But moving the apprentice to 'EPA' or
    'Completed', and releasing the payment that completion earns, are
    consequences of a decision they were entitled to make. Those run with
    provider rights, still audited under the assessor's own username.
    """
    return Actor(username=actor.username, role=config.ADMIN, display_name=actor.display_name)


def _move_status(actor: Actor, apprentice_id: int, new_status: str, *, reason: str) -> None:
    from education_system.systems.apprenticeships.services import apprentice_service

    apprentice_service.change_status(
        _provider_actor(actor), apprentice_id, new_status, reason=reason
    )


def _require_admin(actor: Actor) -> None:
    """EPAO reference data is provider-admin territory.

    There is no separate ``epao.manage`` permission: the directory is
    configuration, not day-to-day work, so it rides on the admin role.
    """
    if not actor.is_admin:
        raise PermissionDenied("Only a provider administrator may manage EPAOs")


# ═════════════════════════════════════════════════════════════════════
# Validation
# ═════════════════════════════════════════════════════════════════════

def _validate_epao(payload: dict[str, Any], *, existing: EPAO | None) -> dict[str, Any]:
    """Normalise and check an EPAO payload.

    Only keys actually present are returned, so a partial edit does not
    blank the fields the form did not show.
    """
    data: dict[str, Any] = {}
    if existing is None or "name" in payload:
        data["name"] = _require_text(payload.get("name"), "EPAO name")
    for key in ("contact_name", "phone"):
        if key in payload:
            data[key] = _optional_text(payload.get(key))
    if "contact_email" in payload:
        data["contact_email"] = _validate_email(payload.get("contact_email"))
    if "standards" in payload:
        data["standards"] = _normalise_standards(payload.get("standards"))
    if "active" in payload:
        data["active"] = 1 if payload.get("active") else 0
    return data


def _validate_booking(payload: dict[str, Any], *, existing: EPABooking | None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if existing is None or "method" in payload:
        data["method"] = validate_method(payload.get("method"))
    if "epao_id" in payload:
        data["epao_id"] = _validate_epao_id(payload.get("epao_id"))
    if "scheduled_date" in payload:
        data["scheduled_date"] = _validate_date(payload.get("scheduled_date"), "Scheduled date")
    for key in ("scheduled_time", "location", "assessor_name", "assessor_username", "notes"):
        if key in payload:
            data[key] = _optional_text(payload.get(key))
    if payload.get("resit_of"):
        data["resit_of"] = int(payload["resit_of"])
    return data


def _validate_epao_id(value: Any) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        epao_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("EPAO is not valid") from exc
    if epa_repository.get_epao(epao_id) is None:
        raise ValidationError(f"No EPAO with id {epao_id}")
    return epao_id


def _normalise_standards(value: Any) -> str | None:
    """Store the approved standards as an upper-cased comma list."""
    if not value:
        return None
    parts = value.split(",") if isinstance(value, str) else [str(v) for v in value]
    cleaned = [p.strip().upper() for p in parts if p.strip()]
    return ", ".join(cleaned) or None


def _require_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{label} is required")
    if len(text) > 120:
        raise ValidationError(f"{label} must be 120 characters or fewer")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _validate_email(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "@" not in text or text.startswith("@") or text.endswith("@") or " " in text:
        raise ValidationError(f"{text!r} is not a valid email address")
    return text


def _validate_date(value: Any, label: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{label} must be a date in YYYY-MM-DD format") from exc
