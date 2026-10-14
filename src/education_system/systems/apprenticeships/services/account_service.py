"""Accounts: passwords, multi-factor enrolment, and who may sign in here.

Logins are not this system's property. They live in the platform's
shared ``auth.db`` and are the same account the user takes into the
university or the sixth form, so nothing here owns a password or a TOTP
secret — this module is the adapter that lets the apprenticeships
screens reach the platform auth layer without every window importing it
and re-deriving the same rules.

Two rules are this system's own, and they are the reason the adapter is
not just a re-export:

* an account only reaches these screens once it holds a ``user_systems``
  row for ``apprenticeships``, so granting and revoking are expressed in
  this system's five roles rather than the platform's school vocabulary
  (which has no word for an end-point assessor);
* a login is only *useful* once it is linked to the record it belongs to
  — an apprentice, an employer contact or a member of staff — because
  every scope check reads that link. Granting without linking produces
  an account that signs in to empty screens, so :func:`link_to_record`
  sits next to the grant rather than in a separate tool.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.records import audit
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    employer_repository,
    staff_repository,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    SYSTEM_KEY,
)

logger = logging.getLogger(__name__)

# What a role needs linking to before its screens hold anything.
LINK_TARGETS: dict[str, str] = {
    config.APPRENTICE: "apprentice record",
    config.EMPLOYER: "employer contact",
    config.STAFF: "staff record",
}


class AccountError(Exception):
    """The platform auth layer refused an account operation.

    Distinct from ``ValidationError`` only in where it came from; both
    are shown to the user verbatim, because the auth layer's messages
    ("Cannot reuse any of your last 5 passwords") are the actionable
    ones.
    """


# ═════════════════════════════════════════════════════════════════════
# The signed-in account
# ═════════════════════════════════════════════════════════════════════

def whoami(actor: Actor) -> dict[str, Any]:
    """The platform account behind *actor*, as far as this system can see.

    ``user_id`` is None when the login does not resolve — a test actor,
    or an account removed from ``auth.db`` while a session was open. The
    screens use that to explain why the account actions are unavailable
    rather than failing when one is pressed.
    """
    row = _user_row(actor.username)
    return {
        "username": actor.username,
        "user_id": row["id"] if row else None,
        "display_name": (row["display_name"] if row else "") or actor.display_name,
        "email": (row["email"] if row else None),
        "is_active": bool(row["is_active"]) if row else False,
        "must_change_password": bool(row["must_change_password"]) if row else False,
        "role": actor.role,
        "role_label": actor.role_label,
        "linked": is_linked(actor),
        "link_target": LINK_TARGETS.get(actor.role),
    }


def is_linked(actor: Actor) -> bool:
    """Does this login resolve to the record its role needs?"""
    if actor.role == config.APPRENTICE:
        return actor.apprentice_id is not None
    if actor.role == config.EMPLOYER:
        return actor.employer_id is not None
    if actor.role == config.STAFF:
        return actor.staff_id is not None
    return True


# ═════════════════════════════════════════════════════════════════════
# Password
# ═════════════════════════════════════════════════════════════════════

def password_requirements() -> list[str]:
    """The platform's password policy, in words, for the change form.

    Derived by asking the validator rather than restated here, so a
    policy change in the platform cannot leave this screen lying. The
    probes are deliberately awful passwords; each one names the rule it
    is meant to trip.
    """
    from education_system.platform.identity.auth.password_manager import (
        validate_password_strength,
    )

    rules: list[str] = []
    for probe in ("aA1!", "abcdefghijkl!1", "ABCDEFGHIJKL!1", "Abcdefghijkl!",
                  "Abcdefghijkl1"):
        ok, message = validate_password_strength(probe)
        if not ok and message not in rules:
            rules.append(message)
    if not rules:
        rules.append("Any password the platform accepts.")
    rules.append("Cannot repeat any of your last 5 passwords.")
    return rules


def change_password(actor: Actor, *, current: str, new: str, confirm: str) -> None:
    """Change *actor*'s own password on the shared platform account.

    Every signed-in session is invalidated by the platform when the hash
    changes, this one included — so the caller must tell the user they
    are about to be signed out rather than leaving them staring at a
    screen whose next click will fail.
    """
    if not (current or "").strip():
        raise ValidationError("Enter your current password")
    if not (new or "").strip():
        raise ValidationError("Enter a new password")
    if new != confirm:
        raise ValidationError("The new passwords do not match")
    if new == current:
        raise ValidationError("The new password must be different from the current one")

    user_id = _require_user_id(actor.username)
    _guard(lambda: _auth().change_password(user_id, current, new))
    logger.info("Password changed for %s via the apprenticeships system", actor.username)


# ═════════════════════════════════════════════════════════════════════
# Multi-factor authentication
# ═════════════════════════════════════════════════════════════════════

def mfa_status(actor: Actor) -> dict[str, Any]:
    """Whether MFA is on for this account, and how many codes are left."""
    row = _user_row(actor.username)
    if row is None:
        return {"available": False, "enabled": False, "recovery_codes_remaining": 0}
    service = _mfa()
    enabled = bool(_guard(lambda: service.is_mfa_enabled(row["id"])))
    return {
        "available": True,
        "enabled": enabled,
        "recovery_codes_remaining": (
            int(_guard(lambda: service.get_remaining_recovery_codes(row["id"]))) if enabled else 0
        ),
    }


def enrol_mfa(actor: Actor) -> dict[str, Any]:
    """Start authenticator enrolment, returning the secret and recovery codes.

    The recovery codes are shown once and never again — only their
    hashes are stored — so the caller must display them before moving
    on. Re-enrolling replaces any existing secret and invalidates the
    old codes, which is what "I lost my phone" needs.
    """
    user_id = _require_user_id(actor.username)
    result = _guard(lambda: _mfa().setup_totp(user_id, actor.username))
    logger.info("MFA enrolment started for %s", actor.username)
    return dict(result)


def confirm_mfa(actor: Actor, code: str) -> bool:
    """Check a code from the authenticator against the enrolled secret."""
    if not (code or "").strip():
        raise ValidationError("Enter the six-digit code from your authenticator app")
    user_id = _require_user_id(actor.username)
    return bool(_guard(lambda: _mfa().verify_totp(user_id, code.strip())))


def disable_mfa(actor: Actor, code: str) -> None:
    """Turn MFA off, once a current code proves the authenticator is to hand.

    Requiring the code is the point: an unlocked, unattended session
    must not be able to strip the second factor off the account.
    """
    user_id = _require_user_id(actor.username)
    if not confirm_mfa(actor, code):
        raise ValidationError(
            "That code was not accepted, so MFA has been left on. Use a recovery "
            "code instead if you no longer have the authenticator."
        )
    _guard(lambda: _mfa().disable_mfa(user_id))
    logger.info("MFA disabled for %s", actor.username)


def disable_mfa_with_recovery_code(actor: Actor, code: str) -> None:
    """Turn MFA off using a recovery code, for a lost authenticator."""
    if not (code or "").strip():
        raise ValidationError("Enter one of your recovery codes")
    user_id = _require_user_id(actor.username)
    if not _guard(lambda: _mfa().verify_recovery_code(user_id, code.strip())):
        raise ValidationError("That recovery code was not accepted")
    _guard(lambda: _mfa().disable_mfa(user_id))
    logger.warning("MFA disabled for %s using a recovery code", actor.username)


# ═════════════════════════════════════════════════════════════════════
# Who may sign in here
# ═════════════════════════════════════════════════════════════════════

def list_accounts(actor: Actor) -> list[dict[str, Any]]:
    """Every account with apprenticeships access, and what it links to.

    Administrators only. The list names other people's logins and their
    account state, which is not a tutor's business.
    """
    _require_admin(actor)
    from education_system.platform.identity.auth.db import connect

    with _closing(connect()) as conn:
        rows = conn.execute(
            """SELECT u.id, u.username, u.display_name, u.email,
                      u.is_active, u.must_change_password, us.role
                 FROM users u
                 JOIN user_systems us ON us.user_id = u.id
                WHERE us.system_key = ?
                ORDER BY us.role, u.username""",
            (SYSTEM_KEY,),
        ).fetchall()

    linked = _link_index()
    return [
        {
            "user_id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"] or row["username"],
            "email": row["email"],
            "is_active": bool(row["is_active"]),
            "must_change_password": bool(row["must_change_password"]),
            "role": row["role"],
            "role_label": config.ROLE_LABELS.get(row["role"], row["role"]),
            "linked_to": linked.get((row["username"] or "").lower(), {}).get(row["role"]),
        }
        for row in rows
    ]


def list_grantable_accounts(actor: Actor) -> list[dict[str, Any]]:
    """Platform accounts that do not yet have access to this system."""
    _require_admin(actor)
    from education_system.platform.identity.auth.db import connect

    with _closing(connect()) as conn:
        rows = conn.execute(
            """SELECT u.id, u.username, u.display_name
                 FROM users u
                WHERE u.is_active = 1
                  AND NOT EXISTS (SELECT 1 FROM user_systems us
                                   WHERE us.user_id = u.id AND us.system_key = ?)
                ORDER BY u.username""",
            (SYSTEM_KEY,),
        ).fetchall()
    return [
        {
            "user_id": r["id"],
            "username": r["username"],
            "display_name": r["display_name"] or r["username"],
        }
        for r in rows
    ]


def grant_role(actor: Actor, username: str, role: str) -> dict[str, Any]:
    """Give an existing platform account a role in this system.

    Writes ``user_systems`` directly rather than through the platform's
    ``RoleManager``: that class validates against the school role
    hierarchy, which has no entry for apprentice, employer or end-point
    assessor and would reject three of the five roles outright.
    """
    _require_admin(actor)
    name = _require_username(username)
    granted = _validate_role(role)

    from education_system.platform.identity.auth.db import connect

    with _closing(connect()) as conn:
        user = conn.execute(
            "SELECT id, username FROM users WHERE username = ?", (name,)
        ).fetchone()
        if user is None:
            raise ValidationError(
                f"No platform account named {name!r}. The account has to exist in the "
                "shared login database before it can be given access here."
            )
        existing = conn.execute(
            "SELECT role FROM user_systems WHERE user_id = ? AND system_key = ?",
            (user["id"], SYSTEM_KEY),
        ).fetchone()
        if existing and existing["role"] == granted:
            raise ValidationError(f"{name} already holds the {granted!r} role here")
        if existing:
            conn.execute(
                "UPDATE user_systems SET role = ? WHERE user_id = ? AND system_key = ?",
                (granted, user["id"], SYSTEM_KEY),
            )
            detail = f"role changed from {existing['role']!r} to {granted!r}"
        else:
            conn.execute(
                "INSERT INTO user_systems (user_id, system_key, role) VALUES (?, ?, ?)",
                (user["id"], SYSTEM_KEY, granted),
            )
            detail = f"granted {granted!r}"
        conn.commit()

    compliance_repository.record(
        action="update" if existing else "create", entity="user_access", entity_id=name,
        actor=actor.username, actor_role=actor.role, detail=detail,
        changes=audit.change("role", existing["role"] if existing else None, granted),
    )
    logger.info("Apprenticeships access for %s: %s (by %s)", name, detail, actor.username)
    if granted == config.APPRENTICE:
        # The account may already match an apprentice record; link it to
        # that learner now rather than at its first sign-in.
        from education_system.systems.apprenticeships.services import login_links

        login_links.try_sync_username(name)
    return {"username": name, "role": granted, "detail": detail,
            "needs_link": granted in LINK_TARGETS}


def revoke_access(actor: Actor, username: str) -> None:
    """Take away a login's access to this system.

    The records the login is attached to are untouched: an apprentice
    whose portal account is revoked is still an apprentice, and deleting
    their evidence because somebody lost a laptop would be absurd.
    """
    _require_admin(actor)
    name = _require_username(username)
    if name.lower() == (actor.username or "").lower():
        raise ValidationError(
            "You cannot revoke your own access — ask another administrator, so the "
            "system is never left without one."
        )

    from education_system.platform.identity.auth.db import connect

    with _closing(connect()) as conn:
        user = conn.execute("SELECT id FROM users WHERE username = ?", (name,)).fetchone()
        if user is None:
            raise ValidationError(f"No platform account named {name!r}")
        # Read first, only so the audit entry can say which role went.
        held = conn.execute(
            "SELECT role FROM user_systems WHERE user_id = ? AND system_key = ?",
            (user["id"], SYSTEM_KEY),
        ).fetchone()
        cursor = conn.execute(
            "DELETE FROM user_systems WHERE user_id = ? AND system_key = ?",
            (user["id"], SYSTEM_KEY),
        )
        if cursor.rowcount == 0:
            raise ValidationError(f"{name} does not have access to this system")
        conn.commit()

    compliance_repository.record(
        action="delete", entity="user_access", entity_id=name,
        actor=actor.username, actor_role=actor.role, detail="Apprenticeships access revoked",
        changes=audit.change("role", held["role"] if held else None, None),
    )
    logger.warning("Apprenticeships access revoked for %s by %s", name, actor.username)


def link_candidates(actor: Actor, role: str) -> list[dict[str, Any]]:
    """Records a login of *role* could be attached to.

    Already-linked records are included and marked, because reassigning
    a username from a leaver to their replacement is a normal thing to
    do and hiding the row would make it look impossible.
    """
    _require_admin(actor)
    kind = _validate_role(role)
    if kind == config.APPRENTICE:
        return [
            {"id": s.apprentice.apprentice_id, "label": s.full_name,
             "detail": f"{s.programme_title or 'no programme'} · {s.apprentice.status}",
             "username": s.apprentice.username}
            for s in apprentice_repository.list_summaries()
        ]
    if kind == config.STAFF:
        return [
            {"id": m.staff_id, "label": m.full_name, "detail": m.staff_role,
             "username": m.username}
            for m in staff_repository.list_all(active_only=True)
        ]
    if kind == config.EMPLOYER:
        rows = []
        for employer in employer_repository.list_all():
            for manager in employer_repository.list_managers(
                employer.employer_id, active_only=True
            ):
                rows.append({
                    "id": manager.manager_id, "label": manager.full_name,
                    "detail": f"{employer.name}"
                              + (" · primary contact" if manager.is_primary else ""),
                    "username": manager.username,
                })
        return rows
    return []


def link_to_record(actor: Actor, username: str, role: str, record_id: int) -> str:
    """Attach a login to the record its screens are scoped by.

    Returns a sentence naming what was linked, because "done" is not a
    useful answer when the whole point is which record it landed on.
    """
    _require_admin(actor)
    name = _require_username(username)
    kind = _validate_role(role)
    if kind not in LINK_TARGETS:
        raise ValidationError(
            f"A {config.ROLE_LABELS.get(kind, kind)} login is not scoped to a single "
            "record, so there is nothing to link it to."
        )

    if kind == config.APPRENTICE:
        record = apprentice_repository.get(record_id)
        if record is None:
            raise ValidationError(f"No apprentice with id {record_id}")
        apprentice_repository.update(record_id, {"username": name})
        label, previous = record.full_name, record.username
    elif kind == config.STAFF:
        member = staff_repository.get(record_id)
        if member is None:
            raise ValidationError(f"No staff record with id {record_id}")
        staff_repository.update(record_id, {"username": name})
        label, previous = member.full_name, member.username
    else:
        manager = employer_repository.get_manager(record_id)
        if manager is None:
            raise ValidationError(f"No employer contact with id {record_id}")
        employer_repository.update_manager(record_id, {"username": name})
        label, previous = manager.full_name, manager.username

    compliance_repository.record(
        action="update", entity="user_access", entity_id=name,
        actor=actor.username, actor_role=actor.role,
        detail=f"Linked to {LINK_TARGETS[kind]} {record_id} ({label})",
        # Relinking a record moves it from one login to another; the
        # previous holder is what an auditor needs to see.
        changes=audit.change(f"{LINK_TARGETS[kind]} {record_id} login", previous, name),
    )
    logger.info("Login %s linked to %s %s by %s", name, kind, record_id, actor.username)
    if kind == config.APPRENTICE:
        # The learner-record link follows the login: onto this record's
        # learner, and off the previous login if nothing else holds it.
        from education_system.systems.apprenticeships.services import login_links

        login_links.try_sync_apprentice(record_id, previous_username=previous)
    return f"{name} is now linked to {label}."


# ═════════════════════════════════════════════════════════════════════
# Internals
# ═════════════════════════════════════════════════════════════════════

def _auth() -> Any:
    from education_system.platform.identity.auth.core import UserAuth

    return UserAuth()


def _mfa() -> Any:
    from education_system.platform.identity.auth.mfa_service import MFAService

    return MFAService()


def _guard(action: Any) -> Any:
    """Run a platform auth call, re-raising its refusals as :class:`AccountError`.

    The platform raises its own ``AuthError``/``MFAError``, which the
    interfaces would otherwise have to import and catch alongside this
    system's ``ValidationError``. Narrowing it to one exception here
    keeps ``prompts.run_action`` and ``widgets.guard`` as the only two
    places that know how to report a failure.
    """
    from education_system.platform.identity.auth.exceptions import (
        AuthError,
        MFAError,
    )
    from education_system.platform.identity.auth.exceptions import (
        ValidationError as AuthValidationError,
    )

    try:
        return action()
    except (AuthError, MFAError, AuthValidationError) as exc:
        raise AccountError(str(exc)) from exc


class _closing:
    """``contextlib.closing`` for the platform's raw sqlite3 connections."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def __enter__(self) -> Any:
        return self._conn

    def __exit__(self, *exc_info: Any) -> None:
        self._conn.close()


def _user_row(username: str) -> Any:
    """The shared-auth row for a username, or None.

    Defensive: an auth database that is missing or unreadable must
    degrade to "no account actions available" rather than taking down
    the screen that asked.
    """
    if not (username or "").strip():
        return None
    try:
        from education_system.platform.identity.auth.db import connect

        with _closing(connect()) as conn:
            return conn.execute(
                "SELECT id, username, display_name, email, is_active, must_change_password "
                "FROM users WHERE username = ?",
                (username.strip(),),
            ).fetchone()
    except Exception:
        logger.warning("Could not read the shared auth account for %s", username, exc_info=True)
        return None


def _require_user_id(username: str) -> int:
    row = _user_row(username)
    if row is None:
        raise ValidationError(
            "This session is not backed by an account in the shared login database, "
            "so account changes are not available here."
        )
    return int(row["id"])


def _link_index() -> dict[str, dict[str, str]]:
    """``{username: {role: what it is linked to}}`` across all three record types."""
    index: dict[str, dict[str, str]] = {}

    def add(username: str | None, role: str, label: str) -> None:
        if username and username.strip():
            index.setdefault(username.strip().lower(), {})[role] = label

    for summary in apprentice_repository.list_summaries():
        add(summary.apprentice.username, config.APPRENTICE, summary.full_name)
    for member in staff_repository.list_all():
        add(member.username, config.STAFF, member.full_name)
    for employer in employer_repository.list_all():
        for manager in employer_repository.list_managers(employer.employer_id):
            add(manager.username, config.EMPLOYER, f"{manager.full_name} ({employer.name})")
    return index


def _require_admin(actor: Actor) -> None:
    if not actor.is_admin:
        raise PermissionDenied("Only a provider administrator may manage accounts")


def _require_username(value: Any) -> str:
    name = str(value or "").strip()
    if not name:
        raise ValidationError("A username is required")
    return name


def _validate_role(value: Any) -> str:
    role = str(value or "").strip().lower()
    if role not in config.ROLES:
        allowed = ", ".join(config.ROLES)
        raise ValidationError(f"Role must be one of: {allowed}")
    return role
