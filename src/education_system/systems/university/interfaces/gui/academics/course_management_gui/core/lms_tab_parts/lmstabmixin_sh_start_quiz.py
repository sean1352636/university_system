"""Methods _sh_start_quiz through _sh_view_my_progress."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import lms_tab_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class LMSTabMixin:
    def _sh_start_quiz(self):
        if not self._sh_quiz_svc:
            return
        for w in self._sh_quiz_area.winfo_children():
            w.destroy()
        self._sh_quiz_answer_vars.clear()
        val = self._sh_stu_quiz_var.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.dialogs.lms', default="LMS"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.dialogs.please_enter_a_quiz_id', default="Please enter a Quiz ID.")); return
        qid = int(val)

        questions = self._sh_quiz_svc.list_questions(qid)
        if not questions:
            ttk.Label(self._sh_quiz_area, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.labels.no_questions_found_for_this_quiz', default="No questions found for this quiz.")).pack(); return

        canvas = tk.Canvas(self._sh_quiz_area, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self._sh_quiz_area, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")

        for i, q in enumerate(questions, 1):
            q_frame = ttk.Frame(scroll_frame, padding=8); q_frame.pack(fill="x", padx=10)
            ttk.Label(q_frame, text=f"Q{i}. {q['question_text']}",
                      font=("Helvetica", 10, "bold"), wraplength=500).pack(anchor="w")
            ttk.Label(q_frame, text=f"({q['marks']} marks)", font=("Helvetica", 8)).pack(anchor="w")
            ans_var = tk.StringVar()
            self._sh_quiz_answer_vars[q["id"]] = ans_var
            if q["question_type"] == "multiple_choice" and (q.get("options") or q.get("options_json")):
                try:
                    options = q.get("options") or json.loads(q.get("options_json", "[]"))
                except (json.JSONDecodeError, TypeError):
                    options = []
                for opt in options:
                    ttk.Radiobutton(q_frame, text=opt, variable=ans_var, value=opt).pack(anchor="w", padx=15)
            elif q["question_type"] == "true_false":
                ttk.Radiobutton(q_frame, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.buttons.true', default="True"), variable=ans_var, value="true").pack(anchor="w", padx=15)
                ttk.Radiobutton(q_frame, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.buttons.false', default="False"), variable=ans_var, value="false").pack(anchor="w", padx=15)
            else:
                ttk.Entry(q_frame, textvariable=ans_var, width=40).pack(anchor="w", padx=15)
            ttk.Separator(q_frame, orient="horizontal").pack(fill="x", pady=5)

        ttk.Button(scroll_frame, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.buttons.submit_quiz', default="Submit Quiz"),
                   command=lambda qid=qid: self._sh_submit_quiz(qid)).pack(pady=15)

    def _sh_submit_quiz(self, quiz_id):
        if not self._sh_quiz_svc:
            return
        answers = {str(qid): var.get() for qid, var in self._sh_quiz_answer_vars.items()}
        try:
            result = self._sh_quiz_svc.submit_quiz(quiz_id, self._lms_user_id or "", answers)
            status = "PASSED" if result["passed"] else "FAILED"
            msg = f"Score: {result['score']}\nResult: {status}"
            if result["passed"]:
                messagebox.showinfo(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.dialogs.quiz_result', default="Quiz Result"), msg)
            else:
                messagebox.showwarning(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.dialogs.quiz_result', default="Quiz Result"), msg)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.dialogs.lms', default="LMS"), str(e))

    def _create_lms_student_progress_subtab(self):
        if not self._sh_progress_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.tabs.my_progress', default="My Progress"))

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.labels.course_id_code', default="Course ID / Code:")).pack(side=tk.LEFT, padx=5)
        self._sh_my_prog_course_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_my_prog_course_var, width=14).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.buttons.view_progress', default="View Progress"), command=self._sh_view_my_progress).pack(side=tk.LEFT, padx=5)

        self._sh_my_prog_frame = ttk.Frame(tab)
        self._sh_my_prog_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _sh_view_my_progress(self):
        if not self._sh_progress_svc:
            return
        for w in self._sh_my_prog_frame.winfo_children():
            w.destroy()
        cid = self._sh_resolve_course(self._sh_my_prog_course_var.get())
        if cid is None:
            return
        sid = self._lms_user_id or ""
        prog = self._sh_progress_svc.get_student_progress(sid, cid)
        ttk.Label(self._sh_my_prog_frame, text=f"Completed {prog['completed']} of {prog['total']} lessons",
                  font=("Helvetica", 13, "bold")).pack(anchor="w")
        ttk.Progressbar(self._sh_my_prog_frame, length=400, mode="determinate",
                        maximum=100, value=prog["percentage"]).pack(fill="x", pady=10)
        ttk.Label(self._sh_my_prog_frame, text=f"{prog['percentage']}% complete",
                  font=("Helvetica", 11)).pack(anchor="w")
        completed = self._sh_progress_svc.list_completed_lessons(sid, cid)
        if completed:
            ttk.Label(self._sh_my_prog_frame, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_sh_start_quiz.labels.completed_lessons', default="Completed Lessons:"),
                      font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(15, 5))
            for c in completed:
                ttk.Label(self._sh_my_prog_frame,
                          text=f"  - {c['lesson_title']} ({c['module_title']})  {c.get('completed_at', '')}",
                          font=("Helvetica", 9)).pack(anchor="w")
