"""
Permission Management Module

Handles permission checking, setting, and management operations for users and roles.

Classes:
    PermissionManager: Manages permission operations
"""

from typing import Optional, List, Dict
import logging
import re
from datetime import datetime

from university_system.infrastructure.database.db import sqlite3

logger = logging.getLogger(__name__)

# Import optional features
try:
    from university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

__all__ = ['PermissionManager']


class PermissionManager:
    """Manager for permission operations."""

    def __init__(self, db_manager, activity_logger, current_user_getter, session_checker):
        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self.get_current_user = current_user_getter
        self.check_session = session_checker

    def check_permission(self, permission: str, raise_exception: bool = False, current_user: dict = None):
        """Check if current user has a specific permission.

        Also checks delegated permissions when the user is acting as a delegate.
        """
        if not current_user:
            current_user = self.get_current_user()
        if not current_user:
            return False

        # Direct permission check
        if permission in current_user.get('permissions', []):
            return True

        # Check delegated permissions when acting as a delegate
        acting_as_delegate_for = current_user.get('acting_as_delegate_for')
        if acting_as_delegate_for:
            return self._check_delegated_permission(
                current_user.get('id'), acting_as_delegate_for, permission
            )

        return False

    def has_permission(self, permission: str, current_user: dict = None) -> bool:
        """Check if user has permission without raising exceptions.

        Also checks delegated permissions when the user is acting as a delegate.
        """
        try:
            if not current_user:
                current_user = self.get_current_user()
            if not current_user or not self.check_session():
                return False

            # Direct permission check
            if permission in current_user.get('permissions', []):
                return True

            # Check delegated permissions
            acting_as_delegate_for = current_user.get('acting_as_delegate_for')
            if acting_as_delegate_for:
                return self._check_delegated_permission(
                    current_user.get('id'), acting_as_delegate_for, permission
                )

            return False
        except Exception:
            return False

    def _check_delegated_permission(self, delegate_user_id: int, target_user_id: int, permission: str) -> bool:
        """Check if delegate has a specific delegated permission for target user.

        Looks up active delegated_access records and checks if the requested
        permission falls within the granted scope.
        """
        try:
            from university_system.infrastructure.auth.delegated_access_scopes import DELEGATION_SCOPES
            import json

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT scope_json FROM delegated_access
                       WHERE delegate_user_id = ? AND grantor_user_id = ?
                       AND is_active = 1
                       AND (expires_at IS NULL OR expires_at > datetime('now'))''',
                    (delegate_user_id, target_user_id)
                )
                rows = cursor.fetchall()

                for (scope_json,) in rows:
                    scope_keys = json.loads(scope_json) if scope_json else []
                    for key in scope_keys:
                        scope = DELEGATION_SCOPES.get(key)
                        if scope and permission in scope.get('permissions', []):
                            return True
            return False
        except Exception as e:
            logger.debug(f"Delegated permission check error: {e}")
            return False

    def get_user_permissions(self, user_id: int) -> List[str]:
        """Get all permissions for a user based on role."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
                user_data = cursor.fetchone()
                if not user_data:
                    return []
                role = user_data[0]
                cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
                role_result = cursor.fetchone()
                if not role_result:
                    return []
                role_id = role_result[0]
                cursor.execute('''
                    SELECT p.permission_name
                    FROM permissions p
                    JOIN role_permissions rp ON p.id = rp.permission_id
                    WHERE rp.role_id = ?
                ''', (role_id,))
                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return []

    def set_user_permission(self, user_id: int, permission_name: str, granted: bool = True) -> bool:
        """Set a custom permission for a user."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to modify user permissions.")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT ua.username FROM user_accounts ua WHERE ua.user_id = ?', (user_id,))
                user_data = cursor.fetchone()
                if not user_data:
                    print("User not found.")
                    return False

                username = user_data[0]
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (permission_name,))
                permission_data = cursor.fetchone()
                if not permission_data:
                    print(f"Permission '{permission_name}' not found.")
                    return False

                permission_id = permission_data[0]
                cursor.execute(
                    'SELECT id FROM user_permissions WHERE user_id = ? AND permission_id = ?',
                    (user_id, permission_id)
                )
                if cursor.fetchone():
                    cursor.execute(
                        'UPDATE user_permissions SET granted = ? WHERE user_id = ? AND permission_id = ?',
                        (1 if granted else 0, user_id, permission_id)
                    )
                else:
                    cursor.execute(
                        'INSERT INTO user_permissions (user_id, permission_id, granted) VALUES (?, ?, ?)',
                        (user_id, permission_id, 1 if granted else 0)
                    )

                conn.commit()
                action = "granted" if granted else "revoked"
                self.activity_logger(current_user['username'], f'Permission {action}: {permission_name}',
                                   f'For user: {username}', current_user['id'])
                print(f"Permission '{permission_name}' has been {action} to user {username}.")
                return True
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def remove_user_permission(self, user_id: int, permission_name: str) -> bool:
        """Remove custom permission from user."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to modify user permissions.")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT ua.username FROM user_accounts ua WHERE ua.user_id = ?', (user_id,))
                user_data = cursor.fetchone()
                if not user_data:
                    print("User not found.")
                    return False

                username = user_data[0]
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (permission_name,))
                permission_data = cursor.fetchone()
                if not permission_data:
                    print(f"Permission '{permission_name}' not found.")
                    return False

                permission_id = permission_data[0]
                cursor.execute(
                    'DELETE FROM user_permissions WHERE user_id = ? AND permission_id = ?',
                    (user_id, permission_id)
                )
                conn.commit()
                self.activity_logger(current_user['username'], f'Custom permission removed: {permission_name}',
                                   f'For user: {username}', current_user['id'])
                print(f"Custom permission '{permission_name}' removed from user {username}.")
                return True
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def list_permissions(self) -> Optional[List[Dict]]:
        """List all permissions."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to view permissions.")
            return None

        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT id, permission_name, description, created_at FROM permissions ORDER BY permission_name')
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None

    def create_permission(self, permission_name: str, description: str) -> bool:
        """Create a new permission."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to create permissions.")
            return False

        if not permission_name or not description:
            print("Permission name and description are required.")
            return False

        if not re.match(r'^[a-z][a-z0-9_]*$', permission_name):
            print("Invalid permission name format.")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (permission_name,))
                if cursor.fetchone():
                    print(f"Permission '{permission_name}' already exists.")
                    return False

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                             (permission_name, description, timestamp))
                conn.commit()
                self.activity_logger(current_user['username'], f'Permission created: {permission_name}',
                                   None, current_user['id'])
                print(f"Permission '{permission_name}' created successfully.")
                return True
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def delete_permission(self, permission_id: int) -> bool:
        """Delete a permission."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to delete permissions.")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT permission_name FROM permissions WHERE id = ?', (permission_id,))
                permission_data = cursor.fetchone()
                if not permission_data:
                    print("Permission not found.")
                    return False

                permission_name = permission_data[0]
                cursor.execute('DELETE FROM permissions WHERE id = ?', (permission_id,))
                conn.commit()
                self.activity_logger(current_user['username'], f'Permission deleted: {permission_name}',
                                   None, current_user['id'])
                print(f"Permission '{permission_name}' has been deleted.")
                return True
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
