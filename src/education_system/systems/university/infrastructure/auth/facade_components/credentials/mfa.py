"""Extracted backwards-compatible UserAuth methods.

Two-factor authentication lives in the shared auth (``auth.db``), like the
password: these methods take the university user id callers hold, resolve
the shared id **by username** (``_shared_id_for``) and use the platform MFA
service. The university's ``user_accounts`` no longer keeps a TOTP secret.
"""
from ...facade_support import *


class AuthCredentialsMfaMixin:
    def _shared_mfa(self, user_id):
        from education_system.platform.identity.auth.mfa.service import MFAService
        shared_id = self._shared_id_for(user_id=user_id)
        if shared_id is None:
            return None, None
        return MFAService.for_shared_auth(), int(shared_id)

    def _username_for(self, user_id):
        current = self.current_user or {}
        if user_id in (current.get('id'), current.get('user_id')) and current.get('username'):
            return current['username']
        try:
            with self.db_manager.get_connection() as conn:
                row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
            return row[0] if row else None
        except Exception:
            return None

    def is_two_fa_enabled(self, user_id):
        """Is a second factor active for this user (in the shared auth)?"""
        svc, shared_id = self._shared_mfa(user_id)
        if svc is None:
            return False
        try:
            return bool(svc.is_mfa_active(shared_id))
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
            return False

    def enable_two_fa(self, user_id):
        """Set up an authenticator app (TOTP) for a user."""
        svc, shared_id = self._shared_mfa(user_id)
        if svc is None:
            return {'success': False, 'message': "No sign-in account for this user."}
        result = svc.setup_totp(shared_id, self._username_for(user_id) or "")
        if not result.get('success'):
            return {'success': False, 'message': result.get('error') or "2FA could not be set up."}
        return {**result, 'message': "Two-factor authentication is set up.",
                'recovery_codes': result.get('recovery_codes') or []}

    def disable_two_fa(self, user_id):
        """Turn off two-factor authentication for a user."""
        svc, shared_id = self._shared_mfa(user_id)
        if svc is None:
            return {'success': False, 'message': "No sign-in account for this user."}
        result = svc.disable_mfa(shared_id)
        return {**result, 'message': result.get('message') or (
            "Two-factor authentication is off." if result.get('success')
            else result.get('error') or "2FA could not be turned off.")}

    def verify_two_fa_code(self, user_id, code):
        """Check an authenticator code."""
        svc, shared_id = self._shared_mfa(user_id)
        if svc is None:
            return False
        try:
            result = svc.verify_totp(shared_id, code)
        except Exception:
            return False
        return bool(result.get('success')) if isinstance(result, dict) else bool(result)

    def generate_recovery_codes(self, user_id):
        """New recovery codes (old ones stop working)."""
        svc, shared_id = self._shared_mfa(user_id)
        if svc is None:
            return {'success': False, 'message': "No sign-in account for this user."}
        result = svc.generate_recovery_codes(shared_id)
        return {**result, 'recovery_codes': result.get('codes') or [],
                'message': "New recovery codes created." if result.get('success')
                else result.get('error') or "Recovery codes could not be created."}

    def regenerate_recovery_codes(self, user_id):
        return self.generate_recovery_codes(user_id)

    def use_recovery_code(self, user_id, code):
        """Use (and spend) a recovery code."""
        svc, shared_id = self._shared_mfa(user_id)
        if svc is None:
            return False
        try:
            result = svc.verify_recovery_code(shared_id, code)
        except Exception:
            return False
        return bool(result.get('success')) if isinstance(result, dict) else bool(result)

    def get_two_fa_qr_code(self, user_id):
        """The QR code for setting up an authenticator app (sets up TOTP)."""
        result = self.enable_two_fa(user_id)
        return result.get('qr_code') if result.get('success') else None

    def complete_two_fa_login(self, user_id, username, code=None):
        """Finish a sign-in that needed a second factor. ``user_id`` is the
        shared id returned by :meth:`login` with ``requires_2fa``. Older
        callers pass ``(user_id, code)``."""
        if code is None:
            username, code = None, username
        if self._shared_auth is None:
            return False
        from education_system.platform.identity.auth.exceptions import AuthError as SharedAuthError
        try:
            user_info = self._shared_auth.verify_mfa(int(user_id), code)
        except SharedAuthError:
            return False
        self._start_shared_session(user_info, username or user_info.get("username"))
        return True
