"""Module Management — what a module *is*.

Module Scheduling owns when and where a module is taught (sessions, rooms,
timetables, conflicts). This window owns the module itself: its catalogue
record, the programmes it belongs to, its prerequisites, who is enrolled,
who teaches it, and how it is assessed.
"""

from education_system.systems.university.domains.academics.interfaces.gui.module_management.window import (
    ModuleManagementGUI,
)

__all__ = ["ModuleManagementGUI"]
