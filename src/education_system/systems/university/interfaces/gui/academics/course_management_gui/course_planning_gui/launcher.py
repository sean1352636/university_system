"""Standalone launcher for CoursePlanningGUI."""
from __future__ import annotations

import tkinter as tk

from . import CoursePlanningGUI  # re-exported by __init__.py

# Standalone launcher for testing
def launch_course_planning_gui():
    """Launch the Course Planning GUI standalone."""
    root = tk.Tk()
    root.withdraw()

    # Mock auth for testing
    class MockAuth:
        current_user = {
            'id': 'TEST001',
            'username': 'test_student',
            'role': 'student'
        }

    app = CoursePlanningGUI(root, MockAuth())
    root.mainloop()
