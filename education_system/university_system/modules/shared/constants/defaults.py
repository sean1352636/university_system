"""Centralized system defaults for the university system.

DEPRECATED: This module has been moved to university_system.core.defaults
to prevent circular imports. This file now re-exports everything from core
for backward compatibility.

New code should import from:
    from education_system.university_system.core.defaults import DEFAULT_ADMIN_USERNAME, ...

This backward compatibility shim will be removed in a future version.
"""

# Re-export everything from core.defaults for backward compatibility
from education_system.university_system.core.defaults import (
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_ADMIN_FIRST_NAME,
    DEFAULT_ADMIN_LAST_NAME,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_STUDENT_ID,
    DEFAULT_STUDENT_USERNAME,
    DEFAULT_STUDENT_EMAIL,
    DEFAULT_STUDENT_FIRST_NAME,
    DEFAULT_STUDENT_LAST_NAME,
    DEFAULT_STUDENT_PASSWORD,
    DEFAULT_STAFF_PASSWORD,
    UNIVERSITY_NAME,
    UNIVERSITY_EMAIL_DOMAIN,
    UNIVERSITY_NOREPLY_EMAIL,
    SYSTEM_ADMIN_EMAIL,
    SYSTEM_SUPPORT_EMAIL,
    DEMO_MODE,
    get_admin_email,
    get_fallback_email,
    get_default_student_data,
    get_default_admin_data,
    print_generated_passwords,
)

__all__ = [
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
    "UNIVERSITY_NAME",
    "UNIVERSITY_EMAIL_DOMAIN",
    "UNIVERSITY_NOREPLY_EMAIL",
    "SYSTEM_ADMIN_EMAIL",
    "SYSTEM_SUPPORT_EMAIL",
    "DEMO_MODE",
    "get_admin_email",
    "get_fallback_email",
    "get_default_student_data",
    "get_default_admin_data",
    "print_generated_passwords",
]
