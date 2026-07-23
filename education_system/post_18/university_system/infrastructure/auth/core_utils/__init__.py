"""
Core Utilities Module

This module contains core utilities, constants, and helper functions
used throughout the authentication system.

Modules
-------
- constants: Role and permission definitions
- utils: Validation and helper functions
- global_auth: Global authentication instance management
"""

# Constants
from education_system.post_18.university_system.infrastructure.auth.core_utils.constants import (
    ROLES,
    PERMISSIONS,
    DEFAULT_SESSION_TIMEOUT,
    DEFAULT_MAX_LOGIN_ATTEMPTS,
    DEFAULT_LOCKOUT_TIME,
    PASSWORD_MIN_LENGTH,
    PBKDF2_ITERATIONS,
)

# Utility functions
from education_system.post_18.university_system.infrastructure.auth.core_utils.utils import (
    validate_username,
    validate_password,
    validate_email,
    generate_temp_password,
    ensure_students_table,
    get_default_password,
    infer_role_for_username,
)

# Global auth functions
from education_system.post_18.university_system.infrastructure.auth.core_utils.global_auth import (
    get_current_user,
    set_auth_instance,
    get_auth_instance,
    clear_auth_instance,
    is_user_logged_in,
    get_current_user_id,
    get_current_username,
    get_current_user_role,
    get_global_auth,
    set_global_auth,
    reset_global_auth,
)

__all__ = [
    # Constants
    'ROLES',
    'PERMISSIONS',
    'DEFAULT_SESSION_TIMEOUT',
    'DEFAULT_MAX_LOGIN_ATTEMPTS',
    'DEFAULT_LOCKOUT_TIME',
    'PASSWORD_MIN_LENGTH',
    'PBKDF2_ITERATIONS',

    # Utility functions
    'validate_username',
    'validate_password',
    'validate_email',
    'generate_temp_password',
    'ensure_students_table',
    'get_default_password',
    'infer_role_for_username',

    # Global auth
    'get_current_user',
    'set_auth_instance',
    'get_auth_instance',
    'clear_auth_instance',
    'is_user_logged_in',
    'get_current_user_id',
    'get_current_username',
    'get_current_user_role',
    'get_global_auth',
    'set_global_auth',
    'reset_global_auth',
]
