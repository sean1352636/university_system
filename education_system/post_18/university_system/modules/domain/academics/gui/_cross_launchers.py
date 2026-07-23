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
from dataclasses import dataclass
from tkinter import messagebox
from typing import Any


@dataclass
class AcademicContext:
    """Pre-filter hint passed when one academic GUI launches a sibling.

    All fields optional. Callees inspect what they care about and ignore
    the rest — adding a field here never breaks an existing target.
    """
    student_id: str | None = None
    module_code: str | None = None
    course_code: str | None = None
    exam_id: int | None = None
    term: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, "")}


def _apply_context(gui_obj: Any, context: AcademicContext | None) -> None:
    """Best-effort hand-off: attach the context and call ``apply_context``
    if the target GUI implements it. Targets that don't are unaffected.
    """
    if context is None:
        return
    try:
        setattr(gui_obj, "academic_context", context)
        if hasattr(gui_obj, "apply_context"):
            gui_obj.apply_context(context)
    except Exception:
        pass


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


def open_exam_gui(parent: tk.Misc, auth=None, *,
                  context: AcademicContext | None = None) -> None:
    """Launch the Exam Scheduler in a Toplevel."""
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui.exam_management.app import (
            ExamSchedulerApp,
        )
        win = _toplevel(parent, "Exam Scheduler", "1200x800")
        gui = ExamSchedulerApp(win)
        _apply_context(gui, context)
    except Exception as exc:
        messagebox.showerror("Error", f"Failed to open Exam Scheduler: {exc}")


def open_grade_gui(parent: tk.Misc, auth=None, *,
                   context: AcademicContext | None = None) -> None:
    """Launch the Grade Tracking GUI in a Toplevel."""
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app import (
            GradeTrackingApp,
        )
        win = _toplevel(parent, "Grade Tracking", "1200x800")
        gui = GradeTrackingApp(win, auth=auth)
        _apply_context(gui, context)
    except Exception as exc:
        messagebox.showerror("Error", f"Failed to open Grade Tracking: {exc}")


def open_module_gui(parent: tk.Misc, auth=None, *,
                    context: AcademicContext | None = None) -> None:
    """Launch the Module Scheduling GUI in a Toplevel."""
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui.module_scheduling.main_gui import (
            ModuleSchedulingGUI,
        )
        win = _toplevel(parent, "Module Scheduling", "1400x900")
        gui = ModuleSchedulingGUI(win)
        if auth is not None and hasattr(gui, "set_auth"):
            gui.set_auth(auth)
        _apply_context(gui, context)
    except Exception as exc:
        messagebox.showerror("Error", f"Failed to open Module Scheduling: {exc}")


def open_course_gui(parent: tk.Misc, auth=None, *,
                    context: AcademicContext | None = None) -> None:
    """Launch the Course Management GUI in a Toplevel."""
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core.main_gui import (
            CourseManagementGUI,
        )
        win = _toplevel(parent, "Course Management", "1200x800")
        gui = CourseManagementGUI(win, auth_system=auth)
        _apply_context(gui, context)
    except Exception as exc:
        messagebox.showerror("Error", f"Failed to open Course Management: {exc}")


__all__ = [
    "AcademicContext",
    "open_exam_gui",
    "open_grade_gui",
    "open_module_gui",
    "open_course_gui",
]
