"""Default configuration for the shared authentication module."""

import os

# Session / security
SESSION_TIMEOUT_MINUTES = int(os.getenv("EDU_SESSION_TIMEOUT", "30"))
MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# System keys and display names
SYSTEMS = {
    "university": "University Management System",
    "college": "Sixth Form College",
    "school": "Secondary School",
    "primary": "Primary School",
}
