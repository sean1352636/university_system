"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthAuthenticationBiometricLoginMixin:
    def login_via_biometric(self, biometric_type, template_data):
        """Login via biometric authentication"""
        return self.login_manager.login_via_biometric(biometric_type, template_data)
