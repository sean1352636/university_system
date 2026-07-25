"""Tkinter views for Secondary School Departments."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.secondary.domain.staff.departments import (
    departments as data,
)
from education_system.systems.secondary.domain.staff.departments.departments import (
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
from education_system.systems.secondary.domain.staff import (
    staff as staff_data,
)

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
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Departments — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    DepartmentsTab(nb, scope="active",      label="Active")
    DepartmentsTab(nb, scope="over_budget", label="Over Budget")
    DepartmentsTab(nb, scope="all",         label="All Departments")
    PerStaffTab(nb)
    SummaryTab(nb)


def _staff_options() -> list[tuple[str | None, str]]:
    rows = sorted(staff_data.list_staff(),
                   key=lambda s: s.staff_id)
    opts: list[tuple[str | None, str]] = [(None, "(none)")]
    for s in rows:
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        opts.append((s.staff_id,
                       f"{s.staff_id} — {full}"))
    return opts


def _staff_options_required() -> list[tuple[str, str]]:
    rows = sorted(staff_data.list_staff(),
                   key=lambda s: s.staff_id)
    return [(s.staff_id,
             f"{s.staff_id} — "
             f"{getattr(s, 'first_name', '')} "
             f"{getattr(s, 'last_name', '')}".strip())
            for s in rows]


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
        self.f_fac = ttk.Combobox(bar, values=("",) + FACULTIES,
                                    state="readonly", width=22)
        self.f_fac.current(0)
        self.f_fac.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=14)
            self.f_status.current(0)
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
        amt = _prompt_text(self.frame, "Amount (£)")
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
        when = _prompt_text(self.frame, "Left on (YYYY-MM-DD)",
                              initial=_dt.date.today().isoformat())
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
        self.combo = ttk.Combobox(bar, state="readonly", width=42)
        opts = _staff_options_required()
        self._opts = opts
        self.combo["values"] = [lbl for _, lbl in opts]
        self.combo.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Show",
                    command=self._show).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.text.config(state="disabled")

    def _show(self) -> None:
        idx = self.combo.current()
        if idx < 0:
            return
        sid = self._opts[idx][0]
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
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit dept #{department.department_id}"
                          if department else "New department")
        self.win.geometry("820x780")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if department:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
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
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(0, 0, "Name*", "name", width=48)
        entry(1, 0, "Code", "code")
        combo(1, 2, "Faculty*", "faculty", FACULTIES)

        ttk.Label(body, text="Head of Dept").grid(
            row=2, column=0, sticky="w", padx=4, pady=2)
        self.hod_combo = ttk.Combobox(body, state="readonly",
                                          width=42)
        opts = _staff_options()
        self._staff_opts = opts
        self.hod_combo["values"] = [lbl for _, lbl in opts]
        self.hod_combo.current(0)
        self.hod_combo.grid(row=2, column=1, sticky="ew",
                                padx=4, pady=2)

        ttk.Label(body, text="Deputy Head").grid(
            row=2, column=2, sticky="w", padx=4, pady=2)
        self.deputy_combo = ttk.Combobox(body, state="readonly",
                                              width=42)
        self.deputy_combo["values"] = [lbl for _, lbl in opts]
        self.deputy_combo.current(0)
        self.deputy_combo.grid(row=2, column=3, sticky="ew",
                                    padx=4, pady=2)

        entry(3, 0, "Location", "location")
        combo(3, 2, "Status*", "status", STATUSES)
        entry(4, 0, "Budget year", "budget_year")
        entry(4, 2, "Budget total (£)", "budget_total")
        entry(5, 0, "Budget allocated (£)", "budget_allocated")
        entry(5, 2, "Budget spent (£)", "budget_spent")
        entry(6, 0, "Subjects", "subject_codes", width=48)

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

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
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
        for i, (sid, _) in enumerate(self._staff_opts):
            if sid == d.head_of_department:
                self.hod_combo.current(i)
            if sid == d.deputy_head:
                self.deputy_combo.current(i)
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(d, k) or "")

    def _save(self) -> None:
        hidx = self.hod_combo.current()
        didx = self.deputy_combo.current()
        payload: dict = {
            "head_of_department":
                self._staff_opts[hidx][0] if hidx >= 0 else None,
            "deputy_head":
                self._staff_opts[didx][0] if didx >= 0 else None,
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
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit membership #{membership.membership_id}"
                          if membership else "New membership")
        self.win.geometry("560x500")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Staff*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.staff_combo = ttk.Combobox(body, state="readonly",
                                            width=42)
        opts = _staff_options_required()
        self._staff_opts = opts
        self.staff_combo["values"] = [lbl for _, lbl in opts]
        self.staff_combo.grid(row=0, column=1, sticky="ew",
                                  padx=4, pady=4)
        ttk.Label(body, text="Role*").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.role = tk.StringVar(value=DEFAULT_DEPT_ROLE)
        ttk.Combobox(body, textvariable=self.role,
                      values=DEPT_ROLES, state="readonly").grid(
            row=1, column=1, sticky="ew", padx=4, pady=4)
        self.is_primary = tk.BooleanVar()
        ttk.Checkbutton(body, text="Primary department",
                         variable=self.is_primary).grid(
            row=2, column=0, columnspan=2, sticky="w",
            padx=4, pady=4)
        ttk.Label(body, text="Joined on").grid(
            row=3, column=0, sticky="w", padx=4, pady=4)
        self.joined = tk.StringVar(
            value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.joined,
                    width=14).grid(
            row=3, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Left on").grid(
            row=4, column=0, sticky="w", padx=4, pady=4)
        self.left = tk.StringVar()
        ttk.Entry(body, textvariable=self.left, width=14).grid(
            row=4, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Notes").grid(
            row=5, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=6, width=42,
                                wrap="word")
        self.notes.grid(row=5, column=1, sticky="ew",
                          padx=4, pady=4)

        if membership:
            for i, (sid, _) in enumerate(self._staff_opts):
                if sid == membership.staff_id:
                    self.staff_combo.current(i)
                    break
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
        idx = self.staff_combo.current()
        if idx < 0:
            messagebox.showerror("Departments",
                                    "Pick a staff member.",
                                    parent=self.win)
            return
        payload = {
            "staff_id": self._staff_opts[idx][0],
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


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var).pack(fill="x", padx=8)
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
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("320x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
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
