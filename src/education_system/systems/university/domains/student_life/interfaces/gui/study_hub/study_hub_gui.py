"""Study Hub — one window for everything a student does to study.

This was three separate buttons opening three separate windows: AI Study
Tools, Study Matching and Study Recommendations. They were not three
features so much as three views of one thing — the same student, the
same profile, the same record of hours studied — and because they were
built apart they disagreed with each other. See
``study_hub/services/profiles.py`` for what that cost.

Each tab is the original screen, unchanged: they already accepted a
parent Frame, so they embed directly rather than being rewritten. The
Recommendations and Study Partners screens now live in this package
(``recommendations_tab`` / ``partners_tab``); their old
``study_recommendations`` and ``study_matching`` packages are gone, and
the main window has one Study Hub button in place of their two.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

__all__ = ["StudyHubGUI", "launch_study_hub_gui"]


class StudyHubGUI:
    """Tabbed container over the three study screens."""

    #: (tab label, module path, class name). Imported lazily and one at a
    #: time so a broken screen costs its own tab, not the whole hub.
    TABS = (
        ("📘  Study Plan",
         "education_system.systems.university.domains.student_life.interfaces."
         "gui.ai_study.ai_study_gui", "AIStudyGUI"),
        ("💡  Recommendations",
         "education_system.systems.university.domains.student_life.interfaces."
         "gui.study_hub.recommendations_tab", "StudyRecommendationGUI"),
        ("🤝  Study Partners",
         "education_system.systems.university.domains.student_life.interfaces."
         "gui.study_hub.partners_tab", "StudyMatchingGUI"),
    )

    def __init__(self, parent=None, auth=None):
        self.auth = auth
        self.panels = {}

        # A workspace tab Frame has no wm_title; a Tk/Toplevel does.
        if parent is not None and not hasattr(parent, "wm_title"):
            self.window = parent
            self._owns_window = False
        else:
            self.window = tk.Toplevel(parent) if parent else tk.Tk()
            self.window.title(_t("study_hub.window.title", default="Study Hub"))
            self._owns_window = True
            try:
                from education_system.platform.delivery.gui.window_sizing import center
                center(self.window, 1200, 820, minsize=(900, 600))
            except Exception:
                self.window.geometry("1200x820")

        self._build()

    def _build(self):
        header = tk.Frame(self.window, bg="#2c3e50")
        header.pack(fill="x")
        tk.Label(header, text=_t("study_hub.header.title", default="Study Hub"),
                 font=("Segoe UI", 16, "bold"), bg="#2c3e50", fg="white",
                 anchor="w").pack(anchor="w", padx=18, pady=(12, 0))
        tk.Label(header,
                 text=_t("study_hub.header.subtitle",
                         default="Plan your study, act on recommendations, "
                                 "and find people to study with."),
                 font=("Segoe UI", 9), bg="#2c3e50", fg="#bdc3c7",
                 anchor="w").pack(anchor="w", padx=18, pady=(2, 12))

        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        for label, module_path, class_name in self.TABS:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=label)
            self._build_tab(frame, label, module_path, class_name)

    def _build_tab(self, frame, label, module_path, class_name):
        """Embed one screen, reporting failure in its own tab."""
        try:
            import importlib
            panel_cls = getattr(importlib.import_module(module_path), class_name)
            self.panels[label] = panel_cls(frame, auth=self.auth)
        except Exception as exc:
            logger.exception("Study Hub tab %r failed to build", label)
            ttk.Label(frame,
                      text=f"{label.strip()} could not be loaded.\n\n{exc}",
                      justify="center", padding=30).pack(expand=True)

    def run(self):
        if self._owns_window and isinstance(self.window, tk.Tk):
            self.window.mainloop()


def launch_study_hub_gui(parent=None, auth=None):
    """Open the Study Hub."""
    try:
        return StudyHubGUI(parent, auth=auth)
    except Exception as exc:
        logger.exception("Failed to launch Study Hub")
        from tkinter import messagebox
        messagebox.showerror(_t("common.error", default="Error"),
                             f"Failed to open Study Hub: {exc}")
        return None
