"""File-system paths for the Primary School Management System.

Path constants are safe to import without side effects — directories are
**not** created on import.  Call :func:`ensure_directories` once at
application startup (CLI ``main()``, GUI ``run()``, or API init) before
any I/O that relies on these paths.
"""

from education_system.shared.core.paths import get_system_paths

_paths = get_system_paths(__file__, "primary_school.db")

# ── Directories ────────────────────────────────────────────────────────
PRIMARY_SCHOOL_ROOT = _paths.system_root
DATA_DIR = _paths.data_dir
DB_DIR = _paths.db_dir
CONFIG_DIR = _paths.config_dir
LOGS_DIR = _paths.logs_dir

# ── Files ──────────────────────────────────────────────────────────────
DB_FILE = _paths.db_file


def ensure_directories() -> None:
    """Create all required directories if they do not exist.

    Thin wrapper around :meth:`SystemPaths.ensure_directories` so that
    callers only need to import this module rather than reaching into the
    shared paths infrastructure directly.
    """
    _paths.ensure_directories()


__all__ = [
    "PRIMARY_SCHOOL_ROOT",
    "DATA_DIR",
    "DB_DIR",
    "DB_FILE",
    "CONFIG_DIR",
    "LOGS_DIR",
    "ensure_directories",
]
