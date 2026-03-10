"""
GUI Logic Layer - Separates business logic from UI components.

This module provides testable business logic classes that can be used
by GUI components without coupling to Tkinter or other UI frameworks.

Example usage:
    from education_system.university_system.modules.shared.gui.logic import StudentFormLogic

    # In tests - no GUI needed
    logic = StudentFormLogic()
    valid, errors = logic.validate_student_data({'name': 'John', 'email': 'john@example.com'})

    # In GUI - thin wrapper
    class StudentFormGUI:
        def __init__(self, root):
            self.logic = StudentFormLogic()

        def on_submit(self):
            data = self._collect_form_data()
            valid, errors = self.logic.validate_student_data(data)
            if not valid:
                self._show_errors(errors)
"""

from education_system.university_system.modules.shared.gui.logic.student_form_logic import StudentFormLogic

__all__ = ['StudentFormLogic']
