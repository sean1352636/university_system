"""Staff HR menus asking ``domain/staff_hr/access`` who may see what.

Menus receive the signed-in username; the session itself comes from the
shared context (set by ``staff_hr_cli.set_auth``).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _access():
    from education_system.systems.university.domains.staff.domain.staff_hr import access
    return access


def actor():
    """The signed-in session (auth object), or None."""
    try:
        from education_system.systems.university.infrastructure.shared_context import get_auth
        auth = get_auth()
    except Exception:
        return None
    return auth if auth is not None and getattr(auth, 'current_user', None) else None


def user_key(auth=None) -> str:
    return _access().username_of(auth if auth is not None else actor()) or ''


def can(capability: str, auth=None) -> bool:
    try:
        return _access().can(auth if auth is not None else actor(), capability)
    except Exception:
        logger.warning("Staff HR access check %s failed; hiding it", capability, exc_info=True)
        return False


def approvable(rows, key: str = 'user_id', auth=None) -> list:
    """The requests the signed-in person may approve (their reports', anyone's
    for HR, never their own)."""
    a = _access()
    who = auth if auth is not None else actor()
    out = []
    for row in rows or []:
        data = row if isinstance(row, dict) else dict(row)
        owner = a.staff_key(data.get(key)) or data.get(key)
        if owner and a.can_approve_for(who, str(owner)):
            out.append(row)
    return out


def may_approve(owner, auth=None) -> bool:
    a = _access()
    key = a.staff_key(owner) or owner
    return bool(key) and a.can_approve_for(auth if auth is not None else actor(), str(key))


__all__ = ['actor', 'user_key', 'can', 'approvable', 'may_approve']
