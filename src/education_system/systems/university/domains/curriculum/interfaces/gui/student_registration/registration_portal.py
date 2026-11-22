"""Module Registration portal.

Students see the modules of their course and year: compulsory ones (enrolled
automatically, not droppable), optional ones to choose (sent for approval
when the course requires it) and everything they are enrolled on, and can
browse the whole module catalogue with each module's details. Staff act
for a chosen student, approve choices and may override with a reason;
admins also set registration periods, credit rules and module credits, and
reconcile the enrolment records.

Every rule is in ``university/application/modules/registration`` and
``module_registration_admin``; this module only presents them.
"""

from __future__ import annotations

import tkinter as tk
from contextlib import closing
from tkinter import messagebox, simpledialog, ttk

from education_system.systems.university.domains.curriculum.interfaces.gui.student_registration.common_imports import (  # noqa: E501
    get_auth, get_connection, get_student_id, get_user_role, logger,
)

TITLE = "Module Registration"
PRIVILEGED_ROLES = {'admin', 'administrator', 'superadmin', 'super_admin', 'staff', 'registrar',
                    'lecturer', 'instructor', 'faculty'}
ADMIN_ROLES = {'admin', 'administrator', 'superadmin', 'super_admin', 'registrar'}


def _rules():
    from education_system.systems.university.application.modules import (
        registration as module_registration,
    )
    return module_registration


def _catalogue():
    from education_system.systems.university.application.modules import (
        catalogue as module_catalogue,
    )
    return module_catalogue


def _messages():
    from education_system.systems.university.application.modules import (
        registration_messages as module_registration_messages,
    )
    return module_registration_messages


def _admin_rules():
    from education_system.systems.university.application.modules import (
        registration_admin as module_registration_admin,
    )
    return module_registration_admin


def _call(parent, fn, *args, write=False, **kwargs):
    """Run a rule on its own connection; a refusal becomes a dialog (None)."""
    try:
        with closing(get_connection(row_factory=False)) as conn:
            result = fn(conn, *args, **kwargs)
            if write:
                conn.commit()
            return True if result is None else result
    except ValueError as exc:
        messagebox.showerror(TITLE, str(exc), parent=parent)
    except Exception as exc:
        logger.exception("module registration action failed")
        messagebox.showerror(TITLE, f"That did not work: {exc}", parent=parent)
    return None


def _tree(parent, columns, widths, height=8, select="browse"):
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=3)
    view = ttk.Treeview(frame, columns=[c for c, _h in columns], show="headings", height=height,
                        selectmode=select)
    for (key, title), width in zip(columns, widths):
        view.heading(key, text=title)
        view.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=view.yview)
    view.configure(yscrollcommand=bar.set)
    bar.pack(side=tk.RIGHT, fill=tk.Y)
    view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    return view


def _bar(parent, buttons, side=tk.TOP):
    bar = ttk.Frame(parent, padding=(6, 2))
    bar.pack(side=side, fill=tk.X)
    for label, command in buttons:
        ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
    return bar


def _username(auth):
    user = getattr(auth, "current_user", None) or {}
    if not isinstance(user, dict):
        user = getattr(user, "__dict__", {}) or {}
    return str(user.get("username") or user.get("id") or "unknown")


class StudentRegistrationPortal:
    """Module registration for a student, or for staff acting for one."""

    def __init__(self, parent_frame, auth_instance=None):
        self.parent_frame = parent_frame
        self.auth = auth_instance or get_auth()
        self.role = (get_user_role(self.auth) or '').lower()
        self.is_privileged = self.role in PRIVILEGED_ROLES
        self.is_admin = self.role in ADMIN_ROLES
        self.actor = _username(self.auth)
        self.student_id = None if self.is_privileged else get_student_id(self.auth)
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        if self.is_privileged:
            self._build_student_picker()
        self.notebook = ttk.Notebook(self.parent_frame)
        self.notebook.pack(fill='both', expand=True, padx=8, pady=6)
        self.reg_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.reg_tab, text="Registration")
        self.annual_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.annual_tab, text="Annual registration")
        self._build_annual()
        self.catalogue_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.catalogue_tab, text="Browse catalogue")
        self._build_catalogue()
        if self.is_privileged:
            self.approval_tab = ttk.Frame(self.notebook)
            self.notebook.add(self.approval_tab, text="Choices to approve")
            self._build_approvals()
        if self.is_admin:
            self.setup_tab = ttk.Frame(self.notebook)
            self.notebook.add(self.setup_tab, text="Setup")
            self._build_setup()
        self.refresh()

    # Backwards-compatible alias for the original entry point.
    def setup_notebook(self):
        self._build_ui()

    def _build_student_picker(self):
        bar = ttk.Frame(self.parent_frame, padding=(8, 6, 8, 0))
        bar.pack(fill='x')
        ttk.Label(bar, text="Student", font=('Arial', 10, 'bold')).pack(side='left')
        self.search = ttk.Entry(bar, width=24)
        self.search.pack(side='left', padx=4)
        self.search.bind('<KeyRelease>', lambda _e: self._filter_students())
        self.student_combo = ttk.Combobox(bar, width=50, state='readonly')
        self.student_combo.pack(side='left', padx=4)
        self.student_combo.bind('<<ComboboxSelected>>', lambda _e: self._pick())
        self._students = self._load_students()
        self._filter_students()

    @staticmethod
    def _load_students():
        with closing(get_connection(row_factory=False)) as conn:
            return [(f"{sid} — {name} ({status}, {course})", sid) for sid, name, status, course in
                    conn.execute("SELECT student_id, TRIM(COALESCE(first_name, '') || ' ' || "
                                 "COALESCE(last_name, '')), status, course FROM students WHERE "
                                 "student_id NOT LIKE 'ERASED-%' ORDER BY last_name, first_name")]

    def _filter_students(self):
        term = self.search.get().strip().lower()
        self._shown = [(label, sid) for label, sid in self._students if term in label.lower()]
        self.student_combo.configure(values=[label for label, _sid in self._shown])

    def _pick(self):
        index = self.student_combo.current()
        if 0 <= index < len(self._shown):
            self.student_id = self._shown[index][1]
            self.refresh()

    # ------------------------------------------------------------------
    # Registration tab
    # ------------------------------------------------------------------
    def refresh(self):
        for child in self.reg_tab.winfo_children():
            child.destroy()
        if not self.student_id:
            ttk.Label(self.reg_tab, padding=20, text=(
                "Choose a student above." if self.is_privileged else
                "Your account is not linked to a student record.")).pack(anchor='w')
            return
        data = _call(self.parent_frame, _rules().overview, self.student_id)
        if not isinstance(data, dict):
            return
        self.data = data
        self._summary(data)
        self._compulsory(data)
        self._optional(data)
        self._enrolled(data)

    def _summary(self, d):
        s, r, w = d["student"], d["rules"], d["window"]
        window = {"unconfigured": "open (no registration period set)", "open": "open",
                  "late_add": "late adds only", "before_open": "not open yet",
                  "closed": "closed"}.get(w["phase"], w["phase"])
        deadline = f" · add deadline {w['deadline']}" if w.get("deadline") else ""
        credits = f"{d['credits']} credits enrolled (target {r['target_credits']}, " \
                  f"max {r['max_credits']})"
        if d["unknown_credits"]:
            credits += f" · {d['unknown_credits']} module(s) have no credit value yet"
        text = (f"{s['name']} ({s['student_id']}) · {s['course'] or s['course_raw']} year "
                f"{s['year_of_study']} · {s['status']}\nRegistration {window}{deadline} · "
                f"{credits}")
        if d["blocked"]:
            text += f"\n⚠ {d['blocked']}"
        if d["pending"]:
            text += f"\nChoices awaiting approval: {', '.join(d['pending']['modules'])}"
        ttk.Label(self.reg_tab, text=text, padding=(8, 6), justify='left',
                  wraplength=1000).pack(anchor='w')

    def _compulsory(self, d):
        frame = ttk.LabelFrame(self.reg_tab, text="Compulsory modules", padding=4)
        frame.pack(fill='both', expand=True, padx=6, pady=2)
        _bar(frame, (("Enrol all compulsory modules", self._enrol_compulsory),), tk.BOTTOM)
        self.compulsory_tree = _tree(frame, [("code", "Module"), ("name", "Name"),
                                             ("credits", "Credits"), ("state", "Status")],
                                     [110, 380, 70, 160], height=5)
        for m in d["structure"]["compulsory"]:
            self.compulsory_tree.insert('', 'end', values=(m["code"], m["name"],
                                                           m["credits"] or "—",
                                                           m["state"] or "not enrolled"))

    def _optional(self, d):
        frame = ttk.LabelFrame(self.reg_tab, text="Optional modules (select, then submit)",
                               padding=4)
        frame.pack(fill='both', expand=True, padx=6, pady=2)
        limits = d["rules"]
        ttk.Label(frame, text=f"Choose {limits['min_optional']}"
                              f"{'' if limits['max_optional'] is None else '–' + str(limits['max_optional'])}"
                              f" option(s)" + (" · needs approval" if limits["needs_approval"]
                                               else "")).pack(anchor='w', padx=6)
        buttons = [("Submit my choices" if not self.is_privileged else "Submit choices for "
                    "student", self._submit_choices)]
        if self.is_privileged:
            buttons.append(("Enrol selected now…", self._staff_enrol_selected))
        _bar(frame, buttons, tk.BOTTOM)
        self.optional_tree = _tree(frame, [("code", "Module"), ("name", "Name"),
                                           ("credits", "Credits"), ("state", "Status")],
                                   [110, 380, 70, 160], height=4, select="extended")
        for m in d["structure"]["optional"]:
            self.optional_tree.insert('', 'end', iid=m["code"], values=(
                m["code"], m["name"], m["credits"] or "—", m["state"] or ""))

    def _enrolled(self, d):
        frame = ttk.LabelFrame(self.reg_tab, text="Everything currently enrolled", padding=4)
        frame.pack(fill='both', expand=True, padx=6, pady=2)
        codes = [m["code"] for k in ("compulsory", "optional") for m in d["structure"][k]
                 if m["state"] == "Enrolled"] + d["other_enrolments"]
        buttons = [("Drop selected", self._drop)]
        if self.is_privileged:
            buttons.append(("Enrol another module…", self._staff_enrol_other))
        _bar(frame, buttons, tk.BOTTOM)
        self.enrolled_list = tk.Listbox(frame, height=4)
        self.enrolled_list.pack(fill='both', expand=True, padx=6)
        for code in codes:
            self.enrolled_list.insert('end', code)

    # actions ------------------------------------------------------------
    def _after(self, results):
        enrolled = [c for c, r in results.items() if r in ("enrolled", "reinstated")]
        failures = []
        for code in enrolled:
            failed = _rules().side_effects(self.student_id, code)
            if failed:
                failures.append(f"{code}: {', '.join(failed)}")
        return failures

    def _report(self, results, title="Result"):
        failures = self._after(results)
        lines = [f"{code}: {result}" for code, result in results.items()]
        if failures:
            lines.append("\nFollow-up steps that need checking: " + "; ".join(failures))
        messagebox.showinfo(title, "\n".join(lines) or "Nothing to do.",
                            parent=self.parent_frame)
        self.refresh()

    def _enrol_compulsory(self):
        result = _call(self.parent_frame, _rules().enrol_compulsory, self.student_id, self.actor,
                       write=True)
        if isinstance(result, dict):
            self._report(result, "Compulsory modules")

    def _submit_choices(self):
        codes = list(self.optional_tree.selection())
        result = _call(self.parent_frame, _rules().submit_choices, self.student_id, codes,
                       self.actor, write=True)
        if isinstance(result, dict):
            if result["status"] == "submitted":
                messagebox.showinfo(TITLE, "Choices sent for approval. You will get a message "
                                    "when they are decided.", parent=self.parent_frame)
                self.refresh()
            else:
                self._report(result["results"], "Choices enrolled")

    def _enrol_one(self, code, override=None):
        from education_system.systems.university.domains.curriculum.interfaces.gui._section_picker import (  # noqa: E501
            choose_section,
        )
        rules = _rules()
        section = None
        for _attempt in range(2):
            try:
                with closing(get_connection(row_factory=False)) as conn:
                    result = rules.enrol(conn, self.student_id, code, self.actor,
                                         staff=self.is_privileged, section_id=section,
                                         override=override)
                    conn.commit()
                return result["result"]
            except rules.SectionRequired as need:
                section = choose_section(self.parent_frame, code, need.sections)
                if section is None:
                    return "cancelled"
            except ValueError as exc:
                return f"not enrolled: {exc}"
        return "cancelled"

    def _staff_enrol_selected(self):
        codes = list(self.optional_tree.selection())
        if codes:
            self._report({c: self._enrol_one(c) for c in codes})

    def _staff_enrol_other(self):
        code = simpledialog.askstring(TITLE, "Module code:", parent=self.parent_frame)
        if not code:
            return
        override = simpledialog.askstring(
            TITLE, "If this module is outside the student's course structure or credit limit, "
                   "give the reason for the override (blank = no override):",
            parent=self.parent_frame)
        self._report({code.strip(): self._enrol_one(code.strip(), override or None)})

    def _drop(self):
        sel = self.enrolled_list.curselection()
        if not sel:
            return
        code = self.enrolled_list.get(sel[0])
        reason = None
        if self.is_privileged:
            reason = simpledialog.askstring(TITLE, f"Reason for removing {code}:",
                                            parent=self.parent_frame)
            if reason is None:
                return
        elif not messagebox.askyesno(TITLE, f"Drop {code}?", parent=self.parent_frame):
            return
        status = _call(self.parent_frame, _rules().drop, self.student_id, code, self.actor,
                       staff=self.is_privileged, reason=reason, write=True)
        if status:
            sent = _messages().after_drop(self.student_id, code, status, reason, self.actor)
            note = "" if sent else "\n\nThe acknowledgement message could not be sent."
            messagebox.showinfo(TITLE, f"{code}: {status}{note}", parent=self.parent_frame)
            self.refresh()

    # ------------------------------------------------------------------
    # Module catalogue (read-only)
    # ------------------------------------------------------------------
    def _build_catalogue(self):
        filters = _call(self.parent_frame, _catalogue().catalogue_filters) or {
            "departments": [], "levels": []}
        bar = ttk.Frame(self.catalogue_tab, padding=(6, 6, 6, 2))
        bar.pack(fill='x')
        ttk.Label(bar, text="Department").pack(side='left')
        self.cat_department = ttk.Combobox(bar, values=["", *filters["departments"]],
                                           state='readonly', width=28)
        self.cat_department.pack(side='left', padx=4)
        ttk.Label(bar, text="Level").pack(side='left', padx=(8, 0))
        self.cat_level = ttk.Combobox(bar, values=["", *filters["levels"]], state='readonly',
                                      width=6)
        self.cat_level.pack(side='left', padx=4)
        ttk.Label(bar, text="Search").pack(side='left', padx=(8, 0))
        self.cat_search = ttk.Entry(bar, width=26)
        self.cat_search.pack(side='left', padx=4)
        self.cat_search.bind('<Return>', lambda _e: self._load_catalogue())
        for box in (self.cat_department, self.cat_level):
            box.bind('<<ComboboxSelected>>', lambda _e: self._load_catalogue())
        ttk.Button(bar, text="Search", command=self._load_catalogue).pack(side='left', padx=4)
        ttk.Label(self.catalogue_tab, padding=(8, 0), foreground="#555555", wraplength=1000,
                  text="Browse every module. Modules outside your course structure cannot be "
                       "added here: ask your personal tutor or the Registry, who can enrol you "
                       "with a reason.").pack(anchor='w')
        _bar(self.catalogue_tab, (("Module details…", self._catalogue_details),), tk.BOTTOM)
        self.cat_count = ttk.Label(self.catalogue_tab, text="")
        self.cat_count.pack(side='bottom', anchor='w', padx=8)
        self.catalogue_tree = _tree(self.catalogue_tab, [
            ("code", "Module"), ("name", "Name"), ("credits", "Credits"), ("level", "Level"),
            ("dept", "Department"), ("sem", "Semester"), ("you", "For you")],
            [100, 320, 60, 50, 170, 80, 220], height=14)
        self.catalogue_tree.bind('<Double-1>', lambda _e: self._catalogue_details())
        self._load_catalogue()

    def _load_catalogue(self):
        self.catalogue_tree.delete(*self.catalogue_tree.get_children())
        rows = _call(self.parent_frame, _catalogue().catalogue,
                     department=self.cat_department.get() or None,
                     level=self.cat_level.get() or None,
                     search=self.cat_search.get().strip() or None,
                     student_id=self.student_id) or []
        for m in rows:
            self.catalogue_tree.insert('', 'end', iid=m["module_code"], values=(
                m["module_code"], m["module_name"] or "", m["credits"] or "—", m["level"] or "",
                m["department"] or "", m["semester"] or "", m.get("for_you") or ""))
        self.cat_count.configure(text=f"{len(rows)} module(s)"
                                      + (" (first 500 shown)" if len(rows) >= 500 else ""))

    def _catalogue_details(self):
        sel = self.catalogue_tree.selection()
        if not sel:
            return
        d = _call(self.parent_frame, _catalogue().module_details, sel[0],
                  student_id=self.student_id)
        if not isinstance(d, dict):
            return
        win = tk.Toplevel(self.parent_frame)
        win.title(f"{d['module_code']} — {d['module_name'] or ''}")
        win.transient(self.parent_frame.winfo_toplevel())
        win.geometry(f"{min(760, win.winfo_screenwidth() - 80)}x"
                     f"{min(620, win.winfo_screenheight() - 120)}")
        ttk.Button(win, text="Close", command=win.destroy).pack(side='bottom', pady=6)
        text = tk.Text(win, wrap='word', padx=10, pady=8, font=('Segoe UI', 10))
        bar = ttk.Scrollbar(win, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        text.pack(fill='both', expand=True)
        text.insert('end', _catalogue().details_text(d))
        text.configure(state='disabled')

    # ------------------------------------------------------------------
    # Annual registration
    # ------------------------------------------------------------------
    def _build_annual(self):
        rules = _rules()
        ttk.Label(self.annual_tab, padding=8, wraplength=900, text=(
            f"Register for {rules.academic_year()}: confirm the declarations below. Your "
            "compulsory modules for the year are then enrolled.")).pack(anchor='w')
        self.declarations = {}
        for text in rules.DECLARATIONS:
            var = tk.BooleanVar(value=False)
            ttk.Checkbutton(self.annual_tab, text=text, variable=var).pack(anchor='w', padx=16)
            self.declarations[text] = var
        row = ttk.Frame(self.annual_tab, padding=8)
        row.pack(anchor='w')
        ttk.Label(row, text="Mode of study").pack(side='left')
        self.annual_mode = ttk.Combobox(row, values=["full-time", "part-time", "distance",
                                                     "sandwich"], state='readonly', width=14)
        self.annual_mode.set("full-time")
        self.annual_mode.pack(side='left', padx=6)
        self.returning = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text="Returning student (re-registration)",
                        variable=self.returning).pack(side='left', padx=10)
        ttk.Button(self.annual_tab, text="Complete registration",
                   command=self._annual).pack(anchor='w', padx=16, pady=6)

    def _annual(self):
        if not self.student_id:
            messagebox.showinfo(TITLE, "Choose a student first.", parent=self.parent_frame)
            return
        try:
            result = _rules().annual_register(
                self.student_id, self.actor, mode_of_study=self.annual_mode.get(),
                declarations={k: v.get() for k, v in self.declarations.items()},
                returning=self.returning.get())
        except ValueError as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.parent_frame)
            return
        self._report(result["modules"], f"Registered for {result['academic_year']}")

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------
    def _build_approvals(self):
        ttk.Label(self.approval_tab, padding=6, wraplength=900, text=(
            "Optional module choices from students you are personal tutor for, on courses "
            "whose team you are on, or (admins) everyone.")).pack(anchor='w')
        _bar(self.approval_tab, (("Approve", lambda: self._decide(True)),
                                 ("Reject…", lambda: self._decide(False)),
                                 ("Refresh", self._load_approvals)))
        self.approval_tree = _tree(self.approval_tab, [("id", "#"), ("student", "Student"),
                                                       ("course", "Course"), ("mods", "Choices"),
                                                       ("when", "Submitted")],
                                   [40, 220, 80, 380, 140], height=12)
        self._load_approvals()

    def _load_approvals(self):
        self.approval_tree.delete(*self.approval_tree.get_children())
        for r in _call(self.parent_frame, _rules().submissions, self.actor,
                       admin=self.is_admin) or []:
            self.approval_tree.insert('', 'end', iid=str(r["id"]), values=(
                r["id"], f"{r['student_id']} {r['name']}", r["course"], ", ".join(r["modules"]),
                r["submitted_at"]))

    def _decide(self, approve):
        sel = self.approval_tree.selection()
        if not sel:
            return
        note = "" if approve else simpledialog.askstring(TITLE, "Why are they not approved?",
                                                         parent=self.parent_frame)
        if note is None:
            return
        result = _call(self.parent_frame, _rules().decide, int(sel[0]), approve, self.actor,
                       admin=self.is_admin, note=note, write=True)
        if isinstance(result, dict):
            if approve:
                sid = self.approval_tree.item(sel[0], "values")[1].split()[0]
                for code, r in result["results"].items():
                    if r in ("enrolled", "reinstated"):
                        _rules().side_effects(sid, code)
            self._load_approvals()

    # ------------------------------------------------------------------
    # Setup (admins)
    # ------------------------------------------------------------------
    def _build_setup(self):
        inner = ttk.Notebook(self.setup_tab)
        inner.pack(fill='both', expand=True, padx=4, pady=4)
        self._build_periods(inner)
        self._build_rules(inner)
        self._build_credits(inner)
        self._build_reconcile(inner)

    def _build_periods(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Registration periods")
        _bar(tab, (("Add period…", self._add_period), ("Activate / deactivate", self._toggle_period)))
        self.period_tree = _tree(tab, [("id", "#"), ("year", "Year"), ("opens", "Opens"),
                                       ("closes", "Closes"), ("add", "Add by"),
                                       ("drop", "Drop by"), ("withdraw", "Withdraw by"),
                                       ("on", "Active")], [40, 90, 90, 90, 90, 90, 90, 60])
        self._load_periods()

    def _load_periods(self):
        self.period_tree.delete(*self.period_tree.get_children())
        for p in _call(self.parent_frame, _admin_rules().periods) or []:
            self.period_tree.insert('', 'end', iid=str(p["period_id"]), values=(
                p["period_id"], p["academic_year"], p["registration_opens"],
                p["registration_closes"], p["add_deadline"] or "", p["drop_deadline"] or "",
                p["withdraw_deadline"] or "", "yes" if p["is_active"] else "no"))

    def _add_period(self):
        fields = {}
        for key, label in (("academic_year", "Academic year (e.g. 2026/2027)"),
                           ("opens", "Registration opens (YYYY-MM-DD)"),
                           ("closes", "Registration closes"), ("add_deadline", "Add deadline"),
                           ("drop_deadline", "Drop deadline (clean drop)"),
                           ("withdraw_deadline", "Withdrawal deadline (recorded)")):
            value = simpledialog.askstring(TITLE, label, parent=self.parent_frame,
                                           initialvalue=_rules().academic_year()
                                           if key == "academic_year" else "")
            if value is None:
                return
            fields[key] = value.strip() or None
        late = messagebox.askyesno(TITLE, "Allow late adds after the add deadline?",
                                   parent=self.parent_frame)
        if _call(self.parent_frame, _admin_rules().add_period, late_add_allowed=late,
                 admin=True, write=True, **fields):
            self._load_periods()

    def _toggle_period(self):
        sel = self.period_tree.selection()
        if sel:
            active = self.period_tree.item(sel[0], "values")[7] == "yes"
            if _call(self.parent_frame, _admin_rules().set_period_active, int(sel[0]),
                     not active, admin=True, write=True):
                self._load_periods()

    def _build_rules(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Credit rules")
        _bar(tab, (("Set rules for a course and year…", self._set_rules),))
        self.rules_tree = _tree(tab, [("course", "Course"), ("year", "Year"),
                                      ("target", "Target"), ("max", "Max"), ("min", "Min options"),
                                      ("maxo", "Max options"), ("approval", "Approval")],
                                [90, 50, 70, 70, 90, 90, 80])
        self._load_rules()

    def _load_rules(self):
        self.rules_tree.delete(*self.rules_tree.get_children())
        for r in _call(self.parent_frame, _admin_rules().all_rules) or []:
            self.rules_tree.insert('', 'end', values=(
                r["course_code"], r["year_of_study"], r["target_credits"], r["max_credits"],
                r["min_optional"], "" if r["max_optional"] is None else r["max_optional"],
                "yes" if r["needs_approval"] else "no"))

    def _set_rules(self):
        answers = []
        for label, default in (("Course code", ""), ("Year of study", "1"),
                               ("Target credits", "120"), ("Maximum credits", "140"),
                               ("Fewest optional modules", "0"),
                               ("Most optional modules (blank = no limit)", "")):
            value = simpledialog.askstring(TITLE, label, initialvalue=default,
                                           parent=self.parent_frame)
            if value is None:
                return
            answers.append(value.strip())
        approval = messagebox.askyesno(TITLE, "Do optional choices need approval?",
                                       parent=self.parent_frame)
        course, year, target, maximum, low, high = answers
        if _call(self.parent_frame, _admin_rules().set_rules, course, year, target_credits=target,
                 max_credits=maximum, min_optional=low, max_optional=high or None,
                 needs_approval=approval, actor=self.actor, admin=True, write=True):
            self._load_rules()

    def _build_credits(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Module credits")
        ttk.Label(tab, padding=6, text="Modules with no credit value (credit totals and limits "
                                       "cannot count them). Select and set.").pack(anchor='w')
        _bar(tab, (("Set credits for selected…", self._set_credits),))
        self.credit_tree = _tree(tab, [("code", "Module"), ("name", "Name"), ("course", "Course"),
                                       ("level", "Level")], [110, 380, 90, 70], height=12,
                                 select="extended")
        self._load_credits()

    def _load_credits(self):
        self.credit_tree.delete(*self.credit_tree.get_children())
        for m in _call(self.parent_frame, _admin_rules().modules_without_credits) or []:
            self.credit_tree.insert('', 'end', iid=m["module_code"], values=(
                m["module_code"], m["module_name"] or "", m["course"] or "", m["level"] or ""))

    def _set_credits(self):
        codes = list(self.credit_tree.selection())
        value = codes and simpledialog.askinteger(TITLE, f"Credits for {len(codes)} module(s):",
                                                  initialvalue=20, parent=self.parent_frame)
        if value and _call(self.parent_frame, _admin_rules().set_credits, codes, value,
                           self.actor, admin=True, write=True):
            self._load_credits()

    def _build_reconcile(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Enrolment records")
        ttk.Label(tab, padding=6, wraplength=900, text=(
            "student_modules is the enrolment record everything reads; module_enrolments is the "
            "per-registration copy. Rows where they disagree are listed; Fix makes the copy "
            "match.")).pack(anchor='w')
        _bar(tab, (("Fix all", self._fix), ("Refresh", self._load_mismatches)))
        self.mismatch_tree = _tree(tab, [("student", "Student"), ("module", "Module"),
                                         ("record", "student_modules"),
                                         ("copy", "module_enrolments"), ("fix", "Fix")],
                                   [100, 110, 120, 130, 330], height=12)
        self._load_mismatches()

    def _load_mismatches(self):
        self.mismatch_tree.delete(*self.mismatch_tree.get_children())
        for i, m in enumerate(_call(self.parent_frame, _admin_rules().mismatches) or []):
            self.mismatch_tree.insert('', 'end', iid=str(i), values=(
                m["student_id"], m["module_code"], m["record"] or "—", m["copy"] or "—",
                m["fix"]))

    def _fix(self):
        if not messagebox.askyesno(TITLE, "Make module_enrolments match student_modules for "
                                   "every row listed?", parent=self.parent_frame):
            return
        fixed = _call(self.parent_frame, _admin_rules().fix_mismatches, self.actor, admin=True,
                      write=True)
        if fixed is not None:
            messagebox.showinfo(TITLE, f"{fixed} row(s) fixed.", parent=self.parent_frame)
            self._load_mismatches()
