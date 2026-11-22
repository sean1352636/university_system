"""Port onto Pastoral's windows for other slices.

Academics' cross-launchers offer "open Accessibility & Accommodation Tools"
from assignments; the slice rules keep them from importing Pastoral's GUI
directly, so it comes through here (as ``academic_windows`` does the other
way).
"""

from __future__ import annotations


def open_accessibility_tools(parent, auth=None):
    """Open Accessibility & Accommodation Tools over ``parent`` and return
    the GUI object. Raises ImportError when Pastoral's GUI isn't available."""
    from education_system.systems.university.domains.student_support.interfaces.gui.accessibility_tools_gui import (
        AccessibilityToolsGUI,
    )
    return AccessibilityToolsGUI(parent, auth=auth)
