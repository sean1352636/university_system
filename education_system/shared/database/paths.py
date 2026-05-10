"""Canonical database paths for all education system databases.

Every shared service that needs to query across systems should import from
here rather than computing paths independently.
"""

from pathlib import Path

_SHARED_DIR = Path(__file__).resolve().parent.parent          # .../shared
_EDU_ROOT = _SHARED_DIR.parent                                # .../education_system

AUTH_DB = _SHARED_DIR / "data" / "db_files" / "auth.db"

SYSTEM_DB_PATHS = {
    "university": _EDU_ROOT / "university_system" / "data" / "db_files" / "student_records.db",
}

SYSTEM_ORDER = ["primary", "secondary", "college", "university"]

SYSTEM_LABELS = {
    "university": "University",
}
