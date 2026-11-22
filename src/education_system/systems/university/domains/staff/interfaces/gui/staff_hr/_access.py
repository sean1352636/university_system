"""Staff HR screens asking ``domain/staff_hr/access`` who may see what.

Every Staff HR window holds ``self.auth`` and/or ``self.current_user``;
these helpers take the window and answer from the signed-in person's
username (the Staff HR key — never ``current_user['id']``).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _access():
    from education_system.systems.university.domains.staff.domain.staff_hr import access
    return access


def actor(gui):
    """The signed-in session the window acts for (auth object or user dict)."""
    auth = getattr(gui, 'auth', None)
    if auth is not None and getattr(auth, 'current_user', None):
        return auth
    return getattr(gui, 'current_user', None) or {}


def user_key(gui) -> str:
    """The signed-in person's username."""
    a = _access()
    who = actor(gui)
    return a.username_of(who) or str((a.user_of(who) or {}).get('username') or '')


def can(gui, capability: str) -> bool:
    """May the signed-in person use ``capability`` (see access.CAPABILITIES)?"""
    try:
        return _access().can(actor(gui), capability)
    except Exception:
        logger.warning("Staff HR access check %s failed; hiding it", capability, exc_info=True)
        return False


def approvable(gui, rows, key: str = 'user_id') -> list:
    """The rows (requests) the signed-in person may approve: their reports'
    (anyone's for HR), never their own."""
    a = _access()
    who = actor(gui)
    out = []
    for row in rows or []:
        data = dict(row) if not isinstance(row, dict) else row
        owner = a.staff_key(data.get(key)) or data.get(key)
        if owner and a.can_approve_for(who, str(owner)):
            out.append(row)
    return out


def may_approve(gui, owner) -> bool:
    a = _access()
    key = a.staff_key(owner) or owner
    return bool(key) and a.can_approve_for(actor(gui), str(key))


__all__ = ['actor', 'user_key', 'can', 'approvable', 'may_approve']
