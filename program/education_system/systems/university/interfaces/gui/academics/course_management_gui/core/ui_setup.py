from tkinter.scrolledtext import ScrolledText

from education_system.systems.university.interfaces.gui.academics.course_management_gui.core._imports import (
    _, logging, messagebox, threading, tk, ttk, Path,
    ORIGINAL_MODULE_AVAILABLE, display_enhanced_course_menu,
    ACADEMIC_SYSTEMS_AVAILABLE,
)


class UISetupMixin:
    """Menu bar, toolbar, and tab creation."""

    def _bind_shortcut(self, menu, label, command, accelerator=None, sequence=None):
        """Add a menu command with an accelerator label AND a root key binding.

        Going through one helper makes the two halves impossible to drift
        apart. ``sequence`` is the Tk event spec ('<Control-n>'); accelerator
        is the cosmetic 'Ctrl+N' label shown next to the menu item.
        """
        kwargs = {"label": label, "command": command}
        if accelerator:
            kwargs["accelerator"] = accelerator
        menu.add_command(**kwargs)
        if sequence:
            self.root.bind_all(sequence, lambda _e, c=command: c())

    def _db_module_choices(self):
        """Return ``[(module_code, "CODE - Name"), ...]`` for modules in the DB.

        Used to constrain the "Module timeline" picker so only modules that
        actually exist can be chosen.
        """
        from education_system.systems.university.interfaces.gui.academics.course_management_gui.core._imports import (
            sqlite3, DEFAULT_DB_PATH,
        )
        items = []
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT module_code, COALESCE(module_name, '') FROM modules "
                    "WHERE module_code IS NOT NULL AND module_code != '' "
                    "ORDER BY module_code"
                )
                for code, name in cur.fetchall():
                    items.append((code, f"{code} - {name}" if name else str(code)))
        except Exception:
            logging.getLogger(__name__).exception("Could not load module choices")
        return items

    def _pick_db_code(self, title, prompt, items):
        """Modal picker constrained to DB-backed choices.

        ``items`` is ``[(code, display), ...]``. Returns the chosen *code* or
        ``None`` if cancelled / nothing available. The combo is read-only so a
        value not present in the database cannot be entered.
        """
        if not items:
            messagebox.showinfo(title, _("course_management.messages.nothing_to_pick",
                                         default="No matching records exist in the database."))
            return None

        display_to_code = {display: code for code, display in items}
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.geometry("460x170")

        ttk.Label(dlg, text=prompt).pack(anchor=tk.W, padx=12, pady=(14, 4))
        var = tk.StringVar()
        combo = ttk.Combobox(dlg, textvariable=var, state="readonly",
                             values=[display for _code, display in items], width=56)
        combo.pack(padx=12, fill=tk.X)
        combo.current(0)
        combo.focus_set()

        result = {"code": None}

        def _confirm(_event=None):
            result["code"] = display_to_code.get(var.get())
            dlg.destroy()

        combo.bind("<Return>", _confirm)
        btns = ttk.Frame(dlg)
        btns.pack(pady=14)
        ttk.Button(btns, text=_("common.ok", default="OK"),
                   command=_confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text=_("common.cancel", default="Cancel"),
                   command=dlg.destroy).pack(side=tk.LEFT, padx=5)

        dlg.wait_window()
        return result["code"]

    def create_menu(self):
        """Create the main menu bar with role-based access"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        is_admin = self.is_admin()
        is_staff = self.is_staff()
        is_student = self.is_student()

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("course_management.menu.file"), menu=file_menu)

        # Admin and Staff can import/export
        if is_admin or is_staff:
            self._bind_shortcut(file_menu, _("course_management.menu.import_csv"),
                                self.show_import_csv,
                                accelerator="Ctrl+I", sequence="<Control-i>")
            self._bind_shortcut(file_menu, _("course_management.menu.export_csv"),
                                self.show_export_csv,
                                accelerator="Ctrl+E", sequence="<Control-e>")
            self._bind_shortcut(file_menu,
                                _("course_management.menu.export_pdf", default="Export to PDF"),
                                self.show_export_pdf,
                                accelerator="Ctrl+P", sequence="<Control-p>")
            file_menu.add_separator()

        # Admin only - Database backup
        if is_admin:
            file_menu.add_command(label=_("course_management.menu.database_backup"), command=self.backup_database)
            file_menu.add_separator()

        self._bind_shortcut(file_menu, _("common.exit"), self.root.quit,
                            accelerator="Ctrl+Q", sequence="<Control-q>")

        # Course menu
        course_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("course_management.menu.courses"), menu=course_menu)

        # Admin and Staff can create courses
        if is_admin or is_staff:
            self._bind_shortcut(course_menu, _("course_management.menu.create_course"),
                                self.show_create_course,
                                accelerator="Ctrl+N", sequence="<Control-n>")

        # Everyone can view and search
        self._bind_shortcut(course_menu, _("course_management.menu.view_all_courses"),
                            self.refresh_course_list,
                            accelerator="F5", sequence="<F5>")
        self._bind_shortcut(course_menu, _("course_management.menu.search_courses"),
                            self.show_search_dialog,
                            accelerator="Ctrl+F", sequence="<Control-f>")
        course_menu.add_command(
            label=_("course_management.menu.browse_catalog", default="Browse Catalog"),
            command=self.show_course_catalog,
        )
        course_menu.add_command(
            label=_("course_management.menu.discussion_forums", default="Discussion Forums"),
            command=self.show_course_forums,
        )

        # Cross-domain: surface risk-register entries linked to a
        # course code via risk_bus.list_risks_for("course:CS-BSC").
        def _show_course_risks():
            from education_system.systems.university.services.bus.risks_panel import (
                show_risks_for,
            )
            # Constrain selection to courses that actually exist in the DB.
            labels, mapping = self._ext_course_choices()
            items = [(mapping[label], label) for label in labels]
            cc = self._pick_db_code("Course risks", "Course:", items)
            if not cc:
                return
            show_risks_for(self.root, f"course:{cc.strip()}",
                           title=f"Risks for {cc}")
        course_menu.add_command(
            label="View course risks",
            command=_show_course_risks,
        )

        # Admin and Staff can manage prerequisites
        if is_admin or is_staff:
            course_menu.add_separator()
            course_menu.add_command(label=_("course_management.menu.manage_prerequisites"), command=self.show_prerequisites_window)
            course_menu.add_command(label=_("course_management.menu.remove_prerequisite"), command=self.show_remove_prerequisite)
        # Chain viewer is read-only — useful for everyone
        course_menu.add_command(
            label=_("course_management.menu.prereq_chain", default="Prerequisite Chain"),
            command=self.show_prerequisite_chain,
        )

        # Everyone can find alternatives
        course_menu.add_command(label=_("course_management.menu.find_alternatives"), command=self.find_alternative_courses)

        # Admin and Staff can manage status
        if is_admin or is_staff:
            course_menu.add_command(label=_("course_management.menu.manage_status"), command=self.show_manage_status)

        # Scheduling menu - Admin and Staff only
        if is_admin or is_staff:
            schedule_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("course_management.menu.scheduling"), menu=schedule_menu)
            schedule_menu.add_command(label=_("course_management.menu.create_schedule"), command=self.show_create_schedule)
            schedule_menu.add_command(label=_("course_management.menu.update_schedule"), command=self.show_update_schedule)
            schedule_menu.add_command(label=_("course_management.menu.view_schedules"), command=self.show_view_schedules)
            schedule_menu.add_separator()
            schedule_menu.add_command(
                label=_("course_management.menu.conflict_report", default="Conflict Report"),
                command=self.show_schedule_conflict_report,
            )
        elif is_student:
            # Students can only view schedules
            schedule_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("course_management.menu.scheduling"), menu=schedule_menu)
            schedule_menu.add_command(label=_("course_management.menu.view_schedules"), command=self.show_view_schedules)

        # Enrollment menu - Admin and Staff only
        if is_admin or is_staff:
            enrollment_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("course_management.menu.enrollment"), menu=enrollment_menu)
            enrollment_menu.add_command(label=_("course_management.menu.manage_waitlists"), command=self.show_add_waitlist)
            enrollment_menu.add_command(label=_("course_management.menu.process_waitlists"), command=self.show_process_waitlist)
            enrollment_menu.add_command(label=_("course_management.menu.view_waitlists"), command=self.show_view_waitlists)
        elif is_student:
            # Students can only view waitlists
            enrollment_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("course_management.menu.enrollment"), menu=enrollment_menu)
            enrollment_menu.add_command(label=_("course_management.menu.view_waitlists"), command=self.show_view_waitlists)

        # Analytics menu
        analytics_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("course_management.menu.analytics"), menu=analytics_menu)

        # Admin and Staff get full analytics
        if is_admin or is_staff:
            analytics_menu.add_command(label=_("course_management.menu.course_analytics"), command=self.show_analytics)
            analytics_menu.add_command(label=_("course_management.menu.enrollment_report"), command=self.show_enrollment_report)
            analytics_menu.add_command(label=_("course_management.menu.department_statistics"), command=self.show_department_stats)
            analytics_menu.add_command(label=_("course_management.menu.course_history"), command=self.show_course_history)
            analytics_menu.add_command(label=_("course_management.menu.detailed_analytics"), command=self.show_course_analytics_detailed)
        elif is_student:
            # Students get limited analytics
            analytics_menu.add_command(label=_("course_management.menu.course_analytics"), command=self.show_analytics)
            analytics_menu.add_command(label=_("course_management.menu.course_history"), command=self.show_course_history)

        # Tools menu - Admin and Staff only
        if is_admin or is_staff:
            tools_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("course_management.menu.tools"), menu=tools_menu)

            # Admin only - bulk operations
            if is_admin:
                tools_menu.add_command(label=_("course_management.menu.bulk_update"), command=self.show_bulk_update)
                tools_menu.add_command(label=_("course_management.menu.system_maintenance"), command=self.show_system_maintenance)

            tools_menu.add_command(label=_("course_management.menu.course_recommendations"), command=self.show_recommend_courses)
            tools_menu.add_separator()
            self._bind_shortcut(tools_menu, _("course_management.menu.advanced_search"),
                                self.show_advanced_search,
                                accelerator="Ctrl+Shift+F",
                                sequence="<Control-Shift-F>")

            # Admin only - data validation
            if is_admin:
                tools_menu.add_command(label=_("course_management.menu.data_validation"), command=self.show_data_validation)
                self._bind_shortcut(tools_menu,
                                    _("course_management.menu.audit_log_viewer", default="Audit Log Viewer"),
                                    self.show_audit_log_viewer,
                                    accelerator="Ctrl+L",
                                    sequence="<Control-l>")

            tools_menu.add_separator()
            tools_menu.add_command(
                label=_("course_management.menu.course_health", default="Course Health Dashboard"),
                command=self.show_course_health,
            )
            tools_menu.add_command(
                label=_("course_management.menu.ai_integrity_alerts", default="AI Integrity Alerts"),
                command=self.show_ai_integrity_alerts,
            )
            tools_menu.add_command(
                label=_("course_management.menu.evaluation_templates", default="Evaluation Templates"),
                command=self.show_evaluation_templates,
            )

        # Help menu - available to everyone
        # Open — cross-launch sibling academic GUIs in their own Toplevels.
        from education_system.systems.university.interfaces.gui.academics._cross_launchers import (
            open_exam_gui, open_grade_gui, open_module_gui,
        )
        open_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Open", menu=open_menu)
        open_menu.add_command(
            label="Exam Scheduler",
            command=lambda: open_exam_gui(self.root, getattr(self, "auth", None)),
        )
        open_menu.add_command(
            label="Grade Tracking",
            command=lambda: open_grade_gui(self.root, getattr(self, "auth", None)),
        )
        open_menu.add_command(
            label="Module Scheduling",
            command=lambda: open_module_gui(self.root, getattr(self, "auth", None)),
        )

        # Cross-Domain — conflicts / workload / at-risk / timeline
        from education_system.systems.university.interfaces.gui.academics._cross_dialogs import (
            show_conflicts_dialog, show_instructor_workload_dialog,
            show_at_risk_dialog, show_module_timeline_dialog,
        )
        cross_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Cross-Domain", menu=cross_menu)

        def _show_conflicts_for_course():
            # Constrain selection to courses that actually exist in the DB.
            labels, mapping = self._ext_course_choices()
            items = [(mapping[label], label) for label in labels]
            code = self._pick_db_code("Conflicts", "Course:", items)
            if code:
                show_conflicts_dialog(self.root, course_code=code)

        cross_menu.add_command(
            label="Show conflicts for course…",
            command=_show_conflicts_for_course,
        )
        cross_menu.add_command(
            label="Instructor workload…",
            command=lambda: show_instructor_workload_dialog(self.root),
        )
        cross_menu.add_command(
            label="At-risk students (unified)…",
            command=lambda: show_at_risk_dialog(self.root),
        )
        def _show_module_timeline():
            # Constrain selection to modules that actually exist in the DB.
            code = self._pick_db_code("Module timeline", "Module:",
                                      self._db_module_choices())
            if code:
                show_module_timeline_dialog(self.root, code)

        cross_menu.add_command(
            label="Module timeline…",
            command=_show_module_timeline,
        )

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("course_management.menu.help"), menu=help_menu)
        help_menu.add_command(label=_("course_management.menu.about"), command=self.show_about)
        help_menu.add_command(label=_("course_management.menu.user_guide"), command=self.show_help)

    # --- Pagination helpers (state lives on `self` so refresh/filter can read it) ---

    def _is_filter_active(self) -> bool:
        """True when the user has typed a search term or chosen a non-'All' filter."""
        try:
            all_label = _("common.all")
            return bool(
                (self.search_var.get() or "").strip()
                or (self.dept_filter.get() and self.dept_filter.get() not in ("All", all_label))
                or (self.status_filter.get() and self.status_filter.get() not in ("All", all_label))
            )
        except (AttributeError, tk.TclError):
            return False

    def _reload_current_view(self):
        if self._is_filter_active():
            self.filter_courses()
        else:
            self.refresh_course_list()

    def _on_page_size_change(self):
        try:
            new_size = max(1, int(self._page_size_var.get()))
        except ValueError:
            return
        self._page_size = new_size
        self._page = 0
        self._reload_current_view()

    def page_jump(self, where: str):
        last_page = max(0, (self._page_total - 1) // max(1, self._page_size))
        if where == "first":
            self._page = 0
        elif where == "prev":
            self._page = max(0, self._page - 1)
        elif where == "next":
            self._page = min(last_page, self._page + 1)
        elif where == "last":
            self._page = last_page
        self._reload_current_view()

    def _update_pager_label(self):
        if not hasattr(self, "_page_label_var"):
            return
        if self._page_total <= 0:
            self._page_label_var.set("Page 0 of 0")
            return
        total_pages = max(1, (self._page_total + self._page_size - 1) // self._page_size)
        if self._page >= total_pages:
            self._page = total_pages - 1
        self._page_label_var.set(
            f"Page {self._page + 1} of {total_pages}  ({self._page_total} total)")

    def create_main_interface(self):
        """Create the main interface with tabs"""
        # Create toolbar frame at the top
        toolbar_frame = ttk.Frame(self.root)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        # Return to Main Menu button
        home_button = ttk.Button(toolbar_frame, text=_("course_management.buttons.return_to_main_menu"),
                                command=self.return_to_main_menu)
        home_button.pack(side=tk.LEFT, padx=5)

        # Launch CLI button
        ttk.Button(toolbar_frame,
                   text=_("course_management.buttons.switch_to_cli", default="Switch to CLI"),
                   command=self.open_course_management_cli
                   ).pack(side=tk.LEFT, padx=5)

        # Ensure the curriculum-extension schema exists before any tab that
        # reads from it is built. Defensive: failure here disables the new
        # tabs but must not break the rest of the GUI.
        try:
            if hasattr(self, "_ensure_extension_schema"):
                self._ensure_extension_schema()
        except Exception:
            logging.getLogger(__name__).exception(
                "Failed to ensure curriculum-extension schema")

        # Navigation: a scrollable sidebar of section buttons instead of a
        # horizontal tab strip (cleaner, and every section name is fully
        # visible). SidebarNotebook is API-compatible with ttk.Notebook, so all
        # the create_*_tab builders below work unchanged.
        from education_system.systems.university.interfaces.gui.academics.course_management_gui.core.sidebar_notebook import (
            SidebarNotebook,
        )
        self.notebook = SidebarNotebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Course List Tab
        self.create_course_list_tab()

        # Course Details Tab
        self.create_course_details_tab()

        # Analytics Tab
        self.create_analytics_tab()

        # Instructors Tab
        self.create_instructors_tab()

        # LMS Tab (embedded)
        self.create_lms_tab()

        # Degree Audit Tab (embedded)
        self.create_degree_audit_tab()

        # Course Evaluation Tab (embedded)
        self.create_course_eval_tab()

        # ---- Curriculum extension tabs -------------------------------
        # Each is independently guarded so one failing tab cannot prevent
        # the others (or the rest of the GUI) from loading.
        for builder_name in ("create_sections_tab", "create_requisites_tab",
                              "create_materials_tab", "create_outcomes_tab",
                              "create_approvals_tab", "create_timetable_tab",
                              "create_rollover_tab", "create_crosslisting_tab",
                              "create_grading_tab", "create_waitlist_rules_tab",
                              "create_course_module_links_tab"):
            builder = getattr(self, builder_name, None)
            if builder is None:
                continue
            try:
                builder()
            except Exception:
                logging.getLogger(__name__).exception(
                    "Failed to build curriculum tab via %s", builder_name)

        # Course Planning Tab (embedded)
        self._create_course_planning_tab()

    def _create_course_planning_tab(self):
        """Add a placeholder Course Planning tab that initializes on first click."""
        self._course_planning_placeholder = ttk.Frame(self.notebook)
        self.notebook.add(self._course_planning_placeholder, text="Course Planning")
        self._course_planning_loaded = False

        def _on_tab_changed(event):
            if self._course_planning_loaded:
                return
            selected = self.notebook.select()
            if selected == str(self._course_planning_placeholder):
                self._course_planning_loaded = True
                # Remove placeholder and load the real tab
                self.notebook.forget(self._course_planning_placeholder)
                try:
                    from education_system.systems.university.interfaces.gui.academics.course_management_gui.course_planning_gui import CoursePlanningGUI
                    CoursePlanningGUI(root=self.root, auth=self.auth, parent_notebook=self.notebook)
                    # Select the newly added tab
                    self.notebook.select(self.notebook.index("end") - 1)
                except Exception as e:
                    tab = ttk.Frame(self.notebook)
                    self.notebook.add(tab, text="Course Planning")
                    ttk.Label(tab, text=f"Course Planning could not be loaded: {e}",
                              font=("Arial", 12)).pack(padx=20, pady=20)
                    self.notebook.select(self.notebook.index("end") - 1)

        self.notebook.bind("<<NotebookTabChanged>>", _on_tab_changed, add="+")

    def open_course_management_cli(self):
        """Launch the course management CLI in a terminal."""
        if not ORIGINAL_MODULE_AVAILABLE:
            messagebox.showwarning(_("common.error"), "Course management CLI is unavailable.")
            return

        try:
            # Hide GUI temporarily
            self.root.withdraw()

            # Launch CLI in a new thread
            def run_cli():
                try:
                    display_enhanced_course_menu(self.auth)
                except Exception as e:
                    logging.error(f"CLI mode error: {e}")
                finally:
                    # Show GUI again
                    self.root.after(0, self.root.deiconify)

            cli_thread = threading.Thread(target=run_cli, daemon=True)
            cli_thread.start()

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to launch CLI: {e}")
            self.root.deiconify()

    def create_course_list_tab(self):
        """Create the course list tab"""
        course_frame = ttk.Frame(self.notebook)
        self.notebook.add(course_frame, text=_("course_management.tabs.course_list"))

        # Search and filter frame
        search_frame = ttk.LabelFrame(course_frame, text=_("course_management.labels.search_filter"), padding=10)
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        # Search controls
        ttk.Label(search_frame, text=_("course_management.labels.search")).grid(row=0, column=0, sticky=tk.W)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.grid(row=0, column=1, padx=5)
        self.search_entry.bind('<KeyRelease>', self.on_search_change)

        ttk.Label(search_frame, text=_("course_management.labels.department")).grid(row=0, column=2, sticky=tk.W, padx=(20,0))
        self.dept_filter = ttk.Combobox(search_frame, width=15)
        self.dept_filter.grid(row=0, column=3, padx=5)
        self.dept_filter.bind('<<ComboboxSelected>>', self.on_filter_change)

        ttk.Label(search_frame, text=_("course_management.labels.status")).grid(row=0, column=4, sticky=tk.W, padx=(20,0))
        self.status_filter = ttk.Combobox(search_frame, values=[_("common.all"), _("common.active"), _("common.inactive"), _("common.archived"), _("common.cancelled")], width=10)
        self.status_filter.set(_("common.all"))
        self.status_filter.grid(row=0, column=5, padx=5)
        self.status_filter.bind('<<ComboboxSelected>>', self.on_filter_change)

        # Course list with treeview
        list_frame = ttk.Frame(course_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create treeview with scrollbar
        columns = (
            _("course_management.columns.id"),
            _("course_management.columns.code"),
            _("course_management.columns.name"),
            _("course_management.columns.department"),
            _("course_management.columns.level"),
            _("course_management.columns.credits"),
            _("course_management.columns.enrollment"),
            _("course_management.columns.status")
        )
        column_labels = {
            "ID": _("course_management.columns.id"),
            "Code": _("course_management.columns.code"),
            "Name": _("course_management.columns.name"),
            "Department": _("course_management.columns.department"),
            "Level": _("course_management.columns.level"),
            "Credits": _("course_management.columns.credits"),
            "Enrollment": _("course_management.columns.enrollment"),
            "Status": _("course_management.columns.status")
        }
        # selectmode='extended' enables Ctrl/Shift-click to multi-select
        # so the Delete button can act on a batch of courses.
        self.course_tree = ttk.Treeview(list_frame, columns=columns,
                                        show="headings", height=20,
                                        selectmode="extended")

        # Configure column headings and widths
        for col in columns:
            self.course_tree.heading(col, text=column_labels.get(col, col), command=lambda c=col: self.sort_treeview(c))
            if col == "ID":
                self.course_tree.column(col, width=50)
            elif col == "Code":
                self.course_tree.column(col, width=80)
            elif col == "Name":
                self.course_tree.column(col, width=250)
            elif col in ["Department", "Level"]:
                self.course_tree.column(col, width=100)
            elif col == "Credits":
                self.course_tree.column(col, width=70)
            elif col == "Enrollment":
                self.course_tree.column(col, width=100)
            elif col == "Status":
                self.course_tree.column(col, width=80)

        # Red overlay for courses whose modules have unresolved conflicts.
        self.course_tree.tag_configure('has_conflict', foreground='#c0392b')
        # Orange overlay for courses where total room capacity across
        # scheduled sessions falls short of current enrolment.
        self.course_tree.tag_configure('over_capacity', foreground='#d97706')

        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.course_tree.yview)
        self.course_tree.configure(yscrollcommand=scrollbar.set)

        # Pack treeview and scrollbar
        self.course_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click event
        self.course_tree.bind("<Double-1>", self.on_course_double_click)

        # Soft selection broadcast — sibling academic GUIs highlight the
        # same course without context-switching their tabs.
        def _publish_course_selection(_event=None):
            try:
                sel = self.course_tree.selection()
                if not sel:
                    return
                vals = self.course_tree.item(sel[0], 'values')
                if not vals or len(vals) < 2:
                    return
                code = vals[1]
                if isinstance(code, str) and code.startswith("⚠ "):
                    code = code[2:]
                from education_system.systems.university.services.bus.academic_state import (
                    set_current_selection,
                )
                set_current_selection(course_code=code, source="course_management")
            except Exception:
                pass

        self.course_tree.bind(
            "<<TreeviewSelect>>", _publish_course_selection, add="+",
        )

        # Pagination — keeps the treeview from loading the entire courses
        # table when it grows beyond a few hundred rows. State is set on
        # `self` so it persists across refresh / filter / page-change calls.
        if not hasattr(self, "_page"):
            self._page = 0
        if not hasattr(self, "_page_size"):
            self._page_size = 50
        if not hasattr(self, "_page_total"):
            self._page_total = 0

        pager = ttk.Frame(course_frame)
        pager.pack(fill=tk.X, padx=5)
        ttk.Button(pager, text="<<", width=3,
                   command=lambda: self.page_jump("first")).pack(side=tk.LEFT)
        ttk.Button(pager, text="<", width=3,
                   command=lambda: self.page_jump("prev")).pack(side=tk.LEFT, padx=(2, 6))
        self._page_label_var = tk.StringVar(value="Page 1 of 1")
        ttk.Label(pager, textvariable=self._page_label_var, width=24,
                  anchor=tk.CENTER).pack(side=tk.LEFT)
        ttk.Button(pager, text=">", width=3,
                   command=lambda: self.page_jump("next")).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Button(pager, text=">>", width=3,
                   command=lambda: self.page_jump("last")).pack(side=tk.LEFT)
        ttk.Label(pager, text="  Rows per page:").pack(side=tk.LEFT, padx=(15, 2))
        self._page_size_var = tk.StringVar(value=str(self._page_size))
        page_size_combo = ttk.Combobox(pager, textvariable=self._page_size_var,
                                       values=["25", "50", "100", "250", "500"],
                                       width=5, state="readonly")
        page_size_combo.pack(side=tk.LEFT)
        page_size_combo.bind("<<ComboboxSelected>>",
                             lambda _e: self._on_page_size_change())

        # Buttons frame - Role-based access
        buttons_frame = ttk.Frame(course_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)

        is_admin = self.is_admin()
        is_staff = self.is_staff()

        # Admin and Staff can create courses
        if is_admin or is_staff:
            ttk.Button(buttons_frame, text=_("course_management.buttons.create_course"), command=self.show_create_course).pack(side=tk.LEFT, padx=5)

        # Admin and Staff can edit courses
        if is_admin or is_staff:
            ttk.Button(buttons_frame, text=_("course_management.buttons.edit_course"), command=self.edit_selected_course).pack(side=tk.LEFT, padx=5)

        # Only Admin can delete courses
        if is_admin:
            ttk.Button(buttons_frame, text=_("course_management.buttons.delete_course"), command=self.delete_selected_course).pack(side=tk.LEFT, padx=5)

        # Everyone can refresh
        ttk.Button(buttons_frame, text=_("common.refresh"), command=self.refresh_course_list).pack(side=tk.LEFT, padx=5)

        # Load initial data
        self.refresh_course_list()
        self.load_filter_options()

    # --- Course details tab palette (flat-UI, matches the rest of the GUI) ---
    DETAIL_BG = "#eef1f4"      # page background behind the cards
    _C_HEADER = "#2c3e50"      # dark header banner
    _C_CARD = "#ffffff"        # card surface
    _C_ACCENT = "#3498db"      # section accent / stat numbers
    _C_LABEL = "#6b7280"       # muted field labels
    _C_VALUE = "#1f2933"       # field values
    _C_MUTED = "#95a5a6"       # timestamps / secondary text
    _DETAIL_FONT = "Segoe UI"  # Tk substitutes a sane default where absent

    def create_course_details_tab(self):
        """Create the course details tab (card-based, scrollable layout)."""
        details_frame = ttk.Frame(self.notebook)
        self.notebook.add(details_frame, text=_("course_management.tabs.course_details"))

        # Course selection frame
        selection_frame = ttk.LabelFrame(details_frame, text=_("course_management.labels.select_course"), padding=10)
        selection_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(selection_frame, text=_("course_management.labels.course")).pack(side=tk.LEFT)
        self.course_selector = ttk.Combobox(selection_frame, width=50, state="readonly")
        self.course_selector.pack(side=tk.LEFT, padx=5)
        self.course_selector.bind('<<ComboboxSelected>>', self.on_course_select)

        # Scrollable details area. ttk has no native scrollable frame, so the
        # cards live on a Canvas window that stretches to the canvas width.
        outer = ttk.Frame(details_frame)
        outer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0, bg=self.DETAIL_BG)
        vbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.details_container = tk.Frame(canvas, bg=self.DETAIL_BG)
        win = canvas.create_window((0, 0), window=self.details_container, anchor="nw")

        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        self.details_container.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Scroll with the wheel only while the pointer is over this area, so it
        # doesn't fight the rest of the notebook.
        def _wheel(event):
            delta = -1 * (event.delta // 120) if event.delta else (-1 if event.num == 4 else 1)
            canvas.yview_scroll(delta, "units")
        canvas.bind("<Enter>", lambda e: (
            canvas.bind_all("<MouseWheel>", _wheel),
            canvas.bind_all("<Button-4>", _wheel),
            canvas.bind_all("<Button-5>", _wheel),
        ))
        canvas.bind("<Leave>", lambda e: (
            canvas.unbind_all("<MouseWheel>"),
            canvas.unbind_all("<Button-4>"),
            canvas.unbind_all("<Button-5>"),
        ))

        # Placeholder shown until a course is picked.
        self._details_placeholder()

        # Load course options
        self.load_course_selector_options()

    # =================================================================
    # Course details rendering (card layout)
    # =================================================================

    def _clear_details(self):
        for child in self.details_container.winfo_children():
            child.destroy()

    def _details_placeholder(self):
        """Friendly empty-state before a course is selected."""
        self._clear_details()
        box = tk.Frame(self.details_container, bg=self.DETAIL_BG)
        box.pack(fill=tk.BOTH, expand=True, pady=60)
        tk.Label(
            box, text="📘", font=(self._DETAIL_FONT, 34), bg=self.DETAIL_BG, fg=self._C_MUTED
        ).pack()
        tk.Label(
            box,
            text=_("course_management.labels.select_course"),
            font=(self._DETAIL_FONT, 12), bg=self.DETAIL_BG, fg=self._C_MUTED,
        ).pack(pady=(6, 0))

    def _detail_card(self, title=None, accent=None, parent=None):
        """Create a white rounded-look card and return its inner body frame."""
        parent = parent if parent is not None else self.details_container
        shell = tk.Frame(parent, bg=self._C_CARD,
                         highlightbackground="#e5e7eb", highlightthickness=1)
        shell.pack(fill=tk.X, padx=6, pady=6)
        if title:
            bar = tk.Frame(shell, bg=self._C_CARD)
            bar.pack(fill=tk.X, padx=16, pady=(12, 0))
            tk.Frame(bar, bg=accent or self._C_ACCENT, width=4, height=16).pack(side=tk.LEFT, padx=(0, 8))
            tk.Label(
                bar, text=title, font=(self._DETAIL_FONT, 11, "bold"),
                bg=self._C_CARD, fg=self._C_HEADER,
            ).pack(side=tk.LEFT)
        body = tk.Frame(shell, bg=self._C_CARD)
        body.pack(fill=tk.X, padx=16, pady=12)
        return body

    def _kv_grid(self, body, pairs, cols=2):
        """Lay label/value pairs out in a tidy grid inside a card body.

        Uses its own packed sub-frame so it can sit alongside pack-managed
        siblings (e.g. a fill bar) in the same card without a geometry clash.
        """
        grid = tk.Frame(body, bg=self._C_CARD)
        grid.pack(fill=tk.X, pady=(6, 0) if body.winfo_children() else 0)
        for c in range(cols):
            grid.columnconfigure(c * 2 + 1, weight=1, uniform="val")
        for idx, (label, value) in enumerate(pairs):
            r, base = divmod(idx, cols)
            base *= 2
            tk.Label(
                grid, text=label, font=(self._DETAIL_FONT, 9),
                bg=self._C_CARD, fg=self._C_LABEL, anchor="w",
            ).grid(row=r, column=base, sticky="w", padx=(0, 8), pady=4)
            tk.Label(
                grid, text=str(value), font=(self._DETAIL_FONT, 10, "bold"),
                bg=self._C_CARD, fg=self._C_VALUE, anchor="w", justify="left",
            ).grid(row=r, column=base + 1, sticky="w", padx=(0, 24), pady=4)

    def _text_block(self, title, text, accent=None, parent=None):
        body = self._detail_card(title, accent=accent, parent=parent)
        tk.Label(
            body, text=text, font=(self._DETAIL_FONT, 10),
            bg=self._C_CARD, fg=self._C_VALUE, anchor="w", justify="left",
            wraplength=980,
        ).pack(fill=tk.X)

    # ----- Reusable building blocks shared with the analytics reports -----

    def _scrollable_area(self, parent, bg=None):
        """Return (inner_frame) hosted on a scrollable canvas inside ``parent``.

        The inner frame stretches to the canvas width and scrolls with the
        wheel while the pointer is over it. Used by both the course-details
        tab and the analytics report windows.
        """
        bg = bg or self.DETAIL_BG
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0, bg=bg)
        vbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=bg)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _wheel(event):
            delta = -1 * (event.delta // 120) if event.delta else (-1 if event.num == 4 else 1)
            canvas.yview_scroll(delta, "units")
        canvas.bind("<Enter>", lambda e: (
            canvas.bind_all("<MouseWheel>", _wheel),
            canvas.bind_all("<Button-4>", _wheel),
            canvas.bind_all("<Button-5>", _wheel),
        ))
        canvas.bind("<Leave>", lambda e: (
            canvas.unbind_all("<MouseWheel>"),
            canvas.unbind_all("<Button-4>"),
            canvas.unbind_all("<Button-5>"),
        ))
        return inner

    def _report_header(self, parent, title, subtitle=None):
        """Dark banner used at the top of the analytics report windows."""
        header = tk.Frame(parent, bg=self._C_HEADER)
        header.pack(fill=tk.X, padx=6, pady=(6, 0))
        tk.Label(
            header, text=title, font=(self._DETAIL_FONT, 16, "bold"),
            bg=self._C_HEADER, fg="white", anchor="w",
        ).pack(anchor="w", padx=18, pady=(14, 0 if subtitle else 14))
        if subtitle:
            tk.Label(
                header, text=subtitle, font=(self._DETAIL_FONT, 10),
                bg=self._C_HEADER, fg="#bdc3c7", anchor="w",
            ).pack(anchor="w", padx=18, pady=(2, 12))

    def _stat_strip(self, parent, items, accent=None):
        """Row of headline number cards. ``items`` is a list of (value, label)."""
        accent = accent or self._C_ACCENT
        strip = tk.Frame(parent, bg=self.DETAIL_BG)
        strip.pack(fill=tk.X, padx=2, pady=(2, 0))
        for c in range(len(items)):
            strip.columnconfigure(c, weight=1, uniform="stat")
        for c, (num, lab) in enumerate(items):
            cell = tk.Frame(strip, bg=self._C_CARD, highlightbackground="#e5e7eb", highlightthickness=1)
            cell.grid(row=0, column=c, sticky="ew", padx=4, pady=6)
            tk.Label(cell, text=str(num), font=(self._DETAIL_FONT, 16, "bold"),
                     bg=self._C_CARD, fg=accent).pack(pady=(10, 0))
            tk.Label(cell, text=lab, font=(self._DETAIL_FONT, 9),
                     bg=self._C_CARD, fg=self._C_LABEL).pack(pady=(0, 10))
        return strip

    def _fill_bar(self, parent, percent, label=None):
        """A labelled horizontal fill-rate bar, colour-coded by utilisation."""
        pct = max(0.0, min(100.0, percent))
        colour = "#2ecc71" if pct < 75 else "#f39c12" if pct < 95 else "#e74c3c"
        wrap = tk.Frame(parent, bg=self._C_CARD)
        wrap.pack(fill=tk.X, pady=4)
        if label:
            tk.Label(wrap, text=label, font=(self._DETAIL_FONT, 9),
                     bg=self._C_CARD, fg=self._C_LABEL).pack(anchor="w")
        track = tk.Frame(wrap, bg="#e5e7eb", height=18)
        track.pack(fill=tk.X, pady=(2, 0))
        track.pack_propagate(False)
        fill = tk.Frame(track, bg=colour)
        fill.place(relwidth=pct / 100.0, relheight=1.0)
        tk.Label(track, text=f"{pct:.1f}%", font=(self._DETAIL_FONT, 8, "bold"),
                 bg="#e5e7eb", fg=self._C_HEADER).place(relx=1.0, x=-4, rely=0.5, anchor="e")
        return wrap

    def _ensure_report_tree_style(self):
        """Configure a tidy Treeview style for report tables (idempotent)."""
        if getattr(self, "_report_tree_styled", False):
            return
        style = ttk.Style()
        style.configure("Report.Treeview", rowheight=26, font=(self._DETAIL_FONT, 10),
                        background=self._C_CARD, fieldbackground=self._C_CARD)
        style.configure("Report.Treeview.Heading", font=(self._DETAIL_FONT, 10, "bold"))
        self._report_tree_styled = True

    def _report_table(self, parent, columns, rows, widths=None, anchors=None,
                      tag_colours=None, height=12):
        """Build a styled Treeview table inside a card and return it.

        ``columns`` -> list of headings. ``rows`` -> list of (values, tag).
        ``tag_colours`` -> {tag: foreground}. Zebra striping is applied on top.
        """
        self._ensure_report_tree_style()
        card = tk.Frame(parent, bg=self._C_CARD, highlightbackground="#e5e7eb", highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        holder = tk.Frame(card, bg=self._C_CARD)
        holder.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tree = ttk.Treeview(holder, columns=columns, show="headings",
                            style="Report.Treeview", height=min(height, max(3, len(rows))))
        widths = widths or {}
        anchors = anchors or {}
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=widths.get(col, 120), anchor=anchors.get(col, tk.W),
                        stretch=True)
        tree.tag_configure("_odd", background="#f7f9fb")
        tree.tag_configure("_even", background=self._C_CARD)
        for colour_tag, fg in (tag_colours or {}).items():
            tree.tag_configure(colour_tag, foreground=fg)
        for i, entry in enumerate(rows):
            values, extra_tag = entry if isinstance(entry, tuple) else (entry, None)
            tags = ["_odd" if i % 2 else "_even"]
            if extra_tag:
                tags.append(extra_tag)
            tree.insert("", tk.END, values=values, tags=tags)

        vsb = ttk.Scrollbar(holder, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def render_course_details(self, course):
        """Render a course row as presentable cards instead of raw text."""
        self._clear_details()

        def get(i, default="N/A"):
            return course[i] if len(course) > i and course[i] not in (None, "") else default

        def years(i):
            v = course[i] if len(course) > i else None
            return f"{v} years" if v not in (None, "") else "N/A"

        def money(i):
            v = course[i] if len(course) > i else None
            if isinstance(v, (int, float)):
                return f"£{v:,.2f}"
            return "N/A" if v in (None, "") else str(v)

        def yesno(i):
            if len(course) <= i:
                return "N/A"
            v = course[i]
            return "Yes" if bool(v) else "No" if v in (False, 0) else "N/A"

        def avail_spots():
            max_e = course[15] if len(course) > 15 else None
            cur_e = course[16] if len(course) > 16 else None
            if isinstance(max_e, (int, float)) and isinstance(cur_e, (int, float)):
                return max(0, max_e - cur_e)
            return "N/A"

        # ---- Header banner ----
        header = tk.Frame(self.details_container, bg=self._C_HEADER)
        header.pack(fill=tk.X, padx=6, pady=(6, 0))
        header.columnconfigure(0, weight=1)

        left = tk.Frame(header, bg=self._C_HEADER)
        left.grid(row=0, column=0, sticky="w", padx=18, pady=14)
        tk.Label(
            left, text=str(get(2)), font=(self._DETAIL_FONT, 17, "bold"),
            bg=self._C_HEADER, fg="white", anchor="w", justify="left",
        ).pack(anchor="w")
        subparts = [str(get(1))]
        if get(6) != "N/A":
            subparts.append(str(get(6)))
        if get(5) != "N/A":
            subparts.append(f"Level {get(5)}")
        tk.Label(
            left, text="   •   ".join(subparts), font=(self._DETAIL_FONT, 10),
            bg=self._C_HEADER, fg="#bdc3c7", anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        status = get(17)
        status_colors = {"active": "#2ecc71", "open": "#2ecc71", "inactive": "#e74c3c",
                         "closed": "#e74c3c", "archived": "#95a5a6"}
        badge_bg = status_colors.get(str(status).lower(), self._C_ACCENT) if status != "N/A" else self._C_MUTED
        badge = tk.Label(
            header, text=f"  {status}  ", font=(self._DETAIL_FONT, 9, "bold"),
            bg=badge_bg, fg="white",
        )
        badge.grid(row=0, column=1, sticky="e", padx=18)

        # ---- Stat strip ----
        stats = tk.Frame(self.details_container, bg=self.DETAIL_BG)
        stats.pack(fill=tk.X, padx=2, pady=(2, 0))
        stat_items = [
            (get(7), "Credit Hours"),
            (get(15), "Max Enrolment"),
            (get(16), "Current Enrolment"),
            (avail_spots(), "Available Spots"),
        ]
        for c in range(len(stat_items)):
            stats.columnconfigure(c, weight=1, uniform="stat")
        for c, (num, lab) in enumerate(stat_items):
            cell = tk.Frame(stats, bg=self._C_CARD, highlightbackground="#e5e7eb", highlightthickness=1)
            cell.grid(row=0, column=c, sticky="ew", padx=4, pady=6)
            tk.Label(
                cell, text=str(num), font=(self._DETAIL_FONT, 16, "bold"),
                bg=self._C_CARD, fg=self._C_ACCENT,
            ).pack(pady=(10, 0))
            tk.Label(
                cell, text=lab, font=(self._DETAIL_FONT, 9),
                bg=self._C_CARD, fg=self._C_LABEL,
            ).pack(pady=(0, 10))

        legacy = len(course) < 10

        # ---- Basic information ----
        basic = self._detail_card("Basic Information")
        basic_pairs = [
            ("Course ID", get(0)),
            ("Course Code", get(1)),
            ("Department", get(6)),
            ("Level", get(5)),
        ]
        if not legacy:
            basic_pairs += [("Course Type", get(18)), ("Status", get(17))]
        self._kv_grid(basic, basic_pairs)

        # ---- Description ----
        if get(3) != "N/A":
            self._text_block("Description", get(3), accent="#9b59b6")

        if not legacy:
            # ---- Academic details ----
            acad = self._detail_card("Academic Details", accent="#16a34a")
            self._kv_grid(acad, [
                ("Duration", years(4)),
                ("Credit Hours", get(7)),
                ("Contact Hours/Week", get(8)),
                ("Course Fee", money(12)),
                ("Lab Required", yesno(13)),
                ("Online Available", yesno(14)),
            ])

            # ---- Long-form academic content ----
            if get(9) != "N/A":
                self._text_block("Learning Outcomes", get(9), accent="#16a34a")
            if get(10) != "N/A":
                self._text_block("Assessment Methods", get(10), accent="#f39c12")
            if get(11) != "N/A":
                self._text_block("Required Textbooks", get(11), accent="#f39c12")

            # ---- Additional info ----
            extra_pairs = [p for p in [("Tags", get(19)), ("Availability", get(20))]
                           if p[1] != "N/A"]
            if extra_pairs:
                extra = self._detail_card("Additional Information", accent="#3498db")
                self._kv_grid(extra, extra_pairs)

            # ---- Timestamps (muted footer) ----
            foot = tk.Frame(self.details_container, bg=self.DETAIL_BG)
            foot.pack(fill=tk.X, padx=10, pady=(2, 12))
            tk.Label(
                foot,
                text=f"Created: {get(21)}      Last Updated: {get(22)}",
                font=(self._DETAIL_FONT, 8), bg=self.DETAIL_BG, fg=self._C_MUTED,
            ).pack(anchor="w")
        else:
            # Legacy schema exposes duration but none of the enhanced fields.
            self._kv_grid(self._detail_card("Academic Details", accent="#16a34a"),
                          [("Duration", years(4))])

        # Reset the scroll position to the top for the new course.
        self.details_container.update_idletasks()

    def create_analytics_tab(self):
        """Create the analytics tab with role-based access"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text=_("course_management.tabs.analytics"))

        is_admin = self.is_admin()
        is_staff = self.is_staff()

        # Analytics controls - Admin and Staff only
        if is_admin or is_staff:
            controls_frame = ttk.LabelFrame(analytics_frame, text=_("course_management.labels.analytics_controls"), padding=10)
            controls_frame.pack(fill=tk.X, padx=5, pady=5)

            ttk.Button(controls_frame, text=_("course_management.buttons.generate_course_analytics"), command=self.generate_analytics).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text=_("course_management.messages.open_in_new_window"), command=self.open_analytics_window).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text=_("course_management.buttons.enrollment_report"), command=self.show_enrollment_report).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text=_("course_management.buttons.department_stats"), command=self.show_department_stats).pack(side=tk.LEFT, padx=5)

        # Analytics display. Two stacked surfaces share this area: a
        # card/table dashboard (``analytics_container``) and the legacy
        # ScrolledText (``analytics_text``) still used for recommendations
        # and text-only output. Only one is shown at a time.
        holder = ttk.Frame(analytics_frame)
        holder.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._analytics_holder = holder
        self.analytics_container = self._scrollable_area(holder)
        self.analytics_text = ScrolledText(holder, wrap=tk.WORD, height=25)

        # Friendly empty-state until the dashboard is generated.
        tk.Label(
            self.analytics_container,
            text="📊", font=(self._DETAIL_FONT, 34), bg=self.DETAIL_BG, fg=self._C_MUTED,
        ).pack(pady=(60, 0))
        tk.Label(
            self.analytics_container,
            text=_("course_management.buttons.generate_course_analytics"),
            font=(self._DETAIL_FONT, 12), bg=self.DETAIL_BG, fg=self._C_MUTED,
        ).pack(pady=(6, 0))

    def _analytics_outer(self):
        """The scrollable canvas wrapper hosting ``analytics_container``."""
        return self.analytics_container.master.master

    def show_analytics_cards(self):
        """Reveal the card dashboard, hide the text surface."""
        self.analytics_text.pack_forget()
        outer = self._analytics_outer()
        if not outer.winfo_ismapped():
            outer.pack(fill=tk.BOTH, expand=True)

    def show_analytics_text(self):
        """Reveal the legacy text surface, hide the card dashboard."""
        self._analytics_outer().pack_forget()
        self.analytics_text.pack(fill=tk.BOTH, expand=True)

    def create_instructors_tab(self):
        """Create the instructors tab with role-based access"""
        instructors_frame = ttk.Frame(self.notebook)
        self.notebook.add(instructors_frame, text=_("course_management.tabs.instructors"))

        is_admin = self.is_admin()
        is_staff = self.is_staff()

        # Instructor controls - Admin and Staff only
        if is_admin or is_staff:
            controls_frame = ttk.LabelFrame(instructors_frame, text=_("course_management.labels.instructor_management"), padding=10)
            controls_frame.pack(fill=tk.X, padx=5, pady=5)

            # Admin only - Add instructor
            if is_admin:
                ttk.Button(controls_frame, text=_("course_management.buttons.add_instructor"), command=self.show_add_instructor).pack(side=tk.LEFT, padx=5)

            # Admin and Staff can view instructors
            ttk.Button(controls_frame, text=_("course_management.buttons.view_instructors"), command=self.refresh_instructor_list).pack(side=tk.LEFT, padx=5)

            # Admin only - Assign to course
            if is_admin:
                ttk.Button(controls_frame, text=_("course_management.buttons.assign_to_course"), command=self.show_assign_instructor).pack(side=tk.LEFT, padx=5)

        # Instructor list - displayed as a sortable table
        list_frame = ttk.LabelFrame(instructors_frame, text=_("course_management.tabs.instructors"), padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("id", "name", "email", "department", "specialization", "max_courses", "status")
        headings = {
            "id": "ID",
            "name": "Name",
            "email": "Email",
            "department": "Department",
            "specialization": "Specialization",
            "max_courses": "Max Courses",
            "status": "Status",
        }
        widths = {
            "id": 50,
            "name": 180,
            "email": 240,
            "department": 150,
            "specialization": 170,
            "max_courses": 90,
            "status": 90,
        }

        tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            tree.heading(col, text=headings[col])
            anchor = tk.CENTER if col in ("id", "max_courses", "status") else tk.W
            tree.column(col, width=widths[col], anchor=anchor, stretch=(col in ("name", "email", "specialization")))

        # Zebra striping for readability
        tree.tag_configure("oddrow", background="#f5f5f5")
        tree.tag_configure("evenrow", background="#ffffff")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.instructor_tree = tree

        # Double-click a row to open the instructor details / assignment window
        tree.bind("<Double-1>", self.on_instructor_double_click)

        # Status/count line beneath the table
        self.instructor_count_label = ttk.Label(instructors_frame, text="")
        self.instructor_count_label.pack(fill=tk.X, padx=5, pady=(0, 5))

    def create_academic_systems_tab(self):
        """Create the academic systems tab with LMS, Degree Audit, and Course Evaluation"""
        systems_frame = ttk.Frame(self.notebook)
        self.notebook.add(systems_frame, text=_("course_management.tabs.academic_systems"))

        # Title
        title_label = ttk.Label(systems_frame, text=_("course_management.labels.academic_management_systems"),
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=20)

        # Description
        desc_label = ttk.Label(systems_frame,
                              text=_("course_management.labels.academic_systems_description"),
                              wraplength=600, justify=tk.CENTER)
        desc_label.pack(pady=10)

        # Create scrollable canvas for systems
        canvas_frame = ttk.Frame(systems_frame)
        canvas_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        canvas = tk.Canvas(canvas_frame, bg='#f0f0f0', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Systems container inside canvas
        container = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=container, anchor='nw')

        # Configure canvas scrolling
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
            # Make the container width match the canvas width
            canvas.itemconfig(canvas_window, width=event.width - 20)

        canvas.bind('<Configure>', configure_scroll)
        container.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        canvas.bind_all('<MouseWheel>', on_mousewheel)
        canvas.bind_all('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
        canvas.bind_all('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))

        # Degree Audit System
        audit_frame = ttk.LabelFrame(container, text=_("course_management.labels.degree_audit"), padding=20)
        audit_frame.pack(fill=tk.X, pady=10)

        audit_desc = ttk.Label(audit_frame,
                              text=_("course_management.labels.degree_audit_description"),
                              wraplength=500)
        audit_desc.pack(pady=5)

        ttk.Button(audit_frame, text=_("course_management.buttons.launch_degree_audit"),
                  command=self.show_degree_audit_gui,
                  width=30).pack(pady=10)

        # Course Evaluation System
        eval_frame = ttk.LabelFrame(container, text=_("course_management.labels.course_evaluation"), padding=20)
        eval_frame.pack(fill=tk.X, pady=10)

        eval_desc = ttk.Label(eval_frame,
                             text=_("course_management.labels.course_evaluation_description"),
                             wraplength=500)
        eval_desc.pack(pady=5)

        ttk.Button(eval_frame, text=_("course_management.buttons.launch_course_evaluation"),
                  command=self.show_course_evaluation_gui,
                  width=30).pack(pady=10)

        # Status message if systems not available
        if not ACADEMIC_SYSTEMS_AVAILABLE:
            warning_label = ttk.Label(container,
                                    text=_("course_management.messages.systems_not_available"),
                                    foreground="orange")
            warning_label.pack(pady=10)
