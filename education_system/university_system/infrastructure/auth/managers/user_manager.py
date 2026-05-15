"""
User Management Module

This module handles CRUD operations for users including creation, updates,
deletion, activation/deactivation, and listing operations.

Classes:
    UserManager: Manages user account operations
"""

from typing import Optional, Dict, List, Any
import logging
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.infrastructure.exceptions import (
    InvalidInputError,
    DatabaseError,
)
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

logger = logging.getLogger(__name__)

# Import optional features
try:
    from education_system.university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

__all__ = ['UserManager', 'ROLES']

# Role definitions
ROLES = {
    'admin': 'Administrator with full system access',
    'staff': 'Staff with access to student records and reports',
    'student': 'Student with access to own records only',
    'instructor': 'Instructor with access to assigned modules and student grades',
    'parent': 'Parent with access to their children\'s records'
}


def _overlay_shared_last_login(users: List[Dict]) -> None:
    """Replace each user's ``last_login`` with the shared-auth value.

    Real logins flow through the shared auth DB, which has its own
    ``users`` table with its own ``last_login`` column. The legacy
    ``user_accounts.last_login`` column in the university DB is never
    written, so without this overlay every row reads ``None``.

    Mutates the supplied dicts in place; silently leaves them unchanged
    if shared auth is unavailable.
    """
    if not users:
        return
    try:
        from education_system.shared.auth.db import connect as _shared_connect
    except Exception:
        return
    usernames = [u.get('username') for u in users if u.get('username')]
    if not usernames:
        return
    try:
        with _shared_connect() as conn:
            placeholders = ",".join("?" for _ in usernames)
            rows = conn.execute(
                f"SELECT username, last_login FROM users "
                f"WHERE username IN ({placeholders})",  # nosec B608
                usernames,
            ).fetchall()
    except Exception as exc:
        logger.debug("Shared last_login overlay skipped: %s", exc)
        return
    by_username = {r["username"]: r["last_login"] for r in rows}
    for u in users:
        ll = by_username.get(u.get('username'))
        if ll is not None:
            u['last_login'] = ll


class UserManager:
    """
    Manager for user CRUD operations.

    This class handles creating, updating, deleting, and listing users,
    as well as account activation/deactivation.

    Attributes:
        db_manager: Database manager instance for data operations
        activity_logger: Activity logger for audit trails
        password_hasher: Function to hash passwords
        username_validator: Function to validate username format
        password_validator: Function to validate password strength
        email_validator: Function to validate email format
        current_user: Current logged-in user information
    """

    def __init__(self, db_manager, activity_logger, password_hasher,
                 username_validator, password_validator, email_validator,
                 current_user_getter):
        """
        Initialize the UserManager.

        Parameters:
            db_manager: Database manager instance
            activity_logger: Activity logger instance
            password_hasher: Function to hash passwords (salt, hash) tuple
            username_validator: Function to validate usernames
            password_validator: Function to validate passwords
            email_validator: Function to validate email addresses
            current_user_getter: Function to get current user info
        """
        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self.password_hasher = password_hasher
        self.username_validator = username_validator
        self.password_validator = password_validator
        self.email_validator = email_validator
        self.get_current_user = current_user_getter

    def create_user(self, username: str, password: str, email: str, first_name: str,
                    last_name: str, role: str, student_id: Optional[str] = None,
                    password_reset_required: bool = False) -> bool:
        """
        Create a new user with improved duplicate checking.

        Parameters:
            username: Username for the new account
            password: Password for the account
            email: Email address
            first_name: User's first name
            last_name: User's last name
            role: User role (must be in ROLES dictionary)
            student_id: Optional student ID (for student role)
            password_reset_required: Whether password reset is required on first login

        Returns:
            bool: True if user created successfully, False otherwise

        Raises:
            InvalidInputError: If validation fails for any input
            DatabaseError: If database operation fails

        Notes:
            - Validates username, password, email, and role
            - Checks for duplicate username and email
            - For student role, validates student_id exists
            - Logs activity after creation
        """
        # Validate inputs
        if not self.username_validator(username):
            raise InvalidInputError(
                "Invalid username format. Username must be 3-20 characters and contain only letters, numbers, underscores, or hyphens.",
                code="INVALID_USERNAME",
                details={'username': username}
            )

        if not self.password_validator(password):
            raise InvalidInputError(
                "Invalid password. Password must be at least 8 characters long and contain both letters and numbers.",
                code="INVALID_PASSWORD"
            )

        if not self.email_validator(email):
            raise InvalidInputError(
                "Invalid email format.",
                code="INVALID_EMAIL",
                details={'email': email}
            )

        if role not in ROLES:
            raise InvalidInputError(
                f"Invalid role. Valid roles are: {', '.join(ROLES.keys())}",
                code="INVALID_ROLE",
                details={'role': role, 'valid_roles': list(ROLES.keys())}
            )

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check for duplicates
                cursor.execute('SELECT id FROM user_accounts WHERE username = ?', (username,))
                if cursor.fetchone():
                    if not hasattr(self, '_initialization_mode'):
                        print("Username already exists.")
                    return False

                cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
                if cursor.fetchone():
                    if not hasattr(self, '_initialization_mode'):
                        print("Email already exists.")
                    return False

                # Validate student_id if provided
                if role == 'student' and student_id:
                    cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                    if not cursor.fetchone():
                        print(f"Student ID {student_id} does not exist in the system.")
                        return False

                # Hash password
                salt, password_hash = self.password_hasher(password)

                # Create user
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''INSERT INTO users
                       (username, first_name, last_name, email, role, student_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (username, first_name, last_name, email, role, student_id, timestamp, timestamp)
                )
                user_id = cursor.lastrowid

                # Create account
                cursor.execute(
                    '''INSERT INTO user_accounts
                       (username, password_hash, salt, user_id, created_at, updated_at, password_reset_required)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (username, password_hash, salt, user_id, timestamp, timestamp, 1 if password_reset_required else 0)
                )

                conn.commit()

            # Log activity
            if not hasattr(self, '_initialization_mode'):
                self.activity_logger('system', f'User created: {username}', f'Role: {role}')
                if IMMUTABLE_AUDIT_AVAILABLE:
                    current_user = self.get_current_user()
                    admin_id = str(current_user['id']) if current_user else 'system'
                    safe_log_security_event(
                        action=AuditAction.USER_CREATE,
                        user_id=admin_id,
                        resource_type='user',
                        resource_id=str(user_id),
                        details={'new_username': username, 'role': role}
                    )
                print(f"User {username} created successfully with role {role}.")
            return True

        except sqlite3.Error as e:
            if not hasattr(self, '_initialization_mode'):
                logger.error(f"Database error: {e}")
            return False

    def update_user(self, user_id: int, **kwargs) -> bool:
        """
        Update user information.

        Parameters:
            user_id: ID of user to update
            **kwargs: Fields to update (username, email, role, first_name, last_name, etc.)

        Returns:
            bool: True if update successful, False otherwise

        Notes:
            - Requires 'manage_users' permission or updating own account
            - Validates username and email uniqueness
            - Validates role if provided
            - Updates users and user_accounts tables as needed
        """
        current_user = self.get_current_user()
        if not current_user:
            print("You must be logged in to update user information.")
            return False

        # Permission check
        if current_user['id'] != user_id and 'manage_users' not in current_user.get('permissions', []):
            print("You don't have permission to update other users.")
            return False

        # Validate inputs
        if 'username' in kwargs and not self.username_validator(kwargs['username']):
            print("Invalid username format.")
            return False

        if 'email' in kwargs and not self.email_validator(kwargs['email']):
            print("Invalid email format.")
            return False

        if 'role' in kwargs and kwargs['role'] not in ROLES:
            print(f"Invalid role. Valid roles are: {', '.join(ROLES.keys())}")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get user info
                cursor.execute('''
                    SELECT u.id, ua.username
                    FROM users u
                    JOIN user_accounts ua ON u.id = ua.user_id
                    WHERE u.id = ?
                ''', (user_id,))

                user_data = cursor.fetchone()
                if not user_data:
                    print("User not found.")
                    return False

                _, username = user_data

                # Check uniqueness
                if 'username' in kwargs:
                    cursor.execute('SELECT id FROM user_accounts WHERE username = ? AND user_id != ?',
                                 (kwargs['username'], user_id))
                    if cursor.fetchone():
                        print("Username already exists.")
                        return False

                if 'email' in kwargs:
                    cursor.execute('SELECT id FROM users WHERE email = ? AND id != ?',
                                 (kwargs['email'], user_id))
                    if cursor.fetchone():
                        print("Email already exists.")
                        return False

                # Separate updates for users vs user_accounts tables
                user_updates = {}
                account_updates = {}

                user_fields = ['first_name', 'last_name', 'email', 'role', 'student_id']
                account_fields = ['username', 'is_active']

                for key, value in kwargs.items():
                    if key in user_fields:
                        user_updates[key] = value
                    elif key in account_fields:
                        account_updates[key] = value

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Update users table
                if user_updates:
                    update_fields = [validate_identifier(key, "column") + " = ?" for key in user_updates.keys()]
                    update_fields.append("updated_at = ?")
                    update_values = list(user_updates.values()) + [timestamp, user_id]

                    cursor.execute(
                        'UPDATE users SET ' + ", ".join(update_fields) + ' WHERE id = ?',
                        update_values
                    )

                # Update user_accounts table
                if account_updates:
                    update_fields = [validate_identifier(key, "column") + " = ?" for key in account_updates.keys()]
                    update_fields.append("updated_at = ?")
                    update_values = list(account_updates.values()) + [timestamp, user_id]

                    cursor.execute(
                        'UPDATE user_accounts SET ' + ", ".join(update_fields) + ' WHERE user_id = ?',
                        update_values
                    )

                conn.commit()

            # Log activity
            self.activity_logger(
                current_user['username'],
                f'User updated: {username}',
                f'Fields updated: {", ".join(kwargs.keys())}',
                current_user['id']
            )

            print(f"User {username} updated successfully.")
            return True

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def activate_user(self, user_id: int) -> bool:
        """Activate a user account."""
        current_user = self.get_current_user()
        if not current_user or 'manage_users' not in current_user.get('permissions', []):
            print("You don't have permission to activate users.")
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

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    'UPDATE user_accounts SET is_active = 1, updated_at = ? WHERE user_id = ?',
                    (timestamp, user_id)
                )

                conn.commit()

            self.activity_logger(current_user['username'], f'User activated: {username}', None, current_user['id'])
            print(f"User {username} has been activated.")
            return True

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user account."""
        current_user = self.get_current_user()
        if not current_user or 'manage_users' not in current_user.get('permissions', []):
            print("You don't have permission to deactivate users.")
            return False

        if current_user['id'] == user_id:
            print("You cannot deactivate your own account.")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT u.id, ua.username, u.role
                    FROM users u
                    JOIN user_accounts ua ON u.id = ua.user_id
                    WHERE u.id = ?
                ''', (user_id,))

                user_data = cursor.fetchone()
                if not user_data:
                    print("User not found.")
                    return False

                _, username, role = user_data

                # Prevent deactivating last admin
                if role == 'admin':
                    cursor.execute('''
                        SELECT COUNT(*)
                        FROM users u
                        JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE u.role = ? AND ua.is_active = 1
                    ''', ('admin',))

                    if cursor.fetchone()[0] <= 1:
                        print("Cannot deactivate the last active admin user.")
                        return False

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    'UPDATE user_accounts SET is_active = 0, updated_at = ? WHERE user_id = ?',
                    (timestamp, user_id)
                )

                conn.commit()

            self.activity_logger(current_user['username'], f'User deactivated: {username}', None, current_user['id'])

            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.USER_DISABLE,
                    user_id=str(current_user['id']),
                    resource_type='user',
                    resource_id=str(user_id),
                    details={'target_username': username, 'target_role': role}
                )

            print(f"User {username} has been deactivated.")
            return True

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def delete_user(self, user_id: int) -> bool:
        """Delete a user from the system."""
        current_user = self.get_current_user()
        if not current_user:
            print("You don't have permission to delete users.")
            return False
        is_admin = current_user.get('role', '').lower() == 'admin'
        has_perm = 'manage_users' in current_user.get('permissions', [])
        if not is_admin and not has_perm:
            print("You don't have permission to delete users.")
            return False

        if current_user['id'] == user_id:
            print("You cannot delete your own account.")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Use LEFT JOIN so users without a user_accounts row are still found
                cursor.execute('''
                    SELECT u.id, COALESCE(ua.username, u.student_id, CAST(u.id AS TEXT)), u.role
                    FROM users u
                    LEFT JOIN user_accounts ua ON u.id = ua.user_id
                    WHERE u.id = ?
                ''', (user_id,))

                user_data = cursor.fetchone()
                if not user_data:
                    # User not in legacy DB — try shared auth as fallback
                    try:
                        from education_system.shared.auth.core import UserAuth as SharedAuth
                        shared = SharedAuth()
                        shared_user = shared.get_user_by_id(user_id)
                        if shared_user:
                            shared_conn = shared._conn()
                            try:
                                shared_conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                                shared_conn.execute("DELETE FROM user_systems WHERE user_id = ?", (user_id,))
                                shared_conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                                shared_conn.commit()
                            finally:
                                shared_conn.close()
                            return True
                    except Exception:
                        pass
                    return False

                _, username, role = user_data

                # Prevent deleting last admin
                if role == 'admin':
                    cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', ('admin',))
                    if cursor.fetchone()[0] <= 1:
                        print("Cannot delete the last admin user.")
                        return False

                # Disable FK constraints while cleaning up user data
                cursor.execute("PRAGMA foreign_keys = OFF")

                # Delete from all known user-related tables
                fk_tables = [
                    'two_fa_recovery_codes', 'mfa_recovery_codes',
                    'mfa_methods', 'mfa_otp_codes', 'mfa_trusted_devices',
                    'mfa_user_settings', 'mfa_verification_log', 'mfa_secrets',
                    'user_permissions', 'sessions', 'user_accounts',
                    'activity_log', 'login_history',
                ]
                for table in fk_tables:
                    try:
                        cursor.execute(f'DELETE FROM [{table}] WHERE user_id = ?', (user_id,))
                    except sqlite3.OperationalError:
                        pass  # Table may not exist

                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                cursor.execute("PRAGMA foreign_keys = ON")

                conn.commit()

            self.activity_logger(current_user['username'], f'User deleted: {username}', None, current_user['id'])

            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.USER_DELETE,
                    user_id=str(current_user['id']),
                    resource_type='user',
                    resource_id=str(user_id),
                    details={'deleted_username': username, 'deleted_role': role}
                )

            print(f"User {username} has been deleted.")
            return True

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def list_users(self, role=None) -> Optional[List[Dict]]:
        """List all users in the system, optionally filtered by role."""
        current_user = self.get_current_user()
        if not current_user or 'manage_users' not in current_user.get('permissions', []):
            print("You don't have permission to view all users.")
            return None

        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if role:
                    cursor.execute('''
                        SELECT u.id, ua.username, u.email, u.first_name, u.last_name, u.role,
                               ua.is_active, ua.last_login, u.created_at, u.student_id, ua.two_fa_enabled
                        FROM users u
                        JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE u.role = ?
                        ORDER BY u.role, ua.username
                    ''', (role,))
                else:
                    cursor.execute('''
                        SELECT u.id, ua.username, u.email, u.first_name, u.last_name, u.role,
                               ua.is_active, ua.last_login, u.created_at, u.student_id, ua.two_fa_enabled
                        FROM users u
                        JOIN user_accounts ua ON u.id = ua.user_id
                        ORDER BY u.role, ua.username
                    ''')

                users = [dict(row) for row in cursor.fetchall()]

                # Overlay last_login from the shared auth DB. The legacy
                # ``user_accounts.last_login`` column is never updated
                # because real logins flow through the shared auth
                # system, so without this it always reads ``None``.
                _overlay_shared_last_login(users)
                return users

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None

    def get_user(self, user_id: Optional[int] = None, username: Optional[str] = None) -> Optional[Dict]:
        """Get information about a specific user."""
        current_user = self.get_current_user()
        if not current_user:
            print("You must be logged in to view user information.")
            return None

        # Permission check
        if (user_id is not None and user_id != current_user['id']) or \
           (username is not None and username != current_user['username']):
            if 'manage_users' not in current_user.get('permissions', []):
                print("You don't have permission to view other users.")
                return None

        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if user_id is not None:
                    cursor.execute('''
                        SELECT u.id, ua.username, u.email, u.first_name, u.last_name, u.role,
                               ua.is_active, ua.last_login, u.created_at, u.updated_at, u.student_id,
                               ua.two_fa_enabled
                        FROM users u
                        JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE u.id = ?
                    ''', (user_id,))
                elif username is not None:
                    cursor.execute('''
                        SELECT u.id, ua.username, u.email, u.first_name, u.last_name, u.role,
                               ua.is_active, ua.last_login, u.created_at, u.updated_at, u.student_id,
                               ua.two_fa_enabled
                        FROM users u
                        JOIN user_accounts ua ON u.id = ua.user_id
                        WHERE ua.username = ?
                    ''', (username,))
                else:
                    print("Either user_id or username must be provided.")
                    return None

                user = cursor.fetchone()

                if user:
                    user_dict = dict(user)
                    _overlay_shared_last_login([user_dict])
                    return user_dict
                else:
                    print("User not found.")
                    return None

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None
