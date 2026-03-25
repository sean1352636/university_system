"""Database constants and configuration for the Sixth Form College system."""

from education_system.shared.database.constants import (
    CONNECTION_TIMEOUT,
    BUSY_TIMEOUT,
    POOL_MIN_SIZE,
    POOL_MAX_SIZE,
    PRAGMAS,
    TERMS,
)

# UK A-Level grade scale: (min_score, max_score, ucas_tariff_points)
GRADE_SCALE = {
    "A*": (90, 100, 56),
    "A":  (80, 89, 48),
    "B":  (70, 79, 40),
    "C":  (60, 69, 32),
    "D":  (50, 59, 24),
    "E":  (40, 49, 16),
    "U":  (0, 39, 0),
}

# BTEC grade scale: (min_score, max_score, ucas_tariff_points)
BTEC_GRADE_SCALE = {
    "D*": (90, 100, 56),
    "D":  (75, 89, 48),
    "M":  (55, 74, 32),
    "P":  (40, 54, 16),
    "U":  (0, 39, 0),
}

QUALIFICATION_TYPES = ("A-Level", "BTEC", "T-Level", "GCSE", "Core Maths", "EPQ")
YEAR_GROUPS = ("12", "13")

# Attendance statuses
ATTENDANCE_STATUSES = ("present", "absent", "late", "excused")
