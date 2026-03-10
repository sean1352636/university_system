"""Backward-compatible re-export from the health_portal package.

The HealthPortalGUI implementation has been split into the
``health_portal/`` package.  This stub keeps existing import paths
working (e.g. tests and the management GUI).
"""

# Re-export the public API so that existing imports keep working:
#   from education_system.university_system.modules.domain.health.gui.health_portal_gui import (
#       HealthPortalGUI, launch_health_portal_gui
#   )
from education_system.university_system.modules.domain.health.gui.health_portal import (  # noqa: F401
    HealthPortalGUI,
    launch_health_portal_gui,
)

# Expose names that tests may patch on this module path.
import tkinter as tk  # noqa: F401
from tkinter import messagebox  # noqa: F401
from education_system.university_system.modules.shared.constants import paths  # noqa: F401

__all__ = ["HealthPortalGUI", "launch_health_portal_gui"]
