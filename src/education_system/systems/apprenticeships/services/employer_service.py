"""Employers, their workplaces, and the managers who sign for them.

The employer is a party to the apprenticeship, not a bystander: they
sign the commitment statement, attend every review, confirm off-the-job
hours, and pay for part or all of the training. So they get logins — and
those logins belong to an outsider. An employer user must see their own
organisation and nothing else, which is enforced here by
:func:`_require_employer_access` on every path that names an employer,
a workplace or a manager.

Every function takes ``actor`` first. Provider staff and admins see the
whole employer list; an employer sees one row.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.employers import contacts as contact_rules
from education_system.systems.apprenticeships.domain.employers import models
from education_system.systems.apprenticeships.domain.employers.models import (
    Employer,
    EmployerManager,
    EmployerSummary,
    Workplace,
)
from education_system.systems.apprenticeships.domain.funding import funding_rules
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    employer_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    compliance_repository,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    require,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def list_employers(
    actor: Actor,
    *,
    status: str | None = None,
    search: str | None = None,
    active_only: bool = False,
) -> list[EmployerSummary]:
    """The employers *actor* may see, with any extra filters applied.

    An employer user gets their own organisation and no filters: a
    search box that could return somebody else's row, even empty, tells
    them who else the provider works with.
    """
    require(actor, "employer.view")
    if actor.role == config.EMPLOYER:
        if actor.employer_id is None:
            return []
        summary = repo.get_summary(actor.employer_id)
        return [summary] if summary else []
    return repo.list_summaries(status=status, search=search, active_only=active_only)


def get_employer(actor: Actor, employer_id: int) -> EmployerSummary:
    """One employer with its counts, or raise if there is no such id."""
    require(actor, "employer.view")
    _require_employer_access(actor, employer_id)
    summary = repo.get_summary(employer_id)
    if summary is None:
        raise ValidationError(f"No employer with id {employer_id}")
    return summary


def get_own_employer(actor: Actor) -> EmployerSummary | None:
    """The signed-in employer user's own organisation.

    Returns None rather than raising when the login is not linked to a
    manager record yet — the portal dashboard shows a "not linked"
    message, which is more useful than a stack trace on a half-set-up
    account.
    """
    if actor.employer_id is None:
        return None
    return repo.get_summary(actor.employer_id)


def funding_position(actor: Actor, employer_id: int) -> funding_rules.LevyPosition:
    """The employer's annual levy liability, derived from their pay bill."""
    employer = _load(actor, employer_id)
    return funding_rules.levy_position(employer.paybill)


def list_workplaces(
    actor: Actor, employer_id: int, *, active_only: bool = False
) -> list[Workplace]:
    """The sites this employer places apprentices at."""
    require(actor, "employer.view")
    _require_employer_access(actor, employer_id)
    return repo.list_workplaces(employer_id, active_only=active_only)


def list_managers(
    actor: Actor, employer_id: int, *, active_only: bool = False
) -> list[EmployerManager]:
    """The named contacts at this employer."""
    require(actor, "employer.view")
    _require_employer_access(actor, employer_id)
    return repo.list_managers(employer_id, active_only=active_only)


# ═════════════════════════════════════════════════════════════════════
# Writes
# ═════════════════════════════════════════════════════════════════════

def create_employer(actor: Actor, payload: dict[str, Any]) -> Employer:
    """Add an employing organisation."""
    require(actor, "employer.manage")
    data = _validate(payload, existing=None)

    employer_id = repo.create(data)
    compliance_repository.record(
        action="create", entity="employer", entity_id=employer_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Created {data.get('name')}",
    )
    logger.info("Employer %s created by %s", employer_id, actor.username)

    created = repo.get(employer_id)
    assert created is not None
    return created


def update_employer(actor: Actor, employer_id: int, payload: dict[str, Any]) -> Employer:
    """Edit an employer's details."""
    require(actor, "employer.manage")
    _require_employer_access(actor, employer_id)
    existing = repo.get(employer_id)
    if existing is None:
        raise ValidationError(f"No employer with id {employer_id}")

    data = _validate(payload, existing=existing)
    repo.update(employer_id, data)
    compliance_repository.record(
        action="update", entity="employer", entity_id=employer_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
    )

    updated = repo.get(employer_id)
    assert updated is not None
    return updated


def delete_employer(actor: Actor, employer_id: int, *, reason: str) -> None:
    """Erase an employer along with its workplaces and managers.

    Admin only, and genuinely destructive: it exists for correcting a
    record that should never have been created. An organisation the
    provider has stopped working with gets status 'Ended', which keeps
    the contract history the funding audit reads.
    """
    if not actor.is_admin:
        raise ValidationError(
            "Only an administrator may delete an employer. To end the relationship, "
            "set the employer's status to 'Ended' instead."
        )
    if not (reason or "").strip():
        raise ValidationError("A reason is required to delete an employer")

    summary = repo.get_summary(employer_id)
    if summary is None:
        raise ValidationError(f"No employer with id {employer_id}")

    if summary.apprentice_count:
        raise ValidationError(
            f"{summary.apprentice_count} apprentice record(s) reference "
            f"{summary.name}. Deleting it would strip the employer from their record "
            "and with it the placement the funding claim rests on."
        )

    compliance_repository.record(
        action="delete", entity="employer", entity_id=employer_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {summary.name}: {reason}",
    )
    repo.delete(employer_id)
    logger.warning(
        "Employer %s (%s) deleted by %s: %s",
        employer_id, summary.name, actor.username, reason,
    )


def add_workplace(actor: Actor, employer_id: int, payload: dict[str, Any]) -> Workplace:
    """Add a site this employer may place apprentices at."""
    require(actor, "employer.manage")
    _require_employer_access(actor, employer_id)
    employer = repo.get(employer_id)
    if employer is None:
        raise ValidationError(f"No employer with id {employer_id}")

    data = _validate_workplace(payload, existing=None)
    data["employer_id"] = employer_id

    workplace_id = repo.create_workplace(data)
    compliance_repository.record(
        action="create", entity="workplace", entity_id=workplace_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['name']} added to {employer.name}",
    )
    logger.info("Workplace %s added to employer %s by %s", workplace_id, employer_id,
                actor.username)

    created = repo.get_workplace(workplace_id)
    assert created is not None
    return created


def update_workplace(actor: Actor, workplace_id: int, payload: dict[str, Any]) -> Workplace:
    """Edit a site's details."""
    require(actor, "employer.manage")
    existing = _load_workplace(actor, workplace_id)

    data = _validate_workplace(payload, existing=existing)
    repo.update_workplace(workplace_id, data)
    compliance_repository.record(
        action="update", entity="workplace", entity_id=workplace_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{existing.name}: " + (", ".join(sorted(data)) or "no change"),
    )

    updated = repo.get_workplace(workplace_id)
    assert updated is not None
    return updated


def deactivate_workplace(actor: Actor, workplace_id: int) -> Workplace:
    """Stop new placements at a site without deleting it.

    Deleting would take the site off apprentices already placed there,
    losing the health-and-safety evidence for the period they worked at
    it. Deactivating leaves the history intact.
    """
    require(actor, "employer.manage")
    existing = _load_workplace(actor, workplace_id)

    repo.update_workplace(workplace_id, {"active": 0})
    compliance_repository.record(
        action="update", entity="workplace", entity_id=workplace_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deactivated {existing.name}",
    )
    logger.info("Workplace %s deactivated by %s", workplace_id, actor.username)

    updated = repo.get_workplace(workplace_id)
    assert updated is not None
    return updated


def record_hs_check(
    actor: Actor,
    workplace_id: int,
    *,
    checked_date: str,
    expiry_date: str | None = None,
) -> Workplace:
    """Record a health and safety inspection of a site."""
    require(actor, "employer.manage")
    existing = _load_workplace(actor, workplace_id)

    checked = _validate_date(checked_date, "Check date")
    if checked is None:
        raise ValidationError("A check date is required")
    if checked > date.today().isoformat():
        raise ValidationError("A health and safety check cannot be dated in the future")

    # No expiry means the check never lapses, which is how a site with a
    # standing approval is recorded. Anything else must expire after the
    # check that granted it.
    expiry = _validate_date(expiry_date, "Expiry date")
    if expiry and expiry <= checked:
        raise ValidationError("The expiry date must be after the check date")

    repo.update_workplace(
        workplace_id, {"hs_checked_date": checked, "hs_expiry_date": expiry}
    )
    compliance_repository.record(
        action="approve", entity="workplace", entity_id=workplace_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"H&S check on {existing.name}: {checked}"
               + (f", expires {expiry}" if expiry else ""),
    )
    logger.info("H&S check recorded for workplace %s by %s", workplace_id, actor.username)

    updated = repo.get_workplace(workplace_id)
    assert updated is not None
    return updated


def add_manager(actor: Actor, employer_id: int, payload: dict[str, Any]) -> EmployerManager:
    """Add a named contact at this employer."""
    require(actor, "employer.manage")
    _require_employer_access(actor, employer_id)
    employer = repo.get(employer_id)
    if employer is None:
        raise ValidationError(f"No employer with id {employer_id}")

    data = _validate_manager(payload, existing=None)
    data["employer_id"] = employer_id
    # Promotion runs through set_primary_manager, which demotes the
    # incumbent first. Honouring the flag here would leave two primaries
    # and no way to tell which one signs.
    data.pop("is_primary", None)

    manager_id = repo.create_manager(data)
    compliance_repository.record(
        action="create", entity="employer_manager", entity_id=manager_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['full_name']} added to {employer.name}",
    )
    logger.info("Manager %s added to employer %s by %s", manager_id, employer_id, actor.username)

    created = repo.get_manager(manager_id)
    assert created is not None
    return created


def update_manager(actor: Actor, manager_id: int, payload: dict[str, Any]) -> EmployerManager:
    """Edit a contact's details."""
    require(actor, "employer.manage")
    existing = _load_manager(actor, manager_id)

    data = _validate_manager(payload, existing=existing)
    data.pop("is_primary", None)
    repo.update_manager(manager_id, data)
    compliance_repository.record(
        action="update", entity="employer_manager", entity_id=manager_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{existing.full_name}: " + (", ".join(sorted(data)) or "no change"),
    )

    updated = repo.get_manager(manager_id)
    assert updated is not None
    return updated


def set_primary_manager(actor: Actor, employer_id: int, manager_id: int) -> EmployerManager:
    """Make this contact the employer's signatory."""
    require(actor, "employer.manage")
    _require_employer_access(actor, employer_id)
    existing = repo.get_manager(manager_id)
    if existing is None:
        raise ValidationError(f"No manager with id {manager_id}")
    if existing.employer_id != employer_id:
        raise ValidationError("That contact belongs to a different employer")

    # Demote first, then promote: the table cannot express "only one",
    # and a promotion that left the incumbent flagged would give the
    # commitment statement two signatories.
    repo.clear_primary(employer_id)
    repo.update_manager(manager_id, {"is_primary": 1})
    compliance_repository.record(
        action="update", entity="employer_manager", entity_id=manager_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{existing.full_name} set as primary contact",
    )
    logger.info(
        "Manager %s set as primary for employer %s by %s",
        manager_id, employer_id, actor.username,
    )

    updated = repo.get_manager(manager_id)
    assert updated is not None
    return updated


def deactivate_manager(actor: Actor, manager_id: int) -> EmployerManager:
    """Retire a contact.

    Their login stops resolving to the employer as a side effect — the
    portal lookup only matches active contacts — so this is also how an
    employer user's access is revoked.
    """
    require(actor, "employer.manage")
    existing = _load_manager(actor, manager_id)

    repo.update_manager(manager_id, {"active": 0, "is_primary": 0})
    compliance_repository.record(
        action="update", entity="employer_manager", entity_id=manager_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deactivated {existing.full_name}",
    )
    logger.info("Manager %s deactivated by %s", manager_id, actor.username)

    updated = repo.get_manager(manager_id)
    assert updated is not None
    return updated


# ═════════════════════════════════════════════════════════════════════
# Validation
# ═════════════════════════════════════════════════════════════════════

def _require_employer_access(actor: Actor, employer_id: int) -> None:
    """Raise unless *actor* may touch this organisation's records.

    Only the employer role is constrained: admins and provider staff
    work across the whole employer base, and the roles with no employer
    permission at all never reach here. An employer login with no
    resolved organisation matches nothing, which is the safe direction.
    """
    if actor.role != config.EMPLOYER:
        return
    if actor.employer_id is not None and actor.employer_id == employer_id:
        return
    raise PermissionDenied("You do not have access to this employer's records")


def _load(actor: Actor, employer_id: int) -> Employer:
    """The employer record, once *actor* is allowed to see it."""
    require(actor, "employer.view")
    _require_employer_access(actor, employer_id)
    employer = repo.get(employer_id)
    if employer is None:
        raise ValidationError(f"No employer with id {employer_id}")
    return employer


def _load_workplace(actor: Actor, workplace_id: int) -> Workplace:
    """A site, scoped through the employer that owns it."""
    workplace = repo.get_workplace(workplace_id)
    if workplace is None:
        raise ValidationError(f"No workplace with id {workplace_id}")
    _require_employer_access(actor, workplace.employer_id)
    return workplace


def _load_manager(actor: Actor, manager_id: int) -> EmployerManager:
    """A contact, scoped through the employer that owns them."""
    manager = repo.get_manager(manager_id)
    if manager is None:
        raise ValidationError(f"No manager with id {manager_id}")
    _require_employer_access(actor, manager.employer_id)
    return manager


def _validate(payload: dict[str, Any], *, existing: Employer | None) -> dict[str, Any]:
    """Normalise and check an employer payload.

    Only keys actually present are validated and returned, so a partial
    edit from a form showing four fields does not blank the other eight.
    """
    data: dict[str, Any] = {}

    if existing is None or "name" in payload:
        data["name"] = _require_text(payload.get("name"), "Employer name")

    for key in ("company_number", "sector", "address", "postcode", "notes"):
        if key in payload:
            data[key] = _optional_text(payload.get(key))

    if "headcount" in payload:
        data["headcount"] = _validate_count(payload.get("headcount"), "Headcount")
    if "paybill" in payload:
        data["paybill"] = _validate_money(payload.get("paybill"), "Pay bill")

    if "size" in payload or "headcount" in payload:
        # Derived from headcount when the form does not offer a band. The
        # small-employer funding rule keys off the band, so leaving it
        # blank when we know the headcount would quietly cost the
        # employer an exemption they qualify for.
        headcount = data.get("headcount", existing.headcount if existing else None)
        data["size"] = models.validate_size(_optional_text(payload.get("size")), headcount)

    if "status" in payload:
        data["status"] = models.validate_status(payload.get("status"))

    for key in ("contract_start", "contract_end"):
        if key in payload:
            data[key] = _validate_date(payload.get(key), key.replace("_", " ").capitalize())

    start = data.get("contract_start", existing.contract_start if existing else None)
    end = data.get("contract_end", existing.contract_end if existing else None)
    if start and end and end <= start:
        raise ValidationError("The contract end date must be after the start date")

    return data


def _validate_workplace(payload: dict[str, Any], *, existing: Workplace | None) -> dict[str, Any]:
    """Normalise and check a workplace payload."""
    data: dict[str, Any] = {}

    if existing is None or "name" in payload:
        data["name"] = _require_text(payload.get("name"), "Site name")
    for key in ("address", "postcode"):
        if key in payload:
            data[key] = _optional_text(payload.get(key))

    checked = existing.hs_checked_date if existing else None
    if "hs_checked_date" in payload:
        checked = _validate_date(payload.get("hs_checked_date"), "Check date")
        data["hs_checked_date"] = checked
    if "hs_expiry_date" in payload:
        expiry = _validate_date(payload.get("hs_expiry_date"), "Expiry date")
        if expiry and checked and expiry <= checked:
            raise ValidationError("The expiry date must be after the check date")
        data["hs_expiry_date"] = expiry

    if "active" in payload:
        data["active"] = 1 if _as_bool(payload.get("active")) else 0

    return data


def validate_contact_payload(
    payload: dict[str, Any], *, existing: EmployerManager | None
) -> dict[str, Any]:
    """Normalise a contact payload the way add/update_manager do.

    Public so the contacts screen's service can reuse the same rules
    without reaching into this module's privates.
    """
    return _validate_manager(payload, existing=existing)


def _validate_manager(
    payload: dict[str, Any], *, existing: EmployerManager | None
) -> dict[str, Any]:
    """Normalise and check an employer manager payload."""
    data: dict[str, Any] = {}

    if existing is None or "full_name" in payload:
        data["full_name"] = _require_text(payload.get("full_name"), "Contact name")
    for key in ("job_title", "phone", "username"):
        if key in payload:
            data[key] = _optional_text(payload.get(key))
    if "email" in payload:
        data["email"] = _validate_email(payload.get("email"))
    if "is_primary" in payload:
        data["is_primary"] = 1 if _as_bool(payload.get("is_primary")) else 0
    if "active" in payload:
        data["active"] = 1 if _as_bool(payload.get("active")) else 0
    if "contact_role" in payload:
        data["contact_role"] = contact_rules.validate_contact_role(payload.get("contact_role"))

    return data


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


def _validate_count(value: Any, label: str) -> int | None:
    # None has to survive: "never told us" and "genuinely zero" mean
    # different things to the small-employer rule.
    if value in (None, ""):
        return None
    try:
        count = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must be a whole number") from exc
    if count < 0:
        raise ValidationError(f"{label} cannot be negative")
    return count


def _validate_money(value: Any, label: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        amount = float(str(value).strip().replace(",", "").lstrip(config.CURRENCY_SYMBOL))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must be a number") from exc
    if amount < 0:
        raise ValidationError(f"{label} cannot be negative")
    return round(amount, 2)


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(value)
