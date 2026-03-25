"""Template dialog interface for the enhanced reporting GUI.

This module re-exports the :class:`TemplateDialog` along with
``start_gui`` and ``start_enhanced_reporting_gui`` functions from the
core module.  Importing from this module allows for a clean separation
between dialog handling and the rest of the GUI code.
"""

from __future__ import annotations

from education_system.university_system.modules.shared.gui.enhanced_reporting.core import TemplateDialog, start_gui, start_enhanced_reporting_gui

__all__ = [
    "TemplateDialog",
    "start_gui",
    "start_enhanced_reporting_gui",
]