"""Tkinter views for Sixth Form Enrichments.

Notebook with 3 tabs:

* Activities  — left = filterable list of clubs/squads/programmes,
                right = full detail + enrolments table.
* Enrolments  — flat per-student enrolment view.
* Summary     — counts, by-day, by-category.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.academics.enrichment import (
    enrichment as data,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.sixthform_system.modules.domain.academics.enrichment.enrichment import (
    ACTIVITY_STATUSES,
    Activity,
    CATEGORIES,
    DAYS,
    DEFAULT_ACTIVITY_STATUS,
    DEFAULT_CATEGORY,
    ENROLMENT_STATUSES,
    Enrolment,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_enrichment_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Enrichment — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ActivitiesTab(nb)
    EnrolmentsTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name
             for s in student_data.list_students()}


# ══ Activities tab ════════════════════════════════════════════════

class ActivitiesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Activities")
        self._selected_id: int | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Search:").pack(side="left")
        self.f_search = ttk.Entry(bar, width=16)
        self.f_search.pack(side="left", padx=(2, 8))
        self.f_search.bind("<Return>", lambda _e: self.refresh())

        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Combobox(bar, values=("",) + CATEGORIES,
                                    state="readonly", width=22)
        self.f_cat.current(0)
        self.f_cat.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Day:").pack(side="left")
        self.f_day = ttk.Combobox(bar, values=("",) + DAYS,
                                    state="readonly", width=10)
        self.f_day.current(0)
        self.f_day.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar,
                                       values=("",) + ACTIVITY_STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        self.open_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Open only",
                          variable=self.open_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        pane = ttk.Panedwindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=4)

        # Left: activities list
        left = ttk.Frame(pane)
        pane.add(left, weight=2)
        cols = ("id", "name", "category", "when",
                "lead", "cap", "active", "status")
        self.tree = ttk.Treeview(left, columns=cols, show="headings")
        widths = {"id": 50, "name": 180, "category": 170,
                  "when": 150, "lead": 110,
                  "cap": 50, "active": 70, "status": 90}
        headings = {"id": "ID", "name": "Name",
                    "category": "Category", "when": "When",
                    "lead": "Lead", "cap": "Cap",
                    "active": "Active", "status": "Status"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c in ("cap", "active") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(left, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Open",     background="#d8f4d8")
        self.tree.tag_configure("Full",     background="#fff7d0")
        self.tree.tag_configure("Waitlist", background="#fff7d0")
        self.tree.tag_configure("Closed",   background="#eeeeee")
        self.tree.tag_configure("Archived", background="#eeeeee")
        self.tree.tag_configure("Draft",    background="#eef7ff")
        self.tree.bind("<<TreeviewSelect>>",
                        lambda _e: self._on_select())
        self.tree.bind("<Double-1>",
                        lambda _e: self._edit_activity())

        # Right: detail + enrolments
        right = ttk.Frame(pane)
        pane.add(right, weight=3)
        self.detail_var = tk.StringVar(
            value="Select an activity on the left.")
        ttk.Label(right, textvariable=self.detail_var,
                   font=("", 11, "bold"),
                   anchor="w").pack(fill="x", padx=2, pady=(0, 4))
        self.subdetail_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.subdetail_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", padx=2, pady=(0, 6))

        enr_cols = ("id", "student", "name", "status", "role",
                     "attended", "last")
        self.enr_tree = ttk.Treeview(right, columns=enr_cols,
                                          show="headings")
        enr_headings = {"id": "ID", "student": "Student",
                          "name": "Name", "status": "Status",
                          "role": "Role",
                          "attended": "Attended",
                          "last": "Last"}
        enr_widths = {"id": 50, "student": 80, "name": 200,
                       "status": 100, "role": 100,
                       "attended": 80, "last": 100}
        for c in enr_cols:
            self.enr_tree.heading(c, text=enr_headings[c])
            anchor = "center" if c == "attended" else "w"
            self.enr_tree.column(c, width=enr_widths[c],
                                      anchor=anchor)
        evs = ttk.Scrollbar(right, orient="vertical",
                              command=self.enr_tree.yview)
        self.enr_tree.configure(yscrollcommand=evs.set)
        self.enr_tree.pack(side="left", fill="both", expand=True)
        evs.pack(side="right", fill="y")
        self.enr_tree.tag_configure("Active",    background="#d8f4d8")
        self.enr_tree.tag_configure("Withdrawn", background="#eeeeee")
        self.enr_tree.tag_configure("Completed", background="#eef7ff")
        self.enr_tree.tag_configure("On Hold",   background="#fff7d0")
        self.enr_tree.tag_configure("Removed",   background="#ffd0d0")

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="Edit activity",
                    command=self._edit_activity).pack(side="left")
        ttk.Button(actions, text="Status",
                    command=self._status_activity).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Delete activity",
                    command=self._delete_activity).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Sign student up",
                    command=self._sign_up).pack(side="left",
                                                  padx=(16, 4))
        ttk.Button(actions, text="Attendance +1",
                    command=self._attend).pack(side="left", padx=2)
        ttk.Button(actions, text="Withdraw",
                    command=self._withdraw).pack(side="left", padx=2)
        ttk.Button(actions, text="Complete",
                    command=self._complete).pack(side="left", padx=2)
        ttk.Button(actions, text="Enrolment status",
                    command=self._enr_status).pack(side="left", padx=2)
        ttk.Button(actions, text="Delete enrolment",
                    command=self._delete_enr).pack(side="left", padx=2)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _clear(self) -> None:
        self.f_search.delete(0, "end")
        self.f_cat.current(0)
        self.f_day.current(0)
        self.f_status.current(0)
        self.open_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_activities_with_detail(
                search=self.f_search.get().strip() or None,
                category=self.f_cat.get() or None,
                day_of_week=self.f_day.get() or None,
                status=self.f_status.get() or None,
                open_only=self.open_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for r in rows:
            a = r.activity
            cap = (str(a.capacity) if a.capacity is not None else "—")
            tags = (a.status,) if a.status in ACTIVITY_STATUSES else ()
            self.tree.insert("", "end", iid=str(a.activity_id), values=(
                a.activity_id, a.name, a.category,
                a.when_label, a.lead_staff or "—",
                cap, r.active, a.status,
            ), tags=tags)
        self.count_var.set(f"{len(rows)} activity/activities.")

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
        for i in self.enr_tree.get_children():
            self.enr_tree.delete(i)
        self.detail_var.set(
            "Select an activity on the left.")
        self.subdetail_var.set("")

    def _render_detail(self) -> None:
        for i in self.enr_tree.get_children():
            self.enr_tree.delete(i)
        if self._selected_id is None:
            return
        detail = data.get_activity_detail(self._selected_id)
        if detail is None:
            self._clear_detail()
            return
        a = detail.activity
        self.detail_var.set(f"#{a.activity_id}  {a.name}")
        sub_bits = [
            f"{a.category}",
            f"{a.when_label}",
            f"Lead: {a.lead_staff or '—'}",
            f"Location: {a.location or '—'}",
        ]
        if a.capacity is not None:
            sub_bits.append(f"{detail.active_count}/{a.capacity}"
                              + ("  FULL" if detail.is_full else ""))
        else:
            sub_bits.append(f"{detail.active_count} active")
        sub_bits.append(f"Status: {a.status}")
        if a.cost is not None:
            sub_bits.append(f"Cost: £{a.cost:.2f}")
        self.subdetail_var.set("  ·  ".join(sub_bits))
        names = _name_lookup()
        for e in detail.enrolments:
            tags = (e.status,) if e.status in ENROLMENT_STATUSES else ()
            self.enr_tree.insert("", "end",
                                      iid=str(e.enrolment_id), values=(
                e.enrolment_id, e.student_id,
                names.get(e.student_id, "?"),
                e.status, e.role or "—",
                e.sessions_attended,
                e.last_attended or "—",
            ), tags=tags)

    def _selected_activity(self) -> Activity | None:
        if self._selected_id is None:
            return None
        return data.get_activity(self._selected_id)

    def _selected_enr_id(self) -> int | None:
        sel = self.enr_tree.selection()
        if not sel:
            return None
        return int(sel[0])

    # ── Activity actions ──────────────────────────────────────────
    def _new(self) -> None:
        ActivityDialog(self.frame.winfo_toplevel(),
                          existing=None, on_save=self.refresh)

    def _edit_activity(self) -> None:
        a = self._selected_activity()
        if a is None:
            messagebox.showinfo("Edit",
                                  "Select an activity first.")
            return
        ActivityDialog(self.frame.winfo_toplevel(),
                          existing=a, on_save=self.refresh)

    def _status_activity(self) -> None:
        a = self._selected_activity()
        if a is None:
            messagebox.showinfo("Status",
                                  "Select an activity first.")
            return
        ActivityStatusDialog(self.frame.winfo_toplevel(),
                                a, on_save=self.refresh)

    def _delete_activity(self) -> None:
        a = self._selected_activity()
        if a is None:
            messagebox.showinfo("Delete",
                                  "Select an activity first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete activity #{a.activity_id} ({a.name})? "
                "All enrolments go too."):
            return
        try:
            data.delete_activity(a.activity_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self._selected_id = None
        self.refresh()

    # ── Enrolment actions ─────────────────────────────────────────
    def _sign_up(self) -> None:
        a = self._selected_activity()
        if a is None:
            messagebox.showinfo("Sign up",
                                  "Select an activity first.")
            return
        SignUpDialog(self.frame.winfo_toplevel(),
                       activity=a, on_save=self.refresh)

    def _attend(self) -> None:
        eid = self._selected_enr_id()
        if eid is None:
            messagebox.showinfo("Attendance",
                                  "Select an enrolment first.")
            return
        try:
            data.record_attendance(eid, sessions=1)
        except ValidationError as e:
            messagebox.showerror("Attendance", str(e))
            return
        self.refresh()

    def _withdraw(self) -> None:
        eid = self._selected_enr_id()
        if eid is None:
            messagebox.showinfo("Withdraw",
                                  "Select an enrolment first.")
            return
        if not messagebox.askyesno("Withdraw",
                                     f"Withdraw enrolment #{eid}?"):
            return
        try:
            data.withdraw(eid)
        except ValidationError as e:
            messagebox.showerror("Withdraw", str(e))
            return
        self.refresh()

    def _complete(self) -> None:
        eid = self._selected_enr_id()
        if eid is None:
            messagebox.showinfo("Complete",
                                  "Select an enrolment first.")
            return
        try:
            data.complete(eid)
        except ValidationError as e:
            messagebox.showerror("Complete", str(e))
            return
        self.refresh()

    def _enr_status(self) -> None:
        eid = self._selected_enr_id()
        if eid is None:
            messagebox.showinfo("Status",
                                  "Select an enrolment first.")
            return
        e = data.get_enrolment(eid)
        if e is None:
            return
        EnrolmentStatusDialog(self.frame.winfo_toplevel(),
                                  e, on_save=self.refresh)

    def _delete_enr(self) -> None:
        eid = self._selected_enr_id()
        if eid is None:
            messagebox.showinfo("Delete",
                                  "Select an enrolment first.")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete enrolment #{eid}?"):
            return
        try:
            data.delete_enrolment(eid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Enrolments tab ════════════════════════════════════════════════

class EnrolmentsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Enrolments")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar,
                                       values=("",) + ENROLMENT_STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        self.active_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Active only",
                          variable=self.active_var,
                          command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "activity", "student", "name",
                "status", "attended", "last", "role")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "activity": 220, "student": 80,
                  "name": 180, "status": 100,
                  "attended": 80, "last": 100, "role": 100}
        headings = {"id": "ID", "activity": "Activity",
                    "student": "Student", "name": "Name",
                    "status": "Status", "attended": "Attended",
                    "last": "Last", "role": "Role"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "attended" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Active",    background="#d8f4d8")
        self.tree.tag_configure("Withdrawn", background="#eeeeee")
        self.tree.tag_configure("Completed", background="#eef7ff")
        self.tree.tag_configure("On Hold",   background="#fff7d0")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_enrolments_with_detail(
                student_id=self.f_student.get().strip() or None,
                status=self.f_status.get() or None,
                active_only=self.active_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for r in rows:
            e = r.enrolment
            tags = (e.status,) if e.status in ENROLMENT_STATUSES else ()
            self.tree.insert("", "end", iid=str(e.enrolment_id), values=(
                e.enrolment_id, r.activity_name,
                e.student_id, r.student_name,
                e.status, e.sessions_attended,
                e.last_attended or "—",
                e.role or "—",
            ), tags=tags)
        self.count_var.set(f"{len(rows)} enrolment(s).")


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        ttk.Button(self.frame, text="Refresh",
                    command=self.refresh).pack(side="top", anchor="w",
                                                 padx=8, pady=(8, 4))
        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        summ = data.summary()
        lines = [
            f"Total activities  : {summ.total_activities}",
            f"Open              : {summ.open_count}",
            f"Full              : {summ.full_activities}",
            f"Enrolments        : {summ.total_enrolments}",
            f"Active enrolments : {summ.active_enrolments}",
            f"Students engaged  : {summ.students_engaged}",
            "",
            "By status:",
        ]
        for s in ACTIVITY_STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("By category:")
        for c in CATEGORIES:
            n = summ.by_category.get(c, 0)
            if n:
                lines.append(f"  {c:<26} : {n}")
        if summ.by_day:
            lines.append("")
            lines.append("By day:")
            for d, n in summ.by_day.items():
                lines.append(f"  {d:<14} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class ActivityStatusDialog:
    def __init__(self, parent: tk.Misc, existing: Activity,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — activity #{existing.activity_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=ACTIVITY_STATUSES,
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
            data.set_activity_status(
                self.existing.activity_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class EnrolmentStatusDialog:
    def __init__(self, parent: tk.Misc, existing: Enrolment,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — enrolment #{existing.enrolment_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=ENROLMENT_STATUSES,
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
            data.set_enrolment_status(
                self.existing.enrolment_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class SignUpDialog:
    def __init__(self, parent: tk.Misc, *, activity: Activity,
                 on_save: Callable[[], None]) -> None:
        self.activity = activity
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Sign up — {activity.name}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        # Show capacity status
        detail = data.get_activity_detail(self.activity.activity_id)
        info = (f"Active: {detail.active_count if detail else 0}"
                + (f" / {self.activity.capacity}"
                   if self.activity.capacity is not None else "")
                + ("  [FULL]"
                   if detail and detail.is_full else ""))
        ttk.Label(form, text=info, foreground="#555").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        opts = _student_options()
        self._ids = [s for s, _ in opts]
        ttk.Label(form, text="Student:").grid(row=1, column=0,
                                                 sticky="e", pady=4)
        self.student_cb = ttk.Combobox(
            form, values=[l for _, l in opts],
            state="readonly", width=44)
        if opts:
            self.student_cb.current(0)
        self.student_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Role:").grid(row=2, column=0,
                                              sticky="e", pady=4)
        self.role_e = ttk.Entry(form, width=24)
        self.role_e.grid(row=2, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Sign up",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.student_cb.current()
        if idx < 0:
            messagebox.showerror("Sign up", "Pick a student.")
            return
        try:
            data.sign_up(
                self.activity.activity_id,
                self._ids[idx],
                role=self.role_e.get().strip() or None,
            )
        except (ValidationError, Exception) as e:
            messagebox.showerror("Sign up failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ActivityDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Activity | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Activity" if existing
                          else "New Activity")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        def add_row(label: str, widget: tk.Widget,
                     extra: tk.Widget | None = None,
                     extra_label: str | None = None) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            widget.grid(row=r, column=1, sticky="w", padx=6)
            if extra is not None:
                ttk.Label(form, text=extra_label).grid(
                    row=r, column=2, sticky="e", pady=3)
                extra.grid(row=r, column=3, sticky="w", padx=6)
            r += 1

        self.name_e = ttk.Entry(form, width=36)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        add_row("Name:", self.name_e)

        self.category_cb = ttk.Combobox(form, values=CATEGORIES,
                                           state="readonly", width=24)
        self.category_cb.set(self.existing.category
                                if self.existing else DEFAULT_CATEGORY)
        self.status_cb = ttk.Combobox(form, values=ACTIVITY_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_ACTIVITY_STATUS)
        add_row("Category:", self.category_cb,
                  self.status_cb, "Status:")

        self.day_cb = ttk.Combobox(form, values=("",) + DAYS,
                                      state="readonly", width=12)
        self.day_cb.set((self.existing.day_of_week or "")
                          if self.existing else "")
        self.year_cb = ttk.Combobox(form, values=("",) + YEAR_GROUPS,
                                       state="readonly", width=10)
        self.year_cb.set((self.existing.year_group or "")
                            if self.existing else "")
        add_row("Day:", self.day_cb, self.year_cb, "Year:")

        self.start_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.start_time:
            self.start_e.insert(0, self.existing.start_time[:5])
        self.end_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.end_time:
            self.end_e.insert(0, self.existing.end_time[:5])
        add_row("Start time:", self.start_e,
                  self.end_e, "End time:")

        self.location_e = ttk.Entry(form, width=36)
        if self.existing and self.existing.location:
            self.location_e.insert(0, self.existing.location)
        add_row("Location:", self.location_e)

        self.lead_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.lead_staff:
            self.lead_e.insert(0, self.existing.lead_staff)
        add_row("Lead staff:", self.lead_e)

        self.capacity_e = ttk.Entry(form, width=8)
        if self.existing and self.existing.capacity is not None:
            self.capacity_e.insert(0, str(self.existing.capacity))
        self.cost_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.cost is not None:
            self.cost_e.insert(0, f"{self.existing.cost:.2f}")
        add_row("Capacity:", self.capacity_e,
                  self.cost_e, "Cost (£):")

        self.term_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.term:
            self.term_e.insert(0, self.existing.term)
        add_row("Term:", self.term_e)

        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                     sticky="ne", pady=3)
        self.desc_t = tk.Text(form, width=50, height=4)
        if self.existing and self.existing.description:
            self.desc_t.insert("1.0", self.existing.description)
        self.desc_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=50, height=3)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        return {
            "name":        self.name_e.get().strip(),
            "category":    self.category_cb.get().strip(),
            "day_of_week": self.day_cb.get().strip() or None,
            "start_time":  self.start_e.get().strip() or None,
            "end_time":    self.end_e.get().strip() or None,
            "location":    self.location_e.get().strip(),
            "lead_staff":  self.lead_e.get().strip(),
            "capacity":    self.capacity_e.get().strip() or None,
            "cost":        self.cost_e.get().strip() or None,
            "year_group":  self.year_cb.get().strip() or None,
            "term":        self.term_e.get().strip(),
            "status":      self.status_cb.get().strip(),
            "description": self.desc_t.get("1.0", "end").strip(),
            "notes":       self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_activity(
                    self.existing.activity_id, payload)
            else:
                data.create_activity(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
