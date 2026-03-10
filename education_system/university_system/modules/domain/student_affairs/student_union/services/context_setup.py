from __future__ import annotations

from education_system.university_system.infrastructure.auth import UserAuth

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

def set_auth(auth_obj: UserAuth) -> None:
    """
    Inject the shared authentication instance for this module.

    The ``auth`` object should be a properly initialised instance of
    :class:`refactored.auth.user_authentication.UserAuth`.  This helper
    function allows the application entry point to pass in a single
    authentication object so that all student union functionality can
    reference the same session and permissions.
    """
    # Import union_context directly to avoid circular import
    from education_system.university_system.modules.domain.student_affairs.student_union.services import union_context
    union_context.auth = auth_obj
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_obj)
