"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthAuthenticationWebauthnLoginMixin:
    def login_via_webauthn(self, assertion_data):
        """Login via WebAuthn assertion"""
        return self.login_manager.login_via_webauthn(assertion_data)
