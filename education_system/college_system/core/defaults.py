"""Default configuration values sourced from environment or hardcoded."""

import os
import secrets
import string

# Server defaults
API_HOST = os.getenv("COLLEGE_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("COLLEGE_API_PORT", "5000"))
API_DEBUG = os.getenv("COLLEGE_API_DEBUG", "false").lower() == "true"

# Auth defaults
SESSION_TIMEOUT_MINUTES = int(os.getenv("COLLEGE_SESSION_TIMEOUT", "30"))
JWT_EXPIRY_HOURS = int(os.getenv("COLLEGE_JWT_EXPIRY", "24"))
JWT_SECRET = os.getenv("COLLEGE_JWT_SECRET", "change-me-in-production")
MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5

# Default credentials (first run only)
DEFAULT_ADMIN_USERNAME = "admin1"
DEFAULT_ADMIN_PASSWORD = "admin1234"
DEFAULT_TEACHER_USERNAME = "staff1"
DEFAULT_TEACHER_PASSWORD = "staff1234"
DEFAULT_STUDENT_USERNAME = "student1"
DEFAULT_STUDENT_PASSWORD = "student1234"

# Student ID format
STUDENT_ID_PREFIX = "SFC"
STUDENT_ID_LENGTH = 7  # e.g., SFC0001

# Staff ID format
STAFF_ID_PREFIX = "STF"


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        # Ensure at least one of each category
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*" for c in password)
        ):
            return password
