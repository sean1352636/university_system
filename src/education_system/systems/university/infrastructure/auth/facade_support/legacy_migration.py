"""Extracted backwards-compatible UserAuth methods."""
import logging

logger = logging.getLogger(__name__)

from ..facade_support import *

class AuthFacadeSupportLegacyMigrationMixin:
    def _migrate_legacy_to_shared(self, username, password, result):
        """Best-effort: provision a shared bcrypt account after a verified legacy
        login so subsequent logins skip the slow PBKDF2 path.

        A failure here must never affect the login outcome, so the whole body is
        swallowed at debug level.
        """
        if self._shared_auth is None:
            return
        try:
            role = None
            display_name = username
            email = ""

            # For the True / 'password_reset_required' results, _complete_login
            # has populated session_manager.current_user. For the 2FA dict it
            # has not, so read role/email straight from the university DB.
            current = getattr(self.session_manager, "current_user", None)
            if isinstance(result, dict):
                try:
                    with self.db_manager.get_connection() as conn:
                        row = conn.execute(
                            "SELECT role, email FROM users WHERE username = ?",
                            (username,),
                        ).fetchone()
                        if row:
                            role = row[0]
                            email = row[1] or ""
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)
            elif current:
                role = current.get("role")
                display_name = current.get("display_name") or username
                email = current.get("email") or ""

            systems = [("university", role or "student")]
            self._shared_auth.provision_user(
                username, password,
                display_name=display_name, email=email, systems=systems,
            )

            # Carry over any university TOTP secret so the shared login still
            # challenges for MFA. Separate try/except so an MFA-sync failure
            # doesn't undo a successful password provision.
            try:
                from education_system.launcher.auth import sync_university_mfa_to_shared
                sync_university_mfa_to_shared()
            except Exception as exc:
                logger.debug("MFA sync after migration failed for '%s': %s", username, exc)

            logger.info("Migrated '%s' to shared bcrypt auth", username)
        except Exception as exc:
            logger.debug("legacy→shared migration failed for '%s': %s", username, exc)
