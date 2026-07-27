"""Centralised filesystem path helpers for the platform package.

Mirrors ``systems/university/infrastructure/paths.py``: runtime state belongs
in one gitignored tree at the repository root, never inside the package
(ADR 0018). Platform modules previously derived their own data directories
from ``Path(__file__).parent``, which wrote databases and config into
``education_system/platform/*/data/`` — inside the source tree, and separate
from the real databases under ``var/``.

IMPORTANT: Directories are NOT created on import. Call ``ensure_directories()``
during application initialisation.

This module has no dependencies beyond the standard library, so it can be
imported from anywhere in the platform package without circular imports.
"""

from __future__ import annotations

from pathlib import Path

# `.../education_system/platform/paths.py` -> platform -> education_system -> <repo root>
PLATFORM_ROOT: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = PLATFORM_ROOT.parents[1]

# Runtime state lives in one gitignored tree at the repository root (ADR 0018).
VAR_DIR: Path = REPO_ROOT / "var"

DATA_DIR: Path = VAR_DIR / "data" / "platform"
DB_FILES_DIR: Path = DATA_DIR / "db_files"
CONFIG_DIR: Path = DATA_DIR / "config"
DOCUMENTS_DIR: Path = DATA_DIR / "documents"
LOGS_DIR: Path = VAR_DIR / "logs" / "platform"

# Databases shared across all five systems
AUTH_DB_FILE: Path = DB_FILES_DIR / "auth.db"
AUDIT_DB_FILE: Path = DB_FILES_DIR / "audit.db"
MISCONDUCT_DB_FILE: Path = DB_FILES_DIR / "misconduct.db"

# Config written at runtime by the admin GUIs
EMAIL_CONFIG_PATH: Path = CONFIG_DIR / "email_config.json"
SMS_CONFIG_PATH: Path = CONFIG_DIR / "sms_config.json"


def ensure_directories() -> None:
    """Create the runtime directory structure. Safe to call repeatedly."""
    for d in (DATA_DIR, DB_FILES_DIR, CONFIG_DIR, DOCUMENTS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


__all__ = [
    "PLATFORM_ROOT",
    "REPO_ROOT",
    "VAR_DIR",
    "DATA_DIR",
    "DB_FILES_DIR",
    "CONFIG_DIR",
    "DOCUMENTS_DIR",
    "LOGS_DIR",
    "AUTH_DB_FILE",
    "AUDIT_DB_FILE",
    "MISCONDUCT_DB_FILE",
    "EMAIL_CONFIG_PATH",
    "SMS_CONFIG_PATH",
    "ensure_directories",
]
