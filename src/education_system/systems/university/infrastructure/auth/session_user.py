"""Build the university-side ``current_user`` from a shared-login result.

The shared login (``platform.identity.auth``) authenticates against the central
``auth.db``, whose ``users.id`` is its own id space. The university keeps a
separate ``users`` table in ``student_records.db`` with *different* ids for the
same people — ``admin`` is id 19 centrally and id 1 locally. Handing a central
id to a university-side lookup therefore does not fail loudly; it silently
resolves to a different person, and every permission-gated menu then renders
for whoever happens to hold that id locally.

So the session user is built from the *username*, and its permissions come from
the role the shared login reports — never from a user-id lookup against the
university database.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["resolve_local_identity", "role_permissions", "build_session_user"]


def resolve_local_identity(username: str) -> tuple[Optional[int], Optional[str]]:
    """Return ``(university_user_id, student_id)`` for *username*.

    Both are ``None`` when the user has no row in the university database —
    the caller then falls back to the shared id.
    """
    try:
        from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH

        conn = sqlite3.connect(str(UNIVERSITY_DEFAULT_DB_PATH))
        try:
            row = conn.execute(
                "SELECT id, student_id FROM users WHERE username = ?", (username,)
            ).fetchone()
        finally:
            conn.close()
        if row:
            return row[0], row[1]
    except (sqlite3.Error, OSError, ImportError) as exc:
        logger.debug("Could not resolve local university identity for %r: %s", username, exc)
    return None, None


def role_permissions(role: str, permission_manager: Any = None) -> list[str]:
    """Return the permissions granted to *role*.

    Prefers the university database's ``role_permissions`` table, which is the
    live grant set and a superset of the static defaults for every role. Falls
    back to ``constants.PERMISSIONS`` when the database has nothing for the
    role, so a fresh or unseeded install still gets a working menu.
    """
    if permission_manager is not None:
        try:
            perms = permission_manager.get_role_permissions(role)
            if perms:
                return list(perms)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Role permission lookup failed for %r: %s", role, exc)

    from education_system.systems.university.infrastructure.auth.core_utils.constants import (
        PERMISSIONS,
    )

    fallback = list(PERMISSIONS.get(role, []))
    if not fallback:
        # A role with no grants is not a harmless empty list: every
        # check_permission() call then returns False, and the user is refused
        # from each feature with that feature's own "you don't have
        # permission" wording. Nothing anywhere names the real cause, which
        # makes it look like a dozen unrelated bugs. Say it once, loudly.
        #
        # Known case: auth.db grants 'alumni' for the university system, but
        # 'alumni' is absent from both the role_permissions table and the
        # PERMISSIONS fallback, so those accounts are denied everything.
        logger.warning(
            "Role %r resolved to ZERO permissions (not in the role_permissions "
            "table, and no entry in the PERMISSIONS fallback: %s). Every "
            "permission check for this session will fail and features will "
            "report 'access denied'.",
            role, sorted(PERMISSIONS),
        )
    return fallback


def build_session_user(user_info: dict, role: str, permission_manager: Any = None) -> dict:
    """Build the university ``current_user`` dict for a shared-login session.

    *user_info* is the payload returned by the shared login; *role* is the
    user's university role. ``id``/``user_id`` are the **university-local**
    ids so that in-app lookups resolve to the right person, with the central
    id preserved as ``shared_auth_id``.
    """
    username = user_info.get("username", "")
    local_id, student_id = resolve_local_identity(username)
    effective_id = local_id or user_info.get("user_id")
    if student_id and str(role or "").lower() in ("student", "alumni"):
        # Sign-in is where a login from before automatic linking meets it:
        # link it to the student's platform learner record. Never raises.
        from education_system.platform.cross_system import login_links
        login_links.try_sync_username(username)

    return {
        "id": effective_id,
        "user_id": effective_id,
        "shared_auth_id": user_info.get("user_id"),
        "username": username,
        "display_name": user_info.get("display_name", username),
        "email": user_info.get("email", ""),
        "role": role,
        "permissions": role_permissions(role, permission_manager),
        "password_reset_required": 0,
        "student_id": student_id,
        "systems": user_info.get("systems", []),
    }
