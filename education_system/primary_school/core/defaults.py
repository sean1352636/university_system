"""Default configuration values for the Primary School Management System."""

import os

from education_system.shared.core.defaults import (
    LOCKOUT_DURATION_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    MIN_PASSWORD_LENGTH,
    SESSION_TIMEOUT_MINUTES,
    STAFF_ID_PREFIX,
    generate_secure_password,
    load_or_create_jwt_secret,
)
from education_system.primary_school.core.paths import DATA_DIR

# ── API settings ─────────────────────────────────────────────────────────
API_HOST = os.getenv("PRIMARY_SCHOOL_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("PRIMARY_SCHOOL_API_PORT", "5002"))
API_DEBUG = os.getenv("PRIMARY_SCHOOL_API_DEBUG", "false").lower() == "true"

# ── JWT Secret ───────────────────────────────────────────────────────────
_JWT_SECRET_FILE = DATA_DIR / ".jwt_secret"
JWT_SECRET = load_or_create_jwt_secret("PRIMARY_SCHOOL_JWT_SECRET", _JWT_SECRET_FILE)

# ── Default first-run credentials ────────────────────────────────────────
# Suffix "3" distinguishes primary school from other subsystems that share
# a single auth database (university=no suffix, college=1, secondary=2).
# Passwords are randomly generated per process when not set via env vars.
# They are only used on first run to seed the database — existing accounts
# are never overwritten.  Set the env vars for reproducible deployments.
DEFAULT_ADMIN_USERNAME = "admin3"
DEFAULT_ADMIN_PASSWORD = os.getenv("PRIMARY_ADMIN_PASSWORD") or generate_secure_password(16)
DEFAULT_TEACHER_USERNAME = "staff3"
DEFAULT_TEACHER_PASSWORD = os.getenv("PRIMARY_STAFF_PASSWORD") or generate_secure_password(16)
DEFAULT_STUDENT_USERNAME = "student3"
DEFAULT_STUDENT_PASSWORD = os.getenv("PRIMARY_STUDENT_PASSWORD") or generate_secure_password(16)
DEFAULT_PARENT_USERNAME = "parent3"
DEFAULT_PARENT_PASSWORD = os.getenv("PRIMARY_PARENT_PASSWORD") or generate_secure_password(16)

# ── ID prefixes ──────────────────────────────────────────────────────────
PUPIL_ID_PREFIX = "PRI"

# ── Year groups & key stages ─────────────────────────────────────────────
# Nursery / Pre-Reception is intentionally excluded; this system covers
# Reception through Year 6 only.
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
# KS1/KS2 national curriculum attainment descriptors.
ASSESSMENT_LEVELS = [
    "Emerging",
    "Developing",
    "Expected",
    "Greater Depth",
]

# EYFS Profile uses a different statutory scale (not "Greater Depth").
EYFS_PROFILE_LEVELS = [
    "Emerging",
    "Expected",
    "Exceeding",
]


__all__ = [
    # Re-exported from shared
    "LOCKOUT_DURATION_MINUTES",
    "MAX_LOGIN_ATTEMPTS",
    "MIN_PASSWORD_LENGTH",
    "SESSION_TIMEOUT_MINUTES",
    "STAFF_ID_PREFIX",
    "generate_secure_password",
    "load_or_create_jwt_secret",
    # API
    "API_HOST",
    "API_PORT",
    "API_DEBUG",
    "JWT_SECRET",
    # Credentials
    "DEFAULT_ADMIN_USERNAME",
    "DEFAULT_ADMIN_PASSWORD",
    "DEFAULT_TEACHER_USERNAME",
    "DEFAULT_TEACHER_PASSWORD",
    "DEFAULT_STUDENT_USERNAME",
    "DEFAULT_STUDENT_PASSWORD",
    "DEFAULT_PARENT_USERNAME",
    "DEFAULT_PARENT_PASSWORD",
    # Domain constants
    "PUPIL_ID_PREFIX",
    "YEAR_GROUPS",
    "KEY_STAGES",
    "ASSESSMENT_LEVELS",
    "EYFS_PROFILE_LEVELS",
]
