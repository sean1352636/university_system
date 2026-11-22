"""Departments screen.

The old Departments window's tabs are kept: Active, Over Budget and All
Departments (each with the Faculty / Status / Name filter, Apply, New
department; columns ID, Name, Code, Faculty, HoD, Deputy, Budget, Members,
Status; Edit, Change status, Add spend, Delete, Refresh; and the Members
list below with Add, End, Edit, Delete), Per Staff (Staff, Show) and
Summary (Refresh). The department form keeps every old field (name, code,
faculty, head of dept, deputy head, location, budget year / total /
allocated / spent, aims, policies, status, notes); the member form keeps
Staff, Role, Primary department, Joined on, Left on, Notes.

Added: people are picked from the Staff Directory; Subjects (add / remove a
subject, which sets the subject's department; Import from subjects), Export
CSV and History on each list. New tabs: Overview (staff, subjects, teaching
groups and counts for a department) and Meetings (minutes and actions - the
head of department runs their own). Rules: :mod:`modules.staff.domain.departments`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.staff.domain import departments as DP
from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = W.ERRORS
_form = W.form_dialog
_TITLE = "Departments"
_STATUS_TAGS = {"Active": "#e7f6ea", "Restructuring": "#fff4d6", "Merged": "#e6f2ff",
                "Disbanded": "#eeeeee", "Archived": "#eeeeee"}


def _staff_kind() -> tuple:
    return ("edit", ["", *SD.choices()])


def _label(staff_id: int | None) -> str:
    m = SD.find(staff_id) if staff_id else None
    return m.label if m else ""


def _dept_fields(d: DP.Department | None) -> list:
    g = _getter(d)
    return [
        ("name", "Name*", g("name"), None), ("code", "Code", g("code"), None),
        ("faculty", "Faculty", g("faculty", DP.DEFAULT_FACULTY), DP.FACULTIES),
        ("head_id", "Head of Dept", _label(d.head_id) if d else "", _staff_kind()),
        ("second_id", "Deputy Head (2nd in dept)", _label(d.second_id) if d else "",
         _staff_kind()),
        ("location", "Location", g("location"), None),
        ("budget_year", "Budget year", g("budget_year"), None),
        ("budget_total", "Budget total (£)", g("budget_total"), None),
        ("budget_allocated", "Budget allocated (£)", g("budget_allocated"), None),
        ("budget_spent", "Budget spent (£)", g("budget_spent"), None),
        ("aims", "Aims", g("aims"), "text"), ("policies", "Policies", g("policies"), "text"),
        ("status", "Status", g("status", DP.DEFAULT_STATUS), DP.STATUSES),
        ("notes", "Notes", g("notes"), "text")]


def _member_fields(m: DP.Membership | None) -> list:
    out = [] if m else [("staff_id", "Staff*", "", _staff_kind())]
    return out + [
        ("role_in_department", "Role*", m.role_in_department if m else DP.DEFAULT_DEPT_ROLE,
         DP.DEPT_ROLES),
        ("is_primary", "Primary department", m.is_primary if m else False, "check"),
        ("joined_on", "Joined on (blank = today)", m.joined_on if m else "", None),
        ("left_on", "Left on", (m.left_on or "") if m else "", None),
        ("notes", "Notes", (m.notes or "") if m else "", "text")]


def _getter(obj: Any):
    """g(key, default) - the field's value, or *default* when blank / no record."""
    def g(key: str, default: Any = "") -> Any:
        v = None if obj is None else getattr(obj, key)
        return default if v is None else v
    return g


def _diff(obj: Any, values: dict[str, Any], resolve: dict[str, Any] | None = None
          ) -> dict[str, Any]:
    out = {}
    for k, v in values.items():
        cur = getattr(obj, k)
        if resolve and k in resolve:
            cur = resolve[k]
        if str(v if v is not None else "") != str(cur if cur is not None else ""):
            out[k] = v
    return out


class _DepartmentList:
    """One of the old Active / Over Budget / All Departments tabs."""

    def __init__(self, page: DepartmentsPage, tab: ttk.Frame, scope: str) -> None:
        self.page, self.scope = page, scope
        paned = ttk.PanedWindow(tab, orient="vertical")
        paned.pack(fill="both", expand=True)
        top, bottom = ttk.Frame(paned), ttk.Frame(paned)
        paned.add(top, weight=3)
        paned.add(bottom, weight=2)
        bar = ttk.Frame(top)
        bar.pack(fill="x", pady=(0, 4))
        self.f_fac = tk.StringVar()
        self.f_status = tk.StringVar()
        self.f_name = tk.StringVar()
        ttk.Label(bar, text="Faculty:").pack(side="left")
        ttk.Combobox(bar, textvariable=self.f_fac, values=["", *DP.FACULTIES],
                     state="readonly", width=22).pack(side="left", padx=(2, 8))
        if scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            ttk.Combobox(bar, textvariable=self.f_status, values=["", *DP.STATUSES],
                         state="readonly", width=14).pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Name:").pack(side="left")
        ttk.Entry(bar, textvariable=self.f_name, width=20).pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply", command=self.refresh).pack(side="left", padx=4)
        page._button(bar, "New department", self.new, True).pack_configure(padx=(16, 0))
        self.tree = W.tree(top, [("id", "Id", 50), ("name", "Name", 200), ("code", "Code", 70),
                                 ("faculty", "Faculty", 170), ("hod", "Hod", 130),
                                 ("deputy", "Deputy", 130), ("budget", "Budget", 150),
                                 ("members", "Members", 70), ("status", "Status", 110)],
                           height=10, stretch={"name"},
                           tags={**_STATUS_TAGS, "over_budget": {"background": "#ffd1d1",
                                                                 "foreground": "#8c0d0d"}})
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.refresh_members())
        self.tree.bind("<Double-Button-1>", lambda _e: self.edit())
        acts = ttk.Frame(top)
        acts.pack(fill="x", pady=(4, 0))
        for text, cmd, ed in (("Edit", self.edit, True), ("Change status", self.set_status, True),
                              ("Add spend", self.add_spend, True), ("Delete", self.delete, True),
                              ("Refresh", self.refresh, False),
                              ("Subjects…", self.subjects, False),
                              ("History", self.history, False)):
            page._button(acts, text, cmd, ed)
        self.count = ttk.Label(acts, text="")
        self.count.pack(side="right")
        mbar = ttk.Frame(bottom)
        mbar.pack(fill="x", pady=(4, 4))
        ttk.Label(mbar, text="Members").pack(side="left")
        for text, cmd in (("Add", self.add_member), ("End", self.end_member),
                          ("Edit", self.edit_member), ("Delete", self.delete_member)):
            b = ttk.Button(mbar, text=text, command=cmd)
            if not page.editor:
                b.state(["disabled"])
            b.pack(side="right", padx=4)
        self.mtree = W.tree(bottom, [("id", "Id", 50), ("primary", "Primary", 60),
                                     ("staff", "Staff", 200), ("role", "Role", 180),
                                     ("joined", "Joined", 100), ("left", "Left", 100),
                                     ("notes", "Notes", 240)], height=6, stretch={"notes"},
                            tags=W.STANDARD_TAGS)
        self.rows: dict[str, DP.Department] = {}
        self.mrows: dict[str, DP.Membership] = {}
        self.refresh()

    def refresh(self) -> None:
        kw: dict[str, Any] = {"faculty": self.f_fac.get() or None, "name": self.f_name.get()}
        if self.scope == "active":
            kw["active_only"] = True
        elif self.scope == "over_budget":
            kw["over_budget"] = True
        else:
            kw["status"] = self.f_status.get() or None
        rows = DP.list_departments(**kw)
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for d in rows:
            self.rows[str(d.department_id)] = d
            self.tree.insert("", "end", iid=str(d.department_id),
                             tags=("over_budget",) if d.budget_over else (d.status,),
                             values=(d.department_id, d.name, d.code or "", d.faculty,
                                     d.head_name or "", d.second_name or "", d.budget_text,
                                     d.member_count, d.status))
        self.count.configure(text=f"{len(rows)} department(s)")
        if sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])
        self.refresh_members()

    def _selected(self, title: str) -> DP.Department | None:
        sel = self.tree.selection()
        if not sel:
            self.page._info(title, "Select a department first.")
            return None
        return DP.get(int(sel[0]))

    def refresh_members(self) -> None:
        self.mtree.delete(*self.mtree.get_children())
        self.mrows = {}
        sel = self.tree.selection()
        if not sel:
            return
        for m in DP.list_memberships(int(sel[0])):
            self.mrows[str(m.membership_id)] = m
            self.mtree.insert("", "end", iid=str(m.membership_id),
                              tags=() if m.is_current else ("muted",),
                              values=(m.membership_id, "yes" if m.is_primary else "",
                                      f"{m.staff_name} ({m.staff_code})", m.role_in_department,
                                      m.joined_on, m.left_on or "", m.notes or ""))

    def new(self) -> None:
        def save(v):
            DP.create({k: x for k, x in v.items() if x not in ("", None)},
                      actor=self.page.principal)
            self.page.refresh_all()
        _form(self.page.parent, "New department", _dept_fields(None), save,
              note="The head and deputy become members automatically.")

    def edit(self) -> None:
        d = self._selected("Edit")
        if d is None:
            return

        def save(v):
            DP.update(d.department_id, _diff(d, v, {"head_id": _label(d.head_id),
                                                    "second_id": _label(d.second_id)}),
                      actor=self.page.principal)
            self.page.refresh_all()
        _form(self.page.parent, f"Edit — {d.name}", _dept_fields(d), save,
              note="Renaming also renames the department on its subjects.")

    def set_status(self) -> None:
        d = self._selected("Change status")
        if d is None:
            return

        def save(v):
            DP.set_status(d.department_id, v["status"], actor=self.page.principal)
            self.page.refresh_all()
        _form(self.page.parent, f"Status — {d.name}",
              [("status", "Status", d.status, DP.STATUSES)], save)

    def add_spend(self) -> None:
        d = self._selected("Add spend")
        if d is None:
            return

        def save(v):
            DP.add_spend(d.department_id, amount=v["amount"], actor=self.page.principal)
            self.page.refresh_all()
        _form(self.page.parent, f"Add spend — {d.name}",
              [("amount", "Amount (£, negative = refund)", "", None)], save,
              note=f"Spent so far: {d.budget_text or 'no budget set'}")

    def delete(self) -> None:
        d = self._selected("Delete")
        if d is None or not messagebox.askyesno(
                "Delete", f"Delete {d.name} and its memberships?", parent=self.page._top()):
            return
        try:
            DP.delete(d.department_id, actor=self.page.principal)
        except _ERRORS as e:
            self.page._err("Delete", e)
            return
        self.page.refresh_all()

    def history(self) -> None:
        d = self._selected("History")
        if d is None:
            return
        text = "\n".join(f"{h['at']}  {h['actor']:<12} {h['action']:<15} "
                         + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
                         for h in DP.history(d.department_id)) or "(no changes recorded)"
        W.text_window(self.page.parent, f"History — {d.name}", text)

    def subjects(self) -> None:
        d = self._selected("Subjects")
        if d is not None:
            self.page.subjects_window(d)

    def _member(self, title: str) -> DP.Membership | None:
        sel = self.mtree.selection()
        if not sel:
            self.page._info(title, "Select a member first.")
            return None
        return self.mrows[sel[0]]

    def add_member(self) -> None:
        d = self._selected("Add member")
        if d is None:
            return

        def save(v):
            DP.add_member(d.department_id, v, actor=self.page.principal)
            self.page.refresh_all()
        _form(self.page.parent, f"Add member — {d.name}", _member_fields(None), save)

    def edit_member(self) -> None:
        m = self._member("Edit member")
        if m is None:
            return

        def save(v):
            DP.update_membership(m.membership_id, _diff(m, v), actor=self.page.principal)
            self.page.refresh_all()
        _form(self.page.parent, f"Edit — {m.staff_name}", _member_fields(m), save)

    def end_member(self) -> None:
        m = self._member("End membership")
        if m is None:
            return

        def save(v):
            DP.end_membership(m.membership_id, v["left_on"] or None, actor=self.page.principal)
            self.page.refresh_all()
        _form(self.page.parent, f"End — {m.staff_name}",
              [("left_on", "Left on (blank = today)", "", None)], save)

    def delete_member(self) -> None:
        m = self._member("Delete membership")
        if m is None or not messagebox.askyesno(
                "Delete membership", f"Delete {m.staff_name}'s membership record?\n\n"
                                     "(End keeps it with a left date.)",
                parent=self.page._top()):
            return
        try:
            DP.delete_membership(m.membership_id, actor=self.page.principal)
        except _ERRORS as e:
            self.page._err("Delete membership", e)
            return
        self.page.refresh_all()


class DepartmentsPage:
    TABS = ("Active", "Over Budget", "All Departments", "Per Staff", "Summary", "Overview",
            "Meetings")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = DP.is_editor(principal)
        activity_log.record("departments.view")
        ttk.Label(parent, text=_TITLE, font=("", 16, "bold")).pack(anchor="w")
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 6))
        self.summary_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.summary_var, foreground="#666").pack(side="left")
        self._button(bar, "Export CSV…", self.export).pack_configure(side="right")
        self._button(bar, "Import from subjects", self.import_subjects, True).pack_configure(
            side="right")
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: dict[str, Any] = {}
        start = state.get("tab") if state.get("tab") in self.TABS else "Active"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _button(self, bar, text: str, command, editor_only: bool = False) -> ttk.Button:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side="left", padx=2)
        return b

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self._built:
            tab = self.tabs[name]
            self._built[name] = {
                "Active": lambda: _DepartmentList(self, tab, "active"),
                "Over Budget": lambda: _DepartmentList(self, tab, "over_budget"),
                "All Departments": lambda: _DepartmentList(self, tab, "all"),
                "Per Staff": lambda: self._build_per_staff(tab),
                "Summary": lambda: self._build_summary(tab),
                "Overview": lambda: self._build_overview(tab),
                "Meetings": lambda: self._build_meetings(tab)}[name]() or True
        self._refresh(name)
        s = DP.summary()
        self.summary_var.set(f"Departments: {s['total']}  Active: {s['active']}  Members: "
                             f"{s['members']}  Over budget: {s['over_budget']}")

    def _refresh(self, name: str) -> None:
        obj = self._built.get(name)
        if isinstance(obj, _DepartmentList):
            obj.refresh()
        elif name == "Summary":
            self.refresh_summary()
        elif name == "Overview":
            self.refresh_overview()
        elif name == "Meetings":
            self.refresh_meetings()

    def refresh_all(self) -> None:
        for name in list(self._built):
            self._refresh(name)

    def _dept_choices(self) -> list[str]:
        return [f"{d.name} (#{d.department_id})" for d in DP.list_departments()]

    @staticmethod
    def _dept_from(text: str) -> DP.Department | None:
        if text and text.endswith(")") and "#" in text:
            return DP.find(int(text[text.rindex("#") + 1:-1]))
        return None

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            initialfile="departments.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = DP.export_csv(path, actor=self.principal)
        except (*_ERRORS, OSError) as e:
            self._err("Export CSV", e)
            return
        self._info("Export CSV", f"Exported {n} department(s).")

    def import_subjects(self) -> None:
        try:
            made = DP.import_from_subjects(actor=self.principal)
        except _ERRORS as e:
            self._err("Import from subjects", e)
            return
        self.refresh_all()
        self._info("Import from subjects",
                   "Made: " + ", ".join(d.name for d in made) if made else
                   "Every department named on a subject already exists.")

    def subjects_window(self, d: DP.Department) -> None:
        win, frm = W.dialog(self.parent, f"Subjects — {d.name}", size="560x420")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        tree = W.tree(frm, [("code", "Code", 80), ("name", "Subject", 240),
                            ("ks", "Key stage", 80), ("active", "Active", 60)], height=12,
                      stretch={"name"})

        def refresh() -> None:
            tree.delete(*tree.get_children())
            for s in DP.subjects_for(d.department_id):
                tree.insert("", "end", iid=str(s.subject_id), values=(
                    s.code, s.name, s.key_stage, "yes" if s.is_active else "no"))

        def add() -> None:
            others = DP.unassigned_subjects()
            if not others:
                self._info("Add subject", "Every subject is already in a department.")
                return

            def save(v):
                hit = next((s for s in others if s.label == v["subject"]), None)
                if hit is None:
                    raise DP.ValidationError(["Choose a subject"])
                DP.assign_subject(d.department_id, hit.subject_id, actor=self.principal)
                refresh()
            _form(win, "Add subject", [("subject", "Subject", "",
                                        [s.label for s in others])], save)

        def remove() -> None:
            sel = tree.selection()
            if not sel:
                return
            try:
                DP.remove_subject(d.department_id, int(sel[0]), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Remove subject", W.problems(e), parent=win)
                return
            refresh()
        for text, cmd in (("Add subject…", add), ("Remove", remove)):
            b = ttk.Button(bar, text=text, command=cmd)
            if not self.editor:
                b.state(["disabled"])
            b.pack(side="left", padx=2)
        ttk.Label(bar, text="Sets the subject's department (Subjects screen).",
                  foreground="#777").pack(side="left", padx=8)
        refresh()

    # ── Per Staff ────────────────────────────────────────────────────

    def _build_per_staff(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Staff:").pack(side="left")
        self.ps_staff = tk.StringVar(value=self.state.get("per_staff", ""))
        ttk.Combobox(bar, textvariable=self.ps_staff, values=SD.choices(include_leavers=True),
                     width=40).pack(side="left", padx=4)
        ttk.Button(bar, text="Show", command=self.refresh_per_staff).pack(side="left")
        self.ps_tree = W.tree(tab, [("dept", "Department", 200), ("role", "Role", 180),
                                    ("primary", "Primary", 60), ("joined", "Joined", 100),
                                    ("left", "Left", 100)], height=14, stretch={"dept"},
                              tags=W.STANDARD_TAGS)

    def refresh_per_staff(self) -> None:
        self.state["per_staff"] = self.ps_staff.get()
        self.ps_tree.delete(*self.ps_tree.get_children())
        m = SD.find(self.ps_staff.get())
        if m is None:
            if self.ps_staff.get():
                self._info("Per Staff", "No such member of staff.")
            return
        for x in DP.memberships_for_staff(m.staff_id):
            self.ps_tree.insert("", "end", tags=() if x.is_current else ("muted",), values=(
                x.department_name, x.role_in_department, "yes" if x.is_primary else "",
                x.joined_on, x.left_on or ""))

    # ── Summary ──────────────────────────────────────────────────────

    def _build_summary(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Refresh", command=self.refresh_summary).pack(side="left")
        self.sum_text = tk.Text(tab, wrap="word", font=("TkFixedFont", 10))
        self.sum_text.pack(fill="both", expand=True)

    def refresh_summary(self) -> None:
        s = DP.summary()
        lines = [f"Departments: {s['total']}   Active: {s['active']}   Members: {s['members']}",
                 f"Budget: £{s['budget_spent']:,.2f} spent of £{s['budget_total']:,.2f}   "
                 f"Over budget: {s['over_budget']}"]
        if s["without_head"]:
            lines.append("No head of department: " + ", ".join(s["without_head"]))
        for title, key in (("By faculty", "by_faculty"), ("By status", "by_status")):
            lines += ["", f"{title}:"] + [f"  {k:<26}: {n}" for k, n in s[key].items()]
        self.sum_text.configure(state="normal")
        self.sum_text.delete("1.0", "end")
        self.sum_text.insert("1.0", "\n".join(lines))
        self.sum_text.configure(state="disabled")

    # ── Overview ─────────────────────────────────────────────────────

    def _dept_bar(self, tab, key: str, command) -> tk.StringVar:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Department:").pack(side="left")
        var = tk.StringVar(value=self.state.get(key, ""))
        cb = ttk.Combobox(bar, textvariable=var, values=self._dept_choices(), state="readonly",
                          width=36, postcommand=lambda: cb.configure(
                              values=self._dept_choices()))
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: command())
        if not var.get() and cb["values"]:
            var.set(cb["values"][0])
        self._last_bar = bar
        return var

    def _build_overview(self, tab) -> None:
        self.ov_dept = self._dept_bar(tab, "overview", self.refresh_overview)
        self.ov_counts = tk.StringVar()
        ttk.Label(tab, textvariable=self.ov_counts, foreground="#444").pack(anchor="w")
        cols = ttk.Frame(tab)
        cols.pack(fill="both", expand=True)
        left, right = ttk.Frame(cols), ttk.Frame(cols)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Staff").pack(anchor="w")
        self.ov_staff = W.tree(left, [("staff", "Staff", 180), ("role", "Role", 150)],
                               height=8, stretch={"staff"})
        ttk.Label(left, text="Subjects").pack(anchor="w", pady=(6, 0))
        self.ov_subj = W.tree(left, [("code", "Code", 70), ("name", "Subject", 200)],
                              height=6, stretch={"name"})
        ttk.Label(right, text="Teaching groups this year").pack(anchor="w")
        self.ov_groups = W.tree(right, [("code", "Group", 90), ("year", "Yr", 40),
                                        ("teacher", "Teacher", 150), ("pupils", "Pupils", 60),
                                        ("lessons", "Lessons", 60)], height=8,
                                stretch={"teacher"})
        ttk.Label(right, text="Open actions").pack(anchor="w", pady=(6, 0))
        self.ov_actions = W.tree(right, [("due", "Due", 90), ("what", "Action", 220),
                                         ("owner", "Owner", 120)], height=6, stretch={"what"},
                                 tags=W.STANDARD_TAGS)

    def refresh_overview(self) -> None:
        d = self._dept_from(self.ov_dept.get())
        for t in (self.ov_staff, self.ov_subj, self.ov_groups, self.ov_actions):
            t.delete(*t.get_children())
        if d is None:
            self.ov_counts.set("No departments yet." if not self._dept_choices() else "")
            return
        self.state["overview"] = self.ov_dept.get()
        try:
            o = DP.overview(d.department_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Overview", e)
            return
        c = o["counts"]
        self.ov_counts.set(f"Head: {d.head_name or '-'}   2nd: {d.second_name or '-'}   Staff: "
                           f"{c['staff']} ({c['teaching_staff']} teaching, {c['fte']} FTE)   "
                           f"Subjects: {c['subjects']}   Groups: {c['groups']}   Pupil places: "
                           f"{c['pupil_places']}   Lessons/week: {c['lessons_per_week']}   "
                           f"Open actions: {c['open_actions']} ({c['overdue_actions']} overdue)")
        for m in o["members"]:
            self.ov_staff.insert("", "end", values=(m.staff_name, m.role_in_department))
        for s in o["subjects"]:
            self.ov_subj.insert("", "end", values=(s.code, s.name))
        for g in o["groups"]:
            self.ov_groups.insert("", "end", values=(g.group.code, g.group.year_group,
                                                     g.group.teacher_name
                                                     or g.group.teacher_username or "",
                                                     g.pupils, g.lessons or ""))
        for a in o["open_actions"]:
            self.ov_actions.insert("", "end", tags=("bad",) if a.overdue else (),
                                   values=(a.due_date or "", a.description, a.owner_name or ""))

    # ── Meetings ─────────────────────────────────────────────────────

    def _build_meetings(self, tab) -> None:
        self.mt_dept = self._dept_bar(tab, "meetings", self.refresh_meetings)
        bar = self._last_bar
        self.mt_buttons = []
        for text, cmd in (("New meeting…", self.new_meeting), ("Edit…", self.edit_meeting),
                          ("Minutes", self.show_minutes), ("Delete", self.delete_meeting),
                          ("Add action…", self.add_action)):
            self.mt_buttons.append(self._button(bar, text, cmd))
        self.mt_tree = W.tree(tab, [("date", "Date", 100), ("title", "Meeting", 260),
                                    ("present", "Present", 260), ("actions", "Actions", 70)],
                              height=8, stretch={"title"})
        self.mt_tree.bind("<<TreeviewSelect>>", lambda _e: self.refresh_actions())
        self.mt_tree.bind("<Double-1>", lambda _e: self.show_minutes())
        abar = ttk.Frame(tab)
        abar.pack(fill="x", pady=(6, 4))
        ttk.Label(abar, text="Actions from the selected meeting").pack(side="left")
        for text, st in (("Done", "Done"), ("Dropped", "Dropped"), ("Reopen", "Open")):
            ttk.Button(abar, text=text, command=lambda st=st: self.action_status(st)).pack(
                side="right", padx=2)
        self.ac_tree = W.tree(tab, [("id", "Id", 50), ("what", "Action", 300),
                                    ("owner", "Owner", 150), ("due", "Due", 90),
                                    ("status", "Status", 80)], height=6, stretch={"what"},
                              tags=W.STANDARD_TAGS)

    def _mt_dept(self) -> DP.Department | None:
        return self._dept_from(self.mt_dept.get())

    def refresh_meetings(self) -> None:
        d = self._mt_dept()
        self.mt_tree.delete(*self.mt_tree.get_children())
        allowed = bool(d and DP.can_manage_meetings(self.principal, d))
        for b in self.mt_buttons:
            if b.cget("text") == "Minutes":
                continue
            b.state(["!disabled"] if allowed else ["disabled"])
        if d is None:
            self.refresh_actions()
            return
        self.state["meetings"] = self.mt_dept.get()
        for mt in DP.list_meetings(d.department_id):
            self.mt_tree.insert("", "end", iid=str(mt.meeting_id), values=(
                mt.meeting_date, mt.title, mt.attendees or "",
                len(DP.list_actions(meeting_id=mt.meeting_id))))
        self.refresh_actions()

    def _meeting(self, title: str) -> DP.Meeting | None:
        sel = self.mt_tree.selection()
        if not sel:
            self._info(title, "Select a meeting first.")
            return None
        return DP.get_meeting(int(sel[0]))

    def refresh_actions(self) -> None:
        self.ac_tree.delete(*self.ac_tree.get_children())
        sel = self.mt_tree.selection()
        if not sel:
            return
        for a in DP.list_actions(meeting_id=int(sel[0])):
            self.ac_tree.insert("", "end", iid=str(a.action_id),
                                tags=("bad",) if a.overdue else (
                                    ("muted",) if a.status != "Open" else ()),
                                values=(a.action_id, a.description, a.owner_name or "",
                                        a.due_date or "", a.status))

    _MEETING_FIELDS = (("meeting_date", "Date (blank = today)", None),
                       ("title", "Title", None), ("attendees", "Present", None),
                       ("apologies", "Apologies", None), ("agenda", "Agenda", "text"),
                       ("minutes", "Minutes", "text"))

    def new_meeting(self) -> None:
        d = self._mt_dept()
        if d is None:
            return

        def save(v):
            DP.add_meeting(d.department_id, v, actor=self.principal)
            self.refresh_meetings()
        _form(self.parent, f"New meeting — {d.name}",
              [(k, label, "Department meeting" if k == "title" else "", kind)
               for k, label, kind in self._MEETING_FIELDS], save)

    def edit_meeting(self) -> None:
        mt = self._meeting("Edit meeting")
        if mt is None:
            return

        def save(v):
            DP.update_meeting(mt.meeting_id, v, actor=self.principal)
            self.refresh_meetings()
        _form(self.parent, f"Meeting — {mt.meeting_date}",
              [(k, label, getattr(mt, k) or "", kind)
               for k, label, kind in self._MEETING_FIELDS], save)

    def show_minutes(self) -> None:
        mt = self._meeting("Minutes")
        if mt is not None:
            W.text_window(self.parent, f"Minutes — {mt.title}", DP.minutes_text(mt.meeting_id),
                          save_name=f"minutes-{mt.meeting_date}.txt")

    def delete_meeting(self) -> None:
        mt = self._meeting("Delete meeting")
        if mt is None or not messagebox.askyesno(
                "Delete meeting", f"Delete the meeting of {mt.meeting_date} and its actions?",
                parent=self._top()):
            return
        try:
            DP.delete_meeting(mt.meeting_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete meeting", e)
            return
        self.refresh_meetings()

    def add_action(self) -> None:
        mt = self._meeting("Add action")
        if mt is None:
            return

        def save(v):
            DP.add_action(mt.meeting_id, v, actor=self.principal)
            self.refresh_meetings()
            if self.mt_tree.exists(str(mt.meeting_id)):
                self.mt_tree.selection_set(str(mt.meeting_id))
        _form(self.parent, "Add action", [
            ("description", "Action*", "", "text"), ("owner", "Owner", "", _staff_kind()),
            ("due_date", "Due date", "", None), ("notes", "Notes", "", None)], save)

    def action_status(self, status: str) -> None:
        sel = self.ac_tree.selection()
        if not sel:
            self._info("Action", "Select an action first.")
            return
        try:
            DP.set_action_status(int(sel[0]), status, actor=self.principal)
        except _ERRORS as e:
            self._err("Action", e)
            return
        self.refresh_actions()


def draw_departments(parent: ttk.Frame, *, principal: Principal, state: dict
                     ) -> DepartmentsPage:
    return DepartmentsPage(parent, principal=principal, state=state)
