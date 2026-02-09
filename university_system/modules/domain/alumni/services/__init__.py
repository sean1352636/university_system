"""
Alumni Relations & Engagement Service Module

NOTE: This module now redirects to the comprehensive alumni_management system.
"""

# Import from the comprehensive alumni management system
from university_system.modules.domain.student_affairs.services.alumni_management import (
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
