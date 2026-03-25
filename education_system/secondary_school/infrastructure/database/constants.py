"""Database constants and configuration for the Secondary School system."""

from education_system.shared.database.constants import (
    CONNECTION_TIMEOUT,
    BUSY_TIMEOUT,
    POOL_MIN_SIZE,
    POOL_MAX_SIZE,
    PRAGMAS,
    TERMS,
)

# UK GCSE grade scale (9-1 reformed): (min_score, grade_description)
GCSE_GRADE_SCALE = {
    "9": (90, 100),
    "8": (80, 89),
    "7": (70, 79),
    "6": (60, 69),
    "5": (50, 59),
    "4": (40, 49),
    "3": (30, 39),
    "2": (20, 29),
    "1": (10, 19),
    "U": (0, 9),
}

# Key Stages
KEY_STAGES = ("KS3", "KS4")
YEAR_GROUPS = ("7", "8", "9", "10", "11")
KS3_YEARS = ("7", "8", "9")
KS4_YEARS = ("10", "11")

# Attendance statuses
ATTENDANCE_STATUSES = ("present", "absent", "late", "authorised_absent", "unauthorised_absent")

# Behaviour categories
BEHAVIOUR_TYPES = ("positive", "negative")
BEHAVIOUR_CATEGORIES = (
    "achievement", "effort", "homework", "kindness",  # positive
    "disruption", "late", "uniform", "homework_missing", "bullying", "defiance",  # negative
)

SANCTION_LEVELS = ("verbal_warning", "detention", "isolation", "suspension", "exclusion")
REWARD_TYPES = ("merit", "commendation", "prize", "certificate")
