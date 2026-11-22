"""The integrity cases list for screens that embed it (the assignment
system's admin tools), backed by the same rules and tab as the Academic
Integrity window."""

from __future__ import annotations

from tkinter import ttk

from education_system.systems.university.application.integrity import access
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.officer_tabs import (  # noqa: E501
    CasesTab,
)
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.window import (  # noqa: E501
    signed_in_user,
)
from education_system.systems.university.infrastructure.ui.record_screens import call


class _Host:
    def __init__(self, who, officer):
        self.who = who
        self.is_officer = officer
        self.tab = None

    def changed(self):
        if self.tab is not None:
            self.tab.refresh()


def build_cases_panel(parent, auth):
    """A cases tab inside ``parent``, or a refusal label. Officers see every
    case; other staff the cases they opened."""
    user = signed_in_user(auth)
    who = call(parent, access.from_user, user) if user else None
    if who is None or not who.is_staff:
        label = ttk.Label(parent, text="Integrity cases are for staff who are signed in.")
        label.pack(anchor="w", padx=10, pady=10)
        return label
    host = _Host(who, bool(call(parent, access.is_officer, who, quiet=True)))
    host.tab = CasesTab(parent, host)
    host.tab.pack(fill="both", expand=True)
    host.tab.refresh()
    return host.tab
