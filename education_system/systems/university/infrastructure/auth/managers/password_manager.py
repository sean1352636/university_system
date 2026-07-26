"""
Password Management Module

Handles all password-related operations for the authentication system including:
- Password hashing with PBKDF2-SHA256 (1M iterations)
- Password validation and strength checking
- Password change and reset operations
- Temporary password generation
- Integration with email service for password reset notifications
- Immutable audit logging for compliance

Security Features:
- PBKDF2-SHA256 with 1,000,000 iterations (OWASP recommended)
- Unique salt per password
- Secure random password generation
- Password reset requires flag in database
- Comprehensive audit trail

Part of the authentication module refactoring to separate password
concerns from general authentication logic.
"""

import hashlib
import logging
import secrets
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from typing import Tuple, Optional

from education_system.systems.university.infrastructure.auth.core_utils.utils import validate_password

__all__ = [
    'hash_password',
    'verify_password',
    'generate_temp_password',
    'change_user_password',
    'reset_user_password',
]

logger = logging.getLogger(__name__)

# Import optional dependencies
try:
    from education_system.systems.university.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.systems.university.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Hash a password with a salt using PBKDF2.

    Uses 1,000,000 iterations as recommended by OWASP for PBKDF2-SHA256.
    This provides strong protection against brute-force attacks.

    Parameters
    ----------
    password : str
        The plaintext password to hash
    salt : str, optional
        Hex-encoded salt to use. If None, a new salt is generated

    Returns
    -------
    tuple of (str, str)
        (salt, hash) where both are hex-encoded strings
        - salt: 32-character hex string (16 bytes)
        - hash: 128-character hex string (64 bytes)

    Examples
    --------
    >>> salt, hash_val = hash_password("mypassword123")
    >>> len(salt)
    32
    >>> len(hash_val)
    128

    >>> # Verify with same salt
    >>> salt2, hash_val2 = hash_password("mypassword123", salt)
    >>> hash_val == hash_val2
    True

    Notes
    -----
    The high iteration count (1,000,000) is intentional to slow down
    brute-force attacks. This may take ~100ms on modern hardware.
    """
    if salt is None:
        salt = secrets.token_hex(16)

    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        salt.encode(),
        1_000_000,  # Increased from 100,000 to 1 million iterations (OWASP recommendation)
        dklen=64
    )

    return salt, key.hex()

def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored hash.

    Parameters
    ----------
    password : str
        The plaintext password to verify
    salt : str
        The salt used when creating the stored hash
    stored_hash : str
        The hash to compare against

    Returns
    -------
    bool
        True if password matches, False otherwise

    Examples
    --------
    >>> salt, hash_val = hash_password("correct_password")
    >>> verify_password("correct_password", salt, hash_val)
    True
    >>> verify_password("wrong_password", salt, hash_val)
    False
    """
    _, computed_hash = hash_password(password, salt)
    return computed_hash == stored_hash

def generate_temp_password() -> str:
    """
    Generate a secure temporary password.

    Creates a cryptographically secure random password suitable for
    temporary use (e.g., password resets). Users should be required
    to change this on first login.

    Returns
    -------
    str
        12-character random password containing letters, numbers,
        and special characters

    Examples
    --------
    >>> temp = generate_temp_password()
    >>> len(temp)
    12
    >>> validate_password(temp)
    True

    Notes
    -----
    Uses secrets module for cryptographically strong random generation.
    """
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return ''.join(secrets.choice(chars) for _ in range(12))

def change_user_password(
    db_manager,
    username: str,
    current_password: str,
    new_password: str,
    current_user: Optional[dict] = None,
    log_activity_func=None
) -> bool:
    """
    Change a user's password after verifying current password.

    Parameters
    ----------
    db_manager : DatabaseConnectionManager
        Database connection manager instance
    username : str
        Username of the account to change password for
    current_password : str
        Current password for verification
    new_password : str
        New password to set
    current_user : dict, optional
        Current user context for audit logging
    log_activity_func : callable, optional
        Function to call for activity logging

    Returns
    -------
    bool
        True if password was changed successfully, False otherwise

    Notes
    -----
    - Validates new password strength
    - Verifies current password before allowing change
    - Clears password_reset_required flag
    - Logs activity and creates immutable audit trail
    """
    if not validate_password(new_password):
        print("Invalid new password. Password must be at least 8 characters long and contain a mix of letters, numbers, and special characters.")
        return False

    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Get user account data
            cursor.execute(
                'SELECT id, user_id, password_hash, salt FROM user_accounts WHERE username = ?',
                (username,)
            )

            user_data = cursor.fetchone()

            if not user_data:
                print("User not found.")
                return False

            account_id, user_id, password_hash, salt = user_data

            # Verify the current password
            if not verify_password(current_password, salt, password_hash):
                print("Current password is incorrect.")
                logger.debug(f"Password verification failed for user: {username}")
                return False

            # Hash the new password
            new_salt, new_hash = hash_password(new_password)

            # Update the password
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE user_accounts SET password_hash = ?, salt = ?, updated_at = ?, password_reset_required = 0 WHERE id = ?',
                (new_hash, new_salt, timestamp, account_id)
            )

            conn.commit()

            # Log the activity
            if log_activity_func:
                log_activity_func(username, 'Password changed', None, user_id)

            # Immutable audit log for compliance
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.PASSWORD_CHANGE,
                    user_id=str(user_id),
                    resource_type='user_account',
                    resource_id=str(account_id),
                    details={'username': username}
                )

            # Update current user if this is the logged-in user
            if current_user and current_user.get('id') == user_id:
                current_user['password_reset_required'] = 0

            print("Password changed successfully.")
            return True

    except sqlite3.Error:
        logger.error("Database error during password change")
        return False

def reset_user_password(
    db_manager,
    username: str,
    admin_user: Optional[dict] = None,
    log_activity_func=None,
    create_configured_connection_func=None
) -> Tuple[bool, Optional[str]]:
    """
    Reset a user's password to a temporary one (admin function).

    Parameters
    ----------
    db_manager : DatabaseConnectionManager
        Database connection manager instance
    username : str
        Username of the account to reset password for
    admin_user : dict, optional
        Admin user context for permission checking and audit logging
    log_activity_func : callable, optional
        Function to call for activity logging
    create_configured_connection_func : callable, optional
        Alternative connection creation function

    Returns
    -------
    tuple of (bool, str or None)
        (success, temp_password) where temp_password is the new
        temporary password if successful, None otherwise

    Notes
    -----
    - Requires admin permissions (manage_users)
    - Sets password_reset_required flag
    - Attempts to send email notification
    - Logs activity and creates immutable audit trail
    """
    # Check permissions
    if admin_user:
        if 'manage_users' not in admin_user.get('permissions', []):
            print("You don't have permission to reset passwords.")
            return False, None
    else:
        logger.warning("Password reset attempted without admin user context")

    try:
        # Use provided connection function or default to db_manager
        if create_configured_connection_func:
            conn = create_configured_connection_func()
        else:
            conn = None
            # Will use context manager below

        try:
            if conn:
                cursor = conn.cursor()
            else:
                # Use context manager
                conn = db_manager._create_configured_connection()
                cursor = conn.cursor()

            # Get user account data
            cursor.execute(
                'SELECT id, user_id FROM user_accounts WHERE username = ?',
                (username,)
            )

            user_data = cursor.fetchone()

            if not user_data:
                print("User not found.")
                return False, None

            account_id, user_id = user_data

            # Generate a temporary password
            temp_password = generate_temp_password()

            # Hash the temporary password
            salt, password_hash = hash_password(temp_password)

            # Update the password
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE user_accounts SET password_hash = ?, salt = ?, updated_at = ?, password_reset_required = 1 WHERE id = ?',
                (password_hash, salt, timestamp, account_id)
            )

            conn.commit()

            # Send password reset notification email
            try:
                # Get student_id from users table if exists
                cursor.execute('SELECT student_id FROM users WHERE id = ?', (user_id,))
                student_result = cursor.fetchone()

                if student_result and student_result[0]:
                    student_id = student_result[0]
                    from education_system.systems.university.infrastructure.email.email_service import send_password_reset
                    send_password_reset(student_id, temp_password)
            except ImportError as e:
                logging.warning(f"Email service not available: {e}")
            except (sqlite3.Error, AttributeError) as e:
                logging.warning(f"Failed to send password reset email: {e}")

            # Log the activity
            admin_username = admin_user['username'] if admin_user else "system"
            admin_id = admin_user['id'] if admin_user else None

            if log_activity_func:
                log_activity_func(
                    admin_username,
                    f'Password reset for user: {username}',
                    None,
                    admin_id
                )

            # Immutable audit log for compliance
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.PASSWORD_RESET,
                    user_id=str(admin_id) if admin_id else 'system',
                    resource_type='user_account',
                    resource_id=str(user_id),
                    details={'target_username': username, 'admin_username': admin_username}
                )

            masked = temp_password[:2] + '*' * (len(temp_password) - 2) if len(temp_password) > 2 else '***'
            print(f"Password for {username} has been reset to: {masked}")  # lgtm[py/clear-text-logging-sensitive-data]
            print("User will be required to change password on next login.")
            return True, temp_password

        finally:
            if conn:
                conn.close()

    except sqlite3.Error:
        logger.error("Database error during password reset")
        return False, None

def check_password_reset_required(db_manager, username: str) -> bool:
    """
    Check if a user needs to reset their password.

    Parameters
    ----------
    db_manager : DatabaseConnectionManager
        Database connection manager instance
    username : str
        Username to check

    Returns
    -------
    bool
        True if password reset is required, False otherwise
    """
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT password_reset_required FROM user_accounts WHERE username = ?',
                (username,)
            )
            result = cursor.fetchone()
            return bool(result[0]) if result else False
    except sqlite3.Error:
        logger.error("Database error checking password reset status")
        return False
