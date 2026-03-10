from .internship_gui import InternshipGUI
from .notifications import send_internship_notification, send_application_confirmation

from ._imports import (
    setup_internship_permissions,
    init_internship_db,
    set_auth,
    view_available_internships,
    view_internship_details,
    apply_for_internship,
    view_applications,
    review_application,
    create_internship,
    edit_internship,
    delete_internship,
    generate_internship_report,
    display_internship_menu,
)

import tkinter as tk


def launch_gui(auth_object=None):
    """Launch the GUI version of the internship management system"""
    root = tk.Tk()
    app = InternshipGUI(root, auth_object)
    root.mainloop()


def main(auth_object=None, mode='gui'):
    """
    Main entry point for the internship management system

    Args:
        auth_object: Authentication object from main system
        mode: 'gui' for GUI mode, 'cli' for CLI mode
    """
    if auth_object:
        set_auth(auth_object)

    if mode.lower() == 'gui':
        launch_gui(auth_object)
    else:
        display_internship_menu()
