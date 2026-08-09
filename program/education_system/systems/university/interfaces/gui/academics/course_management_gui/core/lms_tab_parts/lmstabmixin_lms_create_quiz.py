"""Methods _lms_create_quiz through _lms_view_my_grades."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import lms_tab_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class LMSTabMixin:
    def _lms_create_quiz(self):
        cid = self._lms_get_selected_course_id('lms_quiz_course_combo')
        if not cid:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_course_first")); return

        dlg = tk.Toplevel(self.root); dlg.title(_("lms.dialogs.create_quiz"))
        dlg.geometry("500x550"); dlg.transient(self.root); dlg.grab_set()
        fields = {}

        for i, (lbl, key, default) in enumerate([
            ("Title:", 'title', ''), ("Duration (mins):", 'duration', '60'),
            ("Passing Score (%):", 'passing_score', '70'), ("Max Attempts:", 'max_attempts', '1'),
            ("Available From:", 'available_from', datetime.now().strftime('%Y-%m-%d')),
            ("Available Until:", 'available_until', ''),
        ]):
            ttk.Label(dlg, text=lbl).grid(row=i, column=0, sticky=tk.W, padx=5, pady=5)
            fields[key] = ttk.Entry(dlg, width=40)
            fields[key].insert(0, default)
            fields[key].grid(row=i, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.description', default="Description:")).grid(row=6, column=0, sticky=tk.NW, padx=5, pady=5)
        desc_text = tk.Text(dlg, width=40, height=5); desc_text.grid(row=6, column=1, padx=5, pady=5)

        def save():
            title = fields['title'].get().strip()
            if not title:
                messagebox.showerror(_("common.error"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.dialogs.title_is_required', default="Title is required")); return
            try:
                qid = LMSQuizManager.create_quiz(
                    lms_course_id=cid, title=title,
                    description=desc_text.get('1.0', tk.END).strip(),
                    duration_minutes=int(fields['duration'].get()),
                    passing_score=float(fields['passing_score'].get()),
                    max_attempts=int(fields['max_attempts'].get()),
                    available_from=fields['available_from'].get().strip(),
                    available_until=fields['available_until'].get().strip())
                log_activity('create', 'lms_quiz', str(qid), {'course_id': cid, 'title': title})
                messagebox.showinfo(_("common.success"), f"Quiz created (ID: {qid})")
                dlg.destroy(); self._lms_load_quizzes()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_create_quiz')}: {e}")

        ttk.Button(dlg, text=_("lms.buttons.create_quiz"), command=save).grid(row=7, column=0, columnspan=2, pady=20)

    def _lms_add_questions(self):
        sel = self.lms_quizzes_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_quiz_first")); return
        quiz_id = self.lms_quizzes_tree.item(sel[0])['values'][0]

        dlg = tk.Toplevel(self.root); dlg.title(f"Add Questions to Quiz {quiz_id}")
        dlg.geometry("600x550"); dlg.transient(self.root); dlg.grab_set()

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.question_text', default="Question Text:")).grid(row=0, column=0, sticky=tk.NW, padx=5, pady=5)
        question_text = tk.Text(dlg, width=50, height=5); question_text.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.type', default="Type:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        type_combo = ttk.Combobox(dlg, values=["Multiple Choice", "True/False", "Short Answer", "Essay"],
                                  width=48, state='readonly')
        type_combo.current(0); type_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.correct_answer', default="Correct Answer:")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        answer_entry = ttk.Entry(dlg, width=50); answer_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.points', default="Points:")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        points_entry = ttk.Entry(dlg, width=50); points_entry.insert(0, "1")
        points_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.options_json', default="Options (JSON):")).grid(row=4, column=0, sticky=tk.NW, padx=5, pady=5)
        options_text = tk.Text(dlg, width=50, height=5)
        options_text.insert('1.0', '["Option A", "Option B", "Option C", "Option D"]')
        options_text.grid(row=4, column=1, padx=5, pady=5)

        def save():
            text = question_text.get('1.0', tk.END).strip()
            if not text:
                messagebox.showerror(_("common.error"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.dialogs.question_text_is_required', default="Question text is required")); return
            try:
                qid = LMSQuizManager.add_question(
                    quiz_id=quiz_id, question_text=text, question_type=type_combo.get(),
                    correct_answer=answer_entry.get().strip(), points=int(points_entry.get()),
                    options=options_text.get('1.0', tk.END).strip())
                messagebox.showinfo(_("common.success"), f"Question added (ID: {qid})")
                question_text.delete('1.0', tk.END); answer_entry.delete(0, tk.END)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_add_question')}: {e}")

        ttk.Button(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.buttons.add_question', default="Add Question"), command=save).grid(row=5, column=0, columnspan=2, pady=20)

    def _lms_view_submissions(self):
        sel = self.lms_quizzes_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_quiz_first")); return
        quiz_id = self.lms_quizzes_tree.item(sel[0])['values'][0]
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT submission_id, student_id, attempt_number, score,
                           total_points, time_taken_minutes, submitted_at
                    FROM lms_quiz_submissions WHERE quiz_id = ?
                    ORDER BY submitted_at DESC
                ''', (quiz_id,))
                submissions = cursor.fetchall()

            dlg = tk.Toplevel(self.root); dlg.title(f"Quiz Submissions - Quiz {quiz_id}")
            dlg.geometry("900x600")
            lf = ttk.LabelFrame(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.submissions', default="Submissions"), padding=10)
            lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            cols = ("ID", "Student", "Attempt", "Score", "Total", "Time (min)", "Submitted")
            tree = ttk.Treeview(lf, columns=cols, show='headings', height=20)
            for c in cols:
                tree.heading(c, text=c); tree.column(c, width=120)
            for sub in submissions:
                tree.insert('', tk.END, values=sub)
            sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_submissions')}: {e}")

    def _create_lms_gradebook_subtab(self):
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.tabs.gradebook', default="Gradebook"))

        sel = ttk.Frame(tab); sel.pack(fill=tk.X, pady=5)
        ttk.Label(sel, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.course', default="Course:")).grid(row=0, column=0, padx=5, pady=5)
        self.lms_gradebook_course_combo = ttk.Combobox(sel, width=40, state='readonly')
        self.lms_gradebook_course_combo.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(sel, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.student_id', default="Student ID:")).grid(row=0, column=2, padx=5, pady=5)
        self.lms_gradebook_student_entry = ttk.Entry(sel, width=20)
        self.lms_gradebook_student_entry.grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(sel, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.buttons.load_grades', default="Load Grades"), command=self._lms_load_grades).grid(row=0, column=4, padx=5, pady=5)

        btn = ttk.Frame(tab); btn.pack(fill=tk.X, pady=5)
        ttk.Button(btn, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.buttons.add_grade', default="Add Grade"), command=self._lms_add_grade).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.buttons.calculate_course_grade', default="Calculate Course Grade"), command=self._lms_calculate_grade).pack(side=tk.LEFT, padx=5)

        lf = ttk.LabelFrame(tab, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.gradebook_entries', default="Gradebook Entries"), padding=10)
        lf.pack(fill=tk.BOTH, expand=True, pady=5)
        cols = ("ID", "Student", "Type", "Assignment", "Score", "Max", "Weight", "Graded By", "Date")
        self.lms_gradebook_tree = ttk.Treeview(lf, columns=cols, show='headings', height=15)
        for c in cols:
            self.lms_gradebook_tree.heading(c, text=c); self.lms_gradebook_tree.column(c, width=100)
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.lms_gradebook_tree.yview)
        self.lms_gradebook_tree.configure(yscrollcommand=sb.set)
        self.lms_gradebook_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _lms_load_grades(self):
        cid = self._lms_get_selected_course_id('lms_gradebook_course_combo')
        sid = self.lms_gradebook_student_entry.get().strip()
        if not cid or not sid:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.dialogs.select_course_and_enter_student_id', default="Select course and enter student ID")); return
        self.lms_gradebook_tree.delete(*self.lms_gradebook_tree.get_children())
        try:
            for g in LMSGradebookManager.get_student_grades(cid, sid):
                self.lms_gradebook_tree.insert('', tk.END, values=(
                    g.get('entry_id'), g.get('student_id'), g.get('assignment_type'),
                    g.get('assignment_id'), g.get('score'), g.get('max_score'),
                    g.get('weight'), g.get('graded_by'), g.get('graded_at')))
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_grades')}: {e}")

    def _lms_add_grade(self):
        cid = self._lms_get_selected_course_id('lms_gradebook_course_combo')
        if not cid:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_course_first")); return

        dlg = tk.Toplevel(self.root); dlg.title(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.windows.add_grade_entry', default="Add Grade Entry"))
        dlg.geometry("500x500"); dlg.transient(self.root); dlg.grab_set()
        fields = {}

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.student_id', default="Student ID:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['student_id'] = ttk.Entry(dlg, width=40); fields['student_id'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.assignment_type', default="Assignment Type:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['type'] = ttk.Combobox(dlg, values=["Quiz", "Assignment", "Exam", "Project", "Participation"],
                                      width=38, state='readonly')
        fields['type'].current(0); fields['type'].grid(row=1, column=1, padx=5, pady=5)

        for i, (lbl, key, default) in enumerate([
            ("Assignment ID:", 'assignment_id', ''), ("Score:", 'score', ''),
            ("Max Score:", 'max_score', ''), ("Weight:", 'weight', '1.0'),
        ], start=2):
            ttk.Label(dlg, text=lbl).grid(row=i, column=0, sticky=tk.W, padx=5, pady=5)
            fields[key] = ttk.Entry(dlg, width=40); fields[key].insert(0, default)
            fields[key].grid(row=i, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.feedback', default="Feedback:")).grid(row=6, column=0, sticky=tk.NW, padx=5, pady=5)
        feedback_text = tk.Text(dlg, width=40, height=5); feedback_text.grid(row=6, column=1, padx=5, pady=5)

        def save():
            sid = fields['student_id'].get().strip()
            if not sid:
                messagebox.showerror(_("common.error"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.dialogs.student_id_is_required', default="Student ID is required")); return
            try:
                eid = LMSGradebookManager.add_grade_entry(
                    lms_course_id=cid, student_id=sid,
                    assignment_type=fields['type'].get(),
                    assignment_id=int(fields['assignment_id'].get()),
                    score=float(fields['score'].get()), max_score=float(fields['max_score'].get()),
                    weight=float(fields['weight'].get()),
                    feedback=feedback_text.get('1.0', tk.END).strip(),
                    graded_by=self._lms_user_id)
                log_activity('create', 'lms_grade', str(eid), {'course_id': cid, 'student_id': sid})
                messagebox.showinfo(_("common.success"), f"Grade added (ID: {eid})")
                dlg.destroy(); self._lms_load_grades()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_add_grade')}: {e}")

        ttk.Button(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.buttons.add_grade', default="Add Grade"), command=save).grid(row=7, column=0, columnspan=2, pady=20)

    def _lms_calculate_grade(self):
        cid = self._lms_get_selected_course_id('lms_gradebook_course_combo')
        sid = self.lms_gradebook_student_entry.get().strip()
        if not cid or not sid:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.dialogs.select_course_and_enter_student_id', default="Select course and enter student ID")); return
        try:
            grade = LMSGradebookManager.calculate_course_grade(cid, sid)
            messagebox.showinfo(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.dialogs.course_grade', default="Course Grade"), f"Overall grade for {sid}:\n{grade:.2f}%")
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_calculate_grade')}: {e}")

    def _create_lms_my_courses_subtab(self):
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_("lms.tabs.my_courses"))

        ttk.Label(tab, text=_("lms.labels.my_enrolled_courses"),
                  font=('Arial', 12, 'bold')).pack(pady=10)

        btn = ttk.Frame(tab); btn.pack(fill=tk.X, pady=5)
        ttk.Button(btn, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.buttons.enrol_in_lms_course', default="Enrol in LMS Course"), command=self._lms_enrol).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.view_materials"), command=self._lms_view_materials).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.view_my_grades"), command=self._lms_view_my_grades).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("common.refresh"), command=self._lms_load_student_courses).pack(side=tk.LEFT, padx=5)

        lf = ttk.LabelFrame(tab, text=_("lms.frames.enrolled_courses"), padding=10)
        lf.pack(fill=tk.BOTH, expand=True, pady=5)
        cols = ("Course ID", "Module Code", "Instructor", "Progress %", "Last Accessed")
        self.lms_student_courses_tree = ttk.Treeview(lf, columns=cols, show='headings', height=15)
        for c in cols:
            self.lms_student_courses_tree.heading(c, text=c)
            self.lms_student_courses_tree.column(c, width=150)
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.lms_student_courses_tree.yview)
        self.lms_student_courses_tree.configure(yscrollcommand=sb.set)
        self.lms_student_courses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self._lms_load_student_courses()

    def _lms_enrol(self):
        dlg = tk.Toplevel(self.root); dlg.title(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.windows.enrol_in_lms_course', default="Enrol in LMS Course"))
        dlg.geometry("500x350"); dlg.transient(self.root); dlg.grab_set()
        frm = ttk.Frame(dlg, padding=10); frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.available_lms_courses', default="Available LMS Courses"), font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        course_map = {}
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT c.lms_course_id, c.module_code, c.instructor_id,
                           c.enrollment_limit,
                           (SELECT COUNT(*) FROM lms_student_enrollment e
                            WHERE e.lms_course_id = c.lms_course_id AND e.is_active = 1) as enrolled
                    FROM lms_courses c
                    WHERE c.is_published = 1
                      AND c.lms_course_id NOT IN (
                          SELECT lms_course_id FROM lms_student_enrollment
                          WHERE student_id = ? AND is_active = 1)
                    ORDER BY c.module_code
                ''', (self._lms_user_id,))
                for row in cursor.fetchall():
                    cid, code, instructor, limit_val, enrolled = row
                    spots = f"{enrolled}/{limit_val}" if limit_val else f"{enrolled}/unlimited"
                    label = f"{code} (Instructor: {instructor}, Enrolled: {spots})"
                    course_map[label] = cid
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load available courses: {e}")
            dlg.destroy(); return

        if not course_map:
            ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.no_available_courses_to_enrol_in', default="No available courses to enrol in.")).pack(pady=20)
            ttk.Button(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.buttons.close', default="Close"), command=dlg.destroy).pack(pady=10); return

        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.select_a_course', default="Select a course:")).pack(anchor=tk.W, pady=(10, 5))
        course_combo = ttk.Combobox(frm, values=list(course_map.keys()), width=60, state='readonly')
        course_combo.pack(fill=tk.X, pady=(0, 10))
        if course_map:
            course_combo.current(0)

        def do_enrol():
            selected = course_combo.get()
            if selected not in course_map:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.dialogs.please_select_a_course', default="Please select a course.")); return
            lms_cid = course_map[selected]
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT enrollment_limit FROM lms_courses WHERE lms_course_id = ?", (lms_cid,))
                    limit_row = cursor.fetchone()
                    if limit_row and limit_row[0] and limit_row[0] > 0:
                        cursor.execute("SELECT COUNT(*) FROM lms_student_enrollment WHERE lms_course_id = ? AND is_active = 1", (lms_cid,))
                        if cursor.fetchone()[0] >= limit_row[0]:
                            messagebox.showwarning(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.dialogs.course_full', default="Course Full"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.dialogs.this_course_has_reached_its_enrollment_limit', default="This course has reached its enrollment limit.")); return
                    cursor.execute('INSERT INTO lms_student_enrollment (lms_course_id, student_id) VALUES (?, ?)',
                                   (lms_cid, self._lms_user_id))
                    conn.commit()
                messagebox.showinfo(_("common.success"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.dialogs.successfully_enrolled', default="Successfully enrolled!"))
                dlg.destroy(); self._lms_load_student_courses()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to enrol: {e}")

        btn_frame = ttk.Frame(frm); btn_frame.pack(fill=tk.X, pady=20)
        ttk.Button(btn_frame, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.buttons.enrol', default="Enrol"), command=do_enrol).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.buttons.cancel', default="Cancel"), command=dlg.destroy).pack(side=tk.RIGHT, padx=5)

    def _lms_load_student_courses(self):
        if not hasattr(self, 'lms_student_courses_tree'):
            return
        self.lms_student_courses_tree.delete(*self.lms_student_courses_tree.get_children())
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT e.lms_course_id, c.module_code, c.instructor_id,
                           e.progress_percentage, e.last_accessed
                    FROM lms_student_enrollment e
                    JOIN lms_courses c ON e.lms_course_id = c.lms_course_id
                    WHERE e.student_id = ? AND e.is_active = 1 AND c.is_published = 1
                    ORDER BY e.enrollment_date DESC
                ''', (self._lms_user_id,))
                for row in cursor.fetchall():
                    self.lms_student_courses_tree.insert('', tk.END, values=tuple(row))
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_enrolled_courses')}: {e}")

    def _lms_view_materials(self):
        sel = self.lms_student_courses_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_course_first")); return
        cid = self.lms_student_courses_tree.item(sel[0])['values'][0]
        try:
            content_list = LMSContentManager.get_course_content(cid)
            dlg = tk.Toplevel(self.root); dlg.title(f"Course Materials - Course {cid}"); dlg.geometry("900x600")
            lf = ttk.LabelFrame(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.course_materials', default="Course Materials"), padding=10)
            lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            cols = ("ID", "Type", "Title", "Description", "Release Date")
            tree = ttk.Treeview(lf, columns=cols, show='headings', height=20)
            for c in cols:
                tree.heading(c, text=c)
                tree.column(c, width=250 if c in ("Title", "Description") else 100)
            for ct in content_list:
                tree.insert('', tk.END, values=(
                    ct.get('content_id'), ct.get('content_type'), ct.get('title'),
                    ct.get('description', '')[:100], ct.get('release_date', '')))
            sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_materials')}: {e}")

    def _lms_view_my_grades(self):
        sel = self.lms_student_courses_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_course_first")); return
        cid = self.lms_student_courses_tree.item(sel[0])['values'][0]
        try:
            grades = LMSGradebookManager.get_student_grades(cid, self._lms_user_id)
            overall = LMSGradebookManager.calculate_course_grade(cid, self._lms_user_id)
            dlg = tk.Toplevel(self.root); dlg.title(f"My Grades - Course {cid}"); dlg.geometry("900x600")

            overall_frame = ttk.LabelFrame(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.overall_grade', default="Overall Grade"), padding=10)
            overall_frame.pack(fill=tk.X, padx=10, pady=10)
            ttk.Label(overall_frame, text=f"Course Grade: {overall:.2f}%",
                      font=('Arial', 14, 'bold')).pack(pady=5)

            lf = ttk.LabelFrame(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_create_quiz.labels.individual_grades', default="Individual Grades"), padding=10)
            lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            cols = ("Type", "Assignment", "Score", "Max", "Weight", "Graded By", "Date")
            tree = ttk.Treeview(lf, columns=cols, show='headings', height=15)
            for c in cols:
                tree.heading(c, text=c); tree.column(c, width=120)
            for g in grades:
                tree.insert('', tk.END, values=(
                    g.get('assignment_type'), g.get('assignment_id'),
                    g.get('score'), g.get('max_score'), g.get('weight'),
                    g.get('graded_by'), g.get('graded_at')))
            sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_grades')}: {e}")
