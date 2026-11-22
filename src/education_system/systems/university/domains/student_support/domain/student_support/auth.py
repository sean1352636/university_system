"""
Authentication and authorization helpers for the Student Support module.

Who may see what lives here, in one place:

* :func:`current_requester` — the signed-in person, resolved by **username**
  (``auth.db`` ids and ``student_records.db`` ids differ, so the session's
  ``id`` is never used to look anyone up);
* :func:`can_view_ticket` / :func:`ticket_scope_sql` — ticket visibility,
  the single gate. The requester always sees their own ticket; everyone else
  by the ticket's team and confidentiality tier (``confidentiality``:
  standard — the team's support staff and admins; restricted — the team, the
  health team for health / wellbeing tickets, admins; safeguarding — the
  safeguarding leads and admins; plus break-glass grants).
* :func:`can_work_ticket` — may act on a ticket as staff (not as requester).
* :func:`can_see_internal` — internal notes and private attachments are for
  the staff working the ticket only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

# Global auth instance
auth = None

# Logger
logger = logging.getLogger(__name__)

# Roles that work support tickets. ``staff`` is the university's support /
# professional-services role; instructors are deliberately not here.
SUPPORT_ROLES = frozenset({'staff', 'support_staff', 'support_agent', 'helpdesk_agent'})
ADMIN_ROLES = frozenset({'admin', 'administrator', 'super_admin', 'superadmin'})


def set_auth(auth_instance):
    """
    Set the authentication instance for the student support module.

    Registers the authentication instance both locally in this module and
    globally so that support operations can access user context for
    authorization and audit logging. Called after the user has logged in.
    """
    global auth
    auth = auth_instance
    try:
        # Imported here: the university auth package costs seconds to load
        # and nothing else in this module needs it.
        from education_system.systems.university.infrastructure.auth import set_auth_instance
        set_auth_instance(auth_instance)
    except ImportError:
        logger.debug("university auth package unavailable; support auth set locally only")
    logger.info("Auth instance set for student support module")


def get_auth_instance():
    """The current authentication instance, or None."""
    return auth


def get_current_user_safe():
    """Current user data, or None if not authenticated (never raises)."""
    if auth and getattr(auth, 'current_user', None):
        return auth.current_user
    return None


def user_of(actor: Any = None) -> Optional[dict]:
    """The ``current_user`` dict for ``actor`` — an auth object, a user dict,
    or None for the module's signed-in session."""
    if actor is None:
        actor = auth
    if actor is None:
        return None
    if isinstance(actor, dict):
        return actor or None
    return getattr(actor, 'current_user', None) or None


def require_auth(actor: Any = None) -> dict:
    """The signed-in user; PermissionError when nobody is signed in."""
    user = user_of(actor)
    if not user or not user.get('username'):
        raise PermissionError("You must be logged in to perform this action")
    return user


def require_role(allowed_roles, actor: Any = None):
    """PermissionError unless the signed-in user has one of ``allowed_roles``."""
    user = require_auth(actor)
    if user.get('role') not in allowed_roles:
        raise PermissionError(f"This action requires one of these roles: {', '.join(allowed_roles)}")


# ── identity ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Requester:
    """The signed-in person as the support tables know them."""
    username: str
    role: str
    users_id: Optional[int]       # student_records.db users.id (None: no local profile)
    student_id: Optional[str]     # student number (None for staff)

    @property
    def is_staff(self) -> bool:
        return self.role in SUPPORT_ROLES or self.role in ADMIN_ROLES


def _lookup(username: str, conn=None):
    if conn is not None:
        row = conn.execute("SELECT id, student_id FROM users WHERE username = ?",
                           (username,)).fetchone()
        return (row[0], row[1]) if row else (None, None)
    from education_system.systems.university.infrastructure.auth.session_user import (
        resolve_local_identity,
    )
    return resolve_local_identity(username)


def current_requester(actor: Any = None, conn=None) -> Requester:
    """The signed-in person, resolved by username (PermissionError if none).

    Pass ``conn`` to resolve on an already-open connection.
    """
    user = require_auth(actor)
    username = str(user['username'])
    users_id, student_id = _lookup(username, conn)
    if student_id is None and user.get('role') == 'student':
        # A student login without a local profile still has a student number
        # on the session (set from the same users row at sign-in).
        student_id = user.get('student_id')
    return Requester(username=username, role=str(user.get('role') or ''),
                     users_id=users_id, student_id=student_id)


def requester_student_id(actor: Any = None, conn=None) -> Optional[str]:
    """The signed-in person's student number (None for staff)."""
    return current_requester(actor, conn).student_id


# ── visibility ───────────────────────────────────────────────────────────


def is_support_staff(actor: Any = None) -> bool:
    """True for the support roles and admins."""
    user = user_of(actor)
    return bool(user) and (user.get('role') in SUPPORT_ROLES or user.get('role') in ADMIN_ROLES)


def is_admin(actor: Any = None) -> bool:
    user = user_of(actor)
    return bool(user) and user.get('role') in ADMIN_ROLES


def can_see_internal(actor: Any = None, ticket=None, conn=None) -> bool:
    """Internal notes and private attachments: the staff working ``ticket``
    (without a ticket: support staff)."""
    if ticket is not None:
        return can_work_ticket(actor, ticket, conn)
    return is_support_staff(actor)


def _get(ticket, key):
    try:
        return ticket[key]
    except (KeyError, IndexError, TypeError):
        return None


def owns_ticket(requester: Requester, ticket) -> bool:
    """True when ``requester`` raised ``ticket`` (a dict or sqlite3.Row)."""
    username = _get(ticket, 'requester_username')
    if username:
        return str(username) == requester.username
    # Rows written before the requester column existed (not yet backfilled):
    # match the student number Student Support stored in student_id/user_id.
    if requester.student_id:
        return requester.student_id in {str(_get(ticket, 'student_id') or ''),
                                        str(_get(ticket, 'user_id') or '')}
    return False


def _tiers():
    # Imported here: confidentiality imports this module.
    from education_system.systems.university.domains.student_support.domain.student_support import (
        confidentiality,
    )
    return confidentiality


def can_view_ticket(actor: Any, ticket, conn=None) -> bool:
    """May ``actor`` see ``ticket`` at all (requester, team, tier, break-glass)?"""
    return _tiers().can_view(actor, ticket, conn)


def can_work_ticket(actor: Any, ticket, conn=None) -> bool:
    """May ``actor`` work ``ticket`` as staff — change status, assign, merge,
    escalate, refer, see internal notes?"""
    return ticket is not None and _tiers().can_work(actor, ticket, conn)


def is_case_worker(actor: Any = None) -> bool:
    """Does ``actor`` work tickets at all (staff queues, break-glass)?"""
    return _tiers().is_case_worker(actor)


def ticket_scope_sql(actor: Any = None, alias: str = '', conn=None) -> tuple[str, list]:
    """``(where_sql, params)`` limiting a ``support_tickets`` query to the
    tickets ``actor`` may see. ``alias`` is the table alias, if any."""
    return _tiers().scope_sql(actor, alias, conn)


# ── kept for existing callers ────────────────────────────────────────────


def check_ticket_ownership(ticket_student_id):
    """True if the signed-in user may access a ticket raised by
    ``ticket_student_id`` (support staff: any ticket)."""
    user = get_current_user_safe()
    if not user:
        return False
    if is_support_staff(user):
        return True
    try:
        return current_requester(user).student_id == ticket_student_id
    except PermissionError:
        return False


def has_staff_permissions():
    """True if the signed-in user is support staff (support roles or admin)."""
    return is_support_staff()
