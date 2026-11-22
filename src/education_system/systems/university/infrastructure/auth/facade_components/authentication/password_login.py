"""Extracted backwards-compatible UserAuth methods."""
import logging

logger = logging.getLogger(__name__)

from ...facade_support import *

class AuthAuthenticationPasswordLoginMixin:
    def login(self, username, password, ip_address=None):
        """
        Authenticate a user with username and password against the shared
        auth database — the only place passwords are kept.

        The university's old ``user_accounts`` table no longer holds
        credentials (migration 2b4d6f8a0c3e), so there is no legacy
        fallback: a rejected password is a rejected password. Returns
        True on success, or ``{'success', 'requires_2fa', 'user_id',
        'username'}`` when a second factor is needed
        (:meth:`complete_two_fa_login` finishes it). Raises
        InvalidCredentialsError / AuthenticationError on failure.
        """
        if self._shared_auth is None:
            raise AuthenticationError(
                "The sign-in service is not available. Please try again later.",
                code="AUTH_SERVICE_UNAVAILABLE",
                details={'username': username},
            )
        from education_system.platform.identity.auth.exceptions import (
            AuthError as SharedAuthError,
        )
        try:
            user_info = self._shared_auth.login(username, password)
        except SharedAuthError as exc:
            if ACTIVITY_LOGGER_AVAILABLE:
                log_login(username, success=False)
            raise InvalidCredentialsError(str(exc) or "Invalid username or password.",
                                          details={'username': username}) from exc
        except Exception as exc:
            logger.error("Shared sign-in failed for '%s': %s", username, exc)
            raise AuthenticationError(
                "An unexpected error occurred during login. Please try again.",
                code="AUTH_UNEXPECTED_ERROR",
                details={'username': username, 'error_type': type(exc).__name__},
            ) from exc

        if user_info.get("mfa_required"):
            return {
                "success": True,
                "requires_2fa": True,
                "user_id": user_info["user_id"],
                "username": user_info["username"],
            }
        self._start_shared_session(user_info, username)
        logger.info("User '%s' logged in via shared auth", username)
        return True

    def _start_shared_session(self, user_info, username):
        """Make ``user_info`` (from the shared auth) the current university
        session: the university role, the local profile looked up by
        username, the local id kept as ``id`` so local references
        (messages, …) still match, and the shared id as ``shared_auth_id``."""
        role = "student"  # default
        for s in user_info.get("systems", []):
            if s["system_key"] == "university":
                role = s["role"]
                break

        permissions = []
        try:
            permissions = self.permission_manager.get_user_permissions(user_info["user_id"])
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        student_id = None
        legacy_user_id = None
        email = user_info.get("email", "")
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, student_id, email FROM users WHERE username = ?",
                    (username,),
                )
                row = cursor.fetchone()
                if row:
                    legacy_user_id = row[0]
                    student_id = row[1]
                    email = row[2] or email
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        effective_id = legacy_user_id or user_info["user_id"]
        user_dict = {
            "id": effective_id,
            "user_id": effective_id,
            "shared_auth_id": user_info["user_id"],
            "username": user_info["username"],
            "display_name": user_info.get("display_name", username),
            "role": role,
            "permissions": permissions,
            "password_reset_required": 0,
            "student_id": student_id,
            "email": email,
            "systems": user_info.get("systems", []),
        }
        self.session_manager.set_current_user(user_dict)
        self.current_user = user_dict
        self.last_activity = datetime.now()
        if ACTIVITY_LOGGER_AVAILABLE:
            set_user(username)
            log_login(username, success=True)
        return user_dict

    def logout(self):
        """
        Log out the current user.

        Delegates to LoginManager for logout logic.
        """
        self.login_manager.logout()

        # Clear session state
        self.current_user = None
        self.last_activity = None

    def is_logged_in(self):
        """Check if a user is currently logged in"""
        return self.current_user is not None
