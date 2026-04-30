"""Cross-GUI launchers for the four academic management surfaces.

Each helper opens the target GUI in a Toplevel parented to the
caller, so the four windows (Exam, Grade Tracking, Module Scheduling,
Course Management) can be open side-by-side and share the same auth
context. All imports are lazy so this module can be referenced from
any of the four without creating an import cycle.

Errors are surfaced as messagebox.showerror dialogs but never raised
back to the caller — the originating GUI must keep working even if
the launch target is broken.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox


def _toplevel(parent: tk.Misc, title: str, geometry: str = "1200x800") -> tk.Toplevel:
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(geometry)
    win.minsize(1000, 600)
    try:
        win.transient(parent)
    except tk.TclError:
        pass
    return win


def open_exam_gui(parent: tk.Misc, auth=None) -> None:
    """Launch the Exam Scheduler in a Toplevel."""
    try:
        from education_system.university_system.modules.domain.academics.gui.exam_management.app import (
            ExamSchedulerApp,
        )
        win = _toplevel(parent, "Exam Scheduler", "1200x800")
        ExamSchedulerApp(win)
    except Exception as exc:
        messagebox.showerror("Error", f"Failed to open Exam Scheduler: {exc}")


def open_grade_gui(parent: tk.Misc, auth=None) -> None:
    """Launch the Grade Tracking GUI in a Toplevel."""
    try:
        from education_system.university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app import (
            GradeTrackingApp,
        )
        win = _toplevel(parent, "Grade Tracking", "1200x800")
        GradeTrackingApp(win, auth=auth)
    except Exception as exc:
        messagebox.showerror("Error", f"Failed to open Grade Tracking: {exc}")


def open_module_gui(parent: tk.Misc, auth=None) -> None:
    """Launch the Module Scheduling GUI in a Toplevel."""
    try:
        from education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui import (
            ModuleSchedulingGUI,
        )
        win = _toplevel(parent, "Module Scheduling", "1400x900")
        gui = ModuleSchedulingGUI(win)
        if auth is not None and hasattr(gui, "set_auth"):
            gui.set_auth(auth)
    except Exception as exc:
        messagebox.showerror("Error", f"Failed to open Module Scheduling: {exc}")


def open_course_gui(parent: tk.Misc, auth=None) -> None:
    """Launch the Course Management GUI in a Toplevel."""
    try:
        from education_system.university_system.modules.domain.academics.gui.course_management_gui.core.main_gui import (
            CourseManagementGUI,
        )
        win = _toplevel(parent, "Course Management", "1200x800")
        CourseManagementGUI(win, auth_system=auth)
    except Exception as exc:
        messagebox.showerror("Error", f"Failed to open Course Management: {exc}")


__all__ = [
    "open_exam_gui",
    "open_grade_gui",
    "open_module_gui",
    "open_course_gui",
]
