"""Centralised filesystem path helpers for the program package.

This module exposes absolute :class:`pathlib.Path` objects for the key
directories used across the application (databases, logs, email assets,
chatbot resources, etc.).  Importing from here keeps the rest of the
codebase agnostic to the current working directory and ensures all
runtime artefacts end up inside ``program/data`` rather than the user's
cwd.

IMPORTANT: Directories are NOT created on import. Call ensure_directories()
during application initialization to create the directory structure.
"""

from __future__ import annotations

from pathlib import Path


def _ensure(dir_path: Path) -> Path:
    """Create *dir_path* (and parents) if it does not already exist."""
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


# ``.../university_system/modules/shared/constants/paths.py`` -> project root is three
# levels up from this file to reach university_system directory.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]

# Repository root - same as project root (university_system folder)
REPO_ROOT: Path = PROJECT_ROOT

# Useful high-level anchors used by other modules
# SRC_DIR is kept for backward compatibility but prefer using modules/shared
SRC_DIR: Path = PROJECT_ROOT / "modules"
DATA_DIR: Path = PROJECT_ROOT / "data"

# Database paths
DB_DIR: Path = DATA_DIR / "db_files"
DB_EXPORTS_DIR: Path = DB_DIR / "exports"
DEFAULT_DB_PATH: Path = DB_DIR / "student_records.db"

# Logging paths - centralized location within university_system directory
LOG_DIR: Path = PROJECT_ROOT / "logs"

# Backup paths
BACKUP_DIR: Path = PROJECT_ROOT / "backups"

# Reports paths - centralized in templates directory
REPORTS_DIR: Path = PROJECT_ROOT / "data" / "reports"
REPORT_TEMPLATES_DIR: Path = PROJECT_ROOT / "templates" / "reports_templates"
REPORT_CACHE_DIR: Path = PROJECT_ROOT / "data" / "report_cache"

# Email subsystem paths - consolidated to templates/email
EMAIL_DATA_DIR: Path = DATA_DIR / "email"
EMAIL_CONFIG_PATH: Path = EMAIL_DATA_DIR / "email_config.json"
EMAIL_TEMPLATES_DIR: Path = PROJECT_ROOT / "templates" / "email"

# Activity logger configuration lives alongside other shared config files.
# Consolidated to modules/shared/config
LOGGER_CONFIG_DIR: Path = PROJECT_ROOT / "modules" / "shared" / "config"

# Chatbot assets (uploads/models) live under a dedicated namespace.
CHATBOT_DATA_DIR: Path = DATA_DIR / "chatbot"
CHATBOT_UPLOAD_DIR: Path = CHATBOT_DATA_DIR / "uploads"
CHATBOT_MODELS_DIR: Path = CHATBOT_DATA_DIR / "models"
CHATBOT_CONFIG_PATH: Path = LOGGER_CONFIG_DIR / "chatbot_config.json"

# QR codes directory
QR_CODES_DIR: Path = PROJECT_ROOT / "qr_codes"

# Analytics directories - consolidated under data/analytics
ANALYTICS_DIR: Path = DATA_DIR / "analytics"
ANALYTICS_PLOTS_DIR: Path = ANALYTICS_DIR / "plots"
ANALYTICS_REPORTS_DIR: Path = ANALYTICS_DIR / "reports"

# Submissions directory - for assignment submissions
SUBMISSIONS_DIR: Path = DATA_DIR / "submissions"

# Templates directory - unified location at project root
TEMPLATES_DIR: Path = PROJECT_ROOT / "templates"
ASSIGNMENT_TEMPLATES_DIR: Path = TEMPLATES_DIR / "assignments"
BACKUP_TEMPLATES_DIR: Path = TEMPLATES_DIR / "backup_templates"

# Email reminder templates
EMAIL_REMINDER_TEMPLATES_DIR: Path = EMAIL_TEMPLATES_DIR / "reminders"

# NLTK data directory - for natural language processing data
NLTK_DATA_DIR: Path = DATA_DIR / "nltk_data"


def ensure_directories() -> None:
    """
    Explicitly create all required directories.

    This function should be called during application bootstrap/initialization,
    not at import time. This keeps imports side-effect free.
    """
    _ensure(DATA_DIR)
    _ensure(DB_DIR)
    _ensure(DB_EXPORTS_DIR)
    _ensure(LOG_DIR)
    _ensure(BACKUP_DIR)
    _ensure(REPORTS_DIR)
    _ensure(REPORT_TEMPLATES_DIR)
    _ensure(REPORT_CACHE_DIR)
    _ensure(EMAIL_DATA_DIR)
    _ensure(EMAIL_TEMPLATES_DIR)
    _ensure(LOGGER_CONFIG_DIR)
    _ensure(CHATBOT_DATA_DIR)
    _ensure(CHATBOT_UPLOAD_DIR)
    _ensure(CHATBOT_MODELS_DIR)
    _ensure(QR_CODES_DIR)
    _ensure(ANALYTICS_DIR)
    _ensure(ANALYTICS_PLOTS_DIR)
    _ensure(ANALYTICS_REPORTS_DIR)
    _ensure(SUBMISSIONS_DIR)
    _ensure(TEMPLATES_DIR)
    _ensure(ASSIGNMENT_TEMPLATES_DIR)
    _ensure(BACKUP_TEMPLATES_DIR)
    _ensure(EMAIL_REMINDER_TEMPLATES_DIR)
    _ensure(NLTK_DATA_DIR)

__all__ = [
    "PROJECT_ROOT",
    "REPO_ROOT",
    "SRC_DIR",
    "DATA_DIR",
    "DB_DIR",
    "DB_EXPORTS_DIR",
    "DEFAULT_DB_PATH",
    "LOG_DIR",
    "BACKUP_DIR",
    "REPORTS_DIR",
    "REPORT_TEMPLATES_DIR",
    "REPORT_CACHE_DIR",
    "EMAIL_DATA_DIR",
    "EMAIL_CONFIG_PATH",
    "EMAIL_TEMPLATES_DIR",
    "LOGGER_CONFIG_DIR",
    "CHATBOT_DATA_DIR",
    "CHATBOT_UPLOAD_DIR",
    "CHATBOT_MODELS_DIR",
    "CHATBOT_CONFIG_PATH",
    "QR_CODES_DIR",
    "ANALYTICS_DIR",
    "ANALYTICS_PLOTS_DIR",
    "ANALYTICS_REPORTS_DIR",
    "SUBMISSIONS_DIR",
    "TEMPLATES_DIR",
    "ASSIGNMENT_TEMPLATES_DIR",
    "BACKUP_TEMPLATES_DIR",
    "EMAIL_REMINDER_TEMPLATES_DIR",
    "NLTK_DATA_DIR",
    "ensure_directories",
]
