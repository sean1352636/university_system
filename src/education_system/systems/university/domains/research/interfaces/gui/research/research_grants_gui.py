"""Research grants, as embedded in the Finance window.

The same Grants tab as the Research Portal (``research_portal/grants_tab``),
hosted on its own: :class:`ResearchGrantsGUI` builds it inside Finance's
tab (or a window of its own), and :func:`launch_research_grants_gui` opens
it standalone. The rules are ``university/application/research/grants``.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)


class _Host:
    """The little of the portal a tab needs: who is signed in, and hooks."""

    def __init__(self, root, who):
        self.root = root
        self.who = who

    def show(self, area, record_id=None):
        pass

    def changed(self):
        pass

    def status(self, message):
        pass


def _researcher(parent, auth):
    from education_system.systems.university.application.research import access as ra
    from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
        common,
    )
    user = getattr(auth, "current_user", None) if auth is not None else None
    if not user:
        try:
            from education_system.systems.university.infrastructure.shared_context import (
                get_auth,
            )
            user = getattr(get_auth(), "current_user", None)
        except Exception:
            logger.debug("no shared auth", exc_info=True)
    return common.call(parent, ra.from_user, user, quiet=True) if user else None


class ResearchGrantsGUI:
    """``ResearchGrantsGUI(root, auth, parent_container=frame)``."""

    def __init__(self, root, auth=None, parent_container=None):
        self.root = root
        if parent_container is None:
            parent_container = tk.Toplevel(root)
            parent_container.title("Research Grants")
            parent_container.geometry("1366x768")
        self.container = parent_container
        who = _researcher(parent_container, auth)
        if who is None or not who.is_staff:
            ttk.Label(parent_container, text="Research grants are for signed-in staff.",
                      padding=30).pack(anchor="nw")
            self.tab = None
            return
        from education_system.systems.university.domains.research.interfaces.gui.research.research_portal.grants_tab import (  # noqa: E501
            GrantsTab,
        )
        self.tab = GrantsTab(parent_container, _Host(root, who))
        self.tab.pack(fill="both", expand=True)
        self.tab.refresh()


def launch_research_grants_gui(root=None, auth=None):
    """Open the grants screen in a window of its own."""
    owns = root is None
    if owns:
        root = tk.Tk()
        root.withdraw()
    gui = ResearchGrantsGUI(root, auth)
    if owns:
        gui.container.protocol("WM_DELETE_WINDOW", root.destroy)
        root.mainloop()
    return gui


__all__ = ["ResearchGrantsGUI", "launch_research_grants_gui"]
