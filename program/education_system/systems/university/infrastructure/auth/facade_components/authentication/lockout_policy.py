"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthAuthenticationLockoutPolicyMixin:
    def lock_account(self, user_id):
        """Lock a user account"""
        # Deactivate the user account as a lock mechanism
        return self.user_manager.deactivate_user(user_id)

    def unlock_account(self, user_id):
        """Unlock a user account"""
        return self.user_manager.activate_user(user_id)

    def emergency_unlock(self, username, emergency_password):
        """Emergency unlock a locked account"""
        return self.account_security_manager.emergency_unlock(username, emergency_password)

    def is_account_locked(self, username):
        """Check if an account is locked"""
        remaining = self.account_security_manager.get_remaining_login_attempts(username)
        return remaining <= 0

    def get_failed_login_attempts(self, username):
        """Get number of remaining login attempts"""
        return self.account_security_manager.get_remaining_login_attempts(username)

    def get_remaining_login_attempts(self, username):
        """Get number of remaining login attempts"""
        return self.account_security_manager.get_remaining_login_attempts(username)

    def clear_failed_attempts(self, username):
        """Clear failed login attempts for a user"""
        return self.account_security_manager.reset_login_attempts(username)
