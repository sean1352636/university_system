"""Shared Tk pieces for the university's record screens (research portal,
graduation, alumni office): one-transaction rule calls, the form dialog and
the list / detail / actions tab.

* :func:`call` runs one rule from ``university/application/research/`` in
  its own transaction. A refusal (``ValueError`` / ``PermissionError``)
  becomes an error dialog and ``None``; e-mails returned by a write are sent
  after the commit.
* :class:`FormDialog` is the one data-entry dialog (text, multiline, combo,
  date, tick box, staff picker).
* :class:`RecordTab` is a list on the left, the selected record on the
  right and the record's actions in a bar pinned to the bottom, so the
  buttons stay on screen at 1366×768.
"""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import messagebox, ttk

logger = logging.getLogger(__name__)

TITLE = "University"


def _looks_like_emails(result) -> bool:
    return isinstance(result, list) and bool(result) and all(
        isinstance(e, tuple) and len(e) == 3 and "@" in str(e[0]) for e in result)


def call(parent, fn, *args, write=False, quiet=False, **kwargs):
    """Run ``fn(conn, *args, **kwargs)``. ``None`` means it was refused or
    failed (already reported); a write that returns nothing gives ``True``."""
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    try:
        result = fn(conn, *args, **kwargs)
        if write:
            conn.commit()
    except (ValueError, PermissionError) as exc:
        conn.rollback()
        if not quiet:
            messagebox.showerror(TITLE, str(exc), parent=parent)
        return None
    except Exception as exc:
        conn.rollback()
        logger.exception("research portal action failed: %s", getattr(fn, "__name__", fn))
        if not quiet:
            messagebox.showerror(TITLE, f"That did not work: {exc}", parent=parent)
        return None
    finally:
        conn.close()
    if write:
        emails = result.get("emails") if isinstance(result, dict) else (
            result if _looks_like_emails(result) else None)
        if emails:
            send_emails(emails)
    return True if result is None else result


def send_emails(emails) -> int:
    """Best-effort delivery of ``(address, subject, body)`` tuples."""
    try:
        from education_system.systems.university.infrastructure.email import send_email
    except Exception:
        return 0
    sent = 0
    for address, subject, body in emails:
        try:
            send_email(recipient_email=address, subject=subject, body=body)
            sent += 1
        except Exception:
            continue
    return sent


def money(value) -> str:
    try:
        return f"£{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def nice(value) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("_", " ")


# ── trees ───────────────────────────────────────────────────────────────


def make_tree(parent, columns, height=12, pack=True):
    """``columns`` is ``[(key, heading, width), …]``. Returns the tree."""
    frame = ttk.Frame(parent)
    if pack:
        frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                        height=height, selectmode="browse")
    for key, heading, width in columns:
        tree.heading(key, text=heading)
        tree.column(key, width=width, minwidth=40, stretch=True)
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    tree.frame = frame
    return tree


def fill(tree, rows, iid, values):
    """Replace the tree's rows; ``iid(row)`` and ``values(row)`` pick them out."""
    tree.delete(*tree.get_children())
    for row in rows:
        tree.insert("", "end", iid=str(iid(row)), values=[nice(v) if v in (None, "") else v
                                                          for v in values(row)])


def selected(tree):
    sel = tree.selection()
    return sel[0] if sel else None


# ── the detail pane ─────────────────────────────────────────────────────


class Detail(ttk.Frame):
    """Read-only formatted text: headings, label/value pairs and tables."""

    def __init__(self, parent):
        super().__init__(parent)
        self.text = tk.Text(self, wrap="word", relief="flat", padx=10, pady=8,
                            font=("Segoe UI", 10), state="disabled", height=10)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("title", font=("Segoe UI", 13, "bold"), spacing3=6)
        self.text.tag_configure("heading", font=("Segoe UI", 10, "bold"), spacing1=10,
                                spacing3=2, foreground="#3c5a99")
        self.text.tag_configure("label", foreground="#555555")
        self.text.tag_configure("warn", foreground="#b0620a")
        self.text.tag_configure("bad", foreground="#b3261e")

    def clear(self, message=""):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if message:
            self.text.insert("end", message, ("label",))
        self.text.configure(state="disabled")

    def show(self, title, sections):
        """``sections``: ``[(heading, pairs | lines | str), …]`` where pairs
        are ``(label, value)`` tuples and lines plain strings."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", f"{title}\n", ("title",))
        for heading, body in sections:
            if heading:
                self.text.insert("end", f"{heading}\n", ("heading",))
            if isinstance(body, str):
                self.text.insert("end", f"{body}\n")
                continue
            for item in body or ["—"]:
                if isinstance(item, tuple):
                    label, value, *tag = item
                    self.text.insert("end", f"{label}: ", ("label",))
                    self.text.insert("end", f"{nice(value)}\n", tuple(tag))
                else:
                    self.text.insert("end", f"{item}\n")
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)


# ── the form dialog ─────────────────────────────────────────────────────


@dataclass
class Field:
    key: str
    label: str
    # text | multiline | combo | date | check | staff | number
    # | pick (dropdown of known values) | datepick (day / month / year dropdowns)
    kind: str = "text"
    choices: object = field(default_factory=list)   # values or (value, label) pairs; for
    #                                                 "pick" also a no-argument callable
    required: bool = False
    hint: str = ""
    filter: bool = False        # pick: type to narrow the list (long lists, e.g. students)
    depends_on: str = ""        # pick: key of the field this list depends on
    choices_for: object = None  # pick: callable(parent_value) -> pairs, run when it changes


def staff_choices(parent):
    """``[(username, "Name (Department)")]`` for staff pickers."""
    from education_system.systems.university.application.research import access as ra
    rows = call(parent, ra.staff_list, quiet=True) or []
    return [(r["username"], f"{r['name'] or r['username']} ({r['username']}"
             + (f", {r['department']}" if r["department"] else "") + ")") for r in rows]


class FormDialog(tk.Toplevel):
    """Modal form; ``result`` is a dict of the values, or ``None`` if cancelled."""

    def __init__(self, parent, title, fields, values=None, columns=1):
        super().__init__(parent)
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.resizable(True, True)
        self.result = None
        self._fields = fields
        self._vars = {}
        self._labels = {}
        self._widgets = {}
        self._dependents = {}
        values = values or {}
        buttons = ttk.Frame(self, padding=(10, 6))
        buttons.pack(side="bottom", fill="x")          # packed first: always visible
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(buttons, text="Save", command=self._save).pack(side="right", padx=4)
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        for n, f in enumerate(fields):
            row, col = divmod(n, columns) if f.kind != "multiline" else (n, 0)
            self._build(body, f, values.get(f.key), row, col * 2, columns)
        for c in range(columns):
            body.columnconfigure(c * 2 + 1, weight=1)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        top = parent.winfo_toplevel()
        height = min(self.winfo_reqheight(), max(top.winfo_screenheight() - 120, 400))
        self.geometry(f"{max(self.winfo_reqwidth(), 520)}x{height}")
        self.grab_set()

    @staticmethod
    def _pairs(choices):
        if callable(choices):
            choices = choices() or []
        return [(c, c) if not isinstance(c, tuple) else (c[0], c[1]) for c in choices]

    def _build_pick(self, body, f, value):
        """A dropdown of known values. ``filter`` makes it type-to-narrow;
        ``depends_on`` refreshes it from ``choices_for`` when that field
        changes. The value saved is the item's value, not its label."""
        parent_value = None
        if f.depends_on and f.choices_for is not None:
            parent_value = self._current(f.depends_on)
            pairs = self._pairs(f.choices_for(parent_value))
        else:
            pairs = self._pairs(f.choices)
        self._labels[f.key] = pairs
        shown = next((label for v, label in pairs if str(v) == str(value)),
                     "" if value in (None, "") else str(value))
        var = tk.StringVar(value=shown)
        widget = ttk.Combobox(body, textvariable=var, values=[p[1] for p in pairs], width=40,
                              state="normal" if f.filter else "readonly",
                              height=min(20, max(3, len(pairs))))
        self._vars[f.key] = var
        self._widgets[f.key] = widget
        if f.filter:
            def narrow(_event=None, key=f.key):
                typed = self._vars[key].get().strip().lower()
                labels = [lbl for _v, lbl in self._labels[key]]
                self._widgets[key].configure(
                    values=[lbl for lbl in labels if typed in lbl.lower()] if typed else labels)
            widget.bind("<KeyRelease>", narrow)
            widget.bind("<FocusIn>", narrow)
        if f.depends_on:
            self._dependents.setdefault(f.depends_on, []).append(f)
        return widget

    def _current(self, key):
        """The value (not label) a field holds right now."""
        f = next((x for x in self._fields if x.key == key), None)
        if f is None or key not in self._vars:
            return None
        try:
            return self._value(f, strict=False)
        except ValueError:
            return None

    def _refresh_dependents(self, key):
        for f in self._dependents.get(key, []):
            pairs = self._pairs(f.choices_for(self._current(key))) if f.choices_for else []
            self._labels[f.key] = pairs
            labels = [p[1] for p in pairs]
            self._widgets[f.key].configure(values=labels)
            if self._vars[f.key].get() not in labels:
                self._vars[f.key].set("")
            self._refresh_dependents(f.key)

    def _build(self, body, f, value, row, col, columns):
        ttk.Label(body, text=f.label + (" *" if f.required else "")).grid(
            row=row, column=col, sticky="nw", padx=(0, 6), pady=3)
        span = columns * 2 - 1 if f.kind == "multiline" else 1
        if f.kind == "pick":
            widget = self._build_pick(body, f, value)
        elif f.kind == "datepick":
            from education_system.platform.delivery.gui.date_picker import DatePicker
            widget = DatePicker(body, value=str(value) if value else None)
            self._vars[f.key] = widget
        elif f.kind == "multiline":
            widget = tk.Text(body, height=4, width=60, wrap="word", font=("Segoe UI", 10))
            widget.insert("1.0", "" if value is None else str(value))
            self._vars[f.key] = widget
        elif f.kind == "check":
            var = tk.BooleanVar(value=bool(value))
            widget = ttk.Checkbutton(body, variable=var)
            self._vars[f.key] = var
        elif f.kind in ("combo", "staff"):
            pairs = [(c, c) if not isinstance(c, tuple) else c for c in f.choices]
            self._labels[f.key] = pairs
            shown = next((label for v, label in pairs if str(v) == str(value)),
                         "" if value is None else str(value))
            var = tk.StringVar(value=shown)
            widget = ttk.Combobox(body, textvariable=var, values=[p[1] for p in pairs],
                                  width=40, state="normal" if f.kind == "staff" else "readonly")
            self._vars[f.key] = var
        else:
            var = tk.StringVar(value="" if value is None else str(value))
            widget = ttk.Entry(body, textvariable=var, width=42)
            self._vars[f.key] = var
        widget.grid(row=row, column=col + 1, columnspan=span, sticky="ew", pady=3)
        if f.kind in ("pick", "combo", "staff"):
            self._widgets.setdefault(f.key, widget)
            widget.bind("<<ComboboxSelected>>",
                        lambda _e, key=f.key: self._refresh_dependents(key), add="+")
            widget.bind("<FocusOut>",
                        lambda _e, key=f.key: self._refresh_dependents(key), add="+")
        if f.hint or f.kind == "date":
            ttk.Label(body, text=f.hint or "YYYY-MM-DD", foreground="#777777").grid(
                row=row, column=col + 2 if span == 1 and columns == 1 else col + 1,
                sticky="w" if columns == 1 else "e", padx=4)

    def _value(self, f, strict=True):
        holder = self._vars[f.key]
        if f.kind == "multiline":
            return holder.get("1.0", "end").strip()
        if f.kind == "check":
            return bool(holder.get())
        if f.kind == "datepick":
            return holder.get()
        text = holder.get().strip()
        if f.kind == "pick":
            if not text:
                return ""
            for value, label in self._labels.get(f.key, []):
                if text == label or text.lower() == str(value).lower():
                    return value
            if strict:
                raise ValueError(f"Choose {f.label.lower()} from the list")
            return None
        if f.kind in ("combo", "staff"):
            for value, label in self._labels[f.key]:
                if text == label:
                    return value
            if f.kind == "staff" and "(" in text and text.endswith(")"):
                return text[text.rindex("(") + 1:-1].split(",")[0].strip()
        if f.kind == "number" and text:
            try:
                return float(text)
            except ValueError:
                raise ValueError(f"{f.label} must be a number") from None
        return text

    def _save(self):
        try:
            values = {f.key: self._value(f) for f in self._fields}
        except ValueError as exc:
            messagebox.showerror(TITLE, str(exc), parent=self)
            return
        missing = [f.label for f in self._fields if f.required and values[f.key] in ("", None)]
        if missing:
            messagebox.showerror(TITLE, "Please fill in: " + ", ".join(missing), parent=self)
            return
        self.result = values
        self.destroy()


def ask(parent, title, fields, values=None, columns=1):
    dlg = FormDialog(parent, title, fields, values, columns)
    parent.wait_window(dlg)
    return dlg.result


def ask_pick(parent, title, label, choices, *, filter=True, required=True, value=None):
    """One dropdown in a small dialog; returns the chosen value or ``None``."""
    values = ask(parent, title, [Field("pick", label, "pick", choices, required=required,
                                       filter=filter)], {"pick": value} if value else None)
    return None if values is None else values["pick"]


def ask_text(parent, title, label, required=True, multiline=True):
    result = ask(parent, title, [Field("text", label, "multiline" if multiline else "text",
                                       required=required)])
    return None if result is None else result["text"]


def confirm(parent, message) -> bool:
    return messagebox.askyesno(TITLE, message, parent=parent)


def info(parent, message) -> None:
    messagebox.showinfo(TITLE, message, parent=parent)


# ── the list / detail / actions tab ─────────────────────────────────────


class RecordTab(ttk.Frame):
    """Subclasses set ``columns`` and ``statuses`` and implement
    ``load(conn, search, status)``, ``values(row)``, ``row_id(row)``,
    ``fetch(conn, record_id)``, ``render(record)`` and ``actions(record)``
    (``[(label, command)]``); ``new_actions()`` adds buttons beside the search
    box. ``self.who`` is the signed-in :class:`Researcher`; ``self.write(rule,
    *args)`` runs a write rule (``rule(conn, *args)``) and reloads."""

    columns: list = []
    statuses: tuple = ()
    list_width = 560

    def __init__(self, parent, portal):
        super().__init__(parent)
        self.portal = portal
        self.who = portal.who
        self.record = None
        self.current_id = None
        self._rows = {}
        top = ttk.Frame(self, padding=(6, 6, 6, 2))
        top.pack(side="top", fill="x")
        ttk.Label(top, text="Search").pack(side="left")
        self.search = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.search, width=24)
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda _e: self.refresh())
        if self.statuses:
            ttk.Label(top, text="Status").pack(side="left", padx=(8, 0))
            self.status = tk.StringVar(value="")
            box = ttk.Combobox(top, textvariable=self.status, values=("", *self.statuses),
                               width=18, state="readonly")
            box.pack(side="left", padx=4)
            box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        else:
            self.status = tk.StringVar(value="")
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=4)
        for label, command in self.new_actions():
            ttk.Button(top, text=label, command=command).pack(side="left", padx=4)
        self.extra_toolbar(top)
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=6, pady=4)
        left = ttk.Frame(panes, width=self.list_width)
        right = ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        self.count = ttk.Label(left, text="")
        self.count.pack(side="bottom", anchor="w")
        self.tree = make_tree(left, self.columns)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._selected())
        self.actions_bar = ttk.Frame(right, padding=(0, 4))
        self.actions_bar.pack(side="bottom", fill="x")      # packed before the detail
        self.detail = Detail(right)
        self.detail.pack(fill="both", expand=True)
        self.detail.clear("Select a record on the left.")

    # subclass hooks
    def new_actions(self):
        return []

    def extra_toolbar(self, bar):
        pass

    def load(self, conn, search, status):
        return []

    def values(self, row):
        return []

    def row_id(self, row):
        return row.get("id")

    def fetch(self, conn, record_id):
        return None

    def render(self, record):
        self.detail.show(str(record), [])

    def actions(self, record):
        return []

    # behaviour
    def refresh(self):
        rows = call(self, self.load, self.search.get().strip() or None,
                    self.status.get() or None) or []
        self._rows = {str(self.row_id(r)): r for r in rows}
        fill(self.tree, rows, self.row_id, self.values)
        self.count.configure(text=f"{len(rows)} record(s)")
        if self.current_id and str(self.current_id) in self._rows:
            self.tree.selection_set(str(self.current_id))
            self.tree.see(str(self.current_id))
        else:
            self.current_id = None
            self.record = None
            self.detail.clear("Select a record on the left.")
            self._set_actions([])

    def open_record(self, record_id):
        self.current_id = record_id
        self.refresh()
        self._show(record_id)       # now, not on the later selection event

    def _selected(self):
        rid = selected(self.tree)
        if rid is not None:
            self.current_id = rid
            self._show(rid)

    def _show(self, record_id):
        record = call(self, self.fetch, record_id)
        if record is None:
            return
        self.record = record
        self.render(record)
        self._set_actions(self.actions(record))

    def reload(self):
        """After a write: refresh the list and the open record."""
        self.refresh()
        if self.current_id is not None:
            self._show(self.current_id)
        self.portal.changed()

    def _set_actions(self, actions):
        for child in self.actions_bar.winfo_children():
            child.destroy()
        row = None
        for n, (label, command) in enumerate(actions):
            if n % 5 == 0:            # wrap so buttons never run off the side
                row = ttk.Frame(self.actions_bar)
                row.pack(side="top", fill="x")
            ttk.Button(row, text=label, command=command).pack(side="left", padx=3, pady=2)

    def write(self, fn, *args, done=None, **kwargs):
        """Run a write rule; on success reload and optionally say ``done``."""
        result = call(self, fn, *args, write=True, **kwargs)
        if result is not None:
            self.reload()
            if done:
                info(self, done)
        return result
