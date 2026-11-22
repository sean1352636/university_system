"""Extracted backwards-compatible UserAuth methods."""
import logging

logger = logging.getLogger(__name__)

from ...facade_support import *

class AuthCredentialsPasswordsMixin:
    def _hash_password(self, password, salt=None):
        """
        Hash a password with a salt using PBKDF2.

        Uses 1,000,000 iterations as recommended by OWASP for PBKDF2-SHA256.
        """
        if salt is None:
            salt = secrets.token_hex(16)

        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt.encode(),
            1_000_000,  # OWASP recommendation
            dklen=64
        )

        return salt, key.hex()

    def _shared_id_for(self, user_id=None, username=None):
        """The shared auth (auth.db) id for a university user, resolved by
        **username** — the local and shared databases number users
        independently, so a local id is never passed to the shared auth."""
        current = self.current_user or {}
        if current.get('shared_auth_id') is not None and (
                username in (None, current.get('username'))
                and user_id in (None, current.get('id'), current.get('user_id'))):
            return int(current['shared_auth_id'])
        if username is None and user_id is not None:
            try:
                with self.db_manager.get_connection() as conn:
                    row = conn.execute("SELECT username FROM users WHERE id = ?",
                                       (user_id,)).fetchone()
                username = row[0] if row else None
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        if not username:
            return None
        from education_system.platform.identity.auth.mfa.service import MFAService
        return MFAService.resolve_shared_user_id(0, username=username)

    def change_password(self, username, old_password, new_password):
        """Change a user's password in the shared auth (the only password
        store). Raises the shared AuthError for a wrong current password or
        a weak new one."""
        if self._shared_auth is None:
            raise AuthenticationError("The sign-in service is not available.",
                                      code="AUTH_SERVICE_UNAVAILABLE")
        shared_id = self._shared_id_for(username=username)
        if shared_id is None:
            raise AuthenticationError(f"No sign-in account for '{username}'.",
                                      code="ACCOUNT_NOT_FOUND")
        self._shared_auth.change_password(int(shared_id), old_password, new_password)
        return True

    def reset_password(self, username, admin_user_id=None, temporary_password=None):
        """Unlock a user and reset to a forced-change temporary password."""
        # Passwords live only in the shared auth; there is no local copy to
        # reset any more.
        if self._shared_auth is None:
            raise AuthenticationError("The sign-in service is not available.",
                                      code="AUTH_SERVICE_UNAVAILABLE")
        result = self._shared_auth.unlock_and_reset_password(
            username, temporary_password=temporary_password)
        succeeded = result[0] if isinstance(result, tuple) else bool(result)
        if succeeded:
            try:
                self.account_security_manager.reset_login_attempts(username)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        return result
