"""Base class for AssignmentManager with shared initialization and helpers"""

import tkinter as tk
from tkinter import ttk


class AssignmentManagerBase:
    """Assignment CRUD operations and management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def show_assignment_status(self, message, msg_type):
        """Show status message in assignment status frame"""
        for widget in self.assignment_status_frame.winfo_children():
            widget.destroy()

        if msg_type == "success":
            style = 'Success.TLabel'
        elif msg_type == "error":
            style = 'Error.TLabel'
        else:
            style = 'Warning.TLabel'

        status_label = ttk.Label(self.assignment_status_frame, text=message, style=style)
        status_label.pack(anchor='w')
