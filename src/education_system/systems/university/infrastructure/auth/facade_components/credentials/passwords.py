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

    def change_password(self, username, old_password, new_password):
        """Change user password.

        Tries the shared auth system first (where most users now live),
        then falls back to the legacy university-only ``user_accounts``
        table for accounts that have not yet been migrated.
        """
        # ── Try shared auth first ────────────────────────────────────
        # If the user authenticated via shared auth, a shared_auth_id is set;
        # in that case any error from shared.change_password is the real
        # error and must be propagated rather than masked by the legacy
        # fallback (which would re-verify against a stale legacy hash and
        # report a misleading "current password incorrect").
        if self._shared_auth is not None and self.current_user:
            shared_id = self.current_user.get('shared_auth_id')
            if shared_id is not None:
                from education_system.platform.identity.auth.exceptions import (
                    AuthError as SharedAuthError,
                )
                try:
                    self._shared_auth.change_password(int(shared_id), old_password, new_password)
                    return True
                except SharedAuthError:
                    raise
                except Exception as exc:
                    logger.warning(
                        "Shared change_password unexpected error for user_id=%s: %s",
                        shared_id, exc,
                    )
                    # Unexpected error — fall through to legacy as a best effort
            elif self.current_user.get('id') is not None:
                # No shared_auth_id — user authenticated via legacy path.
                # Try shared opportunistically but treat failure as "not in shared".
                try:
                    self._shared_auth.change_password(int(self.current_user['id']),
                                                      old_password, new_password)
                    return True
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

        # ── Fallback to legacy user_accounts table ───────────────────
        from education_system.systems.university.infrastructure.auth.managers.password_manager import change_user_password
        return change_user_password(self.db_manager, username, old_password, new_password,
                                    current_user=self.current_user)

    def reset_password(self, username, admin_user_id=None, temporary_password=None):
        """Unlock a user and reset to a forced-change temporary password."""
        if self._shared_auth is not None:
            try:
                return self._shared_auth.unlock_and_reset_password(
                    username, temporary_password=temporary_password
                )
            except Exception as exc:
                logger.debug("Shared unlock/reset unavailable for '%s': %s", username, exc)
        from education_system.systems.university.infrastructure.auth.managers.password_manager import reset_user_password
        result = reset_user_password(self.db_manager, username, admin_user=self.current_user)
        succeeded = result[0] if isinstance(result, tuple) else bool(result)
        if succeeded:
            self.account_security_manager.reset_login_attempts(username)
        return result
