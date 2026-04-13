"""JWT authentication for the Primary School API — delegates to shared auth."""

import functools

from flask import g, jsonify

from education_system.shared.api.auth import (
    generate_token,
    decode_token,
    token_required,
    role_required,
    system_required,
    _create_mfa_token,
)
from education_system.primary_school.infrastructure.auth.role_manager import RoleManager

_role_mgr = RoleManager()


def permission_required(*permissions: str):
    """Require the caller to hold at least one of the given permissions.

    Uses the primary school's :class:`RoleManager` to resolve permissions
    via the role hierarchy, so an ``admin`` automatically inherits every
    permission granted to ``teacher`` and ``teaching_assistant``.

    Usage::

        @permission_required("manage_pupils")
        def create_pupil():
            ...

        @permission_required("view_finance", "manage_finance")
        def get_budget():
            ...
    """
    def decorator(f):
        @functools.wraps(f)
        @token_required
        def decorated(*args, **kwargs):
            role = g.current_user.get("role", "")
            if not any(_role_mgr.has_permission(role, p) for p in permissions):
                return jsonify({
                    "error": "Access denied",
                    "message": f"Requires permission: {', '.join(permissions)}",
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
