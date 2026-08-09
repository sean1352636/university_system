"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthAuthenticationPasswordLoginMixin:
    def login(self, username, password, ip_address=None):
        """
        Authenticate a user with username and password.

        Tries the shared auth database first (unified credentials across all
        education systems), then falls back to the legacy university-only
        ``user_accounts`` table for accounts that have not yet been migrated.
        """
        # ── Try shared auth first ────────────────────────────────────
        if self._shared_auth is not None:
            try:
                from education_system.platform.identity.auth.exceptions import (
                    AuthError as SharedAuthError,
                )
                user_info = self._shared_auth.login(username, password)

                # Shared auth succeeded — check MFA
                if user_info.get("mfa_required"):
                    return {
                        "success": True,
                        "requires_2fa": True,
                        "user_id": user_info["user_id"],
                        "username": user_info["username"],
                    }

                # Extract the university role from the systems list
                role = "student"  # default
                for s in user_info.get("systems", []):
                    if s["system_key"] == "university":
                        role = s["role"]
                        break

                # Build the current_user dict in the university format
                # (includes both 'id' and 'user_id' for backward compat)
                permissions = []
                try:
                    permissions = self.permission_manager.get_user_permissions(
                        user_info["user_id"]
                    )
                except Exception:
                    pass

                # Look up university-specific profile data
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
                    pass

                # Use legacy user ID if available so that existing
                # database references (messages, etc.) still match.
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

                # Log the successful login
                if ACTIVITY_LOGGER_AVAILABLE:
                    set_user(username)
                    log_login(username, success=True)

                logger.info("User '%s' logged in via shared auth", username)
                return True
            except SharedAuthError:
                # Shared auth rejected — fall through to legacy auth
                pass
            except Exception as exc:
                logger.debug("Shared auth failed for '%s': %s", username, exc)

        # ── Fall back to legacy university auth ──────────────────────
        # NOTE: login_manager.login() RAISES (InvalidCredentialsError /
        # AuthenticationError / DatabaseError) on bad credentials — it does not
        # return False. Do not wrap it in try/except; the GUI relies on those
        # exceptions. On success it returns True, 'password_reset_required', or
        # the 2FA dict — all three mean the password was verified.
        result = self.login_manager.login(username, password)

        # Update session state if login successful
        if result is True or result == 'password_reset_required':
            # _complete_login already set current_user in session_manager
            self.current_user = self.session_manager.current_user
            self.last_activity = datetime.now()
        elif isinstance(result, dict) and result.get('success'):
            self.last_activity = datetime.now()

        # Self-migrate this legacy account into the shared bcrypt auth so that
        # the next and all subsequent logins use the fast shared path instead of
        # the ~3s PBKDF2 (1,000,000-iteration) verification. We have the verified
        # plaintext password in hand, so we re-hash with bcrypt — robust to the
        # inconsistent PBKDF2 params across creation sites.
        password_verified = (
            result is True
            or result == 'password_reset_required'
            or (isinstance(result, dict) and result.get('success'))
        )
        if password_verified:
            self._migrate_legacy_to_shared(username, password, result)

        return result

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
