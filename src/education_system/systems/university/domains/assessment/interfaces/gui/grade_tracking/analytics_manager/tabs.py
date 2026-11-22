"""Tab/view construction methods for AnalyticsManager."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

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
        self.notebook.add(analytics_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.tabs.analytics', default="Analytics"))

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
        controls_label = ttk.Label(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.analytics_options', default="Analytics Options"), style='Header.TLabel')
        controls_label.pack(pady=10)

        # Performance Analysis
        perf_frame = ttk.LabelFrame(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.performance_analysis', default="Performance Analysis"), padding=10)
        perf_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(perf_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.at_risk_students', default="At-Risk Students"),
                  command=self.identify_at_risk_students,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.grade_distribution', default="Grade Distribution"),
                  command=self.show_grade_distribution,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.module_performance', default="Module Performance"),
                  command=self.analyze_module_performance,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.course_comparison', default="Course Comparison"),
                  command=self.compare_course_performance,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.trends_over_time', default="Trends Over Time"),
                  command=self.analyze_performance_trends,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Risk Assessment
        risk_frame = ttk.LabelFrame(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.risk_assessment', default="Risk Assessment"), padding=10)
        risk_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(risk_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.student_risk_assessment', default="Student Risk Assessment"),
                  command=self.student_risk_assessment,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(risk_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.early_warning_system', default="Early Warning System"),
                  command=self.early_warning_system,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(risk_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.dropout_risk_analysis', default="Dropout Risk Analysis"),
                  command=self.dropout_risk_analysis,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(risk_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.intervention_recommendations', default="Intervention Recommendations"),
                  command=self.intervention_recommendations,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Visualization Options
        viz_frame = ttk.LabelFrame(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.visualizations', default="Visualizations"), padding=10)
        viz_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(viz_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.performance_dashboard', default="Performance Dashboard"),
                  command=self.generate_performance_dashboard,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(viz_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.grade_trends_chart', default="Grade Trends Chart"),
                  command=self.show_grade_trends_chart,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(viz_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.student_progress_charts', default="Student Progress Charts"),
                  command=self.student_progress_charts,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Right panel - Display area
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, weight=2)

        # Results display area
        results_label = ttk.Label(right_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.analytics_results', default="Analytics Results"), style='Header.TLabel')
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
        self.notebook.add(reports_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.tabs.reports', default="Reports"))

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

        reports_label = ttk.Label(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.report_generation', default="Report Generation"), style='Header.TLabel')
        reports_label.pack(pady=10)

        # Student Reports
        student_reports = ttk.LabelFrame(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.student_reports', default="Student Reports"), padding=10)
        student_reports.pack(fill='x', padx=10, pady=5)

        ttk.Button(student_reports, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.individual_transcript', default="Individual Transcript"),
                  command=self.generate_individual_transcript,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(student_reports, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.student_progress_report', default="Student Progress Report"),
                  command=self.generate_student_progress_report,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(student_reports, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.competency_profile', default="Competency Profile"),
                  command=self.generate_competency_profile,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(student_reports, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.at_risk_student_report', default="At-Risk Student Report"),
                  command=self.generate_at_risk_report,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Module Reports
        module_reports = ttk.LabelFrame(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.module_reports', default="Module Reports"), padding=10)
        module_reports.pack(fill='x', padx=10, pady=5)

        ttk.Button(module_reports, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.module_grade_report', default="Module Grade Report"),
                  command=self.generate_module_grade_report,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(module_reports, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.module_outcome_report', default="Module Outcome Report"),
                  command=self.generate_module_outcome_report,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(module_reports, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.assessment_analysis', default="Assessment Analysis"),
                  command=self.generate_assessment_analysis,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # System Reports
        system_reports = ttk.LabelFrame(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.system_reports', default="System Reports"), padding=10)
        system_reports.pack(fill='x', padx=10, pady=5)

        ttk.Button(system_reports, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.institution_summary', default="Institution Summary"),
                  command=self.generate_institution_summary,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(system_reports, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.performance_analytics', default="Performance Analytics"),
                  command=self.generate_performance_analytics,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(system_reports, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.trend_analysis_report', default="Trend Analysis Report"),
                  command=self.generate_trend_analysis_report,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(system_reports, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.risk_assessment_report', default="Risk Assessment Report"),
                  command=self.generate_comprehensive_risk_report,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Export Options
        export_frame = ttk.LabelFrame(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.export_options', default="Export Options"), padding=10)
        export_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(export_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.export_to_pdf', default="Export to PDF"),
                  command=self.export_reports_pdf,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(export_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.export_to_csv', default="Export to CSV"),
                  command=self.export_reports_csv,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(export_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.export_to_excel', default="Export to Excel"),
                  command=self.export_reports_excel,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Right panel - Report preview
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, weight=2)

        preview_label = ttk.Label(right_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.report_preview', default="Report Preview"), style='Header.TLabel')
        preview_label.pack(pady=10)

        # Report preview area
        self.report_preview = scrolledtext.ScrolledText(right_panel, height=35, width=70)
        self.report_preview.pack(fill='both', expand=True, padx=10, pady=5)

    def create_competency_content(self):
        """Competency framework and recorded student attainment.

        This used to display three hard-coded rows ("Technical Skills /
        Advanced / Portfolio Project / Dr. Smith"). They looked like
        records and were not, so the screen reported attainment that did
        not exist. It now reads the competency tables, and says plainly
        when they are empty.
        """
        # Assessment's grading data, through its port (services/bus).
        from education_system.systems.university.services.bus import grading_analytics as data

        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        summary = data.attainment_summary()

        # --- Attainment -----------------------------------------------
        attain = ttk.Frame(self.notebook)
        self.notebook.add(attain, text=_t(
            'gui.academics.grade_tracking.analytics_manager.tabs.tabs.attainment',
            default="Attainment"))
        ttk.Label(attain, text="Competency-Based Assessment",
                  font=('Arial', 14, 'bold')).pack(anchor="w", padx=10, pady=(10, 2))
        ttk.Label(attain,
                  text=(f"{summary['competencies']} competencies · "
                        f"{summary['levels']} levels defined · "
                        f"{summary['records']} records across "
                        f"{summary['students_assessed']} student(s)"),
                  foreground="#6b7280").pack(anchor="w", padx=10, pady=(0, 6))

        filter_row = ttk.Frame(attain)
        filter_row.pack(fill=tk.X, padx=10, pady=(0, 6))
        ttk.Label(filter_row, text="Student:").pack(side=tk.LEFT)
        student_var = tk.StringVar()
        try:
            from education_system.systems.university.infrastructure.ui.field_pickers import (
                attach_picker,
            )
            attach_picker(filter_row, 'student', id_var=student_var,
                          width=30).pack(side=tk.LEFT, padx=6)
        except Exception:
            ttk.Entry(filter_row, textvariable=student_var,
                      width=20).pack(side=tk.LEFT, padx=6)

        attain_tree = self._analysis_table(
            attain, ("Student", "Competency", "Level", "Assessed", "Evidence"),
            {"Student": 170, "Competency": 180, "Level": 120,
             "Assessed": 100, "Evidence": 220})

        def load_attainment():
            rows = data.student_attainment(student_var.get().strip() or None)
            self._fill_tree(attain_tree, [
                (r["student_name"], r["competency"], r["level"],
                 r["assessed"], r["evidence"]) for r in rows],
                "No competency attainment recorded yet.")

        ttk.Button(filter_row, text=_t(
            'gui.academics.grade_tracking.analytics_manager.tabs.buttons.search',
            default="Search"), command=load_attainment).pack(side=tk.LEFT, padx=4)
        ttk.Button(filter_row, text=_t(
            'gui.academics.grade_tracking.analytics_manager.tabs.buttons.show_all',
            default="Show all"),
            command=lambda: (student_var.set(""), load_attainment())).pack(side=tk.LEFT)
        load_attainment()

        # --- Framework ------------------------------------------------
        framework = ttk.Frame(self.notebook)
        self.notebook.add(framework, text=_t(
            'gui.academics.grade_tracking.analytics_manager.tabs.tabs.framework',
            default="Framework"))
        ttk.Label(framework, text="Competencies", font=('Arial', 10, 'bold')
                  ).pack(anchor="w", padx=10, pady=(10, 2))
        comp_tree = self._analysis_table(
            framework, ("Category", "Competency", "Description", "Students"),
            {"Category": 140, "Competency": 180, "Description": 280, "Students": 90})
        self._fill_tree(comp_tree, [
            (c["category"], c["name"], c["description"], c["holders"])
            for c in data.list_competencies()],
            "No competencies defined yet.")

        ttk.Label(framework, text="Levels", font=('Arial', 10, 'bold')
                  ).pack(anchor="w", padx=10, pady=(10, 2))
        level_tree = self._analysis_table(
            framework, ("Competency", "Level", "Value", "Description"),
            {"Competency": 180, "Level": 140, "Value": 70, "Description": 280})
        self._fill_tree(level_tree, [
            (l["competency"], l["level_name"], l["level_value"], l["description"])
            for l in data.competency_levels()],
            "No competency levels defined yet.")


    def create_prediction_content(self):
        """Create predictive analytics tab"""
        # Initialize notebook for this view
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        prediction_frame = ttk.Frame(self.notebook)
        self.notebook.add(prediction_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.tabs.predictions', default="Predictions"))

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

        prediction_label = ttk.Label(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.predictive_analytics', default="Predictive Analytics"), style='Header.TLabel')
        prediction_label.pack(pady=10)

        # Performance Prediction
        perf_pred_frame = ttk.LabelFrame(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.performance_prediction', default="Performance Prediction"), padding=10)
        perf_pred_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(perf_pred_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.grade_prediction', default="Grade Prediction"),
                  command=self.predict_grades_dialog,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_pred_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.gpa_prediction', default="GPA Prediction"),
                  command=self.predict_gpa_dialog,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_pred_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.module_success_prediction', default="Module Success Prediction"),
                  command=self.predict_module_success,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(perf_pred_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.success_probability_calculator', default="Success Probability Calculator"),
                  command=self.calculate_success_probability,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Risk Prediction
        risk_pred_frame = ttk.LabelFrame(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.risk_prediction', default="Risk Prediction"), padding=10)
        risk_pred_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(risk_pred_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.at_risk_prediction_model', default="At-Risk Prediction Model"),
                  command=self.build_at_risk_model,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(risk_pred_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.dropout_risk_analysis', default="Dropout Risk Analysis"),
                  command=self.analyze_dropout_risk,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(risk_pred_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.early_warning_alerts', default="Early Warning Alerts"),
                  command=self.generate_early_warnings,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Trend Forecasting
        trend_frame = ttk.LabelFrame(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.trend_forecasting', default="Trend Forecasting"), padding=10)
        trend_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(trend_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.performance_trends', default="Performance Trends"),
                  command=self.forecast_performance_trends,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(trend_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.course_performance_forecast', default="Course Performance Forecast"),
                  command=self.forecast_course_performance,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(trend_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.success_rate_trends', default="Success Rate Trends"),
                  command=self.forecast_success_rates,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Batch Operations
        batch_frame = ttk.LabelFrame(left_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.batch_operations', default="Batch Operations"), padding=10)
        batch_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(batch_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.batch_grade_predictions', default="Batch Grade Predictions"),
                  command=self.batch_predict_grades,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(batch_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.batch_risk_assessment', default="Batch Risk Assessment"),
                  command=self.batch_risk_assessment,
                  style='Custom.TButton').pack(fill='x', pady=2)
        ttk.Button(batch_frame, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.buttons.generate_interventions', default="Generate Interventions"),
                  command=self.generate_interventions,
                  style='Custom.TButton').pack(fill='x', pady=2)

        # Right panel - Results display
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, weight=2)

        results_label = ttk.Label(right_panel, text=_t('gui.academics.grade_tracking.analytics_manager.tabs.labels.prediction_results', default="Prediction Results"), style='Header.TLabel')
        results_label.pack(pady=10)

        # Results display area
        self.prediction_results = scrolledtext.ScrolledText(right_panel, height=25, width=60)
        self.prediction_results.pack(fill='both', expand=True, padx=10, pady=5)

        # Chart display for predictions
        self.prediction_chart_frame = ttk.Frame(right_panel)
        self.prediction_chart_frame.pack(fill='both', expand=True, padx=10, pady=5)

    # ------------------------------------------------------------------
    # Grade Curve Analysis / Performance Analysis
    #
    # Both sidebar buttons used to fall through to the generic Analytics
    # screen. The figures behind them existed only in the CLI, where
    # every function prints as it goes and stops for input(), so none of
    # it could be reused. The queries now live in
    # grading/curve_analysis_data.py and both front-ends share them.
    # ------------------------------------------------------------------

    @staticmethod
    def _fill_tree(tree, rows, empty_message="No data recorded yet."):
        """Populate a Treeview, or say plainly that there is nothing.

        An empty table looks identical to a broken one, which is how
        these screens hid the fact that they were never wired up.
        """
        for item in tree.get_children():
            tree.delete(item)
        if not rows:
            tree.insert("", tk.END, values=(empty_message,) + ("",) * 8)
            return
        for i, row in enumerate(rows):
            tree.insert("", tk.END, values=row, tags=("odd",) if i % 2 else ())

    def _analysis_table(self, parent, columns, widths=None):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        widths = widths or {}
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=widths.get(col, 130),
                        anchor=tk.E if col not in columns[:1] else tk.W)
        tree.tag_configure("odd", background="#f7f9fb")
        bar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=bar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def create_curve_analysis_content(self):
        """Grade distribution, and a preview of applying a curve."""
        # Assessment's grading data, through its port (services/bus).
        from education_system.systems.university.services.bus import grading_analytics as data

        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # --- Distribution -------------------------------------------
        dist = ttk.Frame(self.notebook)
        self.notebook.add(dist, text=_t(
            'gui.academics.grade_tracking.analytics_manager.tabs.tabs.distribution',
            default="Distribution"))
        ttk.Label(dist, text="Grade Distribution", font=('Arial', 14, 'bold')
                  ).pack(anchor="w", padx=10, pady=(10, 4))

        overall = data.grade_distribution_overall()
        for title, key in (("Module final grades", "module_grades"),
                           ("Assessment grades", "assessment_grades")):
            ttk.Label(dist, text=title, font=('Arial', 10, 'bold')
                      ).pack(anchor="w", padx=10, pady=(8, 2))
            tree = self._analysis_table(dist, ("Grade", "Count", "Share"),
                                        {"Grade": 120, "Count": 90, "Share": 90})
            self._fill_tree(tree, [(r["grade"], r["count"], f"{r['percentage']:.1f}%")
                                   for r in overall[key]],
                            "No grades recorded yet.")

        # --- By course / module type ---------------------------------
        breakdown = ttk.Frame(self.notebook)
        self.notebook.add(breakdown, text=_t(
            'gui.academics.grade_tracking.analytics_manager.tabs.tabs.breakdown',
            default="Breakdown"))
        for title, fetch in (("By course", data.grade_distribution_by_course),
                             ("By module type", data.grade_distribution_by_module_type)):
            ttk.Label(breakdown, text=title, font=('Arial', 10, 'bold')
                      ).pack(anchor="w", padx=10, pady=(10, 2))
            rows = []
            for group, entries in fetch().items():
                for entry in entries:
                    rows.append((group, entry["grade"], entry["count"],
                                 f"{entry['percentage']:.1f}%"))
            tree = self._analysis_table(breakdown, ("Group", "Grade", "Count", "Share"),
                                        {"Group": 180})
            self._fill_tree(tree, rows, "No grades recorded yet.")

        # --- Curve preview -------------------------------------------
        curve = ttk.Frame(self.notebook)
        self.notebook.add(curve, text=_t(
            'gui.academics.grade_tracking.analytics_manager.tabs.tabs.curve_preview',
            default="Curve Preview"))
        controls = ttk.Frame(curve)
        controls.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(controls, text="Adjustment (marks):").pack(side=tk.LEFT)
        adjust_var = tk.StringVar(value="5")
        ttk.Spinbox(controls, from_=-50, to=50, width=6,
                    textvariable=adjust_var).pack(side=tk.LEFT, padx=(6, 12))
        summary = ttk.Label(controls, text="", foreground="#2c3e50")
        summary.pack(side=tk.LEFT, padx=10)

        preview_tree = self._analysis_table(
            curve, ("Student", "Module", "Current", "Curved", "Grade", "New grade"),
            {"Student": 120, "Module": 130})

        def refresh_preview():
            try:
                adjustment = float(adjust_var.get())
            except ValueError:
                summary.config(text="Adjustment must be a number.", foreground="#c0392b")
                return
            result = data.curve_preview(adjustment=adjustment)
            self._fill_tree(preview_tree, [
                (r["student_id"], r["module_code"], f"{r['old_score']:.1f}",
                 f"{r['new_score']:.1f}", r["old_grade"], r["new_grade"])
                for r in result["rows"]], "No module grades recorded yet.")
            summary.config(
                text=f"{result['changed']} of {len(result['rows'])} would change grade",
                foreground="#2c3e50")

        # Preview only: applying a curve rewrites recorded marks, so that
        # stays a deliberate action in the CLI rather than a side-effect
        # of opening a tab.
        ttk.Button(controls, text=_t(
            'gui.academics.grade_tracking.analytics_manager.tabs.buttons.preview',
            default="Preview"), command=refresh_preview).pack(side=tk.LEFT)
        ttk.Label(curve, text="Preview only — no marks are changed.",
                  foreground="#6b7280").pack(anchor="w", padx=10)
        refresh_preview()

    def create_performance_analysis_content(self):
        """Comparative performance and trends over time."""
        # Assessment's grading data, through its port (services/bus).
        from education_system.systems.university.services.bus import grading_analytics as data

        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        compare = ttk.Frame(self.notebook)
        self.notebook.add(compare, text=_t(
            'gui.academics.grade_tracking.analytics_manager.tabs.tabs.comparison',
            default="Comparison"))
        ttk.Label(compare, text="Comparative Performance", font=('Arial', 14, 'bold')
                  ).pack(anchor="w", padx=10, pady=(10, 4))

        columns = ("Group", "Results", "Average", "Lowest", "Highest")
        for title, fetch in (("By course", data.performance_by_course),
                             ("By module type", data.performance_by_module_type)):
            ttk.Label(compare, text=title, font=('Arial', 10, 'bold')
                      ).pack(anchor="w", padx=10, pady=(8, 2))
            tree = self._analysis_table(compare, columns, {"Group": 200})
            self._fill_tree(tree, [
                (r["group"], r["results"], f"{r['average']:.1f}",
                 f"{r['lowest']:.1f}", f"{r['highest']:.1f}") for r in fetch()],
                "No scored module grades recorded yet.")

        trends = ttk.Frame(self.notebook)
        self.notebook.add(trends, text=_t(
            'gui.academics.grade_tracking.analytics_manager.tabs.tabs.trends',
            default="Trends"))
        ttk.Label(trends, text="Performance Over Time", font=('Arial', 14, 'bold')
                  ).pack(anchor="w", padx=10, pady=(10, 4))
        tree = self._analysis_table(trends, ("Period", "Results", "Average"),
                                    {"Period": 160})
        self._fill_tree(tree, [(r["period"], r["results"], f"{r['average']:.1f}")
                               for r in data.grade_trend_by_period()],
                        "No dated module grades recorded yet.")
