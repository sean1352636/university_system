"""Default configuration values for the Primary School Management System."""

import os
import secrets
import string

# ── API settings ──────────────────────────────────────────────────────────
API_HOST = os.getenv("PRIMARY_SCHOOL_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("PRIMARY_SCHOOL_API_PORT", "5002"))
API_DEBUG = os.getenv("PRIMARY_SCHOOL_API_DEBUG", "false").lower() == "true"
JWT_SECRET = os.getenv("PRIMARY_SCHOOL_JWT_SECRET", secrets.token_hex(32))

# ── Session / security ───────────────────────────────────────────────────
SESSION_TIMEOUT_MINUTES = 30
MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# ── Default first-run credentials ─────────────────────────────────────────
DEFAULT_ADMIN_USERNAME = "admin3"
DEFAULT_ADMIN_PASSWORD = "admin1234"
DEFAULT_TEACHER_USERNAME = "staff3"
DEFAULT_TEACHER_PASSWORD = "staff1234"
DEFAULT_STUDENT_USERNAME = "student3"
DEFAULT_STUDENT_PASSWORD = "student1234"
DEFAULT_PARENT_USERNAME = "parent"
DEFAULT_PARENT_PASSWORD = "Parent@123"

# ── ID prefixes ───────────────────────────────────────────────────────────
PUPIL_ID_PREFIX = "PRI"
STAFF_ID_PREFIX = "STF"

# ── Year groups & key stages ──────────────────────────────────────────────
YEAR_GROUPS = ["Reception", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "Year 6"]

KEY_STAGES = {
    "Reception": "EYFS",
    "Year 1": "KS1",
    "Year 2": "KS1",
    "Year 3": "KS2",
    "Year 4": "KS2",
    "Year 5": "KS2",
    "Year 6": "KS2",
}

# ── Assessment descriptors ───────────────────────────────────────────────
ASSESSMENT_LEVELS = [
    "Emerging",
    "Developing",
    "Expected",
    "Greater Depth",
]

EYFS_PROFILE_LEVELS = [
    "Emerging",
    "Expected",
    "Exceeding",
]


def generate_password(length: int = 12) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.isupper() for c in pwd) and any(c.islower() for c in pwd)
                and any(c.isdigit() for c in pwd) and any(c in "!@#$%" for c in pwd)):
            return pwd
