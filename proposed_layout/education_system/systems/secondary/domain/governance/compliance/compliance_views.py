"""GUI panels for the Secondary School Compliance register.

Tabbed view: Register (filterable item list with row actions), New item
(create form) and Summary (counts by category and derived status).
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any

from education_system.systems.secondary.domain.governance.compliance import compliance as data
from education_system.systems.secondary.domain.governance.compliance.compliance import (
    CATEGORIES,
    DEFAULT_FREQUENCY,
    DEFAULT_STATUS,
    DERIVED_STATUSES,
    FREQUENCIES,
    STATUSES,
    Item,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def open_compliance_window(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Compliance")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    register_tab = ttk.Frame(nb, padding=8)
    new_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(register_tab, text="Register")
    nb.add(new_tab,      text="New item")
    nb.add(summary_tab,  text="Summary")

    state = {"refresh_register": None, "refresh_summary": None}

    def refresh_all() -> None:
        if state["refresh_register"]:
            state["refresh_register"]()
        if state["refresh_summary"]:
            state["refresh_summary"]()

    _build_register_tab(gui, register_tab, state, refresh_all)
    _build_new_tab(gui, new_tab, refresh_all)
    _build_summary_tab(gui, summary_tab, state)


# ── Register tab ───────────────────────────────────────────────────

def _build_register_tab(gui, parent: ttk.Frame,
                         state: dict, refresh_all) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    cat_var = tk.StringVar()
    status_var = tk.StringVar()
    owner_var = tk.StringVar()
    query_var = tk.StringVar()
    overdue_var = tk.BooleanVar(value=False)

    ttk.Label(filt, text="Category:").pack(side="left")
    ttk.Combobox(filt, textvariable=cat_var,
                  values=["", *CATEGORIES], state="readonly", width=14
                  ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                  values=["", *STATUSES], state="readonly", width=14
                  ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Owner:").pack(side="left")
    ttk.Entry(filt, textvariable=owner_var, width=14
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Search:").pack(side="left")
    ttk.Entry(filt, textvariable=query_var, width=18
              ).pack(side="left", padx=(4, 8))
    ttk.Checkbutton(filt, text="Overdue only", variable=overdue_var
                     ).pack(side="left", padx=(4, 8))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True, pady=(4, 4))
    footer = ttk.Label(parent, text="", foreground="#555")
    footer.pack(anchor="w")
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(6, 0))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions.winfo_children():
            w.destroy()
        try:
            views = data.list_views(
                category=cat_var.get() or None,
                status=status_var.get() or None,
                owner=owner_var.get().strip() or None,
                query=query_var.get().strip() or None,
                overdue_only=overdue_var.get(),
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("id", "category", "title", "owner", "next",
                "frequency", "status")
        headings = {
            "id":        ("#",         50),
            "category":  ("Category",  110),
            "title":     ("Title",     280),
            "owner":     ("Owner",     130),
            "next":      ("Next/Due",  100),
            "frequency": ("Freq.",      90),
            "status":    ("Status",    120),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings",
                             height=16)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        # Tag overdue rows for visual emphasis.
        tree.tag_configure("overdue", foreground="#a33")
        tree.tag_configure("soon", foreground="#a36")

        for v in views:
            it = v.item
            nxt = it.next_review or it.due_date or "—"
            tag = ""
            if v.derived_status == "Overdue":
                tag = "overdue"
            elif (v.days_until_due is not None
                   and 0 <= v.days_until_due <= 30):
                tag = "soon"
            tree.insert("", "end", iid=str(it.item_id), values=(
                it.item_id, it.category, it.title, it.owner or "",
                nxt, it.frequency, v.derived_status,
            ), tags=(tag,) if tag else ())

        footer.configure(text=f"{len(views)} item(s).")
        gui.status_var.set(f"Compliance: {len(views)} match(es)")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _edit() -> None:
            rid = _selected()
            if rid is None:
                messagebox.showinfo("No selection", "Pick an item first.",
                                     parent=gui.root)
                return
            _edit_dialog(gui, rid, refresh_all)

        def _delete() -> None:
            rid = _selected()
            if rid is None:
                messagebox.showinfo("No selection", "Pick an item first.",
                                     parent=gui.root)
                return
            existing = data.get_item(rid)
            if existing is None:
                refresh_all()
                return
            if not messagebox.askyesno(
                    "Delete item",
                    f"Delete '#{rid} — {existing.title}'?",
                    parent=gui.root):
                return
            try:
                data.delete_item(rid)
            except Exception as e:
                logger.exception("delete_item failed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh_all()

        def _review() -> None:
            rid = _selected()
            if rid is None:
                messagebox.showinfo("No selection", "Pick an item first.",
                                     parent=gui.root)
                return
            _review_dialog(gui, rid, refresh_all)

        ttk.Button(actions, text="Edit", command=_edit
                    ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Mark reviewed", command=_review
                    ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Delete", command=_delete
                    ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Refresh", command=refresh_all
                    ).pack(side="left", padx=(12, 0))

    ttk.Button(filt, text="Apply", command=refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
                command=lambda: (cat_var.set(""), status_var.set(""),
                                  owner_var.set(""), query_var.set(""),
                                  overdue_var.set(False), refresh())
                ).pack(side="left", padx=(4, 0))

    state["refresh_register"] = refresh
    refresh()


# ── Edit dialog ────────────────────────────────────────────────────

def _edit_dialog(gui, item_id: int, refresh_all) -> None:
    existing = data.get_item(item_id)
    if existing is None:
        messagebox.showerror("Not found", f"No item #{item_id}",
                              parent=gui.root)
        return
    win = tk.Toplevel(gui.root)
    win.title(f"Edit compliance item #{item_id}")
    win.transient(gui.root)
    win.after_idle(win.grab_set)

    frm = ttk.Frame(win, padding=12)
    frm.grid()

    def _entry_row(row: int, label: str, var: tk.StringVar,
                    width: int = 36, values: list[str] | None = None
                    ) -> None:
        ttk.Label(frm, text=label).grid(row=row, column=0, sticky="e",
                                          padx=(0, 6), pady=2)
        if values is not None:
            ttk.Combobox(frm, textvariable=var, values=values,
                          state="readonly", width=max(18, width - 4)
                          ).grid(row=row, column=1, sticky="w", pady=2)
        else:
            ttk.Entry(frm, textvariable=var, width=width
                      ).grid(row=row, column=1, sticky="w", pady=2)

    cat_var = tk.StringVar(value=existing.category)
    title_var = tk.StringVar(value=existing.title)
    owner_var = tk.StringVar(value=existing.owner or "")
    status_var = tk.StringVar(value=existing.status)
    freq_var = tk.StringVar(value=existing.frequency)
    due_var = tk.StringVar(value=existing.due_date or "")
    last_var = tk.StringVar(value=existing.last_review or "")
    next_var = tk.StringVar(value=existing.next_review or "")
    notes_var = tk.StringVar(value=existing.notes or "")

    _entry_row(0, "Category:", cat_var, values=list(CATEGORIES))
    _entry_row(1, "Title:", title_var)
    _entry_row(2, "Owner:", owner_var)
    _entry_row(3, "Status:", status_var, values=list(STATUSES))
    _entry_row(4, "Frequency:", freq_var, values=list(FREQUENCIES))
    _entry_row(5, "Due date:", due_var, width=18)
    _entry_row(6, "Last review:", last_var, width=18)
    _entry_row(7, "Next review:", next_var, width=18)
    _entry_row(8, "Notes:", notes_var, width=42)

    def save() -> None:
        try:
            data.update_item(item_id, {
                "category": cat_var.get(),
                "title": title_var.get(),
                "owner": owner_var.get(),
                "status": status_var.get(),
                "frequency": freq_var.get(),
                "due_date": due_var.get() or None,
                "last_review": last_var.get() or None,
                "next_review": next_var.get() or None,
                "notes": notes_var.get() or None,
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_item crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        refresh_all()

    bar = ttk.Frame(frm)
    bar.grid(row=9, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ── Mark-reviewed dialog ───────────────────────────────────────────

def _review_dialog(gui, item_id: int, refresh_all) -> None:
    existing = data.get_item(item_id)
    if existing is None:
        return
    win = tk.Toplevel(gui.root)
    win.title(f"Mark reviewed — #{item_id}")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    when_var = tk.StringVar(value=_date.today().isoformat())
    notes_var = tk.StringVar(value="")
    ttk.Label(frm, text=existing.title, foreground="#555"
              ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
    ttk.Label(frm, text="Reviewed on:").grid(row=1, column=0, sticky="e",
                                              padx=(0, 6), pady=2)
    ttk.Entry(frm, textvariable=when_var, width=18
              ).grid(row=1, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Notes:").grid(row=2, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
    ttk.Entry(frm, textvariable=notes_var, width=42
              ).grid(row=2, column=1, sticky="w", pady=2)

    def save() -> None:
        try:
            item = data.mark_reviewed(item_id,
                                        reviewed_on=when_var.get(),
                                        notes=notes_var.get() or None)
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("mark_reviewed crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        nxt = item.next_review or "—"
        messagebox.showinfo("Reviewed",
                              f"#{item.item_id} reviewed. Next: {nxt}",
                              parent=gui.root)
        refresh_all()

    bar = ttk.Frame(frm)
    bar.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ── New tab ────────────────────────────────────────────────────────

def _build_new_tab(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent, text="Create a new compliance item",
              font=("", 12, "bold")).pack(anchor="w", pady=(0, 8))

    form = ttk.Frame(parent)
    form.pack(anchor="w", fill="x")

    cat_var = tk.StringVar(value="Policy")
    title_var = tk.StringVar()
    owner_var = tk.StringVar()
    status_var = tk.StringVar(value=DEFAULT_STATUS)
    freq_var = tk.StringVar(value=DEFAULT_FREQUENCY)
    due_var = tk.StringVar()
    last_var = tk.StringVar()
    next_var = tk.StringVar()
    notes_var = tk.StringVar()

    rows = [
        ("Category:",     cat_var,    "combo", list(CATEGORIES)),
        ("Title:",        title_var,  "entry", None),
        ("Owner:",        owner_var,  "entry", None),
        ("Status:",       status_var, "combo", list(STATUSES)),
        ("Frequency:",    freq_var,   "combo", list(FREQUENCIES)),
        ("Due date:",     due_var,    "date",  None),
        ("Last review:",  last_var,   "date",  None),
        ("Next review:",  next_var,   "date",  None),
        ("Notes:",        notes_var,  "entry", None),
    ]
    for i, (label, var, kind, values) in enumerate(rows):
        ttk.Label(form, text=label).grid(row=i, column=0, sticky="e",
                                          padx=(0, 6), pady=2)
        if kind == "combo":
            ttk.Combobox(form, textvariable=var, values=values,
                          state="readonly", width=24
                          ).grid(row=i, column=1, sticky="w", pady=2)
        elif kind == "date":
            ttk.Entry(form, textvariable=var, width=18
                      ).grid(row=i, column=1, sticky="w", pady=2)
        else:
            ttk.Entry(form, textvariable=var, width=42
                      ).grid(row=i, column=1, sticky="w", pady=2)

    msg = ttk.Label(parent, text="", foreground="#555")
    msg.pack(anchor="w", pady=(8, 0))

    def submit() -> None:
        try:
            item = data.create_item({
                "category": cat_var.get(),
                "title": title_var.get(),
                "owner": owner_var.get(),
                "status": status_var.get(),
                "frequency": freq_var.get(),
                "due_date": due_var.get() or None,
                "last_review": last_var.get() or None,
                "next_review": next_var.get() or None,
                "notes": notes_var.get() or None,
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("create_item crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return
        for v in (title_var, owner_var, due_var, last_var, next_var, notes_var):
            v.set("")
        msg.configure(text=f"Created #{item.item_id} — {item.title}")
        gui.status_var.set(f"Compliance: created #{item.item_id}")
        refresh_all()

    ttk.Button(parent, text="Create item", command=submit
                ).pack(anchor="w", pady=(8, 0))


# ── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame, state: dict) -> None:
    counters = ttk.Frame(parent)
    counters.pack(anchor="w", fill="x", pady=(0, 12))

    total_var = tk.StringVar(value="—")
    overdue_var = tk.StringVar(value="—")
    soon_var = tk.StringVar(value="—")
    nodate_var = tk.StringVar(value="—")

    def _tile(col: int, label: str, var: tk.StringVar,
               hint: str, fg: str = "#222") -> None:
        tile = ttk.LabelFrame(counters, padding=10)
        tile.grid(row=0, column=col, padx=4, sticky="nsew")
        counters.columnconfigure(col, weight=1, uniform="x")
        ttk.Label(tile, text=label, foreground="#666").pack(anchor="w")
        ttk.Label(tile, textvariable=var, font=("", 22, "bold"),
                   foreground=fg).pack(anchor="w", pady=(2, 0))
        ttk.Label(tile, text=hint, foreground="#888",
                   font=("", 9)).pack(anchor="w")

    _tile(0, "Total items", total_var, "Across all categories")
    _tile(1, "Overdue", overdue_var,
           "Past next review / due date", fg="#a33")
    _tile(2, "Due within 30 days", soon_var, "Action required soon")
    _tile(3, "No review date", nodate_var, "Date missing")

    breakdown = ttk.Frame(parent)
    breakdown.pack(fill="both", expand=True, pady=(4, 0))
    breakdown.columnconfigure(0, weight=1, uniform="b")
    breakdown.columnconfigure(1, weight=1, uniform="b")

    cat_frame = ttk.LabelFrame(breakdown, text="By category", padding=6)
    cat_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    cat_tree = ttk.Treeview(cat_frame, columns=("name", "count"),
                              show="headings", height=10)
    cat_tree.heading("name", text="Category")
    cat_tree.heading("count", text="Items")
    cat_tree.column("name", width=200, anchor="w")
    cat_tree.column("count", width=80, anchor="e")
    cat_tree.pack(fill="both", expand=True)

    status_frame = ttk.LabelFrame(breakdown, text="By status (derived)",
                                    padding=6)
    status_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    status_tree = ttk.Treeview(status_frame, columns=("name", "count"),
                                 show="headings", height=10)
    status_tree.heading("name", text="Status")
    status_tree.heading("count", text="Items")
    status_tree.column("name", width=200, anchor="w")
    status_tree.column("count", width=80, anchor="e")
    status_tree.pack(fill="both", expand=True)

    def refresh() -> None:
        try:
            s = data.summary()
        except Exception:
            logger.exception("compliance summary failed")
            total_var.set("—")
            overdue_var.set("—")
            soon_var.set("—")
            nodate_var.set("—")
            return
        total_var.set(str(s.total))
        overdue_var.set(str(s.overdue))
        soon_var.set(str(s.due_soon))
        nodate_var.set(str(s.no_review_date))
        for child in cat_tree.get_children():
            cat_tree.delete(child)
        for cat in CATEGORIES:
            cat_tree.insert("", "end",
                              values=(cat, s.by_category.get(cat, 0)))
        for child in status_tree.get_children():
            status_tree.delete(child)
        for st in DERIVED_STATUSES:
            status_tree.insert("", "end",
                                 values=(st, s.by_status.get(st, 0)))
        gui.status_var.set("Compliance summary refreshed")

    ttk.Button(parent, text="Refresh", command=refresh
                ).pack(anchor="w", pady=(8, 0))

    state["refresh_summary"] = refresh
    refresh()
