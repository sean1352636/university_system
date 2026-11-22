"""Who is asking, and what they are allowed to see.

Five roles share one database here, and three of them are outsiders:
an employer must see their own apprentices and nobody else's, an
apprentice their own record only, and an end-point assessor the
assessment side without the provider's formative judgements. Getting
that wrong is a data breach, not a bug.

So every service call takes an :class:`Actor`. The actor carries the
role *and* the identity it resolves to — which employer, which
apprentice, which member of staff — and services use both: they call
:func:`require` for the capability check and read the scope fields to
constrain the query. Filtering in the interface layer instead would
mean every new screen re-deriving the same rules, and eventually one of
them getting it wrong.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from education_system.systems.apprenticeships import config

logger = logging.getLogger(__name__)

SYSTEM_KEY = "apprenticeships"


class PermissionDenied(PermissionError):
    """The actor may not do this.

    Distinct from ``ValidationError``: the request was well formed, the
    caller just isn't allowed. Interfaces show it as a refusal rather
    than a correctable input error.
    """


@dataclass(frozen=True)
class Actor:
    """The authenticated user, resolved against this system's records.

    The scope fields are the whole point. ``employer_id`` on an employer
    actor is not a convenience — it is the boundary of everything they
    are permitted to read.
    """

    username: str
    role: str
    display_name: str = ""
    # Set when the login maps onto a record in this system.
    apprentice_id: int | None = None
    employer_id: int | None = None
    staff_id: int | None = None

    @property
    def role_label(self) -> str:
        return config.ROLE_LABELS.get(self.role, self.role.replace("_", " ").title())

    @property
    def is_admin(self) -> bool:
        return self.role == config.ADMIN

    @property
    def is_provider(self) -> bool:
        """Provider staff see formative assessment; outsiders do not."""
        return self.role in config.PROVIDER_ROLES

    @property
    def name(self) -> str:
        return self.display_name or self.username

    def can(self, permission: str) -> bool:
        return config.can(self.role, permission)

    def permissions(self) -> frozenset[str]:
        return config.permissions_for(self.role)


# An actor with no role and no scope. Used by read-only internals that
# need an Actor-shaped argument but do their own gating.
ANONYMOUS = Actor(username="", role="")


def require(actor: Actor | None, permission: str) -> None:
    """Raise unless *actor* holds *permission*."""
    if actor is None or not actor.can(permission):
        role = (actor.role if actor else None) or "unknown"
        raise PermissionDenied(
            f"Your role ({config.ROLE_LABELS.get(role, role)}) may not perform this action"
        )


def require_any(actor: Actor | None, *permissions: str) -> None:
    """Raise unless *actor* holds at least one of *permissions*."""
    if actor is not None and any(actor.can(p) for p in permissions):
        return
    role = (actor.role if actor else None) or "unknown"
    raise PermissionDenied(
        f"Your role ({config.ROLE_LABELS.get(role, role)}) may not perform this action"
    )


def resolve(user_info: dict[str, Any] | None, role: str | None = None) -> Actor:
    """Build an :class:`Actor` from a shared-auth session.

    *user_info* is the dict the platform login hands back. The role comes
    from its ``systems`` list rather than the argument where possible —
    the launcher passes a role through several hops and the stored grant
    is the authoritative one.

    Resolution failures are not errors. A brand-new employer login with
    no manager record yet gets an actor with ``employer_id=None``, and
    the scoping helpers below turn that into "sees nothing" rather than
    "sees everything" — the safe direction.
    """
    username = str((user_info or {}).get("username") or "").strip()
    display_name = str((user_info or {}).get("display_name") or "").strip()

    resolved_role = _role_from_user_info(user_info) or (role or "").strip().lower()
    if resolved_role not in config.ROLES:
        # An account granted a generic platform role (say "teacher") that
        # has no apprenticeships meaning is treated as provider staff,
        # the least-privileged role that can still do a day's work.
        resolved_role = _map_platform_role(resolved_role)

    actor = _attach_scope(Actor(username=username, role=resolved_role, display_name=display_name))
    if actor.role == config.APPRENTICE and actor.apprentice_id is not None:
        # Sign-in is where an account from before automatic linking meets
        # it, so the learner-record link is checked here too.
        from education_system.systems.apprenticeships.application.security import login_links

        login_links.try_sync_username(actor.username)
    return actor


def _role_from_user_info(user_info: dict[str, Any] | None) -> str | None:
    """The role granted for this system, from the session's systems list."""
    for entry in (user_info or {}).get("systems") or []:
        if entry.get("system_key") == SYSTEM_KEY:
            return str(entry.get("role") or "").strip().lower()
    return None


def _map_platform_role(role: str) -> str:
    """Translate a generic platform role into an apprenticeships one.

    Superadmins arrive holding "admin" across the school systems, and
    the launcher's role picker offers the platform vocabulary. Anything
    unrecognised falls to staff, never to admin.
    """
    return {
        "admin": config.ADMIN,
        "staff": config.STAFF,
        "teacher": config.STAFF,
        "instructor": config.STAFF,
        "assessor": config.STAFF,
        "student": config.APPRENTICE,
        "apprentice": config.APPRENTICE,
        "learner": config.APPRENTICE,
        "employer": config.EMPLOYER,
        "parent": config.EMPLOYER,
        "epa": config.END_POINT_ASSESSOR,
        "assessor_epa": config.END_POINT_ASSESSOR,
    }.get(role, config.STAFF)


def _attach_scope(actor: Actor) -> Actor:
    """Look up the record this login corresponds to.

    Wrapped defensively: a lookup failure (a missing table on a fresh
    install, say) must degrade to an unscoped actor rather than block
    login entirely. Unscoped means restricted, not privileged.
    """
    if not actor.username or actor.is_admin:
        return actor

    from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
        apprentice_repository,
        employer_repository,
        staff_repository,
    )

    try:
        if actor.role == config.APPRENTICE:
            record = apprentice_repository.get_by_username(actor.username)
            if record:
                return Actor(
                    username=actor.username,
                    role=actor.role,
                    display_name=actor.display_name or record.full_name,
                    apprentice_id=record.apprentice_id,
                    employer_id=record.employer_id,
                )
        elif actor.role == config.EMPLOYER:
            employer = employer_repository.get_by_manager_username(actor.username)
            if employer:
                return Actor(
                    username=actor.username,
                    role=actor.role,
                    display_name=actor.display_name,
                    employer_id=employer.employer_id,
                )
        elif actor.role == config.STAFF:
            member = staff_repository.get_by_username(actor.username)
            if member:
                return Actor(
                    username=actor.username,
                    role=actor.role,
                    display_name=actor.display_name or member.full_name,
                    staff_id=member.staff_id,
                )
    except Exception:
        logger.debug("Could not resolve scope for %s", actor.username, exc_info=True)
    return actor


# ═════════════════════════════════════════════════════════════════════
# Scoping
# ═════════════════════════════════════════════════════════════════════
#
# These turn an actor into repository filter arguments. Services splat
# them into list calls, so a screen cannot accidentally query wider than
# the actor's role allows.


class OutOfScope(Exception):
    """Raised internally when an actor's scope can match nothing."""


def apprentice_filters(actor: Actor) -> dict[str, Any]:
    """Repository filters restricting a cohort query to *actor*'s scope.

    Admins and end-point assessors get an empty dict — they legitimately
    see the whole cohort, the assessor because they are assessing
    against it. Everyone else is constrained, and an unresolved scope
    yields an impossible filter rather than an open one.
    """
    if actor.role in (config.ADMIN, config.END_POINT_ASSESSOR):
        return {}
    if actor.role == config.STAFF:
        # A tutor without a staff record has no caseload to show. Falling
        # back to the whole cohort would be the wrong kind of helpful.
        return {"tutor_id": actor.staff_id or _IMPOSSIBLE_ID}
    if actor.role == config.EMPLOYER:
        return {"employer_id": actor.employer_id or _IMPOSSIBLE_ID}
    if actor.role == config.APPRENTICE:
        return {"apprentice_id": actor.apprentice_id or _IMPOSSIBLE_ID}
    return {"apprentice_id": _IMPOSSIBLE_ID}


# No autoincrement primary key will ever be negative, so this matches
# nothing — an explicit empty result rather than an accidental full one.
_IMPOSSIBLE_ID = -1


def may_view_apprentice(actor: Actor, apprentice: Any) -> bool:
    """Is this apprentice inside *actor*'s scope?

    *apprentice* is anything carrying ``apprentice_id``, ``employer_id``
    and ``tutor_id`` — the record or a summary.
    """
    if apprentice is None:
        return False
    record = getattr(apprentice, "apprentice", apprentice)
    if actor.role in (config.ADMIN, config.END_POINT_ASSESSOR):
        return True
    if actor.role == config.STAFF:
        return actor.staff_id is not None and getattr(record, "tutor_id", None) == actor.staff_id
    if actor.role == config.EMPLOYER:
        return (
            actor.employer_id is not None
            and getattr(record, "employer_id", None) == actor.employer_id
        )
    if actor.role == config.APPRENTICE:
        return (
            actor.apprentice_id is not None
            and getattr(record, "apprentice_id", None) == actor.apprentice_id
        )
    return False


def require_apprentice_access(actor: Actor, apprentice: Any) -> None:
    """Raise unless *actor* may see this apprentice.

    The message deliberately does not confirm the record exists — an
    employer probing ids should not be able to tell "not yours" from
    "no such apprentice".
    """
    if not may_view_apprentice(actor, apprentice):
        raise PermissionDenied("You do not have access to this apprentice's record")


def visible_roles(actor: Actor) -> tuple[str, ...]:
    """Roles *actor* may assign when creating accounts. Admin only."""
    return config.ROLES if actor.is_admin else ()
