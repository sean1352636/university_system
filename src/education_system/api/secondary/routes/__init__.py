"""Secondary school REST route blueprints.

One blueprint per module. Registered by the unified server.
"""

from education_system.api.secondary.routes.academics_routes import (
    academics_bp,
)
from education_system.api.secondary.routes.assessment_routes import (
    assessment_bp,
)
from education_system.api.secondary.routes.finance_routes import (
    finance_bp,
)
from education_system.api.secondary.routes.governance_routes import (
    governance_bp,
)
from education_system.api.secondary.routes.pastoral_routes import (
    pastoral_bp,
)
from education_system.api.secondary.routes.pupils_routes import (
    pupils_bp,
)
from education_system.api.secondary.routes.reports_routes import (
    reports_bp,
)
from education_system.api.secondary.routes.staff_comms_routes import (
    staff_comms_bp,
)

__all__ = [
    "academics_bp",
    "assessment_bp",
    "finance_bp",
    "governance_bp",
    "pastoral_bp",
    "pupils_bp",
    "reports_bp",
    "staff_comms_bp",
]

ALL_BLUEPRINTS = (
    academics_bp,
    assessment_bp,
    finance_bp,
    governance_bp,
    pastoral_bp,
    pupils_bp,
    reports_bp,
    staff_comms_bp,
)

# ── Main-menu feature routes ─────────────────────────────────────────
# Generated from this system's GUI/CLI navigation by
# tools/gen_menu_routes.py, so every feature the desktop menus present has
# an addressable endpoint. They mount under /api/menu/... and cannot collide
# with the hand-written resource routes above.
from education_system.api.secondary.routes.menu import MENU_BLUEPRINTS  # noqa: E402

ALL_BLUEPRINTS = tuple(ALL_BLUEPRINTS) + tuple(MENU_BLUEPRINTS)
