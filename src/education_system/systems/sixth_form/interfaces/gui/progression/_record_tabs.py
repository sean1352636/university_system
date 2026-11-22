"""Shared Tk building blocks for the progression record screens.

The progression gap work (UCAS deadlines, Extra/Clearing, admissions
tests, student finance, Gatsby coverage, employer vetting, sustained
destinations) added a dozen small record screens that all have the same
shape: a filter bar, an action bar, a table, and a form dialog for a
row. Writing each one out longhand would be a dozen copies of the same
hundred lines, so they share these two pieces:

* :class:`RecordTable` — filter bar + action bar packed *before* the
  expanding table (the window-sizing convention), rows supplied by a
  callable that returns dicts.
* :func:`form_dialog` — a modal form built from field specs, which hands
  the values to a ``save`` callable and stays open with the error shown
  if that raises ``ValueError`` (every domain ``ValidationError`` is one).

Field specs are plain tuples ``(key, label, kind, choices)`` where
*kind* is ``text`` / ``multiline`` / ``longtext`` / ``choice`` / ``bool`` /
``date`` / ``number`` / ``readonly`` and *choices* is a sequence or a callable
returning one (only used by ``choice``).
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable, Iterable, Sequence

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel

logger = logging.getLogger(__name__)

FieldSpec = tuple  # (key, label, kind, choices)

_BOOL_TRUE = ("1", "y", "yes", "true", "t")


def _choices(spec: FieldSpec) -> list[str]:
    raw = spec[3] if len(spec) > 3 else ()
    if callable(raw):
        raw = raw()
    return [str(c) for c in (raw or ())]


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def form_dialog(parent: tk.Misc, title: str, fields: Sequence[FieldSpec],
                initial: dict[str, Any] | None,
                save: Callable[[dict[str, Any]], Any],
                after: Callable[[], None] | None = None,
                *, intro: str | None = None) -> None:
    """Open a modal form; ``save(values)`` does the write.

    ``values`` holds every non-readonly field as a string ("" when blank)
    except ``bool`` fields, which are real booleans. A ``ValueError`` from
    ``save`` is shown and the dialog stays open so nothing typed is lost.
    """
    initial = initial or {}
    top = tk.Toplevel(parent.winfo_toplevel())
    top.title(title)
    multiline = sum(1 for f in fields if f[2] == "multiline")
    longtext = sum(1 for f in fields if f[2] == "longtext")
    height = min(860, 160 + 34 * len(fields) + 90 * multiline + 200 * longtext)
    width = 820 if longtext else 620
    window_sizing.fit(top, f"{width}x{height}", (480, 300))
    top.transient(parent.winfo_toplevel())

    outer = ttk.Frame(top, padding=12)
    outer.pack(fill="both", expand=True)
    if intro:
        ttk.Label(outer, text=intro, foreground="#555", wraplength=560,
                  justify="left").pack(anchor="w", pady=(0, 8))

    # Buttons first so they stay on screen however tall the form gets.
    buttons = ttk.Frame(outer)
    buttons.pack(side="bottom", fill="x", pady=(10, 0))

    form = ttk.Frame(outer)
    form.pack(fill="both", expand=True)
    form.columnconfigure(1, weight=1)

    getters: dict[str, Callable[[], Any]] = {}
    for row, spec in enumerate(fields):
        key, label, kind = spec[0], spec[1], spec[2]
        ttk.Label(form, text=f"{label}:").grid(
            row=row, column=0, sticky="nw", padx=(0, 8), pady=3)
        value = initial.get(key)
        if kind in ("multiline", "longtext"):
            box = tk.Text(form, height=4 if kind == "multiline" else 11,
                          width=56 if kind == "multiline" else 80, wrap="word")
            box.insert("1.0", _fmt(value))
            box.grid(row=row, column=1, sticky="ew", pady=3)
            getters[key] = (lambda b=box: b.get("1.0", "end-1c").strip())
        elif kind == "bool":
            var = tk.BooleanVar(value=bool(value) and
                                str(value).lower() not in ("0", "no", "false"))
            ttk.Checkbutton(form, variable=var).grid(
                row=row, column=1, sticky="w", pady=3)
            getters[key] = var.get
        elif kind == "choice":
            var = tk.StringVar(value=_fmt(value))
            ttk.Combobox(form, textvariable=var, values=_choices(spec),
                         state="readonly", width=44).grid(
                row=row, column=1, sticky="w", pady=3)
            getters[key] = (lambda v=var: v.get().strip())
        elif kind == "readonly":
            ttk.Label(form, text=_fmt(value), foreground="#333",
                      wraplength=420, justify="left").grid(
                row=row, column=1, sticky="w", pady=3)
        else:
            var = tk.StringVar(value=_fmt(value))
            width = 14 if kind in ("date", "number") else 46
            ttk.Entry(form, textvariable=var, width=width).grid(
                row=row, column=1, sticky="w", pady=3)
            if kind == "date":
                ttk.Label(form, text="YYYY-MM-DD", foreground="#888").grid(
                    row=row, column=2, sticky="w", padx=4)
            getters[key] = (lambda v=var: v.get().strip())

    def do_save() -> None:
        values = {k: g() for k, g in getters.items()}
        try:
            save(values)
        except ValueError as exc:
            # A refusal the user can fix (bad date, missing field), not a
            # fault: a warning, so it is not logged with a traceback.
            messagebox.showwarning(title, str(exc), parent=top)
            return
        except Exception as exc:
            logger.exception("%s: save failed", title)
            messagebox.showerror(title, f"Unexpected error: {exc}", parent=top)
            return
        top.destroy()
        if after:
            after()

    ttk.Button(buttons, text="Save", command=do_save).pack(side="right")
    ttk.Button(buttons, text="Cancel", command=top.destroy).pack(
        side="right", padx=(0, 6))
    grab_when_viewable(top)


def show_text(parent: tk.Misc, title: str, text: str) -> None:
    """A read-only scrolling text window, for reports and detail views."""
    top = make_toplevel(parent.winfo_toplevel())
    top.title(title)
    window_sizing.fit(top, "820x620", (500, 360))
    bar = ttk.Frame(top, padding=(8, 8, 8, 0))
    bar.pack(fill="x")
    ttk.Button(bar, text="Close", command=top.destroy).pack(side="right")
    frame = ttk.Frame(top, padding=8)
    frame.pack(fill="both", expand=True)
    box = tk.Text(frame, wrap="word", font=("TkFixedFont", 10))
    sb = ttk.Scrollbar(frame, orient="vertical", command=box.yview)
    box.configure(yscrollcommand=sb.set)
    box.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    box.insert("1.0", text)
    box.configure(state="disabled")


def info(parent: tk.Misc, title: str, message: str) -> None:
    messagebox.showinfo(title, message, parent=parent.winfo_toplevel())


def warn(parent: tk.Misc, title: str, message: str) -> None:
    messagebox.showwarning(title, message, parent=parent.winfo_toplevel())


def error(parent: tk.Misc, title: str, message: str) -> None:
    messagebox.showerror(title, message, parent=parent.winfo_toplevel())


def confirm(parent: tk.Misc, title: str, message: str) -> bool:
    return messagebox.askyesno(title, message, parent=parent.winfo_toplevel())


class RecordTable:
    """Filter bar, action bar and a table of dict rows.

    ``load(filters)`` returns the rows; ``filters`` maps each filter key to
    its current string value. ``actions`` is a list of
    ``(label, handler)`` where ``handler(table)`` reads
    :meth:`selected` itself — so an action that needs no selection (New,
    Report) and one that does (Edit) look the same here.
    """

    def __init__(self, parent: tk.Misc,
                 columns: Sequence[tuple[str, str, int]],
                 load: Callable[[dict[str, str]], Iterable[dict[str, Any]]],
                 *, key: str,
                 actions: Sequence[tuple[str, Callable[["RecordTable"], None]]] = (),
                 filters: Sequence[FieldSpec] = (),
                 note: str | None = None,
                 tags: Callable[[dict[str, Any]], str | None] | None = None,
                 on_open: Callable[["RecordTable"], None] | None = None) -> None:
        self.parent = parent
        self.columns = list(columns)
        self._load = load
        self.key = key
        self._tags = tags
        self._rows: dict[str, dict[str, Any]] = {}
        self._filter_vars: dict[str, tk.StringVar] = {}

        if note:
            ttk.Label(parent, text=note, foreground="#555", wraplength=1000,
                      justify="left").pack(anchor="w", pady=(0, 6))

        fbar = ttk.Frame(parent)
        fbar.pack(fill="x", pady=(0, 4))
        for spec in filters:
            fkey, label, kind = spec[0], spec[1], spec[2]
            ttk.Label(fbar, text=f"{label}:").pack(side="left")
            var = tk.StringVar(value=str(spec[4]) if len(spec) > 4 else "")
            if kind == "choice":
                ttk.Combobox(fbar, textvariable=var,
                             values=[""] + _choices(spec), state="readonly",
                             width=18).pack(side="left", padx=(4, 10))
            else:
                ttk.Entry(fbar, textvariable=var, width=12).pack(
                    side="left", padx=(4, 10))
            self._filter_vars[fkey] = var
        ttk.Button(fbar, text="Refresh", command=self.refresh).pack(side="left")

        abar = ttk.Frame(parent)
        abar.pack(fill="x", pady=(0, 4))
        for label, handler in actions:
            ttk.Button(abar, text=label,
                       command=lambda h=handler: self._run(h)).pack(
                side="left", padx=(0, 4))

        self.status = ttk.Label(parent, text="", foreground="#555")
        self.status.pack(side="bottom", anchor="w", pady=(4, 0))

        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(holder, columns=[c[0] for c in self.columns],
                                 show="headings", height=16)
        for ckey, title, width in self.columns:
            self.tree.heading(ckey, text=title)
            self.tree.column(ckey, width=width, anchor="w")
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for tag, colour in (("bad", "#a33"), ("warn", "#7a5800"),
                            ("good", "#0d6b2a"), ("muted", "#777")):
            self.tree.tag_configure(tag, foreground=colour)
        if on_open:
            self.tree.bind("<Double-1>", lambda _e: self._run(on_open))
        self.refresh()

    def _run(self, handler: Callable[["RecordTable"], None]) -> None:
        try:
            handler(self)
        except ValueError as exc:
            # Handlers raise ValueError for things the user can put right
            # ("Select a row first.", "Not eligible yet"). Shown as a
            # warning: an error dialog raised inside this except block was
            # logged at ERROR with a full traceback, as if it had crashed.
            warn(self.parent, "Cannot do that", str(exc))
        except Exception as exc:
            logger.exception("Record action failed")
            error(self.parent, "Error", f"Unexpected error: {exc}")

    def filters(self) -> dict[str, str]:
        return {k: v.get().strip() for k, v in self._filter_vars.items()}

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        try:
            rows = list(self._load(self.filters()))
        except ValueError as exc:
            self.status.configure(text=str(exc), foreground="#a33")
            return
        except Exception as exc:
            logger.exception("Could not load records")
            self.status.configure(text=f"Could not load: {exc}",
                                  foreground="#a33")
            return
        for row in rows:
            iid = str(row[self.key])
            self._rows[iid] = row
            tag = self._tags(row) if self._tags else None
            self.tree.insert("", "end", iid=iid,
                             values=[_fmt(row.get(c[0])) for c in self.columns],
                             tags=(tag,) if tag else ())
        self.status.configure(text=f"{len(rows)} row(s)", foreground="#555")

    def selected(self) -> dict[str, Any] | None:
        sel = self.tree.selection()
        return self._rows.get(sel[0]) if sel else None

    def require(self) -> dict[str, Any]:
        row = self.selected()
        if row is None:
            raise ValueError("Select a row first.")
        return row


def student_choices() -> list[str]:
    """``"<id> — <name>"`` labels for every student, for choice fields."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    return [f"{s.student_id} — {s.full_name}" for s in _students.list_students()]


def student_id_of(label: str) -> str:
    """The id out of a :func:`student_choices` label (or a bare id)."""
    return (label or "").split(" — ")[0].strip()


def notebook_tab(nb: ttk.Notebook, title: str,
                 build: Callable[[ttk.Frame], None]) -> ttk.Frame:
    """Add a tab and build it, showing the error in the tab if it fails."""
    tab = ttk.Frame(nb, padding=8)
    nb.add(tab, text=title)
    try:
        build(tab)
    except Exception as exc:
        logger.exception("Could not build the %s tab", title)
        ttk.Label(tab, text=f"This tab could not be loaded: {exc}",
                  foreground="#a33", wraplength=700).pack(anchor="w")
    return tab


__all__ = ["FieldSpec", "RecordTable", "form_dialog", "show_text", "info",
           "error", "confirm", "student_choices", "student_id_of",
           "notebook_tab"]
