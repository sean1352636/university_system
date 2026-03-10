"""File-system paths for the Primary School Management System."""

from pathlib import Path

PRIMARY_SCHOOL_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PRIMARY_SCHOOL_ROOT / "data"
DB_FILE = DATA_DIR / "db_files" / "primary_school.db"
DB_DIR = DATA_DIR / "db_files"
CONFIG_DIR = DATA_DIR / "config"
LOGS_DIR = PRIMARY_SCHOOL_ROOT / "logs"


def ensure_directories():
    """Create required directories if they do not exist."""
    for d in (DB_DIR, CONFIG_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


ensure_directories()
