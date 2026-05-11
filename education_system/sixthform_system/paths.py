"""Centralised file/directory paths for the Sixth Form System.

All modules that need to read or write files inside this system should
import from here rather than building paths with ``Path(__file__).parent``.
That keeps the layout in one place — if the data/ directory moves or
needs to honour an environment override, only this module changes.

Environment overrides
---------------------
``EDU_SIXTHFORM_DATA_DIR``  Absolute path to use for the data directory
                           (default: ``<package>/data``).
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Package layout ──────────────────────────────────────────────────
PACKAGE_ROOT: Path = Path(__file__).resolve().parent

# ── Data directory ──────────────────────────────────────────────────
# Holds the local SQLite DB(s). Overridable via env so tests / installers
# can redirect it without touching code.
DATA_DIR: Path = Path(
    os.environ.get("EDU_SIXTHFORM_DATA_DIR")
    or (PACKAGE_ROOT / "data")
).resolve()

# ── Individual files ────────────────────────────────────────────────
STUDENTS_DB: Path = DATA_DIR / "sixthform.db"

# Enrolments live in the same SQLite file as students so cross-table
# joins / FK cascades work without coordinating two connections.
ENROLMENTS_DB: Path = STUDENTS_DB

# Courses share the same DB for the same reason — staff want to filter
# students by course / course by status etc.
COURSES_DB: Path = STUDENTS_DB

# Subjects (qualifications offered by the sixth form) are the source
# of truth for what student/course dropdowns can pick from.
SUBJECTS_DB: Path = STUDENTS_DB

# Class groups (teaching sets within a course) and their many-to-many
# membership table.
CLASS_GROUPS_DB: Path = STUDENTS_DB


def ensure_directories() -> None:
    """Create any directories listed above. Safe to call repeatedly."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


__all__ = [
    "PACKAGE_ROOT",
    "DATA_DIR",
    "STUDENTS_DB",
    "ENROLMENTS_DB",
    "COURSES_DB",
    "SUBJECTS_DB",
    "CLASS_GROUPS_DB",
    "ensure_directories",
]
