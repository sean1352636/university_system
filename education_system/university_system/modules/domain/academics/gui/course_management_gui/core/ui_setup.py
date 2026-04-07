from tkinter.scrolledtext import ScrolledText

from education_system.university_system.modules.domain.academics.gui.course_management_gui.core._imports import (
    _, logging, messagebox, threading, tk, ttk, Path,
    ORIGINAL_MODULE_AVAILABLE, display_enhanced_course_menu,
    ACADEMIC_SYSTEMS_AVAILABLE,
)


class UISetupMixin:
    """Menu bar, toolbar, and tab creation."""

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
            file_menu.add_command(label=_("course_management.menu.import_csv"), command=self.show_import_csv)
            file_menu.add_command(label=_("course_management.menu.export_csv"), command=self.show_export_csv)
            file_menu.add_separator()

        # Admin only - Database backup
        if is_admin:
            file_menu.add_command(label=_("course_management.menu.database_backup"), command=self.backup_database)
            file_menu.add_separator()

        file_menu.add_command(label=_("common.exit"), command=self.root.quit)

        # Course menu
        course_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("course_management.menu.courses"), menu=course_menu)

        # Admin and Staff can create courses
        if is_admin or is_staff:
            course_menu.add_command(label=_("course_management.menu.create_course"), command=self.show_create_course)

        # Everyone can view and search
        course_menu.add_command(label=_("course_management.menu.view_all_courses"), command=self.refresh_course_list)
        course_menu.add_command(label=_("course_management.menu.search_courses"), command=self.show_search_dialog)

        # Admin and Staff can manage prerequisites
        if is_admin or is_staff:
            course_menu.add_separator()
            course_menu.add_command(label=_("course_management.menu.manage_prerequisites"), command=self.show_prerequisites_window)
            course_menu.add_command(label=_("course_management.menu.remove_prerequisite"), command=self.show_remove_prerequisite)

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
            tools_menu.add_command(label=_("course_management.menu.advanced_search"), command=self.show_advanced_search)

            # Admin only - data validation
            if is_admin:
                tools_menu.add_command(label=_("course_management.menu.data_validation"), command=self.show_data_validation)

        # Help menu - available to everyone
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("course_management.menu.help"), menu=help_menu)
        help_menu.add_command(label=_("course_management.menu.about"), command=self.show_about)
        help_menu.add_command(label=_("course_management.menu.user_guide"), command=self.show_help)

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
        ttk.Button(toolbar_frame, text="Open CLI", command=self.open_course_management_cli).pack(side=tk.LEFT, padx=5)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
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
                    from education_system.university_system.modules.domain.academics.gui.course_management_gui.course_planning_gui import CoursePlanningGUI
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
        self.course_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)

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

        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.course_tree.yview)
        self.course_tree.configure(yscrollcommand=scrollbar.set)

        # Pack treeview and scrollbar
        self.course_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click event
        self.course_tree.bind("<Double-1>", self.on_course_double_click)

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

    def create_course_details_tab(self):
        """Create the course details tab"""
        details_frame = ttk.Frame(self.notebook)
        self.notebook.add(details_frame, text=_("course_management.tabs.course_details"))

        # Course selection frame
        selection_frame = ttk.LabelFrame(details_frame, text=_("course_management.labels.select_course"), padding=10)
        selection_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(selection_frame, text=_("course_management.labels.course")).pack(side=tk.LEFT)
        self.course_selector = ttk.Combobox(selection_frame, width=50)
        self.course_selector.pack(side=tk.LEFT, padx=5)
        self.course_selector.bind('<<ComboboxSelected>>', self.on_course_select)

        # Details display frame
        self.details_frame = ttk.LabelFrame(details_frame, text=_("course_management.labels.course_information"), padding=10)
        self.details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create scrolled text for details
        self.details_text = ScrolledText(self.details_frame, wrap=tk.WORD, height=20)
        self.details_text.pack(fill=tk.BOTH, expand=True)

        # Load course options
        self.load_course_selector_options()

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

        # Analytics display
        self.analytics_text = ScrolledText(analytics_frame, wrap=tk.WORD, height=25)
        self.analytics_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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

        # Instructor list
        self.instructor_text = ScrolledText(instructors_frame, wrap=tk.WORD, height=25)
        self.instructor_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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
