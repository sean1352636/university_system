"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthPersistencePermissionsMixin:
    def check_permission(self, permission, raise_exception=False):
        """Check if current user has a specific permission"""
        return self.permission_manager.check_permission(permission, raise_exception)

    def has_permission(self, permission):
        """Check if current user has a specific permission"""
        return self.permission_manager.has_permission(permission)

    def get_user_permissions(self, user_id):
        """Get all permissions for a user"""
        return self.permission_manager.get_user_permissions(user_id)

    def grant_permission(self, user_id, permission_name):
        """Grant a permission to a user"""
        return self.permission_manager.set_user_permission(user_id, permission_name, granted=True)

    def revoke_permission(self, user_id, permission_name):
        """Revoke a permission from a user"""
        return self.permission_manager.set_user_permission(user_id, permission_name, granted=False)

    def set_user_permission(self, user_id, permission_name, granted=True):
        """Set a user permission (grant or revoke)"""
        return self.permission_manager.set_user_permission(user_id, permission_name, granted)

    def remove_user_permission(self, user_id, permission_name):
        """Remove a user permission entirely"""
        return self.permission_manager.remove_user_permission(user_id, permission_name)

    def list_permissions(self):
        """List all available permissions"""
        return self.permission_manager.list_permissions()

    def create_role(self, role_name, description, permissions=None):
        """Create a new role"""
        return self.role_manager.create_role(role_name, description, permissions)

    def delete_role(self, role_id):
        """Delete a role"""
        return self.role_manager.delete_role(role_id)

    def list_roles(self):
        """List all roles"""
        return self.role_manager.list_roles()

    def get_role(self, role_id=None, role_name=None):
        """Get role information by ID or name"""
        return self.role_manager.get_role(role_id=role_id, role_name=role_name)

    def get_role_permissions(self, role_name):
        """Get permissions for a role"""
        role = self.role_manager.get_role(role_name=role_name)
        if role:
            return role.get('permissions', [])
        return []

    def update_role(self, role_id, **kwargs):
        """Update a role"""
        return self.role_manager.update_role(role_id, **kwargs)

    def add_role_permission(self, role_id, permission_name):
        """Add a permission to a role"""
        return self.role_manager.add_role_permission(role_id, permission_name)

    def assign_role_permission(self, role_id, permission_name):
        """Assign a permission to a role (alias for add_role_permission)"""
        return self.role_manager.add_role_permission(role_id, permission_name)

    def remove_role_permission(self, role_id, permission_name):
        """Remove a permission from a role"""
        return self.role_manager.remove_role_permission(role_id, permission_name)
