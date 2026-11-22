"""Whose Staff HR record is this, and may the signed-in person touch it?

Shared by the self-service managers (profile, appraisal, training, time,
onboarding, academic). Every person is keyed by username
(:func:`access.staff_key`); a check runs only when the caller passes an
``actor`` (the auth object or user dict), so older callers that pass none keep
working.
"""

from __future__ import annotations

from typing import Any, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access


def key(value: Any, conn=None) -> Optional[str]:
    """The username ``value`` names (a username, ``users.id`` or employee
    number); the text itself when it names nobody known."""
    if value is None:
        return None
    found = access.staff_key(value, conn)
    if found:
        return found
    text = str(value).strip()
    return text or None


def me(actor: Any) -> str:
    """The signed-in username (PermissionError when nobody is)."""
    return access.require_user(actor)['username']


def require_self_or_hr(actor: Any, staff: str, conn=None, what: str = "do this") -> str:
    """The person themselves or HR — line managers are not enough (personal
    files, documents, emergency contacts)."""
    name = me(actor)
    if name == staff or access.is_hr(actor, conn):
        return name
    raise PermissionError(f"Only the person themselves or HR can {what}")


def require_self_or_manager(actor: Any, staff: str, conn=None, what: str = "do this") -> str:
    """The person, anyone above them in the line, or HR."""
    name = me(actor)
    if name == staff or access.can_manage_person(actor, staff, conn):
        return name
    raise PermissionError(f"Only the person, their line manager or HR can {what}")


def require_view(actor: Any, staff: str, conn=None, what: str = "this person's record") -> str:
    access.require_view_person(actor, staff, conn, what)
    return me(actor)


def require_hr(actor: Any, conn=None, what: str = "do this") -> str:
    access.require(actor, 'hr', f"Only HR can {what}", conn)
    return me(actor)


def decider(actor: Any, approver_id: Any, conn) -> dict:
    """Who is deciding: the signed-in ``actor`` when given, else the person
    an older caller named by ``approver_id`` (username, ``users.id`` or
    employee number) with their university role. PermissionError when
    neither names anyone — a decision is never made by nobody."""
    if actor is not None:
        return access.require_user(actor)
    name = access.staff_key(approver_id, conn) if approver_id not in (None, '') else None
    if not name:
        raise PermissionError("Please sign in to make this decision")
    row = conn.execute("SELECT role FROM users WHERE username = ?", (name,)).fetchone()
    return {'username': name, 'role': str((row[0] if row else '') or '').strip().lower()}


def require_approver(actor: Any, approver_id: Any, staff: str, conn,
                     what: str = "decide this request") -> dict:
    """The decider (see :func:`decider`), who must be allowed to approve for
    ``staff`` (:func:`access.can_approve_for`: above them in the line, or
    HR — never themselves)."""
    who = decider(actor, approver_id, conn)
    if not staff or not access.can_approve_for(who, staff, conn):
        raise PermissionError(f"Only their line manager or HR can {what}")
    return who


__all__ = ['key', 'me', 'require_self_or_hr', 'require_self_or_manager', 'require_view',
           'require_hr', 'decider', 'require_approver']
