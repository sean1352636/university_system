"""Methods update_progress through create_whatif_scenario."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import degree_audit_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

# Imported after the namespace splat so it cannot be shadowed.
from .. import report_widgets as _report


class DegreeAuditGUI:
    def update_progress(self):
        """Refresh student's degree progress display"""
        try:
            student_id = self._student_id_from_label(self.progress_student_entry.get())
            if not student_id:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.course_management_gui.degree_audit_gui_parts.degreeauditgui_update_progress.dialogs.please_select_a_student', default="Please select a student"))
                return

            # Simply reload the progress to refresh display
            self.load_student_progress()

            log_activity('update', 'degree_progress', student_id, {})

            messagebox.showinfo(_("common.success"), _t('gui.academics.course_management_gui.degree_audit_gui_parts.degreeauditgui_update_progress.dialogs.progress_refreshed_successfully', default="Progress refreshed successfully"))

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to update progress: {e}")

    def initialize_progress(self):
        """Initialize/update student course assignment"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("degree_audit.dialogs.initialize_student_course"))
        dialog.geometry("400x250")

        ttk.Label(dialog, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        student_entry = ttk.Entry(dialog, width=30)
        student_entry.grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(dialog, text=_("degree_audit.labels.course")).grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        course_combo = ttk.Combobox(dialog, width=28, state='readonly')
        course_combo.grid(row=1, column=1, padx=10, pady=10)

        # Load courses (CS/DS)
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, code, name
                    FROM courses
                    WHERE code IN ('CS', 'DS')
                    ORDER BY code
                ''')
                courses = cursor.fetchall()
                course_combo['values'] = [f"{row[1]} - {row[2]}" for row in courses]
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load courses: {e}")

        ttk.Label(dialog, text=_("degree_audit.labels.enrollment_year")).grid(row=2, column=0, sticky=tk.W, padx=10, pady=10)
        year_entry = ttk.Entry(dialog, width=30)
        year_entry.insert(0, str(datetime.now().year))
        year_entry.grid(row=2, column=1, padx=10, pady=10)

        def save_init():
            try:
                student_id = student_entry.get().strip()
                course_selection = course_combo.get()
                enrollment_year = year_entry.get().strip()

                if not student_id or not course_selection:
                    messagebox.showerror(_("common.error"), _("degree_audit.messages.all_fields_required"))
                    return

                # Extract course code from selection
                course_code = course_selection.split('-')[0].strip()

                with get_connection() as conn:
                    cursor = conn.cursor()

                    # Check if student exists
                    cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                    if not cursor.fetchone():
                        messagebox.showerror(_("common.error"), _("degree_audit.messages.student_not_found_db").format(student_id=student_id))
                        return

                    # Update student's course
                    cursor.execute('''
                        UPDATE students
                        SET course = ?, enrollment_date = ?
                        WHERE student_id = ?
                    ''', (course_code, f"{enrollment_year}-09-01", student_id))

                    conn.commit()

                log_activity('create', 'degree_progress', student_id,
                           {'course': course_code, 'year': enrollment_year})

                messagebox.showinfo(_("common.success"),
                                  _("degree_audit.messages.course_assigned_success").format(course_code=course_code, student_id=student_id))
                dialog.destroy()
                self.progress_student_entry.delete(0, tk.END)
                self.progress_student_entry.insert(0, student_id)
                self.load_student_progress()

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to initialize: {e}")

        ttk.Button(dialog, text=_("degree_audit.buttons.initialize"),
                  command=save_init).grid(row=3, column=0, columnspan=2, pady=20)

    def check_prerequisites(self):
        """Check whether a student has met a module's prerequisites.

        Rendered as cards rather than a text dump, on the tab's scrolling
        surface so a module with many prerequisites is readable rather than
        clipped.
        """
        try:
            student_id = self._student_id_from_label(self.prereq_student_entry.get())
            module_label = self.prereq_module_entry.get().strip()
            # Combobox entries are "CIS0001 — Module Name"; pull the code.
            module_code = module_label.split(" — ", 1)[0].strip() if module_label else ""

            if not student_id or not module_code:
                messagebox.showwarning(_("common.warning"),
                                       _t('gui.academics.course_management_gui.degree_audit_gui_parts.degreeauditgui_update_progress.dialogs.please_select_both_a_student_and_a_module', default="Please select both a student and a module"))
                return

            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    'SELECT first_name, last_name FROM students WHERE student_id = ?',
                    (student_id,))
                student = cursor.fetchone()
                if not student:
                    messagebox.showerror(_("common.error"),
                                         f"Student {student_id} not found in database")
                    return
                student_name = f"{student[0] or ''} {student[1] or ''}".strip() or student_id

                cursor.execute('''
                    SELECT sm.module_code, sm.status, sm.grade, m.module_name, m.prerequisites
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ? AND sm.module_code = ?
                ''', (student_id, module_code))
                enrolment = cursor.fetchone()

                rows = []
                eligible = None
                if enrolment:
                    prerequisites = (enrolment[4] or "").strip()
                    if prerequisites and prerequisites.lower() != 'none':
                        for prereq in [p.strip() for p in prerequisites.split(',') if p.strip()]:
                            cursor.execute(
                                'SELECT grade, status FROM student_modules '
                                'WHERE student_id = ? AND module_code = ?',
                                (student_id, prereq))
                            got = cursor.fetchone()
                            cursor.execute(
                                'SELECT module_name FROM modules WHERE module_code = ?',
                                (prereq,))
                            name_row = cursor.fetchone()
                            name = (name_row[0] if name_row else "") or "—"
                            if not got:
                                rows.append((prereq, name, "Not taken", "—", False))
                            else:
                                grade = got[0] or "Not graded"
                                status = got[1] or "Unknown"
                                met = str(status).strip().lower() in (
                                    'completed', 'complete', 'passed', 'pass')
                                rows.append((prereq, name, status, grade, met))
                        eligible = all(r[4] for r in rows)
                    else:
                        eligible = True

            self._render_prereq_results(
                student_id=student_id, student_name=student_name,
                module_code=module_code, enrolment=enrolment,
                rows=rows, eligible=eligible)

            log_activity('check', 'prerequisite', module_code,
                         {'student_id': student_id})

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to check prerequisites: {e}")

    def _render_prereq_results(self, *, student_id, student_name, module_code,
                               enrolment, rows, eligible):
        """Draw the prerequisite outcome onto the tab's scrolling surface."""
        surface = self.prereq_results
        _report.clear(surface)

        if not enrolment:
            _report.banner(surface, f"Prerequisite check — {module_code}",
                           f"{student_name} ({student_id})", tone=_report.MUTED)
            _report.verdict(
                surface, False, "Not enrolled on this module",
                f"{student_name} has no enrolment record for {module_code}, so "
                f"there is nothing to check against.", neutral=True)
            return

        module_name = enrolment[3] or "Unknown module"
        status = enrolment[1] or "Unknown"
        grade = enrolment[2] or "Not graded"
        prerequisites = (enrolment[4] or "").strip() or "None"

        _report.banner(surface, f"{module_code} — {module_name}",
                       f"{student_name} ({student_id})")

        met_count = sum(1 for r in rows if r[4])
        _report.stat_strip(surface, [
            (len(rows), "Prerequisites"),
            (met_count, "Met", _report.OK if met_count == len(rows) else _report.WARN),
            (len(rows) - met_count, "Outstanding",
             _report.BAD if met_count < len(rows) else _report.OK),
        ])

        body = _report.card(surface, "This module")
        _report.kv_grid(body, [
            ("Module", module_code),
            ("Enrolment status", status),
            ("Current grade", grade),
            ("Declared prerequisites", prerequisites),
        ])

        if rows:
            _report.card(surface, "Prerequisite modules", accent="#9b59b6")
            _report.table(
                surface,
                ("Code", "Module", "Status", "Grade", "Met"),
                [(c, n, st, g, "Yes" if ok else "No") for c, n, st, g, ok in rows],
                widths={"Code": 100, "Module": 250, "Status": 110,
                        "Grade": 90, "Met": 60})

        if eligible:
            _report.verdict(
                surface, True, "Eligible",
                "All prerequisites have been met."
                if rows else "This module declares no prerequisites.")
        else:
            outstanding = [f"{c} ({n})" for c, n, _st, _g, ok in rows if not ok]
            _report.verdict(
                surface, False, "Not eligible",
                "Outstanding: " + ", ".join(outstanding))

    def add_prerequisite(self):
        """Add a new prerequisite relationship"""
        try:
            module_code = self.prereq_course_entry.get().strip()
            prerequisite = self.prereq_prereq_entry.get().strip()
            min_grade = self.prereq_grade_entry.get().strip()

            if not module_code or not prerequisite:
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.course_prereq_required"))
                return

            prereq_id = DegreeProgramManager.add_prerequisite(
                module_code=module_code,
                prerequisite_module_code=prerequisite,
                min_grade=min_grade if min_grade else None
            )

            log_activity('create', 'prerequisite', str(prereq_id),
                       {'course': module_code, 'prerequisite': prerequisite})

            messagebox.showinfo(_("common.success"),
                              _("degree_audit.messages.prerequisite_added").format(id=prereq_id))

            # Clear fields
            self.prereq_course_entry.delete(0, tk.END)
            self.prereq_prereq_entry.delete(0, tk.END)
            self.prereq_grade_entry.delete(0, tk.END)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("degree_audit.messages.failed_add_prerequisite").format(error=e))

    def _whatif_student_id(self):
        """Extract bare student_id from the formatted Combobox label."""
        return self._student_id_from_label(self.whatif_student_entry.get())

    def create_whatif_scenario(self):
        """Create and analyze what-if scenario for course switching"""
        try:
            student_id = self._whatif_student_id()
            scenario_name = self.whatif_name_entry.get().strip()
            course_selection = self.whatif_program_combo.get()
            notes = self.whatif_notes_text.get('1.0', tk.END).strip()

            if not student_id or not scenario_name or not course_selection:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.course_management_gui.degree_audit_gui_parts.degreeauditgui_update_progress.dialogs.all_fields_are_required', default="All fields are required"))
                return

            # Extract course code from selection (format: "1: CS - Computer Science")
            target_course_code = course_selection.split(':')[1].split('-')[0].strip()

            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT course FROM students WHERE student_id = ?', (student_id,))
                student_data = cursor.fetchone()
                if not student_data:
                    messagebox.showerror(_("common.error"), f"Student {student_id} not found")
                    return

                current_course = student_data[0]

                # Look up target course details and ensure a matching
                # ``degree_programs`` row exists. ``courses.id`` is a
                # string ('CS', 'DS', …), and the scenario table FKs
                # to ``degree_programs.program_id`` (an INTEGER), so
                # we mirror the course into degree_programs on first
                # use and use the resulting integer id (8.117.91 fix —
                # previously this stored ``target_program_id = 0``,
                # which violated the FK because degree_programs is
                # empty out of the box).
                cursor.execute(
                    "SELECT COALESCE(course_name, name), "
                    "       COALESCE(course_type, 'Bachelors'), "
                    "       COALESCE(department, ''), "
                    "       COALESCE(credits, credit_hours, 360) "
                    "FROM courses "
                    "WHERE UPPER(COALESCE(course_code, code)) = ?",
                    (target_course_code.upper(),))
                course_row = cursor.fetchone()
                if not course_row:
                    messagebox.showerror(_("common.error"),
                                         f"Course {target_course_code} not found")
                    return
                course_name, course_type, department, credits = course_row

                cursor.execute(
                    "INSERT OR IGNORE INTO degree_programs "
                    "(program_code, program_name, degree_type, department, "
                    " total_credits_required) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (target_course_code, course_name, course_type,
                     department, int(credits) if credits else 360))
                cursor.execute(
                    "SELECT program_id FROM degree_programs WHERE program_code = ?",
                    (target_course_code,))
                target_program_id = cursor.fetchone()[0]

                cursor.execute('''
                    INSERT INTO degree_what_if_scenarios
                    (student_id, scenario_name, target_program_id, notes, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (student_id, scenario_name, target_program_id,
                      f"Target Course: {target_course_code}\n{notes}",
                      datetime.now().isoformat()))

                scenario_id = cursor.lastrowid
                conn.commit()

            log_activity('create', 'whatif_scenario', str(scenario_id),
                       {'student_id': student_id, 'target_course': target_course_code})

            messagebox.showinfo(_("common.success"),
                              f"What-if scenario '{scenario_name}' created (ID: {scenario_id})\n"
                              f"Current Course: {current_course}\n"
                              f"Target Course: {target_course_code}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to create scenario: {e}")
