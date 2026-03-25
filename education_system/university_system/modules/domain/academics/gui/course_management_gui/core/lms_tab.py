"""LMS mixin – embeds the Learning Management System as a tab in CourseManagementGUI.

All LMS functionality is implemented directly here. No external LMS GUI files
are required.
"""

from education_system.university_system.modules.domain.academics.gui.course_management_gui.core._imports import (
    _, tk, ttk, messagebox, ScrolledText, sqlite3, DEFAULT_DB_PATH, datetime, json,
)

try:
    from education_system.university_system.modules.domain.academics.services.lms.lms_core import (
        LMSCourseManager, LMSContentManager, LMSDiscussionManager,
        LMSQuizManager, LMSGradebookManager,
    )
    from education_system.university_system.modules.domain.academics.services.lms.db_schema import initialize_lms_database
    from education_system.university_system.infrastructure.database.db import get_connection
    LMS_AVAILABLE = True
except ImportError:
    LMS_AVAILABLE = False

try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
except ImportError:
    def log_activity(*a, **kw): pass

# Shared LMS services (module/lesson layer, resources, progress)
try:
    from education_system.shared.lms.course_content_service import CourseContentService
    from education_system.shared.lms.learning_progress_service import LearningProgressService
    from education_system.shared.lms.quiz_service import QuizService
    from education_system.shared.lms.resource_library_service import ResourceLibraryService
    from education_system.shared.lms.schema import create_lms_tables
    SHARED_LMS_AVAILABLE = True
except ImportError:
    SHARED_LMS_AVAILABLE = False


class LMSTabMixin:
    """Adds an LMS tab with sub-notebook to the course management GUI."""

    # ------------------------------------------------------------------
    # Tab creation
    # ------------------------------------------------------------------

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

    # ==================================================================
    # COURSES TAB
    # ==================================================================

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

        ttk.Label(frm, text="Course:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
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

        ttk.Label(frm, text="Instructor ID:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        instructor_entry = ttk.Entry(frm, width=40)
        instructor_entry.insert(0, self._lms_user_id or '')
        instructor_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frm, text="Description:").grid(row=2, column=0, sticky=tk.NW, padx=5, pady=5)
        desc_text = tk.Text(frm, width=40, height=5)
        desc_text.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(frm, text="Syllabus URL:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        syllabus_entry = ttk.Entry(frm, width=40)
        syllabus_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(frm, text="Start Date:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        start_entry = ttk.Entry(frm, width=40)
        start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        start_entry.grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(frm, text="End Date:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        end_entry = ttk.Entry(frm, width=40)
        end_entry.grid(row=5, column=1, padx=5, pady=5)

        ttk.Label(frm, text="Enrollment Limit:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        limit_entry = ttk.Entry(frm, width=40)
        limit_entry.insert(0, "100")
        limit_entry.grid(row=6, column=1, padx=5, pady=5)

        def save_course():
            try:
                selected = course_combo.get()
                if selected not in course_map:
                    messagebox.showerror(_("common.error"), "Please select a course."); return
                code = course_map[selected]
                instr = instructor_entry.get().strip()
                if not instr:
                    messagebox.showerror(_("common.error"), "Instructor ID is required."); return
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
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

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

    # ==================================================================
    # CONTENT TAB
    # ==================================================================

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

        ttk.Label(dlg, text="Content Type:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['type'] = ttk.Combobox(dlg, values=["Lecture", "Reading", "Video", "Assignment", "Quiz"],
                                      width=38, state='readonly')
        fields['type'].current(0); fields['type'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Title:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['title'] = ttk.Entry(dlg, width=40); fields['title'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Description:").grid(row=2, column=0, sticky=tk.NW, padx=5, pady=5)
        fields['description'] = tk.Text(dlg, width=40, height=5); fields['description'].grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Content URL:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['url'] = ttk.Entry(dlg, width=40); fields['url'].grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Order:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        fields['order'] = ttk.Entry(dlg, width=40); fields['order'].insert(0, "0")
        fields['order'].grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Release Date:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        fields['release_date'] = ttk.Entry(dlg, width=40)
        fields['release_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        fields['release_date'].grid(row=5, column=1, padx=5, pady=5)

        def save():
            title = fields['title'].get().strip()
            if not title:
                messagebox.showerror(_("common.error"), "Title is required"); return
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

    def _lms_add_video(self):
        sel = self.lms_content_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_content_first")); return
        content_id = self.lms_content_tree.item(sel[0])['values'][0]

        dlg = tk.Toplevel(self.root); dlg.title(_("lms.dialogs.add_video_lecture"))
        dlg.geometry("500x400"); dlg.transient(self.root); dlg.grab_set()
        fields = {}

        ttk.Label(dlg, text="Video URL:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['video_url'] = ttk.Entry(dlg, width=40); fields['video_url'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Duration (mins):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['duration'] = ttk.Entry(dlg, width=40); fields['duration'].insert(0, "0")
        fields['duration'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Thumbnail URL:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        fields['thumbnail'] = ttk.Entry(dlg, width=40); fields['thumbnail'].grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Transcript URL:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['transcript'] = ttk.Entry(dlg, width=40); fields['transcript'].grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Quality:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        fields['quality'] = ttk.Combobox(dlg, values=['360p', '480p', '720p', '1080p', '4K'], width=38, state='readonly')
        fields['quality'].current(2); fields['quality'].grid(row=4, column=1, padx=5, pady=5)

        def save():
            url = fields['video_url'].get().strip()
            if not url:
                messagebox.showerror(_("common.error"), "Video URL is required"); return
            try:
                vid = LMSContentManager.add_video_lecture(
                    content_id=content_id, video_url=url,
                    duration_minutes=int(fields['duration'].get()),
                    thumbnail_url=fields['thumbnail'].get().strip(),
                    transcript_url=fields['transcript'].get().strip(),
                    video_quality=fields['quality'].get())
                log_activity('create', 'lms_video_lecture', str(vid), {'content_id': content_id})
                messagebox.showinfo(_("common.success"), f"Video added (ID: {vid})")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_add_video')}: {e}")

        ttk.Button(dlg, text="Add Video", command=save).grid(row=5, column=0, columnspan=2, pady=20)

    # ==================================================================
    # DISCUSSIONS TAB
    # ==================================================================

    def _create_lms_discussions_subtab(self):
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_("lms.tabs.discussions"))

        sel = ttk.Frame(tab); sel.pack(fill=tk.X, pady=5)
        ttk.Label(sel, text=_("lms.labels.select_course")).pack(side=tk.LEFT, padx=5)
        self.lms_discussion_course_combo = ttk.Combobox(sel, width=50, state='readonly')
        self.lms_discussion_course_combo.pack(side=tk.LEFT, padx=5)
        self.lms_discussion_course_combo.bind('<<ComboboxSelected>>', self._lms_load_forums)
        ttk.Button(sel, text=_("lms.buttons.load_forums"), command=self._lms_load_forums).pack(side=tk.LEFT, padx=5)

        btn = ttk.Frame(tab); btn.pack(fill=tk.X, pady=5)
        ttk.Button(btn, text=_("lms.buttons.create_forum"), command=self._lms_create_forum).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.view_posts"), command=self._lms_view_posts).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.add_post"), command=self._lms_add_post).pack(side=tk.LEFT, padx=5)

        lf = ttk.LabelFrame(tab, text=_("lms.frames.discussion_forums"), padding=10)
        lf.pack(fill=tk.BOTH, expand=True, pady=5)
        cols = ("ID", "Topic", "Description", "Created By", "Pinned", "Created")
        self.lms_forums_tree = ttk.Treeview(lf, columns=cols, show='headings', height=15)
        for c in cols:
            self.lms_forums_tree.heading(c, text=c)
            self.lms_forums_tree.column(c, width=250 if c in ("Topic", "Description") else 100)
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.lms_forums_tree.yview)
        self.lms_forums_tree.configure(yscrollcommand=sb.set)
        self.lms_forums_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _lms_load_forums(self, *a):
        cid = self._lms_get_selected_course_id('lms_discussion_course_combo')
        if not cid:
            return
        self.lms_forums_tree.delete(*self.lms_forums_tree.get_children())
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT forum_id, topic, description, created_by, is_pinned, created_at
                    FROM lms_discussion_forums WHERE lms_course_id = ?
                    ORDER BY is_pinned DESC, created_at DESC
                ''', (cid,))
                for row in cursor.fetchall():
                    pinned = "Yes" if row[4] == 1 else "No"
                    self.lms_forums_tree.insert('', tk.END, values=(
                        row[0], row[1], row[2], row[3], pinned, row[5]))
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_forums')}: {e}")

    def _lms_create_forum(self):
        cid = self._lms_get_selected_course_id('lms_discussion_course_combo')
        if not cid:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_course_first")); return

        dlg = tk.Toplevel(self.root); dlg.title(_("lms.dialogs.create_discussion_forum"))
        dlg.geometry("500x400"); dlg.transient(self.root); dlg.grab_set()

        ttk.Label(dlg, text="Topic:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        topic_entry = ttk.Entry(dlg, width=40); topic_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Description:").grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        desc_text = tk.Text(dlg, width=40, height=8); desc_text.grid(row=1, column=1, padx=5, pady=5)

        pin_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg, text="Pin Forum", variable=pin_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        def save():
            topic = topic_entry.get().strip()
            if not topic:
                messagebox.showerror(_("common.error"), "Topic is required"); return
            try:
                fid = LMSDiscussionManager.create_forum(
                    lms_course_id=cid, topic=topic,
                    description=desc_text.get('1.0', tk.END).strip(),
                    created_by=self._lms_user_id, is_pinned=pin_var.get())
                log_activity('create', 'lms_forum', str(fid), {'course_id': cid, 'topic': topic})
                messagebox.showinfo(_("common.success"), f"Forum created (ID: {fid})")
                dlg.destroy(); self._lms_load_forums()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_create_forum')}: {e}")

        ttk.Button(dlg, text=_("lms.buttons.create_forum"), command=save).grid(row=3, column=0, columnspan=2, pady=20)

    def _lms_view_posts(self):
        sel = self.lms_forums_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_forum_first")); return
        forum_id = self.lms_forums_tree.item(sel[0])['values'][0]
        try:
            posts = LMSDiscussionManager.get_forum_posts(forum_id)
            dlg = tk.Toplevel(self.root)
            dlg.title(f"Forum Posts - Forum {forum_id}"); dlg.geometry("800x600")
            posts_text = ScrolledText(dlg, wrap=tk.WORD, width=80, height=30)
            posts_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            for post in posts:
                posts_text.insert(tk.END,
                    f"Post ID: {post.get('post_id')}\n"
                    f"User: {post.get('user_id')}\n"
                    f"Date: {post.get('created_at')}\n"
                    f"Likes: {post.get('likes_count', 0)}\n"
                    f"Content: {post.get('content')}\n"
                    f"{'-' * 80}\n\n")
            posts_text.config(state='disabled')
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_posts')}: {e}")

    def _lms_add_post(self):
        sel = self.lms_forums_tree.selection()
        if not sel:
            messagebox.showwarning(_("common.warning"), _("lms.messages.select_forum_first")); return
        forum_id = self.lms_forums_tree.item(sel[0])['values'][0]

        dlg = tk.Toplevel(self.root); dlg.title("Add Post"); dlg.geometry("500x400")
        dlg.transient(self.root); dlg.grab_set()

        ttk.Label(dlg, text="Post Content:").grid(row=0, column=0, sticky=tk.NW, padx=5, pady=5)
        content_text = tk.Text(dlg, width=50, height=15); content_text.grid(row=0, column=1, padx=5, pady=5)

        def save():
            content = content_text.get('1.0', tk.END).strip()
            if not content:
                messagebox.showerror(_("common.error"), "Post content is required"); return
            try:
                pid = LMSDiscussionManager.add_post(forum_id=forum_id, user_id=self._lms_user_id, content=content)
                log_activity('create', 'lms_post', str(pid), {'forum_id': forum_id})
                messagebox.showinfo(_("common.success"), f"Post added (ID: {pid})")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_add_post')}: {e}")

        ttk.Button(dlg, text="Add Post", command=save).grid(row=1, column=0, columnspan=2, pady=20)

    # ==================================================================
    # QUIZZES TAB
    # ==================================================================

    def _create_lms_quizzes_subtab(self):
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_("lms.tabs.quizzes"))

        sel = ttk.Frame(tab); sel.pack(fill=tk.X, pady=5)
        ttk.Label(sel, text=_("lms.labels.select_course")).pack(side=tk.LEFT, padx=5)
        self.lms_quiz_course_combo = ttk.Combobox(sel, width=50, state='readonly')
        self.lms_quiz_course_combo.pack(side=tk.LEFT, padx=5)
        self.lms_quiz_course_combo.bind('<<ComboboxSelected>>', self._lms_load_quizzes)
        ttk.Button(sel, text=_("lms.buttons.load_quizzes"), command=self._lms_load_quizzes).pack(side=tk.LEFT, padx=5)

        btn = ttk.Frame(tab); btn.pack(fill=tk.X, pady=5)
        ttk.Button(btn, text=_("lms.buttons.create_quiz"), command=self._lms_create_quiz).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.add_questions"), command=self._lms_add_questions).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text=_("lms.buttons.view_submissions"), command=self._lms_view_submissions).pack(side=tk.LEFT, padx=5)

        lf = ttk.LabelFrame(tab, text=_("lms.frames.quizzes"), padding=10)
        lf.pack(fill=tk.BOTH, expand=True, pady=5)
        cols = ("ID", "Title", "Duration (min)", "Passing Score", "Max Attempts", "From", "Until")
        self.lms_quizzes_tree = ttk.Treeview(lf, columns=cols, show='headings', height=15)
        for c in cols:
            self.lms_quizzes_tree.heading(c, text=c)
            self.lms_quizzes_tree.column(c, width=200 if c == "Title" else 100)
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.lms_quizzes_tree.yview)
        self.lms_quizzes_tree.configure(yscrollcommand=sb.set)
        self.lms_quizzes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _lms_load_quizzes(self, *a):
        cid = self._lms_get_selected_course_id('lms_quiz_course_combo')
        if not cid:
            return
        self.lms_quizzes_tree.delete(*self.lms_quizzes_tree.get_children())
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT quiz_id, title, duration_minutes, passing_score,
                           max_attempts, available_from, available_until
                    FROM lms_quizzes WHERE lms_course_id = ?
                    ORDER BY created_at DESC
                ''', (cid,))
                for row in cursor.fetchall():
                    self.lms_quizzes_tree.insert('', tk.END, values=tuple(row))
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_load_quizzes')}: {e}")

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

        ttk.Label(dlg, text="Description:").grid(row=6, column=0, sticky=tk.NW, padx=5, pady=5)
        desc_text = tk.Text(dlg, width=40, height=5); desc_text.grid(row=6, column=1, padx=5, pady=5)

        def save():
            title = fields['title'].get().strip()
            if not title:
                messagebox.showerror(_("common.error"), "Title is required"); return
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

        ttk.Label(dlg, text="Question Text:").grid(row=0, column=0, sticky=tk.NW, padx=5, pady=5)
        question_text = tk.Text(dlg, width=50, height=5); question_text.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        type_combo = ttk.Combobox(dlg, values=["Multiple Choice", "True/False", "Short Answer", "Essay"],
                                  width=48, state='readonly')
        type_combo.current(0); type_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Correct Answer:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        answer_entry = ttk.Entry(dlg, width=50); answer_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Points:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        points_entry = ttk.Entry(dlg, width=50); points_entry.insert(0, "1")
        points_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Options (JSON):").grid(row=4, column=0, sticky=tk.NW, padx=5, pady=5)
        options_text = tk.Text(dlg, width=50, height=5)
        options_text.insert('1.0', '["Option A", "Option B", "Option C", "Option D"]')
        options_text.grid(row=4, column=1, padx=5, pady=5)

        def save():
            text = question_text.get('1.0', tk.END).strip()
            if not text:
                messagebox.showerror(_("common.error"), "Question text is required"); return
            try:
                qid = LMSQuizManager.add_question(
                    quiz_id=quiz_id, question_text=text, question_type=type_combo.get(),
                    correct_answer=answer_entry.get().strip(), points=int(points_entry.get()),
                    options=options_text.get('1.0', tk.END).strip())
                messagebox.showinfo(_("common.success"), f"Question added (ID: {qid})")
                question_text.delete('1.0', tk.END); answer_entry.delete(0, tk.END)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_add_question')}: {e}")

        ttk.Button(dlg, text="Add Question", command=save).grid(row=5, column=0, columnspan=2, pady=20)

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
            lf = ttk.LabelFrame(dlg, text="Submissions", padding=10)
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

    # ==================================================================
    # GRADEBOOK TAB
    # ==================================================================

    def _create_lms_gradebook_subtab(self):
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text="Gradebook")

        sel = ttk.Frame(tab); sel.pack(fill=tk.X, pady=5)
        ttk.Label(sel, text="Course:").grid(row=0, column=0, padx=5, pady=5)
        self.lms_gradebook_course_combo = ttk.Combobox(sel, width=40, state='readonly')
        self.lms_gradebook_course_combo.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(sel, text="Student ID:").grid(row=0, column=2, padx=5, pady=5)
        self.lms_gradebook_student_entry = ttk.Entry(sel, width=20)
        self.lms_gradebook_student_entry.grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(sel, text="Load Grades", command=self._lms_load_grades).grid(row=0, column=4, padx=5, pady=5)

        btn = ttk.Frame(tab); btn.pack(fill=tk.X, pady=5)
        ttk.Button(btn, text="Add Grade", command=self._lms_add_grade).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text="Calculate Course Grade", command=self._lms_calculate_grade).pack(side=tk.LEFT, padx=5)

        lf = ttk.LabelFrame(tab, text="Gradebook Entries", padding=10)
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
            messagebox.showwarning(_("common.warning"), "Select course and enter student ID"); return
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

        dlg = tk.Toplevel(self.root); dlg.title("Add Grade Entry")
        dlg.geometry("500x500"); dlg.transient(self.root); dlg.grab_set()
        fields = {}

        ttk.Label(dlg, text="Student ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['student_id'] = ttk.Entry(dlg, width=40); fields['student_id'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dlg, text="Assignment Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
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

        ttk.Label(dlg, text="Feedback:").grid(row=6, column=0, sticky=tk.NW, padx=5, pady=5)
        feedback_text = tk.Text(dlg, width=40, height=5); feedback_text.grid(row=6, column=1, padx=5, pady=5)

        def save():
            sid = fields['student_id'].get().strip()
            if not sid:
                messagebox.showerror(_("common.error"), "Student ID is required"); return
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

        ttk.Button(dlg, text="Add Grade", command=save).grid(row=7, column=0, columnspan=2, pady=20)

    def _lms_calculate_grade(self):
        cid = self._lms_get_selected_course_id('lms_gradebook_course_combo')
        sid = self.lms_gradebook_student_entry.get().strip()
        if not cid or not sid:
            messagebox.showwarning(_("common.warning"), "Select course and enter student ID"); return
        try:
            grade = LMSGradebookManager.calculate_course_grade(cid, sid)
            messagebox.showinfo("Course Grade", f"Overall grade for {sid}:\n{grade:.2f}%")
        except Exception as e:
            messagebox.showerror(_("common.error"), f"{_('lms.messages.failed_calculate_grade')}: {e}")

    # ==================================================================
    # MY COURSES TAB (Student)
    # ==================================================================

    def _create_lms_my_courses_subtab(self):
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_("lms.tabs.my_courses"))

        ttk.Label(tab, text=_("lms.labels.my_enrolled_courses"),
                  font=('Arial', 12, 'bold')).pack(pady=10)

        btn = ttk.Frame(tab); btn.pack(fill=tk.X, pady=5)
        ttk.Button(btn, text="Enrol in LMS Course", command=self._lms_enrol).pack(side=tk.LEFT, padx=5)
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
        dlg = tk.Toplevel(self.root); dlg.title("Enrol in LMS Course")
        dlg.geometry("500x350"); dlg.transient(self.root); dlg.grab_set()
        frm = ttk.Frame(dlg, padding=10); frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Available LMS Courses", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

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
            ttk.Label(frm, text="No available courses to enrol in.").pack(pady=20)
            ttk.Button(frm, text="Close", command=dlg.destroy).pack(pady=10); return

        ttk.Label(frm, text="Select a course:").pack(anchor=tk.W, pady=(10, 5))
        course_combo = ttk.Combobox(frm, values=list(course_map.keys()), width=60, state='readonly')
        course_combo.pack(fill=tk.X, pady=(0, 10))
        if course_map:
            course_combo.current(0)

        def do_enrol():
            selected = course_combo.get()
            if selected not in course_map:
                messagebox.showwarning(_("common.warning"), "Please select a course."); return
            lms_cid = course_map[selected]
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT enrollment_limit FROM lms_courses WHERE lms_course_id = ?", (lms_cid,))
                    limit_row = cursor.fetchone()
                    if limit_row and limit_row[0] and limit_row[0] > 0:
                        cursor.execute("SELECT COUNT(*) FROM lms_student_enrollment WHERE lms_course_id = ? AND is_active = 1", (lms_cid,))
                        if cursor.fetchone()[0] >= limit_row[0]:
                            messagebox.showwarning("Course Full", "This course has reached its enrollment limit."); return
                    cursor.execute('INSERT INTO lms_student_enrollment (lms_course_id, student_id) VALUES (?, ?)',
                                   (lms_cid, self._lms_user_id))
                    conn.commit()
                messagebox.showinfo(_("common.success"), f"Successfully enrolled!")
                dlg.destroy(); self._lms_load_student_courses()
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to enrol: {e}")

        btn_frame = ttk.Frame(frm); btn_frame.pack(fill=tk.X, pady=20)
        ttk.Button(btn_frame, text="Enrol", command=do_enrol).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT, padx=5)

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
            lf = ttk.LabelFrame(dlg, text="Course Materials", padding=10)
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

            overall_frame = ttk.LabelFrame(dlg, text="Overall Grade", padding=10)
            overall_frame.pack(fill=tk.X, padx=10, pady=10)
            ttk.Label(overall_frame, text=f"Course Grade: {overall:.2f}%",
                      font=('Arial', 14, 'bold')).pack(pady=5)

            lf = ttk.LabelFrame(dlg, text="Individual Grades", padding=10)
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

    # ==================================================================
    # SHARED LMS: Modules & Lessons, Create Lesson, Resources, Progress
    # ==================================================================

    def _create_lms_modules_subtab(self):
        if not self._sh_content_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text="Modules & Lessons")

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text="Course ID:").pack(side=tk.LEFT, padx=5)
        self._sh_mod_course_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_mod_course_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Load Modules", command=self._sh_load_modules).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="New Module", command=self._sh_new_module_dialog).pack(side=tk.LEFT, padx=5)

        cols = ("ID", "Title", "Type", "Published", "Order")
        self._sh_modules_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self._sh_modules_tree.heading(c, text=c); self._sh_modules_tree.column(c, width=120)
        self._sh_modules_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_row = ttk.Frame(tab); btn_row.pack(fill=tk.X, pady=5)
        ttk.Button(btn_row, text="Publish Module", command=self._sh_publish_module).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Unpublish Module", command=self._sh_unpublish_module).pack(side=tk.LEFT, padx=5)

    def _sh_load_modules(self):
        if not self._sh_content_svc:
            return
        val = self._sh_mod_course_var.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning("LMS", "Please enter a Course ID."); return
        cid = int(val)
        self._sh_modules_tree.delete(*self._sh_modules_tree.get_children())
        for m in self._sh_content_svc.list_modules(cid):
            self._sh_modules_tree.insert("", "end", values=(
                m["id"], m["title"], "Module", "Yes" if m["published"] else "No", m["order_index"]))
            for ls in self._sh_content_svc.list_lessons(m["id"]):
                self._sh_modules_tree.insert("", "end", values=(
                    ls["id"], f"   {ls['title']}", ls["content_type"], "", ls["order_index"]))

    def _sh_new_module_dialog(self):
        if not self._sh_content_svc:
            return
        val = self._sh_mod_course_var.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning("LMS", "Please enter a Course ID first."); return
        cid = int(val)
        dlg = tk.Toplevel(self.root); dlg.title("New Module"); dlg.geometry("380x200"); dlg.grab_set()
        frm = ttk.Frame(dlg, padding=15); frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Title:").grid(row=0, column=0, sticky="w", pady=4)
        title_var = tk.StringVar()
        ttk.Entry(frm, textvariable=title_var, width=35).grid(row=0, column=1, pady=4)
        ttk.Label(frm, text="Description:").grid(row=1, column=0, sticky="w", pady=4)
        desc_var = tk.StringVar()
        ttk.Entry(frm, textvariable=desc_var, width=35).grid(row=1, column=1, pady=4)

        def _save():
            t = title_var.get().strip()
            if not t:
                messagebox.showwarning("LMS", "Title is required"); return
            try:
                self._sh_content_svc.create_module(cid, t, desc_var.get())
                dlg.destroy(); self._sh_load_modules()
            except Exception as e:
                messagebox.showerror("LMS", str(e))
        ttk.Button(frm, text="Save", command=_save).grid(row=2, column=1, sticky="e", pady=10)

    def _sh_publish_module(self):
        sel = self._sh_modules_tree.selection()
        if not sel or not self._sh_content_svc:
            return
        vals = self._sh_modules_tree.item(sel[0], "values")
        if vals[2] == "Module":
            self._sh_content_svc.publish_module(int(vals[0])); self._sh_load_modules()

    def _sh_unpublish_module(self):
        sel = self._sh_modules_tree.selection()
        if not sel or not self._sh_content_svc:
            return
        vals = self._sh_modules_tree.item(sel[0], "values")
        if vals[2] == "Module":
            self._sh_content_svc.unpublish_module(int(vals[0])); self._sh_load_modules()

    # ------------------------------------------------------------------

    def _create_lms_create_lesson_subtab(self):
        if not self._sh_content_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text="Create Lesson")
        frm = ttk.Frame(tab, padding=10); frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Module ID:").grid(row=0, column=0, sticky="w", pady=4)
        self._sh_lesson_mod_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._sh_lesson_mod_var, width=10).grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(frm, text="Title:").grid(row=1, column=0, sticky="w", pady=4)
        self._sh_lesson_title_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._sh_lesson_title_var, width=40).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(frm, text="Content Type:").grid(row=2, column=0, sticky="w", pady=4)
        self._sh_lesson_type_var = tk.StringVar(value="text")
        ttk.Combobox(frm, textvariable=self._sh_lesson_type_var, width=18,
                     values=["text", "video_link", "document", "quiz", "activity"],
                     state="readonly").grid(row=2, column=1, sticky="w", pady=4)
        ttk.Label(frm, text="Duration (mins):").grid(row=3, column=0, sticky="w", pady=4)
        self._sh_lesson_dur_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._sh_lesson_dur_var, width=10).grid(row=3, column=1, sticky="w", pady=4)
        ttk.Label(frm, text="Content:").grid(row=4, column=0, sticky="nw", pady=4)
        self._sh_lesson_content_txt = tk.Text(frm, width=50, height=8)
        self._sh_lesson_content_txt.grid(row=4, column=1, sticky="w", pady=4)
        ttk.Button(frm, text="Create Lesson", command=self._sh_create_lesson).grid(row=5, column=1, sticky="e", pady=10)

    def _sh_create_lesson(self):
        if not self._sh_content_svc:
            return
        val = self._sh_lesson_mod_var.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning("LMS", "Please enter a Module ID."); return
        mod_id = int(val)
        title = self._sh_lesson_title_var.get().strip()
        if not title:
            messagebox.showwarning("LMS", "Title is required"); return
        dur_str = self._sh_lesson_dur_var.get().strip()
        dur = int(dur_str) if dur_str.isdigit() else None
        content = self._sh_lesson_content_txt.get("1.0", "end-1c")
        try:
            self._sh_content_svc.create_lesson(mod_id, title, self._sh_lesson_type_var.get(), content, duration_mins=dur)
            messagebox.showinfo("LMS", f"Lesson '{title}' created successfully")
            self._sh_lesson_title_var.set(""); self._sh_lesson_content_txt.delete("1.0", "end"); self._sh_lesson_dur_var.set("")
        except Exception as e:
            messagebox.showerror("LMS", str(e))

    # ------------------------------------------------------------------

    def _create_lms_resources_subtab(self):
        if not self._sh_resource_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text="Resources")

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text="Search:").pack(side=tk.LEFT, padx=5)
        self._sh_res_search_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_res_search_var, width=25).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Search", command=self._sh_search_resources).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Show All", command=self._sh_list_all_resources).pack(side=tk.LEFT, padx=5)
        if self._lms_user_role in ('admin', 'instructor', 'staff'):
            ttk.Button(top, text="Upload", command=self._sh_upload_resource_dialog).pack(side=tk.LEFT, padx=5)

        cols = ("ID", "Title", "Type", "Downloads", "Uploaded By")
        self._sh_res_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._sh_res_tree.heading(c, text=c); self._sh_res_tree.column(c, width=120)
        self._sh_res_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_row = ttk.Frame(tab); btn_row.pack(fill=tk.X, pady=5)
        ttk.Button(btn_row, text="Download", command=self._sh_download_resource).pack(side=tk.LEFT, padx=5)
        if self._lms_user_role in ('admin', 'instructor', 'staff'):
            ttk.Button(btn_row, text="Delete", command=self._sh_delete_resource).pack(side=tk.LEFT, padx=5)

    def _sh_populate_resource_tree(self, resources):
        self._sh_res_tree.delete(*self._sh_res_tree.get_children())
        for r in resources:
            self._sh_res_tree.insert("", "end", values=(
                r["id"], r["title"], r["resource_type"], r["download_count"], r.get("uploaded_by", "")))

    def _sh_list_all_resources(self):
        if self._sh_resource_svc:
            self._sh_populate_resource_tree(self._sh_resource_svc.list_resources())

    def _sh_search_resources(self):
        if not self._sh_resource_svc:
            return
        q = self._sh_res_search_var.get().strip()
        if not q:
            self._sh_list_all_resources(); return
        self._sh_populate_resource_tree(self._sh_resource_svc.search_resources(q))

    def _sh_download_resource(self):
        sel = self._sh_res_tree.selection()
        if not sel or not self._sh_resource_svc:
            return
        rid = int(self._sh_res_tree.item(sel[0], "values")[0])
        res = self._sh_resource_svc.download_resource(rid)
        if res:
            messagebox.showinfo("LMS", f"Resource: {res['title']}\nPath: {res['file_path']}\nDownloads: {res['download_count']}")

    def _sh_upload_resource_dialog(self):
        if not self._sh_resource_svc:
            return
        dlg = tk.Toplevel(self.root); dlg.title("Upload Resource"); dlg.geometry("420x300"); dlg.grab_set()
        frm = ttk.Frame(dlg, padding=15); frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Title:").grid(row=0, column=0, sticky="w", pady=4)
        title_var = tk.StringVar()
        ttk.Entry(frm, textvariable=title_var, width=35).grid(row=0, column=1, pady=4)
        ttk.Label(frm, text="Description:").grid(row=1, column=0, sticky="w", pady=4)
        desc_var = tk.StringVar()
        ttk.Entry(frm, textvariable=desc_var, width=35).grid(row=1, column=1, pady=4)
        ttk.Label(frm, text="File Path / URL:").grid(row=2, column=0, sticky="w", pady=4)
        path_var = tk.StringVar()
        ttk.Entry(frm, textvariable=path_var, width=35).grid(row=2, column=1, pady=4)
        ttk.Label(frm, text="Type:").grid(row=3, column=0, sticky="w", pady=4)
        type_var = tk.StringVar(value="document")
        ttk.Combobox(frm, textvariable=type_var, width=18,
                     values=["document", "presentation", "spreadsheet", "image", "video_link", "audio", "other"],
                     state="readonly").grid(row=3, column=1, sticky="w", pady=4)
        ttk.Label(frm, text="Course ID (optional):").grid(row=4, column=0, sticky="w", pady=4)
        cid_var = tk.StringVar()
        ttk.Entry(frm, textvariable=cid_var, width=10).grid(row=4, column=1, sticky="w", pady=4)

        def _save():
            t = title_var.get().strip()
            if not t:
                messagebox.showwarning("LMS", "Title is required"); return
            cid_str = cid_var.get().strip()
            cid = int(cid_str) if cid_str.isdigit() else None
            try:
                self._sh_resource_svc.upload_resource(t, desc_var.get(), path_var.get(), type_var.get(), self._lms_user_id or "", cid)
                dlg.destroy(); self._sh_list_all_resources()
            except Exception as e:
                messagebox.showerror("LMS", str(e))
        ttk.Button(frm, text="Upload", command=_save).grid(row=5, column=1, sticky="e", pady=10)

    def _sh_delete_resource(self):
        sel = self._sh_res_tree.selection()
        if not sel or not self._sh_resource_svc:
            return
        rid = int(self._sh_res_tree.item(sel[0], "values")[0])
        if messagebox.askyesno("LMS", "Delete this resource?"):
            self._sh_resource_svc.delete_resource(rid); self._sh_list_all_resources()

    # ------------------------------------------------------------------

    def _create_lms_staff_progress_subtab(self):
        if not self._sh_progress_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text="Student Progress")

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text="Course ID:").pack(side=tk.LEFT, padx=5)
        self._sh_prog_course_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_prog_course_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Load Stats", command=self._sh_load_course_stats).pack(side=tk.LEFT, padx=5)

        self._sh_stats_frame = ttk.Frame(tab)
        self._sh_stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _sh_load_course_stats(self):
        if not self._sh_progress_svc:
            return
        val = self._sh_prog_course_var.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning("LMS", "Please enter a Course ID."); return
        cid = int(val)
        for w in self._sh_stats_frame.winfo_children():
            w.destroy()
        stats = self._sh_progress_svc.get_course_completion_stats(cid)
        for i, (lbl, val) in enumerate([
            ("Total Lessons", str(stats["total_lessons"])),
            ("Students", str(stats["total_students"])),
            ("Avg Completion", f"{stats['avg_percentage']}%"),
            ("Fully Completed", str(stats["fully_completed"])),
        ]):
            card = ttk.LabelFrame(self._sh_stats_frame, text=lbl, padding=15)
            card.grid(row=0, column=i, padx=8, pady=8)
            ttk.Label(card, text=val, font=("Helvetica", 18, "bold")).pack()
        if stats["total_lessons"] > 0 and stats["total_students"] > 0:
            bar_frame = ttk.Frame(self._sh_stats_frame)
            bar_frame.grid(row=1, column=0, columnspan=4, pady=15, sticky="ew")
            ttk.Label(bar_frame, text="Avg. Completion").pack(anchor="w")
            ttk.Progressbar(bar_frame, length=400, mode="determinate",
                            maximum=100, value=stats["avg_percentage"]).pack(fill="x", pady=5)

    # ------------------------------------------------------------------

    def _create_lms_current_lesson_subtab(self):
        if not self._sh_progress_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text="Current Lesson")

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text="Course ID:").pack(side=tk.LEFT, padx=5)
        self._sh_cur_course_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_cur_course_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Load Next Lesson", command=self._sh_load_next_lesson).pack(side=tk.LEFT, padx=5)

        self._sh_lesson_display = ttk.Frame(tab)
        self._sh_lesson_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self._sh_lesson_id_loaded = None

    def _sh_load_next_lesson(self):
        if not self._sh_progress_svc:
            return
        for w in self._sh_lesson_display.winfo_children():
            w.destroy()
        val = self._sh_cur_course_var.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning("LMS", "Please enter a Course ID."); return
        cid = int(val)
        sid = self._lms_user_id or ""
        lesson = self._sh_progress_svc.get_next_lesson(sid, cid)
        if not lesson:
            ttk.Label(self._sh_lesson_display, text="All lessons completed!",
                      font=("Helvetica", 14, "bold")).pack(expand=True)
            self._sh_lesson_id_loaded = None; return
        self._sh_lesson_id_loaded = lesson["id"]
        ttk.Label(self._sh_lesson_display, text=lesson["title"], font=("Helvetica", 14, "bold")).pack(anchor="w")
        ttk.Label(self._sh_lesson_display,
                  text=f"Type: {lesson['content_type']}   Duration: {lesson['duration_mins'] or '?'} mins",
                  font=("Helvetica", 9)).pack(anchor="w", pady=(0, 10))
        txt = tk.Text(self._sh_lesson_display, wrap="word", height=12, width=70)
        txt.insert("1.0", lesson.get("content") or "(No content)")
        txt.configure(state="disabled")
        txt.pack(fill=tk.BOTH, expand=True, pady=5)
        ttk.Button(self._sh_lesson_display, text="Mark Complete", command=self._sh_mark_complete).pack(pady=10)

    def _sh_mark_complete(self):
        if not self._sh_progress_svc or not self._sh_lesson_id_loaded:
            return
        self._sh_progress_svc.mark_lesson_complete(self._lms_user_id or "", self._sh_lesson_id_loaded)
        messagebox.showinfo("LMS", "Lesson marked as complete!")
        self._sh_load_next_lesson()

    # ------------------------------------------------------------------

    def _create_lms_take_quiz_subtab(self):
        if not self._sh_quiz_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text="Take Quiz")

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text="Quiz ID:").pack(side=tk.LEFT, padx=5)
        self._sh_stu_quiz_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_stu_quiz_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Start Quiz", command=self._sh_start_quiz).pack(side=tk.LEFT, padx=5)

        self._sh_quiz_area = ttk.Frame(tab)
        self._sh_quiz_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._sh_quiz_answer_vars = {}

    def _sh_start_quiz(self):
        if not self._sh_quiz_svc:
            return
        for w in self._sh_quiz_area.winfo_children():
            w.destroy()
        self._sh_quiz_answer_vars.clear()
        val = self._sh_stu_quiz_var.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning("LMS", "Please enter a Quiz ID."); return
        qid = int(val)

        questions = self._sh_quiz_svc.list_questions(qid)
        if not questions:
            ttk.Label(self._sh_quiz_area, text="No questions found for this quiz.").pack(); return

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
                ttk.Radiobutton(q_frame, text="True", variable=ans_var, value="true").pack(anchor="w", padx=15)
                ttk.Radiobutton(q_frame, text="False", variable=ans_var, value="false").pack(anchor="w", padx=15)
            else:
                ttk.Entry(q_frame, textvariable=ans_var, width=40).pack(anchor="w", padx=15)
            ttk.Separator(q_frame, orient="horizontal").pack(fill="x", pady=5)

        ttk.Button(scroll_frame, text="Submit Quiz",
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
                messagebox.showinfo("Quiz Result", msg)
            else:
                messagebox.showwarning("Quiz Result", msg)
        except Exception as e:
            messagebox.showerror("LMS", str(e))

    # ------------------------------------------------------------------

    def _create_lms_student_progress_subtab(self):
        if not self._sh_progress_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text="My Progress")

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text="Course ID:").pack(side=tk.LEFT, padx=5)
        self._sh_my_prog_course_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_my_prog_course_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="View Progress", command=self._sh_view_my_progress).pack(side=tk.LEFT, padx=5)

        self._sh_my_prog_frame = ttk.Frame(tab)
        self._sh_my_prog_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _sh_view_my_progress(self):
        if not self._sh_progress_svc:
            return
        for w in self._sh_my_prog_frame.winfo_children():
            w.destroy()
        val = self._sh_my_prog_course_var.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning("LMS", "Please enter a Course ID."); return
        cid = int(val)
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
            ttk.Label(self._sh_my_prog_frame, text="Completed Lessons:",
                      font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(15, 5))
            for c in completed:
                ttk.Label(self._sh_my_prog_frame,
                          text=f"  - {c['lesson_title']} ({c['module_title']})  {c.get('completed_at', '')}",
                          font=("Helvetica", 9)).pack(anchor="w")
