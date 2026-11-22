"""Open a converted applicant's real Student Directory profile.

The profile is drawn in the main window's content area
(``student_views.open_profile(gui, student_id)``), the same way Advanced
Search opens a student. The admissions window is opened from the main
window, so the main GUI object is found from the window's Tk root; when
admissions runs on its own (no main window) a read-only summary is shown
instead.
"""

from __future__ import annotations

import logging
import tkinter as tk

from education_system.platform.delivery.gui.parented_dialogs import messagebox

logger = logging.getLogger(__name__)


def _main_gui(widget: tk.Misc | None):
    """The main sixth form window object whose Tk root owns *widget*.

    The Admissions window names it (``main_gui``) when it was opened
    from the main window; standalone, there is none."""
    w = widget
    while w is not None:
        gui = getattr(w, "main_gui", None)
        if gui is not None and hasattr(gui, "content_frame"):
            return gui
        w = getattr(w, "master", None)
    return None


def open_student(widget: tk.Misc | None, student_id: str) -> None:
    gui = None
    try:
        gui = _main_gui(widget)
    except Exception:  # noqa: BLE001 — fall back to the summary
        logger.debug("main window lookup failed", exc_info=True)
    if gui is not None:
        try:
            from education_system.systems.sixth_form.interfaces.gui.learners.students import (
                student_views,
            )
            student_views.open_profile(gui, student_id)
            root = getattr(gui, "root", None)
            if root is not None:
                root.deiconify()
                root.lift()
                root.focus_force()
            return
        except Exception as e:  # noqa: BLE001 — shown
            logger.exception("Could not open student profile %s", student_id)
            messagebox.showerror("Student record", str(e))
            return
    _summary(student_id)


def _summary(student_id: str) -> None:
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students,
        )
        st = students.get_student(student_id)
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Student record", str(e))
        return
    if st is None:
        messagebox.showinfo("Student record",
                            f"Student {student_id} not found.")
        return
    messagebox.showinfo(
        f"Student {st.student_id}",
        f"{st.first_name} {st.last_name}\n"
        f"Email: {getattr(st, 'email', '—')}\n"
        f"Subjects: {getattr(st, 'subject_1', '—')}, "
        f"{getattr(st, 'subject_2', '—')}, {getattr(st, 'subject_3', '—')}"
        "\n\n(Open the Student Directory from the main window for the full "
        "profile.)")
