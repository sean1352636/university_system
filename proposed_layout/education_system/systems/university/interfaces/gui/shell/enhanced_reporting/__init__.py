"""Enhanced Reporting GUI package initialization.

This package provides the enhanced reporting GUI components for the
university system. It exposes the main GUI class and dialog as well
as convenience functions for launching the interface.  The
``ENHANCED_AVAILABLE`` flag mirrors the availability of the
underlying enhanced reporting services.

The package re-exports :class:`ReportingSystemGUI` and
:class:`TemplateDialog` along with the ``start_gui`` and
``start_enhanced_reporting_gui`` functions for convenience.
"""

from __future__ import annotations

try:
    # Try to import enhanced reporting services to set the flag
    from education_system.systems.university.services.analytics import enhanced_reporting  # type: ignore
    ENHANCED_AVAILABLE: bool = True
except ImportError:
    ENHANCED_AVAILABLE = False

from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import ReportingSystemGUI, start_gui, start_enhanced_reporting_gui
from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.template_dialog import TemplateDialog

__all__ = [
    "ReportingSystemGUI",
    "TemplateDialog",
    "start_gui",
    "start_enhanced_reporting_gui",
    "ENHANCED_AVAILABLE",
]