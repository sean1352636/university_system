"""Centralised filesystem path helpers for the program package.

This module exposes absolute :class:`pathlib.Path` objects for the key
directories used across the application (databases, logs, email assets,
chatbot resources, etc.).  Importing from here keeps the rest of the
codebase agnostic to the current working directory and ensures all
runtime artefacts end up inside ``program/data`` rather than the user's
cwd.

IMPORTANT: Directories are NOT created on import. Call ensure_directories()
during application initialization to create the directory structure.

This module is in the core package and has no dependencies on infrastructure
or modules, preventing circular imports.
"""

from __future__ import annotations

from pathlib import Path
import sys


def _ensure(dir_path: Path) -> Path:
    """Create *dir_path* (and parents) if it does not already exist."""
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


# `.../systems/university/infrastructure/paths.py` -> the package root is one
# level up from infrastructure/ to reach the university package directory.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# Useful aliases
BASE_DIR: Path = PROJECT_ROOT  # For backward compatibility
UNIVERSITY_SYSTEM_DIR: Path = PROJECT_ROOT  # Explicit name

# The actual repository root: university -> systems -> education_system -> <root>
REPO_ROOT: Path = PROJECT_ROOT.parents[2]

# Runtime state lives in one gitignored tree at the repository root, never inside
# the package (ADR 0018). Writing under PROJECT_ROOT is what scattered databases,
# logs and backups through the source tree in the old layout.
VAR_DIR: Path = REPO_ROOT / "var"

# Useful high-level anchors used by other modules
# SRC_DIR is kept for backward compatibility but prefer using modules/shared
SRC_DIR: Path = PROJECT_ROOT / "modules"
DATA_DIR: Path = VAR_DIR / "data" / "university"

# Database paths
DB_DIR: Path = DATA_DIR / "db_files"
DB_FILES_DIR: Path = DB_DIR  # Alias for clarity
DEFAULT_DB_PATH: Path = DB_DIR / "student_records.db"

# Backup metadata file
BACKUP_METADATA_FILE: Path = DATA_DIR / "backup_metadata.json"

# Logging paths - under var/, not inside the package
LOG_DIR: Path = VAR_DIR / "logs" / "university"

# Backup paths - organised by type under a single top-level directory
BACKUP_DIR: Path = VAR_DIR / "backups" / "university"
BACKUP_DATABASE_DIR: Path = BACKUP_DIR / "database"
BACKUP_FILES_DIR: Path = BACKUP_DIR / "files"
BACKUP_ATTENDANCE_DIR: Path = BACKUP_DIR / "attendance"
BACKUP_FINANCE_DIR: Path = BACKUP_DIR / "finance"
BACKUP_LIBRARY_DIR: Path = BACKUP_DIR / "library"
BACKUP_HEALTH_DIR: Path = BACKUP_DIR / "health"
BACKUP_SETTINGS_DIR: Path = BACKUP_DIR / "settings"
BACKUP_CALENDAR_DIR: Path = BACKUP_DIR / "calendar"
BACKUP_SUBMISSIONS_DIR: Path = BACKUP_DIR / "submissions"
# Backward-compatible aliases
DB_BACKUPS_DIR: Path = BACKUP_DATABASE_DIR

# Export paths - organised under data for consistent hierarchy
EXPORTS_DIR: Path = DATA_DIR / "exports"
EXPORTS_DATABASE_DIR: Path = EXPORTS_DIR / "database"
EXPORTS_PDF_DIR: Path = EXPORTS_DIR / "pdf"
EXPORTS_TICKETS_DIR: Path = EXPORTS_DIR / "tickets"
EXPORTS_SUBMISSIONS_DIR: Path = EXPORTS_DIR / "submissions"
EXPORTS_REPORTS_DIR: Path = EXPORTS_DIR / "reports"
EXPORTS_BAKERY_DIR: Path = EXPORTS_DIR / "bakery"
# Backward-compatible alias
DB_EXPORTS_DIR: Path = DB_DIR / "exports"

# Reports paths under data
REPORTS_DIR: Path = DATA_DIR / "reports"
REPORT_TEMPLATES_DIR: Path = DATA_DIR / "reports_templates"
REPORT_CACHE_DIR: Path = DATA_DIR / "report_cache"
SCHEDULED_REPORTS_FILE: Path = REPORTS_DIR / "scheduled_reports.json"

# Email subsystem paths - consolidated to templates/email
EMAIL_DATA_DIR: Path = DATA_DIR / "email"
EMAIL_TEMPLATES_DIR: Path = PROJECT_ROOT / "templates" / "email"

# Configuration directory
CONFIG_DIR: Path = DATA_DIR / "config"

# Canonical config/report/template files (previously hardcoded at many call sites)
SAVED_REPORTS_FILE: Path = CONFIG_DIR / "saved_reports.json"
API_SERVER_CONFIG_FILE: Path = CONFIG_DIR / "api_server_config.json"
LICENSES_FILE: Path = CONFIG_DIR / "licenses.json"
DR_CONFIG_FILE: Path = CONFIG_DIR / "dr_config.json"
MAINTENANCE_WINDOWS_FILE: Path = CONFIG_DIR / "maintenance_windows.json"
FINANCE_GUI_SETTINGS_FILE: Path = CONFIG_DIR / "finance_gui_settings.json"


def _resolve_email_config_file() -> Path:
    """Resolve the canonical email config path.

    Matches the resolution order in `education_system.platform.integrations.email.config`:
      1. shared/data/config/email_config.json (canonical)
      2. university_system/data/config/email_config.json (legacy fallback)
      3. shared path as the default for fresh installs (save-path target).
    """
    shared_candidate = PROJECT_ROOT.parent.parent / "shared" / "data" / "config" / "email_config.json"
    legacy_candidate = CONFIG_DIR / "email_config.json"
    if shared_candidate.exists():
        return shared_candidate
    if legacy_candidate.exists():
        return legacy_candidate
    return shared_candidate


EMAIL_CONFIG_FILE: Path = _resolve_email_config_file()
EMAIL_CONFIG_PATH: Path = EMAIL_CONFIG_FILE

# Activity logger configuration lives in config data.
LOGGER_CONFIG_DIR: Path = CONFIG_DIR

# Chatbot assets (uploads/models) live under a dedicated namespace.
CHATBOT_DATA_DIR: Path = DATA_DIR / "chatbot"
CHATBOT_UPLOAD_DIR: Path = CHATBOT_DATA_DIR / "uploads"
CHATBOT_MODELS_DIR: Path = CHATBOT_DATA_DIR / "models"
CHATBOT_CONFIG_PATH: Path = LOGGER_CONFIG_DIR / "chatbot_config.json"

# QR codes directory
QR_CODES_DIR: Path = DATA_DIR / "qr_codes"

# Analytics directories - consolidated under data/analytics
ANALYTICS_DIR: Path = DATA_DIR / "analytics"
ANALYTICS_PLOTS_DIR: Path = ANALYTICS_DIR / "plots"
# Analytics reports now under main reports directory for consolidation
ANALYTICS_REPORTS_DIR: Path = REPORTS_DIR / "analytics"

# Submissions directory - for assignment submissions
SUBMISSIONS_DIR: Path = DATA_DIR / "submissions"

# Uploads directory - for general file uploads
UPLOAD_DIR: Path = DATA_DIR / "uploads"
UPLOADS_DIR: Path = UPLOAD_DIR  # Alias for consistency

# Temporary files directory - for temporary files (instead of /tmp)
TEMP_DIR: Path = DATA_DIR / "temp"

# Templates directory - unified location at project root
TEMPLATES_DIR: Path = PROJECT_ROOT / "templates"
EMAIL_TEMPLATE_MAPPING_FILE: Path = TEMPLATES_DIR / "email_template_mapping.json"
ASSIGNMENT_TEMPLATES_DIR: Path = TEMPLATES_DIR / "assignments"
# Shipped, read-only backup-template seeds; user-saved templates go to data/ (USER_BACKUP_TEMPLATES_DIR)
BACKUP_TEMPLATES_DIR: Path = TEMPLATES_DIR / "backup_templates"
USER_BACKUP_TEMPLATES_DIR: Path = DATA_DIR / "backup_templates"
MEDICAL_TEMPLATES_DIR: Path = TEMPLATES_DIR / "medical_templates"
TICKET_TEMPLATES_DIR: Path = TEMPLATES_DIR / "ticket_templates"
COURSE_EVALUATION_TEMPLATES_DIR: Path = TEMPLATES_DIR / "course_evaluation"

# Email reminder templates
EMAIL_REMINDER_TEMPLATES_DIR: Path = EMAIL_TEMPLATES_DIR / "reminders"

# Finance templates directory - for finance seed/template data
FINANCE_TEMPLATES_DIR: Path = TEMPLATES_DIR / "finance_templates"

# NLTK data directory - for natural language processing data
NLTK_DATA_DIR: Path = DATA_DIR / "nltk_data"

# Student documents directory - for student document storage
STUDENT_DOCUMENTS_DIR: Path = DATA_DIR / "student_documents"

# EXPORTS_DIR is now defined above under "Export paths"

# Charts directory - for chart outputs
CHARTS_DIR: Path = REPORTS_DIR / "charts"

# Locales directory - for internationalization translation files
LOCALES_DIR: Path = DATA_DIR / "locales"
LANGUAGE_CONFIG_PATH: Path = CONFIG_DIR / "language_config.json"

# Assets directory - for static assets
ASSETS_DIR: Path = PROJECT_ROOT / "assets"

# Scripts directory - for utility scripts
SCRIPTS_DIR: Path = PROJECT_ROOT / "scripts"


def ensure_directories() -> None:
    """
    Explicitly create all required directories.

    This function should be called during application bootstrap/initialization,
    not at import time. This keeps imports side-effect free.
    """
    shim = sys.modules.get("education_system.systems.university.infrastructure.paths")
    ensure_fn = getattr(shim, "_ensure", _ensure)

    ensure_fn(DATA_DIR)
    ensure_fn(DB_DIR)
    ensure_fn(LOG_DIR)
    # Backup subdirectories
    ensure_fn(BACKUP_DATABASE_DIR)
    ensure_fn(BACKUP_FILES_DIR)
    ensure_fn(BACKUP_ATTENDANCE_DIR)
    ensure_fn(BACKUP_FINANCE_DIR)
    ensure_fn(BACKUP_LIBRARY_DIR)
    ensure_fn(BACKUP_HEALTH_DIR)
    ensure_fn(BACKUP_SETTINGS_DIR)
    ensure_fn(BACKUP_CALENDAR_DIR)
    # Export subdirectories
    ensure_fn(EXPORTS_DATABASE_DIR)
    ensure_fn(EXPORTS_PDF_DIR)
    ensure_fn(EXPORTS_TICKETS_DIR)
    ensure_fn(EXPORTS_SUBMISSIONS_DIR)
    ensure_fn(EXPORTS_REPORTS_DIR)
    ensure_fn(EXPORTS_BAKERY_DIR)
    ensure_fn(REPORTS_DIR)
    ensure_fn(REPORT_TEMPLATES_DIR)
    ensure_fn(REPORT_CACHE_DIR)
    ensure_fn(EMAIL_DATA_DIR)
    ensure_fn(EMAIL_TEMPLATES_DIR)
    ensure_fn(LOGGER_CONFIG_DIR)
    ensure_fn(CHATBOT_DATA_DIR)
    ensure_fn(CHATBOT_UPLOAD_DIR)
    ensure_fn(CHATBOT_MODELS_DIR)
    ensure_fn(QR_CODES_DIR)
    ensure_fn(ANALYTICS_DIR)
    ensure_fn(ANALYTICS_PLOTS_DIR)
    ensure_fn(ANALYTICS_REPORTS_DIR)
    ensure_fn(SUBMISSIONS_DIR)
    ensure_fn(UPLOAD_DIR)
    ensure_fn(TEMPLATES_DIR)
    ensure_fn(ASSIGNMENT_TEMPLATES_DIR)
    ensure_fn(BACKUP_TEMPLATES_DIR)
    ensure_fn(USER_BACKUP_TEMPLATES_DIR)
    ensure_fn(MEDICAL_TEMPLATES_DIR)
    ensure_fn(TICKET_TEMPLATES_DIR)
    ensure_fn(EMAIL_REMINDER_TEMPLATES_DIR)
    ensure_fn(FINANCE_TEMPLATES_DIR)
    ensure_fn(NLTK_DATA_DIR)
    ensure_fn(STUDENT_DOCUMENTS_DIR)
    ensure_fn(TEMP_DIR)
    ensure_fn(CONFIG_DIR)
    ensure_fn(CHARTS_DIR)
    ensure_fn(LOCALES_DIR)



__all__ = [
    "BASE_DIR",
    "UNIVERSITY_SYSTEM_DIR",
    "PROJECT_ROOT",
    "REPO_ROOT",
    "SRC_DIR",
    "DATA_DIR",
    "DB_DIR",
    "DB_FILES_DIR",
    "DB_EXPORTS_DIR",
    "DEFAULT_DB_PATH",
    "DB_BACKUPS_DIR",
    "BACKUP_METADATA_FILE",
    "LOG_DIR",
    "BACKUP_DIR",
    "BACKUP_DATABASE_DIR",
    "BACKUP_FILES_DIR",
    "BACKUP_ATTENDANCE_DIR",
    "BACKUP_FINANCE_DIR",
    "BACKUP_LIBRARY_DIR",
    "BACKUP_HEALTH_DIR",
    "BACKUP_SETTINGS_DIR",
    "BACKUP_CALENDAR_DIR",
    "EXPORTS_DATABASE_DIR",
    "EXPORTS_PDF_DIR",
    "EXPORTS_TICKETS_DIR",
    "EXPORTS_SUBMISSIONS_DIR",
    "EXPORTS_REPORTS_DIR",
    "EXPORTS_BAKERY_DIR",
    "REPORTS_DIR",
    "REPORT_TEMPLATES_DIR",
    "REPORT_CACHE_DIR",
    "EMAIL_DATA_DIR",
    "EMAIL_CONFIG_PATH",
    "EMAIL_TEMPLATES_DIR",
    "CONFIG_DIR",
    "SAVED_REPORTS_FILE",
    "API_SERVER_CONFIG_FILE",
    "LICENSES_FILE",
    "DR_CONFIG_FILE",
    "MAINTENANCE_WINDOWS_FILE",
    "FINANCE_GUI_SETTINGS_FILE",
    "SCHEDULED_REPORTS_FILE",
    "EMAIL_TEMPLATE_MAPPING_FILE",
    "EMAIL_CONFIG_FILE",
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
    "UPLOAD_DIR",
    "UPLOADS_DIR",
    "TEMP_DIR",
    "TEMPLATES_DIR",
    "ASSIGNMENT_TEMPLATES_DIR",
    "BACKUP_TEMPLATES_DIR",
    "USER_BACKUP_TEMPLATES_DIR",
    "MEDICAL_TEMPLATES_DIR",
    "TICKET_TEMPLATES_DIR",
    "COURSE_EVALUATION_TEMPLATES_DIR",
    "EMAIL_REMINDER_TEMPLATES_DIR",
    "FINANCE_TEMPLATES_DIR",
    "NLTK_DATA_DIR",
    "STUDENT_DOCUMENTS_DIR",
    "EXPORTS_DIR",
    "CHARTS_DIR",
    "LOCALES_DIR",
    "LANGUAGE_CONFIG_PATH",
    "ASSETS_DIR",
    "SCRIPTS_DIR",
    "ensure_directories",
]
