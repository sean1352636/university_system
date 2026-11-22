"""University paths.

Part of :mod:`education_system.paths`; import names from the package, not from here.
"""

from __future__ import annotations

from pathlib import Path

from education_system.paths.core import (
    BACKUP_DIR,
    REPO_ROOT,
    UNIVERSITY_PROJECT_ROOT,
    VAR_DIR,
)
from education_system.paths.platform_shared import (
    PLATFORM_EMAIL_CONFIG_PATH,
    PLATFORM_SECRETS_DIR,
)

def _university_resolve_email_config_file() -> Path:
    """Resolve the canonical email config path.

    Matches the resolution order in
    ``education_system.platform.integrations.email.config``:

      1. the platform-wide config — canonical, and what ``save_email_config``
         writes to;
      2. the per-university config, for installs predating the move to a
         shared location;
      3. the platform path as the default for fresh installs.

    This previously pointed at ``<education_system>/shared/data/config/``,
    which has not existed since the ADR 0018 move. That candidate could never
    resolve, so the university read a non-existent file and reported email as
    unconfigured even when the platform config was present.
    """
    if PLATFORM_EMAIL_CONFIG_PATH.exists():
        return PLATFORM_EMAIL_CONFIG_PATH
    legacy_candidate = UNIVERSITY_CONFIG_DIR / "email_config.json"
    if legacy_candidate.exists():
        return legacy_candidate
    return PLATFORM_EMAIL_CONFIG_PATH


# ═════════════════════════════════════════════════════════════════════
# University
# ═════════════════════════════════════════════════════════════════════

UNIVERSITY_DATA_DIR: Path = VAR_DIR / "data" / "university"

# Database paths
UNIVERSITY_DB_DIR: Path = UNIVERSITY_DATA_DIR / "db_files"
UNIVERSITY_DB_FILES_DIR: Path = UNIVERSITY_DB_DIR  # Alias for clarity
UNIVERSITY_DEFAULT_DB_PATH: Path = UNIVERSITY_DB_DIR / "student_records.db"
UNIVERSITY_HEALTH_DB_PATH: Path = UNIVERSITY_DATA_DIR / "health" / "health_records.db"
UNIVERSITY_SAFEGUARDING_DB_PATH: Path = UNIVERSITY_DATA_DIR / "safeguarding" / "safeguarding_records.db"

# Backup metadata file
UNIVERSITY_BACKUP_METADATA_FILE: Path = UNIVERSITY_DATA_DIR / "backup_metadata.json"
UNIVERSITY_IMPORT_HISTORY_FILE: Path = UNIVERSITY_DATA_DIR / "import_history.json"

# Logging paths - under var/, not inside the package
UNIVERSITY_LOG_DIR: Path = VAR_DIR / "logs" / "university"

# Backup paths - organised by type under a single top-level directory
UNIVERSITY_BACKUP_DIR: Path = BACKUP_DIR / "university"
UNIVERSITY_BACKUP_DATABASE_DIR: Path = UNIVERSITY_BACKUP_DIR / "database"
UNIVERSITY_BACKUP_FILES_DIR: Path = UNIVERSITY_BACKUP_DIR / "files"
UNIVERSITY_BACKUP_ATTENDANCE_DIR: Path = UNIVERSITY_BACKUP_DIR / "attendance"
UNIVERSITY_BACKUP_FINANCE_DIR: Path = UNIVERSITY_BACKUP_DIR / "finance"
UNIVERSITY_BACKUP_LIBRARY_DIR: Path = UNIVERSITY_BACKUP_DIR / "library"
UNIVERSITY_BACKUP_HEALTH_DIR: Path = UNIVERSITY_BACKUP_DIR / "health"
UNIVERSITY_BACKUP_SETTINGS_DIR: Path = UNIVERSITY_BACKUP_DIR / "settings"
UNIVERSITY_BACKUP_CALENDAR_DIR: Path = UNIVERSITY_BACKUP_DIR / "calendar"
UNIVERSITY_BACKUP_SUBMISSIONS_DIR: Path = UNIVERSITY_BACKUP_DIR / "submissions"
UNIVERSITY_BACKUP_SAFETY_DIR: Path = UNIVERSITY_BACKUP_DIR / "safety"
UNIVERSITY_BACKUP_ASSIGNMENTS_DIR: Path = UNIVERSITY_BACKUP_DIR / "assignments"
# Remote backup location and archive member names are centralized here so
# callers do not embed storage-layout literals.
UNIVERSITY_REMOTE_BACKUP_PATH: str = "/backups"
UNIVERSITY_DATABASE_BACKUP_FILENAME: str = "database.db"
# Backward-compatible aliases
UNIVERSITY_DB_BACKUPS_DIR: Path = UNIVERSITY_BACKUP_DATABASE_DIR

# Export paths - organised under data for consistent hierarchy
UNIVERSITY_EXPORTS_DIR: Path = UNIVERSITY_DATA_DIR / "exports"
UNIVERSITY_EXPORTS_DATABASE_DIR: Path = UNIVERSITY_EXPORTS_DIR / "database"
UNIVERSITY_EXPORTS_PDF_DIR: Path = UNIVERSITY_EXPORTS_DIR / "pdf"
UNIVERSITY_EXPORTS_TICKETS_DIR: Path = UNIVERSITY_EXPORTS_DIR / "tickets"
UNIVERSITY_EXPORTS_SUBMISSIONS_DIR: Path = UNIVERSITY_EXPORTS_DIR / "submissions"
UNIVERSITY_EXPORTS_REPORTS_DIR: Path = UNIVERSITY_EXPORTS_DIR / "reports"
UNIVERSITY_EXPORTS_BAKERY_DIR: Path = UNIVERSITY_EXPORTS_DIR / "bakery"
# Backward-compatible alias
UNIVERSITY_DB_EXPORTS_DIR: Path = UNIVERSITY_DB_DIR / "exports"

# Reports paths under data
UNIVERSITY_REPORTS_DIR: Path = UNIVERSITY_DATA_DIR / "reports"
UNIVERSITY_REPORT_TEMPLATES_DIR: Path = UNIVERSITY_DATA_DIR / "reports_templates"
UNIVERSITY_REPORT_CACHE_DIR: Path = UNIVERSITY_DATA_DIR / "report_cache"
UNIVERSITY_SCHEDULED_REPORTS_FILE: Path = UNIVERSITY_REPORTS_DIR / "scheduled_reports.json"

# Email subsystem paths - consolidated to templates/email
UNIVERSITY_EMAIL_DATA_DIR: Path = UNIVERSITY_DATA_DIR / "email"
# E-mail into support tickets: .eml files dropped here are read (folder mode);
# messages that could not be matched wait in quarantine/ for staff review.
UNIVERSITY_SUPPORT_INBOUND_DIR: Path = UNIVERSITY_EMAIL_DATA_DIR / "support_inbound"
UNIVERSITY_EMAIL_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "email"
UNIVERSITY_TEMPLATE_REGISTRY_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "registry"
UNIVERSITY_UI_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "ui"
UNIVERSITY_DOCUMENT_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "documents"
UNIVERSITY_DATA_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "data"
UNIVERSITY_SEED_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "seeds"

# Configuration directory
UNIVERSITY_CONFIG_DIR: Path = UNIVERSITY_DATA_DIR / "config"

# Canonical config/report/template files (previously hardcoded at many call sites)
UNIVERSITY_SAVED_REPORTS_FILE: Path = UNIVERSITY_CONFIG_DIR / "saved_reports.json"
UNIVERSITY_API_SERVER_CONFIG_FILE: Path = UNIVERSITY_CONFIG_DIR / "api_server_config.json"
UNIVERSITY_LICENSES_FILE: Path = UNIVERSITY_CONFIG_DIR / "licenses.json"
UNIVERSITY_DR_CONFIG_FILE: Path = UNIVERSITY_CONFIG_DIR / "dr_config.json"
UNIVERSITY_MAINTENANCE_WINDOWS_FILE: Path = UNIVERSITY_CONFIG_DIR / "maintenance_windows.json"
UNIVERSITY_FINANCE_GUI_SETTINGS_FILE: Path = UNIVERSITY_CONFIG_DIR / "finance_gui_settings.json"

UNIVERSITY_EMAIL_CONFIG_FILE: Path = _university_resolve_email_config_file()
UNIVERSITY_EMAIL_CONFIG_PATH: Path = UNIVERSITY_EMAIL_CONFIG_FILE

# Activity logger configuration lives in config data.
UNIVERSITY_LOGGER_CONFIG_DIR: Path = UNIVERSITY_CONFIG_DIR

# Chatbot assets (uploads/models) live under a dedicated namespace.
UNIVERSITY_CHATBOT_DATA_DIR: Path = UNIVERSITY_DATA_DIR / "chatbot"
UNIVERSITY_CHATBOT_UPLOAD_DIR: Path = UNIVERSITY_CHATBOT_DATA_DIR / "uploads"
UNIVERSITY_CHATBOT_MODELS_DIR: Path = UNIVERSITY_CHATBOT_DATA_DIR / "models"
UNIVERSITY_CHATBOT_CONFIG_PATH: Path = UNIVERSITY_LOGGER_CONFIG_DIR / "chatbot_config.json"

# QR codes directory
UNIVERSITY_QR_CODES_DIR: Path = UNIVERSITY_DATA_DIR / "qr_codes"

# Analytics directories - consolidated under data/analytics
UNIVERSITY_ANALYTICS_DIR: Path = UNIVERSITY_DATA_DIR / "analytics"
UNIVERSITY_ANALYTICS_PLOTS_DIR: Path = UNIVERSITY_ANALYTICS_DIR / "plots"
# Analytics reports now under main reports directory for consolidation
UNIVERSITY_ANALYTICS_REPORTS_DIR: Path = UNIVERSITY_REPORTS_DIR / "analytics"

# Submissions directory - for assignment submissions
UNIVERSITY_SUBMISSIONS_DIR: Path = UNIVERSITY_DATA_DIR / "submissions"

# Uploads directory - for general file uploads
UNIVERSITY_UPLOAD_DIR: Path = UNIVERSITY_DATA_DIR / "uploads"
UNIVERSITY_UPLOADS_DIR: Path = UNIVERSITY_UPLOAD_DIR  # Alias for consistency

# Temporary files directory - for temporary files (instead of /tmp)
UNIVERSITY_TEMP_DIR: Path = UNIVERSITY_DATA_DIR / "temp"

# Templates directory - shipped static assets under assets/
UNIVERSITY_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates"
UNIVERSITY_EMAIL_TEMPLATE_MAPPING_FILE: Path = UNIVERSITY_TEMPLATE_REGISTRY_DIR / "email_template_mapping.json"
UNIVERSITY_ASSIGNMENT_TEMPLATES_DIR: Path = UNIVERSITY_UI_TEMPLATES_DIR / "assignments"
# Shipped, read-only backup-template seeds; user-saved templates go to data/ (UNIVERSITY_USER_BACKUP_TEMPLATES_DIR)
UNIVERSITY_BACKUP_TEMPLATES_DIR: Path = UNIVERSITY_SEED_TEMPLATES_DIR / "backup"
UNIVERSITY_USER_BACKUP_TEMPLATES_DIR: Path = UNIVERSITY_DATA_DIR / "backup_templates"
UNIVERSITY_MEDICAL_TEMPLATES_DIR: Path = UNIVERSITY_DOCUMENT_TEMPLATES_DIR / "medical"
UNIVERSITY_TICKET_TEMPLATES_DIR: Path = UNIVERSITY_UI_TEMPLATES_DIR / "ticketing"
UNIVERSITY_COURSE_EVALUATION_TEMPLATES_DIR: Path = UNIVERSITY_UI_TEMPLATES_DIR / "course_evaluation"

# Email reminder templates
UNIVERSITY_EMAIL_REMINDER_TEMPLATES_DIR: Path = UNIVERSITY_EMAIL_TEMPLATES_DIR / "communications" / "reminders"

# Finance templates directory - for finance seed/template data
UNIVERSITY_FINANCE_TEMPLATES_DIR: Path = UNIVERSITY_DOCUMENT_TEMPLATES_DIR / "finance"

# NLTK data directory - for natural language processing data
UNIVERSITY_NLTK_DATA_DIR: Path = UNIVERSITY_DATA_DIR / "nltk_data"

# Student documents directory - for student document storage
UNIVERSITY_STUDENT_DOCUMENTS_DIR: Path = UNIVERSITY_DATA_DIR / "student_documents"

# Evidence attached to academic integrity cases (copies, with their SHA-256
# recorded in integrity_evidence). Runtime data under var/.
UNIVERSITY_INTEGRITY_EVIDENCE_DIR: Path = UNIVERSITY_DATA_DIR / "integrity_evidence"
# API key for the external-source similarity search (CORE, core.ac.uk), owner-only.
UNIVERSITY_INTEGRITY_CORE_KEY_FILE: Path = PLATFORM_SECRETS_DIR / "core_api_key"
# Trained AI-writing indicator models (joblib, owner-only, sha256 kept in
# ai_detector_model_versions) and federated update files exported by default.
UNIVERSITY_AI_MODELS_DIR: Path = UNIVERSITY_DATA_DIR / "ai_models"

# Branding directory - institution logo and other admin-supplied brand assets.
# Runtime data (an admin uploads it), so it belongs under var/ rather than the
# shipped assets/ tree.
UNIVERSITY_BRANDING_DIR: Path = UNIVERSITY_DATA_DIR / "branding"

# UNIVERSITY_EXPORTS_DIR is now defined above under "Export paths"

# Charts directory - for chart outputs
UNIVERSITY_CHARTS_DIR: Path = UNIVERSITY_REPORTS_DIR / "charts"

# Locales directory - for internationalization translation files
UNIVERSITY_LOCALES_DIR: Path = UNIVERSITY_DATA_DIR / "locales"
UNIVERSITY_LANGUAGE_CONFIG_PATH: Path = UNIVERSITY_CONFIG_DIR / "language_config.json"

# Assets directory - for static assets
UNIVERSITY_ASSETS_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets"

# Utility scripts moved out of the package to tools/<system> (ADR 0018)
UNIVERSITY_SCRIPTS_DIR: Path = REPO_ROOT / "tools" / "university"
