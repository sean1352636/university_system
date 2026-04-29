"""Cross-domain data adapters for the assignment GUI.

Each module here exposes pure data-fetching helpers (no UI, no I/O loops)
so the assignment GUI can pull from parent_portal, library and attendance
services without re-implementing their queries.
"""

from education_system.university_system.modules.domain.academics.gui.assignment_system.integrations.parent_portal import (
    fetch_child_assignments,
    fetch_parent_children,
)
from education_system.university_system.modules.domain.academics.gui.assignment_system.integrations.library import (
    fetch_module_resources,
)
from education_system.university_system.modules.domain.academics.gui.assignment_system.integrations.attendance import (
    fetch_module_attendance,
    fetch_attendance_warning,
)

__all__ = [
    "fetch_child_assignments",
    "fetch_parent_children",
    "fetch_module_resources",
    "fetch_module_attendance",
    "fetch_attendance_warning",
]
