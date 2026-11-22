"""Wellbeing Casework — one window for counselling, Support to Study,
trusted contacts and personal emergency evacuation plans.

Each tab decides for itself what the signed-in person sees (the rules are
in the domain modules): the counselling team gets the referral → triage →
waiting list → sessions → discharge pathway and other staff a referral
form; support staff work Support to Study cases and trusted contacts;
estates, health & safety and disability staff see the PEEP register. A
student gets their own counselling referral, Support to Study case, trusted
contacts and evacuation plan.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)

logger = logging.getLogger(__name__)

TITLE = "Wellbeing Casework"
SECTIONS = ("counselling", "support_to_study", "trusted_contacts", "peeps")


def _tabs_for(auth) -> list[tuple[str, str]]:
    student = access.own_student_id(auth) is not None
    tabs = [("counselling", "Counselling")]
    if student or access.is_support_staff(auth):
        tabs += [("support_to_study", "Support to Study"),
                 ("trusted_contacts", "Trusted Contacts")]
    if student or access.is_staff(auth):
        tabs.append(("peeps", "Evacuation Plans (PEEPs)"))
    return tabs


class WellbeingCaseworkWindow:
    """``parent`` is a window (this opens its own) or a frame to build into
    (the main window's workspace). ``section`` picks the first tab."""

    def __init__(self, parent=None, auth=None, section=None):
        if auth is None:
            from education_system.systems.university.infrastructure.shared_context import get_auth
            auth = get_auth()
        self.auth = auth
        self._owns_window = parent is None or hasattr(parent, "wm_title")
        if self._owns_window:
            self.window = tk.Toplevel(parent) if parent is not None else tk.Tk()
            self.window.title(TITLE)
            from education_system.platform.delivery.gui import window_sizing
            window_sizing.install()
            window_sizing.center(self.window, 1400, 900, minsize=(1200, 800))
            self.frame = ttk.Frame(self.window)
            self.frame.pack(fill=tk.BOTH, expand=True)
        else:
            self.window = parent.winfo_toplevel()
            self.frame = parent
        self.tabs: dict[str, ttk.Frame] = {}
        self._build(section)

    def _build(self, section):
        if not access.current_user(self.auth):
            ttk.Label(self.frame, text="Sign in to use Wellbeing Casework.",
                      font=("Arial", 12)).pack(padx=20, pady=20)
            return
        head = ttk.Frame(self.frame, padding=(10, 8, 10, 0))
        head.pack(fill=tk.X)
        ttk.Label(head, text=TITLE, font=("Arial", 16, "bold")).pack(side=tk.LEFT)
        ttk.Label(head, text="Counselling, Support to Study, trusted contacts and evacuation "
                             "plans", foreground="#555555").pack(side=tk.LEFT, padx=12)
        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        builders = {"counselling": self._counselling, "support_to_study": self._sts,
                    "trusted_contacts": self._trusted, "peeps": self._peeps}
        for key, label in _tabs_for(self.auth):
            self._add(key, label, builders[key])
        tab = self.tabs.get(section)
        if tab is not None:
            self.notebook.select(tab)

    def _add(self, key, label, builder):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=label)
        self.tabs[key] = tab
        try:
            builder(tab).pack(fill=tk.BOTH, expand=True)
        except Exception as exc:
            logger.exception("Wellbeing casework tab %s failed", key)
            ttk.Label(tab, text=f"{label} could not be loaded: {exc}",
                      font=("Arial", 12)).pack(padx=20, pady=20)

    def _counselling(self, tab):
        from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.counselling_service import (
            CounsellingServicePanel,
        )
        return CounsellingServicePanel(tab, self.auth)

    def _sts(self, tab):
        from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.casework.support_to_study_gui import (
            SupportToStudyPanel,
        )
        return SupportToStudyPanel(tab, self.auth)

    def _trusted(self, tab):
        from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.casework.trusted_contacts_gui import (
            TrustedContactsPanel,
        )
        return TrustedContactsPanel(tab, self.auth)

    def _peeps(self, tab):
        from education_system.systems.university.domains.student_support.interfaces.gui.disability.peeps_gui import (
            PeepsPanel,
        )
        return PeepsPanel(tab, self.auth)


def open_casework(parent=None, auth=None, section=None) -> WellbeingCaseworkWindow:
    return WellbeingCaseworkWindow(parent, auth, section)
