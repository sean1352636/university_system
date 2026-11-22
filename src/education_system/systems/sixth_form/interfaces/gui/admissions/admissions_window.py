"""Tkinter views for Sixth Form Admissions.

Notebook tabs:
* Open Pipeline    — applicants still in process (filterable).
* All Applicants   — every applicant including terminal states.
* Interviews       — interview scheduling overview.
* Summary          — pipeline counts.
* Offers, Waitlist, Tasks, Analytics.
* Entry Requirements, Results Day, Open Events, References,
  Online Verification, Year 11 Transition — added by workflow_tabs.py.
* Interview Slots, Interview Rooms (Applications); Cycles, Places &
  Capacity, Oversubscription, Feeder Schools (Cycles & places);
  Insights (Results & reporting); Intake Log, Archive, Erasure Requests,
  Retention, DSL Queue (Records & data protection) — the pages_*
  modules, also added by workflow_tabs.py.

Split 2026-10-22: this module is now a facade. The window entry point lives
here; the tabs, dialogs and helpers live in sibling modules (_common, _sidecar,
tab_*, dialogs_*) and every name is re-exported from here unchanged.
"""

from __future__ import annotations
import tkinter as tk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui import window_sizing
from education_system.platform import branding
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)

# Re-export everything that used to be defined in this module.
from ._common import (
    WIN_GEOMETRY,
    WIN_MINSIZE,
)
from .tab_applicants import (
    ApplicantsTab,
)
from .tab_interviews import (
    InterviewsTab,
)
from .tab_summary_analytics import (
    SummaryTab,
    AnalyticsTab,
)
from .tab_offers_tasks_waitlist import (
    OffersTab,
    TasksTab,
    WaitlistTab,
)


# Sidebar headings for the window's sections, keyed by tab text.
_SECTIONS = {
    "Open Pipeline": "Applications", "All Applicants": "Applications",
    "Interviews": "Applications", "Offers": "Applications",
    "Waitlist": "Applications", "Tasks": "Applications",
    "Open Events": "Recruitment", "Year 11 Transition": "Recruitment",
    "Entry Requirements": "Recruitment",
    "Online Verification": "Recruitment", "References": "Recruitment",
    "Results Day": "Results & reporting", "Summary": "Results & reporting",
    "Analytics": "Results & reporting",
    # Pages added 2026-10-27 (pages_*); new groups come after the old ones.
    "Interview Slots": "Applications", "Interview Rooms": "Applications",
    "Cycles": "Cycles & places", "Places & Capacity": "Cycles & places",
    "Oversubscription": "Cycles & places",
    "Feeder Schools": "Cycles & places",
    "Insights": "Results & reporting",
    "Intake Log": "Records & data protection",
    "Archive": "Records & data protection",
    "Erasure Requests": "Records & data protection",
    "Retention": "Records & data protection",
    "DSL Queue": "Records & data protection",
}


def open_admissions_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Admissions — {branding.SYSTEM_NAME}")
    window_sizing.fit(win, WIN_GEOMETRY, WIN_MINSIZE)
    # Lets "Open student record" show the profile in the main window.
    if parent is not None and hasattr(parent, "content_frame"):
        win.main_gui = parent

    # Sections down a sidebar, grouped, instead of a row of tabs.
    nb = SidebarBook(win, groups=_SECTIONS, title="Admissions")
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ApplicantsTab(nb, open_only=True, label="Open Pipeline")
    all_tab = ApplicantsTab(nb, open_only=False, label="All Applicants")
    InterviewsTab(nb)
    OffersTab(nb)
    WaitlistTab(nb)
    TasksTab(nb)
    SummaryTab(nb, notebook=nb, drill_tab=all_tab)
    AnalyticsTab(nb)
    from education_system.systems.sixth_form.interfaces.gui.admissions import (
        workflow_tabs,
    )
    workflow_tabs.add_workflow_tabs(nb)
