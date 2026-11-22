"""Nursery / Early Years paths.

Part of :mod:`education_system.paths`; import names from the package, not from here.
"""

from __future__ import annotations

from pathlib import Path
import os

from education_system.paths.core import (
    NURSERY_PACKAGE_ROOT,
    VAR_DIR,
)

# ═════════════════════════════════════════════════════════════════════
# Nursery / Early Years
# ═════════════════════════════════════════════════════════════════════

# Runtime state lives under ``var`` (ADR 0018), never inside the
# importable package. SYSTEM_DB_PATHS below is derived from this constant, so
# the cross-system registry and the per-system constant can no longer drift.
NURSERY_DATA_DIR: Path = Path(
    os.environ.get("EDU_NURSERY_DATA_DIR")
    or (VAR_DIR / "data" / "nursery")
).resolve()

# All nursery modules share a single SQLite DB.
NURSERY_DB: Path = NURSERY_DATA_DIR / "nursery.db"
NURSERY_PUPILS_DB: Path = NURSERY_DB
NURSERY_STAFF_DB: Path = NURSERY_DB

# Per-module DB aliases for ported cross-cutting modules. Each module creates
# its own tables (``CREATE TABLE IF NOT EXISTS``) inside the shared nursery DB,
# mirroring how the other systems alias every module DB onto one file.
NURSERY_POLICIES_DB: Path = NURSERY_DB
NURSERY_GDPR_DB: Path = NURSERY_DB
NURSERY_RECRUITMENT_DB: Path = NURSERY_DB
NURSERY_COMPLAINTS_DB: Path = NURSERY_DB
NURSERY_FEEDBACK_DB: Path = NURSERY_DB
NURSERY_EXPENSE_CLAIMS_DB: Path = NURSERY_DB
NURSERY_AUDIT_REPORTS_DB: Path = NURSERY_DB
NURSERY_ACTIVITY_FEED_DB: Path = NURSERY_DB
NURSERY_STAFF_ABSENCE_DB: Path = NURSERY_DB
NURSERY_VISITORS_DB: Path = NURSERY_DB
NURSERY_DBS_CHECKS_DB: Path = NURSERY_DB
NURSERY_APPRAISALS_DB: Path = NURSERY_DB
NURSERY_SETTINGS_DB: Path = NURSERY_DB

# JSON email templates for the Email / Messaging centre. These ship with
# the code (assets/), not the runtime data dir, so they must not hang off
# the env-overridable NURSERY_DATA_DIR.
NURSERY_EMAIL_TEMPLATES_DIR: Path = NURSERY_PACKAGE_ROOT / "assets" / "templates" / "email"
