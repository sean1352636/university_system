"""Tkinter views for Sixth Form ILP (Individual Learning Plans).

Three tabs: Plans (with goals+reviews detail pane), Goals, Summary.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.assessment.ilp import (
    ilp as data,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.post_16.sixthform_system.modules.domain.assessment.ilp.ilp import (
    DEFAULT_GOAL_CATEGORY,
    DEFAULT_GOAL_STATUS,
    DEFAULT_PLAN_STATUS,
    DEFAULT_PLAN_TYPE,
    DEFAULT_REVIEW_FREQUENCY,
    GOAL_CATEGORIES,
    GOAL_STATUSES,
    Goal,
    PLAN_STATUSES,
    PLAN_TYPES,
    PROGRESS_TAGS,
    Plan,
    REVIEW_FREQUENCIES,
    Review,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_ilp_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"ILP — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    PlansTab(nb)
    GoalsTab(nb)
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


# ══ Plans tab ═════════════════════════════════════════════════════

class PlansTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Plans")
        self._selected_id: int | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, values=("",) + PLAN_TYPES,
                                     state="readonly", width=14)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + PLAN_STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Lead:").pack(side="left")
        self.f_lead = ttk.Entry(bar, width=12)
        self.f_lead.pack(side="left", padx=(2, 8))

        self.open_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only",
                          variable=self.open_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.overdue_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Review overdue",
                          variable=self.overdue_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New plan",
                    command=self._new).pack(side="left", padx=(16, 0))

        pane = ttk.Panedwindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=4)

        # Left: list
        left = ttk.Frame(pane)
        pane.add(left, weight=2)
        cols = ("id", "student", "name", "type", "status",
                "lead", "next_due", "title")
        self.tree = ttk.Treeview(left, columns=cols, show="headings")
        widths = {"id": 50, "student": 80, "name": 140,
                  "type": 100, "status": 100,
                  "lead": 110, "next_due": 90, "title": 220}
        headings = {"id": "ID", "student": "Stu", "name": "Name",
                    "type": "Type", "status": "Status",
                    "lead": "Lead", "next_due": "Next due",
                    "title": "Title"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(left, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Active",    background="#d8f4d8")
        self.tree.tag_configure("Draft",     background="#eef7ff")
        self.tree.tag_configure("On Hold",   background="#fff7d0")
        self.tree.tag_configure("Completed", background="#cce8cc")
        self.tree.tag_configure("Withdrawn", background="#eeeeee")
        self.tree.tag_configure("Archived",  background="#eeeeee")
        self.tree.tag_configure("Overdue",   background="#ffd0d0")
        self.tree.bind("<<TreeviewSelect>>",
                        lambda _e: self._on_select())
        self.tree.bind("<Double-1>",
                        lambda _e: self._edit_selected())

        # Right: detail with goals + reviews subtrees
        right = ttk.Frame(pane)
        pane.add(right, weight=3)
        self.detail_var = tk.StringVar(
            value="Select a plan on the left.")
        ttk.Label(right, textvariable=self.detail_var,
                   font=("", 11, "bold"),
                   anchor="w").pack(fill="x", padx=2, pady=(0, 4))
        self.subdetail_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.subdetail_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", padx=2, pady=(0, 6))

        inner = ttk.Notebook(right)
        inner.pack(fill="both", expand=True)

        goals_frame = ttk.Frame(inner)
        inner.add(goals_frame, text="Goals")
        g_cols = ("id", "status", "category", "title",
                   "target", "completed")
        self.goals_tree = ttk.Treeview(goals_frame, columns=g_cols,
                                            show="headings")
        g_widths = {"id": 50, "status": 100, "category": 110,
                     "title": 240, "target": 100, "completed": 100}
        g_headings = {"id": "ID", "status": "Status",
                        "category": "Category", "title": "Title",
                        "target": "Target", "completed": "Completed"}
        for c in g_cols:
            self.goals_tree.heading(c, text=g_headings[c])
            self.goals_tree.column(c, width=g_widths[c], anchor="w")
        gvs = ttk.Scrollbar(goals_frame, orient="vertical",
                              command=self.goals_tree.yview)
        self.goals_tree.configure(yscrollcommand=gvs.set)
        self.goals_tree.pack(side="left", fill="both", expand=True)
        gvs.pack(side="right", fill="y")
        self.goals_tree.tag_configure("done",
                                            background="#d8f4d8")
        self.goals_tree.tag_configure("Not Met",
                                            background="#ffd0d0")
        self.goals_tree.tag_configure("In Progress",
                                            background="#fff7d0")

        reviews_frame = ttk.Frame(inner)
        inner.add(reviews_frame, text="Reviews")
        r_cols = ("id", "date", "progress", "reviewer", "comments")
        self.rv_tree = ttk.Treeview(reviews_frame, columns=r_cols,
                                          show="headings")
        r_widths = {"id": 50, "date": 100, "progress": 110,
                     "reviewer": 140, "comments": 320}
        r_headings = {"id": "ID", "date": "Date",
                        "progress": "Progress",
                        "reviewer": "Reviewer",
                        "comments": "Comments"}
        for c in r_cols:
            self.rv_tree.heading(c, text=r_headings[c])
            self.rv_tree.column(c, width=r_widths[c], anchor="w")
        rvs = ttk.Scrollbar(reviews_frame, orient="vertical",
                              command=self.rv_tree.yview)
        self.rv_tree.configure(yscrollcommand=rvs.set)
        self.rv_tree.pack(side="left", fill="both", expand=True)
        rvs.pack(side="right", fill="y")

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="Edit plan",
                    command=self._edit_selected).pack(side="left")
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Delete plan",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Add goal",
                    command=self._add_goal).pack(side="left",
                                                   padx=(16, 4))
        ttk.Button(actions, text="Edit goal",
                    command=self._edit_goal).pack(side="left", padx=2)
        ttk.Button(actions, text="Achieve goal",
                    command=self._achieve_goal).pack(side="left",
                                                       padx=2)
        ttk.Button(actions, text="Delete goal",
                    command=self._delete_goal).pack(side="left", padx=2)
        ttk.Button(actions, text="Add review",
                    command=self._add_review).pack(side="left",
                                                     padx=(16, 4))
        ttk.Button(actions, text="Delete review",
                    command=self._delete_review).pack(side="left",
                                                        padx=2)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_type.current(0)
        self.f_status.current(0)
        self.f_lead.delete(0, "end")
        self.open_var.set(True)
        self.overdue_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_plans(
                student_id=self.f_student.get().strip() or None,
                plan_type=self.f_type.get() or None,
                status=self.f_status.get() or None,
                lead_like=self.f_lead.get().strip() or None,
                open_only=self.open_var.get(),
                review_overdue=self.overdue_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for p in rows:
            tags = []
            if p.status in PLAN_STATUSES:
                tags.append(p.status)
            if p.review_overdue:
                tags.append("Overdue")
            self.tree.insert("", "end", iid=str(p.plan_id), values=(
                p.plan_id, p.student_id,
                names.get(p.student_id, "?"),
                p.plan_type, p.status,
                p.lead_staff or "—",
                p.next_review_due or "—",
                p.title,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} plan(s).")

        if (self._selected_id is not None
                and self.tree.exists(str(self._selected_id))):
            self.tree.selection_set(str(self._selected_id))
            self._render_detail()
        else:
            self._selected_id = None
            self._clear_detail()

    def _on_select(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            self._selected_id = int(sel[0])
        except ValueError:
            return
        self._render_detail()

    def _clear_detail(self) -> None:
        for i in self.goals_tree.get_children():
            self.goals_tree.delete(i)
        for i in self.rv_tree.get_children():
            self.rv_tree.delete(i)
        self.detail_var.set("Select a plan on the left.")
        self.subdetail_var.set("")

    def _render_detail(self) -> None:
        for i in self.goals_tree.get_children():
            self.goals_tree.delete(i)
        for i in self.rv_tree.get_children():
            self.rv_tree.delete(i)
        if self._selected_id is None:
            return
        detail = data.get_plan_detail(self._selected_id)
        if detail is None:
            self._clear_detail()
            return
        p = detail.plan
        done, total = detail.goal_progress
        self.detail_var.set(f"#{p.plan_id}  {p.title}")
        self.subdetail_var.set(
            f"{p.student_id} — {detail.student_name}  ·  "
            f"{p.plan_type}  ·  {p.status}  ·  "
            f"Lead: {p.lead_staff or '—'}  ·  "
            f"Goals: {done}/{total}  ·  "
            f"Next review: {p.next_review_due or '—'}"
            + ("  (OVERDUE)" if p.review_overdue else ""))
        for g in detail.goals:
            tags = []
            if g.is_done:
                tags.append("done")
            if g.status in ("Not Met", "In Progress"):
                tags.append(g.status)
            self.goals_tree.insert("", "end",
                                        iid=f"g{g.goal_id}", values=(
                g.goal_id, g.status, g.category, g.title,
                g.target_date or "—",
                g.completed_on or "—",
            ), tags=tuple(tags))
        for r in detail.reviews:
            self.rv_tree.insert("", "end",
                                     iid=f"r{r.review_id}", values=(
                r.review_id, r.review_date,
                r.progress or "—",
                r.reviewer or "—",
                (r.comments or "")[:80],
            ))

    def _selected(self) -> Plan | None:
        if self._selected_id is None:
            return None
        return data.get_plan(self._selected_id)

    def _selected_goal_id(self) -> int | None:
        sel = self.goals_tree.selection()
        if not sel:
            return None
        s = sel[0]
        if not s.startswith("g"):
            return None
        return int(s[1:])

    def _selected_review_id(self) -> int | None:
        sel = self.rv_tree.selection()
        if not sel:
            return None
        s = sel[0]
        if not s.startswith("r"):
            return None
        return int(s[1:])

    # ── Plan actions ──────────────────────────────────────────────
    def _new(self) -> None:
        PlanDialog(self.frame.winfo_toplevel(),
                     existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Edit", "Select a plan first.")
            return
        PlanDialog(self.frame.winfo_toplevel(),
                     existing=p, on_save=self.refresh)

    def _status_selected(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Status", "Select a plan first.")
            return
        PlanStatusDialog(self.frame.winfo_toplevel(),
                            p, on_save=self.refresh)

    def _delete_selected(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Delete", "Select a plan first.")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete plan #{p.plan_id}? "
                "Cascade-deletes goals + reviews."):
            return
        try:
            data.delete_plan(p.plan_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self._selected_id = None
        self.refresh()

    # ── Goal actions ──────────────────────────────────────────────
    def _add_goal(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Goal", "Select a plan first.")
            return
        GoalDialog(self.frame.winfo_toplevel(),
                     plan=p, existing=None,
                     on_save=self.refresh)

    def _edit_goal(self) -> None:
        gid = self._selected_goal_id()
        if gid is None:
            messagebox.showinfo("Goal", "Select a goal first.")
            return
        g = data.get_goal(gid)
        if g is None:
            return
        p = self._selected()
        if p is None:
            return
        GoalDialog(self.frame.winfo_toplevel(),
                     plan=p, existing=g,
                     on_save=self.refresh)

    def _achieve_goal(self) -> None:
        gid = self._selected_goal_id()
        if gid is None:
            messagebox.showinfo("Achieve",
                                  "Select a goal first.")
            return
        try:
            data.achieve_goal(gid)
        except Exception as e:
            messagebox.showerror("Achieve", str(e))
            return
        self.refresh()

    def _delete_goal(self) -> None:
        gid = self._selected_goal_id()
        if gid is None:
            messagebox.showinfo("Delete",
                                  "Select a goal first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete goal #{gid}?"):
            return
        try:
            data.delete_goal(gid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()

    # ── Review actions ────────────────────────────────────────────
    def _add_review(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Review",
                                  "Select a plan first.")
            return
        ReviewDialog(self.frame.winfo_toplevel(),
                       plan=p, on_save=self.refresh)

    def _delete_review(self) -> None:
        rid = self._selected_review_id()
        if rid is None:
            messagebox.showinfo("Delete",
                                  "Select a review first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete review #{rid}?"):
            return
        try:
            data.delete_review(rid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Goals tab ═════════════════════════════════════════════════════

class GoalsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Goals")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + GOAL_STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_category = ttk.Combobox(bar,
                                         values=("",) + GOAL_CATEGORIES,
                                         state="readonly", width=14)
        self.f_category.current(0)
        self.f_category.pack(side="left", padx=(2, 8))

        self.open_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only",
                          variable=self.open_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "plan", "category", "title",
                "status", "target", "completed")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "plan": 60, "category": 130,
                  "title": 280, "status": 110,
                  "target": 100, "completed": 100}
        headings = {"id": "ID", "plan": "Plan",
                    "category": "Category", "title": "Title",
                    "status": "Status", "target": "Target",
                    "completed": "Completed"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Achieved",     background="#d8f4d8")
        self.tree.tag_configure("Partially Met", background="#fff7d0")
        self.tree.tag_configure("Not Met",       background="#ffd0d0")
        self.tree.tag_configure("In Progress",   background="#fff7d0")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_goals(
                status=self.f_status.get() or None,
                category=self.f_category.get() or None,
                open_only=self.open_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for g in rows:
            tags = (g.status,) if g.status in GOAL_STATUSES else ()
            self.tree.insert("", "end", iid=str(g.goal_id), values=(
                g.goal_id, g.plan_id, g.category, g.title,
                g.status, g.target_date or "—",
                g.completed_on or "—",
            ), tags=tags)
        self.count_var.set(f"{len(rows)} goal(s).")


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
        ttk.Label(bar, text="Window (days):").pack(side="left")
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
            f"Total plans         : {summ.total_plans}",
            f"Open                : {summ.open_count}",
            f"Distinct students   : {summ.distinct_students}",
            f"Total goals         : {summ.total_goals}",
            f"Goals achieved      : {summ.goals_achieved}",
            f"Reviews overdue     : {summ.review_overdue}",
            f"Reviews due ({win}d)   : {summ.upcoming_review}",
            "",
            "By status:",
        ]
        for s in PLAN_STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("By type:")
        for t in PLAN_TYPES:
            n = summ.by_type.get(t, 0)
            if n:
                lines.append(f"  {t:<14} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class PlanStatusDialog:
    def __init__(self, parent: tk.Misc, existing: Plan,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — plan #{existing.plan_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=PLAN_STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_plan_status(self.existing.plan_id,
                                    self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class GoalDialog:
    def __init__(self, parent: tk.Misc, *,
                 plan: Plan, existing: Goal | None,
                 on_save: Callable[[], None]) -> None:
        self.plan = plan
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Goal" if existing else "New Goal")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text=f"Plan: #{self.plan.plan_id} "
                                 f"{self.plan.title}",
                   font=("", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(0, 8))

        r += 1
        ttk.Label(form, text="Title:").grid(row=r, column=0,
                                               sticky="e", pady=3)
        self.title_e = ttk.Entry(form, width=44)
        if self.existing:
            self.title_e.insert(0, self.existing.title)
        self.title_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Category:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.cat_cb = ttk.Combobox(form, values=GOAL_CATEGORIES,
                                      state="readonly", width=18)
        self.cat_cb.set(self.existing.category if self.existing
                           else DEFAULT_GOAL_CATEGORY)
        self.cat_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=GOAL_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_GOAL_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Target date:").grid(row=r, column=0,
                                                     sticky="e", pady=3)
        self.target_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.target_date:
            self.target_e.insert(0, self.existing.target_date)
        self.target_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                     sticky="ne", pady=3)
        self.desc_t = tk.Text(form, width=44, height=3)
        if self.existing and self.existing.description:
            self.desc_t.insert("1.0", self.existing.description)
        self.desc_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Success criteria:").grid(row=r, column=0,
                                                          sticky="ne",
                                                          pady=3)
        self.success_t = tk.Text(form, width=44, height=3)
        if self.existing and self.existing.success_criteria:
            self.success_t.insert("1.0",
                                       self.existing.success_criteria)
        self.success_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=44, height=2)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        return {
            "plan_id":          self.plan.plan_id,
            "title":            self.title_e.get().strip(),
            "category":         self.cat_cb.get().strip(),
            "status":           self.status_cb.get().strip(),
            "target_date":      self.target_e.get().strip() or None,
            "description":      self.desc_t.get(
                                    "1.0", "end").strip() or None,
            "success_criteria": self.success_t.get(
                                    "1.0", "end").strip() or None,
            "notes":            self.notes_t.get(
                                    "1.0", "end").strip() or None,
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_goal(self.existing.goal_id, payload)
            else:
                data.create_goal(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ReviewDialog:
    def __init__(self, parent: tk.Misc, *,
                 plan: Plan,
                 on_save: Callable[[], None]) -> None:
        self.plan = plan
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Add review — plan #{plan.plan_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Review date:").grid(row=0, column=0,
                                                     sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Reviewer:").grid(row=1, column=0,
                                                  sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if self.plan.lead_staff:
            self.by_e.insert(0, self.plan.lead_staff)
        self.by_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Progress:").grid(row=2, column=0,
                                                  sticky="e", pady=4)
        self.progress_cb = ttk.Combobox(
            form, values=("",) + PROGRESS_TAGS,
            state="readonly", width=14)
        self.progress_cb.current(0)
        self.progress_cb.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Comments:").grid(row=3, column=0,
                                                  sticky="ne", pady=4)
        self.comments_t = tk.Text(form, width=44, height=4)
        self.comments_t.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Next steps:").grid(row=4, column=0,
                                                    sticky="ne", pady=4)
        self.next_t = tk.Text(form, width=44, height=3)
        self.next_t.grid(row=4, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Next review due:").grid(row=5, column=0,
                                                          sticky="e",
                                                          pady=4)
        self.next_due_e = ttk.Entry(form, width=14)
        self.next_due_e.grid(row=5, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save review",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.add_review(
                self.plan.plan_id,
                review_date=self.date_e.get().strip() or None,
                reviewer=self.by_e.get().strip() or None,
                progress=self.progress_cb.get().strip() or None,
                comments=self.comments_t.get(
                    "1.0", "end").strip() or None,
                next_steps=self.next_t.get(
                    "1.0", "end").strip() or None,
                next_review_due=self.next_due_e.get().strip() or None,
            )
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class PlanDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Plan | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit ILP" if existing else "New ILP")
        self.win.transient(parent)
        self.win.geometry("880x720")
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)
        meta = ttk.LabelFrame(outer, text="Details", padding=8)
        meta.pack(fill="x", pady=(0, 6))
        r = 0

        ttk.Label(meta, text="Student:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        if self.existing:
            self._student_id = self.existing.student_id
            self.student_cb = None
            names = _name_lookup()
            ttk.Label(meta,
                       text=f"{self._student_id} — "
                             f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, columnspan=3,
                               sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                meta, values=[l for _, l in opts],
                state="readonly", width=44)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, columnspan=3,
                                    sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Title:").grid(row=r, column=0,
                                               sticky="e", pady=3)
        self.title_e = ttk.Entry(meta, width=44)
        if self.existing:
            self.title_e.insert(0, self.existing.title)
        self.title_e.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Type:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.type_cb = ttk.Combobox(meta, values=PLAN_TYPES,
                                       state="readonly", width=18)
        self.type_cb.set(self.existing.plan_type if self.existing
                            else DEFAULT_PLAN_TYPE)
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Status:").grid(row=r, column=2,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(meta, values=PLAN_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_PLAN_STATUS)
        self.status_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Lead:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.lead_e = ttk.Entry(meta, width=26)
        if self.existing and self.existing.lead_staff:
            self.lead_e.insert(0, self.existing.lead_staff)
        self.lead_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Review every:").grid(row=r, column=2,
                                                      sticky="e", pady=3)
        self.freq_cb = ttk.Combobox(meta, values=REVIEW_FREQUENCIES,
                                       state="readonly", width=14)
        self.freq_cb.set(self.existing.review_frequency
                            if self.existing
                            else DEFAULT_REVIEW_FREQUENCY)
        self.freq_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=3)
        self.start_e = ttk.Entry(meta, width=14)
        if self.existing and self.existing.start_date:
            self.start_e.insert(0, self.existing.start_date)
        elif not self.existing:
            self.start_e.insert(0, _today())
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="End date:").grid(row=r, column=2,
                                                  sticky="e", pady=3)
        self.end_e = ttk.Entry(meta, width=14)
        if self.existing and self.existing.end_date:
            self.end_e.insert(0, self.existing.end_date)
        self.end_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Last reviewed:").grid(row=r, column=0,
                                                       sticky="e", pady=3)
        self.last_e = ttk.Entry(meta, width=14)
        if self.existing and self.existing.last_reviewed:
            self.last_e.insert(0, self.existing.last_reviewed)
        self.last_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Next review due:").grid(row=r, column=2,
                                                          sticky="e",
                                                          pady=3)
        self.next_e = ttk.Entry(meta, width=14)
        if self.existing and self.existing.next_review_due:
            self.next_e.insert(0, self.existing.next_review_due)
        self.next_e.grid(row=r, column=3, sticky="w", padx=6)

        body_nb = ttk.Notebook(outer)
        body_nb.pack(fill="both", expand=True, pady=6)
        self._body_widgets: dict[str, tk.Text] = {}
        for label, attr in (
                ("Strengths",            "strengths"),
                ("Barriers",             "barriers"),
                ("Strategies",           "strategies"),
                ("Support provided",     "support_provided"),
                ("Parental involvement", "parental_involvement"),
                ("Success criteria",     "success_criteria"),
                ("Notes",                "notes"),
        ):
            f = ttk.Frame(body_nb)
            body_nb.add(f, text=label)
            t = tk.Text(f, wrap="word", height=6)
            t.pack(fill="both", expand=True)
            if self.existing:
                v = getattr(self.existing, attr, None)
                if v:
                    t.insert("1.0", v)
            self._body_widgets[attr] = t

        bar = ttk.Frame(outer)
        bar.pack(fill="x")
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        if self.existing:
            sid = self._student_id
        elif self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                raise ValidationError("Pick a student")
            sid = self._student_ids[idx]
        else:
            raise ValidationError("Pick a student")
        payload = {
            "student_id":       sid,
            "title":            self.title_e.get().strip(),
            "plan_type":        self.type_cb.get().strip(),
            "status":           self.status_cb.get().strip(),
            "lead_staff":       self.lead_e.get().strip(),
            "review_frequency": self.freq_cb.get().strip(),
            "start_date":       self.start_e.get().strip(),
            "end_date":         self.end_e.get().strip(),
            "last_reviewed":    self.last_e.get().strip(),
            "next_review_due":  self.next_e.get().strip(),
        }
        for attr, t in self._body_widgets.items():
            payload[attr] = t.get("1.0", "end").strip()
        return payload

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_plan(self.existing.plan_id, payload)
            else:
                data.create_plan(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
