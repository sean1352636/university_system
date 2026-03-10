"""Centralized path definitions for the Secondary School Management System."""

from pathlib import Path

# Root directories
SCHOOL_SYSTEM_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SCHOOL_SYSTEM_ROOT.parent

# Data directories
DATA_DIR = SCHOOL_SYSTEM_ROOT / "data"
DB_DIR = DATA_DIR / "db_files"
CONFIG_DIR = DATA_DIR / "config"

# Logs
LOGS_DIR = SCHOOL_SYSTEM_ROOT / "logs"

# Database file
DB_FILE = DB_DIR / "secondary_school.db"


def ensure_directories():
    """Create all required directories if they don't exist."""
    for d in (DB_DIR, CONFIG_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
