"""Extracted demographic-reporting behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *

class AdvancedUiCommonMixin:
    def _setup_styles(self):
        """Setup ttk styles"""
        style = ttk.Style()
        style.configure('AdvReport.TFrame', padding=10)
        style.configure('AdvReportTitle.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('SectionTitle.TLabel', font=('Helvetica', 12, 'bold'))
        style.configure('Stat.TLabel', font=('Helvetica', 10))

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container with notebook for tabs
        main_frame = ttk.Frame(self.window, style='AdvReport.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            title_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.labels.advanced_demographic_report', default="Advanced Demographic Report"),
            style='AdvReportTitle.TLabel'
        ).pack(side=tk.LEFT)

        # Generate button in title area
        ttk.Button(
            title_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.buttons.generate_report', default="Generate Report"),
            command=self._generate_full_report
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            title_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.buttons.refresh_data', default="Refresh Data"),
            command=self._refresh_data
        ).pack(side=tk.RIGHT)

        # Notebook for different report views
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Tab 1: Overview Summary
        self.overview_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.overview_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.tabs.overview_summary', default="Overview Summary"))
        self._create_overview_tab()

        # Tab 2: Gender Analysis
        self.gender_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.gender_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.tabs.gender_analysis', default="Gender Analysis"))
        self._create_analysis_tab(self.gender_frame, 'gender')

        # Tab 3: Age Distribution
        self.age_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.age_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.tabs.age_distribution', default="Age Distribution"))
        self._create_analysis_tab(self.age_frame, 'age')

        # Tab 4: Course Enrollment
        self.course_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.course_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.tabs.course_enrollment', default="Course Enrollment"))
        self._create_analysis_tab(self.course_frame, 'course')

        # Tab 5: Cross-Tabulation
        self.crosstab_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.crosstab_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.tabs.cross_tabulation', default="Cross-Tabulation"))
        self._create_crosstab_tab()

        # Tab 6: Full Report
        self.full_report_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.full_report_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.tabs.full_report', default="Full Report"))
        self._create_full_report_tab()

        # Action buttons at bottom
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X)

        ttk.Button(
            action_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.buttons.save_report_as_txt', default="Save Report as TXT"),
            command=self._save_as_txt
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.buttons.email_report_to_admin', default="Email Report to Admin"),
            command=self._email_to_admin
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.buttons.export_all_data_csv', default="Export All Data (CSV)"),
            command=self._export_all_csv
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text=_t('advanced_search.close_button'),
            command=self.window.destroy
        ).pack(side=tk.RIGHT, padx=5)

        # Auto-generate report on open
        self.window.after(100, self._generate_full_report)

class StudentUiCommonMixin:
    def _setup_styles(self):
        """Setup ttk styles for the window"""
        style = ttk.Style()
        style.configure('Report.TFrame', padding=10)
        style.configure('ReportTitle.TLabel', font=('Helvetica', 14, 'bold'))
        style.configure('FilterLabel.TLabel', font=('Helvetica', 10))
        style.configure('Action.TButton', padding=5)

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, style='Report.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(
            main_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.labels.student_demographic_reports', default="Student Demographic Reports"),
            style='ReportTitle.TLabel'
        )
        title_label.pack(pady=(0, 15))

        # Filters Frame
        filters_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.labels.search_filters', default="Search Filters"), padding=10)
        filters_frame.pack(fill=tk.X, pady=(0, 10))

        # Filter grid - 2 rows x 4 columns
        filter_grid = ttk.Frame(filters_frame)
        filter_grid.pack(fill=tk.X)

        # Row 1: Gender, Age Group, Ethnicity, Academic Level
        filters = [
            ('gender', 'Gender:', 0, 0),
            ('age_group', 'Age Group:', 0, 2),
            ('ethnicity', 'Ethnicity:', 1, 0),
            ('academic_level', 'Academic Level:', 1, 2),
        ]

        for var_name, label_text, row, col in filters:
            ttk.Label(filter_grid, text=label_text, style='FilterLabel.TLabel').grid(
                row=row, column=col, sticky='e', padx=(10, 5), pady=5
            )
            self.filter_vars[var_name] = tk.StringVar(value=_t('gui.shell.advanced_search.demographic_reporting.ui.common.values.all', default="All"))
            combo = ttk.Combobox(
                filter_grid,
                textvariable=self.filter_vars[var_name],
                state='readonly',
                width=20
            )
            combo.grid(row=row, column=col+1, sticky='w', padx=(0, 20), pady=5)
            setattr(self, f'{var_name}_combo', combo)

        # Configure grid weights
        for i in range(4):
            filter_grid.columnconfigure(i, weight=1)

        # Additional filters: Course, Status
        row2_frame = ttk.Frame(filters_frame)
        row2_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(row2_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.labels.course', default="Course:"), style='FilterLabel.TLabel').pack(side=tk.LEFT, padx=(10, 5))
        self.filter_vars['course'] = tk.StringVar(value=_t('gui.shell.advanced_search.demographic_reporting.ui.common.values.all', default="All"))
        self.course_combo = ttk.Combobox(row2_frame, textvariable=self.filter_vars['course'], state='readonly', width=25)
        self.course_combo.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(row2_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.labels.status', default="Status:"), style='FilterLabel.TLabel').pack(side=tk.LEFT, padx=(10, 5))
        self.filter_vars['status'] = tk.StringVar(value=_t('gui.shell.advanced_search.demographic_reporting.ui.common.values.all', default="All"))
        self.status_combo = ttk.Combobox(row2_frame, textvariable=self.filter_vars['status'], state='readonly', width=15)
        self.status_combo.pack(side=tk.LEFT, padx=(0, 20))

        # Search button
        ttk.Button(row2_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.buttons.search', default="Search"), command=self._perform_search, style='Action.TButton').pack(side=tk.LEFT, padx=10)
        ttk.Button(row2_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.buttons.clear_filters', default="Clear Filters"), command=self._clear_filters).pack(side=tk.LEFT)

        # Results Frame
        results_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.labels.results', default="Results"), padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Results count label
        self.results_label = ttk.Label(results_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.labels.no_search_performed_yet', default="No search performed yet"))
        self.results_label.pack(anchor='w', pady=(0, 5))

        # Treeview with scrollbars
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        # Treeview
        columns = ('student_id', 'name', 'gender', 'age', 'course', 'status', 'ethnicity', 'academic_level')
        self.results_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show='headings',
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )

        # Configure columns
        col_widths = {
            'student_id': 100,
            'name': 180,
            'gender': 80,
            'age': 50,
            'course': 200,
            'status': 80,
            'ethnicity': 120,
            'academic_level': 120
        }
        col_headers = {
            'student_id': 'Student ID',
            'name': 'Full Name',
            'gender': 'Gender',
            'age': 'Age',
            'course': 'Course',
            'status': 'Status',
            'ethnicity': 'Ethnicity',
            'academic_level': 'Academic Level'
        }

        for col in columns:
            self.results_tree.heading(col, text=col_headers.get(col, col.title()))
            self.results_tree.column(col, width=col_widths.get(col, 100), minwidth=50)

        # Pack scrollbars and treeview
        y_scroll.config(command=self.results_tree.yview)
        x_scroll.config(command=self.results_tree.xview)

        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Summary Statistics Frame
        stats_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.labels.summary_statistics', default="Summary Statistics"), padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        self.stats_text = tk.Text(stats_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        self.stats_text.pack(fill=tk.X)

        # Action Buttons Frame
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X)

        ttk.Button(
            action_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.buttons.save_report_as_txt', default="Save Report as TXT"),
            command=self._save_as_txt,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.buttons.email_report_to_admin', default="Email Report to Admin"),
            command=self._email_to_admin,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.common.buttons.export_to_csv', default="Export to CSV"),
            command=self._export_csv
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            action_frame,
            text=_t('advanced_search.close_button'),
            command=self.window.destroy
        ).pack(side=tk.RIGHT, padx=5)
