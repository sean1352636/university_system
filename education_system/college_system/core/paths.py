"""Centralized path definitions for the Sixth Form College Management System."""

from pathlib import Path

# Root directories
COLLEGE_SYSTEM_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = COLLEGE_SYSTEM_ROOT.parent

# Data directories
DATA_DIR = COLLEGE_SYSTEM_ROOT / "data"
DB_DIR = DATA_DIR / "db_files"
LOCALES_DIR = DATA_DIR / "locales"
CONFIG_DIR = DATA_DIR / "config"

# Logs
LOGS_DIR = COLLEGE_SYSTEM_ROOT / "logs"

# Database file
DB_FILE = DB_DIR / "sixthform.db"


def ensure_directories():
    """Create all required directories if they don't exist."""
    for d in (DB_DIR, LOCALES_DIR / "en", CONFIG_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
