from education_system.university_system.modules.domain.academics.services.parent_portal.portal import ParentPortal
from education_system.university_system.modules.domain.academics.services.parent_portal.database import (
    initialize_parent_portal,
    integrate_parent_portal_with_main,
    get_student_parent_relationships,
    send_parent_notification,
    add_teacher_report,
)
from education_system.university_system.modules.domain.academics.services.parent_portal.menu import (
    display_parent_portal_menu,
)


def init_parent_portal(auth):
    """Initialize the parent portal module"""
    parent_portal = ParentPortal(auth)
    parent_portal.setup_parent_permissions()
    return parent_portal


# GUI Launcher using factory pattern
try:
    from education_system.university_system.modules.shared.feature_gui_factory import create_gui_launcher

    launch_parent_portal_gui = create_gui_launcher(
        title="Parent Portal Enhancement",
        description="""Comprehensive parent portal for student monitoring and communication.

Features:
\u2022 Parent access management
\u2022 Student progress monitoring
\u2022 Grade and attendance viewing
\u2022 Communication preferences
\u2022 Financial information access
\u2022 Academic records viewing
\u2022 Event calendar & notifications
\u2022 Permission management
\u2022 Meeting requests
\u2022 Document access
\u2022 Activity logging
\u2022 Multi-student support""",
        cli_instruction="Use CLI: Parent Portal Enhancement"
    )
except ImportError:
    # Fallback if factory not available
    def launch_parent_portal_gui(root, auth):
        from tkinter import messagebox
        messagebox.showinfo("Parent Portal", "Please use the CLI: Parent Portal Enhancement")


# Alias for consistency - both names refer to the same comprehensive system
display_parent_portal_enhancement_menu = display_parent_portal_menu


# Export public API
__all__ = [
    'ParentPortal',
    'display_parent_portal_menu',
    'display_parent_portal_enhancement_menu',
    'launch_parent_portal_gui',
    'integrate_parent_portal_with_main',
]
