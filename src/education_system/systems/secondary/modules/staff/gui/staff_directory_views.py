"""Staff Directory screen.

The old Staff Directory window is the first tab ("Directory"), with its
filter bar (Search, Role, Dept, Status, Active only, Tutors, DSL; Apply,
Clear), its columns (ID, Name, Role, Department, Status, Email, Phone, Room,
Flags), Left rows greyed and DSL rows tinted, the count line and its buttons
(View, New, Edit, Mark Left, Delete, Refresh). The old New / Edit form's
fields are all there (staff ID, names, role, department, employment status,
e-mail, work and personal phone, room, line manager, start / end dates,
Tutor / DSL / Examiner flags, qualifications, notes); qualifications and the
personal / HR fields have their own forms so no form is taller than the
screen.

Added: role type and line manager columns and a role-type filter; Profile
(forms tutored, teaching groups, timetable, cover done, departments,
reports, mentees); Qualifications & ECT…, Personal & HR… (HR only), Link
login…, Import logins…, History, Export CSV…. New tabs: Leavers (kept, with
Reinstate) and Summary. Rules: :mod:`modules.staff.domain.staff_directory`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = W.ERRORS
_form = W.form_dialog
_TITLE = "Staff Directory"

_COLUMNS = [("id", "ID", 90), ("name", "Name", 200), ("role", "Role", 160),
            ("type", "Type", 80), ("department", "Department", 140),
            ("status", "Status", 100), ("email", "Email", 200), ("phone", "Phone", 110),
            ("room", "Room", 60), ("manager", "Line manager", 140), ("flags", "Flags", 50)]

_CORE = ("staff_code", "username", "title", "first_name", "last_name", "preferred_name",
         "job_title", "role", "role_type", "department", "employment_status", "contract_type",
         "fte", "start_date", "leave_date", "room", "extension", "work_email", "work_phone",
         "line_manager_id", "is_tutor", "is_dsl", "is_examiner", "notes")
_QUALS = ("qts", "qts_date", "trn", "ect_status", "ect_start", "ect_mentor_id",
          "qualifications")


def _value(m: SD.StaffMember | None, key: str) -> Any:
    if m is None:
        return {"role": SD.DEFAULT_ROLE, "employment_status": SD.DEFAULT_EMPLOYMENT_STATUS,
                "contract_type": SD.DEFAULT_CONTRACT_TYPE, "fte": "1.0",
                "ect_status": "Not applicable", "pension_enrolled": True}.get(key, "")
    v = getattr(m, key)
    if key in ("line_manager_id", "ect_mentor_id") and v:
        other = SD.find(v)
        return other.label if other else ""
    return "" if v is None else v


def _kind(key: str) -> Any:
    staff = ("edit", ["", *SD.choices()])
    return {
        "username": ("edit", ["", *[s["username"] for s in SD.unlinked_logins()]]),
        "title": ["", *SD.TITLES], "role": SD.ROLES, "role_type": SD.ROLE_TYPES,
        "department": ("edit", ["", *sorted(set(SD.DEPARTMENTS) | set(_department_names()))]),
        "employment_status": SD.EMPLOYMENT_STATUSES, "contract_type": SD.CONTRACT_TYPES,
        "leaving_reason": ["", *SD.LEAVING_REASONS], "ect_status": SD.ECT_STATUSES,
        "salary_scale": ["", *SD.SALARY_SCALES], "line_manager_id": staff,
        "ect_mentor_id": staff, "notes": "text", "qualifications": "text",
        "home_address": "text"}.get(key, "check" if key in (
            "is_tutor", "is_dsl", "is_examiner", "qts", "pension_enrolled") else None)


def _department_names() -> list[str]:
    try:
        from education_system.systems.secondary.modules.staff.domain import departments as DP
        return DP.names()
    except Exception:  # noqa: BLE001 - a suggestion list only
        logger.debug("department names unavailable", exc_info=True)
        return []


def _fields(m: SD.StaffMember | None, keys: tuple[str, ...]) -> list:
    out = []
    for k in keys:
        label = SD.LABELS[k]
        if k == "staff_code" and m is None:
            label += " (made up if blank)"
        if k == "username":
            label += " - blank if none"
        out.append((k, label, _value(m, k), _kind(k)))
    return out


def _changes(m: SD.StaffMember, values: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in values.items() if str(v if v is not None else "")
            != str(_value(m, k) if not isinstance(_value(m, k), bool) else _value(m, k))}


class StaffDirectoryPage:
    TABS = ("Directory", "Leavers", "Summary")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = SD.is_editor(principal)
        activity_log.record("staff.view")
        ttk.Label(parent, text=_TITLE, font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Directory"
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
        build = {"Directory": (self._build_directory, self.refresh),
                 "Leavers": (self._build_leavers, self.refresh_leavers),
                 "Summary": (self._build_summary, self.refresh_summary)}[name]
        if name not in self._built:
            self._built.add(name)
            build[0](self.tabs[name])
        build[1]()

    def _refresh_all(self) -> None:
        for name, fn in (("Directory", self.refresh), ("Leavers", self.refresh_leavers),
                         ("Summary", self.refresh_summary)):
            if name in self._built:
                fn()

    def _tree(self, parent) -> ttk.Treeview:
        t = W.tree(parent, _COLUMNS, height=16, stretch={"name", "email"},
                   tags={**W.STANDARD_TAGS, "Left": {"foreground": "#888888"},
                         "DSL": "#fff4d0"}, xscroll=True)
        return t

    def _insert(self, tree, m: SD.StaffMember, rows: dict) -> None:
        rows[str(m.staff_id)] = m
        tags = ("Left",) if m.is_leaver else (("DSL",) if m.is_dsl else ())
        tree.insert("", "end", iid=str(m.staff_id), tags=tags, values=(
            m.staff_code, m.sort_name, m.role, m.role_type, m.department or "",
            m.employment_status, m.email or "", m.work_phone or "", m.room or "",
            m.line_manager_name or "", m.flags))

    # ── Directory (the old window) ───────────────────────────────────

    def _build_directory(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        st = self.state
        self.q = tk.StringVar(value=st.get("q", ""))
        self.f_role = tk.StringVar(value=st.get("role", ""))
        self.f_dept = tk.StringVar(value=st.get("dept", ""))
        self.f_status = tk.StringVar(value=st.get("status", ""))
        self.f_type = tk.StringVar(value=st.get("type", ""))
        self.f_active = tk.BooleanVar(value=st.get("active", True))
        self.f_tutor = tk.BooleanVar(value=st.get("tutor", False))
        self.f_dsl = tk.BooleanVar(value=st.get("dsl", False))
        ttk.Label(bar, text="Search:").pack(side="left")
        e = ttk.Entry(bar, textvariable=self.q, width=18)
        e.pack(side="left", padx=(2, 6))
        e.bind("<Return>", lambda _e: self.refresh())
        for label, var, values, width in (
                ("Role:", self.f_role, ["", *SD.ROLES], 16),
                ("Dept:", self.f_dept, ["", *sorted(set(SD.DEPARTMENTS)
                                                    | set(_department_names()))], 14),
                ("Status:", self.f_status, ["", *SD.EMPLOYMENT_STATUSES], 11),
                ("Type:", self.f_type, ["", *SD.ROLE_TYPES], 9)):
            ttk.Label(bar, text=label).pack(side="left")
            cb = ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                              width=width)
            cb.pack(side="left", padx=(2, 6))
            cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        for text, var in (("Active only", self.f_active), ("Tutors", self.f_tutor),
                          ("DSL", self.f_dsl)):
            ttk.Checkbutton(bar, text=text, variable=var, command=self.refresh).pack(
                side="left", padx=2)
        ttk.Button(bar, text="Apply", command=self.refresh).pack(side="left", padx=2)
        ttk.Button(bar, text="Clear", command=self._clear).pack(side="left", padx=2)
        self.tree = self._tree(tab)
        self.tree.bind("<Double-1>", lambda _e: self.view())
        self.rows: dict[str, SD.StaffMember] = {}
        self.count_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.count_var, anchor="w").pack(fill="x")
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(4, 0))
        for text, cmd, ed in (("View", self.view, False), ("New", self.new, True),
                              ("Edit", self.edit, True), ("Mark Left", self.mark_left, True),
                              ("Delete", self.delete, True), ("Refresh", self.refresh, False)):
            self._button(bar2, text, cmd, ed)
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(4, 0))
        for text, cmd, ed in (("Profile", self.view, False),
                              ("Qualifications & ECT…", self.edit_quals, True),
                              ("Personal & HR…", self.edit_personal, True),
                              ("Link login…", self.link_login, True),
                              ("Import logins…", self.import_logins, True),
                              ("History", self.history, False),
                              ("Export CSV…", self.export, False)):
            self._button(bar3, text, cmd, ed)

    def _clear(self) -> None:
        for v in (self.q, self.f_role, self.f_dept, self.f_status, self.f_type):
            v.set("")
        self.f_active.set(False)
        self.f_tutor.set(False)
        self.f_dsl.set(False)
        self.refresh()

    def _filters(self) -> dict[str, Any]:
        return {"search": self.q.get() or None, "role": self.f_role.get() or None,
                "department": self.f_dept.get() or None,
                "employment_status": self.f_status.get() or None,
                "role_type": self.f_type.get() or None, "tutors": self.f_tutor.get(),
                "dsl": self.f_dsl.get(), "include_leavers": not self.f_active.get()}

    def refresh(self) -> None:
        self.state.update(q=self.q.get(), role=self.f_role.get(), dept=self.f_dept.get(),
                          status=self.f_status.get(), type=self.f_type.get(),
                          active=self.f_active.get(), tutor=self.f_tutor.get(),
                          dsl=self.f_dsl.get())
        try:
            rows = SD.list_staff(**self._filters(), actor=self.principal)
        except _ERRORS as e:
            self._err(_TITLE, e)
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for m in rows:
            self._insert(self.tree, m, self.rows)
        self.count_var.set(f"{len(rows)} staff. (Flags: T=Tutor D=DSL E=Examiner)")
        s = SD.summary()
        self.summary_var.set(f"Current: {s['current']}    FTE: {s['fte']}    Leavers: "
                             f"{s['left']}    Tutors: {s['tutors']}    DSLs: {s['dsls']}    "
                             f"Logins without a record: {s['logins_without_record']}")

    def _selected(self, title: str, tree=None, rows=None) -> SD.StaffMember | None:
        tree, rows = tree or self.tree, rows if rows is not None else self.rows
        sel = tree.selection()
        if not sel:
            self._info(title, "Select a member of staff first.")
            return None
        return SD.find(int(sel[0]))

    def view(self, tree=None, rows=None) -> None:
        m = self._selected("View", tree, rows)
        if m is None:
            return
        try:
            text = SD.profile_text(m.staff_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Profile", e)
            return
        W.text_window(self.parent, f"Profile — {m.full_name}", text, size="760x620",
                      save_name=f"{m.staff_code}-profile.txt")

    def new(self) -> None:
        def save(v):
            m = SD.create({k: x for k, x in v.items() if x not in ("", None)},
                          actor=self.principal)
            self._refresh_all()
            self._info("New staff", f"Created {m.staff_code} — {m.full_name} ({m.role})")
        _form(self.parent, "New staff", _fields(None, _CORE), save,
              note="Pick their login if they have one; leave it blank for staff without "
                   "one (support staff, contractors).")

    def _edit_with(self, title: str, keys: tuple[str, ...], note: str | None = None) -> None:
        m = self._selected(title)
        if m is None:
            return

        def save(v):
            SD.update(m.staff_id, _changes(m, v), actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"{title} — {m.full_name}", _fields(m, keys), save, note=note)

    def edit(self) -> None:
        self._edit_with("Edit staff", _CORE)

    def edit_quals(self) -> None:
        self._edit_with("Qualifications & ECT", _QUALS,
                        "ECT years 1-2 (and an extension) need a mentor.")

    def edit_personal(self) -> None:
        self._edit_with("Personal & HR", SD.PRIVATE_FIELDS,
                        "Only HR sees these. Salary in pounds; dates YYYY-MM-DD.")

    def mark_left(self) -> None:
        m = self._selected("Mark Left")
        if m is None:
            return

        def save(v):
            SD.mark_left(m.staff_id, v["leave_date"], reason=v["reason"] or None,
                         actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Mark {m.full_name} as left", [
            ("leave_date", "Leave date (blank = today)", "", None),
            ("reason", "Reason", "", ["", *SD.LEAVING_REASONS])], save,
            note="The record is kept, with their history; it moves to the Leavers tab.")

    def delete(self) -> None:
        m = self._selected("Delete")
        if m is None or not messagebox.askyesno(
                "Delete", f"Delete {m.full_name} ({m.staff_code})?\n\nOnly for a record made in "
                          "error - anyone with history is marked as left instead.",
                parent=self._top()):
            return
        try:
            SD.delete(m.staff_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete", e)
            return
        self._refresh_all()

    def link_login(self) -> None:
        m = self._selected("Link login")
        if m is None:
            return

        def save(v):
            SD.link_login(m.staff_id, v["username"] or None, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Login for {m.full_name}", [
            ("username", "Login (blank = none)", m.username or "",
             ("edit", ["", *[s["username"] for s in SD.unlinked_logins()]]))], save)

    def import_logins(self) -> None:
        waiting = SD.unlinked_logins()
        if not waiting:
            self._info("Import logins", "Every staff login already has a staff record.")
            return
        names = "\n".join(f"  {s['display_name']} ({s['username']})" for s in waiting[:30])
        if not messagebox.askyesno(
                "Import logins", f"Make a staff record for {len(waiting)} login(s)?\n\n{names}",
                parent=self._top()):
            return
        try:
            made = SD.import_logins(actor=self.principal)
        except _ERRORS as e:
            self._err("Import logins", e)
            return
        self._refresh_all()
        self._info("Import logins", f"Made {len(made)} record(s). Check their roles and "
                                    "departments.")

    def history(self) -> None:
        m = self._selected("History")
        if m is None:
            return
        rows = SD.history(m.staff_id)
        text = "\n".join(f"{h['at']}  {h['actor']:<12} {h['action']:<10} "
                         + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
                         for h in rows) or "(no changes recorded)"
        W.text_window(self.parent, f"History — {m.full_name}", text)

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            initialfile="staff-directory.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        personal = self.editor and messagebox.askyesno(
            "Export CSV", "Include personal and HR fields?", parent=self._top())
        try:
            n = SD.export_csv(path, actor=self.principal, include_personal=personal,
                              **self._filters())
        except (*_ERRORS, OSError) as e:
            self._err("Export CSV", e)
            return
        self._info("Export CSV", f"Exported {n} member(s) of staff.")

    # ── Leavers ──────────────────────────────────────────────────────

    def _build_leavers(self, tab) -> None:
        ttk.Label(tab, text="Staff who have left. Their records and history are kept.",
                  foreground="#555").pack(anchor="w", pady=(0, 6))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.lv_tree = self._tree(tab)
        self.lv_rows: dict[str, SD.StaffMember] = {}
        self._button(bar, "View", lambda: self.view(self.lv_tree, self.lv_rows))
        self._button(bar, "Reinstate…", self.reinstate, True)
        self.lv_tree.bind("<Double-1>", lambda _e: self.view(self.lv_tree, self.lv_rows))

    def refresh_leavers(self) -> None:
        self.lv_tree.delete(*self.lv_tree.get_children())
        self.lv_rows = {}
        for m in SD.list_staff(leavers_only=True, actor=self.principal):
            self._insert(self.lv_tree, m, self.lv_rows)

    def reinstate(self) -> None:
        m = self._selected("Reinstate", self.lv_tree, self.lv_rows)
        if m is None:
            return

        def save(v):
            SD.reinstate(m.staff_id, actor=self.principal, status=v["status"])
            self._refresh_all()
        _form(self.parent, f"Reinstate {m.full_name}", [
            ("status", "Coming back as", SD.DEFAULT_EMPLOYMENT_STATUS,
             [s for s in SD.EMPLOYMENT_STATUSES if s != "Left"])], save)

    # ── Summary ──────────────────────────────────────────────────────

    def _build_summary(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self._button(bar, "Refresh", self.refresh_summary)
        self.sum_text = tk.Text(tab, wrap="word", font=("TkFixedFont", 10), height=24)
        self.sum_text.pack(fill="both", expand=True)

    def refresh_summary(self) -> None:
        s = SD.summary()
        lines = [f"Staff: {s['total']} records, {s['current']} current, {s['active']} active, "
                 f"{s['left']} left.   FTE (current): {s['fte']}",
                 f"Tutors: {s['tutors']}   DSLs: {s['dsls']}   Examiners: {s['examiners']}",
                 f"Without a login: {s['without_login']}   Logins without a record: "
                 f"{s['logins_without_record']}", ""]
        if s["unfilled_critical"]:
            lines.append("No one in these roles: " + ", ".join(s["unfilled_critical"]))
        if s["ects_without_mentor"]:
            lines.append("ECTs without a mentor: " + ", ".join(
                m.full_name for m in s["ects_without_mentor"]))
        for title, key in (("By role type", "by_role_type"), ("By role", "by_role"),
                           ("By department", "by_department"), ("By status", "by_status")):
            lines += ["", f"{title}:"] + [f"  {k:<30} {n}" for k, n in s[key].items()]
        self.sum_text.configure(state="normal")
        self.sum_text.delete("1.0", "end")
        self.sum_text.insert("1.0", "\n".join(lines))
        self.sum_text.configure(state="disabled")


def draw_staff_directory(parent: ttk.Frame, *, principal: Principal, state: dict
                         ) -> StaffDirectoryPage:
    return StaffDirectoryPage(parent, principal=principal, state=state)
