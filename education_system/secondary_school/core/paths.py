"""Centralized path definitions for the Secondary School Management System."""

from education_system.shared.core.paths import get_system_paths

_paths = get_system_paths(__file__, "secondary_school.db")

# Re-export standard paths for backward compatibility
SCHOOL_SYSTEM_ROOT = _paths.system_root
PROJECT_ROOT = _paths.project_root
DATA_DIR = _paths.data_dir
DB_DIR = _paths.db_dir
DB_FILE = _paths.db_file
CONFIG_DIR = _paths.config_dir
LOGS_DIR = _paths.logs_dir


def ensure_directories():
    """Create all required directories if they don't exist."""
    _paths.ensure_directories()
