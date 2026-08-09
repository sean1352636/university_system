"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthAuthenticationFederatedLoginMixin:
    def login_via_sso(self, sso_identity):
        """Login via SSO identity"""
        return self.login_manager.login_via_sso(sso_identity)
