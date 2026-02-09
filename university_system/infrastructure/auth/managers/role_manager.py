"""
Role Management Module

Handles role operations including creation, updates, deletion, and role-permission associations.

Classes:
    RoleManager: Manages role operations
"""

from typing import Optional, List, Dict
import logging
from datetime import datetime

from university_system.infrastructure.database.db import sqlite3

logger = logging.getLogger(__name__)

__all__ = ['RoleManager', 'ROLES']

ROLES = {
    'admin': 'Administrator with full system access',
    'staff': 'Staff with access to student records and reports',
    'student': 'Student with access to own records only',
    'instructor': 'Instructor with access to assigned modules and student grades',
    'parent': 'Parent with access to their children\'s records'
}


class RoleManager:
    """Manager for role operations."""

    def __init__(self, db_manager, activity_logger, current_user_getter):
        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self.get_current_user = current_user_getter

    def create_role(self, role_name: str, description: str, permissions: Optional[List[str]] = None) -> bool:
        """Create a new role with specified permissions."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to create roles.")
            return False

        if not role_name or not description:
            print("Role name and description are required.")
            return False

        if permissions and not isinstance(permissions, list):
            print("Permissions must be a list.")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
                if cursor.fetchone():
                    print(f"Role '{role_name}' already exists.")
                    return False

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    'INSERT INTO roles (role_name, description, created_at, updated_at) VALUES (?, ?, ?, ?)',
                    (role_name, description, timestamp, timestamp)
                )
                role_id = cursor.lastrowid

                if permissions:
                    for perm in permissions:
                        cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                        perm_data = cursor.fetchone()
                        if perm_data:
                            cursor.execute(
                                'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                (role_id, perm_data[0])
                            )
                        else:
                            print(f"Warning: Permission '{perm}' does not exist and will be skipped.")

                conn.commit()
                self.activity_logger(current_user['username'], f'Role created: {role_name}',
                                   f'Permissions: {", ".join(permissions) if permissions else "None"}',
                                   current_user['id'])
                print(f"Role '{role_name}' created successfully.")
                return True
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def update_role(self, role_id: int, **kwargs) -> bool:
        """Update a role's details."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to update roles.")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT role_name FROM roles WHERE id = ?', (role_id,))
                role_data = cursor.fetchone()
                if not role_data:
                    print("Role not found.")
                    return False

                role_name = role_data[0]
                if role_name in ROLES:
                    print(f"Cannot update default role '{role_name}'.")
                    return False

                if 'role_name' in kwargs:
                    cursor.execute('SELECT id FROM roles WHERE role_name = ? AND id != ?',
                                 (kwargs['role_name'], role_id))
                    if cursor.fetchone():
                        print("Role name already exists.")
                        return False

                update_fields = []
                update_values = []
                for key, value in kwargs.items():
                    if key not in ['id', 'created_at']:
                        update_fields.append(f"{key} = ?")
                        update_values.append(value)

                update_fields.append("updated_at = ?")
                update_values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                update_values.append(role_id)

                cursor.execute(
                    f'UPDATE roles SET {", ".join(update_fields)} WHERE id = ?',
                    update_values
                )
                conn.commit()
                self.activity_logger(current_user['username'], f'Role updated: {role_name}',
                                   f'Fields updated: {", ".join(kwargs.keys())}', current_user['id'])
                print(f"Role '{role_name}' updated successfully.")
                return True
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def delete_role(self, role_id: int) -> bool:
        """Delete a role."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to delete roles.")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT role_name FROM roles WHERE id = ?', (role_id,))
                role_data = cursor.fetchone()
                if not role_data:
                    print("Role not found.")
                    return False

                role_name = role_data[0]
                if role_name in ROLES:
                    print(f"Cannot delete default role '{role_name}'.")
                    return False

                cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', (role_name,))
                if cursor.fetchone()[0] > 0:
                    print(f"Cannot delete role '{role_name}' because it is assigned to users.")
                    return False

                cursor.execute('DELETE FROM role_permissions WHERE role_id = ?', (role_id,))
                cursor.execute('DELETE FROM roles WHERE id = ?', (role_id,))
                conn.commit()
                self.activity_logger(current_user['username'], f'Role deleted: {role_name}',
                                   None, current_user['id'])
                print(f"Role '{role_name}' has been deleted.")
                return True
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def list_roles(self) -> Optional[List[Dict]]:
        """List all roles in the system."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to view roles.")
            return None

        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT id, role_name, description, created_at, updated_at FROM roles ORDER BY role_name')
                roles = [dict(row) for row in cursor.fetchall()]

                for role in roles:
                    cursor.execute('''
                        SELECT p.permission_name
                        FROM permissions p
                        JOIN role_permissions rp ON p.id = rp.permission_id
                        WHERE rp.role_id = ?
                    ''', (role['id'],))
                    role['permissions'] = [row[0] for row in cursor.fetchall()]
                    cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', (role['role_name'],))
                    role['user_count'] = cursor.fetchone()[0]

                return roles
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None

    def get_role(self, role_id: Optional[int] = None, role_name: Optional[str] = None) -> Optional[Dict]:
        """Get information about a specific role."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to view role details.")
            return None

        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if role_id is not None:
                    cursor.execute('SELECT id, role_name, description, created_at, updated_at FROM roles WHERE id = ?',
                                 (role_id,))
                elif role_name is not None:
                    cursor.execute('SELECT id, role_name, description, created_at, updated_at FROM roles WHERE role_name = ?',
                                 (role_name,))
                else:
                    print("Either role_id or role_name must be provided.")
                    return None

                role = cursor.fetchone()
                if role:
                    role_dict = dict(role)
                    cursor.execute('''
                        SELECT p.permission_name
                        FROM permissions p
                        JOIN role_permissions rp ON p.id = rp.permission_id
                        WHERE rp.role_id = ?
                    ''', (role_dict['id'],))
                    role_dict['permissions'] = [row[0] for row in cursor.fetchall()]
                    cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', (role_dict['role_name'],))
                    role_dict['user_count'] = cursor.fetchone()[0]
                    return role_dict
                else:
                    print("Role not found.")
                    return None
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None

    def add_role_permission(self, role_id: int, permission_name: str) -> bool:
        """Add a permission to a role."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to modify role permissions.")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT role_name FROM roles WHERE id = ?', (role_id,))
                role_data = cursor.fetchone()
                if not role_data:
                    print("Role not found.")
                    return False

                role_name = role_data[0]
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (permission_name,))
                permission_data = cursor.fetchone()
                if not permission_data:
                    print(f"Permission '{permission_name}' not found.")
                    return False

                permission_id = permission_data[0]
                cursor.execute(
                    'SELECT id FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                    (role_id, permission_id)
                )
                if cursor.fetchone():
                    print(f"Role '{role_name}' already has permission '{permission_name}'.")
                    return True

                cursor.execute(
                    'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                    (role_id, permission_id)
                )
                conn.commit()
                self.activity_logger(current_user['username'], f'Permission added to role: {permission_name}',
                                   f'Role: {role_name}', current_user['id'])
                print(f"Permission '{permission_name}' added to role '{role_name}'.")
                return True
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def remove_role_permission(self, role_id: int, permission_name: str) -> bool:
        """Remove a permission from a role."""
        current_user = self.get_current_user()
        if not current_user or 'manage_roles' not in current_user.get('permissions', []):
            print("You don't have permission to modify role permissions.")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT role_name FROM roles WHERE id = ?', (role_id,))
                role_data = cursor.fetchone()
                if not role_data:
                    print("Role not found.")
                    return False

                role_name = role_data[0]
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (permission_name,))
                permission_data = cursor.fetchone()
                if not permission_data:
                    print(f"Permission '{permission_name}' not found.")
                    return False

                permission_id = permission_data[0]
                cursor.execute(
                    'DELETE FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                    (role_id, permission_id)
                )
                conn.commit()
                self.activity_logger(current_user['username'], f'Permission removed from role: {permission_name}',
                                   f'Role: {role_name}', current_user['id'])
                print(f"Permission '{permission_name}' removed from role '{role_name}'.")
                return True
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
