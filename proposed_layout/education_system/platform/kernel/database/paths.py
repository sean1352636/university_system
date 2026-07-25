"""Canonical database paths for all education system databases.

Every shared service that needs to query across systems should import from
here rather than computing paths independently.
"""

from pathlib import Path

_SHARED_DIR = Path(__file__).resolve().parent.parent          # .../shared
_EDU_ROOT = _SHARED_DIR.parent                                # .../education_system

AUTH_DB = _SHARED_DIR / "data" / "db_files" / "auth.db"

from education_system.systems.secondary.infrastructure.paths import PUPILS_DB as _SECONDARY_DB

SYSTEM_DB_PATHS = {
    "nursery":    _EDU_ROOT / "nursery_system"      / "data" / "nursery.db",
    "primary":    _EDU_ROOT / "primarysch_system"   / "data" / "primary.db",
    "secondary":  _SECONDARY_DB,
    "sixth_form": _EDU_ROOT / "sixthform_system"    / "data" / "sixthform.db",
    "university": _EDU_ROOT / "post_18" / "university_system"   / "data" / "db_files" / "student_records.db",
}

SYSTEM_ORDER = ["nursery", "primary", "secondary", "sixth_form", "university"]

SYSTEM_LABELS = {
    "nursery":    "Nursery",
    "primary":    "Primary School",
    "secondary":  "Secondary School",
    "sixth_form": "Sixth Form College",
    "university": "University",
}
