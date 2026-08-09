"""Extracted function implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _bootstrap_auth_from_env():
    user_id = os.environ.get('EDU_AUTH_USER_ID')
    username = os.environ.get('EDU_AUTH_USERNAME')
    if not (user_id or username):
        return
    perms = [p for p in os.environ.get(
        'EDU_AUTH_PERMISSIONS', '').split(',') if p]
    current_user = {
        'id': user_id or None,
        'user_id': user_id or None,
        'username': username or '',
        'role': os.environ.get('EDU_AUTH_ROLE', '') or '',
        'email': os.environ.get('EDU_AUTH_EMAIL', '') or '',
        'permissions': perms,
    }
    try:
        from types import SimpleNamespace

        def _check(perm, _u=current_user):
            return perm in _u['permissions']
        shim = SimpleNamespace(
            current_user=current_user,
            user_role=current_user['role'],
            check_permission=_check,
            is_authenticated=True,
        )
        from education_system.systems.university.infrastructure.auth import (
            set_global_auth,
        )
        set_global_auth(shim)
        try:
            from education_system.systems.university.infrastructure.shared_context import (  # noqa: E501
                set_auth as _shared_set_auth,
            )
            _shared_set_auth(shim)
        except Exception:
            pass
    except Exception:
        pass
