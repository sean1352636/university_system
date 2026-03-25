"""Default configuration values for the Sixth Form College System."""

import os
from pathlib import Path

from education_system.shared.core.defaults import (  # noqa: F401
    LOCKOUT_DURATION_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    MIN_PASSWORD_LENGTH,
    SESSION_TIMEOUT_MINUTES,
    STAFF_ID_PREFIX,
    generate_secure_password,
    load_or_create_jwt_secret,
)

# ── API settings ─────────────────────────────────────────────────────────
API_HOST = os.getenv("COLLEGE_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("COLLEGE_API_PORT", "5000"))
API_DEBUG = os.getenv("COLLEGE_API_DEBUG", "false").lower() == "true"

# ── JWT Secret ───────────────────────────────────────────────────────────
JWT_EXPIRY_HOURS = int(os.getenv("COLLEGE_JWT_EXPIRY", "24"))
_JWT_SECRET_FILE = Path(__file__).resolve().parent.parent / "data" / ".jwt_secret"
JWT_SECRET = load_or_create_jwt_secret("COLLEGE_JWT_SECRET", _JWT_SECRET_FILE)

# ── Default first-run credentials ────────────────────────────────────────
DEFAULT_ADMIN_USERNAME = "admin1"
DEFAULT_ADMIN_PASSWORD = os.getenv("COLLEGE_ADMIN_PASSWORD") or generate_secure_password(16)
DEFAULT_TEACHER_USERNAME = "staff1"
DEFAULT_TEACHER_PASSWORD = os.getenv("COLLEGE_STAFF_PASSWORD") or generate_secure_password(16)
DEFAULT_STUDENT_USERNAME = "student1"
DEFAULT_STUDENT_PASSWORD = os.getenv("COLLEGE_STUDENT_PASSWORD") or generate_secure_password(16)

# ── ID prefixes ──────────────────────────────────────────────────────────
STUDENT_ID_PREFIX = "SFC"
STUDENT_ID_LENGTH = 7  # e.g., SFC0001
