"""
Tests for Predictive Analytics GUI Module

Tests all functionality in university_system/modules/shared/services/analytics/predictive_analytics_gui.py
"""

import pytest
import tkinter as tk
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call

from education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui import (
    PredictiveAnalyticsGUI,
    CreateRetentionPredictionDialog,
    ViewAtRiskStudentsDialog,
    CreateGraduationForecastDialog,
    CreateCoursePredictionDialog,
    CreateEnrollmentProjectionDialog,
    RecordKPIDialog,
    CreateDashboardDialog,
    launch_predictive_analytics_gui
)


@pytest.fixture
def mock_auth():
    """Create mock authentication object"""
    auth = Mock()
    auth.current_user = {'username': 'test_user', 'user_id': '12345'}
    return auth


@pytest.fixture
def root_window():
    """Create root Tkinter window for testing"""
    root = tk.Tk()
    root.withdraw()  # Hide the window
    yield root
    try:
        root.destroy()
    except Exception:
        pass


class TestPredictiveAnalyticsGUI:
    """Test PredictiveAnalyticsGUI class"""

    def test_init_without_auth(self, root_window):
        """Test initialization without authentication"""
        with patch('tkinter.messagebox.showerror') as mock_error:
            gui = PredictiveAnalyticsGUI(root_window, None)
            mock_error.assert_called_once()

    def test_init_with_auth(self, root_window, mock_auth):
        """Test initialization with authentication"""
        with patch.object(PredictiveAnalyticsGUI, '_init_database'):
            with patch.object(PredictiveAnalyticsGUI, '_create_widgets'):
                with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.log_activity'):
                    gui = PredictiveAnalyticsGUI(root_window, mock_auth)

                    assert gui.auth == mock_auth
                    assert hasattr(gui, 'window')

    def test_init_database(self, root_window, mock_auth):
        """Test database initialization"""
        with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.init_analytics_dashboard_system_db') as mock_init:
            with patch.object(PredictiveAnalyticsGUI, '_create_widgets'):
                gui = PredictiveAnalyticsGUI(root_window, mock_auth)
                # Database init should be called

    def test_create_widgets(self, root_window, mock_auth):
        """Test widget creation"""
        with patch.object(PredictiveAnalyticsGUI, '_init_database'):
            gui = PredictiveAnalyticsGUI(root_window, mock_auth)

            # Check that notebook was created
            assert hasattr(gui, 'notebook')

    def test_load_retention_predictions(self, root_window, mock_auth):
        """Test loading retention predictions"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {
                'prediction_id': 1,
                'student_id': 'S001',
                'retention_probability': 0.85,
                'risk_level': 'Low',
                'prediction_year': 2024,
                'prediction_date': '2024-01-15 10:00:00'
            }
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(PredictiveAnalyticsGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.get_connection', return_value=mock_conn):
                gui = PredictiveAnalyticsGUI(root_window, mock_auth)
                gui._load_retention_predictions()

                # Check that data was inserted into tree
                assert gui.retention_tree.get_children()

    def test_load_graduation_forecasts(self, root_window, mock_auth):
        """Test loading graduation forecasts"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {
                'forecast_id': 1,
                'cohort_year': 2024,
                'program_id': 'CS',
                'predicted_graduation_rate': 0.75,
                'predicted_4year_rate': 0.50,
                'predicted_5year_rate': 0.65,
                'predicted_6year_rate': 0.75,
                'forecast_date': '2024-01-15'
            }
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(PredictiveAnalyticsGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.get_connection', return_value=mock_conn):
                gui = PredictiveAnalyticsGUI(root_window, mock_auth)
                gui._load_graduation_forecasts()

                assert gui.graduation_tree.get_children()

    def test_load_course_predictions(self, root_window, mock_auth):
        """Test loading course demand predictions"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(PredictiveAnalyticsGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.get_connection', return_value=mock_conn):
                gui = PredictiveAnalyticsGUI(root_window, mock_auth)
                gui._load_course_predictions()
                # Should complete without error

    def test_load_enrollment_projections(self, root_window, mock_auth):
        """Test loading enrollment projections"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(PredictiveAnalyticsGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.get_connection', return_value=mock_conn):
                gui = PredictiveAnalyticsGUI(root_window, mock_auth)
                gui._load_enrollment_projections()

    def test_load_kpis(self, root_window, mock_auth):
        """Test loading KPIs"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(PredictiveAnalyticsGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.get_connection', return_value=mock_conn):
                gui = PredictiveAnalyticsGUI(root_window, mock_auth)
                gui._load_kpis()

    def test_load_dashboards(self, root_window, mock_auth):
        """Test loading dashboards"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(PredictiveAnalyticsGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.get_connection', return_value=mock_conn):
                gui = PredictiveAnalyticsGUI(root_window, mock_auth)
                gui._load_dashboards()


class TestCreateRetentionPredictionDialog:
    """Test CreateRetentionPredictionDialog class"""

    def test_init(self, root_window, mock_auth):
        """Test dialog initialization"""
        callback = Mock()

        with patch('tkinter.Toplevel'):
            dialog = CreateRetentionPredictionDialog(root_window, mock_auth, callback)

            assert dialog.auth == mock_auth
            assert dialog.callback == callback

    def test_create_prediction_success(self, root_window, mock_auth):
        """Test creating a retention prediction successfully"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = CreateRetentionPredictionDialog(root_window, mock_auth, callback)

            # Mock form inputs
            dialog.student_entry = Mock()
            dialog.student_entry.get.return_value = 'S001'
            dialog.prob_entry = Mock()
            dialog.prob_entry.get.return_value = '0.75'
            dialog.year_entry = Mock()
            dialog.year_entry.get.return_value = '2024'
            dialog.factors_text = Mock()
            dialog.factors_text.get.return_value = 'Test factors'
            dialog.recommendations_text = Mock()
            dialog.recommendations_text.get.return_value = 'Test recommendations'

            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.RetentionPredictionManager.create_prediction', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.log_activity'):
                        dialog._create()

                        callback.assert_called_once()

    def test_create_prediction_invalid_input(self, root_window, mock_auth):
        """Test creating prediction with invalid input"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = CreateRetentionPredictionDialog(root_window, mock_auth, callback)

            dialog.student_entry = Mock()
            dialog.student_entry.get.return_value = ''
            dialog.prob_entry = Mock()
            dialog.prob_entry.get.return_value = '1.5'  # Invalid

            with patch('tkinter.messagebox.showerror') as mock_error:
                dialog._create()
                mock_error.assert_called_once()


class TestViewAtRiskStudentsDialog:
    """Test ViewAtRiskStudentsDialog class"""

    def test_init(self, root_window, mock_auth):
        """Test dialog initialization"""
        with patch('tkinter.Toplevel'):
            dialog = ViewAtRiskStudentsDialog(root_window, mock_auth)
            assert dialog.auth == mock_auth

    def test_load_students(self, root_window, mock_auth):
        """Test loading at-risk students"""
        with patch('tkinter.Toplevel'):
            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.RetentionPredictionManager.get_at_risk_students') as mock_get:
                mock_get.return_value = [
                    {
                        'student_id': 'S001',
                        'first_name': 'John',
                        'last_name': 'Doe',
                        'retention_probability': 0.45,
                        'risk_level': 'High',
                        'recommendations': 'Provide tutoring'
                    }
                ]

                dialog = ViewAtRiskStudentsDialog(root_window, mock_auth)
                # Should load students without error


class TestCreateGraduationForecastDialog:
    """Test CreateGraduationForecastDialog class"""

    def test_create_forecast_success(self, root_window, mock_auth):
        """Test creating graduation forecast"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = CreateGraduationForecastDialog(root_window, mock_auth, callback)

            dialog.cohort_entry = Mock()
            dialog.cohort_entry.get.return_value = '2024'
            dialog.rate_entry = Mock()
            dialog.rate_entry.get.return_value = '0.75'
            dialog.rate4_entry = Mock()
            dialog.rate4_entry.get.return_value = '0.50'
            dialog.rate5_entry = Mock()
            dialog.rate5_entry.get.return_value = '0.65'
            dialog.rate6_entry = Mock()
            dialog.rate6_entry.get.return_value = '0.75'

            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.GraduationForecastManager.create_forecast', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.log_activity'):
                        dialog._create()
                        callback.assert_called_once()


class TestCreateCoursePredictionDialog:
    """Test CreateCoursePredictionDialog class"""

    def test_create_prediction_success(self, root_window, mock_auth):
        """Test creating course demand prediction"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = CreateCoursePredictionDialog(root_window, mock_auth, callback)

            dialog.module_entry = Mock()
            dialog.module_entry.get.return_value = 'CS101'
            dialog.year_entry = Mock()
            dialog.year_entry.get.return_value = '2024-2025'
            dialog.semester_combo = Mock()
            dialog.semester_combo.get.return_value = 'Fall'
            dialog.enrollment_entry = Mock()
            dialog.enrollment_entry.get.return_value = '150'

            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.CourseDemandPredictionManager.create_prediction', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.log_activity'):
                        dialog._create()
                        callback.assert_called_once()


class TestCreateEnrollmentProjectionDialog:
    """Test CreateEnrollmentProjectionDialog class"""

    def test_create_projection_success(self, root_window, mock_auth):
        """Test creating enrollment projection"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = CreateEnrollmentProjectionDialog(root_window, mock_auth, callback)

            dialog.year_entry = Mock()
            dialog.year_entry.get.return_value = '2025-2026'
            dialog.new_entry = Mock()
            dialog.new_entry.get.return_value = '500'
            dialog.continuing_entry = Mock()
            dialog.continuing_entry.get.return_value = '1500'
            dialog.scenario_combo = Mock()
            dialog.scenario_combo.get.return_value = 'baseline'

            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.EnrollmentProjectionManager.create_projection', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.log_activity'):
                        dialog._create()
                        callback.assert_called_once()


class TestRecordKPIDialog:
    """Test RecordKPIDialog class"""

    def test_record_kpi_success(self, root_window, mock_auth):
        """Test recording a KPI"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = RecordKPIDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = 'Student Satisfaction'
            dialog.category_combo = Mock()
            dialog.category_combo.get.return_value = 'Academic'
            dialog.value_entry = Mock()
            dialog.value_entry.get.return_value = '85.5'
            dialog.target_entry = Mock()
            dialog.target_entry.get.return_value = '90.0'
            dialog.period_combo = Mock()
            dialog.period_combo.get.return_value = 'monthly'

            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.KPIManager.record_kpi', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.log_activity'):
                        dialog._record()
                        callback.assert_called_once()

    def test_record_kpi_invalid_value(self, root_window, mock_auth):
        """Test recording KPI with invalid value"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = RecordKPIDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = 'Test KPI'
            dialog.category_combo = Mock()
            dialog.category_combo.get.return_value = 'Academic'
            dialog.value_entry = Mock()
            dialog.value_entry.get.return_value = 'invalid'
            dialog.target_entry = Mock()
            dialog.target_entry.get.return_value = ''
            dialog.period_combo = Mock()
            dialog.period_combo.get.return_value = 'monthly'

            with patch('tkinter.messagebox.showerror') as mock_error:
                dialog._record()
                mock_error.assert_called_once()


class TestCreateDashboardDialog:
    """Test CreateDashboardDialog class"""

    def test_create_dashboard_success(self, root_window, mock_auth):
        """Test creating a custom dashboard"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = CreateDashboardDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = 'Executive Dashboard'
            dialog.type_combo = Mock()
            dialog.type_combo.get.return_value = 'Executive'
            dialog.public_var = Mock()
            dialog.public_var.get.return_value = True

            with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.DashboardManager.create_dashboard', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    with patch('education_system.university_system.modules.shared.services.analytics.predictive_analytics_gui.log_activity'):
                        dialog._create()
                        callback.assert_called_once()

    def test_create_dashboard_empty_name(self, root_window, mock_auth):
        """Test creating dashboard with empty name"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = CreateDashboardDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = '  '

            with patch('tkinter.messagebox.showerror') as mock_error:
                dialog._create()
                mock_error.assert_called_once()


class TestLauncherFunction:
    """Test launcher function"""

    def test_launch_predictive_analytics_gui_success(self, root_window, mock_auth):
        """Test launching GUI successfully"""
        with patch.object(PredictiveAnalyticsGUI, '__init__', return_value=None):
            launch_predictive_analytics_gui(root_window, mock_auth)
            # Should complete without error

    def test_launch_predictive_analytics_gui_error(self, root_window, mock_auth):
        """Test launching GUI with error"""
        with patch.object(PredictiveAnalyticsGUI, '__init__', side_effect=Exception('Test error')):
            with patch('tkinter.messagebox.showerror') as mock_error:
                launch_predictive_analytics_gui(root_window, mock_auth)
                mock_error.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
