"""Default configuration values for the Secondary School Management System."""

import os
import secrets
import string

# Server defaults
API_HOST = os.getenv("SCHOOL_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("SCHOOL_API_PORT", "5001"))

# Auth defaults
SESSION_TIMEOUT_MINUTES = int(os.getenv("SCHOOL_SESSION_TIMEOUT", "30"))
MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5

# Default credentials (first run only)
DEFAULT_ADMIN_USERNAME = "admin2"
DEFAULT_ADMIN_PASSWORD = "admin1234"
DEFAULT_TEACHER_USERNAME = "staff2"
DEFAULT_TEACHER_PASSWORD = "staff1234"
DEFAULT_STUDENT_USERNAME = "student2"
DEFAULT_STUDENT_PASSWORD = "student1234"

# Student ID format
STUDENT_ID_PREFIX = "SEC"
STUDENT_ID_LENGTH = 7  # e.g., SEC0001

# Staff ID format
STAFF_ID_PREFIX = "STF"


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*" for c in password)
        ):
            return password
