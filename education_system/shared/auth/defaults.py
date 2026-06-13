"""Default configuration for the shared authentication module."""

import os

# Session / security
SESSION_TIMEOUT_MINUTES = int(os.getenv("EDU_SESSION_TIMEOUT", "30"))
MAX_SESSIONS_PER_USER = int(os.getenv("EDU_MAX_SESSIONS", "5"))
MIN_PASSWORD_LENGTH = 12
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# System keys and display names
SYSTEMS = {
    "university": "University Management System",
    "college": "Sixth Form College",
    "school": "Secondary School",
    "primary": "Primary School",
    "nursery": "Nursery",
}
