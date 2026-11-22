"""Alternative Provision paths.

Part of :mod:`education_system.paths`; import names from the package, not from here.

The Alternative Provision system is not yet a member of the cross-system registry
(``SYSTEM_DB_PATHS``) and is not wired into sign-in.
"""

from __future__ import annotations

import os
from pathlib import Path

from education_system.paths.core import VAR_DIR

# Runtime state lives under ``var`` (ADR 0018). Overridable via env so tests
# and safe probes can redirect it without touching code.
ALTERNATIVE_PROVISION_DATA_DIR: Path = Path(
    os.environ.get("EDU_ALTERNATIVE_PROVISION_DATA_DIR")
    or (VAR_DIR / "data" / "alternative_provision")
).resolve()

#: One SQLite file for every alternative provision area.
ALTERNATIVE_PROVISION_DB: Path = ALTERNATIVE_PROVISION_DATA_DIR / "alternative_provision.db"
