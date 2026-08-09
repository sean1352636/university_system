"""Methods _create_lms_modules_subtab through _create_lms_take_quiz_subtab."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import lms_tab_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class LMSTabMixin:
    def _create_lms_modules_subtab(self):
        if not self._sh_content_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.tabs.modules_lessons', default="Modules & Lessons"))

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.course_id_code', default="Course ID / Code:")).pack(side=tk.LEFT, padx=5)
        self._sh_mod_course_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_mod_course_var, width=14).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.load_modules', default="Load Modules"), command=self._sh_load_modules).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.new_module', default="New Module"), command=self._sh_new_module_dialog).pack(side=tk.LEFT, padx=5)

        cols = ("ID", "Title", "Type", "Published", "Order")
        self._sh_modules_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self._sh_modules_tree.heading(c, text=c); self._sh_modules_tree.column(c, width=120)
        self._sh_modules_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_row = ttk.Frame(tab); btn_row.pack(fill=tk.X, pady=5)
        ttk.Button(btn_row, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.publish_module', default="Publish Module"), command=self._sh_publish_module).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.unpublish_module', default="Unpublish Module"), command=self._sh_unpublish_module).pack(side=tk.LEFT, padx=5)

    def _sh_resolve_course(self, raw, silent=False):
        """Resolve a user-entered course identifier to the canonical
        ``courses.id`` value, or ``None`` when it doesn't match a real course.

        The shared ``lms_modules.course_id`` column has no foreign-key
        constraint and, in the university database, ``courses.id`` is a text
        code (e.g. ``CS``) rather than an integer. A plain ``isdigit()`` check
        therefore both accepts any number and rejects every real course. This
        instead matches the entry against the course id, code, or name so only
        genuine courses are accepted. Unless ``silent``, a warning is shown
        explaining what to enter.
        """
        val = (raw or "").strip()
        if not val:
            if not silent:
                messagebox.showwarning(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.please_enter_a_course_id_or_code', default="Please enter a Course ID or code."))
            return None
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='courses'"
                )
                if not cursor.fetchone():
                    if not silent:
                        messagebox.showwarning(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.no_courses_are_available_to_assign_content_to', default="No courses are available to assign content to."))
                    return None
                row = cursor.execute(
                    """
                    SELECT id FROM courses
                    WHERE CAST(id AS TEXT) = ?
                       OR LOWER(COALESCE(course_code, code)) = LOWER(?)
                       OR LOWER(COALESCE(course_name, name)) = LOWER(?)
                    LIMIT 1
                    """,
                    (val, val, val),
                ).fetchone()
        except Exception as e:
            if not silent:
                messagebox.showwarning(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), f"Could not validate the course: {e}")
            return None
        if not row:
            if not silent:
                messagebox.showwarning(
                    _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"),
                    f"'{val}' is not an existing course. Enter a valid Course "
                    "ID or code (e.g. CS).",
                )
            return None
        return row[0]

    def _sh_load_modules(self):
        if not self._sh_content_svc:
            return
        cid = self._sh_resolve_course(self._sh_mod_course_var.get())
        if cid is None:
            return
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
        cid = self._sh_resolve_course(self._sh_mod_course_var.get())
        if cid is None:
            return
        dlg = tk.Toplevel(self.root); dlg.title(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.windows.new_module', default="New Module")); dlg.geometry("380x200"); dlg.grab_set()
        frm = ttk.Frame(dlg, padding=15); frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.title', default="Title:")).grid(row=0, column=0, sticky="w", pady=4)
        title_var = tk.StringVar()
        ttk.Entry(frm, textvariable=title_var, width=35).grid(row=0, column=1, pady=4)
        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.description', default="Description:")).grid(row=1, column=0, sticky="w", pady=4)
        desc_var = tk.StringVar()
        ttk.Entry(frm, textvariable=desc_var, width=35).grid(row=1, column=1, pady=4)

        def _save():
            t = title_var.get().strip()
            if not t:
                messagebox.showwarning(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.title_is_required', default="Title is required")); return
            try:
                self._sh_content_svc.create_module(cid, t, desc_var.get())
                dlg.destroy(); self._sh_load_modules()
            except Exception as e:
                messagebox.showerror(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), str(e))
        ttk.Button(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.save', default="Save"), command=_save).grid(row=2, column=1, sticky="e", pady=10)

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

    def _create_lms_create_lesson_subtab(self):
        if not self._sh_content_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.tabs.create_lesson', default="Create Lesson"))
        frm = ttk.Frame(tab, padding=10); frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.module_id', default="Module ID:")).grid(row=0, column=0, sticky="w", pady=4)
        self._sh_lesson_mod_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._sh_lesson_mod_var, width=10).grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.title', default="Title:")).grid(row=1, column=0, sticky="w", pady=4)
        self._sh_lesson_title_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._sh_lesson_title_var, width=40).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.content_type', default="Content Type:")).grid(row=2, column=0, sticky="w", pady=4)
        self._sh_lesson_type_var = tk.StringVar(value=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.values.text', default="text"))
        ttk.Combobox(frm, textvariable=self._sh_lesson_type_var, width=18,
                     values=["text", "video_link", "document", "quiz", "activity"],
                     state="readonly").grid(row=2, column=1, sticky="w", pady=4)
        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.duration_mins', default="Duration (mins):")).grid(row=3, column=0, sticky="w", pady=4)
        self._sh_lesson_dur_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._sh_lesson_dur_var, width=10).grid(row=3, column=1, sticky="w", pady=4)
        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.content', default="Content:")).grid(row=4, column=0, sticky="nw", pady=4)
        self._sh_lesson_content_txt = tk.Text(frm, width=50, height=8)
        self._sh_lesson_content_txt.grid(row=4, column=1, sticky="w", pady=4)
        ttk.Button(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.create_lesson', default="Create Lesson"), command=self._sh_create_lesson).grid(row=5, column=1, sticky="e", pady=10)

    def _sh_create_lesson(self):
        if not self._sh_content_svc:
            return
        val = self._sh_lesson_mod_var.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.please_enter_a_module_id', default="Please enter a Module ID.")); return
        mod_id = int(val)
        title = self._sh_lesson_title_var.get().strip()
        if not title:
            messagebox.showwarning(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.title_is_required', default="Title is required")); return
        dur_str = self._sh_lesson_dur_var.get().strip()
        dur = int(dur_str) if dur_str.isdigit() else None
        content = self._sh_lesson_content_txt.get("1.0", "end-1c")
        try:
            self._sh_content_svc.create_lesson(mod_id, title, self._sh_lesson_type_var.get(), content, duration_mins=dur)
            messagebox.showinfo(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), f"Lesson '{title}' created successfully")
            self._sh_lesson_title_var.set(""); self._sh_lesson_content_txt.delete("1.0", "end"); self._sh_lesson_dur_var.set("")
        except Exception as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), str(e))

    def _create_lms_resources_subtab(self):
        if not self._sh_resource_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.tabs.resources', default="Resources"))

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.search', default="Search:")).pack(side=tk.LEFT, padx=5)
        self._sh_res_search_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_res_search_var, width=25).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.search', default="Search"), command=self._sh_search_resources).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.show_all', default="Show All"), command=self._sh_list_all_resources).pack(side=tk.LEFT, padx=5)
        if self._lms_user_role in ('admin', 'instructor', 'staff'):
            ttk.Button(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.upload', default="Upload"), command=self._sh_upload_resource_dialog).pack(side=tk.LEFT, padx=5)

        cols = ("ID", "Title", "Type", "Downloads", "Uploaded By")
        self._sh_res_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._sh_res_tree.heading(c, text=c); self._sh_res_tree.column(c, width=120)
        self._sh_res_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_row = ttk.Frame(tab); btn_row.pack(fill=tk.X, pady=5)
        ttk.Button(btn_row, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.download', default="Download"), command=self._sh_download_resource).pack(side=tk.LEFT, padx=5)
        if self._lms_user_role in ('admin', 'instructor', 'staff'):
            ttk.Button(btn_row, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.delete', default="Delete"), command=self._sh_delete_resource).pack(side=tk.LEFT, padx=5)

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
            messagebox.showinfo(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), f"Resource: {res['title']}\nPath: {res['file_path']}\nDownloads: {res['download_count']}")

    def _sh_upload_resource_dialog(self):
        if not self._sh_resource_svc:
            return
        dlg = tk.Toplevel(self.root); dlg.title(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.windows.upload_resource', default="Upload Resource")); dlg.geometry("420x300"); dlg.grab_set()
        frm = ttk.Frame(dlg, padding=15); frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.title', default="Title:")).grid(row=0, column=0, sticky="w", pady=4)
        title_var = tk.StringVar()
        ttk.Entry(frm, textvariable=title_var, width=35).grid(row=0, column=1, pady=4)
        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.description', default="Description:")).grid(row=1, column=0, sticky="w", pady=4)
        desc_var = tk.StringVar()
        ttk.Entry(frm, textvariable=desc_var, width=35).grid(row=1, column=1, pady=4)
        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.file_path_url', default="File Path / URL:")).grid(row=2, column=0, sticky="w", pady=4)
        path_var = tk.StringVar()
        ttk.Entry(frm, textvariable=path_var, width=35).grid(row=2, column=1, pady=4)
        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.type', default="Type:")).grid(row=3, column=0, sticky="w", pady=4)
        type_var = tk.StringVar(value=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.values.document', default="document"))
        ttk.Combobox(frm, textvariable=type_var, width=18,
                     values=["document", "presentation", "spreadsheet", "image", "video_link", "audio", "other"],
                     state="readonly").grid(row=3, column=1, sticky="w", pady=4)
        ttk.Label(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.course_id_optional', default="Course ID (optional):")).grid(row=4, column=0, sticky="w", pady=4)
        cid_var = tk.StringVar()
        ttk.Entry(frm, textvariable=cid_var, width=10).grid(row=4, column=1, sticky="w", pady=4)

        def _save():
            t = title_var.get().strip()
            if not t:
                messagebox.showwarning(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.title_is_required', default="Title is required")); return
            cid_str = cid_var.get().strip()
            cid = int(cid_str) if cid_str.isdigit() else None
            try:
                self._sh_resource_svc.upload_resource(t, desc_var.get(), path_var.get(), type_var.get(), self._lms_user_id or "", cid)
                dlg.destroy(); self._sh_list_all_resources()
            except Exception as e:
                messagebox.showerror(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), str(e))
        ttk.Button(frm, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.upload', default="Upload"), command=_save).grid(row=5, column=1, sticky="e", pady=10)

    def _sh_delete_resource(self):
        sel = self._sh_res_tree.selection()
        if not sel or not self._sh_resource_svc:
            return
        rid = int(self._sh_res_tree.item(sel[0], "values")[0])
        if messagebox.askyesno(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.delete_this_resource', default="Delete this resource?")):
            self._sh_resource_svc.delete_resource(rid); self._sh_list_all_resources()

    def _create_lms_staff_progress_subtab(self):
        if not self._sh_progress_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.tabs.student_progress', default="Student Progress"))

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.course_id_code', default="Course ID / Code:")).pack(side=tk.LEFT, padx=5)
        self._sh_prog_course_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_prog_course_var, width=14).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.load_stats', default="Load Stats"), command=self._sh_load_course_stats).pack(side=tk.LEFT, padx=5)

        self._sh_stats_frame = ttk.Frame(tab)
        self._sh_stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _sh_load_course_stats(self):
        if not self._sh_progress_svc:
            return
        cid = self._sh_resolve_course(self._sh_prog_course_var.get())
        if cid is None:
            return
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
            ttk.Label(bar_frame, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.avg_completion', default="Avg. Completion")).pack(anchor="w")
            ttk.Progressbar(bar_frame, length=400, mode="determinate",
                            maximum=100, value=stats["avg_percentage"]).pack(fill="x", pady=5)

    def _create_lms_current_lesson_subtab(self):
        if not self._sh_progress_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.tabs.current_lesson', default="Current Lesson"))

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.course_id_code', default="Course ID / Code:")).pack(side=tk.LEFT, padx=5)
        self._sh_cur_course_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_cur_course_var, width=14).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.load_next_lesson', default="Load Next Lesson"), command=self._sh_load_next_lesson).pack(side=tk.LEFT, padx=5)

        self._sh_lesson_display = ttk.Frame(tab)
        self._sh_lesson_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self._sh_lesson_id_loaded = None

    def _sh_load_next_lesson(self):
        if not self._sh_progress_svc:
            return
        for w in self._sh_lesson_display.winfo_children():
            w.destroy()
        cid = self._sh_resolve_course(self._sh_cur_course_var.get())
        if cid is None:
            return
        sid = self._lms_user_id or ""
        lesson = self._sh_progress_svc.get_next_lesson(sid, cid)
        if not lesson:
            ttk.Label(self._sh_lesson_display, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.all_lessons_completed', default="All lessons completed!"),
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
        ttk.Button(self._sh_lesson_display, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.mark_complete', default="Mark Complete"), command=self._sh_mark_complete).pack(pady=10)

    def _sh_mark_complete(self):
        if not self._sh_progress_svc or not self._sh_lesson_id_loaded:
            return
        self._sh_progress_svc.mark_lesson_complete(self._lms_user_id or "", self._sh_lesson_id_loaded)
        messagebox.showinfo(_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lms', default="LMS"), _t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.dialogs.lesson_marked_as_complete', default="Lesson marked as complete!"))
        self._sh_load_next_lesson()

    def _create_lms_take_quiz_subtab(self):
        if not self._sh_quiz_svc:
            return
        tab = ttk.Frame(self.lms_notebook, padding=10)
        self.lms_notebook.add(tab, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.tabs.take_quiz', default="Take Quiz"))

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=5)
        ttk.Label(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.labels.quiz_id', default="Quiz ID:")).pack(side=tk.LEFT, padx=5)
        self._sh_stu_quiz_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._sh_stu_quiz_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text=_t('gui.academics.course_management_gui.core.lms_tab_parts.lmstabmixin_create_lms_modules_subtab.buttons.start_quiz', default="Start Quiz"), command=self._sh_start_quiz).pack(side=tk.LEFT, padx=5)

        self._sh_quiz_area = ttk.Frame(tab)
        self._sh_quiz_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._sh_quiz_answer_vars = {}
