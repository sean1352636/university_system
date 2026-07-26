"""Feature 4 — Learning outcomes & curriculum mapping.

Define a course's learning outcomes (CLOs) and map each one to higher-level
standards: program outcomes, accreditation criteria, or graduate attributes.
Selecting an outcome on the left shows (and lets you edit) its mappings on
the right — the basis for accreditation / curriculum-coverage reporting.
"""

from education_system.systems.university.interfaces.gui.academics.course_management_gui.core.ext_common import (
    ExtFormDialog, tk, ttk, messagebox, _, logger,
)

STANDARD_TYPES = [
    "Program Outcome", "Accreditation Criterion", "Graduate Attribute",
    "Institutional Outcome", "Professional Standard", "Other",
]


class OutcomesTabMixin:
    """Learning-outcomes & mapping tab."""

    def create_outcomes_tab(self):
        if not self._ensure_extension_schema():
            return
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.outcomes",
                                            default="Learning Outcomes"))

            sel = ttk.LabelFrame(frame, text=_("course_management.labels.select_course",
                                               default="Select Course"), padding=10)
            sel.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(sel, text="Course:").pack(side=tk.LEFT, padx=5)
            self._clo_course_combo = ttk.Combobox(sel, width=50, state="readonly")
            self._clo_course_combo.pack(side=tk.LEFT, padx=5)
            self._clo_course_combo.bind("<<ComboboxSelected>>", self._reload_outcomes)
            ttk.Button(sel, text=_("common.refresh", default="Refresh"),
                       command=self._reload_clo_courses).pack(side=tk.LEFT, padx=5)

            paned = ttk.Panedwindow(frame, orient=tk.HORIZONTAL)
            paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            paned.add(self._build_outcomes_pane(paned), weight=2)
            paned.add(self._build_mappings_pane(paned), weight=2)

            self._reload_clo_courses()
        except Exception as exc:
            self._ext_report_error("build Learning Outcomes tab", exc)

    # -- course selection ----------------------------------------------

    def _reload_clo_courses(self):
        try:
            labels, self._clo_course_map = self._ext_course_choices()
            self._clo_course_combo["values"] = labels
            if labels and not self._clo_course_combo.get():
                self._clo_course_combo.current(0)
            self._reload_outcomes()
        except Exception as exc:
            self._ext_report_error("load courses", exc)

    def _current_clo_course(self):
        return self._ext_code_from_label(self._clo_course_combo.get(),
                                         getattr(self, "_clo_course_map", {}))

    # ------------------------------------------------------------------
    # Outcomes pane
    # ------------------------------------------------------------------

    def _build_outcomes_pane(self, parent):
        pane = ttk.LabelFrame(parent, text="Course Learning Outcomes", padding=8)
        bar = ttk.Frame(pane)
        bar.pack(fill=tk.X, pady=3)
        if self._ext_can_edit():
            ttk.Button(bar, text=_("common.add", default="Add"),
                       command=self._add_outcome).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.edit", default="Edit"),
                       command=self._edit_outcome).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.delete", default="Delete"),
                       command=self._delete_outcome).pack(side=tk.LEFT, padx=5)

        cols = ("ID", "Code", "Description")
        self._clo_tree = ttk.Treeview(pane, columns=cols, show="headings", height=14)
        for c, w in (("ID", 45), ("Code", 80), ("Description", 360)):
            self._clo_tree.heading(c, text=c)
            self._clo_tree.column(c, width=w)
        self._clo_tree.bind("<<TreeviewSelect>>", self._reload_mappings)
        sb = ttk.Scrollbar(pane, orient=tk.VERTICAL, command=self._clo_tree.yview)
        self._clo_tree.configure(yscrollcommand=sb.set)
        self._clo_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        return pane

    def _reload_outcomes(self, *_a):
        if not hasattr(self, "_clo_tree"):
            return
        self._ext_clear_tree(self._clo_tree)
        if hasattr(self, "_mapping_tree"):
            self._ext_clear_tree(self._mapping_tree)
        code = self._current_clo_course()
        if not code:
            return
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, outcome_code, description FROM course_learning_outcomes "
                    "WHERE course_code=? ORDER BY outcome_code, id", (code,))
                rows = cur.fetchall()
            for row in rows:
                self._clo_tree.insert("", tk.END, values=row)
            logger.debug("Loaded %d outcomes for %s", len(rows), code)
        except Exception as exc:
            self._ext_report_error("load learning outcomes", exc)

    def _outcome_fields(self, data=None):
        data = data or {}
        return [
            ("outcome_code", "Code (e.g. CLO1):",
             {"default": data.get("outcome_code", ""), "width": 20}),
            ("description", "Description:",
             {"type": "text", "default": data.get("description", ""), "height": 6}),
        ]

    def _add_outcome(self):
        if not self._ext_can_edit():
            return
        code = self._current_clo_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return

        def submit(values):
            desc = (values.get("description") or "").strip()
            if not desc:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Description is required.")
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "INSERT INTO course_learning_outcomes "
                        "(course_code, outcome_code, description, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (code, values["outcome_code"], desc,
                         self._ext_now(), self._ext_now()))
            except Exception as exc:
                self._ext_report_error("add learning outcome", exc)
                return False
            self._ext_audit("create", "learning_outcome", course_code=code,
                            outcome_code=values["outcome_code"])
            self._reload_outcomes()
            return True

        ExtFormDialog(self.root, self, f"Add Learning Outcome for {code}",
                      self._outcome_fields(), submit,
                      submit_label="Add", geometry="520x320")

    def _selected_outcome(self):
        vals = self._ext_selected_values(self._clo_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select an outcome first.")
            return None
        return vals

    def _edit_outcome(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_outcome()
        if not vals:
            return
        clo_id = vals[0]
        data = {"outcome_code": vals[1], "description": vals[2]}

        def submit(values):
            desc = (values.get("description") or "").strip()
            if not desc:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Description is required.")
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "UPDATE course_learning_outcomes SET outcome_code=?, "
                        "description=?, updated_at=? WHERE id=?",
                        (values["outcome_code"], desc, self._ext_now(), clo_id))
            except Exception as exc:
                self._ext_report_error("update learning outcome", exc)
                return False
            self._ext_audit("update", "learning_outcome", outcome_id=clo_id)
            self._reload_outcomes()
            return True

        ExtFormDialog(self.root, self, "Edit Learning Outcome",
                      self._outcome_fields(data), submit,
                      submit_label="Save", geometry="520x320")

    def _delete_outcome(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_outcome()
        if not vals:
            return
        clo_id = vals[0]
        if not messagebox.askyesno(
                _("common.confirm", default="Confirm"),
                f"Delete outcome '{vals[1] or vals[0]}' and all its mappings?"):
            return
        try:
            with self._ext_db(write=True) as conn:
                conn.execute("DELETE FROM outcome_program_mappings WHERE outcome_id=?",
                             (clo_id,))
                conn.execute("DELETE FROM course_learning_outcomes WHERE id=?", (clo_id,))
        except Exception as exc:
            self._ext_report_error("delete learning outcome", exc)
            return
        self._ext_audit("delete", "learning_outcome", outcome_id=clo_id)
        self._reload_outcomes()

    # ------------------------------------------------------------------
    # Mappings pane
    # ------------------------------------------------------------------

    def _build_mappings_pane(self, parent):
        pane = ttk.LabelFrame(parent, text="Mapped standards (for selected outcome)",
                              padding=8)
        bar = ttk.Frame(pane)
        bar.pack(fill=tk.X, pady=3)
        if self._ext_can_edit():
            ttk.Button(bar, text="Add Mapping",
                       command=self._add_mapping).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.delete", default="Remove"),
                       command=self._delete_mapping).pack(side=tk.LEFT, padx=5)

        cols = ("ID", "Type", "Code", "Description")
        self._mapping_tree = ttk.Treeview(pane, columns=cols, show="headings", height=14)
        widths = {"ID": 45, "Type": 140, "Code": 90, "Description": 280}
        for c in cols:
            self._mapping_tree.heading(c, text=c)
            self._mapping_tree.column(c, width=widths.get(c, 100))
        sb = ttk.Scrollbar(pane, orient=tk.VERTICAL, command=self._mapping_tree.yview)
        self._mapping_tree.configure(yscrollcommand=sb.set)
        self._mapping_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        return pane

    def _current_outcome_id(self):
        vals = self._ext_selected_values(self._clo_tree)
        return vals[0] if vals else None

    def _reload_mappings(self, *_a):
        if not hasattr(self, "_mapping_tree"):
            return
        self._ext_clear_tree(self._mapping_tree)
        outcome_id = self._current_outcome_id()
        if not outcome_id:
            return
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, standard_type, standard_code, standard_description "
                    "FROM outcome_program_mappings WHERE outcome_id=? "
                    "ORDER BY standard_type, standard_code", (outcome_id,))
                rows = cur.fetchall()
            for row in rows:
                self._mapping_tree.insert("", tk.END, values=row)
        except Exception as exc:
            self._ext_report_error("load outcome mappings", exc)

    def _add_mapping(self):
        if not self._ext_can_edit():
            return
        outcome_id = self._current_outcome_id()
        if not outcome_id:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a learning outcome first.")
            return

        def submit(values):
            scode = (values.get("standard_code") or "").strip()
            sdesc = (values.get("standard_description") or "").strip()
            if not scode and not sdesc:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Provide a standard code or description.")
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "INSERT INTO outcome_program_mappings "
                        "(outcome_id, standard_type, standard_code, "
                        " standard_description, created_at) VALUES (?, ?, ?, ?, ?)",
                        (outcome_id, values["standard_type"], scode, sdesc,
                         self._ext_now()))
            except Exception as exc:
                self._ext_report_error("add mapping", exc)
                return False
            self._ext_audit("create", "outcome_mapping", outcome_id=outcome_id,
                            standard_code=scode)
            self._reload_mappings()
            return True

        ExtFormDialog(
            self.root, self, "Map Outcome to Standard",
            [("standard_type", "Standard type:",
              {"type": "combo", "values": STANDARD_TYPES,
               "default": "Program Outcome"}),
             ("standard_code", "Standard code:", {"width": 25}),
             ("standard_description", "Standard description:",
              {"type": "text", "height": 4})],
            submit, submit_label="Add", geometry="520x340")

    def _delete_mapping(self):
        if not self._ext_can_edit():
            return
        vals = self._ext_selected_values(self._mapping_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a mapping to remove.")
            return
        if not messagebox.askyesno(_("common.confirm", default="Confirm"),
                                   f"Remove mapping to '{vals[2] or vals[3]}'?"):
            return
        try:
            with self._ext_db(write=True) as conn:
                conn.execute("DELETE FROM outcome_program_mappings WHERE id=?", (vals[0],))
        except Exception as exc:
            self._ext_report_error("remove mapping", exc)
            return
        self._ext_audit("delete", "outcome_mapping", mapping_id=vals[0])
        self._reload_mappings()
