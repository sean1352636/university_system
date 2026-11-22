"""Tkinter views for Primary School Departments."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.primary.domain.staff.departments import (
    departments as data,
)
from education_system.systems.primary.domain.staff.departments.departments import (
    DEFAULT_DEPT_ROLE,
    DEFAULT_FACULTY,
    DEFAULT_STATUS,
    DEPT_ROLES,
    Department,
    FACULTIES,
    Membership,
    STATUSES,
    ValidationError,
)
from education_system.systems.primary.interfaces.gui import kit

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Active":        ("#e6f7e6", "#0d6b2a"),
    "Restructuring": ("#fff7e6", "#7a5800"),
    "Merged":        ("#e6e6ff", "#3a3a8c"),
    "Disbanded":     ("#ffd1d1", "#8c0d0d"),
    "Archived":      ("#eeeeee", "#444444"),
}


def open_departments_window(parent=None) -> None:
    data.init_db()
    if parent is None:
        # Run on its own (no main window): a standalone window as before.
        win = tk.Tk()
        win.title(f"Departments — {branding.SYSTEM_NAME}")
        win.geometry(WIN_GEOMETRY)
        win.minsize(*WIN_MINSIZE)
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        _draw_departments(frame, None)
        return
    kit.show_page(parent, "Departments",
                  lambda page: _draw_departments(page, parent))


def _draw_departments(parent, host) -> None:
    kit.page_heading(parent, "Departments",
                     "Departments and faculties: heads, budgets and "
                     "staff memberships.")
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    DepartmentsTab(nb, scope="active",      label="Active")
    DepartmentsTab(nb, scope="over_budget", label="Over Budget")
    DepartmentsTab(nb, scope="all",         label="All Departments")
    PerStaffTab(nb)
    SummaryTab(nb)


def _subject_code_choices() -> list[tuple[str, str]]:
    try:
        from education_system.systems.primary.domain.academics.subjects import (
            subjects,
        )
        return [(s.code, f"{s.name} ({s.code})") for s in subjects.list_all()
                if s.code]
    except Exception:  # noqa: BLE001 - an empty list beats a broken form
        logger.exception("subject list for departments failed")
        return []


def _pick_subject_codes(owner, var: tk.StringVar) -> None:
    """Tick subjects from the list; writes them comma-separated into
    *var* (the format the Subjects field has always held)."""
    current = [c.strip() for c in var.get().split(",") if c.strip()]
    choices = _subject_code_choices()
    known = {v for v, _l in choices}
    choices += [(c, c) for c in current if c not in known]
    win, frm = kit.dialog(owner, "Subjects")
    win.transient(owner.winfo_toplevel()); win.after_idle(win.grab_set)
    picker = kit.MultiPicker(frm, choices, selected=current, height=12)
    picker.pack(fill="both", expand=True)

    def ok() -> None:
        var.set(", ".join(picker.get()))
        win.destroy()

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 0))
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    win.wait_window()


# ── Departments tab ─────────────────────────────────────

class DepartmentsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        paned = ttk.PanedWindow(self.frame, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=8)
        self.top = ttk.Frame(paned)
        self.bottom = ttk.Frame(paned)
        paned.add(self.top, weight=3)
        paned.add(self.bottom, weight=2)
        self._build_top()
        self._build_bottom()
        self.refresh()

    def _build_top(self) -> None:
        bar = ttk.Frame(self.top)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Faculty:").pack(side="left")
        self.f_fac = kit.ChoiceField(bar, tk.StringVar(), choices=FACULTIES,
                                     blank=True, width=22)
        self.f_fac.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = kit.ChoiceField(bar, tk.StringVar(),
                                            choices=STATUSES, blank=True,
                                            width=14)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Name:").pack(side="left")
        self.f_name = ttk.Entry(bar, width=20)
        self.f_name.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New department",
                    command=self._new).pack(side="left",
                                                padx=(16, 0))

        table_frame = ttk.Frame(self.top)
        table_frame.pack(fill="both", expand=True)
        cols = ("id", "name", "code", "faculty", "hod",
                "deputy", "budget", "members", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "name": 220, "code": 70,
                   "faculty": 200, "hod": 110, "deputy": 110,
                   "budget": 180, "members": 80, "status": 120}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "members")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("over_budget",
                                   background="#ffd1d1",
                                   foreground="#8c0d0d")
        self.tree.bind("<<TreeviewSelect>>",
                         lambda _e: self._refresh_members())
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.top)
        actions.pack(fill="x", pady=(4, 0))
        for label, cmd in (
                ("Edit",          self._edit),
                ("Change status", self._set_status),
                ("Add spend",     self._add_spend),
                ("Delete",        self._delete),
                ("Refresh",       self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _build_bottom(self) -> None:
        bar = ttk.Frame(self.bottom)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Members").pack(side="left")
        ttk.Button(bar, text="Add",
                    command=self._add_member).pack(side="right",
                                                       padx=4)
        ttk.Button(bar, text="End",
                    command=self._end_member).pack(side="right",
                                                       padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_member).pack(side="right",
                                                        padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_member).pack(side="right",
                                                          padx=4)

        table_frame = ttk.Frame(self.bottom)
        table_frame.pack(fill="both", expand=True)
        cols = ("id", "primary", "staff", "role",
                "joined", "left", "notes")
        self.mtree = ttk.Treeview(table_frame, columns=cols,
                                       show="headings",
                                       selectmode="browse")
        widths = {"id": 50, "primary": 60, "staff": 110,
                   "role": 200, "joined": 100, "left": 100,
                   "notes": 240}
        for c in cols:
            self.mtree.heading(c,
                                   text=c.replace("_", " ").title())
            self.mtree.column(c, width=widths[c],
                                  anchor=("center"
                                           if c in ("id", "primary")
                                           else "w"))
        mvsb = ttk.Scrollbar(table_frame, orient="vertical",
                                command=self.mtree.yview)
        self.mtree.configure(yscrollcommand=mvsb.set)
        self.mtree.pack(side="left", fill="both", expand=True)
        mvsb.pack(side="right", fill="y")
        self.mtree.bind("<Double-Button-1>",
                            lambda _e: self._edit_member())

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_fac.get():
            f["faculty"] = self.f_fac.get()
        if self.f_name.get().strip():
            f["name_like"] = self.f_name.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "active":
            f["active_only"] = True
        elif self.scope == "over_budget":
            f["over_budget"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_departments(**self._filters())
        for d in rows:
            if d.budget_total is not None:
                spent = d.budget_spent or 0.0
                budget = (f"£{spent:.0f}/£{d.budget_total:.0f}")
                if d.budget_over:
                    budget += "  OVER"
            else:
                budget = "—"
            members = data.member_count(d.department_id)
            tag = ("over_budget" if d.budget_over else d.status)
            self.tree.insert(
                "", "end", iid=str(d.department_id),
                values=(d.department_id, d.name,
                         d.code or "—", d.faculty,
                         d.head_of_department or "—",
                         d.deputy_head or "—",
                         budget, members, d.status),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} department(s)")
        self._refresh_members()

    def _selected(self) -> Department | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Departments",
                                  "Select a department first.",
                                  parent=self.frame)
            return None
        return data.get_department(int(sel[0]))

    def _refresh_members(self) -> None:
        for iid in self.mtree.get_children():
            self.mtree.delete(iid)
        sel = self.tree.selection()
        if not sel:
            return
        did = int(sel[0])
        for m in data.list_memberships(did):
            notes = (m.notes.splitlines()[0]
                       if m.notes else "")
            self.mtree.insert(
                "", "end", iid=str(m.membership_id),
                values=(m.membership_id,
                         "yes" if m.is_primary else "",
                         m.staff_id, m.role_in_department,
                         m.joined_on, m.left_on or "—",
                         notes))

    def _selected_member(self) -> Membership | None:
        sel = self.mtree.selection()
        if not sel:
            return None
        return data.get_membership(int(sel[0]))

    def _new(self) -> None:
        if DepartmentEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        d = self._selected()
        if d and DepartmentEditor(
                self.frame, department=d).result is not None:
            self.refresh()

    def _set_status(self) -> None:
        d = self._selected()
        if not d:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=d.status)
        if not new:
            return
        try:
            data.set_status(d.department_id, new)
        except ValidationError as exc:
            messagebox.showerror("Departments", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _add_spend(self) -> None:
        d = self._selected()
        if not d:
            return
        amt = _prompt_value(
            self.frame, "Amount (£)",
            make=lambda m, v: kit.NumberField(m, v, increment=0.01,
                                              to=999999, width=12))
        if not amt:
            return
        try:
            data.add_spend(d.department_id, amount=float(amt))
        except (ValueError, ValidationError) as exc:
            messagebox.showerror("Departments", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        d = self._selected()
        if not d:
            return
        if not messagebox.askyesno(
                "Departments",
                f"Delete department #{d.department_id} "
                "(and all memberships)?", parent=self.frame):
            return
        data.delete_department(d.department_id)
        self.refresh()

    def _add_member(self) -> None:
        d = self._selected()
        if not d:
            return
        if MembershipEditor(
                self.frame,
                department_id=d.department_id).result is not None:
            self._refresh_members()
            self.refresh()

    def _edit_member(self) -> None:
        d = self._selected()
        m = self._selected_member()
        if not d or not m:
            messagebox.showinfo("Departments",
                                  "Select a membership first.",
                                  parent=self.frame)
            return
        if MembershipEditor(
                self.frame,
                department_id=d.department_id,
                membership=m).result is not None:
            self._refresh_members()
            self.refresh()

    def _end_member(self) -> None:
        m = self._selected_member()
        if not m:
            return
        when = _prompt_value(self.frame, "Left on",
                             initial=_dt.date.today().isoformat(),
                             make=lambda m, v: kit.DateField(m, v))
        if not when:
            return
        try:
            data.end_membership(m.membership_id, left_on=when)
        except ValidationError as exc:
            messagebox.showerror("Departments", str(exc),
                                    parent=self.frame)
            return
        self._refresh_members()
        self.refresh()

    def _delete_member(self) -> None:
        m = self._selected_member()
        if not m:
            return
        if not messagebox.askyesno(
                "Departments",
                f"Delete membership #{m.membership_id}?",
                parent=self.frame):
            return
        data.delete_membership(m.membership_id)
        self._refresh_members()
        self.refresh()


class PerStaffTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per Staff")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Staff:").pack(side="left")
        self.staff_var = tk.StringVar()
        self.combo = kit.StaffPicker(bar, self.staff_var, active_only=False,
                                     width=42)
        self.combo.bind_change(lambda _v: self._show())
        self.combo.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Show",
                    command=self._show).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.text.config(state="disabled")

    def _show(self) -> None:
        sid = self.staff_var.get().strip()
        if not sid:
            return
        rows = data.memberships_for_staff(sid)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end",
                            f"Department memberships for {sid}\n"
                            f"{'=' * 60}\n\n"
                            f"Total: {len(rows)}\n\n")
        for m in rows:
            d = data.get_department(m.department_id)
            name = d.name if d else f"#{m.department_id}"
            flag = "PRIMARY  " if m.is_primary else ""
            self.text.insert("end",
                                f"  {flag}{name}\n"
                                f"    {m.role_in_department}  "
                                f"({m.joined_on} → "
                                f"{m.left_on or 'current'})\n")
            if m.notes:
                self.text.insert("end", f"    {m.notes}\n")
            self.text.insert("end", "\n")
        self.text.config(state="disabled")


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Departments Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total departments   : {s.total}\n"
                            f"Active              : {s.active}\n"
                            f"Restructuring       : {s.restructuring}\n"
                            f"Disbanded           : {s.disbanded}\n"
                            f"Total members       : {s.total_members}\n"
                            f"Distinct staff      : {s.distinct_staff}\n"
                            f"Budget total        : £{s.budget_total:.2f}\n"
                            f"Budget spent        : £{s.budget_spent:.2f}\n"
                            f"Over budget         : {s.budget_over_count}\n\n")
        self.text.insert("end", "By faculty:\n")
        for k in FACULTIES:
            n = s.by_faculty.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<26}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editors ──────────────────────────────────────────────

class DepartmentEditor:
    def __init__(self, parent, *,
                 department: Department | None = None) -> None:
        self.department = department
        self.result: Department | None = None
        self.win = tk.Toplevel(parent.winfo_toplevel())
        self.win.title(f"Edit dept #{department.department_id}"
                          if department else "New department")
        self.win.geometry("900x680")
        self.win.transient(parent.winfo_toplevel()); self.win.after_idle(self.win.grab_set)
        self._build()
        if department:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body, footer = kit.scrolled_form(self.win)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            kit.ChoiceField(body, v, choices=values, width=width).grid(
                row=row, column=col + 1, sticky="w", padx=4, pady=2)

        def money(row, col, label, key):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            kit.NumberField(body, v, increment=0.01, to=9999999,
                            width=12).grid(
                row=row, column=col + 1, sticky="w", padx=4, pady=2)

        entry(0, 0, "Name*", "name", width=48)
        entry(1, 0, "Code", "code")
        combo(1, 2, "Faculty*", "faculty", FACULTIES)

        ttk.Label(body, text="Head of Dept").grid(
            row=2, column=0, sticky="w", padx=4, pady=2)
        self.hod_var = tk.StringVar()
        kit.StaffPicker(body, self.hod_var, active_only=False,
                        width=30).grid(row=2, column=1, sticky="w",
                                       padx=4, pady=2)

        ttk.Label(body, text="Deputy Head").grid(
            row=2, column=2, sticky="w", padx=4, pady=2)
        self.deputy_var = tk.StringVar()
        kit.StaffPicker(body, self.deputy_var, active_only=False,
                        width=30).grid(row=2, column=3, sticky="w",
                                       padx=4, pady=2)

        entry(3, 0, "Location", "location")
        combo(3, 2, "Status*", "status", STATUSES)
        ttk.Label(body, text="Budget year").grid(
            row=4, column=0, sticky="w", padx=4, pady=2)
        self.vars["budget_year"] = tk.StringVar()
        kit.AcademicYearPicker(body, self.vars["budget_year"],
                               blank=True).grid(
            row=4, column=1, sticky="w", padx=4, pady=2)
        money(4, 2, "Budget total (£)", "budget_total")
        money(5, 0, "Budget allocated (£)", "budget_allocated")
        money(5, 2, "Budget spent (£)", "budget_spent")
        entry(6, 0, "Subjects", "subject_codes", width=48)
        ttk.Button(body, text="Pick…",
                   command=lambda: _pick_subject_codes(
                       self.win, self.vars["subject_codes"])).grid(
            row=6, column=2, sticky="w", padx=4, pady=2)

        row = 7
        for key, label in (
                ("aims",     "Aims"),
                ("policies", "Policies"),
                ("notes",    "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=3, width=74, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = footer
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["faculty"].set(DEFAULT_FACULTY)
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        d = self.department
        assert d is not None
        for key in ("name", "code", "faculty", "location",
                     "budget_year", "subject_codes", "status"):
            self.vars[key].set(getattr(d, key) or "")
        self.vars["budget_total"].set(
            str(d.budget_total)
            if d.budget_total is not None else "")
        self.vars["budget_allocated"].set(
            str(d.budget_allocated)
            if d.budget_allocated is not None else "")
        self.vars["budget_spent"].set(
            str(d.budget_spent)
            if d.budget_spent is not None else "")
        self.hod_var.set(d.head_of_department or "")
        self.deputy_var.set(d.deputy_head or "")
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(d, k) or "")

    def _save(self) -> None:
        payload: dict = {
            "head_of_department": self.hod_var.get().strip() or None,
            "deputy_head": self.deputy_var.get().strip() or None,
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.department:
                self.result = data.update_department(
                    self.department.department_id, payload)
            else:
                self.result = data.create_department(payload)
        except ValidationError as exc:
            messagebox.showerror("Departments", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class MembershipEditor:
    def __init__(self, parent, *,
                 department_id: int,
                 membership: Membership | None = None) -> None:
        self.department_id = department_id
        self.membership = membership
        self.result: Membership | None = None
        self.win = tk.Toplevel(parent.winfo_toplevel())
        self.win.title(f"Edit membership #{membership.membership_id}"
                          if membership else "New membership")
        self.win.geometry("620x500")
        self.win.transient(parent.winfo_toplevel()); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Staff*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.staff_var = tk.StringVar()
        kit.StaffPicker(body, self.staff_var, active_only=False,
                        width=42).grid(row=0, column=1, sticky="w",
                                       padx=4, pady=4)
        ttk.Label(body, text="Role*").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.role = tk.StringVar(value=DEFAULT_DEPT_ROLE)
        kit.ChoiceField(body, self.role, choices=DEPT_ROLES).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        self.is_primary = tk.BooleanVar()
        ttk.Checkbutton(body, text="Primary department",
                         variable=self.is_primary).grid(
            row=2, column=0, columnspan=2, sticky="w",
            padx=4, pady=4)
        ttk.Label(body, text="Joined on").grid(
            row=3, column=0, sticky="w", padx=4, pady=4)
        self.joined = tk.StringVar(
            value=_dt.date.today().isoformat())
        kit.DateField(body, self.joined).grid(
            row=3, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Left on").grid(
            row=4, column=0, sticky="w", padx=4, pady=4)
        self.left = tk.StringVar()
        kit.DateField(body, self.left).grid(
            row=4, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Notes").grid(
            row=5, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=6, width=42,
                                wrap="word")
        self.notes.grid(row=5, column=1, sticky="ew",
                          padx=4, pady=4)

        if membership:
            self.staff_var.set(membership.staff_id or "")
            self.role.set(membership.role_in_department)
            self.is_primary.set(membership.is_primary)
            self.joined.set(membership.joined_on)
            self.left.set(membership.left_on or "")
            self.notes.insert("1.0", membership.notes or "")

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        staff_id = self.staff_var.get().strip()
        if not staff_id:
            messagebox.showerror("Departments",
                                    "Pick a staff member.",
                                    parent=self.win)
            return
        payload = {
            "staff_id": staff_id,
            "role_in_department": self.role.get(),
            "is_primary": self.is_primary.get(),
            "joined_on": self.joined.get().strip(),
            "left_on": self.left.get().strip() or None,
            "notes": self.notes.get("1.0", "end").rstrip()
            or None,
        }
        try:
            if self.membership:
                self.result = data.update_membership(
                    self.membership.membership_id, payload)
            else:
                self.result = data.add_member(
                    self.department_id, payload)
        except ValidationError as exc:
            messagebox.showerror("Departments", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_value(parent, title: str, *, initial: str = "",
                  make) -> str | None:
    """A small modal asking for one value; *make(master, var)* builds the
    picker bound to *var*. Returns the value, or None on Cancel."""
    owner = parent.winfo_toplevel()
    win = tk.Toplevel(owner)
    win.title(title); win.geometry("460x150")
    win.transient(owner); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    make(win, var).pack(anchor="w", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent.winfo_toplevel())
    win.title(title); win.geometry("320x140")
    win.transient(parent.winfo_toplevel()); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default or (options[0] if options else ""))
    kit.ChoiceField(win, var, choices=options).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_departments_window"]
