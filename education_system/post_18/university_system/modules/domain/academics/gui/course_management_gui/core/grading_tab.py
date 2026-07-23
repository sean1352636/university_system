"""Feature 9 — Grading scheme & assessment weighting.

Per-course grading configuration that feeds the Grade Tracking system:

* a **scheme** (Letter / Pass-Fail / Percentage / Competency) and pass mark;
* a list of **assessment components** with percentage weights (e.g.
  40% Exam / 60% Coursework), with a live total and a 100% sanity check.
"""

from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core.ext_common import (
    ExtFormDialog, tk, ttk, messagebox, _, logger,
)

SCHEME_TYPES = ["Letter", "Pass/Fail", "Percentage", "Competency", "Credit/No Credit"]


class GradingTabMixin:
    """Grading scheme & assessment-weighting tab."""

    def create_grading_tab(self):
        if not self._ensure_extension_schema():
            return
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.grading",
                                            default="Grading Schemes"))

            sel = ttk.LabelFrame(frame, text=_("course_management.labels.select_course",
                                               default="Select Course"), padding=10)
            sel.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(sel, text="Course:").pack(side=tk.LEFT, padx=5)
            self._gr_course_combo = ttk.Combobox(sel, width=46, state="readonly")
            self._gr_course_combo.pack(side=tk.LEFT, padx=5)
            self._gr_course_combo.bind("<<ComboboxSelected>>", self._reload_grading)
            ttk.Button(sel, text=_("common.refresh", default="Refresh"),
                       command=self._reload_gr_courses).pack(side=tk.LEFT, padx=5)
            # Cross-link: grading schemes here configure how grades are
            # weighted; Grade Management is where those grades are recorded.
            ttk.Button(sel, text=_("course_management.buttons.open_grade_management",
                                   default="Open Grade Management →"),
                       command=self._open_grade_management).pack(side=tk.RIGHT, padx=5)

            # Scheme row.
            scheme = ttk.LabelFrame(frame, text="Grading scheme", padding=10)
            scheme.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(scheme, text="Type:").grid(row=0, column=0, sticky=tk.W, padx=5)
            self._gr_scheme_var = tk.StringVar(value="Letter")
            self._gr_scheme_combo = ttk.Combobox(
                scheme, textvariable=self._gr_scheme_var, values=SCHEME_TYPES,
                state="readonly" if self._ext_can_edit() else "disabled", width=20)
            self._gr_scheme_combo.grid(row=0, column=1, padx=5)
            ttk.Label(scheme, text="Pass mark (%):").grid(row=0, column=2, sticky=tk.W,
                                                          padx=(20, 5))
            self._gr_pass_var = tk.StringVar(value="50")
            ttk.Entry(scheme, textvariable=self._gr_pass_var, width=8,
                      state="normal" if self._ext_can_edit() else "readonly"
                      ).grid(row=0, column=3, padx=5)
            if self._ext_can_edit():
                ttk.Button(scheme, text="Save scheme",
                           command=self._save_scheme).grid(row=0, column=4, padx=15)

            # Components.
            comp = ttk.LabelFrame(frame, text="Assessment components", padding=8)
            comp.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            bar = ttk.Frame(comp)
            bar.pack(fill=tk.X, pady=3)
            if self._ext_can_edit():
                ttk.Button(bar, text="Add Component",
                           command=self._add_component).pack(side=tk.LEFT, padx=5)
                ttk.Button(bar, text=_("common.edit", default="Edit"),
                           command=self._edit_component).pack(side=tk.LEFT, padx=5)
                ttk.Button(bar, text=_("common.delete", default="Delete"),
                           command=self._delete_component).pack(side=tk.LEFT, padx=5)
                # Tie-in: turn these weighted components into actual gradebook
                # assessments in Grade Management for the course's module(s).
                ttk.Button(bar, text=_("course_management.buttons.sync_gradebook",
                                       default="Sync weights → Grade Management"),
                           command=self._push_components_to_gradebook).pack(side=tk.LEFT, padx=15)
            self._gr_total_var = tk.StringVar(value="")
            ttk.Label(bar, textvariable=self._gr_total_var,
                      font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=10)

            # Live read-back from Grade Management for the selected course.
            self._gr_gradebook_var = tk.StringVar(value="")
            ttk.Label(frame, textvariable=self._gr_gradebook_var,
                      foreground="#2c3e50").pack(fill=tk.X, padx=8, pady=(0, 6))

            cols = ("ID", "Component", "Weight %", "Notes")
            self._gr_tree = ttk.Treeview(comp, columns=cols, show="headings", height=12)
            for c, w in (("ID", 45), ("Component", 220), ("Weight %", 90),
                         ("Notes", 320)):
                self._gr_tree.heading(c, text=c)
                self._gr_tree.column(c, width=w)
            sb = ttk.Scrollbar(comp, orient=tk.VERTICAL, command=self._gr_tree.yview)
            self._gr_tree.configure(yscrollcommand=sb.set)
            self._gr_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

            self._reload_gr_courses()
        except Exception as exc:
            self._ext_report_error("build Grading Schemes tab", exc)

    def _open_grade_management(self):
        """Open the Grade Management (Grade Tracking) GUI in its own window."""
        def _build(top):
            from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app import (
                GradeTrackingApp,
            )
            GradeTrackingApp(top, auth=getattr(self, "auth", None))
        self._ext_launch_window(
            _("course_management.titles.grade_management", default="Grade Management"),
            _build, geometry="1400x900", minsize=(1200, 800))

    def _reload_gr_courses(self):
        try:
            labels, self._gr_course_map = self._ext_course_choices()
            self._gr_course_combo["values"] = labels
            if labels and not self._gr_course_combo.get():
                self._gr_course_combo.current(0)
            self._reload_grading()
        except Exception as exc:
            self._ext_report_error("load courses", exc)

    def _current_gr_course(self):
        return self._ext_code_from_label(self._gr_course_combo.get(),
                                         getattr(self, "_gr_course_map", {}))

    def _reload_grading(self, *_a):
        code = self._current_gr_course()
        # Load scheme.
        if code:
            try:
                with self._ext_db() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT scheme_type, pass_mark FROM course_grading_schemes "
                        "WHERE course_code=?", (code,))
                    row = cur.fetchone()
                if row:
                    self._gr_scheme_var.set(row[0])
                    self._gr_pass_var.set(str(row[1]))
                else:
                    self._gr_scheme_var.set("Letter")
                    self._gr_pass_var.set("50")
            except Exception as exc:
                self._ext_report_error("load grading scheme", exc)
        self._reload_components()
        self._gr_refresh_gradebook_summary()

    # ---- Grade Management tie-in -------------------------------------
    def _gr_module_codes(self, course_code, conn):
        """Module codes that belong to *course_code* in Grade Management.

        Uses modules.course, the course↔module bridge map, and an identity
        match (module_code == course_code) so a course with no explicit module
        link still resolves when the codes coincide."""
        codes = set()
        for sql, params in (
                ("SELECT module_code FROM modules WHERE course = ?", (course_code,)),
                ("SELECT module_code FROM course_module_map WHERE course_code = ?", (course_code,)),
                ("SELECT module_code FROM modules WHERE module_code = ?", (course_code,))):
            try:
                for r in conn.execute(sql, params).fetchall():
                    if r[0]:
                        codes.add(r[0])
            except Exception:
                pass
        return codes

    def _gr_refresh_gradebook_summary(self):
        """Show, from Grade Management, the assessment count and live pass rate
        (against this course's pass mark) for the selected course."""
        if not hasattr(self, "_gr_gradebook_var"):
            return
        code = self._current_gr_course()
        if not code:
            self._gr_gradebook_var.set("")
            return
        try:
            try:
                pass_mark = float(self._gr_pass_var.get())
            except (ValueError, AttributeError):
                pass_mark = 50.0
            with self._ext_db() as conn:
                mods = self._gr_module_codes(code, conn)
                if not mods:
                    self._gr_gradebook_var.set(
                        "Grade Management: no linked module for this course.")
                    return
                ph = ",".join("?" * len(mods))
                cur = conn.cursor()
                assessments = cur.execute(
                    f"SELECT COUNT(*) FROM assessments WHERE module_code IN ({ph})",
                    list(mods)).fetchone()[0]
                total = cur.execute(
                    f"SELECT COUNT(*) FROM module_grades WHERE module_code IN ({ph}) "
                    f"AND final_score IS NOT NULL", list(mods)).fetchone()[0]
                passed = cur.execute(
                    f"SELECT COUNT(*) FROM module_grades WHERE module_code IN ({ph}) "
                    f"AND final_score >= ?", list(mods) + [pass_mark]).fetchone()[0]
            if total:
                rate = 100.0 * passed / total
                self._gr_gradebook_var.set(
                    f"Grade Management: {assessments} assessment(s) · "
                    f"{passed}/{total} passing ({rate:.0f}%) at pass mark {pass_mark:.0f}.")
            else:
                self._gr_gradebook_var.set(
                    f"Grade Management: {assessments} assessment(s) · no graded students yet.")
        except Exception:
            self._gr_gradebook_var.set("")

    def _push_components_to_gradebook(self):
        """Create gradebook assessments mirroring this course's weighted
        components, for each linked module. Idempotent on (module, name)."""
        if not self._ext_can_edit():
            return
        code = self._current_gr_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return
        try:
            with self._ext_db(write=True) as conn:
                cur = conn.cursor()
                comps = cur.execute(
                    "SELECT name, weight FROM course_assessment_components "
                    "WHERE course_code = ? ORDER BY id", (code,)).fetchall()
                if not comps:
                    messagebox.showinfo(_("common.info", default="Info"),
                                        "No assessment components to push. Add some first.")
                    return
                mods = self._gr_module_codes(code, conn)
                if not mods:
                    messagebox.showwarning(
                        _("common.warning", default="Warning"),
                        f"No Grade Management module is linked to course {code}.\n"
                        "Create the module (or a Course⇄Module link) first.")
                    return
                created = skipped = 0
                for module_code in mods:
                    existing = {r[0] for r in cur.execute(
                        "SELECT assessment_name FROM assessments WHERE module_code = ?",
                        (module_code,)).fetchall()}
                    for name, weight in comps:
                        if name in existing:
                            skipped += 1
                            continue
                        cur.execute(
                            "INSERT INTO assessments "
                            "(assessment_name, assessment_type, module_code, "
                            " max_points, weight, description) "
                            "VALUES (?, 'Component', ?, 100, ?, "
                            "'Synced from course grading scheme')",
                            (name, module_code, weight))
                        created += 1
        except Exception as exc:
            self._ext_report_error("sync components to gradebook", exc)
            return
        self._ext_audit("sync", "gradebook_assessments", course_code=code,
                        created=created)
        messagebox.showinfo(
            _("common.success", default="Done"),
            f"Synced to Grade Management:\n  • {created} assessment(s) created\n"
            f"  • {skipped} already present\n"
            f"across {len(mods)} module(s).")
        self._gr_refresh_gradebook_summary()

    def _save_scheme(self):
        if not self._ext_can_edit():
            return
        code = self._current_gr_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return
        try:
            pass_mark = float(self._gr_pass_var.get())
        except ValueError:
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 "Pass mark must be a number.")
            return
        if not 0 <= pass_mark <= 100:
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 "Pass mark must be between 0 and 100.")
            return
        try:
            with self._ext_db(write=True) as conn:
                # UPSERT keyed on the UNIQUE course_code.
                conn.execute(
                    "INSERT INTO course_grading_schemes "
                    "(course_code, scheme_type, pass_mark, updated_at) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(course_code) DO UPDATE SET "
                    "scheme_type=excluded.scheme_type, pass_mark=excluded.pass_mark, "
                    "updated_at=excluded.updated_at",
                    (code, self._gr_scheme_var.get(), pass_mark, self._ext_now()))
        except Exception as exc:
            self._ext_report_error("save grading scheme", exc)
            return
        self._ext_audit("update", "grading_scheme", course_code=code,
                        scheme=self._gr_scheme_var.get())
        self.update_status(_("course_management.status.scheme_saved",
                             default="Grading scheme saved for {c}.").format(c=code))
        messagebox.showinfo(_("common.success", default="Success"),
                            f"Grading scheme saved for {code}.")

    def _reload_components(self):
        if not hasattr(self, "_gr_tree"):
            return
        self._ext_clear_tree(self._gr_tree)
        code = self._current_gr_course()
        if not code:
            self._gr_total_var.set("")
            return
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, name, weight, notes FROM course_assessment_components "
                    "WHERE course_code=? ORDER BY id", (code,))
                rows = cur.fetchall()
            total = 0.0
            for rid, name, weight, notes in rows:
                weight = weight or 0.0
                total += weight
                self._gr_tree.insert("", tk.END,
                                     values=(rid, name, f"{weight:g}", notes))
            warn = "" if abs(total - 100.0) < 0.01 or not rows else "  ⚠ should total 100%"
            self._gr_total_var.set(f"Total weight: {total:g}%{warn}")
        except Exception as exc:
            self._ext_report_error("load assessment components", exc)

    def _component_fields(self, data=None):
        data = data or {}
        return [
            ("name", "Component name:", {"default": data.get("name", "")}),
            ("weight", "Weight (%):", {"default": data.get("weight", "0"), "width": 12}),
            ("notes", "Notes:", {"type": "text", "default": data.get("notes", ""),
                                 "height": 3}),
        ]

    def _parse_weight(self, values):
        try:
            weight = float(values.get("weight") or 0)
        except (TypeError, ValueError):
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 "Weight must be a number.")
            return None
        if not 0 <= weight <= 100:
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 "Weight must be between 0 and 100.")
            return None
        return weight

    def _add_component(self):
        if not self._ext_can_edit():
            return
        code = self._current_gr_course()
        if not code:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return

        def submit(values):
            name = (values.get("name") or "").strip()
            if not name:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Component name is required.")
                return False
            weight = self._parse_weight(values)
            if weight is None:
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "INSERT INTO course_assessment_components "
                        "(course_code, name, weight, notes, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (code, name, weight, values["notes"], self._ext_now()))
            except Exception as exc:
                self._ext_report_error("add component", exc)
                return False
            self._ext_audit("create", "assessment_component", course_code=code, name=name)
            self._reload_components()
            return True

        ExtFormDialog(self.root, self, f"Add Component for {code}",
                      self._component_fields(), submit,
                      submit_label="Add", geometry="480x300")

    def _selected_component(self):
        vals = self._ext_selected_values(self._gr_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a component first.")
            return None
        return vals

    def _edit_component(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_component()
        if not vals:
            return
        comp_id = vals[0]
        data = {"name": vals[1], "weight": vals[2], "notes": vals[3]}

        def submit(values):
            name = (values.get("name") or "").strip()
            if not name:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Component name is required.")
                return False
            weight = self._parse_weight(values)
            if weight is None:
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "UPDATE course_assessment_components SET name=?, weight=?, "
                        "notes=? WHERE id=?",
                        (name, weight, values["notes"], comp_id))
            except Exception as exc:
                self._ext_report_error("update component", exc)
                return False
            self._ext_audit("update", "assessment_component", component_id=comp_id)
            self._reload_components()
            return True

        ExtFormDialog(self.root, self, "Edit Component",
                      self._component_fields(data), submit,
                      submit_label="Save", geometry="480x300")

    def _delete_component(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_component()
        if not vals:
            return
        if not messagebox.askyesno(_("common.confirm", default="Confirm"),
                                   f"Delete component '{vals[1]}'?"):
            return
        try:
            with self._ext_db(write=True) as conn:
                conn.execute("DELETE FROM course_assessment_components WHERE id=?",
                             (vals[0],))
        except Exception as exc:
            self._ext_report_error("delete component", exc)
            return
        self._ext_audit("delete", "assessment_component", component_id=vals[0])
        self._reload_components()
