"""Tab/view construction methods for AnalyticsManager."""

import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as scrolledtext


class TabsMixin:
    """Mixin providing tab creation methods for AnalyticsManager."""

    def create_analytics_content(self):
        """Create analytics and performance tab"""
        # Initialize notebook for this view. Each view that uses multiple tabs
        # should create a fresh ttk.Notebook attached to the current content frame.
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        # Create the analytics frame as a child of the notebook
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text="Analytics")

        # Create paned window for layout
        paned = ttk.PanedWindow(analytics_frame, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=10, pady=5)

        # Left panel - Controls with scrollbar
        left_panel_container = ttk.Frame(paned)
        paned.add(left_panel_container, weight=1)

        # Create canvas for scrolling
        canvas = tk.Canvas(left_panel_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_panel_container, orient="vertical", command=canvas.yview)
        left_panel = ttk.Frame(canvas)

        # Configure scrolling
        left_panel.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=left_panel, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scrolling (with existence check to prevent errors after window close)
        def _on_mousewheel(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except tk.TclError:
                pass

        def _on_mousewheel_linux(event):
            try:
                if canvas.winfo_exists():
                    if event.num == 4:
                        canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        canvas.yview_scroll(1, "units")
            except tk.TclError:
                pass

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel_linux)
        canvas.bind_all("<Button-5>", _on_mousewheel_linux)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Analytics controls
        controls_label = ttk.Label(left_panel, text="Analytics Options", style='Header.TLabel')
        controls_label.pack(pady=10)

        # Performance Analysis
        perf_frame = ttk.LabelFrame(left_panel, text="Performance Analysis", padding=10)
        perf_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(perf_frame, text="At-Risk Students",
                  command=self.identify_at_risk_students,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_frame, text="Grade Distribution",
                  command=self.show_grade_distribution,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_frame, text="Module Performance",
                  command=self.analyze_module_performance,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_frame, text="Course Comparison",
                  command=self.compare_course_performance,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_frame, text="Trends Over Time",
                  command=self.analyze_performance_trends,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Risk Assessment
        risk_frame = ttk.LabelFrame(left_panel, text="Risk Assessment", padding=10)
        risk_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(risk_frame, text="Student Risk Assessment",
                  command=self.student_risk_assessment,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(risk_frame, text="Early Warning System",
                  command=self.early_warning_system,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(risk_frame, text="Dropout Risk Analysis",
                  command=self.dropout_risk_analysis,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(risk_frame, text="Intervention Recommendations",
                  command=self.intervention_recommendations,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Visualization Options
        viz_frame = ttk.LabelFrame(left_panel, text="Visualizations", padding=10)
        viz_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(viz_frame, text="Performance Dashboard",
                  command=self.generate_performance_dashboard,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(viz_frame, text="Grade Trends Chart",
                  command=self.show_grade_trends_chart,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(viz_frame, text="Student Progress Charts",
                  command=self.student_progress_charts,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Right panel - Display area
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, weight=2)

        # Results display area
        results_label = ttk.Label(right_panel, text="Analytics Results", style='Header.TLabel')
        results_label.pack(pady=10)

        # Scrollable text area for results
        self.analytics_results = scrolledtext.ScrolledText(right_panel, height=30, width=60)
        self.analytics_results.pack(fill='both', expand=True, padx=10, pady=5)

        # Chart display frame
        self.chart_frame = ttk.Frame(right_panel)
        self.chart_frame.pack(fill='both', expand=True, padx=10, pady=5)

    def create_reports_content(self):
        """Create reports tab"""
        # Initialize notebook for this view
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        # Create reports frame as a child of the notebook
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text="Reports")

        # Create paned window
        paned = ttk.PanedWindow(reports_frame, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=10, pady=5)

        # Left panel - Report options with scrollbar
        left_panel_container = ttk.Frame(paned)
        paned.add(left_panel_container, weight=1)

        # Create canvas for scrolling
        canvas = tk.Canvas(left_panel_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_panel_container, orient="vertical", command=canvas.yview)
        left_panel = ttk.Frame(canvas)

        # Configure scrolling
        left_panel.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=left_panel, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scrolling (with existence check to prevent errors after window close)
        def _on_mousewheel_reports(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except tk.TclError:
                pass

        def _on_mousewheel_linux_reports(event):
            try:
                if canvas.winfo_exists():
                    if event.num == 4:
                        canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        canvas.yview_scroll(1, "units")
            except tk.TclError:
                pass

        canvas.bind_all("<MouseWheel>", _on_mousewheel_reports)
        canvas.bind_all("<Button-4>", _on_mousewheel_linux_reports)
        canvas.bind_all("<Button-5>", _on_mousewheel_linux_reports)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        reports_label = ttk.Label(left_panel, text="Report Generation", style='Header.TLabel')
        reports_label.pack(pady=10)

        # Student Reports
        student_reports = ttk.LabelFrame(left_panel, text="Student Reports", padding=10)
        student_reports.pack(fill='x', padx=10, pady=5)

        ttk.Button(student_reports, text="Individual Transcript",
                  command=self.generate_individual_transcript,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(student_reports, text="Student Progress Report",
                  command=self.generate_student_progress_report,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(student_reports, text="Competency Profile",
                  command=self.generate_competency_profile,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(student_reports, text="At-Risk Student Report",
                  command=self.generate_at_risk_report,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Module Reports
        module_reports = ttk.LabelFrame(left_panel, text="Module Reports", padding=10)
        module_reports.pack(fill='x', padx=10, pady=5)

        ttk.Button(module_reports, text="Module Grade Report",
                  command=self.generate_module_grade_report,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(module_reports, text="Module Outcome Report",
                  command=self.generate_module_outcome_report,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(module_reports, text="Assessment Analysis",
                  command=self.generate_assessment_analysis,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # System Reports
        system_reports = ttk.LabelFrame(left_panel, text="System Reports", padding=10)
        system_reports.pack(fill='x', padx=10, pady=5)

        ttk.Button(system_reports, text="Institution Summary",
                  command=self.generate_institution_summary,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(system_reports, text="Performance Analytics",
                  command=self.generate_performance_analytics,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(system_reports, text="Trend Analysis Report",
                  command=self.generate_trend_analysis_report,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(system_reports, text="Risk Assessment Report",
                  command=self.generate_comprehensive_risk_report,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Export Options
        export_frame = ttk.LabelFrame(left_panel, text="Export Options", padding=10)
        export_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(export_frame, text="Export to PDF",
                  command=self.export_reports_pdf,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(export_frame, text="Export to CSV",
                  command=self.export_reports_csv,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(export_frame, text="Export to Excel",
                  command=self.export_reports_excel,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Right panel - Report preview
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, weight=2)

        preview_label = ttk.Label(right_panel, text="Report Preview", style='Header.TLabel')
        preview_label.pack(pady=10)

        # Report preview area
        self.report_preview = scrolledtext.ScrolledText(right_panel, height=35, width=70)
        self.report_preview.pack(fill='both', expand=True, padx=10, pady=5)

    def create_competency_content(self):
        """Create the competency-based assessment tab (fixed version)"""
        # Initialize notebook for this view
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.competency_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.competency_frame, text="Competencies")

        # Title
        ttk.Label(self.competency_frame, text="Competency-Based Assessment",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Competency assessment functionality
        competency_controls = ttk.Frame(self.competency_frame)
        competency_controls.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(competency_controls, text="Select Student:").pack(side=tk.LEFT, padx=5)
        comp_student_var = tk.StringVar()
        comp_student_combo = ttk.Combobox(competency_controls, textvariable=comp_student_var, width=30)
        comp_student_combo.pack(side=tk.LEFT, padx=5)

        # Competency display
        competency_display = ttk.LabelFrame(self.competency_frame, text="Competency Assessment Matrix", padding=10)
        competency_display.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("Competency", "Level", "Evidence", "Date", "Assessor")
        comp_tree = ttk.Treeview(competency_display, columns=columns, show="headings", height=15)
        for col in columns:
            comp_tree.heading(col, text=col)
            comp_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(competency_display, orient=tk.VERTICAL, command=comp_tree.yview)
        comp_tree.configure(yscrollcommand=scrollbar.set)
        comp_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Sample data
        sample_comps = [
            ("Technical Skills", "Advanced", "Portfolio Project", "2024-01-15", "Dr. Smith"),
            ("Leadership", "Intermediate", "Group Project", "2024-01-10", "Prof. Jones"),
            ("Research", "Proficient", "Term Paper", "2024-01-05", "Dr. Davis"),
        ]
        for comp in sample_comps:
            comp_tree.insert('', tk.END, values=comp)

    def create_prediction_content(self):
        """Create predictive analytics tab"""
        # Initialize notebook for this view
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        prediction_frame = ttk.Frame(self.notebook)
        self.notebook.add(prediction_frame, text="Predictions")

        # Create paned window
        paned = ttk.PanedWindow(prediction_frame, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=10, pady=5)

        # Left panel - Prediction options with scrollbar
        left_panel_container = ttk.Frame(paned)
        paned.add(left_panel_container, weight=1)

        # Create canvas for scrolling
        canvas = tk.Canvas(left_panel_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_panel_container, orient="vertical", command=canvas.yview)
        left_panel = ttk.Frame(canvas)

        # Configure scrolling
        left_panel.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=left_panel, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scrolling (with existence check to prevent errors after window close)
        def _on_mousewheel_prediction(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except tk.TclError:
                pass

        def _on_mousewheel_linux_prediction(event):
            try:
                if canvas.winfo_exists():
                    if event.num == 4:
                        canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        canvas.yview_scroll(1, "units")
            except tk.TclError:
                pass

        canvas.bind_all("<MouseWheel>", _on_mousewheel_prediction)
        canvas.bind_all("<Button-4>", _on_mousewheel_linux_prediction)
        canvas.bind_all("<Button-5>", _on_mousewheel_linux_prediction)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        prediction_label = ttk.Label(left_panel, text="Predictive Analytics", style='Header.TLabel')
        prediction_label.pack(pady=10)

        # Performance Prediction
        perf_pred_frame = ttk.LabelFrame(left_panel, text="Performance Prediction", padding=10)
        perf_pred_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(perf_pred_frame, text="Grade Prediction",
                  command=self.predict_grades_dialog,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_pred_frame, text="GPA Prediction",
                  command=self.predict_gpa_dialog,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_pred_frame, text="Module Success Prediction",
                  command=self.predict_module_success,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_pred_frame, text="Success Probability Calculator",
                  command=self.calculate_success_probability,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Risk Prediction
        risk_pred_frame = ttk.LabelFrame(left_panel, text="Risk Prediction", padding=10)
        risk_pred_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(risk_pred_frame, text="At-Risk Prediction Model",
                  command=self.build_at_risk_model,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(risk_pred_frame, text="Dropout Risk Analysis",
                  command=self.analyze_dropout_risk,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(risk_pred_frame, text="Early Warning Alerts",
                  command=self.generate_early_warnings,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Trend Forecasting
        trend_frame = ttk.LabelFrame(left_panel, text="Trend Forecasting", padding=10)
        trend_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(trend_frame, text="Performance Trends",
                  command=self.forecast_performance_trends,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(trend_frame, text="Course Performance Forecast",
                  command=self.forecast_course_performance,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(trend_frame, text="Success Rate Trends",
                  command=self.forecast_success_rates,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Batch Operations
        batch_frame = ttk.LabelFrame(left_panel, text="Batch Operations", padding=10)
        batch_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(batch_frame, text="Batch Grade Predictions",
                  command=self.batch_predict_grades,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(batch_frame, text="Batch Risk Assessment",
                  command=self.batch_risk_assessment,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(batch_frame, text="Generate Interventions",
                  command=self.generate_interventions,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Right panel - Results display
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, weight=2)

        results_label = ttk.Label(right_panel, text="Prediction Results", style='Header.TLabel')
        results_label.pack(pady=10)

        # Results display area
        self.prediction_results = scrolledtext.ScrolledText(right_panel, height=25, width=60)
        self.prediction_results.pack(fill='both', expand=True, padx=10, pady=5)

        # Chart display for predictions
        self.prediction_chart_frame = ttk.Frame(right_panel)
        self.prediction_chart_frame.pack(fill='both', expand=True, padx=10, pady=5)
