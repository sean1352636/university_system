"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthPersistenceUsersMixin:
    def create_user(self, username, password, email=None, first_name=None, last_name=None, role=None, student_id=None, password_reset_required=False):
        """Create a new user: the sign-in account (password, university
        role) in the shared auth, then the university profile. The
        university keeps no copy of the password."""
        if self._shared_auth is None:
            raise AuthenticationError("The sign-in service is not available.",
                                      code="AUTH_SERVICE_UNAVAILABLE")
        from education_system.platform.identity.auth.exceptions import AuthError as SharedAuthError
        display = " ".join(p for p in (first_name, last_name) if p) or username
        try:
            self._shared_auth.create_user(username, password, display_name=display, email=email,
                                          systems=[("university", role or "student")])
        except SharedAuthError as exc:
            if "already exists" not in str(exc):
                raise
            # The person already signs in elsewhere: grant the university role.
            shared_id = self._shared_id_for(username=username)
            if shared_id is None:
                raise
            conn = self._shared_auth._conn()
            try:
                conn.execute("INSERT OR IGNORE INTO user_systems (user_id, system_key, role) "
                             "VALUES (?, 'university', ?)", (shared_id, role or "student"))
                conn.commit()
            finally:
                conn.close()
        return self.user_manager.create_user(
            username, password, email, first_name, last_name, role, student_id, password_reset_required
        )

    def get_user(self, user_id=None, username=None):
        """Get user information by user ID or username"""
        return self.user_manager.get_user(user_id=user_id, username=username)

    def get_user_by_username(self, username):
        """Get user information by username"""
        return self.user_manager.get_user(username=username)

    def get_user_by_id(self, user_id):
        """Get user information by user ID"""
        return self.user_manager.get_user(user_id=user_id)

    def update_user(self, user_id, **kwargs):
        """Update user information"""
        return self.user_manager.update_user(user_id, **kwargs)

    def delete_user(self, user_id):
        """Delete a user account"""
        return self.user_manager.delete_user(user_id)

    def list_users(self, role=None):
        """List all users, optionally filtered by role"""
        return self.user_manager.list_users(role)

    def activate_user(self, user_id):
        """Activate a user account"""
        return self.user_manager.activate_user(user_id)

    def deactivate_user(self, user_id):
        """Deactivate a user account"""
        return self.user_manager.deactivate_user(user_id)
