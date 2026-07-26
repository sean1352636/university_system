"""Centralised file/directory paths for the Nursery System.

Environment override: ``EDU_NURSERY_DATA_DIR``.

Mirrors ``primarysch_system/core/paths.py`` — every nursery module shares a
single SQLite database (``nursery.db``). The canonical cross-system registry
in ``shared/database/paths.py`` points at the same file.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT: Path = Path(__file__).resolve().parent.parent

DATA_DIR: Path = Path(
    os.environ.get("EDU_NURSERY_DATA_DIR")
    or (PACKAGE_ROOT / "data")
).resolve()

# All nursery modules share a single SQLite DB.
NURSERY_DB: Path = DATA_DIR / "nursery.db"
PUPILS_DB: Path = NURSERY_DB
STAFF_DB: Path = NURSERY_DB

# Per-module DB aliases for ported cross-cutting modules. Each module creates
# its own tables (``CREATE TABLE IF NOT EXISTS``) inside the shared nursery DB,
# mirroring how the other systems alias every module DB onto one file.
POLICIES_DB: Path = NURSERY_DB
GDPR_DB: Path = NURSERY_DB
RECRUITMENT_DB: Path = NURSERY_DB
COMPLAINTS_DB: Path = NURSERY_DB
FEEDBACK_DB: Path = NURSERY_DB
EXPENSE_CLAIMS_DB: Path = NURSERY_DB
AUDIT_REPORTS_DB: Path = NURSERY_DB
ACTIVITY_FEED_DB: Path = NURSERY_DB
STAFF_ABSENCE_DB: Path = NURSERY_DB
VISITORS_DB: Path = NURSERY_DB
DBS_CHECKS_DB: Path = NURSERY_DB
APPRAISALS_DB: Path = NURSERY_DB
SETTINGS_DB: Path = NURSERY_DB

# JSON email templates for the Email / Messaging centre.
EMAIL_TEMPLATES_DIR: Path = DATA_DIR / "templates" / "email"


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EMAIL_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
