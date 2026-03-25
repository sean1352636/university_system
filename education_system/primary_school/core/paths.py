"""File-system paths for the Primary School Management System."""

from education_system.shared.core.paths import get_system_paths

_paths = get_system_paths(__file__, "primary_school.db")

# Re-export standard paths for backward compatibility
PRIMARY_SCHOOL_ROOT = _paths.system_root
DATA_DIR = _paths.data_dir
DB_DIR = _paths.db_dir
DB_FILE = _paths.db_file
CONFIG_DIR = _paths.config_dir
LOGS_DIR = _paths.logs_dir


def ensure_directories():
    """Create required directories if they do not exist."""
    _paths.ensure_directories()


ensure_directories()
