"""Methods create_advising_tab through load_requirements."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import degree_audit_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class DegreeAuditGUI:
    def create_advising_tab(self):
        """Create Academic Advising Appointments tab.

        8.117.93: wrapped in a scrollable Canvas so the Schedule
        Appointment button at the bottom of the schedule form (and
        the appointments list below it) stay reachable on smaller
        windows. Previously the form's natural height plus the
        appointments tree exceeded the tab's available space and the
        Schedule button was pushed off-screen with no way to scroll.
        """
        tab_outer = ttk.Frame(self.notebook)
        self.notebook.add(tab_outer, text=_("degree_audit.tabs.advising_appointments"))

        canvas = tk.Canvas(tab_outer, highlightthickness=0)
        vbar = ttk.Scrollbar(tab_outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)

        tab = ttk.Frame(canvas, padding="10")
        canvas_window = canvas.create_window((0, 0), window=tab, anchor="nw")
        # Keep the inner frame's width matched to the canvas so wide
        # widgets (notes Text, topic Entry) don't trigger horizontal
        # scrolling.
        tab.bind("<Configure>",
                 lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(canvas_window, width=e.width))
        # Mouse-wheel scrolling — bound only while the cursor is over
        # this tab so it doesn't fight the outer notebook.
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")
        canvas.bind("<Enter>",
                    lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>",
                    lambda _e: canvas.unbind_all("<MouseWheel>"))

        ttk.Label(tab, text=_("degree_audit.labels.academic_advising_appointments"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Schedule appointment frame
        schedule_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.schedule_appointment"), padding="10")
        schedule_frame.pack(fill=tk.X, pady=5)

        fields = {}

        ttk.Label(schedule_frame, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['student'] = ttk.Entry(schedule_frame, width=20)
        fields['student'].grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(schedule_frame, text=_("degree_audit.buttons.lookup"), command=lambda: self._lookup_student_for_appointment(fields['student'])).grid(row=0, column=2, padx=2, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.advisor_id")).grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        fields['advisor'] = ttk.Entry(schedule_frame, width=20)
        fields['advisor'].grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(schedule_frame, text=_("degree_audit.buttons.lookup"), command=lambda: self._lookup_advisor_for_appointment(fields['advisor'])).grid(row=0, column=5, padx=2, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.date_format")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['date'] = ttk.Entry(schedule_frame, width=25)
        fields['date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        fields['date'].grid(row=1, column=1, columnspan=2, padx=5, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.time_format")).grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        fields['time'] = ttk.Entry(schedule_frame, width=25)
        fields['time'].insert(0, "10:00")
        fields['time'].grid(row=1, column=4, columnspan=2, padx=5, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.type")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        fields['type'] = ttk.Combobox(schedule_frame, values=[
            _("degree_audit.appointment_types.academic_planning"),
            _("degree_audit.appointment_types.course_selection"),
            _("degree_audit.appointment_types.degree_progress"),
            _("degree_audit.appointment_types.career_advising"),
            _("degree_audit.appointment_types.general"),
            _("degree_audit.appointment_types.other")
        ], width=23, state='readonly')
        fields['type'].current(0)
        fields['type'].grid(row=2, column=1, columnspan=2, padx=5, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.duration_min")).grid(row=2, column=3, sticky=tk.W, padx=5, pady=5)
        fields['duration'] = ttk.Entry(schedule_frame, width=25)
        fields['duration'].insert(0, "30")
        fields['duration'].grid(row=2, column=4, columnspan=2, padx=5, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.topic")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['topic'] = ttk.Entry(schedule_frame, width=58)
        fields['topic'].grid(row=3, column=1, columnspan=5, padx=5, pady=5)

        ttk.Label(schedule_frame, text=_("degree_audit.labels.notes")).grid(row=4, column=0, sticky=tk.NW, padx=5, pady=5)
        fields['notes'] = tk.Text(schedule_frame, width=58, height=4)
        fields['notes'].grid(row=4, column=1, columnspan=5, padx=5, pady=5)

        self.appointment_fields = fields

        ttk.Button(schedule_frame, text=_("degree_audit.buttons.schedule_appointment"),
                  command=self.schedule_appointment).grid(row=5, column=0, columnspan=6, pady=10)

        # Appointments list
        list_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.scheduled_appointments"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Load appointments button
        ttk.Button(list_frame, text=_("degree_audit.buttons.load_my_appointments"),
                  command=self.load_appointments).pack(anchor=tk.W, pady=5)

        columns = ('ID', 'Student', 'Advisor', 'Date', 'Time', 'Type', 'Topic', 'Status')
        column_translations = {
            'ID': _("degree_audit.columns.id"),
            'Student': _("degree_audit.columns.student"),
            'Advisor': _("degree_audit.columns.advisor"),
            'Date': _("degree_audit.columns.date"),
            'Time': _("degree_audit.columns.time"),
            'Type': _("degree_audit.columns.type"),
            'Topic': _("degree_audit.columns.topic"),
            'Status': _("degree_audit.columns.status")
        }
        self.appointments_tree = ttk.Treeview(list_frame, columns=columns,
                                             show='headings', height=8)

        for col in columns:
            self.appointments_tree.heading(col, text=column_translations[col])
            width = 150 if col == 'Topic' else 100
            self.appointments_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.appointments_tree.yview)
        self.appointments_tree.configure(yscrollcommand=scrollbar.set)

        self.appointments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_graduation_tab(self):
        """Create Graduation Audit tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("degree_audit.tabs.graduation_audit"))

        ttk.Label(tab, text=_("degree_audit.labels.graduation_readiness_audit"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Audit controls frame
        control_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.run_graduation_audit"), padding="10")
        control_frame.pack(fill=tk.X, pady=5)

        ttk.Label(control_frame, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.grad_student_entry = ttk.Combobox(control_frame, width=42, state='readonly')
        self.grad_student_entry.grid(row=0, column=1, padx=5, pady=5)
        self._populate_student_combo(self.grad_student_entry)

        ttk.Label(control_frame, text=_("degree_audit.labels.program")).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.grad_program_combo = ttk.Combobox(control_frame, width=40, state='readonly')
        self.grad_program_combo.grid(row=0, column=3, padx=5, pady=5)

        # 8.117.92: autofill the program combo with the student's
        # current course on selection.
        def _autofill_grad_course(_e=None):
            sid = self._student_id_from_label(self.grad_student_entry.get())
            current = self._student_course(sid)
            if not current:
                return
            for opt in self.grad_program_combo['values']:
                if f": {current} -" in opt or opt.startswith(f"{current} -") \
                        or opt.split(":", 1)[-1].strip().startswith(current):
                    self.grad_program_combo.set(opt)
                    return
        self.grad_student_entry.bind('<<ComboboxSelected>>', _autofill_grad_course)

        ttk.Button(control_frame, text=_("degree_audit.buttons.run_audit"),
                  command=self.run_graduation_audit).grid(row=0, column=4, padx=10, pady=5)

        # Checklist frame
        checklist_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.graduation_checklist"), padding="10")
        checklist_frame.pack(fill=tk.X, pady=5)

        self.checklist_vars = {}
        checklist_items = [
            ('all_requirements', _("degree_audit.checklist.all_requirements_met")),
            ('gpa_requirement', _("degree_audit.checklist.gpa_requirement_met")),
            ('credit_requirement', _("degree_audit.checklist.credit_requirement_met")),
            ('residency', _("degree_audit.checklist.residency_requirement_met")),
            ('financial', _("degree_audit.checklist.financial_clearance"))
        ]

        for i, (key, label) in enumerate(checklist_items):
            var = tk.BooleanVar()
            self.checklist_vars[key] = var
            ttk.Checkbutton(checklist_frame, text=label, variable=var,
                           state='disabled').grid(row=i//2, column=(i%2)*2,
                                                 columnspan=2, sticky=tk.W, padx=20, pady=5)

        # Audit results display
        results_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.audit_results"), padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.grad_results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                           width=80, height=12)
        self.grad_results_text.pack(fill=tk.BOTH, expand=True)

        # Approval frame
        approval_frame = ttk.Frame(tab)
        approval_frame.pack(fill=tk.X, pady=10)

        ttk.Label(approval_frame, text=_("degree_audit.labels.graduation_date")).pack(side=tk.LEFT, padx=5)
        self.grad_date_entry = ttk.Entry(approval_frame, width=20)
        self.grad_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.grad_date_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(approval_frame, text=_("degree_audit.buttons.approve_graduation"),
                  command=self.approve_graduation).pack(side=tk.LEFT, padx=20)

        # --- Link to the Graduation Ceremony manager --------------------
        # Enabled only once an audit shows the student is eligible, so an
        # ineligible student can't be pushed into a ceremony from here.
        self._grad_eligible = False
        self._grad_student_id = None
        self._grad_add_ceremony_btn = ttk.Button(
            approval_frame,
            text=_("degree_audit.buttons.add_to_ceremony", default="Add to Graduation Ceremony"),
            command=self._add_to_ceremony, state='disabled')
        self._grad_add_ceremony_btn.pack(side=tk.LEFT, padx=6)
        ttk.Button(
            approval_frame,
            text=_("degree_audit.buttons.open_ceremony", default="Open Ceremony Manager"),
            command=self._open_ceremony_gui).pack(side=tk.LEFT, padx=6)

    def load_courses(self):
        """Load all courses (CS/DS) into combo boxes"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, code, name
                    FROM courses
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
                      AND code IN ('CS', 'DS')
                    ORDER BY name
                ''')

                courses = cursor.fetchall()
                if not courses:
                    print("No CS/DS courses found in database")
                    return

                course_list = [f"{row[0]}: {row[1]} - {row[2]}" for row in courses]

                # Update all combo boxes that need courses
                self.whatif_program_combo['values'] = course_list
                self.grad_program_combo['values'] = course_list

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load courses: {e}")

    def load_student_progress(self):
        """Load and display student degree progress from actual database tables"""
        try:
            # Combobox carries the formatted label "S12345 — Name (Course)";
            # strip back to just the bare ID.
            student_id = self._student_id_from_label(self.progress_student_entry.get())
            if not student_id:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.course_management_gui.degree_audit_gui_parts.degreeauditgui_create_advising_tab.dialogs.please_select_a_student', default="Please select a student"))
                return

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get student information from students table
                cursor.execute('''
                    SELECT student_id, first_name, last_name, course, registration_datetime, enrollment_date
                    FROM students
                    WHERE student_id = ?
                ''', (student_id,))

                student = cursor.fetchone()
                if not student:
                    messagebox.showerror(_("common.error"), f"Student {student_id} not found in database")
                    return

                course_code = student[3]  # course column (CS or DS)
                enrollment_date = student[5] or student[4]  # enrollment_date or registration_datetime

                if not course_code:
                    messagebox.showerror(_("common.error"), f"Student {student_id} has no course assigned")
                    return

                # Get course information
                cursor.execute('''
                    SELECT id, name, code
                    FROM courses
                    WHERE code = ? OR course_code = ?
                ''', (course_code, course_code))

                course = cursor.fetchone()
                course_name = course[1] if course else course_code

                # Calculate total credits from student_modules
                cursor.execute('''
                    SELECT
                        COUNT(DISTINCT sm.module_code) as module_count,
                        SUM(COALESCE(m.credits, 0)) as total_credits,
                        AVG(
                            CASE
                                WHEN sm.grade = 'A' THEN 4.0
                                WHEN sm.grade = 'B' THEN 3.0
                                WHEN sm.grade = 'C' THEN 2.0
                                WHEN sm.grade = 'D' THEN 1.0
                                WHEN sm.grade = 'F' THEN 0.0
                                ELSE NULL
                            END
                        ) as gpa
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                ''', (student_id,))

                progress_data = cursor.fetchone()
                total_credits = progress_data[1] or 0
                gpa = progress_data[2] or 0.0

                # Calculate enrollment year
                enrollment_year = _("common.not_available")
                if enrollment_date:
                    try:
                        enroll_dt = datetime.strptime(enrollment_date.split()[0], '%Y-%m-%d')
                        enrollment_year = str(enroll_dt.year)
                    except (ValueError, TypeError):
                        pass

                # Standard degree is typically 120 credits
                credits_required = 120
                completion_pct = (total_credits / credits_required * 100) if credits_required > 0 else 0

                # Calculate expected graduation (4 years from enrollment)
                expected_grad = _("common.not_available")
                if enrollment_date:
                    try:
                        enroll_dt = datetime.strptime(enrollment_date.split()[0], '%Y-%m-%d')
                        grad_year = enroll_dt.year + 4
                        expected_grad = f"{grad_year}"
                    except (ValueError, TypeError):
                        pass

                # Update labels
                self.progress_labels['Program'].config(text=f"{course_code} - {course_name}")
                self.progress_labels['Credits Earned'].config(text=str(int(total_credits)))
                self.progress_labels['Credits Required'].config(text=str(credits_required))
                self.progress_labels['Current GPA'].config(text=f"{gpa:.2f}")
                self.progress_labels['Completion %'].config(text=f"{completion_pct:.1f}%")
                self.progress_labels['Enrollment Year'].config(text=enrollment_year)
                self.progress_labels['Expected Graduation'].config(text=expected_grad)

                # Load module requirements
                self.load_requirements(student_id, course_code)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load progress: {e}")

    def load_requirements(self, student_id, course_code):
        """Load student modules from student_modules table"""
        try:
            self.progress_tree.delete(*self.progress_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get modules enrolled by student from student_modules
                cursor.execute('''
                    SELECT
                        COALESCE(m.module_type, 'Standard') as module_type,
                        COALESCE(sm.module_code, 'N/A') as module_code,
                        COALESCE(m.module_name, 'Unknown Module') as module_name,
                        COALESCE(m.credits, 0) as credits,
                        COALESCE(sm.status, 'Enrolled') as status,
                        COALESCE(sm.grade, 'Not Graded') as grade
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                    ORDER BY m.module_type, sm.module_code
                ''', (student_id,))

                modules = cursor.fetchall()

                if not modules:
                    self.progress_tree.insert('', tk.END, values=(
                        'N/A',
                        'No modules found',
                        0,
                        'No enrollment data',
                        'N/A'
                    ))
                else:
                    for module in modules:
                        # module: (module_type, module_code, module_name, credits, status, grade)
                        self.progress_tree.insert('', tk.END, values=(
                            module[0],  # module_type (Requirement Type)
                            f"{module[1]} - {module[2]}",  # module_code - module_name (Name)
                            module[3],  # credits (Credits Required)
                            module[4],  # status (Status)
                            module[5]   # grade (Grade Required)
                        ))

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load modules: {e}")
