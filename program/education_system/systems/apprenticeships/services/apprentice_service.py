"""Apprentice records: enrolment, progression through the lifecycle, exit.

Services are where the three concerns meet: permission (may this actor
do it), validation (is the input sound), and orchestration (which
repositories, in what order, in what transaction). The interfaces call
only this layer, so a GUI window and a CLI command enforce identical
rules by construction.

Every function takes ``actor`` first. That is not decoration — reads are
scoped to what the actor may see, and writes are refused outright.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices import status as lifecycle
from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ApprenticeSummary,
    ValidationError,
    planned_end_for,
    validate_uln,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    compliance_repository,
    employer_repository,
    programme_repository,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def list_apprentices(
    actor: Actor,
    *,
    status: str | None = None,
    programme_id: int | None = None,
    employer_id: int | None = None,
    tutor_id: int | None = None,
    search: str | None = None,
    active_only: bool = False,
) -> list[ApprenticeSummary]:
    """The cohort *actor* is allowed to see, with any extra filters applied.

    An employer passing ``employer_id`` for somebody else's organisation
    does not widen anything: their own scope is applied last and wins.
    """
    require_any_view(actor)
    filters: dict[str, Any] = {
        "status": status,
        "programme_id": programme_id,
        "employer_id": employer_id,
        "tutor_id": tutor_id,
        "search": search,
        "active_only": active_only,
    }

    if actor.role == config.APPRENTICE:
        # An apprentice's "cohort" is themselves.
        if actor.apprentice_id is None:
            return []
        summary = repo.get_summary(actor.apprentice_id)
        return [summary] if summary else []
    if actor.role == config.STAFF:
        filters["tutor_id"] = actor.staff_id if actor.staff_id is not None else -1
    elif actor.role == config.EMPLOYER:
        filters["employer_id"] = actor.employer_id if actor.employer_id is not None else -1

    return repo.list_summaries(**filters)


def get_apprentice(actor: Actor, apprentice_id: int) -> ApprenticeSummary:
    """One apprentice, or raise if the actor may not see them."""
    require_any_view(actor)
    summary = repo.get_summary(apprentice_id)
    if summary is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, summary)
    return summary


def get_own_record(actor: Actor) -> ApprenticeSummary | None:
    """The signed-in apprentice's own record.

    Returns None rather than raising when the login has no apprentice
    record yet — the dashboard shows a "not linked" message, which is
    more useful than a stack trace on a half-provisioned account.
    """
    if actor.apprentice_id is None:
        return None
    return repo.get_summary(actor.apprentice_id)


def status_history(actor: Actor, apprentice_id: int) -> list[lifecycle.StatusChange]:
    get_apprentice(actor, apprentice_id)
    return repo.list_status_history(apprentice_id)


def list_breaks(actor: Actor, apprentice_id: int) -> list[dict[str, Any]]:
    get_apprentice(actor, apprentice_id)
    return repo.list_breaks(apprentice_id)


def available_transitions(actor: Actor, apprentice_id: int) -> tuple[str, ...]:
    """Statuses this apprentice may move to next.

    Empty for anyone without manage rights, so an interface can drive
    its status dropdown straight off this without a second check.
    """
    summary = get_apprentice(actor, apprentice_id)
    if not actor.can("apprentice.manage"):
        return ()
    return lifecycle.next_statuses(summary.apprentice.status)


def cohort_statistics(actor: Actor) -> dict[str, Any]:
    """Headline counts for the admin and staff dashboards."""
    require(actor, "report.view")
    summaries = list_apprentices(actor)
    by_status: dict[str, int] = {}
    for summary in summaries:
        key = summary.apprentice.status
        by_status[key] = by_status.get(key, 0) + 1
    active = [s for s in summaries if s.apprentice.is_active]
    behind = [s for s in active if s.is_behind]
    return {
        "total": len(summaries),
        "active": len(active),
        "by_status": by_status,
        "at_gateway": by_status.get("Gateway", 0),
        "completed": by_status.get("Completed", 0),
        "withdrawn": by_status.get("Withdrawn", 0),
        "behind_on_otj": len(behind),
        "behind_list": behind,
        "by_programme": repo.count_by_programme() if actor.is_admin else [],
        "by_employer": repo.count_by_employer() if actor.is_admin else [],
    }


# ═════════════════════════════════════════════════════════════════════
# Writes
# ═════════════════════════════════════════════════════════════════════

def create_apprentice(actor: Actor, payload: dict[str, Any]) -> Apprentice:
    """Enrol an apprentice.

    New records always start as ``Applicant``: putting somebody straight
    onto programme would skip the eligibility checks and the signed
    training plan that funding depends on. Moving them on is a separate,
    audited transition.
    """
    require(actor, "apprentice.manage")
    data = _validate(payload, existing=None)
    data["status"] = "Applicant"

    apprentice_id = repo.create(data)
    _seed_compliance_records(apprentice_id)
    repo.set_status(
        apprentice_id,
        "Applicant",
        from_status=None,
        reason="Enrolled",
        effective_date=date.today().isoformat(),
        actor=actor.username,
    )
    compliance_repository.record(
        action="create", entity="apprentice", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Enrolled {data.get('given_name')} {data.get('family_name')}",
    )
    logger.info("Apprentice %s enrolled by %s", apprentice_id, actor.username)

    created = repo.get(apprentice_id)
    assert created is not None
    return created


def update_apprentice(actor: Actor, apprentice_id: int, payload: dict[str, Any]) -> Apprentice:
    """Edit an apprentice's details.

    Status is deliberately not editable here — it goes through
    :func:`change_status`, which enforces the lifecycle and writes
    history. Silently accepting a status key would let a form bypass
    both.
    """
    require(actor, "apprentice.manage")
    existing = repo.get(apprentice_id)
    if existing is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, existing)

    data = _validate(payload, existing=existing)
    data.pop("status", None)
    repo.update(apprentice_id, data)
    compliance_repository.record(
        action="update", entity="apprentice", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
    )

    updated = repo.get(apprentice_id)
    assert updated is not None
    return updated


def change_status(
    actor: Actor,
    apprentice_id: int,
    new_status: str,
    *,
    reason: str | None = None,
    effective_date: str | None = None,
) -> Apprentice:
    """Move an apprentice through the lifecycle.

    The transition rules live in the domain; this adds the side effects
    each move implies — closing a break on return, stamping an end date
    on completion — so no caller has to remember them.
    """
    require(actor, "apprentice.manage")
    existing = repo.get(apprentice_id)
    if existing is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, existing)

    lifecycle.require_transition(existing.status, new_status, reason)
    when = _validate_date(effective_date, "Effective date") or date.today().isoformat()

    end_date: str | None = None
    if new_status in ("Completed", "Withdrawn", "Transferred"):
        end_date = when
    if existing.status == "Break in Learning" and new_status == "On Programme":
        repo.end_break(apprentice_id, when)
    if new_status == "Break in Learning":
        repo.add_break(
            apprentice_id,
            start_date=when,
            expected_return=None,
            reason=reason or "Not stated",
        )
    if new_status == "Withdrawn":
        repo.add_withdrawal(
            apprentice_id,
            withdrawal_date=when,
            reason=reason or "Not stated",
            recorded_by=actor.username,
        )

    repo.set_status(
        apprentice_id,
        new_status,
        from_status=existing.status,
        reason=reason,
        effective_date=when,
        actor=actor.username,
        actual_end_date=end_date,
    )
    compliance_repository.record(
        action="withdraw" if new_status == "Withdrawn" else "update",
        entity="apprentice", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{existing.status} -> {new_status}" + (f" ({reason})" if reason else ""),
    )
    logger.info(
        "Apprentice %s moved %s -> %s by %s",
        apprentice_id, existing.status, new_status, actor.username,
    )

    updated = repo.get(apprentice_id)
    assert updated is not None
    return updated


def start_programme(
    actor: Actor,
    apprentice_id: int,
    *,
    start_date: str,
    programme_id: int | None = None,
    effective_date: str | None = None,
) -> Apprentice:
    """Take an applicant onto programme, setting the dates that follow.

    The planned end date is derived from the programme's duration and
    the apprentice's contracted hours rather than typed in, because it
    is what the off-the-job target keys off — a hand-entered date that
    disagrees with the programme silently changes the target.
    """
    require(actor, "apprentice.manage")
    existing = repo.get(apprentice_id)
    if existing is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, existing)

    target_programme = programme_id or existing.programme_id
    if target_programme is None:
        raise ValidationError("Assign a programme before starting the apprenticeship")
    programme = programme_repository.get(target_programme)
    if programme is None:
        raise ValidationError(f"No programme with id {target_programme}")

    start = _validate_date(start_date, "Start date")
    if start is None:
        raise ValidationError("Start date is required")

    planned_end = planned_end_for(start, programme.duration_months, existing.weekly_hours)
    repo.update(apprentice_id, {
        "programme_id": target_programme,
        "start_date": start,
        "planned_end_date": planned_end,
    })
    return change_status(
        actor, apprentice_id, "On Programme",
        reason=f"Started {programme.title}",
        effective_date=effective_date or start,
    )


def assign_tutor(actor: Actor, apprentice_id: int, tutor_id: int | None) -> Apprentice:
    """Put an apprentice on a tutor's caseload, or take them off it."""
    require(actor, "apprentice.manage")
    existing = repo.get(apprentice_id)
    if existing is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, existing)

    repo.update(apprentice_id, {"tutor_id": tutor_id})
    compliance_repository.record(
        action="update", entity="apprentice", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Tutor set to {tutor_id}" if tutor_id else "Tutor cleared",
    )
    updated = repo.get(apprentice_id)
    assert updated is not None
    return updated


def delete_apprentice(actor: Actor, apprentice_id: int, *, reason: str) -> None:
    """Erase an apprentice and everything attached to them.

    Admin only, and genuinely destructive: it exists for correcting a
    duplicate or mistaken enrolment. Somebody who actually left is a
    withdrawal — that keeps the record, which the funding audit needs.
    """
    if not actor.is_admin:
        raise ValidationError(
            "Only an administrator may delete a record. To record a departure, "
            "withdraw the apprentice instead."
        )
    if not (reason or "").strip():
        raise ValidationError("A reason is required to delete a record")

    existing = repo.get(apprentice_id)
    if existing is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")

    compliance_repository.record(
        action="delete", entity="apprentice", entity_id=apprentice_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {existing.full_name}: {reason}",
    )
    repo.delete(apprentice_id)
    logger.warning(
        "Apprentice %s (%s) deleted by %s: %s",
        apprentice_id, existing.full_name, actor.username, reason,
    )


# ═════════════════════════════════════════════════════════════════════
# Validation
# ═════════════════════════════════════════════════════════════════════

def _validate(payload: dict[str, Any], *, existing: Apprentice | None) -> dict[str, Any]:
    """Normalise and check an apprentice payload.

    Only keys actually present are validated and returned, so a partial
    edit from a form that shows six fields does not blank the other
    fourteen.
    """
    data: dict[str, Any] = {}

    if existing is None or "given_name" in payload:
        data["given_name"] = _require_text(payload.get("given_name"), "First name")
    if existing is None or "family_name" in payload:
        data["family_name"] = _require_text(payload.get("family_name"), "Last name")

    if "uln" in payload:
        uln = validate_uln(payload.get("uln"))
        if uln:
            clash = repo.get_by_uln(uln)
            if clash and (existing is None or clash.apprentice_id != existing.apprentice_id):
                raise ValidationError(f"ULN {uln} already belongs to {clash.full_name}")
        data["uln"] = uln

    if "date_of_birth" in payload:
        data["date_of_birth"] = _validate_date(payload.get("date_of_birth"), "Date of birth")
    if "email" in payload:
        data["email"] = _validate_email(payload.get("email"))
    for key in ("phone", "username", "prior_learning", "support_needs", "notes"):
        if key in payload:
            data[key] = _optional_text(payload.get(key))

    if "weekly_hours" in payload:
        data["weekly_hours"] = _validate_weekly_hours(payload.get("weekly_hours"))

    if "programme_id" in payload:
        data["programme_id"] = _validate_fk(
            payload.get("programme_id"), programme_repository.get, "programme"
        )
    if "employer_id" in payload:
        data["employer_id"] = _validate_fk(
            payload.get("employer_id"), employer_repository.get, "employer"
        )
    if "workplace_id" in payload:
        data["workplace_id"] = _validate_fk(
            payload.get("workplace_id"), employer_repository.get_workplace, "workplace"
        )
    if "tutor_id" in payload:
        from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
            staff_repository,
        )
        data["tutor_id"] = _validate_fk(payload.get("tutor_id"), staff_repository.get, "tutor")

    if "funding_model" in payload:
        model = _optional_text(payload.get("funding_model"))
        if model and model not in config.FUNDING_MODELS:
            allowed = ", ".join(config.FUNDING_MODELS)
            raise ValidationError(f"Funding model must be one of: {allowed}")
        data["funding_model"] = model

    for key in ("start_date", "planned_end_date", "actual_end_date"):
        if key in payload:
            data[key] = _validate_date(payload.get(key), key.replace("_", " ").capitalize())

    # A workplace must belong to the employer it is recorded against,
    # otherwise the health-and-safety check on the placement means
    # nothing.
    employer_id = data.get("employer_id", existing.employer_id if existing else None)
    workplace_id = data.get("workplace_id", existing.workplace_id if existing else None)
    if workplace_id and employer_id:
        workplace = employer_repository.get_workplace(workplace_id)
        if workplace and workplace.employer_id != employer_id:
            raise ValidationError("That workplace belongs to a different employer")

    start = data.get("start_date", existing.start_date if existing else None)
    end = data.get("planned_end_date", existing.planned_end_date if existing else None)
    if start and end and end <= start:
        raise ValidationError("Planned end date must be after the start date")

    return data


def _seed_compliance_records(apprentice_id: int) -> None:
    """Create the blank English and Maths rows a new apprentice needs.

    Eligibility checks and documents materialise on first read, but
    functional skills are shown on the apprentice's own dashboard from
    day one, so they are worth creating up front.
    """
    try:
        for subject in config.FUNCTIONAL_SKILLS:
            compliance_repository.set_functional_skill(
                apprentice_id, subject, status="Not started"
            )
    except Exception:
        logger.debug("Could not seed functional skills for %s", apprentice_id, exc_info=True)


def require_any_view(actor: Actor) -> None:
    """Every read path needs one of the two view permissions."""
    if actor.can("apprentice.view") or actor.can("apprentice.view_own"):
        return
    require(actor, "apprentice.view")


def _require_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{label} is required")
    if len(text) > 100:
        raise ValidationError(f"{label} must be 100 characters or fewer")
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


def _validate_weekly_hours(value: Any) -> float:
    try:
        hours = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("Weekly hours must be a number") from exc
    if hours <= 0:
        raise ValidationError("Weekly hours must be greater than zero")
    if hours > 60:
        raise ValidationError("Weekly hours cannot exceed 60")
    return round(hours, 1)


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
