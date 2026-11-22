"""Shared Tkinter building blocks for the apprenticeships windows.

Thirty-four windows across five roles would otherwise be thirty-four
copies of the same Treeview wiring, the same modal-dialog scaffolding
and the same "catch ValidationError, show a messagebox" dance. The rest
of the platform duplicates that per module; at this window count the
duplication would be the dominant cost, so this system keeps one
toolkit and every window builds on it.

Nothing here knows about the domain. Windows pass column specs, field
specs and callables; this module turns them into widgets.
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable, Iterable, Sequence
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from education_system.platform import branding
from education_system.platform.delivery.gui import window_sizing
from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.application.workspace import preferences

logger = logging.getLogger(__name__)

WIN_GEOMETRY = config.WIN_GEOMETRY
WIN_MINSIZE = config.WIN_MINSIZE
EMPTY = config.EMPTY_CELL


# ═════════════════════════════════════════════════════════════════════
# Windows and layout
# ═════════════════════════════════════════════════════════════════════

def open_window(parent: Any, title: str, *, geometry: str | None = None) -> tk.Toplevel:
    """A standard top-level window.

    *parent* may be the main GUI object, a Tk widget, or None when a
    window is opened standalone — the same adapter the rest of the
    platform uses, so these windows drop into either context.
    """
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"{title} — {branding.SYSTEM_NAME}")
    # Asked for explicitly rather than left to the launcher's global clamp,
    # so a window opened standalone (a test, or `python -m`) is sized for
    # the screen too.
    window_sizing.fit(win, geometry or WIN_GEOMETRY, WIN_MINSIZE)
    return win


def heading(parent: tk.Misc, text: str, *, subtitle: str | None = None) -> ttk.Frame:
    """A screen title, optionally with a line of explanation under it."""
    frame = ttk.Frame(parent)
    frame.pack(fill="x", pady=(0, 10))
    ttk.Label(frame, text=text, font=("", 16, "bold")).pack(anchor="w")
    if subtitle:
        ttk.Label(
            frame, text=subtitle, foreground=config.MUTED_FG, wraplength=900,
        ).pack(anchor="w", pady=(2, 0))
    return frame


def section(parent: tk.Misc, text: str) -> ttk.LabelFrame:
    """A titled group box."""
    frame = ttk.LabelFrame(parent, text=text, padding=8)
    frame.pack(fill="x", pady=(0, 8))
    return frame


def scrollable(parent: tk.Misc) -> ttk.Frame:
    """A vertically scrolling container.

    Returns the inner frame to pack into. The mouse wheel is bound only
    while the pointer is inside, so several of these on one screen do
    not fight over the wheel.
    """
    outer = ttk.Frame(parent)
    outer.pack(fill="both", expand=True)
    canvas = tk.Canvas(outer, highlightthickness=0)
    bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)

    inner.bind(
        "<Configure>",
        lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
    )
    window = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
    canvas.configure(yscrollcommand=bar.set)
    canvas.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")

    def _wheel(event: Any) -> None:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _wheel))
    canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
    return inner


def button_bar(parent: tk.Misc, buttons: Sequence[tuple[str, Callable[[], None]]]) -> ttk.Frame:
    """A horizontal row of action buttons, anchored so it cannot be squeezed out.

    List screens build heading, filters, table, then actions — and pack
    fills the cavity in that order, so when the window is shorter than
    the content wants, the bar packed last is allocated nothing and the
    user sees a screen with no way to act on it. On a 1366x768 laptop
    that is every list screen in this system.

    So the bar inserts itself ahead of the first expanding sibling and
    anchors to the bottom. The table then absorbs the shortfall instead,
    which costs it visible rows it already has a scrollbar for. Losing
    rows you can scroll back is recoverable; losing the New button is not.
    """
    bar = ttk.Frame(parent)
    anchor = _first_expanding_slave(parent)
    if anchor is not None:
        bar.pack(fill="x", side="bottom", pady=(8, 4), before=anchor)
    else:
        bar.pack(fill="x", pady=(8, 4))
    for label, command in buttons:
        ttk.Button(bar, text=label, command=command).pack(side="left", padx=(0, 6))
    return bar


def _first_expanding_slave(parent: tk.Misc) -> tk.Misc | None:
    """The first already-packed child that grows to fill spare space."""
    try:
        slaves = parent.pack_slaves()
    except (AttributeError, tk.TclError):
        return None
    for slave in slaves:
        try:
            expand = slave.pack_info().get("expand")
        except (AttributeError, tk.TclError):
            continue
        # Tk reports expand as "1"/"0" or a bool depending on the version.
        if str(expand).lower() in ("1", "true", "yes"):
            return slave
    return None


# ═════════════════════════════════════════════════════════════════════
# Read-outs
# ═════════════════════════════════════════════════════════════════════

def kpi_row(parent: tk.Misc, kpis: Iterable[tuple[str, Any]], *, per_row: int = 6) -> ttk.Frame:
    """A row of headline figures.

    Wraps onto further rows past *per_row* so a narrow window does not
    squeeze the tiles into unreadable slivers.
    """
    holder = ttk.Frame(parent)
    holder.pack(fill="x", pady=(0, 10))
    row: ttk.Frame | None = None
    for index, (label, value) in enumerate(kpis):
        if index % per_row == 0:
            row = ttk.Frame(holder)
            row.pack(fill="x", pady=2)
        tile = ttk.Frame(row, relief="ridge", borderwidth=1, padding=8)
        tile.pack(side="left", fill="both", expand=True, padx=3)
        ttk.Label(tile, text=str(value), font=("", 18, "bold")).pack(anchor="w")
        ttk.Label(
            tile, text=label, foreground=config.MUTED_FG, font=("", 9),
        ).pack(anchor="w")
    return holder


def progress_row(
    parent: tk.Misc, label: str, percent: float, *, detail: str = "", rag: str | None = None
) -> ttk.Frame:
    """A labelled progress bar with an optional RAG-coloured caption."""
    frame = ttk.Frame(parent)
    frame.pack(fill="x", pady=3)
    top = ttk.Frame(frame)
    top.pack(fill="x")
    ttk.Label(top, text=label, font=("", 10, "bold")).pack(side="left")
    if detail:
        colour = {"Red": config.ERROR_FG, "Amber": "#a06000", "Green": "#0a6b2d"}.get(
            rag or "", config.MUTED_FG
        )
        ttk.Label(top, text=detail, foreground=colour).pack(side="right")
    bar = ttk.Progressbar(frame, maximum=100, value=max(0.0, min(100.0, percent)))
    bar.pack(fill="x", pady=(2, 0))
    return frame


def field_grid(parent: tk.Misc, pairs: Sequence[tuple[str, Any]], *, columns: int = 2) -> ttk.Frame:
    """A read-only label/value grid for detail panes."""
    grid = ttk.Frame(parent)
    grid.pack(fill="x", pady=(0, 8))
    for index, (label, value) in enumerate(pairs):
        row, col = divmod(index, columns)
        cell = ttk.Frame(grid)
        cell.grid(row=row, column=col, sticky="w", padx=(0, 24), pady=2)
        ttk.Label(
            cell, text=label, foreground=config.MUTED_FG, font=("", 9),
        ).pack(anchor="w")
        ttk.Label(cell, text=_display(value), font=("", 10)).pack(anchor="w")
    for col in range(columns):
        grid.columnconfigure(col, weight=1)
    return grid


def empty_state(parent: tk.Misc, message: str) -> ttk.Label:
    """What to show where a table would be if there is nothing in it."""
    label = ttk.Label(parent, text=message, foreground=config.MUTED_FG)
    label.pack(anchor="w", pady=12)
    return label


# ═════════════════════════════════════════════════════════════════════
# Tables
# ═════════════════════════════════════════════════════════════════════

class DataTable:
    """A Treeview with the wiring every list screen needs.

    *columns* is ``(key, heading, width)`` triples, optionally with a
    fourth ``anchor`` element. ``populate`` takes rows and a function
    mapping each to display values, plus the row's own identity — which
    is what selection returns, so callers get a domain id back rather
    than a widget handle.

    *height* is in rows. Leaving it unset takes the user's rows-per-table
    preference, which is what a screen's main list wants; a fixed value
    is for a pane *inside* a screen, where the surrounding content has
    already decided how much room there is to give it.
    """

    def __init__(
        self,
        parent: tk.Misc,
        columns: Sequence[tuple],
        *,
        height: int | None = None,
        on_activate: Callable[[Any], None] | None = None,
        multiselect: bool = False,
    ) -> None:
        if height is None:
            height = preferences.rows_per_page()
        self._columns = columns
        self._keys = [c[0] for c in columns]
        self._on_activate = on_activate

        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            holder,
            columns=self._keys,
            show="headings",
            height=height,
            selectmode="extended" if multiselect else "browse",
        )
        for spec in columns:
            key, title, width = spec[0], spec[1], spec[2]
            anchor = spec[3] if len(spec) > 3 else "w"
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor=anchor, stretch=True)

        bar = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

        for name, colour in config.STATUS_COLOURS.items():
            self.tree.tag_configure(_tag(name), background=colour)
        for name, colour in config.RAG_COLOURS.items():
            self.tree.tag_configure(_tag(name), background=colour)
        self.tree.tag_configure("muted", foreground=config.MUTED_FG)

        if on_activate is not None:
            self.tree.bind("<Double-1>", lambda _e: self._activate())
            self.tree.bind("<Return>", lambda _e: self._activate())

        self.count_var = tk.StringVar(value="")
        ttk.Label(
            parent, textvariable=self.count_var, foreground=config.MUTED_FG,
        ).pack(anchor="w", pady=(4, 0))

    def populate(
        self,
        rows: Sequence[Any],
        to_values: Callable[[Any], Sequence[Any]],
        *,
        identity: Callable[[Any], Any],
        tag: Callable[[Any], str | None] | None = None,
        noun: str = "row",
    ) -> None:
        """Replace the contents wholesale.

        Delete-then-insert rather than diffing: these tables are at most
        a few hundred rows and refresh on demand, so the simpler code
        wins and there is no flicker to speak of.
        """
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            values = [_display(v) for v in to_values(row)]
            tags = ()
            if tag is not None:
                marker = tag(row)
                if marker:
                    tags = (_tag(marker),)
            self.tree.insert("", "end", iid=str(identity(row)), values=values, tags=tags)
        plural = noun if len(rows) == 1 else f"{noun}s"
        self.count_var.set(f"{len(rows)} {plural}")

    def selected(self) -> str | None:
        """The selected row's identity, or None."""
        selection = self.tree.selection()
        return selection[0] if selection else None

    def selected_many(self) -> list[str]:
        return list(self.tree.selection())

    def selected_int(self) -> int | None:
        raw = self.selected()
        try:
            return int(raw) if raw is not None else None
        except ValueError:
            return None

    def require_selection(self, action: str = "continue") -> str | None:
        """The selection, or None having already told the user why not."""
        chosen = self.selected()
        if chosen is None:
            messagebox.showinfo("Nothing selected", f"Select a row first to {action}.")
        return chosen

    def require_selection_int(self, action: str = "continue") -> int | None:
        chosen = self.require_selection(action)
        try:
            return int(chosen) if chosen is not None else None
        except ValueError:
            return None

    def _activate(self) -> None:
        chosen = self.selected()
        if chosen is not None and self._on_activate is not None:
            self._on_activate(chosen)


# ═════════════════════════════════════════════════════════════════════
# Filters
# ═════════════════════════════════════════════════════════════════════

class FilterBar:
    """A row of filter controls that calls back on any change.

    *specs* are ``(key, label, kind, options)``; kind is "combo",
    "entry" or "check". ``values()`` returns the current state as a dict
    ready to splat into a service call.
    """

    def __init__(
        self,
        parent: tk.Misc,
        specs: Sequence[tuple],
        on_change: Callable[[], None],
    ) -> None:
        self._vars: dict[str, tk.Variable] = {}
        self._kinds: dict[str, str] = {}
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 8))

        for spec in specs:
            key, label, kind = spec[0], spec[1], spec[2]
            options = spec[3] if len(spec) > 3 else ()
            self._kinds[key] = kind
            if kind == "check":
                var: tk.Variable = tk.BooleanVar(value=False)
                ttk.Checkbutton(
                    bar, text=label, variable=var, command=on_change,
                ).pack(side="left", padx=(0, 10))
            else:
                ttk.Label(bar, text=f"{label}:").pack(side="left", padx=(0, 4))
                var = tk.StringVar(value="")
                if kind == "combo":
                    combo = ttk.Combobox(
                        bar, textvariable=var, state="readonly", width=18,
                        values=["All", *[str(o) for o in options]],
                    )
                    combo.set("All")
                    combo.pack(side="left", padx=(0, 10))
                    combo.bind("<<ComboboxSelected>>", lambda _e: on_change())
                else:
                    entry = ttk.Entry(bar, textvariable=var, width=24)
                    entry.pack(side="left", padx=(0, 10))
                    entry.bind("<Return>", lambda _e: on_change())
            self._vars[key] = var

        ttk.Button(bar, text="Refresh", command=on_change).pack(side="left")
        ttk.Button(bar, text="Clear", command=lambda: self.clear(on_change)).pack(
            side="left", padx=(6, 0)
        )

    def values(self) -> dict[str, Any]:
        """Current filter state, with "All" and blanks dropped.

        Omitting rather than passing None keeps the service signatures
        honest: a filter the user has not set is simply not applied.
        """
        out: dict[str, Any] = {}
        for key, var in self._vars.items():
            value = var.get()
            if self._kinds[key] == "check":
                if value:
                    out[key] = True
            elif value and value != "All":
                out[key] = value
        return out

    def clear(self, on_change: Callable[[], None] | None = None) -> None:
        for key, var in self._vars.items():
            var.set(False if self._kinds[key] == "check" else "")
            if self._kinds[key] == "combo":
                var.set("All")
        if on_change is not None:
            on_change()


# ═════════════════════════════════════════════════════════════════════
# Forms
# ═════════════════════════════════════════════════════════════════════

# More fields than this and the form scrolls inside its dialog.
_SCROLL_AFTER_FIELDS = 18


class FormDialog:
    """A modal create/edit form built from a field spec.

    *fields* are dicts: ``key``, ``label``, optional ``kind``
    ("entry" | "combo" | "text" | "check" | "date"), ``options``,
    ``value``, ``required``, ``help``.

    ``on_save`` receives the collected dict. Raising ``ValidationError``
    (or anything else) from it keeps the dialog open and shows the
    message, so the user does not lose what they typed — which is the
    whole reason saving goes through a callback rather than the caller
    reading values back after the dialog closes.
    """

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        fields: Sequence[dict[str, Any]],
        on_save: Callable[[dict[str, Any]], Any],
        *,
        intro: str | None = None,
        save_label: str = "Save",
    ) -> None:
        self._fields = fields
        self._on_save = on_save
        self._vars: dict[str, tk.Variable] = {}
        self._texts: dict[str, tk.Text] = {}
        self.result: Any = None
        self.saved = False
        # What the form held when Save succeeded, for callers that need a
        # field the save callback did not use (an "also do this" tick box).
        self.values_at_save: dict[str, Any] = {}

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.transient(parent.winfo_toplevel())
        self.win.resizable(True, False)
        self._build(title, intro, save_label)
        self.win.after_idle(self.win.grab_set)
        parent.winfo_toplevel().wait_window(self.win)

    def _build(self, title: str, intro: str | None, save_label: str) -> None:
        body = ttk.Frame(self.win, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=title, font=("", 13, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        row = 1
        if intro:
            ttk.Label(
                body, text=intro, foreground=config.MUTED_FG, wraplength=520,
            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
            row += 1

        # A long form (the apprentice record runs to thirty fields) scrolls
        # inside the dialog so the Save button stays on a 768-pixel screen.
        # Short forms are laid out exactly as before.
        form_row = row
        if len(self._fields) > _SCROLL_AFTER_FIELDS:
            form = self._scrolling_area(body, form_row)
            row = 0
        else:
            form = body

        for field in self._fields:
            key = field["key"]
            kind = field.get("kind", "entry")
            if kind == "section":
                ttk.Label(form, text=field["label"], font=("", 10, "bold")).grid(
                    row=row, column=0, columnspan=2, sticky="w", pady=(10, 2)
                )
                row += 1
                continue
            label = field["label"] + (" *" if field.get("required") else "")
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="ne", pady=4, padx=(0, 8))

            if kind == "text":
                widget = tk.Text(form, width=44, height=4, wrap="word")
                widget.insert("1.0", str(field.get("value") or ""))
                widget.grid(row=row, column=1, sticky="we", pady=4)
                self._texts[key] = widget
            elif kind == "check":
                var: tk.Variable = tk.BooleanVar(value=bool(field.get("value")))
                ttk.Checkbutton(form, variable=var).grid(row=row, column=1, sticky="w", pady=4)
                self._vars[key] = var
            elif kind == "combo":
                var = tk.StringVar(value=str(field.get("value") or ""))
                options = [str(o) for o in field.get("options", ())]
                combo = ttk.Combobox(
                    form, textvariable=var, values=options, width=42,
                    state="readonly" if not field.get("editable") else "normal",
                )
                combo.grid(row=row, column=1, sticky="we", pady=4)
                self._vars[key] = var
            else:
                var = tk.StringVar(value=str(field.get("value") or ""))
                ttk.Entry(form, textvariable=var, width=45).grid(
                    row=row, column=1, sticky="we", pady=4
                )
                self._vars[key] = var

            hint = field.get("help")
            if hint:
                row += 1
                ttk.Label(
                    form, text=hint, foreground=config.MUTED_FG, font=("", 8),
                ).grid(row=row, column=1, sticky="w")
            row += 1

        form.columnconfigure(1, weight=1)
        if form is not body:
            row = form_row + 1
        body.columnconfigure(1, weight=1)
        self._error = ttk.Label(body, text="", foreground=config.ERROR_FG, wraplength=520)
        self._error.grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
        row += 1

        bar = ttk.Frame(body)
        bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(bar, text="Cancel", command=self.win.destroy).pack(side="right")
        ttk.Button(bar, text=save_label, command=self._save).pack(side="right", padx=(0, 6))
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _scrolling_area(self, body: ttk.Frame, row: int) -> ttk.Frame:
        """A scrolling frame in grid *row* of *body*, sized to fit the screen."""
        holder = ttk.Frame(body)
        holder.grid(row=row, column=0, columnspan=2, sticky="nsew")
        body.rowconfigure(row, weight=1)
        canvas = tk.Canvas(holder, highlightthickness=0, width=600)
        bar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, padding=(0, 0, 12, 0))
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def resize(_event: Any = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            # As tall as the form needs, but never taller than the screen
            # leaves room for once the title and buttons are drawn.
            room = max(240, self.win.winfo_screenheight() - 260)
            canvas.configure(height=min(inner.winfo_reqheight(), room),
                             width=max(600, inner.winfo_reqwidth()))

        inner.bind("<Configure>", resize)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

        def wheel(event: Any) -> None:
            step = -1 if getattr(event, "num", None) == 4 else 1 if getattr(event, "num", None) == 5 \
                else int(-1 * (event.delta / 120))
            canvas.yview_scroll(step, "units")

        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.win.bind(sequence, wheel)
        self.win.resizable(True, True)
        return inner

    def values(self) -> dict[str, Any]:
        data: dict[str, Any] = {k: v.get() for k, v in self._vars.items()}
        for key, widget in self._texts.items():
            data[key] = widget.get("1.0", "end").strip()
        return data

    def _save(self) -> None:
        values = self.values()
        try:
            self.result = self._on_save(values)
        except Exception as exc:
            # Stay open with the message inline. Losing a half-filled
            # form to a modal error box is the single most annoying
            # thing a data-entry screen can do.
            self._error.config(text=str(exc))
            logger.debug("Form %s rejected", self.win.title(), exc_info=True)
            return
        self.values_at_save = values
        self.saved = True
        self.win.destroy()


# ═════════════════════════════════════════════════════════════════════
# Prompts and error handling
# ═════════════════════════════════════════════════════════════════════

def guard(action: Callable[[], Any], *, title: str = "Error") -> tuple[bool, Any]:
    """Run a service call, turning a refusal into a message box.

    Returns ``(ok, result)``. Validation errors and permission refusals
    are the user's business and shown verbatim; anything else is logged
    with a traceback and shown as an unexpected failure, because the
    message on an arbitrary exception is rarely fit to show anyone.
    """
    try:
        return True, action()
    except Exception as exc:
        _report(exc, title)
        return False, None


def _report(exc: Exception, title: str) -> None:
    from education_system.systems.apprenticeships.domain.apprentices.models import (
        ValidationError,
    )
    from education_system.systems.apprenticeships.application.security.access import PermissionDenied

    if isinstance(exc, PermissionDenied):
        messagebox.showwarning("Not permitted", str(exc))
        return
    if isinstance(exc, ValidationError):
        messagebox.showerror(title, str(exc))
        return
    logger.exception("Unexpected error in %s", title)
    messagebox.showerror(title, f"Unexpected error: {exc}")


def confirm(question: str, *, title: str = "Confirm") -> bool:
    return bool(messagebox.askyesno(title, question))


def ask_reason(prompt: str, *, title: str = "Reason") -> str | None:
    """Ask for a free-text reason. None means cancelled or left blank."""
    answer = simpledialog.askstring(title, prompt)
    if answer is None:
        return None
    answer = answer.strip()
    return answer or None


def inform(message: str, *, title: str = "Done") -> None:
    messagebox.showinfo(title, message)


def warn(message: str, *, title: str = "Not permitted") -> None:
    messagebox.showwarning(title, message)


# ═════════════════════════════════════════════════════════════════════
# Formatting
# ═════════════════════════════════════════════════════════════════════

def _display(value: Any) -> str:
    """Render a cell value, using an em dash for anything missing.

    The one place every table and detail cell passes through, which is
    why the date preference is applied here rather than at each call
    site — and why ``format_date`` has to leave anything that is not an
    ISO date exactly as it found it.
    """
    if value is None or value == "":
        return EMPTY
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return str(preferences.format_date(value))


def money(amount: float | None) -> str:
    if amount is None:
        return EMPTY
    return f"{config.CURRENCY_SYMBOL}{amount:,.2f}"


def percent(value: float | None) -> str:
    if value is None:
        return EMPTY
    return f"{value:.0f}%"


def _tag(name: str) -> str:
    """A Treeview tag name safe to use for any status or rating."""
    return "tag_" + "".join(ch if ch.isalnum() else "_" for ch in str(name).lower())
