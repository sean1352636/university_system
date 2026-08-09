"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthAuthenticationServiceMixin:
    def get_current_user(self):
        """Get the current logged-in user information"""
        return self.current_user

    def check_session(self):
        """Check if current session is valid"""
        return self.session_manager.check_session()

    def update_activity(self):
        """Update last activity timestamp"""
        self.session_manager.update_last_activity()
        self.last_activity = datetime.now()
