"""
Tests for university_system/modules/shared/services/analytics/analytics_dashboard_core.py

This test suite validates:
- Analytics model management
- Retention predictions
- Graduation forecasts
- Course demand predictions
- Enrollment projections
- KPI tracking
- Dashboard management
- Report scheduling
- Data snapshots
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
from contextlib import contextmanager


@contextmanager
def mock_database():
    """Mock database connection and transaction context managers"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 1
    mock_cursor.fetchall.return_value = []
    mock_conn.execute.return_value = mock_cursor
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.close = MagicMock()

    with patch('education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core.transaction') as mock_trans, \
         patch('education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core.get_connection') as mock_get_conn:
        mock_trans.return_value.__enter__.return_value = mock_conn
        mock_trans.return_value.__exit__.return_value = None
        mock_get_conn.return_value = mock_conn
        yield mock_conn, mock_cursor


class TestAnalyticsModelManager:
    """Test AnalyticsModelManager class"""

    def test_register_model_creates_entry(self):
        """Test registering a new analytics model"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            AnalyticsModelManager

        with mock_database() as (mock_conn, mock_cursor):
            model_id = AnalyticsModelManager.register_model(
                model_name="Test Model",
                model_type="classification",
                description="Test description",
                model_version="1.0",
                accuracy_score=0.95
            )

            assert model_id == 1
            assert mock_conn.execute.called

    def test_register_model_with_minimal_parameters(self):
        """Test registering model with only required parameters"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            AnalyticsModelManager

        with mock_database():
            model_id = AnalyticsModelManager.register_model(
                model_name="Minimal Model",
                model_type="regression"
            )

            assert isinstance(model_id, int)

    def test_register_model_error_handling(self):
        """Test error handling in model registration"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            AnalyticsModelManager

        with patch('education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core.transaction') as mock_trans:
            mock_trans.return_value.__enter__.side_effect = Exception("Database error")

            with pytest.raises(Exception) as exc_info:
                AnalyticsModelManager.register_model(
                    model_name="Error Model",
                    model_type="test"
                )

            assert "Error registering model" in str(exc_info.value)


class TestRetentionPredictionManager:
    """Test RetentionPredictionManager class"""

    def test_create_prediction_with_low_risk(self):
        """Test creating retention prediction with low risk"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            RetentionPredictionManager

        with mock_database() as (mock_conn, mock_cursor):
            prediction_id = RetentionPredictionManager.create_prediction(
                student_id="S12345",
                model_id=1,
                retention_probability=0.85,
                prediction_year=2024
            )

            assert prediction_id == 1
            # Verify risk_level was set to "low" for 0.85 probability
            call_args = mock_conn.execute.call_args[0]
            assert "low" in call_args[1]

    def test_create_prediction_with_medium_risk(self):
        """Test creating retention prediction with medium risk"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            RetentionPredictionManager

        with mock_database() as (mock_conn, mock_cursor):
            RetentionPredictionManager.create_prediction(
                student_id="S12345",
                model_id=1,
                retention_probability=0.65,
                prediction_year=2024
            )

            # Verify risk_level was set to "medium"
            call_args = mock_conn.execute.call_args[0]
            assert "medium" in call_args[1]

    def test_create_prediction_with_high_risk(self):
        """Test creating retention prediction with high risk"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            RetentionPredictionManager

        with mock_database() as (mock_conn, mock_cursor):
            RetentionPredictionManager.create_prediction(
                student_id="S12345",
                model_id=1,
                retention_probability=0.45,
                prediction_year=2024
            )

            # Verify risk_level was set to "high"
            call_args = mock_conn.execute.call_args[0]
            assert "high" in call_args[1]

    def test_create_prediction_with_critical_risk(self):
        """Test creating retention prediction with critical risk"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            RetentionPredictionManager

        with mock_database() as (mock_conn, mock_cursor):
            RetentionPredictionManager.create_prediction(
                student_id="S12345",
                model_id=1,
                retention_probability=0.25,
                prediction_year=2024
            )

            # Verify risk_level was set to "critical"
            call_args = mock_conn.execute.call_args[0]
            assert "critical" in call_args[1]

    def test_get_at_risk_students(self):
        """Test retrieving at-risk students"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            RetentionPredictionManager

        with mock_database() as (mock_conn, mock_cursor):
            mock_cursor.fetchall.return_value = [
                {'student_id': 'S001', 'retention_probability': 0.45, 'first_name': 'John'},
                {'student_id': 'S002', 'retention_probability': 0.35, 'first_name': 'Jane'}
            ]

            at_risk = RetentionPredictionManager.get_at_risk_students(min_probability=0.6)

            assert len(at_risk) == 2
            assert mock_cursor.execute.called


class TestGraduationForecastManager:
    """Test GraduationForecastManager class"""

    def test_create_forecast(self):
        """Test creating graduation forecast"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            GraduationForecastManager

        with mock_database() as (mock_conn, mock_cursor):
            forecast_id = GraduationForecastManager.create_forecast(
                cohort_year=2024,
                program_id=1,
                predicted_grad_rate=0.78,
                predicted_4year=0.65,
                predicted_5year=0.72,
                predicted_6year=0.78
            )

            assert forecast_id == 1
            assert mock_conn.execute.called

    def test_create_forecast_with_optional_parameters(self):
        """Test creating forecast with optional parameters"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            GraduationForecastManager

        with mock_database():
            forecast_id = GraduationForecastManager.create_forecast(
                cohort_year=2024,
                program_id=None,
                predicted_grad_rate=0.75,
                predicted_4year=0.60,
                predicted_5year=0.68,
                predicted_6year=0.75,
                model_id=5,
                confidence_interval="95% CI: [0.70, 0.80]"
            )

            assert isinstance(forecast_id, int)


class TestCourseDemandPredictionManager:
    """Test CourseDemandPredictionManager class"""

    def test_create_prediction(self):
        """Test creating course demand prediction"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            CourseDemandPredictionManager

        with mock_database() as (mock_conn, mock_cursor):
            prediction_id = CourseDemandPredictionManager.create_prediction(
                module_code="CS101",
                academic_year="2024/2025",
                semester="Fall",
                predicted_enrollment=150
            )

            assert prediction_id == 1
            assert mock_conn.execute.called

    def test_update_actual_enrollment(self):
        """Test updating prediction with actual enrollment"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            CourseDemandPredictionManager

        with mock_database() as (mock_conn, mock_cursor):
            result = CourseDemandPredictionManager.update_actual_enrollment(
                prediction_id=1,
                actual_enrollment=145
            )

            assert result is True
            assert mock_conn.execute.called

    def test_create_prediction_with_factors(self):
        """Test creating prediction with contributing factors"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            CourseDemandPredictionManager

        with mock_database():
            prediction_id = CourseDemandPredictionManager.create_prediction(
                module_code="CS201",
                academic_year="2024/2025",
                semester="Spring",
                predicted_enrollment=120,
                model_id=3,
                factors="Historical trends, prerequisites, faculty availability"
            )

            assert isinstance(prediction_id, int)


class TestEnrollmentProjectionManager:
    """Test EnrollmentProjectionManager class"""

    def test_create_projection(self):
        """Test creating enrollment projection"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            EnrollmentProjectionManager

        with mock_database() as (mock_conn, mock_cursor):
            projection_id = EnrollmentProjectionManager.create_projection(
                academic_year="2024/2025",
                program_id=1,
                projected_new_students=500,
                projected_continuing=1200
            )

            assert projection_id == 1
            assert mock_conn.execute.called

    def test_create_projection_calculates_total(self):
        """Test projection calculates total enrollment"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            EnrollmentProjectionManager

        with mock_database() as (mock_conn, mock_cursor):
            EnrollmentProjectionManager.create_projection(
                academic_year="2024/2025",
                program_id=1,
                projected_new_students=500,
                projected_continuing=1200
            )

            # Verify total was calculated (500 + 1200 = 1700)
            call_args = mock_conn.execute.call_args[0]
            assert 1700 in call_args[1]

    def test_create_projection_with_scenario(self):
        """Test creating projection with scenario"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            EnrollmentProjectionManager

        with mock_database():
            projection_id = EnrollmentProjectionManager.create_projection(
                academic_year="2025/2026",
                program_id=2,
                projected_new_students=600,
                projected_continuing=1400,
                model_id=2,
                scenario="optimistic"
            )

            assert isinstance(projection_id, int)


class TestKPIManager:
    """Test KPIManager class"""

    def test_record_kpi(self):
        """Test recording KPI metric"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import KPIManager

        with mock_database() as (mock_conn, mock_cursor):
            kpi_id = KPIManager.record_kpi(
                kpi_name="Student Retention Rate",
                kpi_category="academic",
                current_value=0.85,
                target_value=0.90
            )

            assert kpi_id == 1
            assert mock_conn.execute.called

    def test_record_kpi_with_trend(self):
        """Test recording KPI with trend information"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import KPIManager

        with mock_database():
            kpi_id = KPIManager.record_kpi(
                kpi_name="Graduation Rate",
                kpi_category="academic",
                current_value=0.75,
                target_value=0.80,
                period="annual",
                trend="increasing"
            )

            assert isinstance(kpi_id, int)

    def test_get_kpis_by_category(self):
        """Test retrieving KPIs by category"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import KPIManager

        with mock_database() as (mock_conn, mock_cursor):
            mock_cursor.fetchall.return_value = [
                {'kpi_name': 'Metric 1', 'current_value': 0.85},
                {'kpi_name': 'Metric 2', 'current_value': 0.92}
            ]

            kpis = KPIManager.get_kpis_by_category("academic")

            assert len(kpis) == 2
            assert mock_cursor.execute.called


class TestDashboardManager:
    """Test DashboardManager class"""

    def test_create_dashboard(self):
        """Test creating analytics dashboard"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            DashboardManager

        with mock_database() as (mock_conn, mock_cursor):
            dashboard_id = DashboardManager.create_dashboard(
                dashboard_name="Executive Dashboard",
                dashboard_type="executive",
                owner_id="admin123",
                is_public=True
            )

            assert dashboard_id == 1
            assert mock_conn.execute.called

    def test_create_dashboard_with_config(self):
        """Test creating dashboard with layout configuration"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            DashboardManager

        with mock_database():
            dashboard_id = DashboardManager.create_dashboard(
                dashboard_name="Custom Dashboard",
                dashboard_type="custom",
                owner_id="user456",
                is_public=False,
                layout_config='{"layout": "grid", "columns": 3}',
                widget_config='{"theme": "dark"}'
            )

            assert isinstance(dashboard_id, int)

    def test_add_widget(self):
        """Test adding widget to dashboard"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            DashboardManager

        with mock_database() as (mock_conn, mock_cursor):
            widget_id = DashboardManager.add_widget(
                dashboard_id=1,
                widget_type="chart",
                widget_title="Enrollment Trends",
                data_source="enrollment_data",
                chart_type="line"
            )

            assert widget_id == 1
            assert mock_conn.execute.called

    def test_add_widget_with_position(self):
        """Test adding widget with position and size"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            DashboardManager

        with mock_database():
            widget_id = DashboardManager.add_widget(
                dashboard_id=1,
                widget_type="metric",
                widget_title="Total Students",
                data_source="student_count",
                position_x=0,
                position_y=0,
                width=2,
                height=1,
                config='{"format": "number"}'
            )

            assert isinstance(widget_id, int)


class TestReportSchedulerManager:
    """Test ReportSchedulerManager class"""

    def test_create_scheduled_report(self):
        """Test creating scheduled report"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            ReportSchedulerManager

        with mock_database() as (mock_conn, mock_cursor):
            report_id = ReportSchedulerManager.create_scheduled_report(
                report_name="Weekly Enrollment Report",
                report_type="enrollment",
                schedule_frequency="weekly",
                recipients="admin@university.edu"
            )

            assert report_id == 1
            assert mock_conn.execute.called

    def test_create_scheduled_report_with_config(self):
        """Test creating scheduled report with configuration"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            ReportSchedulerManager

        with mock_database():
            report_id = ReportSchedulerManager.create_scheduled_report(
                report_name="Monthly Financial Report",
                report_type="financial",
                schedule_frequency="monthly",
                recipients="finance@university.edu, admin@university.edu",
                report_config='{"format": "PDF", "include_charts": true}'
            )

            assert isinstance(report_id, int)


class TestDataSnapshotManager:
    """Test DataSnapshotManager class"""

    def test_create_snapshot(self):
        """Test creating data snapshot"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            DataSnapshotManager

        with mock_database() as (mock_conn, mock_cursor):
            snapshot_data = {
                "total_students": 5000,
                "total_courses": 250,
                "enrollment_rate": 0.92
            }

            snapshot_id = DataSnapshotManager.create_snapshot(
                snapshot_type="daily",
                data=snapshot_data
            )

            assert snapshot_id == 1
            assert mock_conn.execute.called

    def test_create_snapshot_serializes_json(self):
        """Test snapshot properly serializes data to JSON"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            DataSnapshotManager

        with mock_database() as (mock_conn, mock_cursor):
            snapshot_data = {
                "metrics": {
                    "retention": 0.85,
                    "graduation": 0.78
                },
                "timestamp": "2024-01-29"
            }

            DataSnapshotManager.create_snapshot(
                snapshot_type="weekly",
                data=snapshot_data
            )

            # Verify JSON serialization was called
            call_args = mock_conn.execute.call_args[0]
            # The second argument should contain a JSON string
            assert isinstance(call_args[1][1], str)


class TestCLIFunctions:
    """Test CLI menu functions"""

    def test_display_predictive_analytics_menu_exists(self):
        """Test CLI menu function is defined"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            display_predictive_analytics_menu

        assert callable(display_predictive_analytics_menu)

    @patch('builtins.input', side_effect=['9'])
    @patch('builtins.print')
    def test_display_predictive_analytics_menu_exits(self, mock_print, mock_input):
        """Test CLI menu exits properly"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            display_predictive_analytics_menu

        display_predictive_analytics_menu(None)

        # Menu should have printed
        assert mock_print.called


class TestGUILauncher:
    """Test GUI launcher function"""

    def test_launch_predictive_analytics_gui_exists(self):
        """Test GUI launcher function is defined"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            launch_predictive_analytics_gui

        assert callable(launch_predictive_analytics_gui)


class TestModuleExports:
    """Test module exports"""

    def test_all_exports_defined(self):
        """Test all items in __all__ are defined"""
        from education_system.post_18.university_system.modules.shared.services.analytics import analytics_dashboard_core

        for export_name in analytics_dashboard_core.__all__:
            assert hasattr(analytics_dashboard_core, export_name), \
                f"{export_name} in __all__ but not defined"

    def test_manager_classes_exported(self):
        """Test all manager classes are in __all__"""
        from education_system.post_18.university_system.modules.shared.services.analytics import analytics_dashboard_core

        manager_classes = [
            'AnalyticsModelManager',
            'RetentionPredictionManager',
            'GraduationForecastManager',
            'CourseDemandPredictionManager',
            'EnrollmentProjectionManager',
            'KPIManager',
            'DashboardManager',
            'ReportSchedulerManager',
            'DataSnapshotManager'
        ]

        for manager_class in manager_classes:
            assert manager_class in analytics_dashboard_core.__all__


class TestErrorHandling:
    """Test error handling across managers"""

    def test_managers_handle_database_errors(self):
        """Test managers properly handle and wrap database errors"""
        from education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core import \
            AnalyticsModelManager

        with patch('education_system.post_18.university_system.modules.shared.services.analytics.analytics_dashboard_core.transaction') as mock_trans:
            mock_trans.return_value.__enter__.side_effect = Exception("Connection failed")

            with pytest.raises(Exception) as exc_info:
                AnalyticsModelManager.register_model("Test", "type")

            # Error should be wrapped with descriptive message
            assert "Error registering model" in str(exc_info.value)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
