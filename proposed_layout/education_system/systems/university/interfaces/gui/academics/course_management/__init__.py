"""Course Management — role-scoped portals removed.

The full admin-facing ``CourseManagementGUI`` lives in
``course_management_gui/core/main_gui.py`` and is now the single entry
point for all roles.
"""

from education_system.systems.university.interfaces.gui.academics.course_management_gui.core.main_gui import (
    CourseManagementGUI,
)

__all__ = ["CourseManagementGUI"]
