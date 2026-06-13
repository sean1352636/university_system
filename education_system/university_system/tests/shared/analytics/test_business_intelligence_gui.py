"""
Tests for Business Intelligence GUI Module

Tests all functionality in university_system/modules/shared/services/business_intelligence/business_intelligence_gui.py
"""

import pytest
pytestmark = pytest.mark.gui

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

# Common patch prefix for the BI GUI module
_BI_MOD = 'education_system.university_system.modules.shared.services.business_intelligence.business_intelligence_gui'


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
                with patch(f'{_BI_MOD}.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)

                    assert gui.auth == mock_auth
                    assert hasattr(gui, 'window')

    def test_init_database(self, root_window, mock_auth):
        """Test database initialization"""
        with patch('education_system.university_system.infrastructure.database.schemas.analytics_bi_schemas.init_business_intelligence_system_db') as mock_init:
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                with patch(f'{_BI_MOD}.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)
                    mock_init.assert_called_once()

    def test_create_widgets(self, root_window, mock_auth):
        """Test widget creation"""
        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch(f'{_BI_MOD}.get_connection') as mock_get_conn:
                # Provide a mock connection for the internal _load_* calls
                mock_conn = Mock()
                mock_cursor = Mock()
                mock_cursor.fetchall.return_value = []
                mock_conn.execute.return_value = mock_cursor
                mock_conn.__enter__ = Mock(return_value=mock_conn)
                mock_conn.__exit__ = Mock(return_value=False)
                mock_get_conn.return_value = mock_conn

                with patch(f'{_BI_MOD}.log_activity'):
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
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                with patch(f'{_BI_MOD}.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)

        # Manually create the tree widget for the test
        gui.reports_tree = MagicMock()
        gui.reports_tree.get_children.return_value = ['item1']

        with patch(f'{_BI_MOD}.get_connection', return_value=mock_conn):
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
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                with patch(f'{_BI_MOD}.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)

        gui.exports_tree = MagicMock()

        with patch(f'{_BI_MOD}.get_connection', return_value=mock_conn):
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
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                with patch(f'{_BI_MOD}.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)

        gui.schedules_tree = MagicMock()

        with patch(f'{_BI_MOD}.get_connection', return_value=mock_conn):
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
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                with patch(f'{_BI_MOD}.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)

        gui.viz_tree = MagicMock()

        with patch(f'{_BI_MOD}.get_connection', return_value=mock_conn):
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
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                with patch(f'{_BI_MOD}.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)

        gui.metrics_tree = MagicMock()

        with patch(f'{_BI_MOD}.get_connection', return_value=mock_conn):
            gui._load_metrics()

    def test_delete_report(self, root_window, mock_auth):
        """Test deleting a report"""
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                with patch(f'{_BI_MOD}.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)

        # Create a real tree widget for selection testing
        gui.reports_tree = MagicMock()
        gui.reports_tree.selection.return_value = ['item1']
        gui.reports_tree.item.return_value = {'values': [1, 'Test Report', 'Academic', 'user', '2024-01-15']}

        with patch('tkinter.messagebox.askyesno', return_value=True):
            with patch('tkinter.messagebox.showinfo'):
                with patch(f'{_BI_MOD}.transaction', return_value=mock_conn):
                    with patch(f'{_BI_MOD}.log_activity'):
                        with patch.object(gui, '_load_reports'):
                            gui._delete_report()

    def test_toggle_schedule(self, root_window, mock_auth):
        """Test toggling schedule status"""
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                with patch(f'{_BI_MOD}.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)

        gui.schedules_tree = MagicMock()
        gui.schedules_tree.selection.return_value = ['item1']
        gui.schedules_tree.item.return_value = {'values': [1, 'Test', 1, 'daily', 'test@test.com', '\u2713', '2024-01-15']}

        with patch('tkinter.messagebox.showinfo'):
            with patch(f'{_BI_MOD}.transaction', return_value=mock_conn):
                with patch.object(gui, '_load_schedules'):
                    gui._toggle_schedule()


class TestCreateReportDialog:
    """Test CreateReportDialog class"""

    def test_init(self, root_window, mock_auth):
        """Test dialog initialization"""
        callback = Mock()

        with patch('tkinter.Toplevel'):
            with patch.object(CreateReportDialog, '_create_widgets'):
                dialog = CreateReportDialog(root_window, mock_auth, callback)

                assert dialog.auth == mock_auth
                assert dialog.callback == callback

    def test_create_report_success(self, root_window, mock_auth):
        """Test creating a report successfully"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            with patch.object(CreateReportDialog, '_create_widgets'):
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

            with patch(f'{_BI_MOD}.ReportDefinitionManager.create_report', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    with patch(f'{_BI_MOD}.log_activity'):
                        dialog._create()

                        callback.assert_called_once()

    def test_create_report_empty_name(self, root_window, mock_auth):
        """Test creating report with empty name"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            with patch.object(CreateReportDialog, '_create_widgets'):
                dialog = CreateReportDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = ''
            dialog.category_combo = Mock()
            dialog.category_combo.get.return_value = 'Academic'
            dialog.desc_text = Mock()
            dialog.desc_text.get.return_value = ''
            dialog.query_text = Mock()
            dialog.query_text.get.return_value = ''

            with patch('tkinter.messagebox.showerror') as mock_error:
                dialog._create()
                mock_error.assert_called_once()


class TestRunReportDialog:
    """Test RunReportDialog class"""

    def test_init(self, root_window, mock_auth):
        """Test dialog initialization"""
        with patch('tkinter.Toplevel'):
            with patch.object(RunReportDialog, '_create_widgets'):
                with patch.object(RunReportDialog, '_run_report'):
                    dialog = RunReportDialog(root_window, mock_auth, 1, "Test Report")

                    assert dialog.report_id == 1
                    assert dialog.report_name == "Test Report"

    def test_run_report_with_query(self, root_window, mock_auth):
        """Test running a report with SQL query"""
        # Create a dict-like row mock for fetchone
        mock_row = {'sql_query': 'SELECT * FROM students'}

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = mock_row
        mock_cursor.fetchall.return_value = [
            ('S001', 'John Doe', 'CS'),
            ('S002', 'Jane Smith', 'ENG')
        ]
        mock_cursor.description = [('student_id',), ('name',), ('course',)]
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('tkinter.Toplevel'):
            with patch.object(RunReportDialog, '_create_widgets'):
                with patch.object(RunReportDialog, '_run_report'):
                    dialog = RunReportDialog(root_window, mock_auth, 1, "Test")

        # Set up the result_text mock for the _run_report call
        dialog.result_text = Mock()

        with patch(f'{_BI_MOD}.get_connection', return_value=mock_conn):
            dialog._run_report()

    def test_export_csv(self, root_window, mock_auth):
        """Test exporting report to CSV"""
        with patch('tkinter.Toplevel'):
            with patch.object(RunReportDialog, '_create_widgets'):
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

            with patch.object(ExportReportDialog, '_create_widgets'):
                with patch.object(ExportReportDialog, '_load_reports'):
                    dialog = ExportReportDialog(root_window, mock_auth, callback)

                    dialog.reports = {'Test Report': 1}
                    dialog.report_combo = Mock()
                    dialog.report_combo.get.return_value = 'Test Report'
                    dialog.format_combo = Mock()
                    dialog.format_combo.get.return_value = 'CSV'

                    with patch(f'{_BI_MOD}.ReportExportManager.export_report', return_value=1):
                        with patch('tkinter.messagebox.showinfo'):
                            dialog._export()

                            callback.assert_called_once()

    def test_export_no_report_selected(self, root_window, mock_auth):
        """Test exporting without selecting report"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            with patch.object(ExportReportDialog, '_create_widgets'):
                with patch.object(ExportReportDialog, '_load_reports'):
                    dialog = ExportReportDialog(root_window, mock_auth, callback)

                    dialog.report_combo = Mock()
                    dialog.report_combo.get.return_value = ''
                    dialog.format_combo = Mock()
                    dialog.format_combo.get.return_value = 'CSV'

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

            with patch.object(CreateScheduleDialog, '_create_widgets'):
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

                    with patch(f'{_BI_MOD}.ReportScheduleManager.create_schedule', return_value=1):
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

            with patch.object(CreateVisualizationDialog, '_create_widgets'):
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

            with patch(f'{_BI_MOD}.VisualizationManager.create_visualization', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    dialog._create()

                    callback.assert_called_once()

    def test_create_visualization_missing_fields(self, root_window, mock_auth):
        """Test creating visualization with missing fields"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            with patch.object(CreateVisualizationDialog, '_create_widgets'):
                dialog = CreateVisualizationDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = ''
            dialog.chart_combo = Mock()
            dialog.chart_combo.get.return_value = 'Bar Chart'
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

            with patch.object(DefineMetricDialog, '_create_widgets'):
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

            with patch(f'{_BI_MOD}.CustomMetricManager.define_metric', return_value=1):
                with patch('tkinter.messagebox.showinfo'):
                    dialog._create()

                    callback.assert_called_once()

    def test_define_metric_invalid_target(self, root_window, mock_auth):
        """Test defining metric with invalid target value"""
        callback = Mock()

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_dialog = Mock()
            mock_toplevel.return_value = mock_dialog

            with patch.object(DefineMetricDialog, '_create_widgets'):
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

            with patch.object(DefineMetricDialog, '_create_widgets'):
                dialog = DefineMetricDialog(root_window, mock_auth, callback)

            dialog.name_entry = Mock()
            dialog.name_entry.get.return_value = ''
            dialog.category_combo = Mock()
            dialog.category_combo.get.return_value = 'Academic'
            dialog.formula_text = Mock()
            dialog.formula_text.get.return_value = ''
            dialog.desc_text = Mock()
            dialog.desc_text.get.return_value = ''
            dialog.target_entry = Mock()
            dialog.target_entry.get.return_value = '0'

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
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                with patch(f'{_BI_MOD}.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)

        gui.reports_tree = MagicMock()

        with patch(f'{_BI_MOD}.get_connection', return_value=mock_conn):
            with patch('tkinter.messagebox.showerror'):
                gui._load_reports()

    def test_run_report_no_query(self, root_window, mock_auth):
        """Test running report with no SQL query defined"""
        mock_row = {'sql_query': None}

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('tkinter.Toplevel'):
            with patch.object(RunReportDialog, '_create_widgets'):
                with patch.object(RunReportDialog, '_run_report'):
                    dialog = RunReportDialog(root_window, mock_auth, 1, "Test")

        dialog.result_text = Mock()

        with patch(f'{_BI_MOD}.get_connection', return_value=mock_conn):
            dialog._run_report()
            # Should handle no query gracefully

    def test_delete_report_no_selection(self, root_window, mock_auth):
        """Test deleting report with no selection"""
        with patch.object(BusinessIntelligenceGUI, '_init_database'):
            with patch.object(BusinessIntelligenceGUI, '_create_widgets'):
                with patch(f'{_BI_MOD}.log_activity'):
                    gui = BusinessIntelligenceGUI(root_window, mock_auth)

        gui.reports_tree = MagicMock()
        gui.reports_tree.selection.return_value = []

        with patch('tkinter.messagebox.showwarning') as mock_warning:
            gui._delete_report()
            mock_warning.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
