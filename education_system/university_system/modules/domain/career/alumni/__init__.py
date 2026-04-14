"""Alumni relations and graduate networking.

This domain delegates to the comprehensive alumni management system
under student_affairs. Import from here for convenience.
"""

from education_system.university_system.modules.domain.career.alumni.services import (
    display_alumni_menu,
    display_alumni_relations_menu,
    launch_alumni_relations_gui,
    setup_alumni_permissions,
)

__all__ = [
    'display_alumni_menu',
    'display_alumni_relations_menu',
    'launch_alumni_relations_gui',
    'setup_alumni_permissions',
]
