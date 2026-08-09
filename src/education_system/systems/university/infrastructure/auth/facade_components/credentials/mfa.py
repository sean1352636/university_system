"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthCredentialsMfaMixin:
    def enable_two_fa(self, user_id):
        """Enable two-factor authentication for a user"""
        return self.mfa_manager.enable_two_fa(user_id)

    def disable_two_fa(self, user_id):
        """Disable two-factor authentication for a user"""
        return self.mfa_manager.disable_two_fa(user_id)

    def verify_two_fa_code(self, user_id, code):
        """Verify a two-factor authentication code"""
        return self.mfa_manager.verify_two_fa_code(user_id, code)

    def generate_recovery_codes(self, user_id):
        """Generate recovery codes for two-factor authentication"""
        return self.mfa_manager.generate_recovery_codes(user_id)

    def use_recovery_code(self, user_id, code):
        """Use a recovery code for two-factor authentication"""
        return self.mfa_manager.use_recovery_code(user_id, code)

    def get_two_fa_qr_code(self, user_id):
        """Get QR code for two-factor authentication setup"""
        return self.mfa_manager.get_two_fa_qr_code(user_id)

    def complete_two_fa_login(self, user_id, username, code):
        """Complete two-factor authentication login"""
        return self.login_manager.complete_two_fa_login(user_id, username, code)
