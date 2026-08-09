"""Shared Tk building blocks for the FE College windows.

Twenty-three windows all need the same handful of things: a page header, a row
of KPI tiles, a filtered table, a modal form. Building each one by hand would
mean twenty-three subtly different tables. These helpers keep them identical,
and keep each window module about its own screen rather than about widget
plumbing.

Everything here is plain ``ttk`` — no third-party widgets — so the windows work
against whatever theme the launcher has selected.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from datetime import date
from tkinter import messagebox, ttk
from typing import Any

# Semantic colours, used for status text and tile accents rather than
# decoration. Chosen to stay legible on the clam theme's light background.
TONE = {
    "good": "#1e7a3c",
    "warn": "#b06d00",
    "bad": "#b3261e",
    "muted": "#6b6b6b",
    "info": "#1c5d99",
    "plain": "",
}

# Attendance / viability band -> tone, so every screen colours a band the same.
BAND_TONE = {
    "on target": "good",
    "healthy": "good",
    "full": "good",
    "balanced": "good",
    "below target": "warn",
    "recruiting": "warn",
    "concern": "warn",
    "under-allocated": "warn",
    "at risk": "bad",
    "over-allocated": "bad",
    "cancelled": "bad",
    "no data": "muted",
    "sessional": "muted",
    "archived": "muted",
    "no capacity set": "muted",
}


def tone_for(band: str) -> str:
    return BAND_TONE.get(band, "plain")


def fg(tone: str) -> str:
    return TONE.get(tone, "")


# ── Formatting ──────────────────────────────────────────────────────────────

def pct(value: float | None, dash: str = "—") -> str:
    return f"{value:.1f}%" if value is not None else dash


def money(value: float | None, dash: str = "—") -> str:
    return f"£{value:,.2f}" if value is not None else dash


def when(value: date | str | None, dash: str = "—") -> str:
    if not value:
        return dash
    return value.isoformat() if isinstance(value, date) else str(value)


def yes_no(value: Any) -> str:
    return "Yes" if value else "No"


# ── Layout ──────────────────────────────────────────────────────────────────

def clear(frame: tk.Misc | None) -> None:
    """Remove every child of a frame."""
    if frame is None:
        return
    for child in frame.winfo_children():
        child.destroy()


def page_header(parent: tk.Misc, title: str, subtitle: str = "",
                actions: Sequence[tuple[str, Callable[[], None]]] = ()) -> ttk.Frame:
    """A title, an optional subtitle, and right-aligned action buttons."""
    header = ttk.Frame(parent)
    header.pack(fill="x", pady=(0, 10))
    header.columnconfigure(0, weight=1)

    ttk.Label(header, text=title, font=("", 16, "bold")).grid(row=0, column=0, sticky="w")
    if subtitle:
        ttk.Label(header, text=subtitle, foreground=TONE["muted"]).grid(
            row=1, column=0, sticky="w", pady=(2, 0))

    if actions:
        bar = ttk.Frame(header)
        bar.grid(row=0, column=1, rowspan=2, sticky="e")
        for label, command in actions:
            ttk.Button(bar, text=label, command=command).pack(side="left", padx=(6, 0))
    return header


def kpi_row(parent: tk.Misc,
            tiles: Sequence[tuple[str, str, str, str]]) -> ttk.Frame:
    """A row of ``(label, value, hint, tone)`` tiles sharing the width."""
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(0, 12))
    for i, (label, value, hint, tone) in enumerate(tiles):
        row.columnconfigure(i, weight=1, uniform="kpi")
        tile = ttk.LabelFrame(row, padding=10)
        tile.grid(row=0, column=i, padx=3, sticky="nsew")
        ttk.Label(tile, text=label, foreground=TONE["muted"]).pack(anchor="w")
        ttk.Label(tile, text=value, font=("", 19, "bold"),
                  foreground=fg(tone)).pack(anchor="w", pady=(2, 0))
        ttk.Label(tile, text=hint, foreground=TONE["muted"],
                  font=("", 9), wraplength=190, justify="left").pack(anchor="w", pady=(2, 0))
    return row


def kv_panel(parent: tk.Misc, title: str,
             rows: Sequence[tuple[str, str] | tuple[str, str, str]]) -> ttk.LabelFrame:
    """A label/value panel. Rows may carry a third element naming a tone."""
    panel = ttk.LabelFrame(parent, text=title, padding=10)
    panel.columnconfigure(0, weight=1)
    for r, entry in enumerate(rows):
        label, value = entry[0], entry[1]
        tone = entry[2] if len(entry) > 2 else "plain"
        ttk.Label(panel, text=label, foreground=TONE["muted"]).grid(
            row=r, column=0, sticky="w", pady=2)
        ttk.Label(panel, text=value, font=("", 10, "bold"),
                  foreground=fg(tone)).grid(row=r, column=1, sticky="e", pady=2, padx=(12, 0))
    return panel


def button_bar(parent: tk.Misc,
               buttons: Sequence[tuple[str, Callable[[], None]]],
               side: str = "left") -> ttk.Frame:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(8, 0))
    for label, command in buttons:
        ttk.Button(bar, text=label, command=command).pack(side=side, padx=(0, 6))
    return bar


def empty_state(parent: tk.Misc, message: str) -> ttk.Label:
    label = ttk.Label(parent, text=message, foreground=TONE["muted"])
    label.pack(anchor="w", pady=12)
    return label


def scrollable(parent: tk.Misc) -> tuple[ttk.Frame, tk.Canvas]:
    """A vertically scrollable frame that fills ``parent``.

    Returns ``(inner, canvas)``; pack content into ``inner``.
    """
    outer = ttk.Frame(parent)
    outer.pack(fill="both", expand=True)
    canvas = tk.Canvas(outer, highlightthickness=0)
    bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)

    window = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>",
               lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
    canvas.configure(yscrollcommand=bar.set)
    canvas.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return inner, canvas


# ── Table ───────────────────────────────────────────────────────────────────

class DataTable:
    """A Treeview with headings, widths, sorting, scrollbars and row tones.

    Columns are ``(key, heading, width)`` or ``(key, heading, width, anchor)``.
    Rows are dicts keyed by the column keys; a ``_tone`` key colours the row.
    The original row object can be carried in ``_obj`` and read back from
    :meth:`selection`, which is how the windows get from a click to a model.
    """

    def __init__(self, parent: tk.Misc,
                 columns: Sequence[tuple],
                 *, height: int = 16,
                 on_double_click: Callable[[Any], None] | None = None,
                 selectmode: str = "browse"):
        self.columns = columns
        self._objects: dict[str, Any] = {}
        self._on_double_click = on_double_click

        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        self.frame = frame

        keys = [c[0] for c in columns]
        self.tree = ttk.Treeview(frame, columns=keys, show="headings",
                                 height=height, selectmode=selectmode)
        for spec in columns:
            key, heading, width = spec[0], spec[1], spec[2]
            anchor = spec[3] if len(spec) > 3 else "w"
            self.tree.heading(key, text=heading,
                              command=lambda k=key: self.sort_by(k))
            self.tree.column(key, width=width, anchor=anchor, stretch=True)

        vs = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        for tone, colour in TONE.items():
            if colour:
                self.tree.tag_configure(tone, foreground=colour)
        # Zebra striping makes a wide row easier to follow across the screen.
        self.tree.tag_configure("odd", background="#f4f6f8")

        if on_double_click is not None:
            self.tree.bind("<Double-1>", lambda _e: self._fire_double_click())
        self.tree.bind("<Return>", lambda _e: self._fire_double_click())

        self._rows: list[dict] = []
        self._sort_key: str | None = None
        self._sort_reverse = False

    # ── Data ───────────────────────────────────────────────────────────────

    def set_rows(self, rows: Sequence[dict]) -> None:
        self._rows = list(rows)
        self._render()

    def _render(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._objects.clear()
        for i, row in enumerate(self._rows):
            tags = []
            tone = row.get("_tone")
            if tone and TONE.get(tone):
                tags.append(tone)
            if i % 2:
                tags.append("odd")
            values = [row.get(c[0], "") for c in self.columns]
            item = self.tree.insert("", "end", values=values, tags=tuple(tags))
            if "_obj" in row:
                self._objects[item] = row["_obj"]

    def sort_by(self, key: str) -> None:
        """Sort by a column, flipping direction when it is already sorted."""
        if self._sort_key == key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_key, self._sort_reverse = key, False

        def sort_value(row: dict):
            value = row.get(key, "")
            # Sort numerically where the column holds numbers formatted for
            # display ("92.4%", "£1,204.00"), so 100 doesn't sort before 20.
            if isinstance(value, (int, float)):
                return (0, value)
            text = str(value).replace("£", "").replace("%", "").replace(",", "").strip()
            try:
                return (0, float(text))
            except ValueError:
                return (1, str(value).lower())

        self._rows.sort(key=sort_value, reverse=self._sort_reverse)
        self._render()

    # ── Selection ──────────────────────────────────────────────────────────

    def selection(self) -> Any | None:
        """The object behind the selected row, or None."""
        items = self.tree.selection()
        return self._objects.get(items[0]) if items else None

    def selections(self) -> list[Any]:
        return [self._objects[i] for i in self.tree.selection() if i in self._objects]

    def _fire_double_click(self) -> None:
        if self._on_double_click is None:
            return
        selected = self.selection()
        if selected is not None:
            self._on_double_click(selected)

    def require_selection(self, what: str = "a row") -> Any | None:
        """Return the selection, or warn and return None."""
        selected = self.selection()
        if selected is None:
            messagebox.showinfo("Nothing selected", f"Select {what} first.",
                                parent=self.tree)
        return selected

    @property
    def count(self) -> int:
        return len(self._rows)


# ── Filter bar ──────────────────────────────────────────────────────────────

class FilterBar:
    """A search box plus labelled dropdowns, with Apply / Clear.

    Filters are ``(key, label, values)``; a blank first option means "any".
    :meth:`values` returns ``{key: selection}`` with blanks omitted, ready to
    splat into a service call.
    """

    def __init__(self, parent: tk.Misc, on_change: Callable[[], None],
                 *, search: bool = True,
                 filters: Sequence[tuple[str, str, Sequence[str]]] = (),
                 search_label: str = "Search"):
        self.on_change = on_change
        self._vars: dict[str, tk.StringVar] = {}
        self._search_var: tk.StringVar | None = None

        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 8))
        self.frame = bar

        if search:
            ttk.Label(bar, text=f"{search_label}:").pack(side="left")
            self._search_var = tk.StringVar()
            entry = ttk.Entry(bar, textvariable=self._search_var, width=24)
            entry.pack(side="left", padx=(4, 12))
            entry.bind("<Return>", lambda _e: on_change())
            self.search_entry = entry

        for key, label, values in filters:
            ttk.Label(bar, text=f"{label}:").pack(side="left")
            var = tk.StringVar()
            options = ["", *values]
            combo = ttk.Combobox(bar, textvariable=var, values=options,
                                 state="readonly", width=max(10, min(24, _widest(options))))
            combo.current(0)
            combo.pack(side="left", padx=(4, 12))
            combo.bind("<<ComboboxSelected>>", lambda _e: on_change())
            self._vars[key] = var

        ttk.Button(bar, text="Apply", command=on_change).pack(side="left")
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="left", padx=(6, 0))

        self.count_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.count_var,
                  foreground=TONE["muted"]).pack(side="right")

    def clear(self) -> None:
        if self._search_var is not None:
            self._search_var.set("")
        for var in self._vars.values():
            var.set("")
        self.on_change()

    @property
    def query(self) -> str:
        return self._search_var.get().strip() if self._search_var else ""

    def values(self) -> dict[str, str]:
        return {key: var.get() for key, var in self._vars.items() if var.get()}

    def set_count(self, n: int, noun: str = "row") -> None:
        self.count_var.set(f"{n} {noun}{'' if n == 1 else 's'}")


def _widest(options: Sequence[str]) -> int:
    return max((len(o) for o in options), default=10)


# ── Modal form ──────────────────────────────────────────────────────────────

class FormDialog:
    """A modal form built from field specs; returns a dict or None.

    Each field is ``(key, label, kind, options)`` where ``kind`` is one of
    ``text``, ``multiline``, ``choice``, ``int``, ``float``, ``date``, ``bool``.
    ``options`` supplies the choices for ``choice`` and the initial value for
    everything else via ``initial``.

    Numeric and date fields are converted before the dialog closes, so a caller
    never has to re-parse — and a bad value keeps the dialog open with the
    problem named rather than raising later.
    """

    def __init__(self, parent: tk.Misc, title: str,
                 fields: Sequence[tuple],
                 *, initial: dict | None = None,
                 submit_label: str = "Save",
                 width: int = 46):
        self.result: dict | None = None
        self._fields = fields
        self._vars: dict[str, Any] = {}
        self._widgets: dict[str, tk.Misc] = {}
        initial = initial or {}

        master = getattr(parent, "root", parent)
        self.win = tk.Toplevel(master)
        self.win.title(title)
        self.win.transient(master)
        self.win.resizable(False, False)

        body = ttk.Frame(self.win, padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        for r, spec in enumerate(fields):
            key, label, kind = spec[0], spec[1], spec[2]
            options = spec[3] if len(spec) > 3 else None
            ttk.Label(body, text=label).grid(row=r, column=0, sticky="nw",
                                             pady=4, padx=(0, 12))
            value = initial.get(key)
            widget = self._build_field(body, key, kind, options, value, width)
            widget.grid(row=r, column=1, sticky="ew", pady=4)
            self._widgets[key] = widget

        self.error_var = tk.StringVar()
        ttk.Label(body, textvariable=self.error_var, foreground=TONE["bad"],
                  wraplength=width * 8).grid(row=len(fields), column=0, columnspan=2,
                                             sticky="w", pady=(8, 0))

        actions = ttk.Frame(body)
        actions.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="Cancel", command=self.win.destroy).pack(side="right")
        ttk.Button(actions, text=submit_label, command=self._submit).pack(
            side="right", padx=(0, 8))

        self.win.bind("<Return>", lambda _e: self._submit())
        self.win.bind("<Escape>", lambda _e: self.win.destroy())
        _centre(self.win, master)
        self.win.grab_set()
        if fields:
            first = self._widgets[fields[0][0]]
            try:
                first.focus_set()
            except tk.TclError:
                pass
        self.win.wait_window()

    def _build_field(self, body, key, kind, options, value, width):
        if kind == "multiline":
            widget = tk.Text(body, width=width, height=4, wrap="word")
            if value:
                widget.insert("1.0", str(value))
            self._vars[key] = widget
            return widget
        if kind == "bool":
            var = tk.BooleanVar(value=bool(value))
            self._vars[key] = var
            return ttk.Checkbutton(body, variable=var)
        if kind == "choice":
            var = tk.StringVar(value=str(value) if value is not None else "")
            self._vars[key] = var
            values = list(options or [])
            combo = ttk.Combobox(body, textvariable=var, values=values,
                                 state="readonly", width=width - 2)
            if value in values:
                combo.set(str(value))
            elif values:
                combo.current(0)
            return combo
        var = tk.StringVar(value="" if value is None else str(value))
        self._vars[key] = var
        entry = ttk.Entry(body, textvariable=var, width=width)
        if kind == "date":
            entry.configure(width=width)
        return entry

    def _submit(self) -> None:
        collected: dict[str, Any] = {}
        for spec in self._fields:
            key, label, kind = spec[0], spec[1], spec[2]
            holder = self._vars[key]
            if kind == "multiline":
                raw = holder.get("1.0", "end").strip()
            elif kind == "bool":
                collected[key] = bool(holder.get())
                continue
            else:
                raw = holder.get().strip()

            if kind in ("int", "float") and raw:
                try:
                    collected[key] = int(raw) if kind == "int" else float(raw)
                except ValueError:
                    self.error_var.set(f"{label} must be a number.")
                    return
            elif kind in ("int", "float"):
                collected[key] = 0 if kind == "int" else 0.0
            elif kind == "date" and raw:
                try:
                    collected[key] = date.fromisoformat(raw)
                except ValueError:
                    self.error_var.set(f"{label} must be a date as YYYY-MM-DD.")
                    return
            elif kind == "date":
                collected[key] = None
            else:
                collected[key] = raw
        self.result = collected
        self.win.destroy()


def _centre(win: tk.Misc, parent: tk.Misc) -> None:
    win.update_idletasks()
    try:
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
    except tk.TclError:
        return
    w, h = win.winfo_width(), win.winfo_height()
    win.geometry(f"+{px + max(0, (pw - w) // 2)}+{py + max(0, (ph - h) // 3)}")


def ask(parent, title: str, fields: Sequence[tuple], **kwargs) -> dict | None:
    """Open a :class:`FormDialog` and return its result."""
    return FormDialog(parent, title, fields, **kwargs).result


def confirm(parent, title: str, message: str) -> bool:
    return messagebox.askyesno(title, message, parent=getattr(parent, "root", parent))


def warn(parent, title: str, message: str) -> None:
    messagebox.showwarning(title, message, parent=getattr(parent, "root", parent))


def error(parent, title: str, message: str) -> None:
    messagebox.showerror(title, message, parent=getattr(parent, "root", parent))


def info(parent, title: str, message: str) -> None:
    messagebox.showinfo(title, message, parent=getattr(parent, "root", parent))


def show_text(parent, title: str, body: str, *, width: int = 90,
              height: int = 28) -> None:
    """A read-only scrollable text window — used for profiles and briefs."""
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master)
    win.title(title)
    win.transient(master)
    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)
    text = tk.Text(frame, width=width, height=height, wrap="word")
    bar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=bar.set)
    text.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    text.insert("1.0", body)
    text.configure(state="disabled")
    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))
    _centre(win, master)


__all__ = [
    "BAND_TONE",
    "TONE",
    "DataTable",
    "FilterBar",
    "FormDialog",
    "ask",
    "button_bar",
    "clear",
    "confirm",
    "empty_state",
    "error",
    "fg",
    "info",
    "kpi_row",
    "kv_panel",
    "money",
    "page_header",
    "pct",
    "scrollable",
    "show_text",
    "tone_for",
    "warn",
    "when",
    "yes_no",
]
