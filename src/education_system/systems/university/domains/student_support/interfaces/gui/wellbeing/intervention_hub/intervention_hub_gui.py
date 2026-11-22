"""Early Warning & Interventions — one window for the Early Warning System,
Intervention Support and Intervention Outcomes.

These were three sidebar buttons opening three separate windows: Early
Warning (risk scores, interventions, coaching, tutoring, indicators),
Support Cases (the at-risk caseload — risk, status, intervention type,
contact log, report) and Outcomes (pre/post scores, sessions and
value-added). They are one row of tabs: Early Warning's five, then
Support Cases, Outcomes, and Student Overview, which shows one student
across all three and links a support case to Early Warning
interventions.

Runs embedded in a workspace tab, or standalone via ``main()`` when the
main GUI falls back to a subprocess (identity then arrives in the
``EDU_AUTH_*`` environment variables).
"""

from __future__ import annotations

import logging
import os
import pathlib
import sys
import tkinter as tk
from types import SimpleNamespace
from tkinter import ttk

if __name__ == "__main__":
    # Run as a file by the subprocess launcher: make the package importable.
    _p = pathlib.Path(__file__).resolve()
    while _p.parent != _p and not (_p / "education_system").is_dir():
        _p = _p.parent
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

logger = logging.getLogger(__name__)

__all__ = ["InterventionHubGUI", "launch_intervention_hub_gui", "main"]

def _get_current_user(auth=None):
    """The signed-in user: the caller's auth, then EDU_AUTH_* env vars
    (subprocess launch), then the in-process global auth."""
    user = getattr(auth, "current_user", None) if auth is not None else None
    if user:
        return user
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    if user_id or username:
        perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username,
            'role': os.environ.get('EDU_AUTH_ROLE') or '',
            'email': os.environ.get('EDU_AUTH_EMAIL') or '',
            'permissions': [p for p in perms_raw.split(',') if p],
        }
    try:
        from education_system.systems.university.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _early_warning_tabs(hub):
    """Adds the five Early Warning tabs straight into the window's notebook."""
    from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.intervention_hub.early_warning_tab import (
        EarlyWarningGUI,
    )
    # A subprocess launch has no auth object, only the env identity.
    auth = hub.auth if getattr(hub.auth, "current_user", None) else SimpleNamespace(current_user=hub.user)
    return EarlyWarningGUI(hub.window, auth, on_close=hub.close, notebook=hub.notebook,
                           status_var=hub.status_var, on_overview=hub.open_overview)


def _support_tab(frame, hub):
    from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.intervention_hub.support_tab import (
        InterventionSupportSystem,
    )
    return InterventionSupportSystem(frame, user=hub.user, on_overview=hub.open_overview)


def _outcomes_tab(frame, hub):
    from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.intervention_hub.outcomes_tab import (
        InterventionOutcomesFrame,
    )
    panel = InterventionOutcomesFrame(frame, user=hub.user)
    panel.pack(fill="both", expand=True)
    return panel


def _overview_tab(frame, hub):
    from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.intervention_hub.overview_tab import (
        StudentOverviewFrame,
    )
    panel = StudentOverviewFrame(frame, user=hub.user, hub=hub)
    panel.pack(fill="both", expand=True)
    return panel


class InterventionHubGUI:
    """One row of tabs over early warning, support cases, outcomes and the
    per-student overview that links them."""

    #: Tabs after the five Early Warning ones: (key, label, builder). Built
    #: one at a time so a broken screen costs its own tab, not the window.
    TABS = (
        ("support", "🎓  Support Cases", _support_tab),
        ("outcomes", "📈  Outcomes", _outcomes_tab),
        ("overview", "🔗  Student Overview", _overview_tab),
    )

    def __init__(self, parent=None, auth=None, start_tab=None):
        self.auth = auth
        self.user = _get_current_user(auth)
        self.panels = {}

        # A workspace tab Frame has no wm_title; a Tk/Toplevel does.
        if parent is not None and not hasattr(parent, "wm_title"):
            self.window = parent
            self._owns_window = False
        else:
            self.window = tk.Toplevel(parent) if parent else tk.Tk()
            self.window.title("Early Warning & Interventions")
            self._owns_window = True
            self._maximise()

        self._build()
        self.select(start_tab)

    def _maximise(self):
        """Open full screen, like the main window: ``zoomed`` where the
        window manager honours it, else a screen-sized geometry."""
        win = self.window
        for attempt in (lambda: win.state("zoomed"),
                        lambda: win.attributes("-zoomed", True)):
            try:
                attempt()
                win.update_idletasks()
                if win.winfo_width() > 400:
                    return
            except Exception:
                logger.debug("maximise attempt unavailable", exc_info=True)
        try:
            from education_system.platform.delivery.gui.window_sizing import usable_size
            width, height = usable_size(win)
        except Exception:
            width, height = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{width}x{height}+0+0")
        win.minsize(1100, 700)

    def _build(self):
        # Status bar first so a short screen squeezes the tabs, not it.
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.window, textvariable=self.status_var, relief=tk.SUNKEN,
                  anchor=tk.W).pack(fill=tk.X, side=tk.BOTTOM)

        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill="both", expand=True)
        self._frames = {}

        try:
            ew = _early_warning_tabs(self)
            self.panels["early_warning"] = ew
            self._frames["early_warning"] = getattr(ew, "at_risk_tab", None)
        except Exception as exc:
            logger.exception("Early Warning tabs failed to build")
            frame = tk.Frame(self.notebook, bg="#f0f4f8")
            self.notebook.add(frame, text="⚠️  Early Warning")
            self._frames["early_warning"] = frame
            ttk.Label(frame, text=f"Early Warning could not be loaded.\n\n{exc}",
                      justify="center", padding=30).pack(expand=True)

        for key, label, builder in self.TABS:
            frame = tk.Frame(self.notebook, bg="#f0f4f8")
            self.notebook.add(frame, text=label)
            self._frames[key] = frame
            try:
                self.panels[key] = builder(frame, self)
            except Exception as exc:
                logger.exception("Interventions tab %r failed to build", label)
                ttk.Label(frame,
                          text=f"{label.strip()} could not be loaded.\n\n{exc}",
                          justify="center", padding=30).pack(expand=True)

    def select(self, key):
        """Raise a tab by key (``early_warning`` = At-Risk Students,
        ``support``, ``outcomes``, ``overview``)."""
        frame = self._frames.get(key) if key else None
        if frame is not None:
            self.notebook.select(frame)

    # -- Cross-tab links -------------------------------------------------

    def open_overview(self, student_id):
        """Student Overview for one student."""
        panel = self.panels.get("overview")
        if panel is not None:
            self.select("overview")
            panel.show_student(student_id)

    def open_support_case(self, student_id):
        panel = self.panels.get("support")
        if panel is not None:
            self.select("support")
            panel.select_student(student_id)

    def open_outcomes(self, intervention_id):
        panel = self.panels.get("outcomes")
        if panel is not None:
            self.select("outcomes")
            panel.prefill(intervention_id)

    def refresh_linked(self, refresh_support=False):
        """Another tab changed shared data: reload what shows it."""
        ew = self.panels.get("early_warning")
        if ew is not None and hasattr(ew, "load_interventions"):
            try:
                ew.load_interventions()
            except Exception:
                logger.exception("Early Warning interventions reload failed")
        outcomes = self.panels.get("outcomes")
        if outcomes is not None:
            outcomes.refresh()
        support = self.panels.get("support")
        if refresh_support and support is not None:
            support.reload()

    def close(self):
        """Return to Homescreen: close this window, or its workspace tab."""
        from education_system.platform.delivery.gui.portal_dismiss import dismiss
        dismiss(self.window)

    def run(self):
        if self._owns_window and isinstance(self.window, tk.Tk):
            self.window.mainloop()


def launch_intervention_hub_gui(parent=None, auth=None, start_tab=None):
    """Open the Early Warning & Interventions window."""
    try:
        return InterventionHubGUI(parent, auth=auth, start_tab=start_tab)
    except Exception as exc:
        logger.exception("Failed to launch Early Warning & Interventions")
        from tkinter import messagebox
        messagebox.showerror("Error", f"Failed to open Early Warning & Interventions: {exc}")
        return None


def main() -> None:
    try:
        from education_system.systems.university.infrastructure.logging.log_config import configure_logging
        configure_logging(name=__name__)
    except Exception:
        logger.debug("Central log config unavailable", exc_info=True)
    InterventionHubGUI().run()


if __name__ == "__main__":
    main()
