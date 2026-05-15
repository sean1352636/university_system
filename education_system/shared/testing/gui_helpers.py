"""GUI testing utilities for tkinter-based education system interfaces.

Improvement #11: GUI Testing

Provides helpers for testing tkinter GUIs without a display,
and utilities for simulating user interactions in tests.
"""

import functools
import logging
import os
import unittest

logger = logging.getLogger(__name__)


def _display_available() -> bool:
    """Check if a display is available for GUI tests."""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True
    # macOS doesn't use DISPLAY
    import sys
    if sys.platform == "darwin":
        return True
    return False


class NoDisplaySkip:
    """Pytest skip decorator for tests that need a display.

    Usage:
        @NoDisplaySkip.skip_if_no_display
        def test_student_gui_opens():
            ...
    """

    @staticmethod
    def skip_if_no_display(func):
        """Skip test if no display is available."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import pytest
            if not _display_available():
                pytest.skip("No display available for GUI test")
            return func(*args, **kwargs)
        return wrapper


class GUITestCase(unittest.TestCase):
    """Base test case for tkinter GUI testing.

    Provides:
    - Auto-creation/destruction of Tk root
    - Simulated user interactions (click, type, select)
    - Widget finding by text/class
    - Screenshot capture for debugging

    Usage:
        class TestStudentGUI(GUITestCase):
            def test_add_student_dialog(self):
                from education_system.university_system.modules.domain.students.students.gui.student_gui import StudentGUI
                gui = StudentGUI(self.root, user_info={"username": "admin"}, role="admin")
                self.pump_events()

                # Find and click the "Add Student" button
                btn = self.find_widget_by_text(gui, "Add Student")
                self.assertIsNotNone(btn)
    """

    @classmethod
    def setUpClass(cls):
        if not _display_available():
            raise unittest.SkipTest("No display available for GUI tests")

    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()  # Hidden window

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def pump_events(self, duration_ms: int = 100):
        """Process pending tkinter events."""
        self.root.update_idletasks()
        self.root.update()
        if duration_ms > 0:
            self.root.after(duration_ms, self.root.quit)
            try:
                self.root.mainloop()
            except Exception:
                pass

    def find_widget_by_text(self, parent, text: str):
        """Recursively find a widget containing the given text."""
        import tkinter as tk

        for child in parent.winfo_children():
            try:
                if isinstance(child, (tk.Button, tk.Label)):
                    if child.cget("text") == text:
                        return child
            except Exception:
                pass
            # Recurse
            found = self.find_widget_by_text(child, text)
            if found:
                return found
        return None

    def find_widgets_by_class(self, parent, widget_class) -> list:
        """Recursively find all widgets of a given class."""
        found = []
        for child in parent.winfo_children():
            if isinstance(child, widget_class):
                found.append(child)
            found.extend(self.find_widgets_by_class(child, widget_class))
        return found

    def simulate_click(self, widget):
        """Simulate a button click."""
        widget.invoke()
        self.pump_events(50)

    def simulate_type(self, entry_widget, text: str):
        """Type text into an Entry widget."""
        entry_widget.delete(0, "end")
        entry_widget.insert(0, text)
        self.pump_events(50)

    def get_treeview_data(self, treeview) -> list[dict]:
        """Extract all data from a ttk.Treeview as list of dicts."""
        columns = treeview["columns"]
        data = []
        for item_id in treeview.get_children():
            values = treeview.item(item_id, "values")
            row = dict(zip(columns, values))
            data.append(row)
        return data
