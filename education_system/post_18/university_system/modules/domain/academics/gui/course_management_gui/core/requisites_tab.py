"""Feature 2 — Co-requisites & enrolment restrictions.

Prerequisites already exist elsewhere in the GUI. This tab adds the two
registrar-level rules prerequisites cannot express:

* **Co-requisites** – courses that must be taken concurrently.
* **Enrolment restrictions / reserved seats** – e.g. "Majors only",
  "Seniors only", or "10 seats reserved for Honors".

A course is chosen at the top; both lists below refresh for that course.
"""

from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core.ext_common import (
    ExtFormDialog, tk, ttk, messagebox, _, logger,
)

RESTRICTION_TYPES = [
    "Major", "Minor", "Program", "Class Standing", "Department",
    "Cohort", "Instructor Consent", "Reserved Seats", "Other",
]


class RequisitesTabMixin:
    """Co-requisites & enrolment-restrictions tab."""

    def create_requisites_tab(self):
        if not self._ensure_extension_schema():
            return
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.requisites",
                                            default="Co-reqs & Restrictions"))

            sel = ttk.LabelFrame(frame, text=_("course_management.labels.select_course",
                                               default="Select Course"), padding=10)
            sel.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(sel, text="Course:").pack(side=tk.LEFT, padx=5)
            self._req_course_combo = ttk.Combobox(sel, width=50, state="readonly")
            self._req_course_combo.pack(side=tk.LEFT, padx=5)
            self._req_course_combo.bind("<<ComboboxSelected>>", self._reload_requisites)
            ttk.Button(sel, text=_("common.refresh", default="Refresh"),
                       command=self._reload_req_courses).pack(side=tk.LEFT, padx=5)

            paned = ttk.Panedwindow(frame, orient=tk.VERTICAL)
            paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            paned.add(self._build_coreq_pane(paned), weight=1)
            paned.add(self._build_restriction_pane(paned), weight=1)

            self._reload_req_courses()
        except Exception as exc:
            self._ext_report_error("build Co-reqs & Restrictions tab", exc)

    # -- shared course selection ---------------------------------------

    def _reload_req_courses(self):
        try:
            labels, self._req_course_map = self._ext_course_choices()
            self._req_course_combo["values"] = labels
            if labels and not self._req_course_combo.get():
                self._req_course_combo.current(0)
            self._reload_requisites()
        except Exception as exc:
            self._ext_report_error("load courses", exc)

    def _current_req_course(self):
        return self._ext_code_from_label(self._req_course_combo.get(),
                                         getattr(self, "_req_course_map", {}))

    def _reload_requisites(self, *_a):
        self._reload_coreqs()
        self._reload_restrictions()

    # ------------------------------------------------------------------
    # Co-requisites pane
    # ------------------------------------------------------------------

    def _build_coreq_pane(self, parent):
        pane = ttk.LabelFrame(parent, text="Co-requisites (taken concurrently)",
                              padding=8)
        bar = ttk.Frame(pane)
        bar.pack(fill=tk.X, pady=3)
        if self._ext_can_edit():
            ttk.Button(bar, text="Add Co-requisite",
                       command=self._add_coreq).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.delete", default="Remove"),
                       command=self._delete_coreq).pack(side=tk.LEFT, padx=5)

        cols = ("ID", "Co-requisite", "Notes")
        self._coreq_tree = ttk.Treeview(pane, columns=cols, show="headings", height=6)
        for c, w in (("ID", 45), ("Co-requisite", 160), ("Notes", 400)):
            self._coreq_tree.heading(c, text=c)
            self._coreq_tree.column(c, width=w)
        self._coreq_tree.pack(fill=tk.BOTH, expand=True)
        return pane

    def _reload_coreqs(self):
        if not hasattr(self, "_coreq_tree"):
            return
        self._ext_clear_tree(self._coreq_tree)
        code = self._current_req_course()
        if not code:
            return
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, corequisite_code, notes FROM course_corequisites_ext "
                    "WHERE course_code=? ORDER BY corequisite_code", (code,))
                rows = cur.fetchall()
            for row in rows:
                self._coreq_tree.insert("", tk.END, values=row)
        except Exception as exc:
            self._ext_report_error("load co-requisites", exc)

    def _add_coreq(self):
        if not self._ext_can_edit():
            return
        code = self._current_req_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return
        labels, course_map = self._ext_course_choices()
        # A course cannot be its own co-requisite.
        labels = [l for l in labels
                  if self._ext_code_from_label(l, course_map) != code]

        def submit(values):
            coreq = self._ext_code_from_label(values.get("corequisite"), course_map)
            if not coreq:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Select a co-requisite course.")
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "INSERT INTO course_corequisites_ext "
                        "(course_code, corequisite_code, notes, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (code, coreq, values.get("notes", ""), self._ext_now()))
            except Exception as exc:
                self._ext_report_error("add co-requisite (already linked?)", exc)
                return False
            self._ext_audit("create", "course_corequisite",
                            course_code=code, corequisite=coreq)
            self._ext_notify_course_changed(code, "corequisite_added")
            self._reload_coreqs()
            return True

        ExtFormDialog(
            self.root, self, f"Add Co-requisite for {code}",
            [("corequisite", "Co-requisite course:",
              {"type": "combo", "values": labels, "width": 43}),
             ("notes", "Notes:", {"type": "text", "height": 3})],
            submit, submit_label="Add", geometry="520x260")

    def _delete_coreq(self):
        if not self._ext_can_edit():
            return
        vals = self._ext_selected_values(self._coreq_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a co-requisite to remove.")
            return
        if not messagebox.askyesno(_("common.confirm", default="Confirm"),
                                   f"Remove co-requisite '{vals[1]}'?"):
            return
        try:
            with self._ext_db(write=True) as conn:
                conn.execute("DELETE FROM course_corequisites_ext WHERE id=?", (vals[0],))
        except Exception as exc:
            self._ext_report_error("remove co-requisite", exc)
            return
        self._ext_audit("delete", "course_corequisite", coreq_id=vals[0])
        self._reload_coreqs()

    # ------------------------------------------------------------------
    # Restrictions pane
    # ------------------------------------------------------------------

    def _build_restriction_pane(self, parent):
        pane = ttk.LabelFrame(parent, text="Enrolment restrictions & reserved seats",
                              padding=8)
        bar = ttk.Frame(pane)
        bar.pack(fill=tk.X, pady=3)
        if self._ext_can_edit():
            ttk.Button(bar, text="Add Restriction",
                       command=self._add_restriction).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.edit", default="Edit"),
                       command=self._edit_restriction).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.delete", default="Remove"),
                       command=self._delete_restriction).pack(side=tk.LEFT, padx=5)

        cols = ("ID", "Type", "Applies To", "Reserved Seats", "Active")
        self._restrict_tree = ttk.Treeview(pane, columns=cols, show="headings", height=6)
        widths = {"ID": 45, "Type": 140, "Applies To": 240,
                  "Reserved Seats": 110, "Active": 70}
        for c in cols:
            self._restrict_tree.heading(c, text=c)
            self._restrict_tree.column(c, width=widths.get(c, 100))
        self._restrict_tree.pack(fill=tk.BOTH, expand=True)
        return pane

    def _reload_restrictions(self):
        if not hasattr(self, "_restrict_tree"):
            return
        self._ext_clear_tree(self._restrict_tree)
        code = self._current_req_course()
        if not code:
            return
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, restriction_type, restriction_value, "
                    "reserved_seats, active FROM course_restrictions "
                    "WHERE course_code=? ORDER BY restriction_type", (code,))
                rows = cur.fetchall()
            for rid, rtype, rval, seats, active in rows:
                self._restrict_tree.insert("", tk.END, values=(
                    rid, rtype, rval, seats, "Yes" if active else "No"))
        except Exception as exc:
            self._ext_report_error("load restrictions", exc)

    def _restriction_fields(self, data=None):
        data = data or {}
        return [
            ("restriction_type", "Type:",
             {"type": "combo", "values": RESTRICTION_TYPES,
              "default": data.get("restriction_type", "Major")}),
            ("restriction_value", "Applies to (value):",
             {"default": data.get("restriction_value", "")}),
            ("reserved_seats", "Reserved seats (0 = none):",
             {"default": data.get("reserved_seats", "0"), "width": 10}),
            ("active", "Active", {"type": "check",
                                  "default": data.get("active", True)}),
        ]

    def _parse_seats(self, values):
        try:
            seats = int(values.get("reserved_seats") or 0)
        except (TypeError, ValueError):
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 "Reserved seats must be a whole number.")
            return None
        if seats < 0:
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 "Reserved seats cannot be negative.")
            return None
        return seats

    def _add_restriction(self):
        if not self._ext_can_edit():
            return
        code = self._current_req_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return

        def submit(values):
            seats = self._parse_seats(values)
            if seats is None:
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "INSERT INTO course_restrictions "
                        "(course_code, restriction_type, restriction_value, "
                        " reserved_seats, active, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (code, values["restriction_type"], values["restriction_value"],
                         seats, 1 if values.get("active") else 0, self._ext_now()))
            except Exception as exc:
                self._ext_report_error("add restriction", exc)
                return False
            self._ext_audit("create", "course_restriction", course_code=code,
                            restriction_type=values["restriction_type"])
            self._reload_restrictions()
            return True

        ExtFormDialog(self.root, self, f"Add Restriction for {code}",
                      self._restriction_fields(), submit,
                      submit_label="Add", geometry="480x320")

    def _selected_restriction(self):
        vals = self._ext_selected_values(self._restrict_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a restriction first.")
            return None
        return vals

    def _edit_restriction(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_restriction()
        if not vals:
            return
        rid = vals[0]
        data = {"restriction_type": vals[1], "restriction_value": vals[2],
                "reserved_seats": vals[3], "active": vals[4] == "Yes"}

        def submit(values):
            seats = self._parse_seats(values)
            if seats is None:
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "UPDATE course_restrictions SET restriction_type=?, "
                        "restriction_value=?, reserved_seats=?, active=? WHERE id=?",
                        (values["restriction_type"], values["restriction_value"],
                         seats, 1 if values.get("active") else 0, rid))
            except Exception as exc:
                self._ext_report_error("update restriction", exc)
                return False
            self._ext_audit("update", "course_restriction", restriction_id=rid)
            self._reload_restrictions()
            return True

        ExtFormDialog(self.root, self, "Edit Restriction",
                      self._restriction_fields(data), submit,
                      submit_label="Save", geometry="480x320")

    def _delete_restriction(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_restriction()
        if not vals:
            return
        if not messagebox.askyesno(_("common.confirm", default="Confirm"),
                                   f"Remove restriction '{vals[1]}: {vals[2]}'?"):
            return
        try:
            with self._ext_db(write=True) as conn:
                conn.execute("DELETE FROM course_restrictions WHERE id=?", (vals[0],))
        except Exception as exc:
            self._ext_report_error("remove restriction", exc)
            return
        self._ext_audit("delete", "course_restriction", restriction_id=vals[0])
        self._reload_restrictions()
