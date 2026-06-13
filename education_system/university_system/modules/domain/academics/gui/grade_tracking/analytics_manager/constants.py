"""Constants and database connection setup for analytics manager."""

import os
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core import paths

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Database connection setup
_original_sqlite3_connect_grade = sqlite3.connect


def _patched_sqlite3_connect_grade(database, *args, **kwargs):
    try:
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name in (str(DEFAULT_DB_PATH), "student_grading_system.db"):
            return _original_sqlite3_connect_grade(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite3_connect_grade(database, *args, **kwargs)


sqlite3.connect = _patched_sqlite3_connect_grade

# Import the database connection
try:
    from education_system.university_system.infrastructure.database.db import get_connection
except ImportError:
    def get_connection():
        """Fallback database connection function"""
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        return sqlite3.connect(str(DEFAULT_DB_PATH))

# Global variables for grade systems
GRADE_SYSTEMS = {
    "letter": {
        "A+": 4.3, "A": 4.0, "A-": 3.7,
        "B+": 3.3, "B": 3.0, "B-": 2.7,
        "C+": 2.3, "C": 2.0, "C-": 1.7,
        "D+": 1.3, "D": 1.0, "D-": 0.7,
        "F": 0.0
    },
    "percentage": {
        "range": (0, 100),
        "conversion": {
        (90, 100): "A+", (85, 89.99): "A", (80, 84.99): "A-",
        (75, 79.99): "B+", (70, 74.99): "B", (65, 69.99): "B-",
        (60, 64.99): "C+", (55, 59.99): "C", (50, 54.99): "C-",
        (45, 49.99): "D+", (40, 44.99): "D", (35, 39.99): "D-",
        (0, 34.99): "F"
        }
    }
}
