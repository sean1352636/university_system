"""GUI polish widgets (toast, tooltip, theme, undo, help) and JSON import/export helpers.

Split out of ``academic_year_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import datetime as _dt
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from typing import Callable
from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year as data,
)
from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    DEFAULT_BREAK_TYPE,
    ValidationError,
)
from ._common import logger


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
    """Light/dark switch for this window.

    Light is the rest of the sixth form system's own look: the app's ttk
    theme (``clam``, set by the main window) and its colours, untouched.
    It used to switch the whole app to Tk's grey ``default`` theme and
    paint its own colours, so this window — and every window opened after
    it — looked different from the rest of the system.

    ttk styles are shared by every window in the app, so dark mode is put
    back to light when this window closes.
    """

    DARK = {
        "bg": "#1f1f24", "fg": "#e6e6e6",
        "panel": "#2a2a30", "muted": "#aaa",
    }
    # (style, option, palette key) for everything dark mode changes.
    _OVERRIDES = (
        (".", "background", "bg"), (".", "foreground", "fg"),
        ("TFrame", "background", "bg"),
        ("TLabel", "background", "bg"), ("TLabel", "foreground", "fg"),
        ("TLabelframe", "background", "bg"),
        ("TLabelframe", "foreground", "fg"),
        ("TLabelframe.Label", "background", "bg"),
        ("TLabelframe.Label", "foreground", "fg"),
        ("TNotebook", "background", "bg"),
        ("TNotebook.Tab", "background", "panel"),
        ("TNotebook.Tab", "foreground", "fg"),
        ("Treeview", "background", "panel"),
        ("Treeview", "fieldbackground", "panel"),
        ("Treeview", "foreground", "fg"),
    )

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.style = ttk.Style(root)
        self.dark = False
        # The system's own look, captured before anything is changed.
        self._base_theme = self.style.theme_use()
        self._base = {(st, opt): self.style.lookup(st, opt)
                      for st, opt, _key in self._OVERRIDES}
        try:
            self._base_bg = root.cget("bg")
        except tk.TclError:
            self._base_bg = None
        root.bind("<Destroy>", self._on_destroy, add="+")

    def _on_destroy(self, event) -> None:
        if event.widget is self.root and self.dark:
            self.apply(False)

    def apply(self, dark: bool) -> None:
        self.dark = dark
        if not dark:
            try:
                self.style.theme_use(self._base_theme)
            except tk.TclError:
                pass
            for (st, opt), value in self._base.items():
                if value not in (None, ""):
                    self.style.configure(st, **{opt: value})
            if self._base_bg:
                try:
                    self.root.configure(bg=self._base_bg)
                except tk.TclError:
                    pass
            return
        palette = self.DARK
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        for st, opt, key in self._OVERRIDES:
            self.style.configure(st, **{opt: palette[key]})
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
