"""Tkinter views for Sixth Form Academic Year.

Notebook with 4 tabs:
* Years     — table of academic years, set-current, CRUD.
* Terms     — terms for the selected year.
* Breaks    — holidays / INSET / etc. for the selected year.
* Calendar  — date lookup + year summary.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.academics.academic_year import (
    academic_year as data,
)
from education_system.post_16.sixthform_system.modules.domain.academics.academic_year.academic_year import (
    AcademicYear,
    Break,
    BREAK_TYPES,
    DEFAULT_BREAK_TYPE,
    DEFAULT_TERM_NAME,
    DEFAULT_YEAR_STATUS,
    Term,
    TERM_NAMES,
    ValidationError,
    YEAR_STATUSES,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

# Shared term palette — re-used by Gantt strip and (later) Calendar tab.
TERM_COLOURS: dict[str, str] = {
    "Autumn":   "#f6c453",
    "Autumn 1": "#f6c453",
    "Autumn 2": "#e3a13a",
    "Spring":   "#9ad17e",
    "Spring 1": "#9ad17e",
    "Spring 2": "#74b35e",
    "Summer":   "#7ec4f4",
    "Summer 1": "#7ec4f4",
    "Summer 2": "#5ba6dc",
}
DEFAULT_TERM_COLOUR: str = "#bdbdbd"


def _term_colour(name: str) -> str:
    return TERM_COLOURS.get(name, DEFAULT_TERM_COLOUR)


# ══ GUI polish utilities (items 39-44) ════════════════════════════
#
# Toast, Tooltip, prefs persistence, dark-mode theme, undo stack,
# help overlay. Kept inline so the module stays self-contained.

import json as _json
import os as _os

PREFS_PATH = _os.path.join(
    _os.path.expanduser("~"), ".config", "edu_system",
    "sixthform_academic_year.json")


def _load_prefs() -> dict:
    try:
        with open(PREFS_PATH, encoding="utf-8") as fh:
            d = _json.load(fh)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_prefs(prefs: dict) -> None:
    try:
        _os.makedirs(_os.path.dirname(PREFS_PATH), exist_ok=True)
        with open(PREFS_PATH, "w", encoding="utf-8") as fh:
            _json.dump(prefs, fh, indent=2)
    except OSError as e:
        logger.warning("Could not save prefs: %s", e)


# ── Toast ────────────────────────────────────────────────────────

class Toast:
    """Non-blocking notification at the bottom-right of a window.
    Auto-dismisses after ``ms`` milliseconds."""

    _Y_OFFSET = 60

    def __init__(self, parent: tk.Misc, message: str,
                  *, kind: str = "info", ms: int = 2500) -> None:
        root = parent.winfo_toplevel()
        bg = {"info": "#323232", "warn": "#b66600",
                "error": "#a4322a", "ok": "#2c8a4a"}.get(kind, "#323232")
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        try:
            self.top.attributes("-topmost", True)
        except tk.TclError:
            pass
        lbl = tk.Label(self.top, text=message, fg="white", bg=bg,
                         padx=14, pady=8, font=("TkDefaultFont", 10))
        lbl.pack()
        root.update_idletasks()
        x = root.winfo_rootx() + root.winfo_width() - 320
        y = root.winfo_rooty() + root.winfo_height() - self._Y_OFFSET
        self.top.geometry(f"+{x}+{y}")
        self.top.after(ms, self._close)
        lbl.bind("<Button-1>", lambda _e: self._close())

    def _close(self) -> None:
        try:
            self.top.destroy()
        except tk.TclError:
            pass


def toast(parent: tk.Misc, message: str, *,
            kind: str = "info") -> None:
    """Module-level convenience wrapper."""
    try:
        Toast(parent, message, kind=kind)
    except tk.TclError as e:
        logger.warning("Toast failed: %s", e)


# ── Tooltip ──────────────────────────────────────────────────────

class Tooltip:
    """Hover-triggered tooltip on any widget."""

    def __init__(self, widget: tk.Misc, text: str,
                  *, delay_ms: int = 600) -> None:
        self.widget = widget
        self.text = text
        self.delay = delay_ms
        self._after_id: str | None = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, _e=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._tip is not None:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._tip = tk.Toplevel(self.widget)
        self._tip.overrideredirect(True)
        self._tip.geometry(f"+{x}+{y}")
        tk.Label(self._tip, text=self.text, bg="#ffffd6",
                  fg="#222", borderwidth=1, relief="solid",
                  padx=6, pady=2,
                  font=("TkDefaultFont", 9)).pack()

    def _hide(self, _e=None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None


# ── Theme manager (light/dark) ───────────────────────────────────

class ThemeManager:
    LIGHT = {
        "bg": "#f4f4f4", "fg": "#222",
        "panel": "#ffffff", "muted": "#666",
    }
    DARK = {
        "bg": "#1f1f24", "fg": "#e6e6e6",
        "panel": "#2a2a30", "muted": "#aaa",
    }

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.style = ttk.Style(root)
        self.dark = False

    def apply(self, dark: bool) -> None:
        self.dark = dark
        palette = self.DARK if dark else self.LIGHT
        try:
            self.style.theme_use("clam" if dark else "default")
        except tk.TclError:
            pass
        self.style.configure(
            ".", background=palette["bg"], foreground=palette["fg"])
        self.style.configure(
            "TFrame", background=palette["bg"])
        self.style.configure(
            "TLabel", background=palette["bg"], foreground=palette["fg"])
        self.style.configure(
            "TLabelframe", background=palette["bg"],
            foreground=palette["fg"])
        self.style.configure(
            "TLabelframe.Label", background=palette["bg"],
            foreground=palette["fg"])
        self.style.configure(
            "TNotebook", background=palette["bg"])
        self.style.configure(
            "TNotebook.Tab", background=palette["panel"],
            foreground=palette["fg"])
        self.style.configure(
            "Treeview", background=palette["panel"],
            fieldbackground=palette["panel"], foreground=palette["fg"])
        try:
            self.root.configure(bg=palette["bg"])
        except tk.TclError:
            pass


# ── Undo stack ───────────────────────────────────────────────────

class UndoStack:
    """Tiny LIFO of (label, callable) undo entries. Bound to Ctrl-Z."""

    def __init__(self, *, capacity: int = 20) -> None:
        self._items: list[tuple[str, Callable[[], None]]] = []
        self.capacity = capacity

    def push(self, label: str, fn: Callable[[], None]) -> None:
        self._items.append((label, fn))
        if len(self._items) > self.capacity:
            self._items.pop(0)

    def pop(self) -> tuple[str, Callable[[], None]] | None:
        return self._items.pop() if self._items else None

    def peek(self) -> str | None:
        return self._items[-1][0] if self._items else None


# ── Help overlay ─────────────────────────────────────────────────

_HELP_TEXT = """\
Keyboard shortcuts
─────────────────────────────────────────
?              Open this help
Ctrl+Z         Undo last destructive action
Ctrl+1..4      Switch to tab 1..4
Ctrl+N         New (year / term / break, depending on tab)
Ctrl+R         Refresh
Ctrl+D         Toggle dark mode
Ctrl+S         Save & close
Esc            Cancel a dialog
Enter (dialog) Save and close
Double-click   Edit row
Right-click    Context menu (Years tab)

Drag a term bar in the Terms timeline to move it.
Drag its left or right edge to resize.

Year tab filters: type to search; clear with the
'Clear' button. Sort columns by clicking headings.
"""


def show_help_overlay(parent: tk.Misc) -> None:
    top = tk.Toplevel(parent.winfo_toplevel())
    top.title("Help — Academic Year")
    top.transient(parent)
    top.resizable(False, False)
    t = tk.Text(top, width=58, height=22, wrap="word",
                  font=("TkDefaultFont", 10))
    t.pack(padx=12, pady=10)
    t.insert("1.0", _HELP_TEXT)
    t.configure(state="disabled")
    ttk.Button(top, text="Close",
                command=top.destroy).pack(pady=(0, 10))
    top.bind("<Escape>", lambda _e: top.destroy())
    top.focus_set()


def open_academic_year_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Academic Year — {branding.SYSTEM_NAME}")

    # ── Load saved prefs (geometry, theme, last year, last tab) ──
    prefs = _load_prefs()
    win.geometry(prefs.get("geometry", WIN_GEOMETRY))
    win.minsize(*WIN_MINSIZE)

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
               text="📚  Academic Year",
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

    nb = ttk.Notebook(win)
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
    if isinstance(last_tab, int) and 0 <= last_tab < 4:
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


def _export_year_json(parent: tk.Misc, state: dict) -> None:
    import json
    yid = state.get("selected_year_id")
    if yid is None:
        messagebox.showinfo(
            "Export", "Select a year first (Years tab).")
        return
    year = data.get_year(yid)
    if year is None:
        return
    terms = data.list_terms(year_id=yid)
    breaks = data.list_breaks(year_id=yid)
    payload = {
        "schema": "sixthform.academic_year/v1",
        "year": {
            "name":       year.name,
            "start_date": year.start_date,
            "end_date":   year.end_date,
            "status":     year.status,
            "is_current": year.is_current,
            "notes":      year.notes,
        },
        "terms": [
            {"name": t.name, "start_date": t.start_date,
              "end_date": t.end_date, "notes": t.notes}
            for t in terms
        ],
        "breaks": [
            {"name": b.name, "type": b.type,
              "start_date": b.start_date, "end_date": b.end_date,
              "notes": b.notes}
            for b in breaks
        ],
    }
    default = f"academic_year_{year.name.replace('/', '-')}.json"
    path = filedialog.asksaveasfilename(
        parent=parent, defaultextension=".json",
        initialfile=default,
        filetypes=[("JSON", "*.json"), ("All files", "*.*")])
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    except OSError as e:
        messagebox.showerror("Export", str(e))
        return
    messagebox.showinfo(
        "Export",
        f"Wrote year {year.name!r} with {len(terms)} term(s) "
        f"and {len(breaks)} break(s) to:\n{path}")


def _import_year_json(parent: tk.Misc, state: dict,
                       on_done: Callable[[], None]) -> None:
    import json
    path = filedialog.askopenfilename(
        parent=parent,
        filetypes=[("JSON", "*.json"), ("All files", "*.*")])
    if not path:
        return
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError) as e:
        messagebox.showerror("Import", str(e))
        return
    if not isinstance(payload, dict) or "year" not in payload:
        messagebox.showerror("Import",
                                "File doesn't look like a year export.")
        return
    yp = payload["year"]
    name = yp.get("name", "Imported Year")
    # Avoid name collisions
    if data.get_year_by_name(name):
        i = 2
        while data.get_year_by_name(f"{name} ({i})"):
            i += 1
        name = f"{name} ({i})"
    summary = (
        f"Import year:\n"
        f"  Name:  {name}\n"
        f"  Span:  {yp.get('start_date')} → {yp.get('end_date')}\n"
        f"  Terms: {len(payload.get('terms', []))}\n"
        f"  Breaks:{len(payload.get('breaks', []))}\n\n"
        f"The new year will be created with status=Planning and "
        f"is_current=False.")
    if not messagebox.askyesno("Import", summary):
        return
    try:
        new_year = data.create_year({
            "name": name,
            "start_date": yp.get("start_date"),
            "end_date": yp.get("end_date"),
            "status": "Planning",
            "is_current": False,
            "notes": yp.get("notes"),
        })
    except (ValidationError, Exception) as e:
        messagebox.showerror("Import — year", str(e))
        return
    errs: list[str] = []
    for t in payload.get("terms", []):
        try:
            data.create_term({
                "year_id": new_year.year_id,
                "name": t.get("name"),
                "start_date": t.get("start_date"),
                "end_date": t.get("end_date"),
                "notes": t.get("notes"),
            })
        except (ValidationError, Exception) as e:
            errs.append(f"term {t.get('name')!r}: {e}")
    for b in payload.get("breaks", []):
        try:
            data.create_break({
                "year_id": new_year.year_id,
                "name": b.get("name"),
                "type": b.get("type", DEFAULT_BREAK_TYPE),
                "start_date": b.get("start_date"),
                "end_date": b.get("end_date"),
                "notes": b.get("notes"),
            })
        except (ValidationError, Exception) as e:
            errs.append(f"break {b.get('name')!r}: {e}")
    state["selected_year_id"] = new_year.year_id
    if errs:
        messagebox.showwarning(
            "Import — partial",
            f"Year created (#{new_year.year_id}) but some rows "
            f"failed:\n\n" + "\n".join(errs[:20])
            + ("" if len(errs) <= 20 else f"\n…and {len(errs) - 20} more"))
    else:
        messagebox.showinfo(
            "Import",
            f"Created year #{new_year.year_id} {new_year.name!r}.")
    on_done()


def _today() -> str:
    return _dt.date.today().isoformat()


# ══ Years tab ═════════════════════════════════════════════════════

_SORT_KEYS: dict[str, Callable[[AcademicYear], object]] = {
    "id":      lambda y: y.year_id,
    "name":    lambda y: y.name.lower(),
    "start":   lambda y: y.start_date,
    "end":     lambda y: y.end_date,
    "days":    lambda y: y.day_count,
    "status":  lambda y: y.status,
    "current": lambda y: (0 if y.is_current else 1),
}


class YearsTab:
    def __init__(self, nb: ttk.Notebook, state: dict,
                  *, goto_tab: Callable[[int], None] | None = None) -> None:
        self.state = state
        self.goto_tab = goto_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Years")
        self._sort_col: str = "start"
        self._sort_reverse: bool = True
        self._build()
        self.refresh()

    def _build(self) -> None:
        # Yellow banner — shown only when there's no current year.
        self.banner = tk.Label(
            self.frame, text="", bg="#fff3b0", fg="#5a4a00",
            anchor="w", padx=10, pady=4)
        # packed/unpacked dynamically in refresh()

        # Filter bar — search + status filter.
        filt = ttk.Frame(self.frame)
        filt.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(filt, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write",
                                    lambda *_: self._render_rows())
        ttk.Entry(filt, textvariable=self.search_var,
                   width=24).pack(side="left", padx=(2, 12))
        ttk.Label(filt, text="Status:").pack(side="left")
        self.status_cb = ttk.Combobox(
            filt, values=("All",) + YEAR_STATUSES,
            state="readonly", width=12)
        self.status_cb.current(0)
        self.status_cb.bind("<<ComboboxSelected>>",
                              lambda _e: self._render_rows())
        self.status_cb.pack(side="left", padx=(2, 12))
        ttk.Label(filt, text="Year range:").pack(side="left")
        self.from_e = ttk.Entry(filt, width=12)
        self.from_e.pack(side="left", padx=(2, 4))
        ttk.Label(filt, text="to").pack(side="left")
        self.to_e = ttk.Entry(filt, width=12)
        self.to_e.pack(side="left", padx=(2, 4))
        ttk.Button(filt, text="Apply",
                    command=self._render_rows).pack(side="left", padx=4)
        ttk.Button(filt, text="Clear",
                    command=self._clear_filters).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=(4, 4))
        cols = ("id", "name", "start", "end", "days",
                "status", "current")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        self._headings = {"id": "ID", "name": "Name",
                           "start": "Start", "end": "End",
                           "days": "Days", "status": "Status",
                           "current": "Current"}
        widths = {"id": 60, "name": 120, "start": 110, "end": 110,
                  "days": 70, "status": 110, "current": 80}
        for c in cols:
            self.tree.heading(
                c, text=self._headings[c],
                command=lambda _c=c: self._sort_by(_c))
            anchor = "center" if c in ("days", "current") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("current", background="#d8f4d8")
        self.tree.tag_configure("Active", background="#eef7ff")
        self.tree.tag_configure("Archived", background="#eeeeee")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())
        # Right-click context menu (Button-3 on X11, Button-2 on macOS).
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Button-2>", self._on_right_click)

        self.menu = tk.Menu(self.frame, tearoff=False)
        self.menu.add_command(label="Edit",
                                 command=self._edit_selected)
        self.menu.add_command(label="Set current",
                                 command=self._set_current)
        self.menu.add_command(label="Duplicate (+1 year)",
                                 command=self._duplicate_selected)
        self.menu.add_separator()
        self.menu.add_command(label="Archive",
                                 command=lambda: self._set_status("Archived"))
        self.menu.add_command(label="Unarchive (→ Active)",
                                 command=lambda: self._set_status("Active"))
        self.menu.add_separator()
        self.menu.add_command(label="Open Terms",
                                 command=lambda: self._open_tab(1))
        self.menu.add_command(label="Open Breaks",
                                 command=lambda: self._open_tab(2))
        self.menu.add_separator()
        self.menu.add_command(label="Delete",
                                 command=self._delete_selected)

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Set current",
                    command=self._set_current).pack(side="left", padx=4)
        ttk.Button(bar, text="Duplicate",
                    command=self._duplicate_selected).pack(side="left",
                                                              padx=4)
        ttk.Button(bar, text="Archive",
                    command=lambda: self._set_status("Archived")).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Unarchive",
                    command=lambda: self._set_status("Active")).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Separator(bar, orient="vertical").pack(side="left",
                                                       fill="y", padx=8)
        ttk.Button(bar, text="Open Terms »",
                    command=lambda: self._open_tab(1)).pack(side="left",
                                                              padx=2)
        ttk.Button(bar, text="Open Breaks »",
                    command=lambda: self._open_tab(2)).pack(side="left",
                                                              padx=2)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    # ── Banner / data load ──────────────────────────────────────

    def _show_banner(self, text: str) -> None:
        self.banner.configure(text=text)
        if not self.banner.winfo_ismapped():
            self.banner.pack(fill="x", before=self.frame.winfo_children()[0]
                              if self.frame.winfo_children() else None)

    def _hide_banner(self) -> None:
        if self.banner.winfo_ismapped():
            self.banner.pack_forget()

    def refresh(self) -> None:
        self._all_rows: list[AcademicYear] = data.list_years()
        self._render_rows()
        # Auto-select the current year if nothing selected.
        if self.state.get("selected_year_id") is None:
            cur = data.current_year()
            if cur is not None:
                self.state["selected_year_id"] = cur.year_id
                try:
                    self.tree.selection_set(str(cur.year_id))
                except tk.TclError:
                    pass

    # ── Filtering / sorting / rendering ─────────────────────────

    def _clear_filters(self) -> None:
        self.search_var.set("")
        self.status_cb.current(0)
        self.from_e.delete(0, "end")
        self.to_e.delete(0, "end")
        self._render_rows()

    def _sort_by(self, col: str) -> None:
        if col not in _SORT_KEYS:
            return
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        for c, label in self._headings.items():
            arrow = ""
            if c == self._sort_col:
                arrow = "  ▼" if self._sort_reverse else "  ▲"
            self.tree.heading(c, text=label + arrow)
        self._render_rows()

    def _filter_rows(self) -> list[AcademicYear]:
        rows = list(self._all_rows)
        q = self.search_var.get().strip().lower()
        if q:
            rows = [r for r in rows
                     if q in r.name.lower()
                     or q in r.status.lower()
                     or q in r.start_date
                     or q in r.end_date]
        st = self.status_cb.get()
        if st and st != "All":
            rows = [r for r in rows if r.status == st]
        frm = self.from_e.get().strip()
        to = self.to_e.get().strip()
        if frm:
            rows = [r for r in rows if r.end_date >= frm]
        if to:
            rows = [r for r in rows if r.start_date <= to]
        key = _SORT_KEYS.get(self._sort_col, _SORT_KEYS["start"])
        rows.sort(key=key, reverse=self._sort_reverse)
        return rows

    def _render_rows(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = self._filter_rows()
        for y in rows:
            tags = []
            if y.is_current:
                tags.append("current")
            if y.status in ("Active", "Archived"):
                tags.append(y.status)
            self.tree.insert("", "end", iid=str(y.year_id), values=(
                y.year_id, y.name, y.start_date, y.end_date,
                y.day_count, y.status, "✓" if y.is_current else "",
            ), tags=tuple(tags))

        total = len(self._all_rows)
        shown = len(rows)
        cur = sum(1 for r in self._all_rows if r.is_current)
        act = sum(1 for r in self._all_rows if r.status == "Active")
        arch = sum(1 for r in self._all_rows if r.status == "Archived")
        plan = sum(1 for r in self._all_rows if r.status == "Planning")
        suffix = "" if shown == total else f"  (showing {shown})"
        self.count_var.set(
            f"{total} year(s) — {cur} current, {act} active, "
            f"{plan} planning, {arch} archived.{suffix}")

        if cur == 0 and total > 0:
            self._show_banner(
                "⚠  No academic year is flagged as current — "
                "select a row and click ‘Set current’.")
        else:
            self._hide_banner()

    # ── Selection / context menu ────────────────────────────────

    def _on_select(self, _evt=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            self.state["selected_year_id"] = int(sel[0])
        except ValueError:
            pass

    def _on_right_click(self, event: tk.Event) -> None:
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self._on_select()
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    # ── Actions ─────────────────────────────────────────────────

    def _new(self) -> None:
        YearDialog(self.frame.winfo_toplevel(),
                    existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        yid = self._selected_id()
        if yid is None:
            messagebox.showinfo("Edit", "Select a year first.")
            return
        existing = data.get_year(yid)
        if existing is None:
            return
        YearDialog(self.frame.winfo_toplevel(),
                    existing=existing, on_save=self.refresh)

    def _set_current(self) -> None:
        yid = self._selected_id()
        if yid is None:
            messagebox.showinfo("Current", "Select a year first.")
            return
        try:
            data.set_current(yid)
        except ValidationError as e:
            messagebox.showerror("Current", str(e))
            return
        self.refresh()

    def _set_status(self, new_status: str) -> None:
        yid = self._selected_id()
        if yid is None:
            messagebox.showinfo("Status", "Select a year first.")
            return
        existing = data.get_year(yid)
        if existing is None:
            return
        if existing.status == new_status:
            return
        try:
            data.update_year(yid, {"status": new_status})
        except (ValidationError, Exception) as e:
            messagebox.showerror("Status change failed", str(e))
            return
        self.refresh()

    def _duplicate_selected(self) -> None:
        yid = self._selected_id()
        if yid is None:
            messagebox.showinfo("Duplicate", "Select a year first.")
            return
        src = data.get_year(yid)
        if src is None:
            return
        try:
            new_name = _bump_year_name(src.name)
            new_start = _shift_iso(src.start_date, 365)
            new_end = _shift_iso(src.end_date, 365)
        except Exception as e:
            messagebox.showerror("Duplicate failed", str(e))
            return
        if not messagebox.askyesno(
                "Duplicate",
                f"Create new year {new_name!r}\n"
                f"({new_start} → {new_end})\n"
                f"with all terms and breaks shifted by +365 days?"):
            return
        try:
            new_year = data.create_year({
                "name": new_name,
                "start_date": new_start,
                "end_date": new_end,
                "status": "Planning",
                "is_current": False,
                "notes": src.notes,
            })
            for t in data.list_terms(year_id=src.year_id):
                try:
                    data.create_term({
                        "year_id": new_year.year_id,
                        "name": t.name,
                        "start_date": _shift_iso(t.start_date, 365),
                        "end_date": _shift_iso(t.end_date, 365),
                        "notes": t.notes,
                    })
                except ValidationError as e:
                    logger.warning("Skipped duplicating term %r: %s",
                                    t.name, e)
            for b in data.list_breaks(year_id=src.year_id):
                try:
                    data.create_break({
                        "year_id": new_year.year_id,
                        "name": b.name,
                        "type": b.type,
                        "start_date": _shift_iso(b.start_date, 365),
                        "end_date": _shift_iso(b.end_date, 365),
                        "notes": b.notes,
                    })
                except ValidationError as e:
                    logger.warning("Skipped duplicating break %r: %s",
                                    b.name, e)
            self.state["selected_year_id"] = new_year.year_id
        except (ValidationError, Exception) as e:
            messagebox.showerror("Duplicate failed", str(e))
            return
        self.refresh()

    def _open_tab(self, idx: int) -> None:
        yid = self._selected_id()
        if yid is not None:
            self.state["selected_year_id"] = yid
        if self.goto_tab is not None:
            self.goto_tab(idx)

    def _delete_selected(self) -> None:
        yid = self._selected_id()
        if yid is None:
            messagebox.showinfo("Delete", "Select a year first.")
            return
        y = data.get_year(yid)
        if y is None:
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete year #{yid} {y.name!r}?\n"
                "Soft-delete — Ctrl-Z to undo."):
            return
        try:
            data.delete_year(yid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        undo = self.state.get("_undo")
        if undo is not None:
            undo.push(f"delete year #{yid}",
                       lambda i=yid: data.restore_year(i))
        toaster = self.state.get("_toast")
        if toaster:
            toaster(f"Deleted year #{yid} — Ctrl-Z to undo",
                      kind="warn")
        if self.state.get("selected_year_id") == yid:
            self.state["selected_year_id"] = None
        self.refresh()


def _shift_iso(date_iso: str, days: int) -> str:
    return (_dt.date.fromisoformat(date_iso)
             + _dt.timedelta(days=days)).isoformat()


def _bump_year_name(name: str) -> str:
    """Best-effort: bump trailing year tokens in a name like '2025/26'
    → '2026/27'. Falls back to appending ' (copy)' if no pattern matches."""
    import re as _re
    m = _re.search(r"(\d{4})\s*/\s*(\d{2,4})\s*$", name)
    if m:
        y1 = int(m.group(1)) + 1
        g2 = m.group(2)
        if len(g2) == 2:
            y2 = (int(g2) + 1) % 100
            tail = f"{y1}/{y2:02d}"
        else:
            tail = f"{y1}/{int(g2) + 1}"
        return name[:m.start()] + tail
    m = _re.search(r"(\d{4})\s*-\s*(\d{2,4})\s*$", name)
    if m:
        y1 = int(m.group(1)) + 1
        g2 = m.group(2)
        if len(g2) == 2:
            y2 = (int(g2) + 1) % 100
            tail = f"{y1}-{y2:02d}"
        else:
            tail = f"{y1}-{int(g2) + 1}"
        return name[:m.start()] + tail
    m = _re.search(r"(\d{4})\s*$", name)
    if m:
        return name[:m.start()] + str(int(m.group(1)) + 1)
    return f"{name} (copy)"[:32]


# ══ Terms tab ═════════════════════════════════════════════════════

def _iso(d: _dt.date) -> str:
    return d.isoformat()


def _classify_terms(year: AcademicYear,
                     terms: list[Term]) -> dict[int, str]:
    """Return {term_id: status} where status is 'ok', 'outside',
    'overlap', or 'gap-before'. 'gap-before' means a gap exists between
    the previous term's end and this term's start (info, not an error)."""
    out: dict[int, str] = {}
    ordered = sorted(terms, key=lambda t: t.start_date)
    prev_end: str | None = None
    for t in ordered:
        if (t.start_date < year.start_date
                or t.end_date > year.end_date
                or t.end_date < t.start_date):
            out[t.term_id] = "outside"
        elif prev_end is not None and t.start_date <= prev_end:
            out[t.term_id] = "overlap"
        elif prev_end is not None:
            try:
                gap = (_dt.date.fromisoformat(t.start_date)
                       - _dt.date.fromisoformat(prev_end)).days
                out[t.term_id] = "gap-before" if gap > 14 else "ok"
            except ValueError:
                out[t.term_id] = "ok"
        else:
            out[t.term_id] = "ok"
        if t.end_date > (prev_end or ""):
            prev_end = t.end_date
    return out


_STATUS_BADGES: dict[str, str] = {
    "ok":         "✓ ok",
    "outside":    "✗ outside year",
    "overlap":    "⚠ overlaps prev",
    "gap-before": "⚠ gap before",
}


def _teaching_days_for_term(year_id: int, t: Term) -> int:
    try:
        return data.teaching_days_in(
            year_id, date_from=t.start_date, date_to=t.end_date)
    except Exception:
        return 0


def _split_even_three(year: AcademicYear) -> list[tuple[str, str, str]]:
    """Return [(name, start_iso, end_iso)] for Autumn/Spring/Summer
    splitting the year roughly into thirds on Mondays/Fridays."""
    start = _dt.date.fromisoformat(year.start_date)
    end = _dt.date.fromisoformat(year.end_date)
    total = (end - start).days
    third = total // 3
    a_end = start + _dt.timedelta(days=third)
    s_start = a_end + _dt.timedelta(days=1)
    s_end = start + _dt.timedelta(days=2 * third)
    su_start = s_end + _dt.timedelta(days=1)
    return [
        ("Autumn", _iso(start),    _iso(a_end)),
        ("Spring", _iso(s_start), _iso(s_end)),
        ("Summer", _iso(su_start), _iso(end)),
    ]


def _suggest_halfterms(year_id: int, terms: list[Term]
                        ) -> list[tuple[str, str, str]]:
    """For each whole-term name (Autumn/Spring/Summer), suggest a
    week-long half-term break starting at the midpoint Monday.
    Returns [(name, start_iso, end_iso)] — caller filters existing."""
    out: list[tuple[str, str, str]] = []
    for t in terms:
        if t.name not in ("Autumn", "Spring", "Summer"):
            continue
        try:
            s = _dt.date.fromisoformat(t.start_date)
            e = _dt.date.fromisoformat(t.end_date)
        except ValueError:
            continue
        mid = s + (e - s) // 2
        # Snap back to Monday
        mid -= _dt.timedelta(days=mid.weekday())
        end = mid + _dt.timedelta(days=4)  # Mon..Fri
        if mid < s or end > e:
            continue
        out.append((f"{t.name} Half-Term", _iso(mid), _iso(end)))
    return out


class TermsTab:
    GANTT_H = 64
    GANTT_PAD = 12

    def __init__(self, nb: ttk.Notebook, state: dict) -> None:
        self.state = state
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Terms")
        self._terms: list[Term] = []
        self._status_by_id: dict[int, str] = {}
        self._teaching_by_id: dict[int, int] = {}
        # Gantt drag state
        self._drag_term_id: int | None = None
        self._drag_kind: str | None = None  # 'left' | 'right' | 'move'
        self._drag_orig: tuple[str, str] | None = None
        self._drag_anchor_x: int = 0
        self._build()
        self.refresh()

    # ── UI construction ─────────────────────────────────────────

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_cb = ttk.Combobox(bar, state="readonly", width=40)
        self.year_cb.pack(side="left", padx=(2, 10))
        self.year_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self._on_year_change())
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")

        # Gantt strip
        gantt_frame = ttk.LabelFrame(self.frame, text="Timeline")
        gantt_frame.pack(fill="x", padx=8, pady=(4, 4))
        self.gantt = tk.Canvas(gantt_frame, height=self.GANTT_H,
                                  bg="#fafafa", highlightthickness=0)
        self.gantt.pack(fill="x", padx=4, pady=4)
        self.gantt.bind("<Configure>", lambda _e: self._draw_gantt())
        self.gantt.bind("<Motion>", self._gantt_motion)
        self.gantt.bind("<ButtonPress-1>", self._gantt_press)
        self.gantt.bind("<B1-Motion>", self._gantt_drag)
        self.gantt.bind("<ButtonRelease-1>", self._gantt_release)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "start", "end", "days", "teach", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings", selectmode="extended")
        headings = {"id": "ID", "name": "Name", "start": "Start",
                    "end": "End", "days": "Days",
                    "teach": "Teaching", "status": "Check"}
        widths = {"id": 60, "name": 160, "start": 110, "end": 110,
                  "days": 70, "teach": 90, "status": 140}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c in ("days", "teach") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("outside",    background="#ffd6d6")
        self.tree.tag_configure("overlap",    background="#ffe3b0")
        self.tree.tag_configure("gap-before", background="#fff7d0")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())
        self.tree.bind("<<TreeviewSelect>>",
                         lambda _e: self._draw_gantt())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        # Action row 1: CRUD
        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 2))
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete selected (bulk)",
                    command=self._bulk_delete).pack(side="left", padx=4)

        # Action row 2: bulk helpers + export
        more = ttk.Frame(self.frame)
        more.pack(fill="x", padx=8, pady=(2, 8))
        ttk.Button(more, text="Auto-fill 3 terms",
                    command=self._autofill_three).pack(side="left")
        ttk.Button(more, text="Suggest half-terms",
                    command=self._suggest_halfterms).pack(side="left",
                                                              padx=4)
        ttk.Separator(more, orient="vertical").pack(side="left",
                                                       fill="y", padx=8)
        ttk.Label(more, text="Copy from:").pack(side="left")
        self.copy_cb = ttk.Combobox(more, state="readonly", width=28)
        self.copy_cb.pack(side="left", padx=(2, 4))
        ttk.Button(more, text="Copy terms",
                    command=self._copy_from_year).pack(side="left")
        ttk.Separator(more, orient="vertical").pack(side="left",
                                                       fill="y", padx=8)
        ttk.Button(more, text="Export CSV",
                    command=lambda: self._export("csv")).pack(side="left")
        ttk.Button(more, text="Export ICS",
                    command=lambda: self._export("ics")).pack(side="left",
                                                                 padx=4)

    # ── Year combobox / state ───────────────────────────────────

    def _year_options(self) -> list[tuple[int, str]]:
        years = data.list_years()
        return [(y.year_id, f"#{y.year_id} {y.name}"
                            f"{' *' if y.is_current else ''}")
                for y in years]

    def _on_year_change(self) -> None:
        idx = self.year_cb.current()
        if idx < 0:
            return
        self.state["selected_year_id"] = self._year_ids[idx]
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        opts = self._year_options()
        self._year_ids = [yid for yid, _ in opts]
        labels = [lbl for _, lbl in opts]
        self.year_cb["values"] = labels

        if not opts:
            self.count_var.set("No academic years configured.")
            self._terms = []
            self._draw_gantt()
            self.copy_cb["values"] = ()
            return

        target = self.state.get("selected_year_id") or self._year_ids[0]
        try:
            idx = self._year_ids.index(target)
        except ValueError:
            idx = 0
            target = self._year_ids[0]
        self.year_cb.current(idx)
        self.state["selected_year_id"] = target

        # Copy-from combo lists every *other* year.
        self._copy_ids: list[int] = [yid for yid in self._year_ids
                                          if yid != target]
        self.copy_cb["values"] = [
            lbl for yid, lbl in opts if yid != target]
        if self._copy_ids:
            self.copy_cb.current(0)
        else:
            self.copy_cb.set("")

        year = data.get_year(target)
        if year is None:
            self._terms = []
            self._draw_gantt()
            return
        self._terms = data.list_terms(year_id=target)
        self._status_by_id = _classify_terms(year, self._terms)
        self._teaching_by_id = {
            t.term_id: _teaching_days_for_term(target, t)
            for t in self._terms}

        for t in self._terms:
            status = self._status_by_id.get(t.term_id, "ok")
            tags = (status,) if status != "ok" else ()
            self.tree.insert("", "end", iid=str(t.term_id), values=(
                t.term_id, t.name, t.start_date, t.end_date,
                t.day_count,
                self._teaching_by_id.get(t.term_id, 0),
                _STATUS_BADGES.get(status, status),
            ), tags=tags)

        issues = sum(1 for s in self._status_by_id.values() if s != "ok")
        teach_total = sum(self._teaching_by_id.values())
        self.count_var.set(
            f"{len(self._terms)} term(s) — {teach_total} teaching day(s)"
            + (f", {issues} with warnings" if issues else ""))
        self._draw_gantt()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _selected_ids(self) -> list[int]:
        out: list[int] = []
        for iid in self.tree.selection():
            try:
                out.append(int(iid))
            except ValueError:
                pass
        return out

    def _current_year(self) -> AcademicYear | None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            return None
        return data.get_year(yid)

    # ── CRUD ────────────────────────────────────────────────────

    def _new(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("New", "Pick a year first.")
            return
        TermDialog(self.frame.winfo_toplevel(), year=year,
                    existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Edit", "Select a term first.")
            return
        existing = data.get_term(tid)
        if existing is None:
            return
        year = data.get_year(existing.year_id)
        if year is None:
            return
        TermDialog(self.frame.winfo_toplevel(), year=year,
                    existing=existing, on_save=self.refresh)

    def _delete_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Delete", "Select a term first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete term #{tid}? (Soft-delete — Ctrl-Z to undo)"):
            return
        try:
            data.delete_term(tid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        undo = self.state.get("_undo")
        if undo is not None:
            undo.push(f"delete term #{tid}",
                       lambda i=tid: data.restore_term(i))
        toaster = self.state.get("_toast")
        if toaster:
            toaster(f"Deleted term #{tid} — Ctrl-Z to undo", kind="warn")
        self.refresh()

    def _bulk_delete(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Delete", "Select one or more terms first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete {len(ids)} term(s)? "
                "(Soft-delete — Ctrl-Z to undo)"):
            return
        errs: list[str] = []
        deleted: list[int] = []
        for tid in ids:
            try:
                if data.delete_term(tid):
                    deleted.append(tid)
            except Exception as e:
                errs.append(f"#{tid}: {e}")
        if errs:
            messagebox.showerror("Some deletes failed", "\n".join(errs))
        undo = self.state.get("_undo")
        if undo is not None and deleted:
            def _restore_many(_ids=deleted) -> None:
                for i in _ids:
                    try:
                        data.restore_term(i)
                    except Exception:
                        pass
            undo.push(f"bulk delete {len(deleted)} term(s)",
                       _restore_many)
        toaster = self.state.get("_toast")
        if toaster and deleted:
            toaster(f"Deleted {len(deleted)} term(s) — Ctrl-Z to undo",
                      kind="warn")
        self.refresh()

    # ── Bulk helpers ────────────────────────────────────────────

    def _autofill_three(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("Auto-fill", "Pick a year first.")
            return
        existing_names = {t.name for t in self._terms}
        if existing_names & {"Autumn", "Spring", "Summer"}:
            if not messagebox.askyesno(
                    "Auto-fill",
                    "This year already has one or more of "
                    "Autumn/Spring/Summer. Skip those and add only "
                    "the missing ones?"):
                return
        plan = _split_even_three(year)
        added = 0
        errs: list[str] = []
        for name, s, e in plan:
            if name in existing_names:
                continue
            try:
                data.create_term({
                    "year_id": year.year_id, "name": name,
                    "start_date": s, "end_date": e, "notes": None,
                })
                added += 1
            except (ValidationError, Exception) as ex:
                errs.append(f"{name}: {ex}")
        if errs:
            messagebox.showerror("Auto-fill issues",
                                    f"Added {added}.\n" + "\n".join(errs))
        else:
            messagebox.showinfo("Auto-fill",
                                   f"Added {added} term(s).")
        self.refresh()

    def _suggest_halfterms(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("Half-terms", "Pick a year first.")
            return
        suggestions = _suggest_halfterms(year.year_id, self._terms)
        if not suggestions:
            messagebox.showinfo(
                "Half-terms",
                "No Autumn/Spring/Summer terms to base "
                "suggestions on.")
            return
        # Drop any whose name+start already exist as a break.
        existing = {(b.name, b.start_date)
                     for b in data.list_breaks(year_id=year.year_id)}
        new = [s for s in suggestions if (s[0], s[1]) not in existing]
        if not new:
            messagebox.showinfo("Half-terms",
                                   "All suggestions already exist.")
            return
        preview = "\n".join(f"  • {n}  {s} → {e}" for n, s, e in new)
        if not messagebox.askyesno(
                "Half-terms",
                f"Insert {len(new)} suggested half-term break(s)?\n\n"
                f"{preview}"):
            return
        errs: list[str] = []
        for name, s, e in new:
            try:
                data.create_break({
                    "year_id": year.year_id, "name": name,
                    "type": "Half-Term", "start_date": s, "end_date": e,
                    "notes": None,
                })
            except (ValidationError, Exception) as ex:
                errs.append(f"{name}: {ex}")
        if errs:
            messagebox.showerror("Some inserts failed",
                                    "\n".join(errs))
        self.refresh()

    def _copy_from_year(self) -> None:
        dest = self._current_year()
        if dest is None:
            messagebox.showinfo("Copy", "Pick a destination year first.")
            return
        idx = self.copy_cb.current()
        if idx < 0 or idx >= len(self._copy_ids):
            messagebox.showinfo("Copy", "Pick a source year.")
            return
        src_id = self._copy_ids[idx]
        src = data.get_year(src_id)
        if src is None:
            return
        try:
            shift = (_dt.date.fromisoformat(dest.start_date)
                      - _dt.date.fromisoformat(src.start_date)).days
        except ValueError as e:
            messagebox.showerror("Copy", str(e))
            return
        src_terms = data.list_terms(year_id=src_id)
        if not src_terms:
            messagebox.showinfo("Copy",
                                   f"{src.name!r} has no terms to copy.")
            return
        if not messagebox.askyesno(
                "Copy",
                f"Copy {len(src_terms)} term(s) from {src.name!r}\n"
                f"into {dest.name!r}, shifted by {shift:+d} days?\n"
                f"Existing terms with the same name will be skipped."):
            return
        existing_names = {t.name for t in self._terms}
        added = 0
        errs: list[str] = []
        for t in src_terms:
            if t.name in existing_names:
                continue
            try:
                data.create_term({
                    "year_id": dest.year_id,
                    "name": t.name,
                    "start_date": _shift_iso(t.start_date, shift),
                    "end_date": _shift_iso(t.end_date, shift),
                    "notes": t.notes,
                })
                added += 1
            except (ValidationError, Exception) as ex:
                errs.append(f"{t.name}: {ex}")
        if errs:
            messagebox.showerror("Copy issues",
                                    f"Added {added}.\n" + "\n".join(errs))
        else:
            messagebox.showinfo("Copy",
                                   f"Copied {added} term(s).")
        self.refresh()

    # ── Export ──────────────────────────────────────────────────

    def _export(self, fmt: str) -> None:
        year = self._current_year()
        if year is None or not self._terms:
            messagebox.showinfo("Export", "Nothing to export.")
            return
        default = f"terms_{year.name.replace('/', '-')}.{fmt}"
        path = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            initialfile=default,
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("All files", "*.*")])
        if not path:
            return
        try:
            if fmt == "csv":
                self._write_csv(path)
            else:
                self._write_ics(path, year)
        except OSError as e:
            messagebox.showerror("Export failed", str(e))
            return
        messagebox.showinfo("Export",
                               f"Wrote {len(self._terms)} term(s) to "
                               f"{path}")

    def _write_csv(self, path: str) -> None:
        import csv
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["term_id", "year_id", "name",
                          "start_date", "end_date",
                          "calendar_days", "teaching_days",
                          "status", "notes"])
            for t in self._terms:
                w.writerow([
                    t.term_id, t.year_id, t.name,
                    t.start_date, t.end_date,
                    t.day_count,
                    self._teaching_by_id.get(t.term_id, 0),
                    self._status_by_id.get(t.term_id, "ok"),
                    t.notes or "",
                ])

    def _write_ics(self, path: str, year: AcademicYear) -> None:
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//SixthForm//AcademicYear//EN",
            "CALSCALE:GREGORIAN",
        ]
        stamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        for t in self._terms:
            try:
                s = _dt.date.fromisoformat(t.start_date)
                e = (_dt.date.fromisoformat(t.end_date)
                       + _dt.timedelta(days=1))  # DTEND exclusive
            except ValueError:
                continue
            uid = f"term-{t.term_id}-y{year.year_id}@sixthform"
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                f"SUMMARY:{t.name} ({year.name})",
                f"DTSTART;VALUE=DATE:{s.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{e.strftime('%Y%m%d')}",
                "END:VEVENT",
            ]
        lines.append("END:VCALENDAR")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\r\n".join(lines) + "\r\n")

    # ── Gantt strip ─────────────────────────────────────────────

    def _gantt_geom(self) -> tuple[AcademicYear, _dt.date, _dt.date,
                                    int, float] | None:
        """Return (year, start, end, width_px, px_per_day) — or None
        if the year span isn't valid."""
        year = self._current_year()
        if year is None:
            return None
        try:
            s = _dt.date.fromisoformat(year.start_date)
            e = _dt.date.fromisoformat(year.end_date)
        except ValueError:
            return None
        total = (e - s).days + 1
        if total <= 0:
            return None
        w = max(self.gantt.winfo_width(), 200) - 2 * self.GANTT_PAD
        ppd = w / total
        return (year, s, e, w, ppd)

    def _date_to_x(self, d: _dt.date, geom) -> float:
        _year, start, _end, _w, ppd = geom
        return self.GANTT_PAD + (d - start).days * ppd

    def _x_to_date(self, x: float, geom) -> _dt.date:
        _year, start, end, _w, ppd = geom
        days = round((x - self.GANTT_PAD) / ppd)
        d = start + _dt.timedelta(days=int(days))
        if d < start:
            return start
        if d > end:
            return end
        return d

    def _draw_gantt(self) -> None:
        self.gantt.delete("all")
        geom = self._gantt_geom()
        if geom is None:
            self.gantt.create_text(
                10, self.GANTT_H // 2, anchor="w",
                text="No academic year selected.",
                fill="#888")
            return
        year, start, end, w, ppd = geom
        # Year bar
        self.gantt.create_rectangle(
            self.GANTT_PAD, 4,
            self.GANTT_PAD + w, 18,
            fill="#eeeeee", outline="#cccccc")
        self.gantt.create_text(
            self.GANTT_PAD + 4, 11, anchor="w",
            text=f"{year.name}   {year.start_date} → {year.end_date}",
            fill="#444", font=("TkDefaultFont", 8))

        # Month gridlines + labels
        cur = _dt.date(start.year, start.month, 1)
        while cur <= end:
            x = self._date_to_x(cur, geom)
            self.gantt.create_line(x, 20, x, self.GANTT_H,
                                       fill="#dddddd", dash=(2, 2))
            self.gantt.create_text(
                x + 2, self.GANTT_H - 4, anchor="sw",
                text=cur.strftime("%b"),
                fill="#999", font=("TkDefaultFont", 7))
            # advance one month
            if cur.month == 12:
                cur = _dt.date(cur.year + 1, 1, 1)
            else:
                cur = _dt.date(cur.year, cur.month + 1, 1)

        selected_ids = set(self._selected_ids())
        for t in self._terms:
            try:
                ts = _dt.date.fromisoformat(t.start_date)
                te = _dt.date.fromisoformat(t.end_date)
            except ValueError:
                continue
            x0 = self._date_to_x(max(ts, start), geom)
            x1 = self._date_to_x(min(te, end), geom)
            if x1 - x0 < 2:
                x1 = x0 + 2
            colour = _term_colour(t.name)
            outline = "#222" if t.term_id in selected_ids else "#666"
            wd = 2 if t.term_id in selected_ids else 1
            self.gantt.create_rectangle(
                x0, 22, x1, self.GANTT_H - 14,
                fill=colour, outline=outline, width=wd,
                tags=(f"term:{t.term_id}", "termbar"))
            # left/right grab handles (4px wide hot zones, drawn faint)
            self.gantt.create_rectangle(
                x0, 22, x0 + 4, self.GANTT_H - 14,
                fill="", outline="",
                tags=(f"term:{t.term_id}", f"handle-left:{t.term_id}"))
            self.gantt.create_rectangle(
                x1 - 4, 22, x1, self.GANTT_H - 14,
                fill="", outline="",
                tags=(f"term:{t.term_id}", f"handle-right:{t.term_id}"))
            if x1 - x0 > 40:
                self.gantt.create_text(
                    (x0 + x1) / 2, (22 + self.GANTT_H - 14) / 2,
                    text=t.name, fill="#222",
                    font=("TkDefaultFont", 8, "bold"))

    def _hit_term(self, x: int, y: int) -> tuple[int, str] | None:
        """Return (term_id, 'left'|'right'|'move') for the canvas hit
        or None."""
        if y < 22 or y > self.GANTT_H - 14:
            return None
        # Order matters: handles first.
        for item in self.gantt.find_overlapping(x - 1, y, x + 1, y):
            tags = self.gantt.gettags(item)
            for tg in tags:
                if tg.startswith("handle-left:"):
                    return (int(tg.split(":", 1)[1]), "left")
                if tg.startswith("handle-right:"):
                    return (int(tg.split(":", 1)[1]), "right")
        for item in self.gantt.find_overlapping(x - 1, y, x + 1, y):
            tags = self.gantt.gettags(item)
            for tg in tags:
                if tg.startswith("term:"):
                    return (int(tg.split(":", 1)[1]), "move")
        return None

    def _gantt_motion(self, event: tk.Event) -> None:
        if self._drag_term_id is not None:
            return
        hit = self._hit_term(event.x, event.y)
        if hit is None:
            self.gantt.configure(cursor="")
        elif hit[1] in ("left", "right"):
            self.gantt.configure(cursor="sb_h_double_arrow")
        else:
            self.gantt.configure(cursor="fleur")

    def _gantt_press(self, event: tk.Event) -> None:
        hit = self._hit_term(event.x, event.y)
        if hit is None:
            return
        tid, kind = hit
        term = next((t for t in self._terms if t.term_id == tid), None)
        if term is None:
            return
        self._drag_term_id = tid
        self._drag_kind = kind
        self._drag_orig = (term.start_date, term.end_date)
        self._drag_anchor_x = event.x
        try:
            self.tree.selection_set(str(tid))
        except tk.TclError:
            pass

    def _gantt_drag(self, event: tk.Event) -> None:
        if self._drag_term_id is None or self._drag_orig is None:
            return
        geom = self._gantt_geom()
        if geom is None:
            return
        _year, start, end, _w, ppd = geom
        delta_days = round((event.x - self._drag_anchor_x) / ppd)
        os_, oe = self._drag_orig
        try:
            so = _dt.date.fromisoformat(os_)
            eo = _dt.date.fromisoformat(oe)
        except ValueError:
            return
        if self._drag_kind == "left":
            ns = so + _dt.timedelta(days=delta_days)
            ne = eo
            if ns < start:
                ns = start
            if ns > ne:
                ns = ne
        elif self._drag_kind == "right":
            ns = so
            ne = eo + _dt.timedelta(days=delta_days)
            if ne > end:
                ne = end
            if ne < ns:
                ne = ns
        else:  # move
            ns = so + _dt.timedelta(days=delta_days)
            ne = eo + _dt.timedelta(days=delta_days)
            if ns < start:
                shift = (start - ns).days
                ns += _dt.timedelta(days=shift)
                ne += _dt.timedelta(days=shift)
            if ne > end:
                shift = (ne - end).days
                ns -= _dt.timedelta(days=shift)
                ne -= _dt.timedelta(days=shift)
        # Live preview without DB write
        for t in self._terms:
            if t.term_id == self._drag_term_id:
                t.start_date = _iso(ns)
                t.end_date = _iso(ne)
                break
        self._draw_gantt()

    def _gantt_release(self, _event: tk.Event) -> None:
        if self._drag_term_id is None:
            return
        tid = self._drag_term_id
        self._drag_term_id = None
        self._drag_kind = None
        self._drag_orig = None
        term = next((t for t in self._terms if t.term_id == tid), None)
        if term is None:
            self.refresh()
            return
        try:
            data.update_term(tid, {
                "start_date": term.start_date,
                "end_date": term.end_date,
            })
        except (ValidationError, Exception) as e:
            messagebox.showerror("Update failed", str(e))
        self.refresh()


# ══ Breaks tab ═════════════════════════════════════════════════════

# Break type → swatch colour (matches treeview row tags).
BREAK_COLOURS: dict[str, str] = {
    "INSET":        "#fff7d0",
    "Holiday":      "#eef7ff",
    "Half-Term":    "#cfe8ff",
    "Bank Holiday": "#ffe6d0",
    "Exam Period":  "#ead0ff",
    "Other":        "#e0e0e0",
}


def _uk_bank_holidays(start: _dt.date, end: _dt.date
                       ) -> list[tuple[str, str]]:
    """Return [(name, iso_date)] for UK England & Wales bank holidays
    falling in [start, end]. Hard-coded table — easier than depending
    on an external feed."""
    table: dict[int, list[tuple[str, str]]] = {
        2024: [("New Year's Day", "2024-01-01"),
               ("Good Friday", "2024-03-29"),
               ("Easter Monday", "2024-04-01"),
               ("Early May Bank Holiday", "2024-05-06"),
               ("Spring Bank Holiday", "2024-05-27"),
               ("Summer Bank Holiday", "2024-08-26"),
               ("Christmas Day", "2024-12-25"),
               ("Boxing Day", "2024-12-26")],
        2025: [("New Year's Day", "2025-01-01"),
               ("Good Friday", "2025-04-18"),
               ("Easter Monday", "2025-04-21"),
               ("Early May Bank Holiday", "2025-05-05"),
               ("Spring Bank Holiday", "2025-05-26"),
               ("Summer Bank Holiday", "2025-08-25"),
               ("Christmas Day", "2025-12-25"),
               ("Boxing Day", "2025-12-26")],
        2026: [("New Year's Day", "2026-01-01"),
               ("Good Friday", "2026-04-03"),
               ("Easter Monday", "2026-04-06"),
               ("Early May Bank Holiday", "2026-05-04"),
               ("Spring Bank Holiday", "2026-05-25"),
               ("Summer Bank Holiday", "2026-08-31"),
               ("Christmas Day", "2026-12-25"),
               ("Boxing Day (Sub.)", "2026-12-28")],
        2027: [("New Year's Day", "2027-01-01"),
               ("Good Friday", "2027-03-26"),
               ("Easter Monday", "2027-03-29"),
               ("Early May Bank Holiday", "2027-05-03"),
               ("Spring Bank Holiday", "2027-05-31"),
               ("Summer Bank Holiday", "2027-08-30"),
               ("Christmas Day (Sub.)", "2027-12-27"),
               ("Boxing Day (Sub.)", "2027-12-28")],
    }
    out: list[tuple[str, str]] = []
    for y in range(start.year, end.year + 1):
        for name, iso in table.get(y, []):
            try:
                d = _dt.date.fromisoformat(iso)
            except ValueError:
                continue
            if start <= d <= end:
                out.append((name, iso))
    return out


def _dow_label(iso: str) -> str:
    try:
        return _dt.date.fromisoformat(iso).strftime("%a")
    except ValueError:
        return ""


def _parse_ics(text: str) -> list[tuple[str, str, str]]:
    """Minimal ICS reader. Returns [(summary, start_iso, end_iso)] from
    VEVENTs with VALUE=DATE DTSTART/DTEND. DTEND is exclusive in iCal —
    we shift it back by one day to be inclusive."""
    out: list[tuple[str, str, str]] = []
    blocks = []
    cur: list[str] = []
    inside = False
    # Unfold line continuations (lines starting with space/tab continue
    # the previous line per RFC 5545).
    raw_lines = text.splitlines()
    folded: list[str] = []
    for ln in raw_lines:
        if ln.startswith((" ", "\t")) and folded:
            folded[-1] += ln[1:]
        else:
            folded.append(ln)
    for ln in folded:
        if ln.startswith("BEGIN:VEVENT"):
            inside = True
            cur = []
        elif ln.startswith("END:VEVENT"):
            inside = False
            blocks.append(cur)
        elif inside:
            cur.append(ln)

    for block in blocks:
        summary = ""
        start = ""
        end = ""
        for ln in block:
            if ln.startswith("SUMMARY:"):
                summary = ln[len("SUMMARY:"):].strip() or "Imported"
            elif ln.startswith("DTSTART"):
                v = ln.split(":", 1)[-1].strip()
                v = v[:8]
                if len(v) == 8 and v.isdigit():
                    start = f"{v[:4]}-{v[4:6]}-{v[6:8]}"
            elif ln.startswith("DTEND"):
                v = ln.split(":", 1)[-1].strip()
                v = v[:8]
                if len(v) == 8 and v.isdigit():
                    end = f"{v[:4]}-{v[4:6]}-{v[6:8]}"
        if not start:
            continue
        if end:
            try:
                end = _shift_iso(end, -1)
            except Exception:
                end = start
        else:
            end = start
        out.append((summary or "Imported", start, end))
    return out


class BreaksTab:
    LAST_TYPE: str = DEFAULT_BREAK_TYPE  # remembered between dialogs

    def __init__(self, nb: ttk.Notebook, state: dict) -> None:
        self.state = state
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Breaks")
        self._grouped: bool = False
        self._breaks: list[Break] = []
        self._terms: list[Term] = []
        self._build()
        self.refresh()

    # ── UI build ────────────────────────────────────────────────

    def _build(self) -> None:
        # Row 1 — year / type filter / refresh.
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_cb = ttk.Combobox(bar, state="readonly", width=40)
        self.year_cb.pack(side="left", padx=(2, 10))
        self.year_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self._on_year_change())
        ttk.Label(bar, text="Type:").pack(side="left")
        self.type_cb = ttk.Combobox(bar, values=("",) + BREAK_TYPES,
                                       state="readonly", width=14)
        self.type_cb.current(0)
        self.type_cb.bind("<<ComboboxSelected>>",
                            lambda _e: self.refresh())
        self.type_cb.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.group_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Group by type",
                          variable=self.group_var,
                          command=self._toggle_grouped).pack(
            side="left", padx=(10, 0))

        # Row 2 — date range filter.
        rng = ttk.Frame(self.frame)
        rng.pack(fill="x", padx=8, pady=(2, 2))
        ttk.Label(rng, text="Date range:").pack(side="left")
        self.from_e = ttk.Entry(rng, width=12)
        self.from_e.pack(side="left", padx=(2, 4))
        ttk.Label(rng, text="to").pack(side="left")
        self.to_e = ttk.Entry(rng, width=12)
        self.to_e.pack(side="left", padx=(2, 4))
        ttk.Button(rng, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(rng, text="Clear",
                    command=self._clear_range).pack(side="left")

        # Row 3 — colour legend.
        legend = ttk.Frame(self.frame)
        legend.pack(fill="x", padx=8, pady=(2, 4))
        ttk.Label(legend, text="Legend:").pack(side="left")
        for name, colour in BREAK_COLOURS.items():
            sw = tk.Label(legend, text=f" {name} ",
                            bg=colour, fg="#222",
                            relief="solid", borderwidth=1,
                            padx=4, pady=0)
            sw.pack(side="left", padx=2)

        # Table
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "type", "start", "end", "days", "check")
        self.tree = ttk.Treeview(
            table_frame, columns=cols,
            show="tree headings", selectmode="extended")
        headings = {"id": "ID", "name": "Name", "type": "Type",
                    "start": "Start (Day)", "end": "End (Day)",
                    "days": "Days", "check": "Check"}
        widths = {"id": 60, "name": 220, "type": 110,
                  "start": 130, "end": 130, "days": 70, "check": 140}
        self.tree.heading("#0", text="")
        self.tree.column("#0", width=20, stretch=False)
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "days" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for typ, colour in BREAK_COLOURS.items():
            self.tree.tag_configure(typ, background=colour)
        self.tree.tag_configure("group", background="#dadada",
                                   font=("TkDefaultFont", 9, "bold"))
        self.tree.tag_configure("outside-term", background="#ffe9e9")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        # Action row 1 — CRUD
        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 2))
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete selected (bulk)",
                    command=self._bulk_delete).pack(side="left", padx=4)

        # Action row 2 — quick adds & imports
        more = ttk.Frame(self.frame)
        more.pack(fill="x", padx=8, pady=(2, 8))
        ttk.Button(more, text="Add INSET day…",
                    command=self._quick_inset).pack(side="left")
        ttk.Button(more, text="Import UK bank holidays",
                    command=self._import_bank_holidays).pack(
            side="left", padx=4)
        ttk.Button(more, text="Recurring template…",
                    command=self._recurring_template).pack(
            side="left", padx=4)
        ttk.Button(more, text="Import .ics…",
                    command=self._import_ics).pack(side="left", padx=4)

    # ── year combo helpers ─────────────────────────────────────

    def _year_options(self) -> list[tuple[int, str]]:
        years = data.list_years()
        return [(y.year_id, f"#{y.year_id} {y.name}"
                            f"{' *' if y.is_current else ''}")
                for y in years]

    def _on_year_change(self) -> None:
        idx = self.year_cb.current()
        if idx < 0:
            return
        self.state["selected_year_id"] = self._year_ids[idx]
        self.refresh()

    def _clear_range(self) -> None:
        self.from_e.delete(0, "end")
        self.to_e.delete(0, "end")
        self.refresh()

    def _toggle_grouped(self) -> None:
        self._grouped = bool(self.group_var.get())
        self.refresh()

    # ── refresh / render ────────────────────────────────────────

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        opts = self._year_options()
        self._year_ids = [yid for yid, _ in opts]
        labels = [lbl for _, lbl in opts]
        self.year_cb["values"] = labels

        if not opts:
            self.count_var.set("No academic years configured.")
            self._breaks = []
            self._terms = []
            return

        target = self.state.get("selected_year_id") or self._year_ids[0]
        try:
            idx = self._year_ids.index(target)
        except ValueError:
            idx = 0
            target = self._year_ids[0]
        self.year_cb.current(idx)
        self.state["selected_year_id"] = target

        btype = self.type_cb.get() or None
        try:
            rows = data.list_breaks(year_id=target, type=btype)
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return

        # Apply date range filter
        frm = self.from_e.get().strip()
        to = self.to_e.get().strip()
        if frm:
            rows = [r for r in rows if r.end_date >= frm]
        if to:
            rows = [r for r in rows if r.start_date <= to]
        self._breaks = rows
        self._terms = data.list_terms(year_id=target)
        term_ranges = [(t.start_date, t.end_date) for t in self._terms]

        def in_any_term(b: Break) -> bool:
            for s, e in term_ranges:
                if not (b.end_date < s or b.start_date > e):
                    return True
            return False

        if self._grouped:
            by_type: dict[str, list[Break]] = {}
            for b in rows:
                by_type.setdefault(b.type, []).append(b)
            for typ in BREAK_TYPES:
                bs = by_type.get(typ, [])
                if not bs:
                    continue
                gid = f"grp:{typ}"
                self.tree.insert(
                    "", "end", iid=gid,
                    text=f"{typ}  ({len(bs)})",
                    values=("", "", "", "", "", "", ""),
                    tags=("group",), open=True)
                for b in bs:
                    self._insert_break_row(b, parent=gid,
                                             outside=not in_any_term(b))
        else:
            for b in rows:
                self._insert_break_row(b, parent="",
                                         outside=not in_any_term(b))

        total_days = sum(b.day_count for b in rows)
        per_type = {}
        for b in rows:
            per_type[b.type] = per_type.get(b.type, 0) + b.day_count
        per_str = "  ".join(f"{k}: {v}d" for k, v in per_type.items())
        outside_n = sum(1 for b in rows if not in_any_term(b))
        outside_str = (f"  ({outside_n} outside any term ⚠)"
                        if outside_n else "")
        self.count_var.set(
            f"{len(rows)} break(s), {total_days} day(s){outside_str}"
            + (f"  —  {per_str}" if per_str else ""))

    def _insert_break_row(self, b: Break, *, parent: str,
                            outside: bool) -> None:
        tags = []
        if b.type in BREAK_COLOURS:
            tags.append(b.type)
        if outside:
            tags.append("outside-term")
        start_lbl = f"{b.start_date} ({_dow_label(b.start_date)})"
        end_lbl = f"{b.end_date} ({_dow_label(b.end_date)})"
        check = "⚠ outside term" if outside else "✓"
        self.tree.insert(parent, "end", iid=str(b.break_id), values=(
            b.break_id, b.name, b.type, start_lbl, end_lbl,
            b.day_count, check,
        ), tags=tuple(tags))

    # ── selection ──────────────────────────────────────────────

    def _selected_id(self) -> int | None:
        for iid in self.tree.selection():
            if iid.startswith("grp:"):
                continue
            try:
                return int(iid)
            except ValueError:
                return None
        return None

    def _selected_ids(self) -> list[int]:
        out: list[int] = []
        for iid in self.tree.selection():
            if iid.startswith("grp:"):
                continue
            try:
                out.append(int(iid))
            except ValueError:
                pass
        return out

    def _current_year(self) -> AcademicYear | None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            return None
        return data.get_year(yid)

    # ── CRUD ────────────────────────────────────────────────────

    def _new(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("New", "Pick a year first.")
            return
        BreakDialog(self.frame.winfo_toplevel(), year=year,
                     existing=None,
                     default_type=BreaksTab.LAST_TYPE,
                     on_save=self._after_new)

    def _after_new(self, last_type: str | None = None) -> None:
        if last_type:
            BreaksTab.LAST_TYPE = last_type
        self.refresh()

    def _edit_selected(self) -> None:
        bid = self._selected_id()
        if bid is None:
            messagebox.showinfo("Edit", "Select a break first.")
            return
        existing = data.get_break(bid)
        if existing is None:
            return
        year = data.get_year(existing.year_id)
        if year is None:
            return
        BreakDialog(self.frame.winfo_toplevel(), year=year,
                     existing=existing, on_save=self._after_new)

    def _delete_selected(self) -> None:
        bid = self._selected_id()
        if bid is None:
            messagebox.showinfo("Delete", "Select a break first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete break #{bid}? (Soft-delete — Ctrl-Z to undo)"):
            return
        try:
            data.delete_break(bid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        undo = self.state.get("_undo")
        if undo is not None:
            undo.push(f"delete break #{bid}",
                       lambda i=bid: data.restore_break(i))
        toaster = self.state.get("_toast")
        if toaster:
            toaster(f"Deleted break #{bid} — Ctrl-Z to undo",
                      kind="warn")
        self.refresh()

    def _bulk_delete(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Delete",
                                   "Select one or more breaks first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete {len(ids)} break(s)? "
                "(Soft-delete — Ctrl-Z to undo)"):
            return
        errs: list[str] = []
        deleted: list[int] = []
        for bid in ids:
            try:
                if data.delete_break(bid):
                    deleted.append(bid)
            except Exception as e:
                errs.append(f"#{bid}: {e}")
        if errs:
            messagebox.showerror("Some deletes failed",
                                    "\n".join(errs))
        undo = self.state.get("_undo")
        if undo is not None and deleted:
            def _restore_many(_ids=deleted) -> None:
                for i in _ids:
                    try:
                        data.restore_break(i)
                    except Exception:
                        pass
            undo.push(f"bulk delete {len(deleted)} break(s)",
                       _restore_many)
        toaster = self.state.get("_toast")
        if toaster and deleted:
            toaster(f"Deleted {len(deleted)} break(s) — Ctrl-Z to undo",
                      kind="warn")
        self.refresh()

    # ── Quick adds / imports ────────────────────────────────────

    def _quick_inset(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("INSET", "Pick a year first.")
            return
        QuickInsetDialog(self.frame.winfo_toplevel(), year=year,
                          on_save=self.refresh)

    def _import_bank_holidays(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("Bank holidays", "Pick a year first.")
            return
        try:
            ys = _dt.date.fromisoformat(year.start_date)
            ye = _dt.date.fromisoformat(year.end_date)
        except ValueError as e:
            messagebox.showerror("Bank holidays", str(e))
            return
        candidates = _uk_bank_holidays(ys, ye)
        if not candidates:
            messagebox.showinfo(
                "Bank holidays",
                "No bank holidays in the built-in table fall within "
                f"{year.name} ({year.start_date} → {year.end_date}).")
            return
        # Skip ones already present (by name + start date)
        existing = {(b.name, b.start_date)
                     for b in data.list_breaks(year_id=year.year_id)}
        new = [(n, d) for (n, d) in candidates
                if (n, d) not in existing]
        if not new:
            messagebox.showinfo("Bank holidays",
                                   "All bank holidays already exist.")
            return
        preview = "\n".join(f"  • {n}  {d}" for n, d in new[:12])
        more = "" if len(new) <= 12 else f"\n  …and {len(new) - 12} more"
        if not messagebox.askyesno(
                "Bank holidays",
                f"Import {len(new)} UK bank holiday(s) as Bank Holiday "
                f"breaks?\n\n{preview}{more}"):
            return
        errs: list[str] = []
        for name, iso in new:
            try:
                data.create_break({
                    "year_id": year.year_id, "name": name,
                    "type": "Bank Holiday",
                    "start_date": iso, "end_date": iso, "notes": None,
                })
            except (ValidationError, Exception) as ex:
                errs.append(f"{name}: {ex}")
        if errs:
            messagebox.showerror("Some inserts failed", "\n".join(errs))
        self.refresh()

    def _recurring_template(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("Recurring", "Pick a year first.")
            return
        RecurringBreakDialog(self.frame.winfo_toplevel(), year=year,
                               on_save=self.refresh)

    def _import_ics(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("Import", "Pick a year first.")
            return
        path = filedialog.askopenfilename(
            filetypes=[("iCalendar", "*.ics"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as e:
            messagebox.showerror("Import", str(e))
            return
        events = _parse_ics(text)
        if not events:
            messagebox.showinfo("Import",
                                   "No usable VEVENTs found.")
            return
        # Filter to year range
        in_range = [(n, s, e) for (n, s, e) in events
                      if not (e < year.start_date
                                or s > year.end_date)]
        if not in_range:
            messagebox.showinfo("Import",
                                   f"No events fall within {year.name}.")
            return
        preview = "\n".join(f"  • {n}  {s} → {e}"
                              for n, s, e in in_range[:10])
        more = ("" if len(in_range) <= 10
                 else f"\n  …and {len(in_range) - 10} more")
        if not messagebox.askyesno(
                "Import",
                f"Import {len(in_range)} event(s) as Holiday breaks?\n\n"
                f"{preview}{more}"):
            return
        errs: list[str] = []
        added = 0
        for name, s, e in in_range:
            try:
                data.create_break({
                    "year_id": year.year_id,
                    "name": name, "type": "Holiday",
                    "start_date": s, "end_date": e, "notes": None,
                })
                added += 1
            except (ValidationError, Exception) as ex:
                errs.append(f"{name}: {ex}")
        if errs:
            messagebox.showerror("Some inserts failed",
                                    f"Added {added}.\n" + "\n".join(errs))
        self.refresh()


# ══ Calendar tab ═════════════════════════════════════════════════

# Heatmap palette for the month grid.
HEAT_COLOURS: dict[str, str] = {
    "outside":      "#ffffff",
    "teaching":     "#dff3d8",
    "weekend":      "#ececec",
    "Holiday":      "#cfe8ff",
    "Half-Term":    "#b8d9f4",
    "INSET":        "#fff3b0",
    "Bank Holiday": "#ffd5b0",
    "Exam Period":  "#ead0ff",
    "Other":        "#d8d8d8",
}


class CalendarTab:
    """Year-at-a-glance: 12-month grid heatmap + click-to-lookup +
    summary panel + term progress."""

    MONTHS_PER_ROW = 4
    DAY_CELL_W = 26
    DAY_CELL_H = 22
    HEADER_H = 20
    MONTH_TITLE_H = 22
    MONTH_PAD_X = 14
    MONTH_PAD_Y = 18
    WEEKNUM_W = 22

    def __init__(self, nb: ttk.Notebook, state: dict) -> None:
        self.state = state
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Calendar")
        # Cache: iso date -> (kind, label)
        self._day_kind: dict[str, tuple[str, str]] = {}
        # Cache: (col, row) bounding boxes of day cells -> iso
        self._cell_rects: list[tuple[int, int, int, int, str]] = []
        self._summary_year_id: int | None = None
        self._build()
        self.refresh()

    # ── UI ──────────────────────────────────────────────────────

    def _build(self) -> None:
        # Top bar — year, ◀/▶ year nav, date, today, look up, print.
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="◀", width=2,
                    command=lambda: self._step_year(-1)).pack(side="left")
        ttk.Label(bar, text=" Year:").pack(side="left")
        self.year_cb = ttk.Combobox(bar, state="readonly", width=34)
        self.year_cb.pack(side="left", padx=(2, 4))
        self.year_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self._on_year_change())
        ttk.Button(bar, text="▶", width=2,
                    command=lambda: self._step_year(1)).pack(side="left")

        ttk.Label(bar, text="    Date:").pack(side="left")
        self.date_e = ttk.Entry(bar, width=14)
        self.date_e.insert(0, _today())
        self.date_e.pack(side="left", padx=(2, 4))
        ttk.Button(bar, text="Today",
                    command=self._set_today).pack(side="left", padx=2)
        ttk.Button(bar, text="Look up",
                    command=self._lookup).pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Save as PostScript…",
                    command=self._save_postscript).pack(side="right")

        # Progress / countdown line
        prog_bar = ttk.Frame(self.frame)
        prog_bar.pack(fill="x", padx=8, pady=(0, 4))
        self.progress = ttk.Progressbar(prog_bar, mode="determinate",
                                            maximum=100, length=200)
        self.progress.pack(side="left")
        self.progress_label = tk.StringVar(value="")
        ttk.Label(prog_bar, textvariable=self.progress_label,
                   anchor="w").pack(side="left", padx=8)

        self.countdown_label = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.countdown_label,
                   anchor="w").pack(fill="x", padx=8)

        # Body — month grid on the left, summary on the right.
        body = ttk.Frame(self.frame)
        body.pack(fill="both", expand=True, padx=8, pady=(4, 4))

        cal_wrap = ttk.LabelFrame(body, text="Year heatmap")
        cal_wrap.pack(side="left", fill="both", expand=True,
                        padx=(0, 6))
        self.cal_canvas = tk.Canvas(cal_wrap, bg="white",
                                       highlightthickness=0)
        cal_vs = ttk.Scrollbar(cal_wrap, orient="vertical",
                                  command=self.cal_canvas.yview)
        self.cal_canvas.configure(yscrollcommand=cal_vs.set)
        self.cal_canvas.pack(side="left", fill="both", expand=True)
        cal_vs.pack(side="right", fill="y")
        self.cal_canvas.bind("<Configure>",
                               lambda _e: self._draw_calendar())
        self.cal_canvas.bind("<Button-1>", self._on_canvas_click)
        self.cal_canvas.bind("<Motion>", self._on_canvas_hover)

        summ = ttk.LabelFrame(body, text="Summary")
        summ.pack(side="left", fill="y")
        self.text = tk.Text(summ, wrap="none", width=46, height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=4, pady=4)
        self.text.configure(state="disabled")

        # Legend strip
        leg = ttk.Frame(self.frame)
        leg.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(leg, text="Heatmap:").pack(side="left")
        for kind in ("teaching", "weekend", "Holiday", "Half-Term",
                       "INSET", "Bank Holiday", "Exam Period", "Other"):
            tk.Label(leg, text=f" {kind} ",
                      bg=HEAT_COLOURS.get(kind, "#ffffff"),
                      fg="#222", relief="solid", borderwidth=1,
                      padx=4).pack(side="left", padx=2)

    # ── Year combo / nav ───────────────────────────────────────

    def _year_options(self) -> list[tuple[int, str]]:
        years = data.list_years()
        return [(y.year_id, f"#{y.year_id} {y.name}"
                            f"{' *' if y.is_current else ''}")
                for y in years]

    def _on_year_change(self) -> None:
        idx = self.year_cb.current()
        if idx < 0:
            return
        self.state["selected_year_id"] = self._year_ids[idx]
        self._render_all()

    def _step_year(self, delta: int) -> None:
        if not self._year_ids:
            return
        try:
            idx = self._year_ids.index(self.state.get("selected_year_id"))
        except (KeyError, ValueError):
            idx = 0
        idx = (idx + delta) % len(self._year_ids)
        self.state["selected_year_id"] = self._year_ids[idx]
        self.year_cb.current(idx)
        self._render_all()

    def _set_today(self) -> None:
        self.date_e.delete(0, "end")
        self.date_e.insert(0, _today())
        self._lookup()

    def refresh(self) -> None:
        opts = self._year_options()
        self._year_ids = [yid for yid, _ in opts]
        labels = [lbl for _, lbl in opts]
        self.year_cb["values"] = labels
        if not opts:
            self._write("No academic years configured.")
            self.cal_canvas.delete("all")
            self.progress["value"] = 0
            self.progress_label.set("")
            self.countdown_label.set("")
            return
        target = self.state.get("selected_year_id") or self._year_ids[0]
        try:
            idx = self._year_ids.index(target)
        except ValueError:
            idx = 0
            target = self._year_ids[0]
        self.year_cb.current(idx)
        self.state["selected_year_id"] = target
        self._render_all()

    # ── Lookup ──────────────────────────────────────────────────

    def _lookup(self) -> None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            messagebox.showinfo("Lookup", "Pick a year first.")
            return
        s = self.date_e.get().strip()
        try:
            term = data.find_term_on(yid, s)
            brk = data.is_break(yid, s)
            d = _dt.date.fromisoformat(s)
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Lookup", str(e))
            return
        lines: list[str] = []
        lines.append(f"Date    : {s} ({d.strftime('%A')})")
        lines.append(f"Term    : "
                     f"{term.name if term else '— (outside any term)'}")
        if brk:
            lines.append(f"Break   : {brk.name} ({brk.type})")
        elif d.weekday() >= 5:
            lines.append("Status  : Weekend (non-teaching)")
        else:
            lines.append("Status  : Teaching day")
        # Day-N-of-year indicators
        year = data.get_year(yid)
        if year is not None:
            try:
                ys = _dt.date.fromisoformat(year.start_date)
                ye = _dt.date.fromisoformat(year.end_date)
                if ys <= d <= ye:
                    n = (d - ys).days + 1
                    total = (ye - ys).days + 1
                    lines.append(f"Day     : {n} of {total} "
                                  f"(year)")
                    if term is not None:
                        try:
                            ts = _dt.date.fromisoformat(term.start_date)
                            te = _dt.date.fromisoformat(term.end_date)
                            tn = (d - ts).days + 1
                            ttot = (te - ts).days + 1
                            lines.append(f"          {tn} of {ttot} "
                                          f"({term.name})")
                        except ValueError:
                            pass
            except ValueError:
                pass
        lines.append("")
        lines.append("─" * 50)
        self._render_summary(prepend="\n".join(lines))

    # ── Render combinator ──────────────────────────────────────

    def _render_all(self) -> None:
        self._build_day_kind_cache()
        self._render_summary()
        self._draw_calendar()
        self._render_progress_and_countdown()

    def _build_day_kind_cache(self) -> None:
        self._day_kind.clear()
        yid = self.state.get("selected_year_id")
        if yid is None:
            return
        year = data.get_year(yid)
        if year is None:
            return
        try:
            ys = _dt.date.fromisoformat(year.start_date)
            ye = _dt.date.fromisoformat(year.end_date)
        except ValueError:
            return
        breaks = data.list_breaks(year_id=yid)
        # iso -> (type, name)
        bmap: dict[str, tuple[str, str]] = {}
        for b in breaks:
            try:
                bs = _dt.date.fromisoformat(b.start_date)
                be = _dt.date.fromisoformat(b.end_date)
            except ValueError:
                continue
            cur = bs
            one = _dt.timedelta(days=1)
            while cur <= be:
                iso = cur.isoformat()
                # Earlier breaks win — explicit by ORDER BY start_date.
                bmap.setdefault(iso, (b.type, b.name))
                cur += one
        cur = ys
        one = _dt.timedelta(days=1)
        while cur <= ye:
            iso = cur.isoformat()
            if iso in bmap:
                self._day_kind[iso] = bmap[iso]
            elif cur.weekday() >= 5:
                self._day_kind[iso] = ("weekend", "Weekend")
            else:
                self._day_kind[iso] = ("teaching", "Teaching day")
            cur += one

    # ── Calendar drawing ───────────────────────────────────────

    def _draw_calendar(self) -> None:
        self.cal_canvas.delete("all")
        self._cell_rects.clear()
        yid = self.state.get("selected_year_id")
        if yid is None:
            return
        year = data.get_year(yid)
        if year is None:
            return
        try:
            ys = _dt.date.fromisoformat(year.start_date)
            ye = _dt.date.fromisoformat(year.end_date)
        except ValueError:
            return

        # Enumerate months spanning the year (inclusive).
        months: list[_dt.date] = []
        cur = _dt.date(ys.year, ys.month, 1)
        end_of = _dt.date(ye.year, ye.month, 1)
        while cur <= end_of:
            months.append(cur)
            if cur.month == 12:
                cur = _dt.date(cur.year + 1, 1, 1)
            else:
                cur = _dt.date(cur.year, cur.month + 1, 1)

        month_w = self.WEEKNUM_W + 7 * self.DAY_CELL_W
        month_h = (self.MONTH_TITLE_H + self.HEADER_H
                    + 6 * self.DAY_CELL_H)
        cols = max(1, self.MONTHS_PER_ROW)
        rows = (len(months) + cols - 1) // cols
        total_w = cols * month_w + (cols + 1) * self.MONTH_PAD_X
        total_h = rows * month_h + (rows + 1) * self.MONTH_PAD_Y
        self.cal_canvas.configure(
            scrollregion=(0, 0, total_w, total_h))

        today_iso = _today()
        lookup_iso = self.date_e.get().strip()

        for i, m in enumerate(months):
            r, c = divmod(i, cols)
            x0 = self.MONTH_PAD_X + c * (month_w + self.MONTH_PAD_X)
            y0 = self.MONTH_PAD_Y + r * (month_h + self.MONTH_PAD_Y)
            self._draw_month(m, ys, ye, x0, y0, month_w, month_h,
                              today_iso, lookup_iso)

    def _draw_month(self, m: _dt.date, ys: _dt.date, ye: _dt.date,
                     x0: int, y0: int, w: int, h: int,
                     today_iso: str, lookup_iso: str) -> None:
        c = self.cal_canvas
        c.create_rectangle(x0, y0, x0 + w, y0 + h,
                              outline="#bbb", fill="white")
        c.create_rectangle(x0, y0, x0 + w, y0 + self.MONTH_TITLE_H,
                              outline="", fill="#f4f4f4")
        c.create_text(x0 + w // 2, y0 + self.MONTH_TITLE_H // 2,
                         text=m.strftime("%B %Y"),
                         font=("TkDefaultFont", 10, "bold"))

        hy = y0 + self.MONTH_TITLE_H
        # Week-number header
        c.create_text(x0 + self.WEEKNUM_W // 2, hy + self.HEADER_H // 2,
                         text="Wk", fill="#888",
                         font=("TkDefaultFont", 8))
        dow_labels = ("M", "T", "W", "T", "F", "S", "S")
        for i, lbl in enumerate(dow_labels):
            cx = (x0 + self.WEEKNUM_W
                   + i * self.DAY_CELL_W + self.DAY_CELL_W // 2)
            c.create_text(cx, hy + self.HEADER_H // 2,
                             text=lbl,
                             fill="#555" if i < 5 else "#888",
                             font=("TkDefaultFont", 8, "bold"))

        # Days
        first = _dt.date(m.year, m.month, 1)
        # Last day of month
        if m.month == 12:
            nxt = _dt.date(m.year + 1, 1, 1)
        else:
            nxt = _dt.date(m.year, m.month + 1, 1)
        last = nxt - _dt.timedelta(days=1)

        # Start at Monday of the week containing `first`.
        start_cell = first - _dt.timedelta(days=first.weekday())
        gy = hy + self.HEADER_H
        for week in range(6):
            row_y = gy + week * self.DAY_CELL_H
            week_anchor = start_cell + _dt.timedelta(days=7 * week)
            # ISO week number for the Thursday of that week (good enough)
            try:
                wknum = week_anchor.isocalendar()[1]
            except ValueError:
                wknum = 0
            c.create_text(
                x0 + self.WEEKNUM_W // 2,
                row_y + self.DAY_CELL_H // 2,
                text=str(wknum), fill="#999",
                font=("TkDefaultFont", 8))
            for i in range(7):
                d = start_cell + _dt.timedelta(days=7 * week + i)
                cx0 = x0 + self.WEEKNUM_W + i * self.DAY_CELL_W
                cy0 = row_y
                cx1 = cx0 + self.DAY_CELL_W
                cy1 = cy0 + self.DAY_CELL_H
                if d.month != m.month:
                    c.create_rectangle(cx0, cy0, cx1, cy1,
                                          fill="#fafafa", outline="#eee")
                    continue
                iso = d.isoformat()
                if ys <= d <= ye:
                    kind, _name = self._day_kind.get(
                        iso, ("outside", ""))
                else:
                    kind = "outside"
                fill = HEAT_COLOURS.get(kind, "#ffffff")
                outline = "#ddd"
                if iso == today_iso:
                    outline = "#1a73e8"
                if iso == lookup_iso:
                    outline = "#d12d2d"
                c.create_rectangle(cx0, cy0, cx1, cy1,
                                      fill=fill, outline=outline)
                c.create_text(cx0 + self.DAY_CELL_W // 2,
                                 cy0 + self.DAY_CELL_H // 2,
                                 text=str(d.day),
                                 fill="#222",
                                 font=("TkDefaultFont", 9))
                self._cell_rects.append((cx0, cy0, cx1, cy1, iso))

    def _on_canvas_click(self, event: tk.Event) -> None:
        x = self.cal_canvas.canvasx(event.x)
        y = self.cal_canvas.canvasy(event.y)
        for cx0, cy0, cx1, cy1, iso in self._cell_rects:
            if cx0 <= x <= cx1 and cy0 <= y <= cy1:
                self.date_e.delete(0, "end")
                self.date_e.insert(0, iso)
                self._lookup()
                return

    def _on_canvas_hover(self, event: tk.Event) -> None:
        x = self.cal_canvas.canvasx(event.x)
        y = self.cal_canvas.canvasy(event.y)
        for cx0, cy0, cx1, cy1, _iso in self._cell_rects:
            if cx0 <= x <= cx1 and cy0 <= y <= cy1:
                self.cal_canvas.configure(cursor="hand2")
                return
        self.cal_canvas.configure(cursor="")

    # ── Progress + countdown ───────────────────────────────────

    def _render_progress_and_countdown(self) -> None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            self.progress["value"] = 0
            self.progress_label.set("")
            self.countdown_label.set("")
            return
        year = data.get_year(yid)
        if year is None:
            return
        today = _dt.date.today()
        try:
            ys = _dt.date.fromisoformat(year.start_date)
            ye = _dt.date.fromisoformat(year.end_date)
        except ValueError:
            return
        # Year countdown
        if today < ys:
            self.countdown_label.set(
                f"📅  Year starts in {(ys - today).days} day(s).")
        elif today > ye:
            self.countdown_label.set(
                f"📅  Year ended {(today - ye).days} day(s) ago.")
        else:
            try:
                taught_so_far = data.teaching_days_in(
                    yid, date_from=year.start_date,
                    date_to=today.isoformat())
                taught_total = data.teaching_days_in(yid)
            except Exception:
                taught_so_far, taught_total = 0, 0
            self.countdown_label.set(
                f"📅  {(ye - today).days} day(s) until end of year   "
                f"·   Teaching day {taught_so_far} of "
                f"{taught_total}")
        # Term progress (current term containing today)
        term = data.find_term_on(yid, today.isoformat())
        if term is None:
            self.progress["value"] = 0
            self.progress_label.set("Not currently in a term.")
            return
        try:
            ts = _dt.date.fromisoformat(term.start_date)
            te = _dt.date.fromisoformat(term.end_date)
        except ValueError:
            return
        elapsed = (today - ts).days + 1
        total = (te - ts).days + 1
        pct = max(0.0, min(100.0, 100.0 * elapsed / max(total, 1)))
        self.progress["value"] = pct
        self.progress_label.set(
            f"{term.name}: day {elapsed} of {total} "
            f"({pct:.0f}%)")

    # ── Summary text ───────────────────────────────────────────

    def _render_summary(self, *, prepend: str = "") -> None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            self._write(prepend or "No year selected.")
            return
        try:
            summ = data.year_summary(yid)
        except ValidationError as e:
            self._write(str(e))
            return
        y = summ.year
        lines: list[str] = []
        if prepend:
            lines.append(prepend)
            lines.append("")
        lines.append(f"#{y.year_id}  {y.name}  "
                     f"({y.start_date} → {y.end_date})")
        lines.append(f"Status            : {y.status}"
                     f"{'  (current)' if y.is_current else ''}")
        lines.append(f"Total days        : {y.day_count}")
        lines.append(f"Teaching days     : {summ.teaching_days}")
        lines.append(f"Non-teaching days : {summ.non_teaching_days}")
        lines.append(f"Weekend days      : {summ.weekend_days}")
        lines.append("")
        lines.append(f"Terms ({len(summ.terms)}):")
        for t in summ.terms:
            lines.append(f"  #{t.term_id:>3}  {t.name:<14}  "
                         f"{t.start_date} → {t.end_date}  "
                         f"({t.day_count} days)")
        lines.append("")
        lines.append(f"Breaks ({len(summ.breaks)}):")
        for b in summ.breaks:
            lines.append(f"  #{b.break_id:>3}  {b.name:<22}  "
                         f"{b.start_date} → {b.end_date}  "
                         f"({b.day_count} days, {b.type})")
        self._write("\n".join(lines))

    def _write(self, text: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.configure(state="disabled")

    # ── Print / export ─────────────────────────────────────────

    def _save_postscript(self) -> None:
        yid = self.state.get("selected_year_id")
        year = data.get_year(yid) if yid is not None else None
        default = (f"calendar_{year.name.replace('/', '-')}.ps"
                    if year else "calendar.ps")
        path = filedialog.asksaveasfilename(
            defaultextension=".ps",
            initialfile=default,
            filetypes=[("PostScript", "*.ps"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.cal_canvas.postscript(file=path, colormode="color")
        except (OSError, tk.TclError) as e:
            messagebox.showerror("Save failed", str(e))
            return
        messagebox.showinfo(
            "Saved",
            f"Calendar saved to {path}\n\n"
            f"Convert to PDF with:  ps2pdf {path}")


# ══ Dialog helpers (date picker, validation) ══════════════════════

def _open_date_picker(parent: tk.Misc, entry: ttk.Entry,
                       *, year_hint: AcademicYear | None = None,
                       on_pick: Callable[[], None] | None = None
                       ) -> None:
    """Pop up a small year/month grid picker and write the chosen ISO
    date back into ``entry`` (replacing whatever is there)."""
    top = tk.Toplevel(parent)
    top.title("Pick a date")
    top.transient(parent)
    top.after_idle(top.grab_set)
    top.resizable(False, False)

    # Seed state from the entry's current value, else today, else year.
    seed: _dt.date
    cur = entry.get().strip()
    try:
        seed = _dt.date.fromisoformat(cur)
    except ValueError:
        if year_hint is not None:
            try:
                seed = _dt.date.fromisoformat(year_hint.start_date)
            except ValueError:
                seed = _dt.date.today()
        else:
            seed = _dt.date.today()

    state = {"year": seed.year, "month": seed.month}

    bar = ttk.Frame(top)
    bar.pack(fill="x", padx=8, pady=6)
    ttk.Button(bar, text="◀", width=2,
                command=lambda: _shift_month(-1)).pack(side="left")
    title_var = tk.StringVar()
    ttk.Label(bar, textvariable=title_var, width=18,
               anchor="center", font=("TkDefaultFont", 10, "bold")
               ).pack(side="left", padx=4)
    ttk.Button(bar, text="▶", width=2,
                command=lambda: _shift_month(1)).pack(side="left")
    ttk.Button(bar, text="Today",
                command=lambda: _jump_today()).pack(side="right")

    grid = ttk.Frame(top)
    grid.pack(padx=8, pady=(0, 8))
    cells: list[tk.Label] = []
    for i, lbl in enumerate(("M", "T", "W", "T", "F", "S", "S")):
        tk.Label(grid, text=lbl, width=3, fg="#888",
                  font=("TkDefaultFont", 8, "bold")
                  ).grid(row=0, column=i, padx=1, pady=1)

    def _shift_month(delta: int) -> None:
        m = state["month"] + delta
        y = state["year"]
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        state["year"] = y
        state["month"] = m
        _redraw()

    def _jump_today() -> None:
        t = _dt.date.today()
        state["year"] = t.year
        state["month"] = t.month
        _redraw()

    def _pick(d: _dt.date) -> None:
        entry.delete(0, "end")
        entry.insert(0, d.isoformat())
        top.destroy()
        if on_pick:
            on_pick()

    def _redraw() -> None:
        for c in cells:
            c.destroy()
        cells.clear()
        y, m = state["year"], state["month"]
        title_var.set(_dt.date(y, m, 1).strftime("%B %Y"))
        first = _dt.date(y, m, 1)
        start = first - _dt.timedelta(days=first.weekday())
        today = _dt.date.today()
        for week in range(6):
            for i in range(7):
                d = start + _dt.timedelta(days=7 * week + i)
                bg = "#fafafa" if d.month != m else "white"
                fg = "#bbb" if d.month != m else "#222"
                bold = ("TkDefaultFont", 9, "bold") \
                          if d == today else ("TkDefaultFont", 9)
                lbl = tk.Label(grid, text=str(d.day), width=3,
                                relief="solid", borderwidth=1,
                                bg=bg, fg=fg, font=bold)
                lbl.grid(row=1 + week, column=i, padx=1, pady=1)
                lbl.bind("<Button-1>",
                           lambda _e, dd=d: _pick(dd))
                lbl.bind("<Enter>",
                           lambda _e, w=lbl: w.configure(bg="#dde9f4"))
                lbl.bind("<Leave>",
                           lambda _e, w=lbl, b=bg:
                               w.configure(bg=b))
                cells.append(lbl)

    btn_bar = ttk.Frame(top)
    btn_bar.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Button(btn_bar, text="Cancel",
                command=top.destroy).pack(side="right")

    _redraw()
    top.bind("<Escape>", lambda _e: top.destroy())


def _attach_picker(parent: tk.Misc, entry: ttk.Entry,
                    *, year_hint: AcademicYear | None = None,
                    on_pick: Callable[[], None] | None = None
                    ) -> ttk.Button:
    """Drop a 📅 button next to ``entry`` that opens a picker."""
    btn = ttk.Button(
        parent, text="📅", width=3,
        command=lambda: _open_date_picker(
            parent.winfo_toplevel(), entry,
            year_hint=year_hint, on_pick=on_pick))
    return btn


def _is_valid_iso(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    try:
        _dt.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def _wire_validation(entry: ttk.Entry, *,
                      on_change: Callable[[], None] | None = None
                      ) -> None:
    """Turn the entry red on blur if its value isn't an ISO date.
    Also fires ``on_change`` on each keystroke (for live day-count)."""
    def _check(_e=None) -> None:
        s = entry.get().strip()
        if not s or _is_valid_iso(s):
            try:
                entry.configure(foreground="black")
            except tk.TclError:
                pass
            entry.configure(background="white")
        else:
            entry.configure(background="#ffe0e0")
    entry.bind("<FocusOut>", _check)
    entry.bind("<KeyRelease>",
                 lambda _e: (_check(),
                              on_change() if on_change else None))


def _days_between(s: str, e: str) -> int | None:
    if not (_is_valid_iso(s) and _is_valid_iso(e)):
        return None
    try:
        return ((_dt.date.fromisoformat(e)
                  - _dt.date.fromisoformat(s)).days + 1)
    except ValueError:
        return None


# ══ Dialogs ═══════════════════════════════════════════════════════

class YearDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: AcademicYear | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Year" if existing else "New Year")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form, text="Name:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=22)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        self.name_e.grid(row=r, column=1, sticky="w", padx=6,
                           columnspan=2)

        # Defaults for a brand-new year: continue from the most recent
        # existing year's end.
        default_start = ""
        default_end = ""
        if not self.existing:
            years = data.list_years()
            if years:
                latest = max(years, key=lambda y: y.end_date)
                try:
                    ds = (_dt.date.fromisoformat(latest.end_date)
                           + _dt.timedelta(days=1))
                    default_start = ds.isoformat()
                    default_end = (ds + _dt.timedelta(days=364)
                                       ).isoformat()
                except ValueError:
                    pass

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        if self.existing:
            self.start_e.insert(0, self.existing.start_date)
        elif default_start:
            self.start_e.insert(0, default_start)
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.start_e,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        r += 1
        ttk.Label(form, text="End date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        if self.existing:
            self.end_e.insert(0, self.existing.end_date)
        elif default_end:
            self.end_e.insert(0, default_end)
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.end_e,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        r += 1
        self.days_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.days_var,
                   foreground="#666").grid(
            row=r, column=1, sticky="w", padx=6, columnspan=2)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=YEAR_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_YEAR_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6,
                              columnspan=2)

        r += 1
        self.current_var = tk.BooleanVar(
            value=(self.existing.is_current if self.existing else False))
        ttk.Checkbutton(form, text="Flag as current year",
                          variable=self.current_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=2, columnspan=2)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6,
                            columnspan=2)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

        _wire_validation(self.start_e, on_change=self._update_days)
        _wire_validation(self.end_e, on_change=self._update_days)
        self._update_days()
        self.name_e.focus_set()
        self.win.bind("<Return>", lambda _e: self._save())
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _update_days(self) -> None:
        n = _days_between(self.start_e.get(), self.end_e.get())
        if n is None:
            self.days_var.set("")
        elif n <= 0:
            self.days_var.set("⚠ end date is before start date")
        else:
            self.days_var.set(f"{n} day(s)")

    def _save(self) -> None:
        payload = {
            "name":       self.name_e.get().strip(),
            "start_date": self.start_e.get().strip(),
            "end_date":   self.end_e.get().strip(),
            "status":     self.status_cb.get().strip(),
            "is_current": self.current_var.get(),
            "notes":      self.notes_t.get("1.0", "end").strip(),
        }
        if payload["status"] == "Archived" and payload["is_current"]:
            messagebox.showerror(
                "Save failed",
                "A year cannot be both Archived and the current year. "
                "Set status to Active or Planning first.")
            return
        try:
            if self.existing:
                data.update_year(self.existing.year_id, payload)
            else:
                data.create_year(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class TermDialog:
    def __init__(self, parent: tk.Misc, *,
                 year: AcademicYear,
                 existing: Term | None,
                 on_save: Callable[[], None]) -> None:
        self.year = year
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Term" if existing else "New Term")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form,
                   text=f"Year: #{self.year.year_id} {self.year.name}  "
                         f"({self.year.start_date} → {self.year.end_date})"
                   ).grid(row=r, column=0, columnspan=2,
                           sticky="w", pady=(0, 8))

        r += 1
        ttk.Label(form, text="Name:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.name_cb = ttk.Combobox(form, values=TERM_NAMES, width=20)
        self.name_cb.set(self.existing.name if self.existing
                            else DEFAULT_TERM_NAME)
        self.name_cb.grid(row=r, column=1, sticky="w", padx=6,
                            columnspan=2)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(0, (self.existing.start_date
                                  if self.existing
                                  else self.year.start_date))
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.start_e, year_hint=self.year,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        r += 1
        ttk.Label(form, text="End date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        self.end_e.insert(0, (self.existing.end_date
                                if self.existing
                                else self.year.end_date))
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.end_e, year_hint=self.year,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        # "+N weeks" helper bar
        r += 1
        weeks_bar = ttk.Frame(form)
        weeks_bar.grid(row=r, column=1, columnspan=2,
                          sticky="w", padx=6, pady=(2, 0))
        ttk.Label(weeks_bar, text="End = Start +").pack(side="left")
        self.weeks_sp = tk.Spinbox(weeks_bar, from_=1, to=52, width=4)
        self.weeks_sp.delete(0, "end")
        self.weeks_sp.insert(0, "12")
        self.weeks_sp.pack(side="left", padx=2)
        ttk.Label(weeks_bar, text="weeks").pack(side="left")
        ttk.Button(weeks_bar, text="Apply", width=6,
                    command=self._apply_weeks).pack(side="left", padx=4)

        r += 1
        self.days_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.days_var,
                   foreground="#666").grid(
            row=r, column=1, sticky="w", padx=6, columnspan=2)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6,
                            columnspan=2)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

        _wire_validation(self.start_e, on_change=self._update_days)
        _wire_validation(self.end_e, on_change=self._update_days)
        self._update_days()
        self.name_cb.focus_set()
        self.win.bind("<Return>", lambda _e: self._save())
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _apply_weeks(self) -> None:
        try:
            s = _dt.date.fromisoformat(self.start_e.get().strip())
            n = max(1, int(self.weeks_sp.get()))
        except (ValueError, TypeError):
            messagebox.showerror(
                "Weeks helper",
                "Enter a valid start date first.")
            return
        end = s + _dt.timedelta(days=n * 7 - 1)
        self.end_e.delete(0, "end")
        self.end_e.insert(0, end.isoformat())
        self._update_days()

    def _update_days(self) -> None:
        n = _days_between(self.start_e.get(), self.end_e.get())
        if n is None:
            self.days_var.set("")
        elif n <= 0:
            self.days_var.set("⚠ end date is before start date")
        else:
            self.days_var.set(f"{n} day(s)")

    def _save(self) -> None:
        payload = {
            "year_id":    self.year.year_id,
            "name":       self.name_cb.get().strip(),
            "start_date": self.start_e.get().strip(),
            "end_date":   self.end_e.get().strip(),
            "notes":      self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_term(self.existing.term_id, payload)
            else:
                data.create_term(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class BreakDialog:
    def __init__(self, parent: tk.Misc, *,
                 year: AcademicYear,
                 existing: Break | None,
                 on_save: Callable[..., None],
                 default_type: str | None = None) -> None:
        self.year = year
        self.existing = existing
        self.on_save = on_save
        self.default_type = default_type or DEFAULT_BREAK_TYPE
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Break" if existing else "New Break")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form,
                   text=f"Year: #{self.year.year_id} {self.year.name}  "
                         f"({self.year.start_date} → {self.year.end_date})"
                   ).grid(row=r, column=0, columnspan=2,
                           sticky="w", pady=(0, 8))

        r += 1
        ttk.Label(form, text="Name:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=30)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        self.name_e.grid(row=r, column=1, sticky="w", padx=6,
                           columnspan=2)

        r += 1
        ttk.Label(form, text="Type:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=BREAK_TYPES,
                                       state="readonly", width=14)
        self.type_cb.set(self.existing.type if self.existing
                            else self.default_type)
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6,
                            columnspan=2)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(0, (self.existing.start_date
                                  if self.existing
                                  else self.year.start_date))
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.start_e, year_hint=self.year,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        r += 1
        ttk.Label(form, text="End date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        self.end_e.insert(0, (self.existing.end_date
                                if self.existing
                                else self.year.start_date))
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.end_e, year_hint=self.year,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        r += 1
        self.days_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.days_var,
                   foreground="#666").grid(
            row=r, column=1, sticky="w", padx=6, columnspan=2)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6,
                            columnspan=2)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

        _wire_validation(self.start_e, on_change=self._update_days)
        _wire_validation(self.end_e, on_change=self._update_days)
        self._update_days()
        self.name_e.focus_set()
        self.win.bind("<Return>", lambda _e: self._save())
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _update_days(self) -> None:
        n = _days_between(self.start_e.get(), self.end_e.get())
        if n is None:
            self.days_var.set("")
        elif n <= 0:
            self.days_var.set("⚠ end date is before start date")
        else:
            self.days_var.set(f"{n} day(s)")

    def _save(self) -> None:
        payload = {
            "year_id":    self.year.year_id,
            "name":       self.name_e.get().strip(),
            "type":       self.type_cb.get().strip(),
            "start_date": self.start_e.get().strip(),
            "end_date":   self.end_e.get().strip(),
            "notes":      self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_break(self.existing.break_id, payload)
            else:
                data.create_break(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        BreaksTab.LAST_TYPE = payload["type"] or BreaksTab.LAST_TYPE
        self.win.destroy()
        try:
            self.on_save(payload["type"])
        except TypeError:
            self.on_save()


class QuickInsetDialog:
    """One-day INSET creator — name + date."""

    def __init__(self, parent: tk.Misc, *,
                 year: AcademicYear,
                 on_save: Callable[[], None]) -> None:
        self.year = year
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Add INSET day")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form,
                   text=f"Year: {year.name}  "
                         f"({year.start_date} → {year.end_date})"
                   ).grid(row=0, column=0, columnspan=2,
                           sticky="w", pady=(0, 8))
        ttk.Label(form, text="Name:").grid(row=1, column=0,
                                              sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=30)
        self.name_e.insert(0, "INSET Day")
        self.name_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Date:").grid(row=2, column=0,
                                              sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        today = _today()
        default_date = (today if year.start_date <= today <= year.end_date
                          else year.start_date)
        self.date_e.insert(0, default_date)
        self.date_e.grid(row=2, column=1, sticky="w", padx=6)
        _attach_picker(form, self.date_e, year_hint=year
                         ).grid(row=2, column=2, sticky="w")
        _wire_validation(self.date_e)
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)
        self.name_e.focus_set()
        self.win.bind("<Return>", lambda _e: self._save())
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _save(self) -> None:
        d = self.date_e.get().strip()
        try:
            data.create_break({
                "year_id": self.year.year_id,
                "name": self.name_e.get().strip() or "INSET Day",
                "type": "INSET",
                "start_date": d, "end_date": d, "notes": None,
            })
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class RecurringBreakDialog:
    """Generate a series of breaks (e.g. weekly PD afternoons) between
    two dates."""

    WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    def __init__(self, parent: tk.Misc, *,
                 year: AcademicYear,
                 on_save: Callable[[], None]) -> None:
        self.year = year
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Recurring break template")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0
        ttk.Label(form,
                   text=f"Year: {year.name}  "
                         f"({year.start_date} → {year.end_date})"
                   ).grid(row=r, column=0, columnspan=3,
                           sticky="w", pady=(0, 8))
        r += 1
        ttk.Label(form, text="Name prefix:").grid(
            row=r, column=0, sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=24)
        self.name_e.insert(0, "PD Afternoon")
        self.name_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        ttk.Label(form, text="Type:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=BREAK_TYPES,
                                       state="readonly", width=14)
        self.type_cb.set("INSET")
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        ttk.Label(form, text="Every:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.every_sp = tk.Spinbox(form, from_=1, to=12, width=4)
        self.every_sp.delete(0, "end")
        self.every_sp.insert(0, "1")
        self.every_sp.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="weeks").grid(row=r, column=2,
                                              sticky="w")
        r += 1
        ttk.Label(form, text="On:").grid(row=r, column=0,
                                            sticky="e", pady=4)
        self.dow_cb = ttk.Combobox(form, values=self.WEEKDAYS,
                                      state="readonly", width=6)
        self.dow_cb.current(4)  # Fri
        self.dow_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        ttk.Label(form, text="From:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.from_e = ttk.Entry(form, width=14)
        self.from_e.insert(0, year.start_date)
        self.from_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.from_e, year_hint=year
                         ).grid(row=r, column=2, sticky="w")
        _wire_validation(self.from_e)
        r += 1
        ttk.Label(form, text="To:").grid(row=r, column=0,
                                            sticky="e", pady=4)
        self.to_e = ttk.Entry(form, width=14)
        self.to_e.insert(0, year.end_date)
        self.to_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.to_e, year_hint=year
                         ).grid(row=r, column=2, sticky="w")
        _wire_validation(self.to_e)
        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Generate",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _save(self) -> None:
        try:
            frm = _dt.date.fromisoformat(self.from_e.get().strip())
            to = _dt.date.fromisoformat(self.to_e.get().strip())
            every = max(1, int(self.every_sp.get()))
        except (ValueError, TypeError) as e:
            messagebox.showerror("Recurring", f"Bad input: {e}")
            return
        dow = self.dow_cb.current()
        if dow < 0:
            messagebox.showerror("Recurring", "Pick a day of week.")
            return
        # Snap from-date forward to the chosen weekday
        shift = (dow - frm.weekday()) % 7
        cur = frm + _dt.timedelta(days=shift)
        step = _dt.timedelta(days=7 * every)
        dates: list[_dt.date] = []
        while cur <= to:
            dates.append(cur)
            cur += step
        if not dates:
            messagebox.showinfo("Recurring",
                                   "No dates produced. Check inputs.")
            return
        name = self.name_e.get().strip() or "Recurring"
        typ = self.type_cb.get().strip() or "INSET"
        preview = "\n".join(f"  • {name} — {d.isoformat()} "
                              f"({d.strftime('%a')})"
                              for d in dates[:10])
        more = ("" if len(dates) <= 10
                 else f"\n  …and {len(dates) - 10} more")
        if not messagebox.askyesno(
                "Recurring",
                f"Create {len(dates)} {typ} break(s)?\n\n"
                f"{preview}{more}"):
            return
        errs: list[str] = []
        for d in dates:
            iso = d.isoformat()
            try:
                data.create_break({
                    "year_id": self.year.year_id,
                    "name": name, "type": typ,
                    "start_date": iso, "end_date": iso, "notes": None,
                })
            except (ValidationError, Exception) as ex:
                errs.append(f"{iso}: {ex}")
        if errs:
            messagebox.showerror("Some inserts failed",
                                    "\n".join(errs))
        self.win.destroy()
        self.on_save()
