"""
Health Portal GUI - imports from the full implementation.

This module provides access to the full Health Portal GUI implementation
located in the interfaces module. It re-exports the class for
backwards compatibility.
"""
from __future__ import annotations
from typing import Any
import logging

from education_system.university_system.core.i18n import get_text, _

logger = logging.getLogger(__name__)

# Try to import the full implementation
try:
    from education_system.university_system.modules.domain.health.gui.health_portal import HealthPortalGUI as _RealHealthPortalGUI

    # Re-export the real implementation
    HealthPortalGUI = _RealHealthPortalGUI
    REAL_IMPLEMENTATION_AVAILABLE = True

except ImportError as e:
    logger.warning(f"Could not import full Health Portal GUI implementation: {e}")
    logger.warning("Using stub implementation with limited functionality")
    REAL_IMPLEMENTATION_AVAILABLE = False

    # Fallback stub implementation
    class HealthPortalGUI:
        """Placeholder GUI class for the health portal."""
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            # Accept arbitrary initialization arguments
            logger.warning("Using stub HealthPortalGUI - full implementation not available")
            self.auth = kwargs.get('auth')
            self.root = None

        def run(self) -> None:
            """Start the GUI (stub implementation)."""
            logger.warning("HealthPortalGUI.run() called but full implementation not available")
            print(_("health.portal_not_available"))
            return None

        def create_main_window(self):
            """Create main window (stub implementation)."""
            logger.warning("HealthPortalGUI.create_main_window() called but full implementation not available")
            return None


__all__ = ['HealthPortalGUI', 'REAL_IMPLEMENTATION_AVAILABLE']