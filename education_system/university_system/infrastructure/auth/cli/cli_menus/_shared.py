"""Shared constants and the lazy chatbot-availability probe."""
from __future__ import annotations

try:
    from education_system.university_system.infrastructure.auth.optional_dependencies import (
        is_chatbot_available,
    )
except ImportError:
    def is_chatbot_available():  # type: ignore[misc]
        return False

# Default roles constant (used for role protection)
ROLES = {
    'admin': 'Administrator with full system access',
    'staff': 'Staff with access to student records and reports',
    'student': 'Student with access to own records only',
    'instructor': 'Instructor with access to assigned modules and student grades',
    'parent': 'Parent with access to their children\'s records',
}
