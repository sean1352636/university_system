"""Feature 4 — Learning outcomes & curriculum mapping.

Define a course's learning outcomes (CLOs) and map each one to higher-level
standards: program outcomes, accreditation criteria, or graduate attributes.
Selecting an outcome on the left shows (and lets you edit) its mappings on
the right — the basis for accreditation / curriculum-coverage reporting.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.core.ext_common import (
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
            ttk.Label(sel, text=_t('gui.academics.course_management_gui.core.outcomes_tab.labels.course', default="Course:")).pack(side=tk.LEFT, padx=5)
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
        pane = ttk.LabelFrame(parent, text=_t('gui.academics.course_management_gui.core.outcomes_tab.labels.course_learning_outcomes', default="Course Learning Outcomes"), padding=8)
        bar = ttk.Frame(pane)
        bar.pack(fill=tk.X, pady=3)
        if self._ext_can_edit():
            ttk.Button(bar, text=_("common.add", default="Add"),
                       command=self._add_outcome).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.edit", default="Edit"),
                       command=self._edit_outcome).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.delete", default="Delete"),
                       command=self._delete_outcome).pack(side=tk.LEFT, padx=5)

        cols = ("ID", "Code", "Bloom", "Description")
        self._clo_tree = ttk.Treeview(pane, columns=cols, show="headings", height=14)
        for c, w in (("ID", 45), ("Code", 80), ("Bloom", 90), ("Description", 300)):
            self._clo_tree.heading(c, text=c)
            self._clo_tree.column(c, width=w)
        self._clo_tree.bind("<<TreeviewSelect>>", self._reload_mappings)
        sb = ttk.Scrollbar(pane, orient=tk.VERTICAL, command=self._clo_tree.yview)
        self._clo_tree.configure(yscrollcommand=sb.set)
        self._clo_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        return pane

    def _ensure_bloom_column(self):
        """Add ``course_learning_outcomes.bloom_level`` if it is missing.

        Guarded ALTER rather than a migration, matching how the rest of this
        codebase adds a late column. Without it the Bloom dropdown would be a
        control that silently discarded whatever you chose.
        """
        if getattr(self, "_bloom_column_ready", False):
            return True
        try:
            with self._ext_db(write=True) as conn:
                cols = {r[1] for r in conn.execute(
                    "PRAGMA table_info(course_learning_outcomes)").fetchall()}
                if "bloom_level" not in cols:
                    conn.execute("ALTER TABLE course_learning_outcomes "
                                 "ADD COLUMN bloom_level TEXT")
            self._bloom_column_ready = True
        except Exception:
            logger.debug("could not add bloom_level column", exc_info=True)
            self._bloom_column_ready = False
        return self._bloom_column_ready

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
                self._ensure_bloom_column()
                cur.execute(
                    "SELECT id, outcome_code, COALESCE(bloom_level, ''), description "
                    "FROM course_learning_outcomes "
                    "WHERE course_code=? ORDER BY outcome_code, id", (code,))
                rows = cur.fetchall()
            for row in rows:
                self._clo_tree.insert("", tk.END, values=row)
            logger.debug("Loaded %d outcomes for %s", len(rows), code)
        except Exception as exc:
            self._ext_report_error("load learning outcomes", exc)

    #: Bloom's taxonomy levels, with the verbs a learning outcome usually
    #: opens with. Offered as a dropdown so a CLO reads consistently rather
    #: than however the author happened to phrase it.
    BLOOM_LEVELS = [
        "Remember — define, list, recall, name",
        "Understand — describe, explain, summarise",
        "Apply — apply, demonstrate, implement, use",
        "Analyse — analyse, compare, differentiate, examine",
        "Evaluate — appraise, critique, justify, defend",
        "Create — design, construct, develop, formulate",
    ]

    def _next_outcome_code(self, course_code):
        """The next unused ``CLOn`` for *course_code*."""
        used = set()
        try:
            with self._ext_db() as conn:
                for (code,) in conn.execute(
                        "SELECT outcome_code FROM course_learning_outcomes "
                        "WHERE course_code = ?", (course_code,)).fetchall():
                    used.add(str(code or "").strip().upper())
        except Exception:
            logger.debug("could not read existing outcome codes", exc_info=True)
        for n in range(1, 41):
            if f"CLO{n}" not in used:
                return f"CLO{n}"
        return "CLO1"

    def _outcome_codes(self, course_code, current=""):
        """Dropdown values: every CLOn up to a sensible ceiling.

        The code used to be a free-text box labelled "Code (e.g. CLO1)", so
        anything at all was accepted — the one outcome in this database is
        coded ``ACC``, which is a course code, not an outcome code.
        """
        codes = [f"CLO{n}" for n in range(1, 21)]
        current = (current or "").strip()
        if current and current not in codes:
            # Keep an existing non-standard code selectable so editing an old
            # row doesn't silently renumber it.
            codes.insert(0, current)
        return codes

    def _outcome_fields(self, data=None, course_code=None):
        data = data or {}
        current = data.get("outcome_code", "")
        default = current or (self._next_outcome_code(course_code) if course_code else "CLO1")
        return [
            ("outcome_code", "Code:",
             {"type": "combo", "values": self._outcome_codes(course_code, current),
              "default": default, "width": 20}),
            ("bloom_level", "Bloom's level:",
             {"type": "combo", "values": [""] + self.BLOOM_LEVELS,
              # Stored as the bare level ("Apply"); match it back to the full
              # dropdown entry so editing shows the current choice selected.
              "default": next((b for b in self.BLOOM_LEVELS
                               if b.split(" — ")[0] == str(data.get("bloom_level", "")).strip()),
                              ""),
              "width": 44}),
            ("description", "Description:",
             {"type": "text", "default": data.get("description", ""), "height": 6}),
        ]

    def _add_outcome(self):
        if not self._ext_can_edit():
            return
        code = self._current_clo_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   _t('gui.academics.course_management_gui.core.outcomes_tab.dialogs.select_a_course_first', default="Select a course first."))
            return

        def submit(values):
            desc = (values.get("description") or "").strip()
            if not desc:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     _t('gui.academics.course_management_gui.core.outcomes_tab.dialogs.description_is_required', default="Description is required."))
                return False
            try:
                with self._ext_db(write=True) as conn:
                    self._ensure_bloom_column()
                    conn.execute(
                        "INSERT INTO course_learning_outcomes "
                        "(course_code, outcome_code, bloom_level, description, "
                        " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (code, values["outcome_code"],
                         (values.get("bloom_level") or "").split(" — ")[0],
                         desc, self._ext_now(), self._ext_now()))
            except Exception as exc:
                self._ext_report_error("add learning outcome", exc)
                return False
            self._ext_audit("create", "learning_outcome", course_code=code,
                            outcome_code=values["outcome_code"])
            self._reload_outcomes()
            return True

        ExtFormDialog(self.root, self, f"Add Learning Outcome for {code}",
                      self._outcome_fields(course_code=code), submit,
                      submit_label="Add", geometry="520x320")

    def _selected_outcome(self):
        vals = self._ext_selected_values(self._clo_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   _t('gui.academics.course_management_gui.core.outcomes_tab.dialogs.select_an_outcome_first', default="Select an outcome first."))
            return None
        return vals

    def _edit_outcome(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_outcome()
        if not vals:
            return
        clo_id = vals[0]
        # Column order is (ID, Code, Bloom, Description).
        data = {"outcome_code": vals[1], "bloom_level": vals[2],
                "description": vals[3]}
        code = self._current_clo_course()

        def submit(values):
            desc = (values.get("description") or "").strip()
            if not desc:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     _t('gui.academics.course_management_gui.core.outcomes_tab.dialogs.description_is_required', default="Description is required."))
                return False
            try:
                with self._ext_db(write=True) as conn:
                    self._ensure_bloom_column()
                    conn.execute(
                        "UPDATE course_learning_outcomes SET outcome_code=?, "
                        "bloom_level=?, description=?, updated_at=? WHERE id=?",
                        (values["outcome_code"],
                         (values.get("bloom_level") or "").split(" — ")[0],
                         desc, self._ext_now(), clo_id))
            except Exception as exc:
                self._ext_report_error("update learning outcome", exc)
                return False
            self._ext_audit("update", "learning_outcome", outcome_id=clo_id)
            self._reload_outcomes()
            return True

        ExtFormDialog(self.root, self, "Edit Learning Outcome",
                      self._outcome_fields(data, course_code=code), submit,
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
        pane = ttk.LabelFrame(parent, text=_t('gui.academics.course_management_gui.core.outcomes_tab.labels.mapped_standards_for_selected_outcome', default="Mapped standards (for selected outcome)"),
                              padding=8)
        bar = ttk.Frame(pane)
        bar.pack(fill=tk.X, pady=3)
        if self._ext_can_edit():
            ttk.Button(bar, text=_t('gui.academics.course_management_gui.core.outcomes_tab.buttons.add_mapping', default="Add Mapping"),
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
                                   _t('gui.academics.course_management_gui.core.outcomes_tab.dialogs.select_a_learning_outcome_first', default="Select a learning outcome first."))
            return

        def submit(values):
            scode = (values.get("standard_code") or "").strip()
            sdesc = (values.get("standard_description") or "").strip()
            if not scode and not sdesc:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     _t('gui.academics.course_management_gui.core.outcomes_tab.dialogs.provide_a_standard_code_or_description', default="Provide a standard code or description."))
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
             # Editable combo: pick a standard already in use, or type a new
             # one. A plain entry gave no hint that these codes repeat.
             ("standard_code", "Standard code:",
              {"type": "combo", "values": self._known_standard_codes(),
               "state": "normal", "width": 25}),
             ("standard_description", "Standard description:",
              {"type": "text", "height": 4})],
            submit, submit_label="Add", geometry="520x340")

    def _known_standard_codes(self):
        """Standard codes already mapped anywhere, for the dropdown."""
        try:
            with self._ext_db() as conn:
                rows = conn.execute(
                    "SELECT DISTINCT standard_code FROM outcome_program_mappings "
                    "WHERE COALESCE(TRIM(standard_code), '') <> '' "
                    "ORDER BY standard_code").fetchall()
            return [r[0] for r in rows]
        except Exception:
            logger.debug("could not read standard codes", exc_info=True)
            return []

    def _delete_mapping(self):
        if not self._ext_can_edit():
            return
        vals = self._ext_selected_values(self._mapping_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   _t('gui.academics.course_management_gui.core.outcomes_tab.dialogs.select_a_mapping_to_remove', default="Select a mapping to remove."))
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
