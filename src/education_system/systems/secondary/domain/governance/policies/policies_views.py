"""GUI panels for the Secondary School Policy register.

Tabbed view:

  * Register — filterable policy list with edit/revision/delete row
    actions. Overdue rows render in red.
  * New policy — create form.
  * Summary — headline tiles + by-category and by-status breakdowns.

Per-policy revisions live in a sub-dialog launched from the row
actions (so the register stays compact).
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any

from education_system.systems.secondary.domain.governance.policies import policies as data
from education_system.systems.secondary.domain.governance.policies.policies import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_REVIEW_CYCLE,
    DEFAULT_STATUS,
    DERIVED_STATUSES,
    Policy,
    REVIEW_CYCLES,
    STATUSES,
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


def open_policies_window(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Policies")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    register_tab = ttk.Frame(nb, padding=8)
    new_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(register_tab, text="Register")
    nb.add(new_tab,      text="New policy")
    nb.add(summary_tab,  text="Summary")

    state: dict[str, Any] = {"refresh_register": None,
                              "refresh_summary": None}

    def refresh_all() -> None:
        if state["refresh_register"]:
            state["refresh_register"]()
        if state["refresh_summary"]:
            state["refresh_summary"]()

    _build_register_tab(gui, register_tab, state, refresh_all)
    _build_new_tab(gui, new_tab, refresh_all)
    _build_summary_tab(gui, summary_tab, state)


# ── Register tab ───────────────────────────────────────────────────

def _build_register_tab(gui, parent: ttk.Frame, state: dict,
                          refresh_all) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 6))

    cat_var = tk.StringVar()
    status_var = tk.StringVar()
    owner_var = tk.StringVar()
    query_var = tk.StringVar()
    overdue_var = tk.BooleanVar(value=False)

    ttk.Label(filt, text="Category:").pack(side="left")
    ttk.Combobox(filt, textvariable=cat_var,
                  values=["", *CATEGORIES], state="readonly", width=16
                  ).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                  values=["", *STATUSES], state="readonly", width=14
                  ).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Owner:").pack(side="left")
    ttk.Entry(filt, textvariable=owner_var, width=14
              ).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Search:").pack(side="left")
    ttk.Entry(filt, textvariable=query_var, width=18
              ).pack(side="left", padx=(4, 4))
    ttk.Checkbutton(filt, text="Overdue only", variable=overdue_var
                     ).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True, pady=(2, 4))
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

        cols = ("id", "category", "title", "version", "owner",
                "next", "revs", "status")
        headings = {
            "id":       ("#",         50),
            "category": ("Category", 130),
            "title":    ("Title",    260),
            "version":  ("Ver.",      60),
            "owner":    ("Owner",    140),
            "next":     ("Next rev.", 100),
            "revs":     ("Rev#",      50),
            "status":   ("Status",   130),
        }
        tree = ttk.Treeview(table_holder, columns=cols,
                              show="headings", height=15)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        tree.tag_configure("overdue", foreground="#a33")
        tree.tag_configure("soon", foreground="#a36")

        for v in views:
            p = v.policy
            tag = ""
            if v.derived_status == "Overdue review":
                tag = "overdue"
            elif (v.days_until_review is not None
                    and 0 <= v.days_until_review <= 30):
                tag = "soon"
            tree.insert("", "end", iid=str(p.policy_id), values=(
                p.policy_id, p.category, p.title, p.version,
                p.owner or "", p.next_review or "—",
                v.revisions_count, v.derived_status,
            ), tags=(tag,) if tag else ())

        footer.configure(text=f"{len(views)} policy(ies).")
        gui.status_var.set(f"Policies: {len(views)} match(es)")

        def _sel() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _edit() -> None:
            pid = _sel()
            if pid is None:
                messagebox.showinfo("No selection", "Pick a policy first.",
                                      parent=gui.root)
                return
            _edit_dialog(gui, pid, refresh_all)

        def _revisions() -> None:
            pid = _sel()
            if pid is None:
                messagebox.showinfo("No selection", "Pick a policy first.",
                                      parent=gui.root)
                return
            _revisions_dialog(gui, pid, refresh_all)

        def _delete() -> None:
            pid = _sel()
            if pid is None:
                messagebox.showinfo("No selection", "Pick a policy first.",
                                      parent=gui.root)
                return
            existing = data.get_policy(pid)
            if existing is None:
                refresh_all()
                return
            if not messagebox.askyesno(
                    "Delete policy",
                    f"Delete '#{pid} — {existing.title}' "
                    f"and all its revisions?", parent=gui.root):
                return
            try:
                data.delete_policy(pid)
            except Exception as e:
                logger.exception("delete_policy crashed")
                messagebox.showerror("Error", str(e), parent=gui.root)
                return
            refresh_all()

        ttk.Button(actions, text="Edit", command=_edit
                    ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Revisions…", command=_revisions
                    ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Delete", command=_delete
                    ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Refresh", command=refresh_all
                    ).pack(side="left", padx=(12, 0))

    ttk.Button(filt, text="Apply", command=refresh
                ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
                command=lambda: (cat_var.set(""), status_var.set(""),
                                  owner_var.set(""), query_var.set(""),
                                  overdue_var.set(False), refresh())
                ).pack(side="left", padx=(4, 0))

    state["refresh_register"] = refresh
    refresh()


# ── Edit dialog ────────────────────────────────────────────────────

def _edit_dialog(gui, policy_id: int, refresh_all) -> None:
    existing = data.get_policy(policy_id)
    if existing is None:
        return
    win = tk.Toplevel(gui.root)
    win.title(f"Edit policy #{policy_id}")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    title = tk.StringVar(value=existing.title)
    category = tk.StringVar(value=existing.category)
    version = tk.StringVar(value=existing.version)
    owner = tk.StringVar(value=existing.owner or "")
    status = tk.StringVar(value=existing.status)
    cycle = tk.StringVar(value=existing.review_cycle)
    approved = tk.StringVar(value=existing.approved_on or "")
    next_review = tk.StringVar(value=existing.next_review or "")
    summary = tk.StringVar(value=existing.summary or "")
    doc = tk.StringVar(value=existing.document_ref or "")

    rows = [
        ("Title:", title, "entry", None),
        ("Category:", category, "combo", list(CATEGORIES)),
        ("Version:", version, "date", None),
        ("Owner:", owner, "entry", None),
        ("Status:", status, "combo", list(STATUSES)),
        ("Review cycle:", cycle, "combo", list(REVIEW_CYCLES)),
        ("Approved on:", approved, "date", None),
        ("Next review:", next_review, "date", None),
        ("Summary:", summary, "entry", None),
        ("Document ref:", doc, "entry", None),
    ]
    for i, (label, var, kind, values) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="e",
                                          padx=(0, 6), pady=2)
        if kind == "combo":
            ttk.Combobox(frm, textvariable=var, values=values,
                          state="readonly", width=22
                          ).grid(row=i, column=1, sticky="w", pady=2)
        elif kind == "date":
            ttk.Entry(frm, textvariable=var, width=18
                      ).grid(row=i, column=1, sticky="w", pady=2)
        else:
            ttk.Entry(frm, textvariable=var, width=46
                      ).grid(row=i, column=1, sticky="w", pady=2)

    def save() -> None:
        try:
            data.update_policy(policy_id, {
                "title": title.get(), "category": category.get(),
                "version": version.get(), "owner": owner.get() or None,
                "status": status.get(), "review_cycle": cycle.get(),
                "approved_on": approved.get() or None,
                "next_review": next_review.get() or None,
                "summary": summary.get() or None,
                "document_ref": doc.get() or None,
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_policy crashed")
            messagebox.showerror("Error", str(e), parent=win)
            return
        win.destroy()
        refresh_all()

    bar = ttk.Frame(frm)
    bar.grid(row=len(rows), column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ── Revisions dialog ───────────────────────────────────────────────

def _revisions_dialog(gui, policy_id: int, refresh_all) -> None:
    existing = data.get_policy(policy_id)
    if existing is None:
        return
    win = tk.Toplevel(gui.root)
    win.title(f"Revisions — policy #{policy_id}")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    win.geometry("780x520")

    frm = ttk.Frame(win, padding=10)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text=f"#{policy_id} · {existing.title} (v{existing.version})",
              font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))

    list_holder = ttk.Frame(frm)
    list_holder.pack(fill="both", expand=True, pady=(0, 8))

    new_frame = ttk.LabelFrame(frm, text="Add revision", padding=8)
    new_frame.pack(fill="x")

    n_version = tk.StringVar(value=existing.version)
    n_when = tk.StringVar(value=_date.today().isoformat())
    n_by = tk.StringVar(value="")
    n_approved = tk.StringVar(value="")
    n_changes = tk.StringVar(value="")

    row = ttk.Frame(new_frame)
    row.pack(fill="x", pady=2)
    ttk.Label(row, text="Version:").pack(side="left")
    ttk.Entry(row, textvariable=n_version, width=10
              ).pack(side="left", padx=(4, 12))
    ttk.Label(row, text="Revised on:").pack(side="left")
    ttk.Entry(row, textvariable=n_when, width=14
              ).pack(side="left", padx=(4, 12))
    ttk.Label(row, text="Revised by:").pack(side="left")
    ttk.Entry(row, textvariable=n_by, width=18
              ).pack(side="left", padx=(4, 12))
    ttk.Label(row, text="Approved by:").pack(side="left")
    ttk.Entry(row, textvariable=n_approved, width=18
              ).pack(side="left", padx=(4, 0))

    row2 = ttk.Frame(new_frame)
    row2.pack(fill="x", pady=2)
    ttk.Label(row2, text="Changes:").pack(side="left")
    ttk.Entry(row2, textvariable=n_changes, width=70
              ).pack(side="left", padx=(4, 0))

    def render() -> None:
        for w in list_holder.winfo_children():
            w.destroy()
        revisions = data.list_revisions(policy_id)
        if not revisions:
            ttk.Label(list_holder, text="No revisions yet.",
                      foreground="#777").pack(anchor="w")
            return
        cols = ("id", "date", "version", "by", "approved", "changes")
        headings = {
            "id":       ("#",       50),
            "date":     ("Date",   100),
            "version":  ("Ver.",    70),
            "by":       ("By",     130),
            "approved": ("Approved by", 150),
            "changes":  ("Changes", 250),
        }
        tree = ttk.Treeview(list_holder, columns=cols,
                              show="headings", height=10)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(list_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for r in revisions:
            tree.insert("", "end", iid=str(r.revision_id), values=(
                r.revision_id, r.revised_on, r.version,
                r.revised_by or "—",
                r.approved_by or "—",
                r.changes or "",
            ))

        def _delete_selected() -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("No selection",
                                     "Pick a revision first.", parent=win)
                return
            rid = int(sel[0])
            if not messagebox.askyesno(
                    "Delete revision",
                    f"Delete revision #{rid}?", parent=win):
                return
            data.delete_revision(rid)
            render()
            refresh_all()

        del_bar = ttk.Frame(list_holder)
        del_bar.pack(fill="x", side="bottom")
        ttk.Button(del_bar, text="Delete revision",
                    command=_delete_selected
                    ).pack(side="left", anchor="w", pady=(4, 0))

    def add() -> None:
        try:
            data.add_revision(policy_id, {
                "version": n_version.get(), "revised_on": n_when.get(),
                "revised_by": n_by.get() or None,
                "approved_by": n_approved.get() or None,
                "changes": n_changes.get() or None,
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("add_revision crashed")
            messagebox.showerror("Error", str(e), parent=win)
            return
        n_changes.set("")
        n_by.set("")
        n_approved.set("")
        n_when.set(_date.today().isoformat())
        render()
        refresh_all()

    bar = ttk.Frame(new_frame)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Add revision", command=add
                ).pack(side="left")
    ttk.Button(bar, text="Close",
                command=win.destroy).pack(side="right")

    render()


# ── New tab ────────────────────────────────────────────────────────

def _build_new_tab(gui, parent: ttk.Frame, refresh_all) -> None:
    ttk.Label(parent, text="Create a new policy",
              font=("", 12, "bold")).pack(anchor="w", pady=(0, 8))

    form = ttk.Frame(parent)
    form.pack(anchor="w", fill="x")

    title = tk.StringVar()
    category = tk.StringVar(value=DEFAULT_CATEGORY)
    version = tk.StringVar(value="1.0")
    owner = tk.StringVar()
    status = tk.StringVar(value=DEFAULT_STATUS)
    cycle = tk.StringVar(value=DEFAULT_REVIEW_CYCLE)
    approved = tk.StringVar()
    next_review = tk.StringVar()
    summary = tk.StringVar()
    doc = tk.StringVar()

    rows = [
        ("Title:", title, "entry", None),
        ("Category:", category, "combo", list(CATEGORIES)),
        ("Version:", version, "date", None),
        ("Owner:", owner, "entry", None),
        ("Status:", status, "combo", list(STATUSES)),
        ("Review cycle:", cycle, "combo", list(REVIEW_CYCLES)),
        ("Approved on:", approved, "date", None),
        ("Next review:", next_review, "date", None),
        ("Summary:", summary, "entry", None),
        ("Document ref:", doc, "entry", None),
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
            ttk.Entry(form, textvariable=var, width=46
                      ).grid(row=i, column=1, sticky="w", pady=2)

    msg = ttk.Label(parent, text="", foreground="#555")
    msg.pack(anchor="w", pady=(8, 0))

    def submit() -> None:
        try:
            p = data.create_policy({
                "title": title.get(), "category": category.get(),
                "version": version.get(), "owner": owner.get() or None,
                "status": status.get(), "review_cycle": cycle.get(),
                "approved_on": approved.get() or None,
                "next_review": next_review.get() or None,
                "summary": summary.get() or None,
                "document_ref": doc.get() or None,
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("create_policy crashed")
            messagebox.showerror("Error", str(e), parent=gui.root)
            return
        for v in (title, owner, approved, next_review, summary, doc):
            v.set("")
        version.set("1.0")
        msg.configure(text=f"Created #{p.policy_id} — {p.title}")
        gui.status_var.set(f"Policies: created #{p.policy_id}")
        refresh_all()

    ttk.Button(parent, text="Create policy", command=submit
                ).pack(anchor="w", pady=(8, 0))


# ── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame, state: dict) -> None:
    tiles = ttk.Frame(parent)
    tiles.pack(anchor="w", fill="x", pady=(0, 12))

    total_var = tk.StringVar(value="—")
    overdue_var = tk.StringVar(value="—")
    soon_var = tk.StringVar(value="—")
    revs_var = tk.StringVar(value="—")
    nodate_var = tk.StringVar(value="—")

    def _tile(col: int, label: str, var: tk.StringVar,
               hint: str, fg: str = "#222") -> None:
        tile = ttk.LabelFrame(tiles, padding=10)
        tile.grid(row=0, column=col, padx=4, sticky="nsew")
        tiles.columnconfigure(col, weight=1, uniform="t")
        ttk.Label(tile, text=label, foreground="#666").pack(anchor="w")
        ttk.Label(tile, textvariable=var, font=("", 20, "bold"),
                   foreground=fg).pack(anchor="w", pady=(2, 0))
        ttk.Label(tile, text=hint, foreground="#888",
                   font=("", 9)).pack(anchor="w")

    _tile(0, "Total policies", total_var, "On register")
    _tile(1, "Overdue review", overdue_var, "Past next review", fg="#a33")
    _tile(2, "Due in 30d", soon_var, "Action soon")
    _tile(3, "No review date", nodate_var, "Date missing")
    _tile(4, "Revisions logged", revs_var, "Lifetime")

    breakdown = ttk.Frame(parent)
    breakdown.pack(fill="both", expand=True, pady=(4, 0))
    breakdown.columnconfigure(0, weight=1, uniform="b")
    breakdown.columnconfigure(1, weight=1, uniform="b")

    cat_frame = ttk.LabelFrame(breakdown, text="By category", padding=6)
    cat_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    cat_tree = ttk.Treeview(cat_frame, columns=("name", "count"),
                              show="headings", height=10)
    cat_tree.heading("name", text="Category")
    cat_tree.heading("count", text="Policies")
    cat_tree.column("name", width=200, anchor="w")
    cat_tree.column("count", width=80, anchor="e")
    cat_tree.pack(fill="both", expand=True)

    status_frame = ttk.LabelFrame(breakdown, text="By status (derived)",
                                    padding=6)
    status_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    status_tree = ttk.Treeview(status_frame, columns=("name", "count"),
                                  show="headings", height=10)
    status_tree.heading("name", text="Status")
    status_tree.heading("count", text="Policies")
    status_tree.column("name", width=200, anchor="w")
    status_tree.column("count", width=80, anchor="e")
    status_tree.pack(fill="both", expand=True)

    def refresh() -> None:
        try:
            s = data.summary()
        except Exception as e:
            logger.exception("policies summary failed")
            messagebox.showerror("Error", str(e), parent=gui.root)
            return
        total_var.set(str(s.total))
        overdue_var.set(str(s.overdue))
        soon_var.set(str(s.due_soon))
        nodate_var.set(str(s.no_review_date))
        revs_var.set(str(s.total_revisions))
        for child in cat_tree.get_children():
            cat_tree.delete(child)
        for c in CATEGORIES:
            cat_tree.insert("", "end",
                              values=(c, s.by_category.get(c, 0)))
        for child in status_tree.get_children():
            status_tree.delete(child)
        for st in DERIVED_STATUSES:
            status_tree.insert("", "end",
                                values=(st, s.by_status.get(st, 0)))
        gui.status_var.set("Policies summary refreshed")

    ttk.Button(parent, text="Refresh", command=refresh
                ).pack(anchor="w", pady=(8, 0))
    state["refresh_summary"] = refresh
    refresh()
