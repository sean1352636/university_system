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
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

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
        logger.debug("Suppressed exception", exc_info=True)


def _toplevel(parent: tk.Misc, title: str, geometry: str = "1200x800") -> tk.Toplevel:
    win = tk.Toplevel(parent)
    win.title(title)
    # geometry() with a size but no offset leaves the window at the
    # Toplevel default position, which lands it in a screen corner.
    # center() clamps to the display and supplies the offset.
    try:
        from education_system.platform.delivery.gui.window_sizing import center
        w, h = (int(part) for part in geometry.lower().split("x", 1))
        center(win, w, h, minsize=(1000, 600))
    except Exception:
        logger.debug("center() unavailable; falling back", exc_info=True)
        win.geometry(geometry)
        win.minsize(1000, 600)
    try:
        win.transient(parent)
    except tk.TclError:
        pass
    return win


def open_exam_gui(parent: tk.Misc, auth=None, *,
                  context: AcademicContext | None = None) -> None:
    """Launch Exam Management in a Toplevel.

    This opened ``ExamSchedulerApp`` directly. Exam Management already
    contains the scheduler — ``ExamPortalGUI``'s Scheduling tab embeds the
    whole of it — so opening the scheduler standalone gave a second, narrower
    window onto the same nine tabs. Every caller (Timetable Manager, Course
    Management, Module Scheduling, Grade Tracking, the Assignment GUI and the
    assessment editor) now lands on the one exam surface.

    Sized to match the main GUI's own Exam Management window rather than the
    smaller default this helper uses for the other academic GUIs.
    """
    try:
        from education_system.systems.university.domains.academics.interfaces.gui.exam_management import (
            ExamPortalGUI,
        )
        win = _toplevel(parent, "Exam Management", "1400x900")
        try:
            win.minsize(1200, 800)
        except tk.TclError:
            pass
        gui = ExamPortalGUI(parent=win, auth=auth)
        _apply_context(gui, context)
    except Exception as exc:
        messagebox.showerror(_t('gui.academics.cross_launchers.dialogs.error', default="Error"), f"Failed to open Exam Management: {exc}")


def open_grade_gui(parent: tk.Misc, auth=None, *,
                   context: AcademicContext | None = None) -> None:
    """Launch the Grade Tracking GUI in a Toplevel."""
    try:
        from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.grade_tracking_app import (
            GradeTrackingApp,
        )
        win = _toplevel(parent, "Grade Tracking", "1200x800")
        gui = GradeTrackingApp(win, auth=auth)
        _apply_context(gui, context)
    except Exception as exc:
        messagebox.showerror(_t('gui.academics.cross_launchers.dialogs.error', default="Error"), f"Failed to open Grade Tracking: {exc}")


def open_module_gui(parent: tk.Misc, auth=None, *,
                    context: AcademicContext | None = None) -> None:
    """Launch the Module Scheduling GUI in a Toplevel."""
    try:
        from education_system.systems.university.domains.academics.interfaces.gui.module_scheduling.main_gui import (
            ModuleSchedulingGUI,
        )
        win = _toplevel(parent, "Module Scheduling", "1400x900")
        gui = ModuleSchedulingGUI(win, auth=auth)
        if auth is not None and hasattr(gui, "set_auth"):
            gui.set_auth(auth)
        _apply_context(gui, context)
    except Exception as exc:
        messagebox.showerror(_t('gui.academics.cross_launchers.dialogs.error', default="Error"), f"Failed to open Module Scheduling: {exc}")


def open_course_gui(parent: tk.Misc, auth=None, *,
                    context: AcademicContext | None = None):
    """Launch the Course Management GUI in a Toplevel."""
    try:
        from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.core.main_gui import (
            CourseManagementGUI,
        )
        win = _toplevel(parent, "Course Management", "1200x800")
        gui = CourseManagementGUI(win, auth_system=auth)
        _apply_context(gui, context)
        # Returned so a caller can select the tab it actually wanted.
        return gui
    except Exception as exc:
        messagebox.showerror(_t('gui.academics.cross_launchers.dialogs.error', default="Error"), f"Failed to open Course Management: {exc}")
        return None



def open_accessibility_gui(parent: tk.Misc, auth=None, *,
                           context: AcademicContext | None = None) -> None:
    """Launch the Accessibility & Accommodation Tools GUI.

    This is the single place accommodations are managed — accessibility
    profiles, the request/approval workflow, general (all-assessment)
    accommodations, per-exam arrangements and assistive tech. The
    assignment system links here rather than keeping its own copy.
    """
    try:
        from education_system.systems.university.domains.pastoral.interfaces.gui.accessibility_tools_gui import (
            AccessibilityToolsGUI,
        )
        gui = AccessibilityToolsGUI(parent, auth=auth)
        _apply_context(gui, context)
    except Exception as exc:
        messagebox.showerror(
            _t('gui.academics.cross_launchers.dialogs.error', default="Error"),
            f"Failed to open Accessibility Tools: {exc}")


__all__ = [
    "AcademicContext",
    "open_exam_gui",
    "open_grade_gui",
    "open_module_gui",
    "open_course_gui",
    "open_accessibility_gui",
]
