"""Local Authority Education paths.

Part of :mod:`education_system.paths`; import names from the package, not from here.

The Local Authority Education system is not yet a member of the cross-system registry
(``SYSTEM_DB_PATHS``) and is not wired into sign-in.
"""

from __future__ import annotations

import os
from pathlib import Path

from education_system.paths.core import VAR_DIR

# Runtime state lives under ``var`` (ADR 0018). Overridable via env so tests
# and safe probes can redirect it without touching code.
LOCAL_AUTHORITY_DATA_DIR: Path = Path(
    os.environ.get("EDU_LOCAL_AUTHORITY_DATA_DIR")
    or (VAR_DIR / "data" / "local_authority")
).resolve()

#: One SQLite file for every local authority education area.
LOCAL_AUTHORITY_DB: Path = LOCAL_AUTHORITY_DATA_DIR / "local_authority.db"
