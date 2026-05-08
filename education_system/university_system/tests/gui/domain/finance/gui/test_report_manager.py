"""Tests for report_manager module"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call, mock_open
import tkinter as tk
from tkinter import messagebox, filedialog
import sys
import os
from datetime import datetime, timedelta
from io import StringIO

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

from education_system.university_system.modules.domain.finance.gui.finance.report_manager import ReportManager


class TestReportManager(unittest.TestCase):
    """Test suite for ReportManager class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock GUI
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.finance_system = Mock()

        # Mock layout and colors
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock(spec=tk.Frame)
        self.mock_gui.layout.tab_frames = {}
        self.mock_gui.layout.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#34495e',
            'info': '#17a2b8'
        }

        # Create manager
        self.manager = ReportManager(self.mock_gui)

    def tearDown(self):
        """Clean up after tests"""
        self.manager = None
        self.mock_gui = None

    def test_initialization(self):
        """Test ReportManager initialization"""
        self.assertEqual(self.manager.gui, self.mock_gui)
        self.assertEqual(self.manager.root, self.mock_gui.root)
        self.assertEqual(self.manager.conn, self.mock_gui.conn)
        self.assertEqual(self.manager.finance_system, self.mock_gui.finance_system)

    def test_initialization_without_finance_system(self):
        """Test initialization when finance_system doesn't exist"""
        gui_without_system = Mock()
        gui_without_system.root = Mock()
        gui_without_system.conn = Mock()
        del gui_without_system.finance_system

        manager = ReportManager(gui_without_system)
        self.assertIsNone(manager.finance_system)

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.tk.Frame')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.ttk.Frame')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.ttk.LabelFrame')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.ScrolledText')
    def test_create_reports_tab(self, mock_scrolled_text, mock_label_frame, mock_ttk_frame, mock_frame):
        """Test creating reports tab"""
        self.manager.create_reports_tab()

        # Verify tab was created
        self.assertIn('reports_detailed', self.mock_gui.layout.tab_frames)

        # Verify report_text widget was created
        self.assertTrue(hasattr(self.manager, 'report_text'))

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.tk.Frame')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.tk.Label')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.tk.Button')
    def test_create_report_card(self, mock_button, mock_label, mock_frame):
        """Test creating a report card"""
        parent = Mock()
        mock_card_frame = Mock()
        mock_frame.return_value = mock_card_frame

        command = Mock()
        self.manager.create_report_card(
            parent, "Test Report", "Description", command, 0, 0
        )

        mock_frame.assert_called_once()
        mock_card_frame.grid.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.messagebox.showinfo')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.tk.StringVar')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.ttk.Entry')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.ttk.Label')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.ttk.Button')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.tk.Toplevel')
    def test_gui_revenue_summary_report(self, mock_toplevel, mock_button, mock_label,
                                         mock_entry, mock_stringvar, mock_showinfo,
                                         mock_get_connection):
        """Test revenue summary report generation"""
        mock_dialog = Mock()
        mock_toplevel.return_value = mock_dialog

        # Create manager and call method
        self.manager.report_text = Mock()
        self.manager.update_status = Mock()
        self.manager.show_tab = Mock()

        self.manager.gui_revenue_summary_report()

        # Verify dialog was created
        mock_toplevel.assert_called_once()
        mock_dialog.title.assert_called_with("Revenue Summary Report")

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.get_connection')
    def test_gui_outstanding_fees_report_with_data(self, mock_get_connection):
        """Test outstanding fees report with data"""
        # Mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock fetchall to return sample data
        mock_cursor.fetchall.return_value = [
            ('S001', 'John', 'Doe', 'Computer Science', 'Tuition', 5000.00, '2024-01-15', 30.5)
        ]

        mock_get_connection.return_value = mock_conn

        # Setup manager
        self.manager.report_text = Mock()
        self.manager.update_status = Mock()
        self.manager.show_tab = Mock()

        self.manager.gui_outstanding_fees_report()

        # Verify database was queried
        mock_cursor.execute.assert_called_once()
        self.manager.show_tab.assert_called()
        self.manager.report_text.delete.assert_called()
        self.manager.report_text.insert.assert_called()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.get_connection')
    def test_gui_outstanding_fees_report_no_data(self, mock_get_connection):
        """Test outstanding fees report with no data"""
        # Mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        mock_get_connection.return_value = mock_conn

        # Setup manager
        self.manager.report_text = Mock()
        self.manager.update_status = Mock()
        self.manager.show_tab = Mock()

        self.manager.gui_outstanding_fees_report()

        # Verify appropriate message shown
        self.manager.report_text.insert.assert_called()
        call_args = self.manager.report_text.insert.call_args[0]
        self.assertIn("No outstanding fees", call_args[1])

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.messagebox.showerror')
    def test_gui_outstanding_fees_report_error(self, mock_error, mock_get_connection):
        """Test outstanding fees report error handling"""
        mock_get_connection.side_effect = Exception("Database error")

        self.manager.gui_outstanding_fees_report()

        mock_error.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.get_connection')
    def test_gui_payment_collection_report(self, mock_get_connection):
        """Test payment collection report"""
        # Mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock monthly data
        mock_cursor.fetchall.return_value = [
            ('2024-01', 150, 75000.00, 500.00),
            ('2024-02', 160, 80000.00, 500.00),
        ]

        mock_get_connection.return_value = mock_conn

        # Setup manager
        self.manager.report_text = Mock()
        self.manager.update_status = Mock()
        self.manager.show_tab = Mock()

        self.manager.gui_payment_collection_report()

        # Verify report was generated
        self.manager.report_text.insert.assert_called()
        call_args = self.manager.report_text.insert.call_args[0]
        self.assertIn("Payment Collection Report", call_args[1])

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.get_connection')
    def test_gui_student_account_summary(self, mock_get_connection):
        """Test student account summary report"""
        # Mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock student data (8 columns: student_id, first_name, last_name, course,
        # fee_count, charged, paid, balance)
        mock_cursor.fetchall.return_value = [
            ('S001', 'John', 'Doe', 'Computer Science', 3, 15000.00, 10000.00, 5000.00)
        ]

        mock_get_connection.return_value = mock_conn

        # Setup manager
        self.manager.report_text = Mock()
        self.manager.update_status = Mock()
        self.manager.show_tab = Mock()

        self.manager.gui_student_account_summary()

        # Verify report was generated
        self.manager.report_text.insert.assert_called()
        call_args = self.manager.report_text.insert.call_args[0]
        self.assertIn("Student Account Summary", call_args[1])

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.get_connection')
    def test_gui_fee_type_analysis(self, mock_get_connection):
        """Test fee type analysis report"""
        # Mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock fee type data
        mock_cursor.fetchall.return_value = [
            ('Tuition', 100, 500000.00, 450000.00, 50000.00, 90.00)
        ]

        mock_get_connection.return_value = mock_conn

        # Setup manager
        self.manager.report_text = Mock()
        self.manager.update_status = Mock()
        self.manager.show_tab = Mock()

        self.manager.gui_fee_type_analysis()

        # Verify report was generated
        self.manager.report_text.insert.assert_called()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.get_connection')
    def test_gui_payment_method_analysis(self, mock_get_connection):
        """Test payment method analysis report"""
        # Mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock payment method data
        mock_cursor.fetchall.return_value = [
            ('Card', 500, 250000.00, 500.00, 50.00, 5000.00, 60.00),
            ('Cash', 200, 100000.00, 500.00, 100.00, 2000.00, 40.00)
        ]

        mock_get_connection.return_value = mock_conn

        # Setup manager
        self.manager.report_text = Mock()
        self.manager.update_status = Mock()
        self.manager.show_tab = Mock()

        self.manager.gui_payment_method_analysis()

        # Verify report was generated
        self.manager.report_text.insert.assert_called()
        call_args = self.manager.report_text.insert.call_args[0]
        self.assertIn("Payment Method Analysis", call_args[1])

    def test_clear_report(self):
        """Test clearing the report display"""
        self.manager.report_text = Mock()
        self.manager.update_status = Mock()

        self.manager.clear_report()

        self.manager.report_text.delete.assert_called_once_with('1.0', tk.END)
        self.manager.update_status.assert_called_once_with("Report cleared")

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.filedialog.asksaveasfilename')
    @patch('builtins.open', new_callable=mock_open)
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.messagebox.showinfo')
    def test_export_report_csv_success(self, mock_showinfo, mock_file, mock_filedialog):
        """Test successful CSV export"""
        self.manager.report_text = Mock()
        self.manager.report_text.get.return_value = "Test report content"

        mock_filedialog.return_value = "/tmp/test_report.csv"

        self.manager.export_report_csv()

        mock_file.assert_called_once()
        mock_showinfo.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.filedialog.asksaveasfilename')
    def test_export_report_csv_cancelled(self, mock_filedialog):
        """Test CSV export when user cancels"""
        self.manager.report_text = Mock()
        self.manager.report_text.get.return_value = "Test report content"

        mock_filedialog.return_value = ""

        # Should not raise any exceptions
        self.manager.export_report_csv()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.filedialog.asksaveasfilename')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.messagebox.showerror')
    def test_export_report_csv_no_content(self, mock_error, mock_filedialog):
        """Test CSV export with no report content"""
        self.manager.report_text = Mock()
        self.manager.report_text.get.return_value = ""

        self.manager.export_report_csv()

        mock_error.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.filedialog.asksaveasfilename')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.messagebox.showerror')
    def test_export_report_excel_no_data(self, mock_error, mock_filedialog):
        """Test Excel export with no data"""
        self.manager.current_report_data = None

        self.manager.export_report_excel()

        mock_error.assert_called_once()

    def test_show_text_window(self):
        """Test showing content in a text window"""
        with patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.tk.Toplevel') as mock_toplevel, \
             patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.ScrolledText') as mock_text, \
             patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.ttk.Button'):
            mock_window = Mock()
            mock_toplevel.return_value = mock_window

            self.manager.show_text_window("Test Title", "Test Content")

            mock_toplevel.assert_called_once()
            mock_window.title.assert_called_with("Test Title")

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.threading.Thread')
    def test_gui_generate_revenue_forecast(self, mock_thread):
        """Test revenue forecast generation"""
        self.manager.update_status = Mock()
        self.manager.show_tab = Mock()

        self.manager.gui_generate_revenue_forecast()

        # Verify thread was started
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def test_update_forecast_output_with_widget(self):
        """Test updating forecast output when widget exists"""
        self.manager.forecast_output = Mock()
        self.manager.update_status = Mock()

        test_content = "Forecast content"
        self.manager.update_forecast_output(test_content)

        self.manager.forecast_output.delete.assert_called_once_with('1.0', tk.END)
        self.manager.forecast_output.insert.assert_called_once_with('1.0', test_content)

    def test_update_forecast_output_without_widget(self):
        """Test updating forecast output when widget doesn't exist"""
        self.manager.update_status = Mock()

        with patch.object(self.manager, 'show_text_window') as mock_show:
            test_content = "Forecast content"
            self.manager.update_forecast_output(test_content)

            mock_show.assert_called_once()


class TestReportManagerCompliance(unittest.TestCase):
    """Test compliance-related report methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.finance_system = Mock()
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock(spec=tk.Frame)
        self.mock_gui.layout.tab_frames = {}
        self.mock_gui.layout.colors = {'primary': '#000'}

        # Mock compliance manager
        self.mock_gui.collections = Mock()

        self.manager = ReportManager(self.mock_gui)

    @patch('education_system.university_system.modules.domain.finance.gui.finance.report_manager.messagebox.showwarning')
    def test_gui_aging_analysis_report_not_available(self, mock_warning):
        """Test aging analysis when compliance manager not available"""
        delattr(self.mock_gui, 'collections')
        manager = ReportManager(self.mock_gui)

        manager.gui_aging_analysis_report()

        mock_warning.assert_called_once()

    def test_gui_aging_analysis_report_available(self):
        """Test aging analysis when compliance manager available"""
        self.manager.gui_aging_analysis_report()

        self.mock_gui.collections.gui_aging_analysis_report.assert_called_once()


if __name__ == '__main__':
    unittest.main()
