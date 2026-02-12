"""
Authentication Utility Functions

Provides validation, sanitization, and helper functions for the
authentication module including:
- Username, password, and email validation
- Password generation
- Database table verification
- Input sanitization

Part of the authentication module refactoring to separate utility
functions from core business logic.
"""

import logging
import re
import secrets
from university_system.infrastructure.database.db import sqlite3
from typing import Optional, Tuple

from university_system.core.sql_safety import (
    validate_column_definition,
    SQLIdentifierError,
)

__all__ = [
    'derive_name_from_username',
    'validate_username',
    'validate_password',
    'validate_email',
    'generate_temp_password',
    'ensure_students_table',
    'infer_role_for_username',
]

logger = logging.getLogger(__name__)

def validate_username(username: str) -> bool:
    """
    Validate username format.

    Ensures username meets security and format requirements:
    - Between 3 and 20 characters
    - Contains only alphanumeric characters, underscores, and hyphens
    - Not empty or None

    Parameters
    ----------
    username : str
        Username to validate

    Returns
    -------
    bool
        True if username is valid, False otherwise

    Examples
    --------
    >>> validate_username("john_doe")
    True
    >>> validate_username("ab")
    False
    >>> validate_username("user@123")
    False
    """
    if not username:
        return False

    if not re.match(r'^[a-zA-Z0-9_-]{3,20}$', username):
        return False

    return True

def validate_password(password: str) -> bool:
    """
    Validate password strength.

    Ensures password meets minimum security requirements:
    - At least 8 characters long
    - Contains at least one letter
    - Contains at least one number

    Parameters
    ----------
    password : str
        Password to validate

    Returns
    -------
    bool
        True if password is valid, False otherwise

    Examples
    --------
    >>> validate_password("password123")
    True
    >>> validate_password("short1")
    False
    >>> validate_password("nodigits")
    False
    """
    if not password or len(password) < 8:
        return False

    if not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
        return False

    return True

def validate_email(email: str) -> bool:
    """
    Validate email format.

    Ensures email follows standard email format with:
    - Local part (before @)
    - Domain part (after @)
    - Valid TLD (at least 2 characters)

    Parameters
    ----------
    email : str
        Email address to validate

    Returns
    -------
    bool
        True if email is valid, False otherwise

    Examples
    --------
    >>> validate_email("user@example.com")
    True
    >>> validate_email("invalid.email")
    False
    >>> validate_email("user@domain")
    False
    """
    if not email:
        return False

    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return False

    return True

def generate_temp_password() -> str:
    """
    Generate a secure temporary password.

    Creates a cryptographically secure random password suitable
    for temporary use (e.g., password resets). Users should be
    required to change this on first login.

    Returns
    -------
    str
        12-character random password containing letters, numbers,
        and special characters

    Examples
    --------
    >>> temp_pass = generate_temp_password()
    >>> len(temp_pass)
    12
    >>> validate_password(temp_pass)
    True
    """
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return ''.join(secrets.choice(chars) for _ in range(12))

def ensure_students_table(cursor: sqlite3.Cursor) -> None:
    """
    Guarantee the student catalogue exists for auth relationships.

    Creates the students table if it doesn't exist and ensures all
    required columns are present. Uses centralized SQL safety
    validation for column definitions.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Database cursor to use for table creation

    Raises
    ------
    sqlite3.Error
        If table creation or modification fails

    Notes
    -----
    This function is safe to call multiple times as it only adds
    missing columns and won't modify existing data.
    """
    try:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            email_address TEXT,
            title TEXT,
            first_name TEXT,
            middle_name TEXT,
            last_name TEXT,
            gender TEXT,
            dob TEXT,
            age INTEGER,
            course TEXT,
            registration_datetime TEXT,
            status TEXT DEFAULT 'Active',
            enrollment_date TEXT
        )
        ''')

        cursor.execute("PRAGMA table_info(students)")
        existing_columns = {column[1] for column in cursor.fetchall()}

        required_columns = {
            'email_address': 'TEXT',
            'title': 'TEXT',
            'first_name': 'TEXT',
            'middle_name': 'TEXT',
            'last_name': 'TEXT',
            'gender': 'TEXT',
            'dob': 'TEXT',
            'age': 'INTEGER',
            'course': 'TEXT',
            'registration_datetime': 'TEXT',
            'status': 'TEXT DEFAULT "Active"',
            'enrollment_date': 'TEXT'
        }

        # Use centralized SQL safety validation for column definitions
        for column, definition in required_columns.items():
            if column not in existing_columns:
                try:
                    # Validate column definition using SQL safety module
                    col_def = validate_column_definition(column, definition)
                    cursor.execute(f'ALTER TABLE students ADD COLUMN [{col_def.name}] {col_def.type_def}')
                    logging.info(f"Added missing column '{column}' to students table")
                except SQLIdentifierError as e:
                    logging.warning(f"Invalid column definition for '{column}': {e}")
                    continue
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        continue
                    logging.warning(f"Could not add column '{column}' to students table: {e}")
                except sqlite3.Error as e:
                    logging.warning(f"SQLite error while adding column '{column}': {e}")

    except sqlite3.Error as e:
        logging.error(f"Failed to ensure students table exists: {e}")
        raise

def infer_role_for_username(username: str) -> str:
    """
    Best-effort role inference when a user profile is missing.

    Attempts to determine user role based on username patterns.
    This is a fallback mechanism and should not be relied upon
    for security-critical decisions.

    Parameters
    ----------
    username : str
        Username to analyze for role inference

    Returns
    -------
    str
        Inferred role ('admin', 'staff', 'instructor', or 'student')

    Examples
    --------
    >>> infer_role_for_username("admin")
    'admin'
    >>> infer_role_for_username("staff_john")
    'staff'
    >>> infer_role_for_username("student123")
    'student'
    >>> infer_role_for_username("prof_smith")
    'instructor'

    Notes
    -----
    This function uses simple pattern matching and should only be
    used as a fallback when proper role information is unavailable.
    """
    lower = username.lower()

    # Check for admin patterns
    if 'admin' in lower or lower == 'root' or lower == 'superuser':
        return 'admin'

    # Check for staff patterns
    if 'staff' in lower or 'employee' in lower:
        return 'staff'

    # Check for instructor patterns
    if any(prefix in lower for prefix in ['prof', 'instructor', 'teacher', 'faculty', 'dr_', 'dr.']):
        return 'instructor'

    # Check for parent patterns
    if 'parent' in lower or 'guardian' in lower:
        return 'parent'

    # Default to student
    return 'student'

def get_default_password(config: dict, key: str, fallback: str) -> str:
    """
    Fetch default password overrides from config if present.

    Allows configuration files to override default passwords for
    different account types. Falls back to the provided default
    if config is unavailable or doesn't contain the key.

    Parameters
    ----------
    config : dict
        Configuration dictionary containing default account settings
    key : str
        Configuration key to look up (e.g., 'admin', 'staff')
    fallback : str
        Default value to use if config lookup fails

    Returns
    -------
    str
        Password from config or fallback value

    Examples
    --------
    >>> config = {'default_accounts': {'admin_password': 'custom123'}}
    >>> get_default_password(config, 'admin', 'default')
    'custom123'
    >>> get_default_password({}, 'admin', 'default')
    'default'
    """
    try:
        defaults = config.get('default_accounts', {})
        if isinstance(defaults, dict):
            value = defaults.get(f"{key}_password") or defaults.get(key)
            if value:
                return str(value)
    except Exception as e:
        logger.debug(f"Failed to get default password from config for key '{key}': {e}")
    return fallback

def create_default_student_if_needed(cursor: sqlite3.Cursor, conn: sqlite3.Connection) -> None:
    """
    Ensure the students table exists and report if it is empty.

    Checks for the existence of the students table and logs
    appropriate warnings if the table is missing or empty.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Database cursor for queries
    conn : sqlite3.Connection
        Database connection (unused, kept for compatibility)

    Notes
    -----
    This function does not create default students, only reports
    on the state of the students table.
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
    table_exists = cursor.fetchone() is not None
    if not table_exists:
        logging.warning(
            "Students table is missing; student-related authentication features may be unavailable."
        )
        return

    cursor.execute('SELECT COUNT(*) FROM students')
    student_count = cursor.fetchone()[0]
    if student_count == 0:
        logging.info(
            "Students table is present but empty. Import student records to enable student-facing workflows."
        )

def check_role_coverage(cursor: sqlite3.Cursor, conn: sqlite3.Connection) -> None:
    """
    Inspect core system accounts and report any missing roles.

    Verifies that the system has at least one account for each
    required role (admin, staff, student) and logs warnings for
    missing roles.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Database cursor for queries
    conn : sqlite3.Connection
        Database connection (unused, kept for compatibility)

    Notes
    -----
    This is a diagnostic function that helps ensure the system
    has proper role coverage for normal operation.
    """
    cursor.execute(
        '''
        SELECT u.role, COUNT(ua.id)
        FROM user_accounts ua
        JOIN users u ON ua.user_id = u.id
        GROUP BY u.role
        '''
    )
    role_counts = {row[0]: row[1] for row in cursor.fetchall()}

    required_roles = {'admin', 'staff', 'student'}
    missing_roles = [role for role in required_roles if role_counts.get(role, 0) == 0]

    if missing_roles:
        logging.warning(
            "No active accounts found for roles: %s. Provision them via the administration tools.",
            ', '.join(sorted(missing_roles)),
        )
    else:
        logging.info("Core role coverage detected: %s", role_counts)

def derive_name_from_username(username: str) -> Tuple[str, str]:
    """
    Create placeholder names from a username when needed.

    Attempts to extract first and last names from a username by splitting
    on common separators (periods, underscores, hyphens, spaces).

    Parameters
    ----------
    username : str
        The username to derive names from

    Returns
    -------
    tuple of (str, str)
        (first_name, last_name) derived from the username.
        Returns ('User', 'Account') if unable to derive meaningful names.

    Examples
    --------
    >>> derive_name_from_username('john.doe')
    ('John', 'Doe')

    >>> derive_name_from_username('alice_smith')
    ('Alice', 'Smith')

    >>> derive_name_from_username('bob')
    ('Bob', 'User')

    >>> derive_name_from_username('')
    ('User', 'Account')
    """
    import re as _re

    tokens = [token for token in _re.split(r'[._\-\s]+', username) if token]
    if len(tokens) >= 2:
        return tokens[0].title(), tokens[-1].title()
    if tokens:
        token = tokens[0].title()
        return token, 'User'
    return 'User', 'Account'
