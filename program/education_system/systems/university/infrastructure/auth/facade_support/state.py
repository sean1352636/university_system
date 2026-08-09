"""Extracted backwards-compatible UserAuth methods."""
from ..facade_support import *

class AuthFacadeSupportStateMixin:
    @property
    def current_user(self):
        """Get current logged-in user from session manager"""
        return self.session_manager.current_user if hasattr(self, 'session_manager') else None

    @current_user.setter
    def current_user(self, value):
        """Set current user in session manager"""
        if hasattr(self, 'session_manager'):
            self.session_manager.current_user = value
        else:
            # During initialization, store in instance
            self.__dict__['current_user'] = value

    @property
    def last_activity(self):
        """Get last activity timestamp from session manager"""
        return self.session_manager.last_activity if hasattr(self, 'session_manager') else None

    @last_activity.setter
    def last_activity(self, value):
        """Set last activity in session manager"""
        if hasattr(self, 'session_manager'):
            self.session_manager.last_activity = value
        else:
            # During initialization, store in instance
            self.__dict__['last_activity'] = value
