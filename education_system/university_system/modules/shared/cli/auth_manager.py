"""
Authentication manager for CLI system.

Handles user authentication, permission management, and user setup.
"""

from education_system.university_system.modules.shared.cli.imports import (
    logging, sqlite3, hashlib, secrets, datetime, DB_PATH, logger, _t,
    log_activity, get_auth, set_auth, UserAuth, get_global_auth, set_global_auth,
    set_auth_instance, defaults
)

# Import exception types
from education_system.university_system.infrastructure.exceptions import DatabaseError, ValidationError

# Check if auth instance is available and import flags
try:
    from education_system.university_system.infrastructure.auth import set_auth_instance as _test_auth
    from education_system.university_system.infrastructure.auth import MFA_AVAILABLE
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    MFA_AVAILABLE = False

# Check if session management is available
try:
    from education_system.university_system.infrastructure.security import session_management
    SESSION_MANAGEMENT_AVAILABLE = True
except ImportError:
    SESSION_MANAGEMENT_AVAILABLE = False

# Check if comprehensive security is available
try:
    from education_system.university_system.infrastructure.security import comprehensive_security
    COMPREHENSIVE_SECURITY_AVAILABLE = True
except ImportError:
    COMPREHENSIVE_SECURITY_AVAILABLE = False

# Check if data encryption is available
try:
    from education_system.university_system.infrastructure.security import data_encryption
    DATA_ENCRYPTION_AVAILABLE = True
except ImportError:
    DATA_ENCRYPTION_AVAILABLE = False

# Check if email OTP is available
try:
    from education_system.university_system.infrastructure.auth import email_otp_service
    EMAIL_OTP_AVAILABLE = True
except ImportError:
    EMAIL_OTP_AVAILABLE = False

# Check if SMS provider is available
try:
    from education_system.university_system.infrastructure.auth import sms_provider
    SMS_PROVIDER_AVAILABLE = True
except ImportError:
    SMS_PROVIDER_AVAILABLE = False

# Define local get_db_connection to avoid circular import
def get_db_connection(timeout=30.0):
    """Get database connection using centralized pool"""
    from education_system.university_system.infrastructure.database.db import get_connection
    return get_connection(db_path=DB_PATH, row_factory=True, timeout=timeout)

# Global auth instance
auth = None


def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
# Initialize all the sub-modules that need auth


def ensure_default_users_exist_once():
    """
    Ensure default users exist but only create them once per session.
    This is the centralized function for creating default users.
    """
    # Check if we've already created users in this session
    if hasattr(ensure_default_users_exist_once, '_users_created'):
        return True

    try:
        conn = get_db_connection(timeout=10.0)
        if not conn:
            return False

        cursor = conn.cursor()

        # Check and create admin user if needed
        admin_data = defaults.get_default_admin_data()
        cursor.execute('SELECT id, role FROM users WHERE username = ?', (admin_data['username'],))
        existing_admin = cursor.fetchone()
        if not existing_admin:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            try:
                cursor.execute('''
                INSERT INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (admin_data['username'], admin_data['first_name'], admin_data['last_name'],
                      admin_data['email'], 'admin', None, current_time, current_time))
                logger.info("Default admin user created")
            except sqlite3.IntegrityError as e:
                # Check if it's just a username conflict with different email
                cursor.execute('SELECT email FROM users WHERE username = ?', (admin_data['username'],))
                existing_email = cursor.fetchone()
                if existing_email:
                    logging.info(f"Admin user exists with email: {existing_email[0]}")
                    logger.info("Default admin user already exists")
                else:
                    logging.error(f"Error creating admin user: {e}")
        elif existing_admin[1] != 'admin':
            # Admin user exists but has wrong role, fix it
            cursor.execute('UPDATE users SET role = ? WHERE username = ?', ('admin', admin_data['username']))
            logger.info("Fixed admin user role")
        else:
            logger.info("Default admin user already exists")

        # Check and create student user if needed
        student_data = defaults.get_default_student_data()
        cursor.execute('SELECT id, role FROM users WHERE username = ?', (student_data['username'],))
        existing_student = cursor.fetchone()
        if not existing_student:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            try:
                cursor.execute('''
                INSERT INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_data['username'], student_data['first_name'], student_data['last_name'],
                      student_data['email'], 'student', student_data['student_id'], current_time, current_time))
                logger.info("Default student user created")
            except sqlite3.IntegrityError as e:
                cursor.execute('SELECT email FROM users WHERE username = ?', (student_data['username'],))
                existing_email = cursor.fetchone()
                if existing_email:
                    logging.info(f"Student user exists with email: {existing_email[0]}")
                    logger.info("Default student user already exists")
                else:
                    logging.error(f"Error creating student user: {e}")
        elif existing_student[1] != 'student':
            # Student user exists but has wrong role, fix it
            cursor.execute('UPDATE users SET role = ? WHERE username = ?', ('student', student_data['username']))
            logger.info("Fixed student user role")
        else:
            logger.info("Default student user already exists")

        conn.commit()
        conn.close()

        # Mark as completed for this session
        ensure_default_users_exist_once._users_created = True
        return True

    except sqlite3.Error as e:
        logging.error(f"Error ensuring default users: {e}")
        return False
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Unexpected error ensuring default users: {e}")
        return False


def create_default_user_if_needed(username, first_name, last_name, email, role, student_id=None):
    """
    Helper function for other modules to create default users safely.
    Returns True if user was created or already exists, False on error.
    """
    try:
        conn = get_db_connection(timeout=10.0)
        if not conn:
            return False

        cursor = conn.cursor()

        # Check if user already exists
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return True  # User already exists

        # Create the user
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, first_name, last_name, email, role, student_id, current_time, current_time))

        conn.commit()
        conn.close()
        logger.info(f"User '{username}' created successfully")
        return True

    except sqlite3.IntegrityError as e:
        logging.error(f"Could not create user '{username}': {e}")
        return False
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error creating user '{username}': {e}")
        return False


def ensure_user_in_communication_system(username, first_name, last_name, email, role, student_id=None):
    """
    Ensure that a user exists in the users table for communication system integration.
    This function should be called whenever a new user account is created.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Check if user already exists by username
        cursor.execute('SELECT id, email FROM users WHERE username = ?', (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            user_id, existing_email = existing_user
            # User exists, check if we need to update email
            if existing_email != email:
                # Check if the new email is already used by another user
                cursor.execute('SELECT id FROM users WHERE email = ? AND username != ?', (email, username))
                email_conflict = cursor.fetchone()

                if email_conflict:
                    logger.warning(f"Email {email} is already in use by another user. Keeping existing email {existing_email} for user {username}.")
                else:
                    # Update the email
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                    UPDATE users
                    SET first_name = ?, last_name = ?, email = ?, role = ?, student_id = ?, updated_at = ?
                    WHERE username = ?
                    ''', (
                        first_name,
                        last_name,
                        email,
                        role,
                        student_id,
                        current_time,
                        username
                    ))
                    conn.commit()
                    logger.info(f"User '{username}' information updated in communication system.")
            else:
                # Email is the same, just update other information
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                UPDATE users
                SET first_name = ?, last_name = ?, role = ?, student_id = ?, updated_at = ?
                WHERE username = ?
                ''', (
                    first_name,
                    last_name,
                    role,
                    student_id,
                    current_time,
                    username
                ))
                conn.commit()
                logger.info(f"User '{username}' information updated in communication system.")
        else:
            # User doesn't exist, use the centralized creation function
            conn.close()
            return create_default_user_if_needed(username, first_name, last_name, email, role, student_id)

        conn.close()
        return True

    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: users.email" in str(e):
            logger.error(f"Email {email} is already in use. Could not integrate user {username}.")
        elif "UNIQUE constraint failed: users.username" in str(e):
            logger.error(f"Username {username} is already in use. Could not integrate user.")
        else:
            logger.error(f"Database integrity error: {e}")
        return False
    except sqlite3.Error as e:
        logging.error(f"Database error during user integration: {e}")
        return False
    except (ValueError, TypeError, ValidationError) as e:
        logging.error(f"Unexpected error during user integration: {e}")
        return False


def _link_auth_to_student_union(auth):
    """Wire authentication to Student Union modules."""
    try:
        from education_system.university_system.modules.domain.student_affairs import student_union
        if hasattr(student_union, 'set_auth_all'):
            student_union.set_auth_all(auth)
        elif hasattr(student_union, 'set_auth'):
            student_union.set_auth(auth)
    except (sqlite3.Error, DatabaseError) as e:
        logger.warning(f"Could not link auth to Student Union: {e}")


def initialize_security_modules():
    """Initialize security and authentication modules"""
    logger.info("Initializing security modules...")

    # Initialize MFA if available
    if MFA_AVAILABLE:
        try:
            logger.info("MFA services loaded")
        except (ValueError, TypeError, ValidationError) as e:
            logger.warning(f"Failed to initialize MFA: {e}")

    # Initialize Session Management if available
    if SESSION_MANAGEMENT_AVAILABLE:
        try:
            logger.info("Session management loaded")
        except (ValueError, TypeError, ValidationError) as e:
            logger.warning(f"Failed to initialize session management: {e}")

    # Initialize Comprehensive Security if available
    if COMPREHENSIVE_SECURITY_AVAILABLE:
        try:
            logger.info("Comprehensive security modules loaded")
        except (ValueError, TypeError, ValidationError) as e:
            logger.warning(f"Failed to initialize comprehensive security: {e}")

    # Initialize Data Encryption if available
    if DATA_ENCRYPTION_AVAILABLE:
        try:
            logger.info("Data encryption services loaded")
        except (ValueError, TypeError, ValidationError) as e:
            logger.warning(f"Failed to initialize data encryption: {e}")

    # Initialize Email OTP if available
    if EMAIL_OTP_AVAILABLE:
        try:
            logger.info("Email OTP services loaded")
        except (ValueError, TypeError, ValidationError) as e:
            logger.warning(f"Failed to initialize email OTP: {e}")

    # Initialize SMS Provider if available
    if SMS_PROVIDER_AVAILABLE:
        try:
            logger.info("SMS provider loaded")
        except (ValueError, TypeError, ValidationError) as e:
            logger.warning(f"Failed to initialize SMS provider: {e}")

    logger.info("Security modules initialized")
    return True


__all__ = [
    'set_auth',
    'ensure_default_users_exist_once',
    'create_default_user_if_needed',
    'ensure_user_in_communication_system',
    '_link_auth_to_student_union',
    'initialize_security_modules',
]
