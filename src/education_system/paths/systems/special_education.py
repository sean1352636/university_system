"""Special Education (SEND) paths.

Part of :mod:`education_system.paths`; import names from the package, not from here.

The SEND system is not yet a member of the cross-system registry
(``SYSTEM_DB_PATHS``) and is not wired into sign-in.
"""

from __future__ import annotations

import os
from pathlib import Path

from education_system.paths.core import VAR_DIR

# Runtime state lives under ``var`` (ADR 0018). Overridable via env so tests
# and safe probes can redirect it without touching code.
SPECIAL_EDUCATION_DATA_DIR: Path = Path(
    os.environ.get("EDU_SPECIAL_EDUCATION_DATA_DIR")
    or (VAR_DIR / "data" / "special_education")
).resolve()

#: One SQLite file for every SEND area, so learner foreign keys and joins work.
SPECIAL_EDUCATION_DB: Path = SPECIAL_EDUCATION_DATA_DIR / "special_education.db"
