"""The two screens every alternative provision area shares: a record list and a record form.

A page is ``draw_records(parent, record_type, ...)``: heading, search box,
a filter per ``RecordType.filters`` field, Add / Edit / Delete / Export,
and a sortable table. Double-click edits (or opens, if ``on_open`` is
given). Rows whose computed columns say "overdue" are shown in red.

The form is built from the record type's fields, so a field added to a
record type appears in its form, list and CSV with no screen code.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
)
from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.core.access import Principal
from education_system.systems.alternative_provision.core.records import Field, RecordType

logger = logging.getLogger(__name__)

ALL = "All"
OVERDUE_FG = "#b00020"
MUTED = "#666"


def heading(parent: tk.Misc, title: str, subtitle: str = "") -> ttk.Frame:
    box = ttk.Frame(parent)
    box.pack(fill="x", pady=(0, 8))
    ttk.Label(box, text=title, font=("", 16, "bold")).pack(anchor="w")
    if subtitle:
        ttk.Label(box, text=subtitle, foreground=MUTED, wraplength=900,
                  justify="left").pack(anchor="w", pady=(2, 0))
    return box


def make_tree(parent: tk.Misc, columns: list[tuple[str, str, int]],
              height: int = 18) -> ttk.Treeview:
    """A Treeview with a scrollbar; *columns* are ``(id, heading, width)``.
    Clicking a heading sorts by it."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                        height=height, selectmode="browse")
    for cid, text, width in columns:
        tree.heading(cid, text=text, command=lambda c=cid: _sort(tree, c, False))
        tree.column(cid, width=width, anchor="w", stretch=True)
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    tree.tag_configure("overdue", foreground=OVERDUE_FG)
    tree.tag_configure("muted", foreground="#999")
    return tree


def _sort_key(text: str) -> Any:
    try:  # DD/MM/YYYY sorts by date
        d, m, y = text.split("/")
        return (0, date(int(y), int(m), int(d)).isoformat())
    except (ValueError, AttributeError):
        pass
    try:
        return (1, float(text.replace("£", "").replace(",", "")))
    except ValueError:
        return (2, text.lower())


def _sort(tree: ttk.Treeview, col: str, reverse: bool) -> None:
    rows = [(tree.set(k, col), k) for k in tree.get_children("")]
    rows.sort(key=lambda x: _sort_key(x[0]), reverse=reverse)
    for i, (_v, k) in enumerate(rows):
        tree.move(k, "", i)
    tree.heading(col, command=lambda: _sort(tree, col, not reverse))


# ── record list ─────────────────────────────────────────────────────

def _ref_labels(rt: RecordType) -> dict[str, dict[int, str]]:
    out: dict[str, dict[int, str]] = {}
    for f in rt.fields:
        if f.kind == "ref" and f.listed:
            out[f.name] = dict(r.options(r.REGISTRY[f.ref]))  # type: ignore[index]
    return out


def draw_records(parent: ttk.Frame, rt: RecordType, *, principal: Principal,
                 state: dict | None = None, learner_id: int | None = None,
                 on_status: Callable[[str], None] | None = None,
                 on_open: Callable[[dict], None] | None = None,
                 open_learner: Callable[[int], None] | None = None,
                 show_heading: bool = True, subtitle: str = "") -> None:
    """The list page for *rt* (only *learner_id*'s records, if given)."""
    state = state if state is not None else {}
    status = on_status or (lambda _t: None)
    if show_heading:
        heading(parent, rt.title, subtitle)

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    search = tk.StringVar(value=state.get("search", ""))
    ttk.Label(bar, text="Search:").pack(side="left")
    entry = ttk.Entry(bar, textvariable=search, width=24)
    entry.pack(side="left", padx=(4, 10))
    filter_vars: dict[str, tk.StringVar] = {}
    for name in rt.filters:
        f = rt.fields_by_name[name]
        var = tk.StringVar(value=state.get(f"filter:{name}", ALL))
        ttk.Label(bar, text=f"{f.label}:").pack(side="left")
        values = [ALL, *f.choices]
        width = min(max(len(v) for v in values) + 2, 28)
        box = ttk.Combobox(bar, textvariable=var, values=values, state="readonly", width=width)
        box.pack(side="left", padx=(4, 10))
        box.bind("<<ComboboxSelected>>", lambda _e: refresh())
        filter_vars[name] = var

    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    count_var = tk.StringVar()
    ttk.Label(actions, textvariable=count_var, foreground=MUTED).pack(side="right")

    show_learner = rt.learner_field is not None and learner_id is None
    columns: list[tuple[str, str, int]] = []
    if show_learner:
        columns.append(("learner_name", "Pupil", 160))
    listed = [f for f in rt.fields if f.listed and f.kind != "learner"]
    columns += [(f.name, f.label, 220 if f.kind in ("long", "ref") else 110) for f in listed]
    columns += [(f"_c{i}", label, 150) for i, (label, _fn) in enumerate(rt.computed)]
    tree = make_tree(parent, columns)
    rows_by_iid: dict[str, dict] = {}

    def refresh() -> None:
        state["search"] = search.get()
        equals = {}
        for name, var in filter_vars.items():
            state[f"filter:{name}"] = var.get()
            if var.get() != ALL:
                equals[name] = var.get()
        try:
            rows = r.list_records(rt, learner_id=learner_id, equals=equals,
                                  search=search.get())
            refs = _ref_labels(rt)
        except Exception as exc:  # noqa: BLE001 - shown, not fatal
            logger.exception("Listing %s failed", rt.key)
            count_var.set(f"Couldn't read {rt.title.lower()}: {exc}")
            return
        tree.delete(*tree.get_children())
        rows_by_iid.clear()
        for row in rows:
            values = [row.get("learner_name") or ""] if show_learner else []
            for f in listed:
                v = row.get(f.name)
                values.append(refs[f.name].get(v, "") if f.kind == "ref" else r.fmt(f, v))
            extra = [fn(row) for _label, fn in rt.computed]
            values += extra
            tags = ("overdue",) if any("overdue" in x.lower() for x in extra) else ()
            if row.get("status") in ("Archived", "Closed", "Ended", "Returned"):
                tags = ("muted",)
            iid = tree.insert("", "end", values=values, tags=tags)
            rows_by_iid[iid] = row
        count_var.set(f"{len(rows)} {rt.singular if len(rows) == 1 else rt.title.lower()}")

    def selected() -> dict | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo(rt.title, f"Select a {rt.singular} first.", parent=parent)
            return None
        return rows_by_iid.get(sel[0])

    def add() -> None:
        fixed = {rt.learner_field.name: learner_id} if (learner_id and rt.learner_field) else {}
        open_form(parent, rt, None, principal=principal, fixed=fixed,
                  on_saved=lambda _id: (refresh(), status(f"{rt.singular.capitalize()} added")))

    def edit(row: dict | None = None) -> None:
        row = row or selected()
        if row is None:
            return
        open_form(parent, rt, row, principal=principal,
                  on_saved=lambda _id: (refresh(), status(f"{rt.singular.capitalize()} saved")))

    def remove() -> None:
        row = selected()
        if row is None:
            return
        if not messagebox.askyesno("Delete", f"Delete this {rt.singular}?\n\n"
                                   f"{rt.label_for(row)}", parent=parent):
            return
        try:
            r.delete(rt, row["id"], actor=principal.username)
        except r.ValidationError as exc:
            messagebox.showwarning("Can't delete", str(exc), parent=parent)
            return
        refresh()
        status(f"{rt.singular.capitalize()} deleted")

    def export() -> None:
        path = filedialog.asksaveasfilename(
            parent=parent, defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"{rt.key}_{date.today().isoformat()}.csv")
        if not path:
            return
        from education_system.systems.alternative_provision.modules import reports
        n = reports.export_csv(rt, path, list(rows_by_iid.values()))
        status(f"Exported {n} row(s) to {path}")

    editable = principal.can_edit(rt.key)
    if editable:
        ttk.Button(actions, text=f"＋ Add {rt.singular}", command=add).pack(side="left")
        ttk.Button(actions, text="Edit", command=edit).pack(side="left", padx=4)
    if principal.can_delete(rt.key):
        ttk.Button(actions, text="Delete", command=remove).pack(side="left")
    if on_open is not None:
        ttk.Button(actions, text="Open", command=lambda: (row := selected()) and on_open(row)
                   ).pack(side="left", padx=4)
    elif open_learner is not None and show_learner:
        ttk.Button(actions, text="Open pupil",
                   command=lambda: (row := selected()) and open_learner(row["learner_id"])
                   ).pack(side="left", padx=4)
    ttk.Button(actions, text="Export CSV…", command=export).pack(side="left", padx=4)

    def on_double(_e) -> None:
        sel = tree.selection()
        if not sel:
            return
        row = rows_by_iid.get(sel[0])
        if row is None:
            return
        if on_open is not None:
            on_open(row)
        elif editable:
            edit(row)

    tree.bind("<Double-1>", on_double)
    search.trace_add("write", lambda *_a: refresh())
    refresh()


# ── record form ─────────────────────────────────────────────────────

class _Input:
    """One form field's widget and how to read it back."""

    def __init__(self, parent: ttk.Frame, f: Field, value: Any, learner_id: int | None,
                 locked: bool) -> None:
        self.field = f
        self.ids: dict[str, int] = {}
        self.var = tk.StringVar()
        self.text: tk.Text | None = None
        if f.kind == "long":
            self.text = tk.Text(parent, height=4, width=60, wrap="word")
            self.text.insert("1.0", value or "")
            self.widget: tk.Widget = self.text
        elif f.kind == "bool":
            self.bool_var = tk.IntVar(value=1 if value else 0)
            self.widget = ttk.Checkbutton(parent, variable=self.bool_var)
        elif f.kind in ("choice", "learner", "ref"):
            if f.kind == "choice":
                labels = list(f.choices)
            else:
                if f.kind == "learner":
                    from education_system.systems.alternative_provision.modules import learners
                    pairs = learners.learner_options(include_archived=locked)
                else:
                    target = r.REGISTRY[f.ref]  # type: ignore[index]
                    pairs = r.options(target, learner_id=learner_id
                                      if target.learner_field else None)
                self.ids = {label: i for i, label in pairs}
                labels = list(self.ids)
                value = next((label for label, i in self.ids.items() if i == value), "")
            if not f.required:
                labels = ["", *labels]
            self.var.set(value or "")
            self.widget = ttk.Combobox(parent, textvariable=self.var, values=labels,
                                       state="disabled" if locked else "readonly", width=48)
        else:
            shown = r.fmt(f, value) if f.kind == "date" else ("" if value is None else str(value))
            self.var.set(shown)
            self.widget = ttk.Entry(parent, textvariable=self.var, width=50)

    def get(self) -> Any:
        f = self.field
        if self.text is not None:
            return self.text.get("1.0", "end").strip()
        if f.kind == "bool":
            return self.bool_var.get()
        if f.kind in ("learner", "ref"):
            return self.ids.get(self.var.get())
        return self.var.get()


def open_form(parent: tk.Misc, rt: RecordType, row: dict | None, *, principal: Principal,
              on_saved: Callable[[int], None], fixed: dict | None = None) -> tk.Toplevel:
    """Add (``row=None``) or edit a record in a dialog. *fixed* pre-fills and
    locks fields (e.g. the learner, when adding from their profile)."""
    fixed = fixed or {}
    win = make_toplevel(parent.winfo_toplevel())
    win.title(f"{'Edit' if row else 'Add'} {rt.singular}")
    window_sizing.fit(win, "720x640", (520, 400))

    outer = ttk.Frame(win, padding=12)
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text=(f"Edit {rt.singular}" if row else f"New {rt.singular}"),
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 8))

    canvas = tk.Canvas(outer, highlightthickness=0)
    bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    body = ttk.Frame(canvas)
    body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw")
    canvas.configure(yscrollcommand=bar.set)
    buttons = ttk.Frame(outer)
    buttons.pack(side="bottom", fill="x", pady=(10, 0))
    canvas.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")

    learner_id = (row or {}).get("learner_id") or fixed.get("learner_id")
    inputs: list[_Input] = []
    r_ = 0
    for f in rt.fields:
        if not f.form:
            continue
        value = fixed.get(f.name, (row or {}).get(f.name) if row else f.initial())
        locked = f.name in fixed or (row is not None and f.kind == "learner")
        label = f.label + (" *" if f.required else "")
        ttk.Label(body, text=label).grid(row=r_, column=0, sticky="nw", padx=(0, 10), pady=4)
        inp = _Input(body, f, value, learner_id, locked)
        inp.widget.grid(row=r_, column=1, sticky="w", pady=4)
        inputs.append(inp)
        hint = f.help or ("DD/MM/YYYY" if f.kind == "date" else "")
        if hint:
            r_ += 1
            ttk.Label(body, text=hint, foreground="#888", font=("", 8)).grid(
                row=r_, column=1, sticky="w")
        r_ += 1

    def save() -> None:
        values = {inp.field.name: inp.get() for inp in inputs}
        values.update(fixed)
        try:
            new_id = r.save(rt, values, record_id=(row or {}).get("id"),
                            actor=principal.username)
        except r.ValidationError as exc:
            messagebox.showwarning("Check the form", str(exc), parent=win)
            return
        notices = r.take_notices()
        win.destroy()
        on_saved(new_id)
        if notices:   # what the save did on the platform (school referrals)
            messagebox.showinfo("Linked schools", "\n\n".join(notices),
                                parent=parent if parent.winfo_exists() else None)

    ttk.Button(buttons, text="Save", command=save).pack(side="right")
    ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="right", padx=6)
    ttk.Label(buttons, text="* required", foreground="#888").pack(side="left")
    win.bind("<Escape>", lambda _e: win.destroy())
    win.grab_set()
    return win
