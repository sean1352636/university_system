"""Who may see and decide disability and accessibility requests.

Accommodations describe a student's condition, so they follow the health
portal's rules (pastoral/application/health/access):

* the health team, administrators, disability services staff
  (:data:`DISABILITY_ROLES`) and anyone holding an accommodation permission
  (:data:`STAFF_PERMISSIONS`) see every student;
* a student sees only their own — by student number, never the account id;
* anyone else sees nothing.

Deciding a request (approve, deny, renew) needs an approver: a health
administrator, an administrator, disability services staff, or the
approve/manage accommodation permission.

``actor`` is the signed-in auth object (with ``current_user`` and
``check_permission``) or a ``current_user`` dict.
"""

from __future__ import annotations

from education_system.systems.university.domains.health.application.health import access as health_access

STAFF_PERMISSIONS = ("view_accommodations", "manage_accommodations", "approve_accommodations")
DISABILITY_ROLES = ("disability_officer", "disability_adviser", "disability_advisor",
                    "accessibility_officer")
APPROVER_ROLES = ("health_admin",) + health_access.ADMIN_ROLES + DISABILITY_ROLES


def current_user(actor) -> dict | None:
    if isinstance(actor, dict):
        return actor
    user = getattr(actor, "current_user", None) if actor is not None else None
    if callable(user):
        try:
            user = user()
        except Exception:
            user = None
    return user if isinstance(user, dict) else None


def _role(actor) -> str:
    return str((current_user(actor) or {}).get("role") or "").lower()


def has_permission(actor, permission) -> bool:
    checker = getattr(actor, "check_permission", None)
    if callable(checker):
        try:
            return bool(checker(permission))
        except Exception:
            return False
    return permission in ((current_user(actor) or {}).get("permissions") or ())


def who(actor) -> health_access.HealthUser | None:
    return health_access.from_user(current_user(actor))


def own_student_id(actor) -> str | None:
    """The signed-in student's student number (``None`` for staff).

    ``current_user['student_id']`` when the session carries it; otherwise
    the university ``users`` row for the username. The account ``id`` is
    never used: it comes from the shared auth database and is not a student
    number."""
    user = current_user(actor) or {}
    if str(user.get("role") or "").lower() not in ("student", "alumni"):
        return None
    if user.get("student_id"):
        return str(user["student_id"])
    if user.get("username"):
        from education_system.systems.university.infrastructure.auth.session_user import (
            resolve_local_identity,
        )
        _local, student_id = resolve_local_identity(str(user["username"]))
        if student_id:
            return str(student_id)
    return None


def is_staff(actor) -> bool:
    person = who(actor)
    return bool(person and (person.is_clinician or person.role in DISABILITY_ROLES)) or any(
        has_permission(actor, p) for p in STAFF_PERMISSIONS)


def scope(actor) -> str | None:
    """``None`` = every student; a student number = only that one.
    Raises ``PermissionError`` for anyone else."""
    if not current_user(actor):
        raise PermissionError("Sign in to use disability and accessibility services.")
    if is_staff(actor):
        return None
    own = own_student_id(actor)
    if own:
        return own
    raise PermissionError("Disability and accessibility records are for disability services, "
                          "the health team and the student themselves.")


def may_manage(actor) -> bool:
    person = who(actor)
    return bool(person and (person.is_clinician or person.role in DISABILITY_ROLES)) or \
        has_permission(actor, "manage_accommodations")


def may_decide(actor) -> bool:
    return _role(actor) in APPROVER_ROLES or has_permission(actor, "approve_accommodations") \
        or has_permission(actor, "manage_accommodations")


def require_staff(actor) -> None:
    if scope(actor) is not None:
        raise PermissionError("Only disability services and the health team can do this.")


def require_decider(actor) -> None:
    require_staff(actor)
    if not may_decide(actor):
        raise PermissionError("Only a disability adviser, a health administrator or an "
                              "accommodation approver can decide requests.")


def require_student(actor, student_id) -> None:
    """Refuse unless ``actor`` may see ``student_id``'s records."""
    allowed = scope(actor)
    if allowed is not None and str(student_id) != allowed:
        raise PermissionError("That request belongs to another student.")


def username(actor) -> str:
    return str((current_user(actor) or {}).get("username") or "unknown")
