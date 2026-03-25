"""Default configuration values for the Secondary School Management System."""

import os

from education_system.shared.core.defaults import (  # noqa: F401
    LOCKOUT_DURATION_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    MIN_PASSWORD_LENGTH,
    SESSION_TIMEOUT_MINUTES,
    STAFF_ID_PREFIX,
    generate_secure_password,
)

# ── API settings ─────────────────────────────────────────────────────────
API_HOST = os.getenv("SCHOOL_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("SCHOOL_API_PORT", "5001"))

# ── Default first-run credentials ────────────────────────────────────────
DEFAULT_ADMIN_USERNAME = "admin2"
DEFAULT_ADMIN_PASSWORD = os.getenv("SCHOOL_ADMIN_PASSWORD") or generate_secure_password(16)
DEFAULT_TEACHER_USERNAME = "staff2"
DEFAULT_TEACHER_PASSWORD = os.getenv("SCHOOL_STAFF_PASSWORD") or generate_secure_password(16)
DEFAULT_STUDENT_USERNAME = "student2"
DEFAULT_STUDENT_PASSWORD = os.getenv("SCHOOL_STUDENT_PASSWORD") or generate_secure_password(16)

# ── ID prefixes ──────────────────────────────────────────────────────────
STUDENT_ID_PREFIX = "SEC"
STUDENT_ID_LENGTH = 7  # e.g., SEC0001
