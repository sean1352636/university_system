"""
Predictive Analytics Dashboard Core Service

ML models, retention predictions, graduation forecasts, enrollment projections,
KPI tracking, and custom dashboards.
"""

from __future__ import annotations

import json
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.feature_gui_factory import create_gui_launcher
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)


class AnalyticsModelManager:
    """Manages analytics models registry"""

    @staticmethod
    def register_model(model_name: str, model_type: str, description: str = "",
                      model_version: str = "1.0", accuracy_score: Optional[float] = None,
                      parameters: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO analytics_models (
                        model_name, model_type, description, model_version,
                        accuracy_score, parameters, last_trained_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (model_name, model_type, description, model_version,
                      accuracy_score, parameters, datetime.now().isoformat()))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error registering model: {e}")


class RetentionPredictionManager:
    """Manages student retention predictions"""

    @staticmethod
    def create_prediction(student_id: str, model_id: int,
                         retention_probability: float, prediction_year: int,
                         factors: str = "", recommendations: str = "") -> int:
        try:
            # Determine risk level
            if retention_probability >= 0.8:
                risk_level = "low"
            elif retention_probability >= 0.6:
                risk_level = "medium"
            elif retention_probability >= 0.4:
                risk_level = "high"
            else:
                risk_level = "critical"

            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO retention_predictions (
                        student_id, model_id, retention_probability, risk_level,
                        prediction_year, factors, recommendations
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, model_id, retention_probability, risk_level,
                      prediction_year, factors, recommendations))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error creating retention prediction: {e}")

    @staticmethod
    def get_at_risk_students(min_probability: float = 0.6) -> List[Dict[str, Any]]:
        """Get students at risk of not being retained"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT rp.*, s.first_name, s.last_name, s.email_address
                FROM retention_predictions rp
                JOIN students s ON rp.student_id = s.student_id
                WHERE rp.retention_probability < ?
                ORDER BY rp.retention_probability ASC
            ''', (min_probability,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


class GraduationForecastManager:
    """Manages graduation rate forecasts"""

    @staticmethod
    def create_forecast(cohort_year: int, program_id: Optional[int],
                       predicted_grad_rate: float, predicted_4year: float,
                       predicted_5year: float, predicted_6year: float,
                       model_id: Optional[int] = None, confidence_interval: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO graduation_forecasts (
                        cohort_year, program_id, predicted_graduation_rate,
                        predicted_4year_rate, predicted_5year_rate, predicted_6year_rate,
                        model_id, confidence_interval
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (cohort_year, program_id, predicted_grad_rate,
                      predicted_4year, predicted_5year, predicted_6year,
                      model_id, confidence_interval))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error creating graduation forecast: {e}")


class CourseDemandPredictionManager:
    """Manages course enrollment demand predictions"""

    @staticmethod
    def create_prediction(module_code: str, academic_year: str, semester: str,
                         predicted_enrollment: int, model_id: Optional[int] = None,
                         factors: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO course_demand_predictions (
                        module_code, academic_year, semester, predicted_enrollment,
                        model_id, factors
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (module_code, academic_year, semester, predicted_enrollment,
                      model_id, factors))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error creating course demand prediction: {e}")

    @staticmethod
    def update_actual_enrollment(prediction_id: int, actual_enrollment: int) -> bool:
        """Update prediction with actual enrollment for accuracy tracking"""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE course_demand_predictions
                    SET actual_enrollment = ?
                    WHERE prediction_id = ?
                ''', (actual_enrollment, prediction_id))
                return True
        except Exception as e:
            raise Exception(f"Error updating actual enrollment: {e}")


class EnrollmentProjectionManager:
    """Manages enrollment projections"""

    @staticmethod
    def create_projection(academic_year: str, program_id: Optional[int],
                         projected_new_students: int, projected_continuing: int,
                         model_id: Optional[int] = None, scenario: str = "baseline") -> int:
        try:
            projected_total = projected_new_students + projected_continuing

            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO enrollment_projections (
                        academic_year, program_id, projected_new_students,
                        projected_continuing_students, projected_total_enrollment,
                        model_id, scenario
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (academic_year, program_id, projected_new_students,
                      projected_continuing, projected_total, model_id, scenario))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error creating enrollment projection: {e}")


class KPIManager:
    """Manages KPI metrics tracking"""

    @staticmethod
    def record_kpi(kpi_name: str, kpi_category: str, current_value: float,
                  target_value: Optional[float] = None, period: str = "monthly",
                  trend: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO kpi_metrics (
                        kpi_name, kpi_category, current_value, target_value, period, trend
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (kpi_name, kpi_category, current_value, target_value, period, trend))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error recording KPI: {e}")

    @staticmethod
    def get_kpis_by_category(category: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT * FROM kpi_metrics
                WHERE kpi_category = ?
                ORDER BY measurement_date DESC
            ''', (category,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


class DashboardManager:
    """Manages custom analytics dashboards"""

    @staticmethod
    def create_dashboard(dashboard_name: str, dashboard_type: str,
                        owner_id: str, is_public: bool = False,
                        layout_config: str = "", widget_config: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO analytics_dashboards (
                        dashboard_name, dashboard_type, owner_id, is_public,
                        layout_config, widget_config
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (dashboard_name, dashboard_type, owner_id, is_public,
                      layout_config, widget_config))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error creating dashboard: {e}")

    @staticmethod
    def add_widget(dashboard_id: int, widget_type: str, widget_title: str,
                  data_source: str, chart_type: str = "", position_x: int = 0,
                  position_y: int = 0, width: int = 4, height: int = 3,
                  config: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO dashboard_widgets (
                        dashboard_id, widget_type, widget_title, data_source,
                        chart_type, position_x, position_y, width, height, config
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (dashboard_id, widget_type, widget_title, data_source,
                      chart_type, position_x, position_y, width, height, config))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error adding widget: {e}")


class ReportSchedulerManager:
    """Manages scheduled reports"""

    @staticmethod
    def create_scheduled_report(report_name: str, report_type: str,
                               schedule_frequency: str, recipients: str,
                               report_config: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO scheduled_reports (
                        report_name, report_type, schedule_frequency, recipients, report_config
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (report_name, report_type, schedule_frequency, recipients, report_config))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error creating scheduled report: {e}")


class DataSnapshotManager:
    """Manages data snapshots for trend analysis"""

    @staticmethod
    def create_snapshot(snapshot_type: str, data: Dict[str, Any]) -> int:
        try:
            data_json = json.dumps(data)
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO analytics_snapshots (snapshot_type, data_json)
                    VALUES (?, ?)
                ''', (snapshot_type, data_json))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error creating snapshot: {e}")


def display_predictive_analytics_menu(auth):
    """Display the Predictive Analytics Dashboard CLI menu"""
    print("\n" + "="*50)
    print(f"   {get_text('analytics.title', default='PREDICTIVE ANALYTICS DASHBOARD')}")
    print("="*50)
    print(f"1. {get_text('analytics.menu.retention', default='Retention Predictions')}")
    print(f"2. {get_text('analytics.menu.graduation', default='Graduation Forecasts')}")
    print(f"3. {get_text('analytics.menu.course_demand', default='Course Demand Prediction')}")
    print(f"4. {get_text('analytics.menu.enrollment', default='Enrollment Projections')}")
    print(f"5. {get_text('analytics.menu.kpi', default='KPI Tracking')}")
    print(f"6. {get_text('analytics.menu.dashboards', default='Custom Dashboards')}")
    print(f"7. {get_text('analytics.menu.reports', default='Scheduled Reports')}")
    print(f"8. {get_text('analytics.menu.language', default='Language')}")
    print(f"9. {get_text('analytics.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    while True:
        try:
            choice = input(f"\n{get_text('analytics.prompt.choice', default='Enter your choice (1-9)')}: ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n{get_text('analytics.feature_available', default='Feature available via Analytics managers')}")
                print("Use: from university_system.modules.shared.services.analytics import KPIManager")
            elif choice == '8':
                display_language_menu_option()
            elif choice == '9':
                print(get_text('analytics.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('analytics.invalid_choice', default='Invalid choice.'))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(get_text('analytics.error', default='Error: {error}').format(error=e))


# Use factory to create GUI launcher
launch_predictive_analytics_gui = create_gui_launcher(
    title="Predictive Analytics Dashboard",
    description="""ML-powered analytics for retention, graduation, and enrollment predictions.

Features:
• Retention predictions
• Graduation forecasts
• Course demand prediction
• Enrollment projections
• KPI tracking
• Custom dashboards""",
    cli_instruction="Use CLI: Predictive Analytics Dashboard"
)



__all__ = [
    'AnalyticsModelManager', 'RetentionPredictionManager',
    'GraduationForecastManager', 'CourseDemandPredictionManager',
    'EnrollmentProjectionManager', 'KPIManager', 'DashboardManager',
    'ReportSchedulerManager', 'DataSnapshotManager',
    'display_predictive_analytics_menu',
    'launch_predictive_analytics_gui',
]
