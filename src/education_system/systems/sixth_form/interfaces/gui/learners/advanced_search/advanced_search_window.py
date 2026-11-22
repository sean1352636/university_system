"""Tkinter views for Sixth Form Advanced Search.

Single window with three tabs:
* Search          — query bar + scope checkboxes + results treeview
                    grouped by scope.
* Saved Searches  — list / run / new / edit / delete saved queries.
* History         — recent runs with re-run / clear.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform import branding
from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.domain.learners.advanced_search import _db as search_db

logger = logging.getLogger(__name__)

from ._widgets import (  # noqa: F401 — re-exported
    WIN_GEOMETRY,
    WIN_MINSIZE,
    _ROW_TAG_COLOURS,
    _DENSITY_ROWHEIGHT,
    _UI_STORE_NAME,
    _ui_store_path,
    _load_ui_store,
    _save_ui_store,
    _load_ann_store,
    _save_ann_store,
    _ann_key,
    _get_annotation,
    _append_action_log,
    _read_action_log,
    _soundex,
    _phonetic_match,
    _sparkline,
    _SHORTCUT_HELP,
    _NL_STOP,
    _NL_SUBJECTS,
    _NL_THEMES,
    _NL_STATUS,
    _nl_to_query,
    _lint_query,
    _choose_from,
)
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from .search_results import _ResultsMixin  # noqa: F401
from .search_actions import _ActionsMixin  # noqa: F401
from .search_tab import SearchTab  # noqa: F401
from .saved_history_tabs import HistoryTab, SavedDialog, SavedTab  # noqa: F401
from .tools_tab import ToolsTab  # noqa: F401
from . import open_handlers


def open_advanced_search_window(parent=None, *, query: str | None = None,
                                scopes: list[str] | None = None) -> None:
    """Open Advanced Search; *query*/*scopes* run a search straight away
    (the Student Directory uses this to hand its search over)."""
    search_db.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Advanced Search — {branding.SYSTEM_NAME}")
    # Clamped to the screen: 1400x900 is taller than a 1366x768 laptop,
    # which pushed the bottom of the Search tab off-screen.
    window_sizing.fit(win, WIN_GEOMETRY, WIN_MINSIZE)

    # One section at a time, chosen from the sidebar, instead of every
    # control crammed onto a single tab.
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    search_tab = SearchTab(nb)
    SavedTab(nb, search_tab)
    HistoryTab(nb, search_tab)
    ToolsTab(nb)
    # "Open" on a result goes to its record screen in the main window.
    open_handlers.register(parent, win)
    if query is not None:
        search_tab.load_query(query, scopes)
