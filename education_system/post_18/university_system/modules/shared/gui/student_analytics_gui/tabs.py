"""Tab creation mixin for the Student Analytics GUI."""
from education_system.post_18.university_system.modules.shared.gui.student_analytics_gui._imports import tk, ttk, scrolledtext, _t, CONFIG


class TabsMixin:
    """Mixin providing all notebook tab creation methods."""

    def create_main_content(self):
        """Create the main content area with tabs and controls"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Analysis tabs
        self.create_basic_analytics_tab()
        self.create_performance_tab()
        self.create_advanced_tab()
        self.create_reports_tab()
        self.create_utilities_tab()
        self.create_output_tab()

    def _make_scrollable_canvas(self, tab):
        """Build a scrollable canvas inside *tab* and return the inner
        Frame the caller should pack widgets into.

        Same shape as 8.117.40 (Student Records) and 8.117.41 (System
        Administration): canvas + vertical + horizontal scrollbars on
        ``grid`` layout. Pre-8.117.42 each tab here used::

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        Two issues that fixes:
        1. Pack ordering — ``canvas`` with ``expand=True`` claimed
           the entire tab before the scrollbar got a chance, so the
           v-scrollbar rendered at zero width.
        2. No horizontal scrollbar at all — wider content got cut
           off on the right with no way to reach it.

        The inner frame's width is bound to the canvas width so
        left-aligned content stretches edge-to-edge instead of
        clinging to the left when there's spare horizontal space."""
        canvas = tk.Canvas(tab, highlightthickness=0)
        vsb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(tab, orient="horizontal", command=canvas.xview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all")),
        )

        window_id = canvas.create_window(
            (0, 0), window=scrollable_frame, anchor="nw")

        # Track canvas width — when the canvas is wider than the
        # natural inner content, stretch the inner frame to match
        # so widgets can fill_x to the right edge.
        canvas.bind(
            "<Configure>",
            lambda e, c=canvas, w=window_id, f=scrollable_frame:
                c.itemconfig(w, width=max(e.width, f.winfo_reqwidth())),
        )

        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)
        return scrollable_frame

    def create_basic_analytics_tab(self):
        """Create basic analytics tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("analytics.tab_basic", default="📊 Basic Analytics"))

        scrollable_frame = self._make_scrollable_canvas(tab)

        # Basic analytics buttons
        basic_analyses = [
            (_t("analytics.student_demographics", default="Student Demographics"), self.run_demographics,
             _t("analytics.student_demographics_desc", default="Analyze age, gender, course distribution and geographic data")),
            (_t("analytics.module_popularity", default="Module Popularity Analysis"), self.run_module_popularity,
             _t("analytics.module_popularity_desc", default="Examine which modules are most popular and successful")),
            (_t("analytics.course_enrollment", default="Course Enrollment Statistics"), self.run_course_enrollments,
             _t("analytics.course_enrollment_desc", default="Review enrollment patterns across different courses")),
            (_t("analytics.registration_timeline", default="Registration Timeline"), self.run_registration_timeline,
             _t("analytics.registration_timeline_desc", default="Track registration patterns over time")),
            (_t("analytics.grade_distribution", default="Grade Distribution Analysis"), self.run_grade_distribution,
             _t("analytics.grade_distribution_desc", default="Analyze grade patterns and academic performance distribution")),
        ]

        for i, (title, command, description) in enumerate(basic_analyses):
            self.create_analysis_button(scrollable_frame, title, command, description, i)

    def create_performance_tab(self):
        """Create performance analytics tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("analytics.tab_performance", default="📈 Performance"))

        scrollable_frame = self._make_scrollable_canvas(tab)

        performance_analyses = [
            (_t("analytics.grade_distribution", default="Grade Distribution Analysis"), self.run_grade_distribution,
             _t("analytics.grade_distribution_perf_desc", default="Analyze grade patterns and academic performance")),
            (_t("analytics.academic_risk", default="Academic Risk Assessment"), self.run_academic_risk,
             _t("analytics.academic_risk_desc", default="Identify students at risk of academic failure")),
            (_t("analytics.module_difficulty", default="Module Difficulty Analysis"), self.run_module_difficulty,
             _t("analytics.module_difficulty_desc", default="Evaluate module difficulty and success rates")),
            (_t("analytics.performance_trends", default="Student Performance Trends"), self.run_performance_trends,
             _t("analytics.performance_trends_desc", default="Track performance changes over time"))
        ]

        for i, (title, command, description) in enumerate(performance_analyses):
            self.create_analysis_button(scrollable_frame, title, command, description, i)

    def create_advanced_tab(self):
        """Create advanced analytics tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("analytics.tab_advanced", default="🔬 Advanced"))

        scrollable_frame = self._make_scrollable_canvas(tab)

        advanced_analyses = [
            (_t("analytics.correlation_analysis", default="Correlation Analysis"), self.run_correlations,
             _t("analytics.correlation_desc", default="Examine relationships between different variables")),
            (_t("analytics.cohort_analysis", default="Cohort Analysis"), self.run_cohorts,
             _t("analytics.cohort_desc", default="Analyze student cohorts and retention patterns")),
            (_t("analytics.engagement_scoring", default="Engagement Scoring"), self.run_engagement,
             _t("analytics.engagement_desc", default="Evaluate student engagement levels and patterns")),
            (_t("analytics.predictive_analytics", default="Predictive Analytics"), self.run_predictive,
             _t("analytics.predictive_desc", default="Use machine learning for predictive insights"))
        ]

        for i, (title, command, description) in enumerate(advanced_analyses):
            self.create_analysis_button(scrollable_frame, title, command, description, i)

    def create_reports_tab(self):
        """Create reporting and export tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("analytics.tab_reports", default="📋 Reports"))

        # Create two columns
        left_frame = ttk.Frame(tab)
        left_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        right_frame = ttk.Frame(tab)
        right_frame.pack(side='right', fill='both', expand=True, padx=5, pady=5)

        # Report generation
        ttk.Label(left_frame, text=_t("analytics.report_generation", default="Report Generation"), style='Heading.TLabel').pack(pady=5)

        report_buttons = [
            (_t("analytics.generate_complete_report", default="Generate Complete Report"), self.run_complete_report),
            (_t("analytics.custom_report_builder", default="Custom Report Builder"), self.run_custom_report),
            (_t("common.return_to_main_menu", default="🏠 Return to Main Menu"), self.return_to_main_menu)
        ]

        for title, command in report_buttons:
            ttk.Button(left_frame, text=title, command=command,
                      style='Action.TButton').pack(fill='x', pady=2)

        # Export options
        ttk.Label(right_frame, text=_t("analytics.export_options", default="Export Options"), style='Heading.TLabel').pack(pady=5)

        export_buttons = [
            (_t("analytics.export_to_excel", default="Export to Excel"), lambda: self.run_export('excel')),
            (_t("analytics.export_to_csv", default="Export to CSV"), lambda: self.run_export('csv')),
            (_t("analytics.export_to_json", default="Export to JSON"), lambda: self.run_export('json')),
            (_t("analytics.statistical_summary", default="Statistical Summary"), lambda: self.run_export('summary'))
        ]

        for title, command in export_buttons:
            ttk.Button(right_frame, text=title, command=command,
                      style='Action.TButton').pack(fill='x', pady=2)

        # Filters frame
        filters_frame = ttk.LabelFrame(tab, text=_t("analytics.filters", default="Filters"), padding=10)
        filters_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(filters_frame, text=_t("analytics.advanced_filtering", default="Advanced Filtering"),
                  command=self.show_filters_dialog).pack(side='left', padx=5)
        ttk.Button(filters_frame, text=_t("analytics.clear_filters", default="Clear Filters"),
                  command=self.clear_filters).pack(side='left', padx=5)

        self.filter_status = ttk.Label(filters_frame, text=_t("analytics.no_filters_applied", default="No filters applied"))
        self.filter_status.pack(side='left', padx=10)

    def create_utilities_tab(self):
        """Create utilities tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("analytics.tab_utilities", default="🔧 Utilities"))

        # Create sections
        sections = [
            (_t("analytics.data_management", default="Data Management"), [
                (_t("analytics.data_quality_check", default="Data Quality Check"), self.run_data_quality),
                (_t("analytics.database_connection_test", default="Database Connection Test"), self.test_database),
            (_t("common.return_to_main_menu", default="🏠 Return to Main Menu"), self.return_to_main_menu)
        ]),
            (_t("analytics.configuration", default="Configuration"), [
                (_t("analytics.configuration_settings", default="Configuration Settings"), self.show_config_dialog),
                (_t("analytics.color_scheme_settings", default="Color Scheme Settings"), self.show_color_dialog),
            (_t("common.return_to_main_menu", default="🏠 Return to Main Menu"), self.return_to_main_menu)
        ]),
            (_t("analytics.help_about", default="Help & About"), [
                (_t("analytics.view_help", default="View Help Documentation"), self.show_help),
                (_t("analytics.about_app", default="About This Application"), self.show_about),
            (_t("common.return_to_main_menu", default="🏠 Return to Main Menu"), self.return_to_main_menu)
        ])
        ]

        for section_title, buttons in sections:
            frame = ttk.LabelFrame(tab, text=section_title, padding=10)
            frame.pack(fill='x', padx=10, pady=5)

            for title, command in buttons:
                ttk.Button(frame, text=title, command=command).pack(side='left', padx=5)

    def create_output_tab(self):
        """Create output/console tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("analytics.tab_output", default="📝 Output"))

        # Create output text area
        self.output_text = scrolledtext.ScrolledText(tab, wrap='word', height=30)
        self.output_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Control buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(button_frame, text=_t("analytics.clear_output", default="Clear Output"),
                  command=self.clear_output).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("analytics.save_output", default="Save Output"),
                  command=self.save_output).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("analytics.copy_to_clipboard", default="Copy to Clipboard"),
                  command=self.copy_output).pack(side='left', padx=5)

    def create_analysis_button(self, parent, title, command, description, row):
        """Create a styled analysis button with description"""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=10, pady=5)

        # Button
        btn = ttk.Button(frame, text=title, command=command,
                        style='Action.TButton', width=30)
        btn.pack(side='left', padx=5)

        # Description
        desc_label = ttk.Label(frame, text=description, foreground='gray')
        desc_label.pack(side='left', padx=10)
