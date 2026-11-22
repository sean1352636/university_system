"""Platform paths shared across every system.

Part of :mod:`education_system.paths`; import names from the package, not from here.
"""

from __future__ import annotations

from pathlib import Path
import os

from education_system.paths.core import (
    PLATFORM_ROOT,
    VAR_DIR,
)

# ═════════════════════════════════════════════════════════════════════
# Platform (shared across all five systems)
# ═════════════════════════════════════════════════════════════════════

# Static assets shipped inside the platform package (never runtime data)
PLATFORM_ASSETS_DIR: Path = PLATFORM_ROOT / "assets"
PLATFORM_TEMPLATES_DIR: Path = PLATFORM_ASSETS_DIR / "templates"
PLATFORM_DOCUMENT_TEMPLATES_DIR: Path = PLATFORM_TEMPLATES_DIR / "documents"
PLATFORM_EMAIL_TEMPLATES_DIR: Path = PLATFORM_TEMPLATES_DIR / "email"
PLATFORM_UI_TEMPLATES_DIR: Path = PLATFORM_TEMPLATES_DIR / "ui"

# Overridable via env, matching every per-system data dir below, so tests
# and installers can redirect it without touching code. This is the one
# that holds auth.db — and therefore the student journey, enrolments and
# transitions — so without an override a test that exercises anything
# cross-system has no choice but to read and write the running
# application's own auth database.
PLATFORM_DATA_DIR: Path = Path(
    os.environ.get("EDU_PLATFORM_DATA_DIR")
    or (VAR_DIR / "data" / "platform")
).resolve()
PLATFORM_DB_FILES_DIR: Path = PLATFORM_DATA_DIR / "db_files"
PLATFORM_CONFIG_DIR: Path = PLATFORM_DATA_DIR / "config"
PLATFORM_DOCUMENTS_DIR: Path = PLATFORM_DATA_DIR / "documents"
PLATFORM_LOGS_DIR: Path = VAR_DIR / "logs" / "platform"

# Databases shared across all five systems
PLATFORM_AUTH_DB_FILE: Path = PLATFORM_DB_FILES_DIR / "auth.db"
PLATFORM_AUDIT_DB_FILE: Path = PLATFORM_DB_FILES_DIR / "audit.db"
PLATFORM_MISCONDUCT_DB_FILE: Path = PLATFORM_DB_FILES_DIR / "misconduct.db"
PLATFORM_RATE_LIMITS_DB_FILE: Path = PLATFORM_DB_FILES_DIR / "rate_limits.db"

# Config written at runtime by the admin GUIs
PLATFORM_EMAIL_CONFIG_PATH: Path = PLATFORM_CONFIG_DIR / "email_config.json"
# Account e-mails written instead of sent while delivery_mode is "sandbox".
PLATFORM_EMAIL_SANDBOX_DIR: Path = PLATFORM_DATA_DIR / "email_sandbox"
# Secrets kept out of config files (ADR 0018: var/ is never committed). Files
# here are written owner-read-only; see platform/integrations/email/config.
PLATFORM_SECRETS_DIR: Path = VAR_DIR / "secrets"
# The single key that seals confidential health fields (Fernet), owner-only.
UNIVERSITY_HEALTH_FIELD_KEY_FILE: Path = PLATFORM_SECRETS_DIR / "health_field_key"
# HMAC secret for the immutable audit log chain (AUDIT_LOG_SECRET), owner-only.
PLATFORM_AUDIT_LOG_SECRET_FILE: Path = PLATFORM_SECRETS_DIR / "audit_log_secret"
PLATFORM_SMTP_PASSWORD_FILE: Path = PLATFORM_SECRETS_DIR / "smtp_password"
# Google OAuth "Desktop app" client JSON used to save exports as Google Sheets;
# the user's token is cached next to it after the first browser sign-in.
PLATFORM_GOOGLE_OAUTH_CLIENT_FILE: Path = PLATFORM_SECRETS_DIR / "google_oauth_client.json"
PLATFORM_GOOGLE_SHEETS_TOKEN_FILE: Path = PLATFORM_SECRETS_DIR / "google_sheets_token.json"
# Password of the support mailbox read into tickets (SUPPORT_IMAP_PASSWORD), owner-only.
UNIVERSITY_SUPPORT_IMAP_PASSWORD_FILE: Path = PLATFORM_SECRETS_DIR / "support_imap_password"
# API token of the LMS the attendance tracker syncs with (LMS_API_TOKEN), owner-only.
UNIVERSITY_LMS_API_TOKEN_FILE: Path = PLATFORM_SECRETS_DIR / "lms_api_token"
PLATFORM_SMS_CONFIG_PATH: Path = PLATFORM_CONFIG_DIR / "sms_config.json"
