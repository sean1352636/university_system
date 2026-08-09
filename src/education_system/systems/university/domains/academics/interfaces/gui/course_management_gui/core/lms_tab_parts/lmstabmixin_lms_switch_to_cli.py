"""Methods _lms_switch_to_cli through _lms_add_content."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import lms_tab_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class LMSTabMixin:
    def _lms_switch_to_cli(self):
        """Switch from LMS GUI to LMS CLI."""
        try:
            from education_system.systems.university.domains.academics.domain.services.lms.lms_core import display_lms_menu
            import threading

            self.root.withdraw()

            def run_cli():
                try:
                    display_lms_menu(self.auth)
                except Exception as e:
                    import logging
                    logging.error(f"LMS CLI error: {e}")
                finally:
                    self.root.after(0, self.root.deiconify)

            cli_thread = threading.Thread(target=run_cli, daemon=True)
            cli_thread.start()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.dialogs.error', default="Error"), f"Failed to launch LMS CLI: {e}")

    def create_lms_tab(self):
        """Create the LMS tab with its own sub-notebook."""
        if not LMS_AVAILABLE:
            return

        try:
            initialize_lms_database()
        except Exception:
            pass

        # Ensure shared LMS tables exist too
        if SHARED_LMS_AVAILABLE:
            try:
                import sqlite3 as _sql
                conn = _sql.connect(str(DEFAULT_DB_PATH))
                conn.row_factory = _sql.Row
                create_lms_tables(conn)
                conn.close()
            except Exception:
                pass

        # Resolve user info once
        self._lms_user_role = self.get_user_role() or 'student'
        self._lms_user_id = None
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            self._lms_user_id = self.auth.current_user.get('username', 'Unknown')

        # Shared services
        db_path = str(DEFAULT_DB_PATH)
        if SHARED_LMS_AVAILABLE:
            self._sh_content_svc = CourseContentService(db_path)
            self._sh_progress_svc = LearningProgressService(db_path)
            self._sh_quiz_svc = QuizService(db_path)
            self._sh_resource_svc = ResourceLibraryService(db_path)
        else:
            self._sh_content_svc = None
            self._sh_progress_svc = None
            self._sh_quiz_svc = None
            self._sh_resource_svc = None

        lms_frame = ttk.Frame(self.notebook)
        self.notebook.add(lms_frame, text=_("lms.title"))

        # LMS toolbar
        lms_toolbar = ttk.Frame(lms_frame)
        lms_toolbar.pack(fill=tk.X, padx=5, pady=(5, 0))
        ttk.Button(lms_toolbar, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.buttons.switch_to_cli', default="Switch to CLI"), command=self._lms_switch_to_cli).pack(side=tk.LEFT, padx=5)

        self.lms_notebook = ttk.Notebook(lms_frame)
        self.lms_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        if self._lms_user_role in ('admin', 'instructor', 'staff'):
            self._create_lms_courses_subtab()
            self._create_lms_content_subtab()
            self._create_lms_discussions_subtab()
            self._create_lms_quizzes_subtab()
            self._create_lms_gradebook_subtab()
            # Shared LMS tabs
            self._create_lms_modules_subtab()
            self._create_lms_create_lesson_subtab()
            self._create_lms_resources_subtab()
            self._create_lms_staff_progress_subtab()

        if self._lms_user_role in ('student', 'admin'):
            self._create_lms_my_courses_subtab()
            # Shared student tabs
            self._create_lms_current_lesson_subtab()
            self._create_lms_take_quiz_subtab()
            self._create_lms_student_progress_subtab()

        # Resources tab visible to students too
        if self._lms_user_role == 'student':
            self._create_lms_resources_subtab()

        self._lms_load_courses()

    def _create_lms_courses_subtab(self):
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_("lms.tabs.courses"))

        btn = ttk.Frame(tab); btn.pack(fill=tk.X, pady=5)
        ttk.Button(btn, text=_("lms.buttons.create_course"), command=self._lms_create_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.publish_course"), command=self._lms_publish_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.view_details"), command=self._lms_view_course_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("common.refresh"), command=self._lms_load_courses).pack(side=tk.LEFT, padx=5)

        lf = ttk.LabelFrame(tab, text=_("lms.frames.lms_courses"), padding=10)
        lf.pack(fill=tk.BOTH, expand=True, pady=5)

        cols = ("ID", "Module Code", "Instructor", "Start", "End", "Limit", "Published")
        self.lms_courses_tree = ttk.Treeview(lf, columns=cols, show='headings', height=15)
        for c in cols:
            self.lms_courses_tree.heading(c, text=c)
            self.lms_courses_tree.column(c, width=150 if c == "Module Code" else 100)
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.lms_courses_tree.yview)
        self.lms_courses_tree.configure(yscrollcommand=sb.set)
        self.lms_courses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _lms_load_courses(self, *a):
        if not hasattr(self, 'lms_courses_tree'):
            return
        self.lms_courses_tree.delete(*self.lms_courses_tree.get_children())
        try:
            if self._lms_user_role == 'instructor':
                courses = LMSCourseManager.get_instructor_courses(self._lms_user_id)
            else:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT lms_course_id, module_code, instructor_id,
                               start_date, end_date, enrollment_limit, is_published
                        FROM lms_courses ORDER BY created_at DESC
                    ''')
                    courses = [dict(row) for row in cursor.fetchall()]

            course_list = []
            for course in courses:
                is_pub = "Yes" if course.get('is_published', 0) == 1 else "No"
                self.lms_courses_tree.insert('', tk.END, values=(
                    course.get('lms_course_id'), course.get('module_code'),
                    course.get('instructor_id'), course.get('start_date', ''),
                    course.get('end_date', ''), course.get('enrollment_limit', 0),
                    is_pub))
                course_list.append(f"{course.get('lms_course_id')}: {course.get('module_code')}")

            for attr in ('lms_content_course_combo', 'lms_discussion_course_combo',
                         'lms_quiz_course_combo', 'lms_gradebook_course_combo'):
                combo = getattr(self, attr, None)
                if combo:
                    combo['values'] = course_list
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_courses')}: {e}")

    def _lms_create_course(self):
        dialog = tk.Toplevel(self.root)
        dialog.title(_("lms.dialogs.create_lms_course"))
        dialog.geometry("550x550"); dialog.transient(self.root); dialog.grab_set()

        frm = ttk.Frame(dialog, padding=10); frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.course', default="Course:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        course_combo = ttk.Combobox(frm, width=45, state='readonly')
        course_combo.grid(row=0, column=1, padx=5, pady=5)

        course_map = {}
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COALESCE(course_code, code), COALESCE(course_name, name) "
                    "FROM courses "
                    "WHERE COALESCE(course_code, code) IS NOT NULL "
                    "AND COALESCE(course_name, name) IS NOT NULL "
                    "AND LOWER(COALESCE(status, 'active')) = 'active' "
                    "ORDER BY COALESCE(course_code, code)")
                for code, name in cursor.fetchall():
                    label = f"{code} - {name}"
                    course_map[label] = code
        except Exception:
            pass
        course_combo['values'] = list(course_map.keys())
        if course_map:
            course_combo.current(0)

        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.instructor_id', default="Instructor ID:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        instructor_entry = ttk.Entry(frm, width=40)
        instructor_entry.insert(0, self._lms_user_id or '')
        instructor_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.description', default="Description:")).grid(row=2, column=0, sticky=tk.NW, padx=5, pady=5)
        desc_text = tk.Text(frm, width=40, height=5)
        desc_text.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.syllabus_url', default="Syllabus URL:")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        syllabus_entry = ttk.Entry(frm, width=40)
        syllabus_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.start_date', default="Start Date:")).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        start_entry = ttk.Entry(frm, width=40)
        start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        start_entry.grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.end_date', default="End Date:")).grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        end_entry = ttk.Entry(frm, width=40)
        end_entry.grid(row=5, column=1, padx=5, pady=5)

        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.enrollment_limit', default="Enrollment Limit:")).grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        limit_entry = ttk.Entry(frm, width=40)
        limit_entry.insert(0, "100")
        limit_entry.grid(row=6, column=1, padx=5, pady=5)

        def save_course():
            try:
                selected = course_combo.get()
                if selected not in course_map:
                    messagebox.showerror(_("common.error"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.dialogs.please_select_a_course', default="Please select a course.")); return
                code = course_map[selected]
                instr = instructor_entry.get().strip()
                if not instr:
                    messagebox.showerror(_("common.error"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.dialogs.instructor_id_is_required', default="Instructor ID is required.")); return
                cid = LMSCourseManager.create_lms_course(
                    module_code=code, instructor_id=instr,
                    course_description=desc_text.get('1.0', tk.END).strip(),
                    syllabus_url=syllabus_entry.get().strip(),
                    start_date=start_entry.get().strip(),
                    end_date=end_entry.get().strip(),
                    enrollment_limit=int(limit_entry.get().strip() or 0))
                log_activity('create', 'lms_course', str(cid), {'course_code': code, 'instructor_id': instr})
                messagebox.showinfo(_("common.success"), f"LMS course created (ID: {cid})")
                dialog.destroy(); self._lms_load_courses()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_create_course')}: {e}")

        btn_frame = ttk.Frame(frm); btn_frame.grid(row=7, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text=_("lms.buttons.create_course"), command=save_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _lms_publish_course(self):
        sel = self.lms_courses_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_course_first")); return
        cid = self.lms_courses_tree.item(sel[0])['values'][0]
        try:
            LMSCourseManager.publish_course(cid)
            log_activity('publish', 'lms_course', str(cid))
            messagebox.showinfo(_("common.success"), _("lms.messages.course_published"))
            self._lms_load_courses()
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_publish_course')}: {e}")

    def _lms_view_course_details(self):
        sel = self.lms_courses_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_course_first")); return
        cid = self.lms_courses_tree.item(sel[0])['values'][0]
        try:
            course = LMSCourseManager.get_course_details(cid)
            if course:
                info = (
                    f"Course ID: {course.get('lms_course_id')}\n"
                    f"Module Code: {course.get('module_code')}\n"
                    f"Instructor: {course.get('instructor_id')}\n"
                    f"Description: {course.get('course_description', 'N/A')}\n"
                    f"Start: {course.get('start_date', 'N/A')}\n"
                    f"End: {course.get('end_date', 'N/A')}\n"
                    f"Limit: {course.get('enrollment_limit', 0)}\n"
                    f"Published: {'Yes' if course.get('is_published') else 'No'}\n")
                messagebox.showinfo(_("lms.dialogs.course_details"), info)
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_course_details')}: {e}")

    def _create_lms_content_subtab(self):
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_("lms.tabs.content"))

        sel = ttk.Frame(tab); sel.pack(fill=tk.X, pady=5)
        ttk.Label(sel, text=_("lms.labels.select_course")).pack(side=tk.LEFT, padx=5)
        self.lms_content_course_combo = ttk.Combobox(sel, width=50, state='readonly')
        self.lms_content_course_combo.pack(side=tk.LEFT, padx=5)
        self.lms_content_course_combo.bind('<<ComboboxSelected>>', self._lms_load_content)
        ttk.Button(sel, text=_("lms.buttons.load_content"), command=self._lms_load_content).pack(side=tk.LEFT, padx=5)

        btn = ttk.Frame(tab); btn.pack(fill=tk.X, pady=5)
        ttk.Button(btn, text=_("lms.buttons.add_content"), command=self._lms_add_content).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.add_video_lecture"), command=self._lms_add_video).pack(side=tk.LEFT, padx=5)

        lf = ttk.LabelFrame(tab, text=_("lms.frames.course_content"), padding=10)
        lf.pack(fill=tk.BOTH, expand=True, pady=5)
        cols = ("ID", "Type", "Title", "Description", "URL", "Order", "Release Date")
        self.lms_content_tree = ttk.Treeview(lf, columns=cols, show='headings', height=15)
        for c in cols:
            self.lms_content_tree.heading(c, text=c)
            self.lms_content_tree.column(c, width=200 if c in ("Title", "Description", "URL") else 80)
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.lms_content_tree.yview)
        self.lms_content_tree.configure(yscrollcommand=sb.set)
        self.lms_content_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _lms_get_selected_course_id(self, combo_attr):
        combo = getattr(self, combo_attr, None)
        if not combo:
            return None
        sel = combo.get()
        if not sel:
            return None
        try:
            return int(sel.split(':')[0])
        except (ValueError, IndexError):
            return None

    def _lms_load_content(self, *a):
        cid = self._lms_get_selected_course_id('lms_content_course_combo')
        if not cid:
            return
        self.lms_content_tree.delete(*self.lms_content_tree.get_children())
        try:
            for c in LMSContentManager.get_course_content(cid):
                self.lms_content_tree.insert('', tk.END, values=(
                    c.get('content_id'), c.get('content_type'), c.get('title'),
                    c.get('description', '')[:50], c.get('content_url', ''),
                    c.get('content_order', 0), c.get('release_date', '')))
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_content')}: {e}")

    def _lms_add_content(self):
        cid = self._lms_get_selected_course_id('lms_content_course_combo')
        if not cid:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_course_first")); return

        dlg = tk.Toplevel(self.root); dlg.title(_("lms.dialogs.add_course_content"))
        dlg.geometry("500x500"); dlg.transient(self.root); dlg.grab_set()
        fields = {}

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.content_type', default="Content Type:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['type'] = ttk.Combobox(dlg, values=["Lecture", "Reading", "Video", "Assignment", "Quiz"],
                                      width=38, state='readonly')
        fields['type'].current(0); fields['type'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.title', default="Title:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['title'] = ttk.Entry(dlg, width=40); fields['title'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.description', default="Description:")).grid(row=2, column=0, sticky=tk.NW, padx=5, pady=5)
        fields['description'] = tk.Text(dlg, width=40, height=5); fields['description'].grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.content_url', default="Content URL:")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['url'] = ttk.Entry(dlg, width=40); fields['url'].grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.order', default="Order:")).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        fields['order'] = ttk.Entry(dlg, width=40); fields['order'].insert(0, "0")
        fields['order'].grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(dlg, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.labels.release_date', default="Release Date:")).grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        fields['release_date'] = ttk.Entry(dlg, width=40)
        fields['release_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        fields['release_date'].grid(row=5, column=1, padx=5, pady=5)

        def save():
            title = fields['title'].get().strip()
            if not title:
                messagebox.showerror(_("common.error"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_lms_switch_to_cli.dialogs.title_is_required', default="Title is required")); return
            try:
                content_id = LMSContentManager.add_content(
                    lms_course_id=cid, content_type=fields['type'].get(), title=title,
                    description=fields['description'].get('1.0', tk.END).strip(),
                    content_url=fields['url'].get().strip(),
                    content_order=int(fields['order'].get()),
                    release_date=fields['release_date'].get().strip())
                log_activity('create', 'lms_content', str(content_id), {'course_id': cid, 'title': title})
                messagebox.showinfo(_("common.success"), f"Content added (ID: {content_id})")
                dlg.destroy(); self._lms_load_content()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_add_content')}: {e}")

        ttk.Button(dlg, text=_("lms.buttons.add_content"), command=save).grid(row=6, column=0, columnspan=2, pady=20)
