"""
User Management Module

This module handles CRUD operations for users including creation, updates,
deletion, activation/deactivation, and listing operations.

Classes:
    UserManager: Manages user account operations
"""

from typing import Optional, Dict, List, Any
import os
import secrets
import string
import logging
from datetime import datetime

from university_system.infrastructure.database.db import sqlite3
from university_system.infrastructure.exceptions import (
    InvalidInputError,
    DatabaseError,
)
from university_system.modules.shared.constants import defaults

logger = logging.getLogger(__name__)

# Import optional features
try:
    from university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from university_system.infrastructure.security.immutable_audit_log import AuditAction
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

    def _create_default_accounts_if_needed(self, cursor, conn, target_usernames: Optional[set] = None):
        """
        Ensure baseline system accounts exist, creating them when missing.

        Creates default admin, staff, and student accounts if they don't exist.
        Uses environment variables for passwords in production.

        Parameters:
            cursor: Database cursor
            conn: Database connection
            target_usernames: Optional set of specific usernames to create

        Side Effects:
            - Creates default user accounts if missing
            - Fixes role inconsistencies in existing accounts
            - Prints warnings for dev passwords
            - Prints success messages for created accounts

        Security:
            - Reads passwords from environment variables
            - Falls back to dev passwords with warnings
            - Logs warnings for insecure defaults
        """
        def generate_secure_password(length=16):
            """Generate a cryptographically secure random password."""
            alphabet = string.ascii_letters + string.digits + string.punctuation
            return ''.join(secrets.choice(alphabet) for _ in range(length))

        # Get passwords from environment variables or use simple defaults for development
        admin_password = os.getenv('DEFAULT_ADMIN_PASSWORD') or os.getenv('INITIAL_ADMIN_PASSWORD')
        if not admin_password:
            admin_password = 'admin123'
            logging.warning(
                "SECURITY WARNING: No DEFAULT_ADMIN_PASSWORD environment variable set. "
                "Using default password for development. NEVER use this in production!"
            )
            print("⚠️  Admin account using default dev password (set DEFAULT_ADMIN_PASSWORD in production)")

        staff_password = os.getenv('DEFAULT_STAFF_PASSWORD') or os.getenv('INITIAL_STAFF_PASSWORD')
        if not staff_password:
            staff_password = 'staff123'
            logging.info("Using default password for staff account (development only)")
            print("⚠️  Staff account using default dev password (set DEFAULT_STAFF_PASSWORD in production)")

        student_password = os.getenv('DEFAULT_STUDENT_PASSWORD') or os.getenv('INITIAL_STUDENT_PASSWORD')
        if not student_password:
            student_password = 'student123'
            logging.info("Using default password for student account (development only)")
            print("⚠️  Student account using default dev password (set DEFAULT_STUDENT_PASSWORD in production)")

        default_accounts = [
            {
                'username': 'admin',
                'password': admin_password,
                'role': 'admin',
                'email': 'admin@example.com',
                'first_name': 'System',
                'last_name': 'Administrator',
                'student_id': None,
            },
            {
                'username': 'staff',
                'password': staff_password,
                'role': 'staff',
                'email': 'staff@example.com',
                'first_name': 'Staff',
                'last_name': 'User',
                'student_id': None,
            },
            {
                'username': defaults.DEFAULT_STUDENT_USERNAME,
                'password': student_password,
                'role': 'student',
                'email': 'student@example.com',
                'first_name': 'Demo',
                'last_name': 'Student',
                'student_id': defaults.DEFAULT_STUDENT_ID,
            },
        ]

        created_accounts = []

        for account in default_accounts:
            if target_usernames and account['username'] not in target_usernames:
                logging.debug(f"Skipping {account['username']} - not in target list")
                continue

            cursor.execute('SELECT id FROM user_accounts WHERE username = ?', (account['username'],))
            existing_account = cursor.fetchone()

            # Check and fix role inconsistencies for existing accounts
            if existing_account:
                cursor.execute(
                    'SELECT id, role FROM users WHERE username = ?',
                    (account['username'],),
                )
                user_row = cursor.fetchone()
                if user_row:
                    user_id, existing_role = user_row
                    if existing_role != account['role']:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        logging.warning(
                            f"Fixing role for '{account['username']}': '{existing_role}' -> '{account['role']}'"
                        )
                        try:
                            cursor.execute(
                                'UPDATE users SET role = ?, updated_at = ? WHERE id = ?',
                                (account['role'], timestamp, user_id)
                            )
                            print(f"✅ Fixed {account['username']} user role to {account['role']}")
                        except sqlite3.Error as exc:
                            logging.error(f"Failed to update role for user '{account['username']}': {exc}")
                else:
                    # User record missing but account exists - create user
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    try:
                        cursor.execute(
                            '''INSERT INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                            (account['username'], account['first_name'], account['last_name'],
                             account['email'], account['role'], account['student_id'], timestamp, timestamp)
                        )
                        new_user_id = cursor.lastrowid
                        cursor.execute(
                            'UPDATE user_accounts SET user_id = ? WHERE username = ?',
                            (new_user_id, account['username'])
                        )
                        print(f"✅ Created missing user record for {account['username']}")
                    except sqlite3.Error as exc:
                        logging.error(f"Failed to create user record for '{account['username']}': {exc}")
                logging.debug(f"Account {account['username']} already exists, skipping creation")
                continue

            logging.info(f"Creating default account: {account['username']}")
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Create user in users table
            cursor.execute(
                'SELECT id FROM users WHERE username = ?',
                (account['username'],),
            )
            user_row = cursor.fetchone()

            if not user_row:
                # Create new user
                cursor.execute(
                    '''INSERT INTO users
                       (username, first_name, last_name, email, role, student_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (account['username'], account['first_name'], account['last_name'],
                     account['email'], account['role'], account['student_id'], timestamp, timestamp)
                )
                user_id = cursor.lastrowid
            else:
                user_id = user_row[0]

            # Hash password and create account
            salt, password_hash = self.password_hasher(account['password'])
            cursor.execute(
                '''INSERT INTO user_accounts
                   (username, password_hash, salt, user_id, created_at, updated_at, password_reset_required)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (account['username'], password_hash, salt, user_id, timestamp, timestamp, 0)
            )

            created_accounts.append(account['username'])
            print(f"✅ Created {account['username']} account ({account['role']})")

        if created_accounts:
            conn.commit()
            logging.info(f"Created default accounts: {', '.join(created_accounts)}")

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
                    update_fields = [f"{key} = ?" for key in user_updates.keys()]
                    update_fields.append("updated_at = ?")
                    update_values = list(user_updates.values()) + [timestamp, user_id]

                    cursor.execute(
                        f'UPDATE users SET {", ".join(update_fields)} WHERE id = ?',
                        update_values
                    )

                # Update user_accounts table
                if account_updates:
                    update_fields = [f"{key} = ?" for key in account_updates.keys()]
                    update_fields.append("updated_at = ?")
                    update_values = list(account_updates.values()) + [timestamp, user_id]

                    cursor.execute(
                        f'UPDATE user_accounts SET {", ".join(update_fields)} WHERE user_id = ?',
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
        if not current_user or 'manage_users' not in current_user.get('permissions', []):
            print("You don't have permission to delete users.")
            return False

        if current_user['id'] == user_id:
            print("You cannot delete your own account.")
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

                # Prevent deleting last admin
                if role == 'admin':
                    cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', ('admin',))
                    if cursor.fetchone()[0] <= 1:
                        print("Cannot delete the last admin user.")
                        return False

                # Delete related data
                cursor.execute('DELETE FROM two_fa_recovery_codes WHERE user_id = ?', (user_id,))
                cursor.execute('DELETE FROM user_permissions WHERE user_id = ?', (user_id,))
                cursor.execute('DELETE FROM user_accounts WHERE user_id = ?', (user_id,))
                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))

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

    def list_users(self) -> Optional[List[Dict]]:
        """List all users in the system."""
        current_user = self.get_current_user()
        if not current_user or 'manage_users' not in current_user.get('permissions', []):
            print("You don't have permission to view all users.")
            return None

        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT u.id, ua.username, u.email, u.first_name, u.last_name, u.role,
                           ua.is_active, ua.last_login, u.created_at, u.student_id, ua.two_fa_enabled
                    FROM users u
                    JOIN user_accounts ua ON u.id = ua.user_id
                    ORDER BY u.role, ua.username
                ''')

                users = [dict(row) for row in cursor.fetchall()]
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
                    return user_dict
                else:
                    print("User not found.")
                    return None

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None
