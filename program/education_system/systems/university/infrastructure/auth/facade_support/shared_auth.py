"""Extracted backwards-compatible UserAuth methods."""
from ..facade_support import *

class AuthFacadeSupportSharedAuthMixin:
    def login_by_method(self, method, **kwargs):
        """Unified login dispatcher for all authentication methods"""
        return self.login_manager.login_by_method(method, **kwargs)
