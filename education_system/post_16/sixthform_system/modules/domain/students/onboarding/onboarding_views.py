"""Tkinter views for Sixth Form Onboarding.

Notebook with 3 tabs:

* Checklists  — master list (filterable) with a per-checklist detail
                pane on the right: items, tick-off, add/edit/delete.
* Templates   — read-only preview of code-defined templates.
* Summary     — counts + overdue / upcoming alerts.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.students.onboarding import (
    onboarding as data,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.post_16.sixthform_system.modules.domain.students.onboarding.onboarding import (
    CATEGORIES,
    CHECKLIST_STATUSES,
    Checklist,
    DEFAULT_CATEGORY,
    DEFAULT_CHECKLIST_STATUS,
    DEFAULT_ITEM_STATUS,
    DEFAULT_TEMPLATE,
    Item,
    ITEM_STATUSES,
    TEMPLATES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_onboarding_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Onboarding — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ChecklistsTab(nb)
    TemplatesTab(nb)
    SummaryTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name
             for s in student_data.list_students()}


# ══ Checklists tab ════════════════════════════════════════════════

class ChecklistsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Checklists")
        self._selected_chk: int | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        # ── Top filter bar ─────────────────────────────────────────
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + CHECKLIST_STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Assigned to:").pack(side="left")
        self.f_assigned = ttk.Entry(bar, width=16)
        self.f_assigned.pack(side="left", padx=(2, 10))

        self.open_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only",
                          variable=self.open_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.overdue_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Overdue only",
                          variable=self.overdue_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear_filters).pack(side="left")
        ttk.Button(bar, text="New checklist…",
                    command=self._new).pack(side="left", padx=(16, 0))

        # ── Split: left = checklists, right = items ───────────────
        pane = ttk.Panedwindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(left, weight=2)
        pane.add(right, weight=3)

        # Left: checklists table
        cols = ("id", "student", "name", "status", "progress",
                "due", "assigned")
        self.tree = ttk.Treeview(left, columns=cols, show="headings")
        headings = {"id": "ID", "student": "Student", "name": "Name",
                    "status": "Status", "progress": "Progress",
                    "due": "Due", "assigned": "Assigned"}
        widths = {"id": 50, "student": 80, "name": 200,
                  "status": 110, "progress": 110, "due": 95,
                  "assigned": 120}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(left, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Completed",   background="#d8f4d8")
        self.tree.tag_configure("In Progress", background="#fff7d0")
        self.tree.tag_configure("Not Started", background="#eef7ff")
        self.tree.tag_configure("On Hold",     background="#eeeeee")
        self.tree.tag_configure("Cancelled",   background="#eeeeee")
        self.tree.tag_configure("Overdue",     background="#ffd0d0")
        self.tree.bind("<<TreeviewSelect>>",
                        lambda _e: self._on_select())
        self.tree.bind("<Double-1>",
                        lambda _e: self._edit_checklist())

        # Left actions
        chk_actions = ttk.Frame(left)
        chk_actions.pack(fill="x", padx=2, pady=(4, 0))
        ttk.Button(chk_actions, text="Edit",
                    command=self._edit_checklist).pack(side="left")
        ttk.Button(chk_actions, text="Status",
                    command=self._status_chk).pack(side="left", padx=4)
        ttk.Button(chk_actions, text="Delete",
                    command=self._delete_chk).pack(side="left", padx=4)
        ttk.Button(chk_actions, text="Refresh",
                    command=self.refresh).pack(side="right")

        # Right: detail header + items
        self.detail_var = tk.StringVar(
            value="Select a checklist on the left.")
        ttk.Label(right, textvariable=self.detail_var,
                   font=("", 11, "bold"),
                   anchor="w").pack(fill="x", padx=2, pady=(0, 4))
        self.subdetail_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.subdetail_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", padx=2, pady=(0, 6))

        item_cols = ("done", "req", "id", "category", "task",
                     "status", "due", "completed")
        self.items_tree = ttk.Treeview(right, columns=item_cols,
                                          show="headings")
        item_headings = {"done": "✓", "req": "*", "id": "ID",
                          "category": "Category", "task": "Task",
                          "status": "Status", "due": "Due",
                          "completed": "Completed"}
        item_widths = {"done": 30, "req": 30, "id": 50,
                        "category": 130, "task": 280,
                        "status": 90, "due": 90, "completed": 130}
        for c in item_cols:
            self.items_tree.heading(c, text=item_headings[c])
            anchor = "center" if c in ("done", "req") else "w"
            self.items_tree.column(c, width=item_widths[c], anchor=anchor)
        ivs = ttk.Scrollbar(right, orient="vertical",
                              command=self.items_tree.yview)
        self.items_tree.configure(yscrollcommand=ivs.set)
        self.items_tree.pack(side="left", fill="both", expand=True)
        ivs.pack(side="right", fill="y")
        self.items_tree.tag_configure("done", background="#d8f4d8")
        self.items_tree.tag_configure("Blocked", background="#ffd0d0")
        self.items_tree.tag_configure("N/A", background="#eeeeee")
        self.items_tree.bind("<Double-1>",
                                lambda _e: self._toggle_item())

        item_actions = ttk.Frame(right)
        item_actions.pack(fill="x", padx=2, pady=(4, 0))
        ttk.Button(item_actions, text="Toggle ✓",
                    command=self._toggle_item).pack(side="left")
        ttk.Button(item_actions, text="Status",
                    command=self._status_item).pack(side="left", padx=4)
        ttk.Button(item_actions, text="New item",
                    command=self._new_item).pack(side="left", padx=4)
        ttk.Button(item_actions, text="Edit",
                    command=self._edit_item).pack(side="left", padx=4)
        ttk.Button(item_actions, text="Delete",
                    command=self._delete_item).pack(side="left", padx=4)

    def _clear_filters(self) -> None:
        self.f_student.delete(0, "end")
        self.f_status.current(0)
        self.f_assigned.delete(0, "end")
        self.open_var.set(True)
        self.overdue_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_checklists_with_detail(
                student_id=self.f_student.get().strip() or None,
                status=self.f_status.get() or None,
                assigned_to=self.f_assigned.get().strip() or None,
                open_only=self.open_var.get(),
                overdue_only=self.overdue_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        today = _today()
        for r in rows:
            c = r.checklist
            progress = (f"{r.done}/{r.total}  "
                        f"(req {r.required_done}/{r.required_total})")
            tags: list[str] = []
            if c.status in CHECKLIST_STATUSES:
                tags.append(c.status)
            if (c.is_open and c.due_date and c.due_date < today):
                tags.append("Overdue")
            self.tree.insert("", "end", iid=str(c.checklist_id), values=(
                c.checklist_id, c.student_id, c.name,
                c.status, progress, c.due_date or "—",
                c.assigned_to or "—",
            ), tags=tuple(tags))

        # Re-select previously selected row if it still exists
        if self._selected_chk is not None and self.tree.exists(
                str(self._selected_chk)):
            self.tree.selection_set(str(self._selected_chk))
            self._render_items()
        else:
            self._selected_chk = None
            self._clear_detail()

    def _on_select(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            self._selected_chk = int(sel[0])
        except ValueError:
            return
        self._render_items()

    def _clear_detail(self) -> None:
        for i in self.items_tree.get_children():
            self.items_tree.delete(i)
        self.detail_var.set("Select a checklist on the left.")
        self.subdetail_var.set("")

    def _render_items(self) -> None:
        for i in self.items_tree.get_children():
            self.items_tree.delete(i)
        if self._selected_chk is None:
            return
        detail = data.get_checklist_detail(self._selected_chk)
        if detail is None:
            self._clear_detail()
            return
        c = detail.checklist
        self.detail_var.set(
            f"#{c.checklist_id}  {c.name}")
        self.subdetail_var.set(
            f"Student: {c.student_id} — {detail.student_name}  ·  "
            f"Status: {c.status}  ·  Due: {c.due_date or '—'}  ·  "
            f"Progress: {detail.done_items}/{detail.total_items} "
            f"({detail.percent_complete}%)  ·  "
            f"Required: {detail.required_done}/{detail.required_total}")
        for it in detail.items:
            mark = "✓" if it.is_done else ""
            req = "*" if it.required else ""
            comp = (f"{it.completed_on} by {it.completed_by or '—'}"
                    if it.completed_on else "")
            tags: list[str] = []
            if it.is_done:
                tags.append("done")
            if it.status in ("Blocked", "N/A"):
                tags.append(it.status)
            self.items_tree.insert("", "end", iid=str(it.item_id), values=(
                mark, req, it.item_id, it.category, it.task_name,
                it.status, it.due_date or "—", comp,
            ), tags=tuple(tags))

    def _selected_chk_id(self) -> int | None:
        return self._selected_chk

    def _selected_item_id(self) -> int | None:
        sel = self.items_tree.selection()
        if not sel:
            return None
        return int(sel[0])

    # ── Checklist actions ─────────────────────────────────────────
    def _new(self) -> None:
        ChecklistDialog(self.frame.winfo_toplevel(),
                          existing=None, on_save=self.refresh)

    def _edit_checklist(self) -> None:
        cid = self._selected_chk_id()
        if cid is None:
            messagebox.showinfo("Edit", "Select a checklist first.")
            return
        existing = data.get_checklist(cid)
        if existing is None:
            return
        ChecklistDialog(self.frame.winfo_toplevel(),
                          existing=existing, on_save=self.refresh)

    def _status_chk(self) -> None:
        cid = self._selected_chk_id()
        if cid is None:
            messagebox.showinfo("Status", "Select a checklist first.")
            return
        existing = data.get_checklist(cid)
        if existing is None:
            return
        ChecklistStatusDialog(self.frame.winfo_toplevel(),
                                existing, on_save=self.refresh)

    def _delete_chk(self) -> None:
        cid = self._selected_chk_id()
        if cid is None:
            messagebox.showinfo("Delete", "Select a checklist first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete checklist #{cid}?\n"
                "All its items will be removed too."):
            return
        try:
            data.delete_checklist(cid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self._selected_chk = None
        self.refresh()

    # ── Item actions ──────────────────────────────────────────────
    def _toggle_item(self) -> None:
        iid = self._selected_item_id()
        if iid is None:
            messagebox.showinfo("Toggle", "Select an item first.")
            return
        existing = data.get_item(iid)
        if existing is None:
            return
        try:
            if existing.is_done:
                data.untick(iid)
            else:
                data.tick(iid)
        except Exception as e:
            messagebox.showerror("Toggle failed", str(e))
            return
        self.refresh()

    def _status_item(self) -> None:
        iid = self._selected_item_id()
        if iid is None:
            messagebox.showinfo("Status", "Select an item first.")
            return
        existing = data.get_item(iid)
        if existing is None:
            return
        ItemStatusDialog(self.frame.winfo_toplevel(),
                           existing, on_save=self.refresh)

    def _new_item(self) -> None:
        cid = self._selected_chk_id()
        if cid is None:
            messagebox.showinfo("New item",
                                  "Select a checklist first.")
            return
        ItemDialog(self.frame.winfo_toplevel(), checklist_id=cid,
                      existing=None, on_save=self.refresh)

    def _edit_item(self) -> None:
        iid = self._selected_item_id()
        if iid is None:
            messagebox.showinfo("Edit", "Select an item first.")
            return
        existing = data.get_item(iid)
        if existing is None:
            return
        ItemDialog(self.frame.winfo_toplevel(),
                      checklist_id=existing.checklist_id,
                      existing=existing, on_save=self.refresh)

    def _delete_item(self) -> None:
        iid = self._selected_item_id()
        if iid is None:
            messagebox.showinfo("Delete", "Select an item first.")
            return
        if not messagebox.askyesno("Delete", f"Delete item #{iid}?"):
            return
        try:
            data.delete_item(iid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Templates tab ════════════════════════════════════════════════

class TemplatesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Templates")
        self._build()

    def _build(self) -> None:
        ttk.Label(
            self.frame,
            text="Templates are defined in code "
                 "(onboarding.py:TEMPLATES). Select a template when "
                 "creating a checklist and these items are seeded.",
            foreground="#555", wraplength=900, anchor="w",
            justify="left",
        ).pack(fill="x", padx=12, pady=(12, 6))

        cols = ("template", "category", "required", "task")
        tree = ttk.Treeview(self.frame, columns=cols,
                               show="tree headings")
        tree.heading("#0", text="")
        tree.heading("template", text="Template")
        tree.heading("category", text="Category")
        tree.heading("required", text="Req.")
        tree.heading("task", text="Task")
        tree.column("#0", width=20)
        tree.column("template", width=200, anchor="w")
        tree.column("category", width=180, anchor="w")
        tree.column("required", width=60, anchor="center")
        tree.column("task", width=520, anchor="w")
        vs = ttk.Scrollbar(self.frame, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True,
                   padx=(12, 0), pady=(0, 12))
        vs.pack(side="right", fill="y", pady=(0, 12), padx=(0, 12))

        for name, items in TEMPLATES.items():
            req = sum(1 for _, _, r in items if r)
            parent = tree.insert(
                "", "end",
                text=f"{name}  ({len(items)} items, {req} required)",
                values=(name, "", "", ""), open=False)
            for task, cat, required in items:
                tree.insert(parent, "end",
                              values=("", cat, "✓" if required else "",
                                       task))


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Upcoming-due window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=6)
        self.window_e.insert(0, "14")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        try:
            win = int(self.window_e.get().strip() or "14")
        except ValueError:
            messagebox.showerror("Summary",
                                    "Window must be a number.")
            return
        summ = data.summary(upcoming_window_days=win)
        lines = [
            f"Total checklists   : {summ.total_checklists}",
            f"Open               : {summ.open_count}",
            f"Completed          : {summ.completed_count}",
            f"Overdue            : {summ.overdue}",
            f"Upcoming due ({win}d){' ' * (8 - len(str(win)))}: "
            f"{summ.upcoming_due}",
            "",
            f"Items total        : {summ.items_total}",
            f"Items done         : {summ.items_done}",
            f"Items overdue      : {summ.items_overdue}",
            "",
            "By checklist status:",
        ]
        for s in CHECKLIST_STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("Items by category:")
        for c in CATEGORIES:
            n = summ.by_category.get(c, 0)
            if n:
                lines.append(f"  {c:<24} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class ChecklistDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Checklist | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Checklist" if existing else "New Checklist")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                 sticky="e", pady=4)
        if self.existing:
            self._student_id = self.existing.student_id
            self.student_cb = None
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{self._student_id} — "
                             f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                form, values=[l for _, l in opts],
                state="readonly", width=44)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Template:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        if self.existing:
            ttk.Label(form,
                       text=self.existing.template_name or "—"
                       ).grid(row=r, column=1, sticky="w", padx=6)
            self.template_cb = None
        else:
            self.template_cb = ttk.Combobox(
                form, values=list(TEMPLATES.keys()),
                state="readonly", width=30)
            self.template_cb.set(DEFAULT_TEMPLATE)
            self.template_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Name:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=44)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        self.name_e.grid(row=r, column=1, sticky="w", padx=6)
        if not self.existing:
            ttk.Label(form, text="(blank = auto)",
                       foreground="#888").grid(row=r, column=2,
                                                  sticky="w")

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=CHECKLIST_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_CHECKLIST_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Started on:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.started_on:
            self.start_e.insert(0, self.existing.started_on)
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Due date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.due_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.due_date:
            self.due_e.insert(0, self.existing.due_date)
        self.due_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Assigned to:").grid(row=r, column=0,
                                                     sticky="e", pady=4)
        self.assigned_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.assigned_to:
            self.assigned_e.insert(0, self.existing.assigned_to)
        self.assigned_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        if self.existing:
            sid = self._student_id
            template = self.existing.template_name
        elif self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                raise ValidationError("Select a student")
            sid = self._student_ids[idx]
            template = (self.template_cb.get()
                         if self.template_cb else "")
        else:
            raise ValidationError("Select a student")
        return {
            "student_id":    sid,
            "template_name": template,
            "name":          self.name_e.get().strip() or None,
            "status":        self.status_cb.get().strip(),
            "started_on":    self.start_e.get().strip() or None,
            "due_date":      self.due_e.get().strip() or None,
            "assigned_to":   self.assigned_e.get().strip() or None,
            "notes":         self.notes_t.get("1.0", "end").strip() or None,
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_checklist(self.existing.checklist_id,
                                        payload)
            else:
                data.create_checklist(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ChecklistStatusDialog:
    def __init__(self, parent: tk.Misc, existing: Checklist,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — checklist #{existing.checklist_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=CHECKLIST_STATUSES,
                                  state="readonly", width=18)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_checklist_status(
                self.existing.checklist_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ItemStatusDialog:
    def __init__(self, parent: tk.Misc, existing: Item,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — item #{existing.item_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"Task: {existing.task_name}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="New status:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=ITEM_STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Completed by:").grid(row=2, column=0,
                                                      sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if existing.completed_by:
            self.by_e.insert(0, existing.completed_by)
        self.by_e.grid(row=2, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_item_status(
                self.existing.item_id, self.cb.get(),
                completed_by=self.by_e.get().strip() or None,
            )
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ItemDialog:
    def __init__(self, parent: tk.Misc, *,
                 checklist_id: int,
                 existing: Item | None,
                 on_save: Callable[[], None]) -> None:
        self.checklist_id = checklist_id
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Item" if existing else "New Item")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="Task:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.task_e = ttk.Entry(form, width=44)
        if self.existing:
            self.task_e.insert(0, self.existing.task_name)
        self.task_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Category:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.cat_cb = ttk.Combobox(form, values=CATEGORIES,
                                      state="readonly", width=22)
        self.cat_cb.set(self.existing.category if self.existing
                           else DEFAULT_CATEGORY)
        self.cat_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        self.required_var = tk.BooleanVar(
            value=(self.existing.required if self.existing else True))
        ttk.Checkbutton(form, text="Required for completion",
                          variable=self.required_var).grid(
            row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=ITEM_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_ITEM_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Due date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.due_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.due_date:
            self.due_e.insert(0, self.existing.due_date)
        self.due_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Completed by:").grid(row=r, column=0,
                                                      sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.completed_by:
            self.by_e.insert(0, self.existing.completed_by)
        self.by_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=3)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "checklist_id": self.checklist_id,
            "task_name":    self.task_e.get().strip(),
            "category":     self.cat_cb.get().strip(),
            "required":     self.required_var.get(),
            "status":       self.status_cb.get().strip(),
            "due_date":     self.due_e.get().strip() or None,
            "completed_by": self.by_e.get().strip() or None,
            "notes":        self.notes_t.get("1.0", "end").strip() or None,
        }
        try:
            if self.existing:
                data.update_item(self.existing.item_id, payload)
            else:
                data.create_item(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
