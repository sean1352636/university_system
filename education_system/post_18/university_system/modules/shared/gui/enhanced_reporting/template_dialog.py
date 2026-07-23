"""Template-dialog facade for the enhanced reporting GUI.

Intentional architectural separation: callers import ``TemplateDialog``,
``start_gui``, and ``start_enhanced_reporting_gui`` from this module so the
dialog handling stays decoupled from the rest of the reporting GUI code.
Not a deprecated shim — keep stable.
"""

from __future__ import annotations

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.core import TemplateDialog, start_gui, start_enhanced_reporting_gui

__all__ = [
    "TemplateDialog",
    "start_gui",
    "start_enhanced_reporting_gui",
]