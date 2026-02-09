"""Centralized system defaults for the university system.

This module provides a single source of truth for default values that are used
throughout the application. Values can be overridden via environment variables.

SECURITY NOTE: Default values here are for development/testing only.
In production, always set environment variables with secure values.
"""

from __future__ import annotations

import os
from typing import Optional


def _get_env(key: str, default: str) -> str:
    """Get environment variable or return default."""
    return os.environ.get(key, default)


def _get_env_int(key: str, default: int) -> int:
    """Get environment variable as integer or return default."""
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


# =============================================================================
# Default User Accounts
# =============================================================================
# These are used when creating initial/demo accounts. In production,
# disable demo accounts or override via environment variables.

DEFAULT_ADMIN_USERNAME = _get_env("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_EMAIL = _get_env("DEFAULT_ADMIN_EMAIL", "admin@university.edu")
DEFAULT_ADMIN_FIRST_NAME = _get_env("DEFAULT_ADMIN_FIRST_NAME", "System")
DEFAULT_ADMIN_LAST_NAME = _get_env("DEFAULT_ADMIN_LAST_NAME", "Administrator")
DEFAULT_ADMIN_PASSWORD = _get_env("DEFAULT_ADMIN_PASSWORD", "admin123")

DEFAULT_STUDENT_ID = _get_env("DEFAULT_STUDENT_ID", "S12345")
DEFAULT_STUDENT_USERNAME = _get_env("DEFAULT_STUDENT_USERNAME", "S12345")
DEFAULT_STUDENT_EMAIL = _get_env("DEFAULT_STUDENT_EMAIL", "student@university.edu")
DEFAULT_STUDENT_FIRST_NAME = _get_env("DEFAULT_STUDENT_FIRST_NAME", "Demo")
DEFAULT_STUDENT_LAST_NAME = _get_env("DEFAULT_STUDENT_LAST_NAME", "Student")
DEFAULT_STUDENT_PASSWORD = _get_env("DEFAULT_STUDENT_PASSWORD", "student123")

DEFAULT_STAFF_PASSWORD = _get_env("DEFAULT_STAFF_PASSWORD", "staff123")


# =============================================================================
# University Information
# =============================================================================
UNIVERSITY_NAME = _get_env("UNIVERSITY_NAME", "Teesside University")
UNIVERSITY_EMAIL_DOMAIN = _get_env("UNIVERSITY_EMAIL_DOMAIN", "university.edu")
UNIVERSITY_NOREPLY_EMAIL = _get_env("UNIVERSITY_NOREPLY_EMAIL", f"noreply@{UNIVERSITY_EMAIL_DOMAIN}")


# =============================================================================
# System Email Addresses (for fallbacks)
# =============================================================================
# Used when user email is not available but system needs to send notifications
SYSTEM_ADMIN_EMAIL = _get_env("SYSTEM_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL)
SYSTEM_SUPPORT_EMAIL = _get_env("SYSTEM_SUPPORT_EMAIL", f"support@{UNIVERSITY_EMAIL_DOMAIN}")


# =============================================================================
# Demo/Test Mode Configuration
# =============================================================================
# When True, demo accounts are created with weak passwords
DEMO_MODE = _get_env("DEMO_MODE", "true").lower() in ("true", "1", "yes")


def get_admin_email() -> str:
    """Get the admin email address for system notifications."""
    return SYSTEM_ADMIN_EMAIL


def get_fallback_email(context: str = "admin") -> str:
    """
    Get a fallback email for when user email is not available.

    Args:
        context: The context for the fallback ("admin", "support", "noreply")

    Returns:
        Appropriate fallback email address
    """
    if context == "admin":
        return SYSTEM_ADMIN_EMAIL
    elif context == "support":
        return SYSTEM_SUPPORT_EMAIL
    elif context == "noreply":
        return UNIVERSITY_NOREPLY_EMAIL
    else:
        return SYSTEM_ADMIN_EMAIL


def get_default_student_data() -> dict:
    """
    Get default student data for demo/test account creation.

    Returns:
        Dictionary with default student information
    """
    return {
        "student_id": DEFAULT_STUDENT_ID,
        "username": DEFAULT_STUDENT_USERNAME,
        "email": DEFAULT_STUDENT_EMAIL,
        "first_name": DEFAULT_STUDENT_FIRST_NAME,
        "last_name": DEFAULT_STUDENT_LAST_NAME,
        "password": DEFAULT_STUDENT_PASSWORD,
    }


def get_default_admin_data() -> dict:
    """
    Get default admin data for demo/test account creation.

    Returns:
        Dictionary with default admin information
    """
    return {
        "username": DEFAULT_ADMIN_USERNAME,
        "email": DEFAULT_ADMIN_EMAIL,
        "first_name": DEFAULT_ADMIN_FIRST_NAME,
        "last_name": DEFAULT_ADMIN_LAST_NAME,
        "password": DEFAULT_ADMIN_PASSWORD,
    }


__all__ = [
    # User defaults
    "DEFAULT_ADMIN_USERNAME",
    "DEFAULT_ADMIN_EMAIL",
    "DEFAULT_ADMIN_FIRST_NAME",
    "DEFAULT_ADMIN_LAST_NAME",
    "DEFAULT_ADMIN_PASSWORD",
    "DEFAULT_STUDENT_ID",
    "DEFAULT_STUDENT_USERNAME",
    "DEFAULT_STUDENT_EMAIL",
    "DEFAULT_STUDENT_FIRST_NAME",
    "DEFAULT_STUDENT_LAST_NAME",
    "DEFAULT_STUDENT_PASSWORD",
    "DEFAULT_STAFF_PASSWORD",
    # University info
    "UNIVERSITY_NAME",
    "UNIVERSITY_EMAIL_DOMAIN",
    "UNIVERSITY_NOREPLY_EMAIL",
    # System emails
    "SYSTEM_ADMIN_EMAIL",
    "SYSTEM_SUPPORT_EMAIL",
    # Configuration
    "DEMO_MODE",
    # Helper functions
    "get_admin_email",
    "get_fallback_email",
    "get_default_student_data",
    "get_default_admin_data",
]
