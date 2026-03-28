"""Canonical database paths for all education system databases.

Every shared service that needs to query across systems should import from
here rather than computing paths independently.
"""

from pathlib import Path

_SHARED_DIR = Path(__file__).resolve().parent.parent          # .../shared
_EDU_ROOT = _SHARED_DIR.parent                                # .../education_system

AUTH_DB = _SHARED_DIR / "data" / "db_files" / "auth.db"

SYSTEM_DB_PATHS = {
    "primary": _EDU_ROOT / "primary_school" / "data" / "db_files" / "primary_school.db",
    "secondary": _EDU_ROOT / "secondary_school" / "data" / "db_files" / "secondary_school.db",
    "college": _EDU_ROOT / "college_system" / "data" / "db_files" / "sixthform.db",
    "university": _EDU_ROOT / "university_system" / "data" / "db_files" / "student_records.db",
}

SYSTEM_ORDER = ["primary", "secondary", "college", "university"]

SYSTEM_LABELS = {
    "primary": "Primary School",
    "secondary": "Secondary School",
    "college": "Sixth Form College",
    "university": "University",
}
