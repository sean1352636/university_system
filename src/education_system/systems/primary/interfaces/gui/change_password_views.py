"""Tkinter change-password dialog (Primary School System) — moved to the platform.

The implementation is now
``education_system.platform.delivery.gui.change_password_gui``. This
module stays as a re-export so the GUI menu wiring keeps resolving.
"""

from __future__ import annotations

from education_system.platform.delivery.gui.change_password_gui import (  # noqa: F401
    ChangePasswordFrame,
    open_change_password_dialog,
)

__all__ = ["ChangePasswordFrame", "open_change_password_dialog"]
