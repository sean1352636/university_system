"""The Exams Office window.

One tabbed screen for the exams officer's work outside entries and
results: timetable and clashes, invigilation, exam-room registers and
seating plans, access arrangements, special consideration, malpractice,
post-results services, certificates and board data files.

``open_exams_office(gui)`` fills the main window's content frame like
the other sixth-form screens; it is also reachable from buttons on the
Exam Entries and Results Day screens.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook

logger = logging.getLogger(__name__)

# (tab label, module under interfaces/gui, builder name)
_TABS: tuple[tuple[str, str, str], ...] = (
    ("Timetable & clashes", "assessment.exams_office.timetable_views", "build_tab"),
    ("Invigilation", "assessment.exams_office.invigilation_views", "build_tab"),
    ("Sittings & seating", "academics.attendance.attendance_exams_views", "build_tab"),
    ("Access arrangements", "assessment.exams_office.access_arrangements_views", "build_tab"),
    ("Special consideration", "assessment.exams_office.special_consideration_views",
     "build_tab"),
    ("Malpractice", "assessment.exams_office.malpractice_views", "build_tab"),
    ("Post-results", "assessment.exams_office.post_results_views", "build_tab"),
    ("Certificates", "assessment.exams_office.certificates_views", "build_tab"),
    ("Board files (EDI)", "assessment.exams_office.edi_views", "build_tab"),
)

_GUI_PKG = "education_system.systems.sixth_form.interfaces.gui."


def _build_lazily(gui, nb: ttk.Notebook) -> None:
    """Build each tab the first time it is shown (keeps opening fast)."""
    built: set[str] = set()
    specs: dict[str, tuple[str, str, str]] = {}

    def on_change(_e=None) -> None:
        tab_id = nb.select()
        if not tab_id or tab_id in built:
            return
        built.add(tab_id)
        frame = nb.nametowidget(tab_id)
        label, module, func = specs[str(tab_id)]
        try:
            import importlib
            getattr(importlib.import_module(_GUI_PKG + module), func)(gui, frame)
        except Exception as e:
            logger.exception("Exams Office tab %s failed", label)
            ttk.Label(frame, text=f"Could not open {label}: {e}",
                      foreground="#a33").pack(anchor="w")

    for spec in _TABS:
        frame = ttk.Frame(nb, padding=8)
        specs[str(frame)] = spec
        nb.add(frame, text=spec[0])
    nb.bind("<<NotebookTabChanged>>", on_change)
    on_change()


def open_exams_office(gui) -> None:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    frame = gui.content_frame
    head = ttk.Frame(frame)
    head.pack(fill="x", pady=(0, 8))
    ttk.Label(head, text="Exams Office", font=("", 16, "bold")).pack(side="left")

    def go(module: str, func: str = "open_directory") -> None:
        import importlib
        getattr(importlib.import_module(_GUI_PKG + module), func)(gui)

    ttk.Button(head, text="Exam Entries →",
               command=lambda: go("assessment.exam_entries.exam_entry_views")
               ).pack(side="right", padx=(6, 0))
    ttk.Button(head, text="Results Day →",
               command=lambda: go("assessment.exam_results.exam_result_views")
               ).pack(side="right")
    nb = SidebarBook(frame)
    nb.pack(fill="both", expand=True)
    _build_lazily(gui, nb)
    gui.status_var.set("Exams Office")
