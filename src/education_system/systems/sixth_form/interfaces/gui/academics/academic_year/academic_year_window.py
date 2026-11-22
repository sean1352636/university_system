"""Tkinter views for Sixth Form Academic Year.

Sidebar sections (year structure, then the merged calendar):
* Years     — table of academic years, set-current, CRUD.
* Terms     — terms for the selected year.
* Breaks    — holidays / INSET / etc. for the selected year.
* Calendar  — date lookup + year summary.

Split 2026-10-22: this module is now a facade. The window entry point lives
here; widgets, tabs, dialogs and helpers live in sibling modules (_common,
_widgets, tab_*, dialogs) and every name is re-exported from here unchanged.
"""

from __future__ import annotations
import datetime as _dt
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui import window_sizing
from education_system.platform import branding
from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year as data,
)

# Re-export everything that used to be defined in this module.
from ._common import (
    logger,
    WIN_GEOMETRY,
    WIN_MINSIZE,
    _load_prefs,
    _save_prefs,
)
from ._widgets import (
    toast,
    Tooltip,
    ThemeManager,
    UndoStack,
    show_help_overlay,
    _export_year_json,
    _import_year_json,
)
from .tab_years import (
    YearsTab,
)
from .tab_terms import (
    TermsTab,
)
from .tab_breaks import (
    BreaksTab,
)
from .tab_calendar import (
    CalendarTab,
)


# Sidebar headings for the window's sections, keyed by tab text.
_SECTIONS = {
    "Years": "Year structure", "Terms": "Year structure",
    "Breaks": "Year structure", "Year Grid": "Year structure",
    "Upcoming": "Calendar", "All Events": "Calendar", "Day": "Calendar",
    "Month": "Calendar", "Week": "Calendar", "Agenda": "Calendar",
    "My Events": "Calendar",
    "Rooms": "Planning", "Y12 / Y13": "Planning", "Bookings": "Planning",
    "Trips": "Planning", "Series": "Planning",
    "Messages": "Admin", "Audit": "Admin", "Archive": "Admin",
    "Summary": "Admin",
}

def open_academic_year_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Academic Year & Calendar — {branding.SYSTEM_NAME}")

    # ── Load saved prefs (geometry, theme, last year, last tab) ──
    prefs = _load_prefs()
    window_sizing.fit(win, prefs.get("geometry", WIN_GEOMETRY), WIN_MINSIZE)

    theme = ThemeManager(win)
    theme.apply(prefs.get("dark", False))
    undo = UndoStack()

    state: dict = {
        "selected_year_id": prefs.get("last_year_id"),
        "_undo": undo,
        "_toast": lambda msg, **k: toast(win, msg, **k),
    }

    # ── Top toolbar (window-level): JSON export/import ────────
    toolbar = ttk.Frame(win)
    toolbar.pack(fill="x", padx=10, pady=(8, 0))
    ttk.Label(toolbar,
               text="📚  Academic Year & Calendar",
               font=("TkDefaultFont", 11, "bold")
               ).pack(side="left")

    def _toggle_dark() -> None:
        theme.apply(not theme.dark)
        toast(win, f"Theme: {'dark' if theme.dark else 'light'}",
                kind="info")

    def _open_help() -> None:
        show_help_overlay(win)

    btn_dark = ttk.Button(toolbar, text="🌗 Dark", width=8,
                              command=_toggle_dark)
    btn_dark.pack(side="right")
    Tooltip(btn_dark, "Toggle dark mode (Ctrl-D)")
    btn_help = ttk.Button(toolbar, text="? Help", width=8,
                              command=_open_help)
    btn_help.pack(side="right", padx=4)
    Tooltip(btn_help, "Show keyboard shortcuts (?)")
    btn_export = ttk.Button(toolbar, text="Export year (JSON)",
                                command=lambda: _export_year_json(win, state))
    btn_export.pack(side="right")
    Tooltip(btn_export, "Export the selected year, "
                          "its terms and breaks as JSON")
    btn_import = ttk.Button(toolbar, text="Import year (JSON)…",
                                command=lambda: _import_year_json(
                                    win, state, _refresh_all_tabs))
    btn_import.pack(side="right", padx=4)
    Tooltip(btn_import, "Import a year from a JSON file")

    # Sections down a sidebar, grouped, instead of a row of tabs.
    nb = SidebarBook(win, groups=_SECTIONS)
    nb.pack(fill="both", expand=True, padx=10, pady=(6, 0))

    # ── Bottom status bar ─────────────────────────────────────
    status = ttk.Frame(win, relief="sunken", padding=(8, 2))
    status.pack(fill="x", side="bottom")
    db_var = tk.StringVar(value=f"DB: {data.DB_PATH}")
    cur_var = tk.StringVar(value="")
    refresh_var = tk.StringVar(value="")
    ttk.Label(status, textvariable=db_var,
               foreground="#555").pack(side="left")
    ttk.Label(status, textvariable=refresh_var,
               foreground="#555").pack(side="right")
    ttk.Label(status, textvariable=cur_var,
               foreground="#055").pack(side="right", padx=12)

    def _refresh_status() -> None:
        cur = data.current_year()
        if cur is None:
            cur_var.set("No current year")
        else:
            cur_var.set(f"Current: {cur.name}")
        refresh_var.set(
            f"Updated {_dt.datetime.now().strftime('%H:%M:%S')}")

    def _goto(idx: int) -> None:
        try:
            nb.select(idx)
        except tk.TclError:
            pass

    years_tab = YearsTab(nb, state, goto_tab=_goto)
    terms_tab = TermsTab(nb, state)
    breaks_tab = BreaksTab(nb, state)
    calendar_tab = CalendarTab(nb, state)

    # ── Events calendar, merged in ─────────────────────────────
    # Academic Year owns the *shape* of the year; the calendar
    # package owns what happens in it. They were two adjacent menu
    # entries and two windows; they are now one window, two groups
    # of tabs. Imported lazily — the calendar package pulls in a
    # lot, and this window must stay cheap to open.
    try:
        from education_system.systems.sixth_form.interfaces.gui.academics.calendar import (  # noqa: E501
            calendar_views as _cal_views,
        )
        _cal_views.add_tabs(nb,
                            actor=_cal_views._actor(parent),
                            role=_cal_views._role(parent))
    except Exception:
        logger.exception("Calendar tabs unavailable; "
                         "showing year structure only")

    def _refresh_all_tabs() -> None:
        years_tab.refresh()
        terms_tab.refresh()
        breaks_tab.refresh()
        calendar_tab.refresh()
        _refresh_status()

    def _on_change(_evt=None) -> None:
        # When a child tab is activated, refresh against the latest
        # selected_year_id (set by the Years tab when the user
        # clicks a row).
        idx = nb.index("current")
        if idx == 1:
            terms_tab.refresh()
        elif idx == 2:
            breaks_tab.refresh()
        elif idx == 3:
            calendar_tab.refresh()
        _refresh_status()

    nb.bind("<<NotebookTabChanged>>", _on_change)
    _refresh_status()

    # ── Restore last-active tab from prefs ─────────────────────
    last_tab = prefs.get("last_tab", 0)
    if isinstance(last_tab, int) and 0 <= last_tab < nb.index("end"):
        try:
            nb.select(last_tab)
        except tk.TclError:
            pass

    # ── Window-level keybindings ───────────────────────────────
    def _do_undo(_e=None) -> None:
        item = undo.pop()
        if item is None:
            toast(win, "Nothing to undo", kind="warn")
            return
        label, fn = item
        try:
            fn()
            toast(win, f"Undid: {label}", kind="ok")
        except Exception as e:
            toast(win, f"Undo failed: {e}", kind="error")
        _refresh_all_tabs()

    def _select_tab(i: int) -> None:
        try:
            nb.select(i)
        except tk.TclError:
            pass

    win.bind("<Control-z>", _do_undo)
    win.bind("<Control-Z>", _do_undo)
    win.bind("<Control-d>", lambda _e: _toggle_dark())
    win.bind("<Control-r>", lambda _e: _refresh_all_tabs())
    win.bind("<Control-Key-1>", lambda _e: _select_tab(0))
    win.bind("<Control-Key-2>", lambda _e: _select_tab(1))
    win.bind("<Control-Key-3>", lambda _e: _select_tab(2))
    win.bind("<Control-Key-4>", lambda _e: _select_tab(3))
    win.bind("?", lambda _e: _open_help())
    win.bind("<F1>", lambda _e: _open_help())

    # ── Save prefs on close ────────────────────────────────────
    def _on_close() -> None:
        try:
            _save_prefs({
                "geometry": win.geometry(),
                "dark": theme.dark,
                "last_year_id": state.get("selected_year_id"),
                "last_tab": nb.index("current"),
            })
        except tk.TclError:
            pass
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)
    win.bind("<Control-s>", lambda _e: _on_close())
