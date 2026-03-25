"""
Tests for Business Intelligence GUI Module

Tests all functionality in university_system/modules/shared/services/business_intelligence/business_intelligence_gui.py
"""

import pytest
import tkinter as tk
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, mock_open

from education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui import (
    BusinessIntelligenceGUI,
    CreateReportDialog,
    RunReportDialog,
    ExportReportDialog,
    CreateScheduleDialog,
    CreateVisualizationDialog,
    DefineMetricDialog,
    launch_business_intelligence_gui
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


class TestBusinessIntelligenceGUI:
    """Test BusinessIntelligenceGUI class"""

    def test_init_without_auth(self, root_window):
        """Test initialization without authentication"""
        with patch('tkinter.messagebox.showerror') as mock_error:
            gui = BusinessIntelligenceGUI(root_window, None)
            mock_error.assert_called_once()

    def test_init_with_auth(self, root_window, mock_auth):
        """Test initialization with authentication"""
        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)

                    assert gui.auth == mock_auth
                    assert hasattr(gui, 'window')

    def test_init_database(self, root_window, mock_auth):
        """Test database initialization"""
        with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.init_business_intelligence_system_db') as mock_init:
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                gui = BusinessIntelligenceGUI(root_window, mock_auth)

    def test_create_widgets(self, root_window, mock_auth):
        """Test widget creation"""
        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            gui = BusinessIntelligenceGUI(root_window, mock_auth)

            assert hasattr(gui, 'notebook')

    def test_load_reports(self, root_window, mock_auth):
        """Test loading reports"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ('1', 'Test Report', 'Academic', 'test_user', '2024-01-15')
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.get_connection', return_value=mock_conn):
                gui = BusinessIntelligenceGUI(root_window, mock_auth)
                gui._load_reports()

                assert gui.reports_tree.get_children()

    def test_load_exports(self, root_window, mock_auth):
        """Test loading export history"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.get_connection', return_value=mock_conn):
                gui = BusinessIntelligenceGUI(root_window, mock_auth)
                gui._load_exports()

    def test_load_schedules(self, root_window, mock_auth):
        """Test loading schedules"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.get_connection', return_value=mock_conn):
                gui = BusinessIntelligenceGUI(root_window, mock_auth)
                gui._load_schedules()

    def test_load_visualizations(self, root_window, mock_auth):
        """Test loading visualizations"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.get_connection', return_value=mock_conn):
                gui = BusinessIntelligenceGUI(root_window, mock_auth)
                gui._load_visualizations()

    def test_load_metrics(self, root_window, mock_auth):
        """Test loading metrics"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.get_connection', return_value=mock_conn):
                gui = BusinessIntelligenceGUI(root_window, mock_auth)
                gui._load_metrics()

    def test_delete_report(self, root_window, mock_auth):
        """Test deleting a report"""
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.get_connection', return_value=mock_conn):
                gui = BusinessIntelligenceGUI(root_window, mock_auth)

                # Insert test item
                gui.reports_tree.insert('', 'end', values=('1', 'Test Report', 'Academic', 'user', '2024-01-15'))
                gui.reports_tree.selection_set(gui.reports_tree.get_children()[0])

                with patch('tkinter.messagebox.askyesno', return_value=True):
                    with patch('tkinter.messagebox.showinfo'):
                        with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.transaction', return_value=mock_conn):
                            with patch.object(gui, '_load_reports'):
                                gui._delete_report()

    def test_toggle_schedule(self, root_window, mock_auth):
        """Test toggling schedule status"""
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.get_connection', return_value=mock_conn):
                gui = BusinessIntelligenceGUI(root_window, mock_auth)

                # Insert test item
                gui.schedules_tree.insert('', 'end', values=('1', 'Test', '1', 'daily', 'test@test.com', '✓', '2024-01-15'))
                gui.schedules_tree.selection_set(gui.schedules_tree.get_children()[0])

                with patch('tkinter.messagebox.showinfo'):
                    with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.transaction', return_value=mock_conn):
                        with patch.object(gui, '_load_schedules'):
                            gui._toggle_schedule()


class TestCreateReportDialog:
    """Test CreateReportDialog class"""

    def test_init(self, root_window, mock_auth):
        """Test dialog initialization"""
        callback = Mock()

        with patch('tkinter.Toplevel'):
            dialog = CreateReportDialog(root_window, mock_auth, callback)

            assert dialog.auth == mock_auth
            assert dialog.callback == callback

    def test_create_report_success(self, root_window, mock_auth):
        """Test creating a report successfully"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = CreateReportDialog(root_window, mock_auth, callback)

            # Mock form inputs
            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = 'Test Report'
            dialog.category_combo = Mock()
            dialog.category_combo.get.return_value = 'Academic'
            dialog.desc_text = Mock()
            dialog.desc_text.get.return_value = 'Test Description'
            dialog.query_text = Mock()
            dialog.query_text.get.return_value = 'SELECT * FROM students'

            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.ReportDefinitionManager.create_report', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.log_activity'):
                        dialog._create()

                        callback.assert_called_once()

    def test_create_report_empty_name(self, root_window, mock_auth):
        """Test creating report with empty name"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = CreateReportDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = ''

            with patch('tkinter.messagebox.showerror') as mock_error:
                dialog._create()
                mock_error.assert_called_once()


class TestRunReportDialog:
    """Test RunReportDialog class"""

    def test_init(self, root_window, mock_auth):
        """Test dialog initialization"""
        with patch('tkinter.Toplevel'):
            with patch.object(RunReportDialog, '_run_report'):
                dialog = RunReportDialog(root_window, mock_auth, 1, "Test Report")

                assert dialog.report_id == 1
                assert dialog.report_name == "Test Report"

    def test_run_report_with_query(self, root_window, mock_auth):
        """Test running a report with SQL query"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {'sql_query': 'SELECT * FROM students'}
        mock_cursor.fetchall.return_value = [
            ('S001', 'John Doe', 'CS'),
            ('S002', 'Jane Smith', 'ENG')
        ]
        mock_cursor.description = [('student_id',), ('name',), ('course',)]
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('tkinter.Toplevel'):
            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.get_connection', return_value=mock_conn):
                dialog = RunReportDialog(root_window, mock_auth, 1, "Test")
                # Should execute query and display results

    def test_export_csv(self, root_window, mock_auth):
        """Test exporting report to CSV"""
        with patch('tkinter.Toplevel'):
            with patch.object(RunReportDialog, '_run_report'):
                dialog = RunReportDialog(root_window, mock_auth, 1, "Test")

                dialog.results = [['val1', 'val2'], ['val3', 'val4']]
                dialog.headers = ['col1', 'col2']

                with patch('tkinter.filedialog.asksaveasfilename', return_value='/tmp/test.csv'):
                    with patch('builtins.open', mock_open()):
                        with patch('csv.writer'):
                            with patch('tkinter.messagebox.showinfo'):
                                dialog._export_csv()


class TestExportReportDialog:
    """Test ExportReportDialog class"""

    def test_export_success(self, root_window, mock_auth):
        """Test exporting a report"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            with patch.object(ExportReportDialog, '_load_reports'):
                dialog = ExportReportDialog(root_window, mock_auth, callback)

                dialog.reports = {'Test Report': 1}
                dialog.report_combo = Mock()
                dialog.report_combo.get.return_value = 'Test Report'
                dialog.format_combo = Mock()
                dialog.format_combo.get.return_value = 'CSV'

                with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.ReportExportManager.export_report', return_value=1):
                    with patch('tkinter.messagebox.showinfo'):
                        dialog._export()

                        callback.assert_called_once()

    def test_export_no_report_selected(self, root_window, mock_auth):
        """Test exporting without selecting report"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            with patch.object(ExportReportDialog, '_load_reports'):
                dialog = ExportReportDialog(root_window, mock_auth, callback)

                dialog.report_combo = Mock()
                dialog.report_combo.get.return_value = ''

                with patch('tkinter.messagebox.showerror') as mock_error:
                    dialog._export()
                    mock_error.assert_called_once()


class TestCreateScheduleDialog:
    """Test CreateScheduleDialog class"""

    def test_create_schedule_success(self, root_window, mock_auth):
        """Test creating a schedule"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            with patch.object(CreateScheduleDialog, '_load_reports'):
                dialog = CreateScheduleDialog(root_window, mock_auth, callback)

                dialog.reports = {'Test Report': 1}
                dialog.name_entry = Mock()
                dialog.name_entry.get.return_value = 'Daily Report'
                dialog.report_combo = Mock()
                dialog.report_combo.get.return_value = 'Test Report'
                dialog.freq_combo = Mock()
                dialog.freq_combo.get.return_value = 'Daily'
                dialog.delivery_combo = Mock()
                dialog.delivery_combo.get.return_value = 'Email'
                dialog.recipients_entry = Mock()
                dialog.recipients_entry.get.return_value = 'test@test.com'
                dialog.format_combo = Mock()
                dialog.format_combo.get.return_value = 'CSV'

                with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.ReportScheduleManager.create_schedule', return_value=1):
                    with patch('tkinter.messagebox.showinfo'):
                        dialog._create()

                        callback.assert_called_once()


class TestCreateVisualizationDialog:
    """Test CreateVisualizationDialog class"""

    def test_create_visualization_success(self, root_window, mock_auth):
        """Test creating a visualization"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = CreateVisualizationDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = 'Enrollment Chart'
            dialog.chart_combo = Mock()
            dialog.chart_combo.get.return_value = 'Bar Chart'
            dialog.source_entry = Mock()
            dialog.source_entry.get.return_value = 'enrollment_data'
            dialog.x_entry = Mock()
            dialog.x_entry.get.return_value = 'month'
            dialog.y_entry = Mock()
            dialog.y_entry.get.return_value = 'count'

            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.VisualizationManager.create_visualization', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    dialog._create()

                    callback.assert_called_once()

    def test_create_visualization_missing_fields(self, root_window, mock_auth):
        """Test creating visualization with missing fields"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = CreateVisualizationDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = ''
            dialog.source_entry = Mock()
            dialog.source_entry.get.return_value = ''

            with patch('tkinter.messagebox.showerror') as mock_error:
                dialog._create()
                mock_error.assert_called_once()


class TestDefineMetricDialog:
    """Test DefineMetricDialog class"""

    def test_define_metric_success(self, root_window, mock_auth):
        """Test defining a custom metric"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = DefineMetricDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = 'Success Rate'
            dialog.category_combo = Mock()
            dialog.category_combo.get.return_value = 'Academic'
            dialog.formula_text = Mock()
            dialog.formula_text.get.return_value = '(passed / total) * 100'
            dialog.desc_text = Mock()
            dialog.desc_text.get.return_value = 'Student success rate'
            dialog.target_entry = Mock()
            dialog.target_entry.get.return_value = '85'

            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.CustomMetricManager.define_metric', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    dialog._create()

                    callback.assert_called_once()

    def test_define_metric_invalid_target(self, root_window, mock_auth):
        """Test defining metric with invalid target value"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = DefineMetricDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = 'Test Metric'
            dialog.category_combo = Mock()
            dialog.category_combo.get.return_value = 'Academic'
            dialog.formula_text = Mock()
            dialog.formula_text.get.return_value = 'formula'
            dialog.desc_text = Mock()
            dialog.desc_text.get.return_value = 'desc'
            dialog.target_entry = Mock()
            dialog.target_entry.get.return_value = 'invalid'

            with patch('tkinter.messagebox.showerror') as mock_error:
                dialog._create()
                mock_error.assert_called_once()

    def test_define_metric_missing_name(self, root_window, mock_auth):
        """Test defining metric without name"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            dialog = DefineMetricDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = ''
            dialog.formula_text = Mock()
            dialog.formula_text.get.return_value = ''

            with patch('tkinter.messagebox.showerror') as mock_error:
                dialog._create()
                mock_error.assert_called_once()


class TestLauncherFunction:
    """Test launcher function"""

    def test_launch_business_intelligence_gui_success(self, root_window, mock_auth):
        """Test launching GUI successfully"""
        with patch.object(BusinessIntelligenceGUI, '__init__', return_value=None):
            launch_business_intelligence_gui(root_window, mock_auth)

    def test_launch_business_intelligence_gui_error(self, root_window, mock_auth):
        """Test launching GUI with error"""
        with patch.object(BusinessIntelligenceGUI, '__init__', side_effect=Exception('Test error')):
            with patch('tkinter.messagebox.showerror') as mock_error:
                launch_business_intelligence_gui(root_window, mock_auth)
                mock_error.assert_called_once()


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_load_reports_database_error(self, root_window, mock_auth):
        """Test handling database error when loading reports"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("DB Error")
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.get_connection', return_value=mock_conn):
                with patch('tkinter.messagebox.showerror'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)
                    gui._load_reports()

    def test_run_report_no_query(self, root_window, mock_auth):
        """Test running report with no SQL query defined"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {'sql_query': None}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('tkinter.Toplevel'):
            with patch('education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui.get_connection', return_value=mock_conn):
                dialog = RunReportDialog(root_window, mock_auth, 1, "Test")
                # Should handle no query gracefully

    def test_delete_report_no_selection(self, root_window, mock_auth):
        """Test deleting report with no selection"""
        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            gui = BusinessIntelligenceGUI(root_window, mock_auth)

            with patch('tkinter.messagebox.showwarning') as mock_warning:
                gui._delete_report()
                mock_warning.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
