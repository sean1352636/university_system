"""Default configuration for the shared authentication module."""

import os

# Session / security
SESSION_TIMEOUT_MINUTES = int(os.getenv("EDU_SESSION_TIMEOUT", "30"))
MAX_SESSIONS_PER_USER = int(os.getenv("EDU_MAX_SESSIONS", "5"))
MIN_PASSWORD_LENGTH = 12
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_DURATION_MINUTES = 15

# System keys and display names
SYSTEMS = {
    "university": "University Management System",
    "sixth_form": "Sixth Form College",
    "secondary": "Secondary School",
    "primary": "Primary School",
    "nursery": "Nursery",
    "apprenticeships": "Apprenticeships",
    "fe_college": "FE College",
}

# Roles each system recognises. The five school-shaped systems share one
# vocabulary; apprenticeships does not, because an apprenticeship has
# five parties round it (provider, tutor, learner, employer and the
# independent assessor) rather than the school's staff-and-pupil pair.
SYSTEM_ROLES = {
    "apprenticeships": (
        "admin", "staff", "apprentice", "employer", "end_point_assessor",
    ),
}

DEFAULT_SYSTEM_ROLES = ("admin", "staff", "teacher", "student", "parent")


def roles_for_system(system_key: str) -> tuple[str, ...]:
    """The role vocabulary *system_key* uses."""
    return SYSTEM_ROLES.get(system_key, DEFAULT_SYSTEM_ROLES)
