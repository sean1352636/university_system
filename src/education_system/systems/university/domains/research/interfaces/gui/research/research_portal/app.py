"""The Research Portal window.

Who sees what:

* students – Dashboard and Ethics (their own applications);
* staff – everything except REF, which is for REF leads and the research
  office; Reports is for the office and heads of department.

Every tab works through ``university/application/research/``, which
checks permissions again, so a hidden tab is a convenience, not the guard.
When the portal opens, the day's research reminders are sent (once a day).
"""

from __future__ import annotations

import importlib
import logging
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)

logger = logging.getLogger(__name__)

_PKG = "education_system.systems.university.domains.research.interfaces.gui.research." \
       "research_portal"

#: (key, tab label, module, class, who may see it)
TABS = (
    ("dashboard", "Dashboard", "dashboard_tab", "DashboardTab", lambda w: True),
    ("projects", "Projects", "projects_tab", "ProjectsTab", lambda w: w.is_staff),
    ("ethics", "Ethics", "ethics_tab", "EthicsTab", lambda w: True),
    ("grants", "Grants", "grants_tab", "GrantsTab", lambda w: w.is_staff),
    ("outputs", "Outputs", "outputs_tab", "OutputsTab", lambda w: w.is_staff),
    ("ref", "REF", "ref_tab", "RefTab", lambda w: w.leads_ref()),
    ("ip", "IP & Commercialisation", "ip_tab", "IPTab", lambda w: w.is_staff),
    ("integrity", "Integrity", "integrity_tab", "IntegrityTab", lambda w: w.is_staff),
    ("degrees", "Research Degrees", "degrees_tab", "DegreesTab", lambda w: w.is_staff),
    ("people", "People", "people_tab", "PeopleTab", lambda w: w.is_staff),
    ("reports", "Reports", "reports_tab", "ReportsTab",
     lambda w: w.is_office or any(r == "head_of_department" for r, _ in w.roles)),
)

#: reminder / search ``ref`` area → tab key
AREAS = {"ethics": "ethics", "grant": "grants", "ip": "ip", "project": "projects",
         "declaration": "integrity", "output": "outputs"}


def _current_user(auth):
    user = getattr(auth, "current_user", None) if auth is not None else None
    if user:
        return user
    try:
        from education_system.systems.university.infrastructure.shared_context import get_auth
        shared = get_auth()
        return getattr(shared, "current_user", None) if shared else None
    except Exception:
        logger.debug("no shared auth", exc_info=True)
        return None


class ResearchPortal:
    """``host`` is a Toplevel / Frame to build into, or ``None`` for a
    window of its own (``run()`` then enters the main loop)."""

    def __init__(self, host=None, auth=None):
        self._owns_root = host is None
        self.auth = auth
        self.root = tk.Tk() if host is None else host
        if self._owns_root:
            self.root.title("Research Portal")
            self.root.geometry("1366x768")
            self.root.minsize(1100, 680)
        from education_system.systems.university.application.research import access as ra
        user = _current_user(auth)
        self.who = common.call(self.root, ra.from_user, user, quiet=True) if user else None
        self.tabs: dict[str, ttk.Frame] = {}
        if not self.who:
            ttk.Label(self.root, text="Sign in to use the Research Portal.",
                      padding=40, font=("Segoe UI", 12)).pack()
            return
        self._header()
        self.statusbar = ttk.Label(self.root, text="", padding=(10, 2), anchor="w")
        self.statusbar.pack(side="bottom", fill="x")        # before the notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(4, 0))
        self._build_tabs()
        self._daily_reminders()

    def _header(self):
        bar = ttk.Frame(self.root, padding=(14, 8))
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Research Office", font=("Segoe UI", 15, "bold")).pack(side="left")
        try:
            from education_system.platform.delivery.gui.portal_dismiss import add_dismiss_button
            add_dismiss_button(bar, self.root, style="ttk", padx=(12, 0))
        except Exception:
            logger.debug("dismiss button unavailable", exc_info=True)
        roles = sorted({r for r, _ in self.who.roles})
        role_text = ", ".join(r.replace("_", " ") for r in roles) or self.who.role
        ttk.Label(bar, text=f"{self.who.username} ({role_text})  ·  "
                            f"{datetime.now():%A %d %B %Y}").pack(side="right")

    def _build_tabs(self):
        for key, label, module, cls, allowed in TABS:
            if not allowed(self.who):
                continue
            try:
                tab_cls = getattr(importlib.import_module(f"{_PKG}.{module}"), cls)
                tab = tab_cls(self.notebook, self)
            except Exception as exc:
                logger.exception("Research Portal tab %s failed", key)
                tab = ttk.Frame(self.notebook)
                ttk.Label(tab, text=f"This tab could not be opened: {exc}",
                          padding=20).pack(anchor="nw")
            self.notebook.add(tab, text=f"  {label}  ")
            self.tabs[key] = tab
        for tab in self.tabs.values():
            if hasattr(tab, "refresh"):
                tab.refresh()

    def _daily_reminders(self):
        from education_system.systems.university.application.research import (
            reminders as research_reminders,
        )
        result = common.call(self.root, research_reminders.run, write=True, quiet=True)
        if isinstance(result, dict) and (result["expired"] or result["reminded"]):
            self.status(f"Reminders sent today: {result['reminded']}; ethics approvals "
                        f"expired: {result['expired']}")

    # ── used by the tabs ──
    def status(self, message):
        if hasattr(self, "statusbar"):
            self.statusbar.configure(text=message)

    def show(self, area, record_id=None):
        """Switch to the tab for ``area`` and open ``record_id`` there."""
        key = AREAS.get(area, area)
        tab = self.tabs.get(key)
        if tab is None:
            return
        self.notebook.select(tab)
        if record_id is not None and hasattr(tab, "open_record"):
            tab.open_record(record_id)

    def changed(self):
        """Something was written: refresh the dashboard's to-do list."""
        dash = self.tabs.get("dashboard")
        if dash is not None and hasattr(dash, "refresh"):
            dash.refresh()

    def run(self):
        if self._owns_root:
            self.root.mainloop()


def main():
    ResearchPortal().run()


if __name__ == "__main__":
    main()
