"""
Predictive Analytics Dashboard GUI

Full-featured Tkinter interface for ML-powered analytics including retention predictions,
graduation forecasts, enrollment projections, and KPI tracking.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.core.activity_logger import log_activity
from education_system.university_system.modules.shared.services.analytics.analytics_dashboard_core import (
    AnalyticsModelManager,
    RetentionPredictionManager,
    GraduationForecastManager,
    CourseDemandPredictionManager,
    EnrollmentProjectionManager,
    KPIManager,
    DashboardManager
)
from education_system.university_system.core.i18n import get_text as _t, _


class PredictiveAnalyticsGUI:
    """Predictive Analytics Dashboard GUI Application"""

    def __init__(self, root, auth):
        """Initialize the Predictive Analytics GUI"""
        self.root = root
        self.auth = auth

        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.auth_required"))
            return

        self.window = tk.Toplevel(root)
        self.window.title(_t("predictive_analytics.window_title"))
        self.window.geometry("1200x800")
        self.window.minsize(1000, 600)

        # Initialize database tables
        self._init_database()

        # Setup UI
        self._create_widgets()

        # Log activity
        log_activity('Accessed Predictive Analytics Dashboard', user=self.auth.current_user.get('username'))
        print("✅ Predictive Analytics Dashboard GUI opened successfully")

    def _init_database(self):
        """Initialize database tables if they don't exist"""
        try:
            from education_system.university_system.infrastructure.database.schemas.analytics_bi_schemas import init_analytics_dashboard_system_db
            init_analytics_dashboard_system_db()
        except ImportError as e:
            print(f"⚠️  Warning: Could not import database schemas: {e}")
        except Exception as e:
            print(f"⚠️  Warning: Database initialization error: {e}")
            messagebox.showwarning(_t("common.warning"), _t("predictive_analytics.db_init_warning", error=str(e)))

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text=_t("predictive_analytics.window_title"),
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

        user_label = ttk.Label(
            header_frame,
            text=f"User: {self.auth.current_user.get('username', 'Unknown')}",
            font=('Arial', 10)
        )
        user_label.pack(side=tk.RIGHT)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self._create_retention_tab()
        self._create_graduation_tab()
        self._create_course_demand_tab()
        self._create_enrollment_tab()
        self._create_kpi_tab()
        self._create_dashboards_tab()

        # Close button
        ttk.Button(
            main_frame,
            text=_t("predictive_analytics.close"),
            command=self.window.destroy
        ).pack(pady=(10, 0))

    def _create_retention_tab(self):
        """Create Retention Predictions tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("predictive_analytics.tabs.retention"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.create_prediction"), command=self._create_retention_prediction).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.view_at_risk"), command=self._view_at_risk_students).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.refresh"), command=self._load_retention_predictions).pack(side=tk.LEFT, padx=5)

        # Predictions list
        list_frame = ttk.LabelFrame(tab, text=_t("predictive_analytics.frames.retention_predictions"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Student ID', 'Probability', 'Risk Level', 'Year', 'Date')
        self.retention_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.retention_tree.heading('#0', text='')
        self.retention_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.retention_tree.heading(col, text=col)
            if col in ['ID', 'Year']:
                self.retention_tree.column(col, width=50)
            elif col == 'Probability':
                self.retention_tree.column(col, width=100)
            else:
                self.retention_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.retention_tree.yview)
        self.retention_tree.configure(yscrollcommand=scrollbar.set)

        self.retention_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_retention_predictions()

    def _create_graduation_tab(self):
        """Create Graduation Forecasts tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("predictive_analytics.tabs.graduation"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.create_forecast"), command=self._create_graduation_forecast).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.refresh"), command=self._load_graduation_forecasts).pack(side=tk.LEFT, padx=5)

        # Forecasts list
        list_frame = ttk.LabelFrame(tab, text=_t("predictive_analytics.frames.graduation_forecasts"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Cohort Year', 'Program ID', 'Predicted Rate', '4-Year', '5-Year', '6-Year', 'Date')
        self.graduation_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.graduation_tree.heading('#0', text='')
        self.graduation_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.graduation_tree.heading(col, text=col)
            if col in ['ID', 'Program ID']:
                self.graduation_tree.column(col, width=60)
            elif col in ['4-Year', '5-Year', '6-Year']:
                self.graduation_tree.column(col, width=80)
            else:
                self.graduation_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.graduation_tree.yview)
        self.graduation_tree.configure(yscrollcommand=scrollbar.set)

        self.graduation_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_graduation_forecasts()

    def _create_course_demand_tab(self):
        """Create Course Demand Predictions tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("predictive_analytics.tabs.course_demand"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.create_prediction"), command=self._create_course_prediction).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.refresh"), command=self._load_course_predictions).pack(side=tk.LEFT, padx=5)

        # Predictions list
        list_frame = ttk.LabelFrame(tab, text=_t("predictive_analytics.frames.course_demand_predictions"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Module Code', 'Academic Year', 'Semester', 'Predicted', 'Actual', 'Date')
        self.course_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.course_tree.heading('#0', text='')
        self.course_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.course_tree.heading(col, text=col)
            if col == 'ID':
                self.course_tree.column(col, width=50)
            elif col in ['Predicted', 'Actual']:
                self.course_tree.column(col, width=80)
            else:
                self.course_tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.course_tree.yview)
        self.course_tree.configure(yscrollcommand=scrollbar.set)

        self.course_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_course_predictions()

    def _create_enrollment_tab(self):
        """Create Enrollment Projections tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("predictive_analytics.tabs.enrollment"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.create_projection"), command=self._create_enrollment_projection).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.refresh"), command=self._load_enrollment_projections).pack(side=tk.LEFT, padx=5)

        # Projections list
        list_frame = ttk.LabelFrame(tab, text=_t("predictive_analytics.frames.enrollment_projections"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Academic Year', 'Program ID', 'New Students', 'Continuing', 'Total', 'Scenario')
        self.enrollment_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.enrollment_tree.heading('#0', text='')
        self.enrollment_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.enrollment_tree.heading(col, text=col)
            if col in ['ID', 'Program ID']:
                self.enrollment_tree.column(col, width=60)
            elif col in ['New Students', 'Continuing', 'Total']:
                self.enrollment_tree.column(col, width=100)
            else:
                self.enrollment_tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.enrollment_tree.yview)
        self.enrollment_tree.configure(yscrollcommand=scrollbar.set)

        self.enrollment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_enrollment_projections()

    def _create_kpi_tab(self):
        """Create KPI Tracking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("predictive_analytics.tabs.kpi"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.record_kpi"), command=self._record_kpi).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.refresh"), command=self._load_kpis).pack(side=tk.LEFT, padx=5)

        # KPIs list
        list_frame = ttk.LabelFrame(tab, text=_t("predictive_analytics.frames.key_performance_indicators"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'KPI Name', 'Category', 'Current Value', 'Target', 'Period', 'Trend', 'Date')
        self.kpi_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.kpi_tree.heading('#0', text='')
        self.kpi_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.kpi_tree.heading(col, text=col)
            if col == 'ID':
                self.kpi_tree.column(col, width=40)
            elif col in ['Current Value', 'Target', 'Trend']:
                self.kpi_tree.column(col, width=90)
            else:
                self.kpi_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.kpi_tree.yview)
        self.kpi_tree.configure(yscrollcommand=scrollbar.set)

        self.kpi_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_kpis()

    def _create_dashboards_tab(self):
        """Create Custom Dashboards tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("predictive_analytics.tabs.dashboards"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.create_dashboard"), command=self._create_dashboard).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.refresh"), command=self._load_dashboards).pack(side=tk.LEFT, padx=5)

        # Dashboards list
        list_frame = ttk.LabelFrame(tab, text=_t("predictive_analytics.frames.available_dashboards"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Dashboard Name', 'Type', 'Owner', 'Public', 'Created')
        self.dashboard_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.dashboard_tree.heading('#0', text='')
        self.dashboard_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.dashboard_tree.heading(col, text=col)
            if col == 'ID':
                self.dashboard_tree.column(col, width=50)
            elif col in ['Type', 'Public']:
                self.dashboard_tree.column(col, width=100)
            else:
                self.dashboard_tree.column(col, width=180)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.dashboard_tree.yview)
        self.dashboard_tree.configure(yscrollcommand=scrollbar.set)

        self.dashboard_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_dashboards()

    # Load methods
    def _load_retention_predictions(self):
        """Load retention predictions"""
        try:
            self.retention_tree.delete(*self.retention_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT prediction_id, student_id, retention_probability,
                           risk_level, prediction_year, prediction_date
                    FROM retention_predictions
                    ORDER BY prediction_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['prediction_id'],
                        row['student_id'],
                        f"{row['retention_probability']:.2%}",
                        row['risk_level'],
                        row['prediction_year'],
                        row['prediction_date'][:10] if row['prediction_date'] else ''
                    )
                    self.retention_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.load_retention", error=str(e)))

    def _load_graduation_forecasts(self):
        """Load graduation forecasts"""
        try:
            self.graduation_tree.delete(*self.graduation_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT forecast_id, cohort_year, program_id,
                           predicted_graduation_rate, predicted_4year_rate,
                           predicted_5year_rate, predicted_6year_rate, forecast_date
                    FROM graduation_forecasts
                    ORDER BY cohort_year DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['forecast_id'],
                        row['cohort_year'],
                        row['program_id'] or 'All',
                        f"{row['predicted_graduation_rate']:.1%}" if row['predicted_graduation_rate'] else 'N/A',
                        f"{row['predicted_4year_rate']:.1%}" if row['predicted_4year_rate'] else 'N/A',
                        f"{row['predicted_5year_rate']:.1%}" if row['predicted_5year_rate'] else 'N/A',
                        f"{row['predicted_6year_rate']:.1%}" if row['predicted_6year_rate'] else 'N/A',
                        row['forecast_date'][:10] if row['forecast_date'] else ''
                    )
                    self.graduation_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.load_graduation", error=str(e)))

    def _load_course_predictions(self):
        """Load course demand predictions"""
        try:
            self.course_tree.delete(*self.course_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT prediction_id, module_code, academic_year, semester,
                           predicted_enrollment, actual_enrollment, prediction_date
                    FROM course_demand_predictions
                    ORDER BY prediction_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['prediction_id'],
                        row['module_code'],
                        row['academic_year'],
                        row['semester'],
                        row['predicted_enrollment'],
                        row['actual_enrollment'] if row['actual_enrollment'] else 'N/A',
                        row['prediction_date'][:10] if row['prediction_date'] else ''
                    )
                    self.course_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.load_course", error=str(e)))

    def _load_enrollment_projections(self):
        """Load enrollment projections"""
        try:
            self.enrollment_tree.delete(*self.enrollment_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT projection_id, academic_year, program_id,
                           projected_new_students, projected_continuing_students,
                           projected_total_enrollment, scenario
                    FROM enrollment_projections
                    ORDER BY academic_year DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['projection_id'],
                        row['academic_year'],
                        row['program_id'] or 'All',
                        row['projected_new_students'],
                        row['projected_continuing_students'],
                        row['projected_total_enrollment'],
                        row['scenario']
                    )
                    self.enrollment_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.load_enrollment", error=str(e)))

    def _load_kpis(self):
        """Load KPIs"""
        try:
            self.kpi_tree.delete(*self.kpi_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT kpi_id, kpi_name, kpi_category, current_value,
                           target_value, period, trend, measurement_date
                    FROM kpi_metrics
                    ORDER BY measurement_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['kpi_id'],
                        row['kpi_name'],
                        row['kpi_category'],
                        f"{row['current_value']:.2f}",
                        f"{row['target_value']:.2f}" if row['target_value'] else 'N/A',
                        row['period'],
                        row['trend'] or '-',
                        row['measurement_date'] if row['measurement_date'] else ''
                    )
                    self.kpi_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.load_kpis", error=str(e)))

    def _load_dashboards(self):
        """Load dashboards"""
        try:
            self.dashboard_tree.delete(*self.dashboard_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT dashboard_id, dashboard_name, dashboard_type,
                           owner_id, is_public, created_at
                    FROM analytics_dashboards
                    ORDER BY created_at DESC
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['dashboard_id'],
                        row['dashboard_name'],
                        row['dashboard_type'],
                        row['owner_id'],
                        '✓' if row['is_public'] else '✗',
                        row['created_at'][:10] if row['created_at'] else ''
                    )
                    self.dashboard_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.load_dashboards", error=str(e)))

    # Action methods
    def _create_retention_prediction(self):
        """Create a new retention prediction"""
        CreateRetentionPredictionDialog(self.window, self.auth, self._load_retention_predictions)

    def _view_at_risk_students(self):
        """View students at risk of not being retained"""
        ViewAtRiskStudentsDialog(self.window, self.auth)

    def _create_graduation_forecast(self):
        """Create a new graduation forecast"""
        CreateGraduationForecastDialog(self.window, self.auth, self._load_graduation_forecasts)

    def _create_course_prediction(self):
        """Create a new course demand prediction"""
        CreateCoursePredictionDialog(self.window, self.auth, self._load_course_predictions)

    def _create_enrollment_projection(self):
        """Create a new enrollment projection"""
        CreateEnrollmentProjectionDialog(self.window, self.auth, self._load_enrollment_projections)

    def _record_kpi(self):
        """Record a new KPI"""
        RecordKPIDialog(self.window, self.auth, self._load_kpis)

    def _create_dashboard(self):
        """Create a new dashboard"""
        CreateDashboardDialog(self.window, self.auth, self._load_dashboards)


# Dialog Classes

class CreateRetentionPredictionDialog:
    """Dialog for creating a retention prediction"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("predictive_analytics.dialogs.create_retention_title"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("predictive_analytics.dialogs.create_retention_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.student_id")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_entry = ttk.Entry(form_frame, width=30)
        self.student_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.probability")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.prob_entry = ttk.Entry(form_frame, width=30)
        self.prob_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.prediction_year")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.year_entry = ttk.Entry(form_frame, width=30)
        self.year_entry.insert(0, str(datetime.now().year + 1))
        self.year_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.factors")).grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.factors_text = scrolledtext.ScrolledText(form_frame, width=28, height=4)
        self.factors_text.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.recommendations")).grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.recommendations_text = scrolledtext.ScrolledText(form_frame, width=28, height=4)
        self.recommendations_text.grid(row=4, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            student_id = self.student_entry.get().strip()
            prob = float(self.prob_entry.get())
            year = int(self.year_entry.get())
            factors = self.factors_text.get('1.0', tk.END).strip()
            recommendations = self.recommendations_text.get('1.0', tk.END).strip()

            if not student_id or prob < 0 or prob > 1:
                messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.invalid_probability"))
                return

            prediction_id = RetentionPredictionManager.create_prediction(
                student_id=student_id,
                model_id=1,  # Default model
                retention_probability=prob,
                prediction_year=year,
                factors=factors,
                recommendations=recommendations
            )

            log_activity(f'Created retention prediction: {prediction_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("predictive_analytics.messages.prediction_created", id=prediction_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.invalid_input"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.create_prediction", error=str(e)))


class ViewAtRiskStudentsDialog:
    """Dialog for viewing at-risk students"""

    def __init__(self, parent, auth):
        self.auth = auth

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("predictive_analytics.dialogs.at_risk_title"))
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)

        self._create_widgets()
        self._load_students()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("predictive_analytics.dialogs.at_risk_header"),
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # List
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = (_t("predictive_analytics.dialogs.student_id").rstrip(':'), _t("common.name"), _t("common.probability"), _t("common.risk_level"), _t("predictive_analytics.recommendations"))
        self.tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=20)

        self.tree.heading('#0', text='')
        self.tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Close button
        ttk.Button(main_frame, text=_t("predictive_analytics.close"), command=self.dialog.destroy).pack(pady=(10, 0))

    def _load_students(self):
        try:
            students = RetentionPredictionManager.get_at_risk_students(min_probability=0.6)

            for student in students:
                values = (
                    student.get('student_id', 'N/A'),
                    f"{student.get('first_name', '')} {student.get('last_name', '')}",
                    f"{student.get('retention_probability', 0):.2%}",
                    student.get('risk_level', 'N/A'),
                    student.get('recommendations', 'N/A')[:50]
                )
                self.tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.load_at_risk", error=str(e)))


class CreateGraduationForecastDialog:
    """Dialog for creating a graduation forecast"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("predictive_analytics.dialogs.create_graduation_title"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("predictive_analytics.dialogs.create_graduation_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.cohort_year")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.cohort_entry = ttk.Entry(form_frame, width=30)
        self.cohort_entry.insert(0, str(datetime.now().year))
        self.cohort_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.predicted_rate")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.rate_entry = ttk.Entry(form_frame, width=30)
        self.rate_entry.insert(0, "0.75")
        self.rate_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.four_year_rate")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.rate4_entry = ttk.Entry(form_frame, width=30)
        self.rate4_entry.insert(0, "0.50")
        self.rate4_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.five_year_rate")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.rate5_entry = ttk.Entry(form_frame, width=30)
        self.rate5_entry.insert(0, "0.65")
        self.rate5_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.six_year_rate")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.rate6_entry = ttk.Entry(form_frame, width=30)
        self.rate6_entry.insert(0, "0.75")
        self.rate6_entry.grid(row=4, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            cohort_year = int(self.cohort_entry.get())
            rate = float(self.rate_entry.get())
            rate4 = float(self.rate4_entry.get())
            rate5 = float(self.rate5_entry.get())
            rate6 = float(self.rate6_entry.get())

            forecast_id = GraduationForecastManager.create_forecast(
                cohort_year=cohort_year,
                program_id=None,
                predicted_grad_rate=rate,
                predicted_4year=rate4,
                predicted_5year=rate5,
                predicted_6year=rate6
            )

            log_activity(f'Created graduation forecast: {forecast_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("predictive_analytics.messages.forecast_created", id=forecast_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.invalid_input"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.create_forecast", error=str(e)))


class CreateCoursePredictionDialog:
    """Dialog for creating a course demand prediction"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("predictive_analytics.dialogs.create_course_title"))
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("predictive_analytics.dialogs.create_course_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.module_code")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_entry = ttk.Entry(form_frame, width=30)
        self.module_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.academic_year")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.year_entry = ttk.Entry(form_frame, width=30)
        self.year_entry.insert(0, f"{datetime.now().year}-{datetime.now().year + 1}")
        self.year_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.semester")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.semester_combo = ttk.Combobox(form_frame, width=27, values=['Fall', 'Spring', 'Summer'])
        self.semester_combo.set('Fall')
        self.semester_combo.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.predicted_enrollment")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.enrollment_entry = ttk.Entry(form_frame, width=30)
        self.enrollment_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            module_code = self.module_entry.get().strip()
            academic_year = self.year_entry.get().strip()
            semester = self.semester_combo.get()
            enrollment = int(self.enrollment_entry.get())

            if not module_code or not academic_year:
                messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.required_module_year"))
                return

            prediction_id = CourseDemandPredictionManager.create_prediction(
                module_code=module_code,
                academic_year=academic_year,
                semester=semester,
                predicted_enrollment=enrollment
            )

            log_activity(f'Created course demand prediction: {prediction_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("predictive_analytics.messages.course_prediction_created", id=prediction_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.invalid_enrollment"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.create_prediction", error=str(e)))


class CreateEnrollmentProjectionDialog:
    """Dialog for creating an enrollment projection"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("predictive_analytics.dialogs.create_enrollment_title"))
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("predictive_analytics.dialogs.create_enrollment_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.academic_year")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.year_entry = ttk.Entry(form_frame, width=30)
        self.year_entry.insert(0, f"{datetime.now().year + 1}-{datetime.now().year + 2}")
        self.year_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.new_students")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.new_entry = ttk.Entry(form_frame, width=30)
        self.new_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.continuing_students")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.continuing_entry = ttk.Entry(form_frame, width=30)
        self.continuing_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.scenario")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.scenario_combo = ttk.Combobox(form_frame, width=27, values=['baseline', 'optimistic', 'pessimistic'])
        self.scenario_combo.set('baseline')
        self.scenario_combo.grid(row=3, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            academic_year = self.year_entry.get().strip()
            new_students = int(self.new_entry.get())
            continuing = int(self.continuing_entry.get())
            scenario = self.scenario_combo.get()

            if not academic_year:
                messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.required_year"))
                return

            projection_id = EnrollmentProjectionManager.create_projection(
                academic_year=academic_year,
                program_id=None,
                projected_new_students=new_students,
                projected_continuing=continuing,
                scenario=scenario
            )

            log_activity(f'Created enrollment projection: {projection_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("predictive_analytics.messages.projection_created", id=projection_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.invalid_student_numbers"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.create_projection", error=str(e)))


class RecordKPIDialog:
    """Dialog for recording a KPI"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("predictive_analytics.dialogs.record_kpi_title"))
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("predictive_analytics.dialogs.record_kpi_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.kpi_name")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.category")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.category_combo = ttk.Combobox(form_frame, width=27, values=[
            'Academic', 'Financial', 'Enrollment', 'Retention', 'Satisfaction'
        ])
        self.category_combo.set('Academic')
        self.category_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.current_value")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.value_entry = ttk.Entry(form_frame, width=30)
        self.value_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.target_value")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.target_entry = ttk.Entry(form_frame, width=30)
        self.target_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.period")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.period_combo = ttk.Combobox(form_frame, width=27, values=['daily', 'weekly', 'monthly', 'quarterly', 'yearly'])
        self.period_combo.set('monthly')
        self.period_combo.grid(row=4, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.record"), command=self._record).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _record(self):
        try:
            name = self.name_entry.get().strip()
            category = self.category_combo.get()
            value = float(self.value_entry.get())
            target_str = self.target_entry.get().strip()
            target = float(target_str) if target_str else None
            period = self.period_combo.get()

            if not name:
                messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.required_kpi_name"))
                return

            kpi_id = KPIManager.record_kpi(
                kpi_name=name,
                kpi_category=category,
                current_value=value,
                target_value=target,
                period=period
            )

            log_activity(f'Created KPI metric: {kpi_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("predictive_analytics.messages.kpi_recorded", id=kpi_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.invalid_numeric"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.record_kpi", error=str(e)))


class CreateDashboardDialog:
    """Dialog for creating a custom dashboard"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("predictive_analytics.dialogs.create_dashboard_title"))
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("predictive_analytics.dialogs.create_dashboard_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.dashboard_name")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.type")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.type_combo = ttk.Combobox(form_frame, width=27, values=[
            'Executive', 'Departmental', 'Student Affairs', 'Financial', 'Custom'
        ])
        self.type_combo.set('Custom')
        self.type_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("predictive_analytics.dialogs.public")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.public_var = tk.BooleanVar()
        ttk.Checkbutton(form_frame, variable=self.public_var).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("predictive_analytics.btn.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            dashboard_type = self.type_combo.get()
            is_public = self.public_var.get()

            if not name:
                messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.required_dashboard_name"))
                return

            dashboard_id = DashboardManager.create_dashboard(
                dashboard_name=name,
                dashboard_type=dashboard_type,
                owner_id=self.auth.current_user.get('username', ''),
                is_public=is_public
            )

            log_activity(f'Created custom dashboard: {dashboard_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("predictive_analytics.messages.dashboard_created", id=dashboard_id))
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.create_dashboard", error=str(e)))


# Launcher function
def launch_predictive_analytics_gui(root, auth):
    """Launch the Predictive Analytics Dashboard GUI"""
    try:
        PredictiveAnalyticsGUI(root, auth)
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("predictive_analytics.errors.launch_gui", error=str(e)))
        print(f"❌ Predictive Analytics GUI error: {e}")


__all__ = ['PredictiveAnalyticsGUI', 'launch_predictive_analytics_gui']
