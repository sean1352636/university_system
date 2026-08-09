"""Extracted ChurchManagementSystem behaviour."""
from .. import *

class ChurchServicesUserContextMixin:
    def get_user_display_name(self):
        """Get display name for current user."""
        if self.current_user:
            name = self.current_user.get('name') or self.current_user.get('full_name')
            if not name:
                first = self.current_user.get('first_name', '')
                last = self.current_user.get('last_name', '')
                name = f"{first} {last}".strip()
            return name or self.current_user.get('username', 'User')
        return 'Guest'

    def get_user_email(self):
        """Get email for current user."""
        if self.current_user:
            return self.current_user.get('email', '')
        return ''


def get_current_user():
    """Get the current authenticated user from the system."""
    try:
        from education_system.systems.university.infrastructure.shared_context import get_current_user as get_user
        user = get_user()
        if user:
            return user
    except ImportError:
        pass
    return None
