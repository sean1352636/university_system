"""Tests for revenue_source_manager module"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import tkinter as tk
from tkinter import messagebox, filedialog
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

from education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager import RevenueSourceManager


def _make_string_var(initial=''):
    """Create a mock StringVar that behaves like tk.StringVar"""
    var = Mock()
    var._value = initial
    var.get = lambda: var._value
    var.set = lambda v: setattr(var, '_value', v)
    return var


class TestRevenueSourceManager(unittest.TestCase):
    """Test suite for RevenueSourceManager class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock GUI
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()

        # Mock layout
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock(spec=tk.Frame)
        self.mock_gui.layout.tab_frames = {}

        # Patch StringVar to avoid needing a real Tk root
        with patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.StringVar', side_effect=lambda **kw: _make_string_var(kw.get('value', ''))):
            self.manager = RevenueSourceManager(self.mock_gui)

    def tearDown(self):
        """Clean up after tests"""
        self.manager = None
        self.mock_gui = None

    def test_initialization(self):
        """Test RevenueSourceManager initialization"""
        self.assertEqual(self.manager.gui, self.mock_gui)
        self.assertEqual(self.manager.root, self.mock_gui.root)
        self.assertEqual(self.manager.conn, self.mock_gui.conn)

    def test_colors_defined(self):
        """Test color scheme is defined"""
        self.assertIn('primary', self.manager.colors)
        self.assertIn('secondary', self.manager.colors)
        self.assertIn('success', self.manager.colors)
        self.assertIn('warning', self.manager.colors)
        self.assertIn('danger', self.manager.colors)

    def test_source_colors_defined(self):
        """Test revenue source colors are defined"""
        expected_sources = [
            'Library', 'Housing', 'Shop', 'Restaurant',
            'Alumni', 'Student Union', 'Trip Management', 'Tuition & Fees'
        ]
        for source in expected_sources:
            self.assertIn(source, self.manager.source_colors)

    def test_date_variables_initialized(self):
        """Test date variables are initialized"""
        self.assertTrue(hasattr(self.manager.start_date_var, 'get'))
        self.assertTrue(hasattr(self.manager.end_date_var, 'get'))
        self.assertTrue(callable(self.manager.start_date_var.get))
        self.assertTrue(callable(self.manager.end_date_var.get))

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.Frame')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.Label')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.Button')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.ttk.Treeview')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.ttk.PanedWindow')
    def test_create_revenue_source_tab(self, mock_paned, mock_tree, mock_button,
                                       mock_label, mock_frame):
        """Test creating revenue source tab"""
        self.manager.root.after = Mock()

        self.manager.create_revenue_source_tab()

        # Verify tab was created
        self.assertIn('revenue_source', self.mock_gui.layout.tab_frames)

        # Verify treeview was created
        self.assertTrue(hasattr(self.manager, 'revenue_tree'))

        # Verify summary label was created
        self.assertTrue(hasattr(self.manager, 'summary_label'))

        # Verify chart frame was created
        self.assertTrue(hasattr(self.manager, 'chart_frame'))

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.get_revenue_by_source')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.messagebox.showinfo')
    def test_load_revenue_data_no_data(self, mock_showinfo, mock_get_revenue):
        """Test loading revenue data when no data available"""
        mock_get_revenue.return_value = {}

        self.manager.revenue_tree = Mock()
        self.manager.revenue_tree.get_children.return_value = []
        self.manager.start_date_var.set('2024-01-01')
        self.manager.end_date_var.set('2024-12-31')

        self.manager.load_revenue_data()

        mock_showinfo.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.get_revenue_by_source')
    def test_load_revenue_data_with_data(self, mock_get_revenue):
        """Test loading revenue data with valid data"""
        # Mock revenue data
        mock_get_revenue.return_value = {
            'Library': {
                'count': 100,
                'total': 5000.00,
                'average': 50.00,
                'min': 10.00,
                'max': 100.00
            },
            'Housing': {
                'count': 50,
                'total': 25000.00,
                'average': 500.00,
                'min': 250.00,
                'max': 1000.00
            }
        }

        # Setup mocks
        self.manager.revenue_tree = Mock()
        self.manager.revenue_tree.get_children.return_value = []
        self.manager.summary_label = Mock()
        self.manager.start_date_var.set('2024-01-01')
        self.manager.end_date_var.set('2024-12-31')

        self.manager.load_revenue_data()

        # Verify data was inserted
        self.assertEqual(self.manager.revenue_tree.insert.call_count, 2)

        # Verify summary was updated
        self.manager.summary_label.config.assert_called_once()

        # Verify data was stored for charting
        self.assertTrue(hasattr(self.manager, 'current_revenue_data'))

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.messagebox.showwarning')
    def test_load_revenue_data_missing_dates(self, mock_warning):
        """Test loading revenue data with missing dates"""
        self.manager.revenue_tree = Mock()
        self.manager.revenue_tree.get_children.return_value = []
        self.manager.start_date_var.set('')
        self.manager.end_date_var.set('')

        self.manager.load_revenue_data()

        mock_warning.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.get_revenue_by_source')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.messagebox.showerror')
    def test_load_revenue_data_error(self, mock_error, mock_get_revenue):
        """Test loading revenue data error handling"""
        mock_get_revenue.side_effect = Exception("Database error")

        self.manager.revenue_tree = Mock()
        self.manager.revenue_tree.get_children.return_value = []
        self.manager.start_date_var.set('2024-01-01')
        self.manager.end_date_var.set('2024-12-31')

        self.manager.load_revenue_data()

        mock_error.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.messagebox.showwarning')
    def test_show_charts_no_data(self, mock_warning):
        """Test showing charts when no data loaded"""
        self.manager.show_charts()

        mock_warning.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.Toplevel')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.FigureCanvasTkAgg')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.Figure')
    def test_show_charts_with_data(self, mock_figure_cls, mock_canvas, mock_toplevel):
        """Test showing charts with valid data"""
        # Setup data
        self.manager.current_revenue_data = {
            'Library': {
                'count': 100,
                'total': 5000.00,
                'average': 50.00,
                'min': 10.00,
                'max': 100.00
            }
        }

        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        # Setup mock figure with working subplot
        mock_fig = Mock()
        mock_figure_cls.return_value = mock_fig
        mock_ax = Mock()
        mock_fig.add_subplot.return_value = mock_ax
        mock_ax.pie.return_value = ([Mock()], [Mock()], [Mock()])
        mock_bar = Mock()
        mock_bar.get_height.return_value = 5000.0
        mock_bar.get_x.return_value = 0
        mock_bar.get_width.return_value = 0.8
        mock_ax.bar.return_value = [mock_bar]

        self.manager.show_charts()

        # Verify window was created
        mock_toplevel.assert_called_once()
        mock_window.title.assert_called_once()

        # Verify canvas was created
        mock_canvas.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.Toplevel')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.messagebox.showerror')
    def test_show_charts_error(self, mock_error, mock_toplevel):
        """Test showing charts error handling"""
        self.manager.current_revenue_data = {'Library': {'total': 5000}}

        mock_toplevel.side_effect = Exception("Chart error")

        self.manager.show_charts()

        mock_error.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.messagebox.showwarning')
    def test_show_trends_no_data(self, mock_warning):
        """Test showing trends when no data loaded"""
        self.manager.show_trends()

        mock_warning.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.FigureCanvasTkAgg')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.Figure')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.plt')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.Toplevel')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.Frame')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.Label')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.Button')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.StringVar')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.ttk.Combobox')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.ttk.Entry')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.get_source_revenue_trend')
    def test_show_trends_with_data(self, mock_get_trend, mock_entry, mock_combo, mock_sv,
                                    mock_button, mock_label, mock_frame, mock_toplevel,
                                    mock_plt, mock_figure_cls, mock_canvas):
        """Test showing trends with valid data"""
        # Setup data
        self.manager.current_revenue_data = {
            'Library': {'total': 5000.00}
        }

        # Mock trend data
        mock_get_trend.return_value = [
            ('2024-01', 1000.00, 20),
            ('2024-02', 1200.00, 25)
        ]

        # Mock StringVar for source selection
        source_var = _make_string_var('Library')
        months_var = _make_string_var('12')
        mock_sv.side_effect = [source_var, months_var]

        # Mock combobox
        mock_combo_inst = Mock()
        mock_combo.return_value = mock_combo_inst

        # Mock figure
        mock_fig = Mock()
        mock_figure_cls.return_value = mock_fig
        mock_ax = Mock()
        mock_fig.add_subplot.return_value = mock_ax
        mock_ax.twinx.return_value = Mock()

        # Mock frame for chart container
        mock_chart_container = Mock()
        mock_chart_container.winfo_children.return_value = []
        mock_frame.return_value = mock_chart_container

        self.manager.show_trends()

        # Verify window was created
        mock_toplevel.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.filedialog.asksaveasfilename')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.export_revenue_by_source_csv')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.messagebox.showinfo')
    def test_export_data_success(self, mock_showinfo, mock_export, mock_filedialog):
        """Test successful data export"""
        mock_filedialog.return_value = "/tmp/revenue_data.csv"
        mock_export.return_value = True

        self.manager.start_date_var.set('2024-01-01')
        self.manager.end_date_var.set('2024-12-31')

        self.manager.export_data()

        # The code passes `start_date.strip() or None` so non-empty dates are passed as-is
        mock_export.assert_called_once_with(
            "/tmp/revenue_data.csv",
            '2024-01-01',
            '2024-12-31'
        )
        mock_showinfo.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.filedialog.asksaveasfilename')
    def test_export_data_cancelled(self, mock_filedialog):
        """Test export when user cancels"""
        mock_filedialog.return_value = ""

        # Should not raise any exceptions
        self.manager.export_data()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.filedialog.asksaveasfilename')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.export_revenue_by_source_csv')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.messagebox.showerror')
    def test_export_data_failure(self, mock_error, mock_export, mock_filedialog):
        """Test export failure handling"""
        mock_filedialog.return_value = "/tmp/revenue_data.csv"
        mock_export.return_value = False

        self.manager.start_date_var.set('2024-01-01')
        self.manager.end_date_var.set('2024-12-31')

        self.manager.export_data()

        mock_error.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.filedialog.asksaveasfilename')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.messagebox.showerror')
    def test_export_data_exception(self, mock_error, mock_filedialog):
        """Test export exception handling"""
        mock_filedialog.side_effect = Exception("File error")

        self.manager.export_data()

        mock_error.assert_called_once()


class TestRevenueDataFormatting(unittest.TestCase):
    """Test revenue data formatting"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock(spec=tk.Frame)
        self.mock_gui.layout.tab_frames = {}

        with patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.tk.StringVar', side_effect=lambda **kw: _make_string_var(kw.get('value', ''))):
            self.manager = RevenueSourceManager(self.mock_gui)

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.get_revenue_by_source')
    def test_revenue_data_formatting(self, mock_get_revenue):
        """Test that revenue data is formatted correctly"""
        # Mock revenue data with specific values
        mock_get_revenue.return_value = {
            'Library': {
                'count': 123,
                'total': 12345.67,
                'average': 100.37,
                'min': 5.50,
                'max': 500.00
            }
        }

        # Setup mocks
        self.manager.revenue_tree = Mock()
        self.manager.revenue_tree.get_children.return_value = []
        self.manager.summary_label = Mock()
        self.manager.start_date_var.set('2024-01-01')
        self.manager.end_date_var.set('2024-12-31')

        self.manager.load_revenue_data()

        # Get the insert call
        insert_call = self.manager.revenue_tree.insert.call_args[1]['values']

        # Verify formatting
        self.assertEqual(insert_call[0], 'Library')  # Source
        self.assertEqual(insert_call[1], '123')  # Count with comma
        self.assertIn('£12,345.67', insert_call[2])  # Total with currency
        self.assertIn('£100.37', insert_call[3])  # Average with currency
        self.assertIn('£5.50', insert_call[4])  # Min with currency
        self.assertIn('£500.00', insert_call[5])  # Max with currency

    @patch('education_system.university_system.modules.domain.finance.gui.finance.revenue_source_manager.get_revenue_by_source')
    def test_percentage_calculation(self, mock_get_revenue):
        """Test percentage calculation is accurate"""
        # Mock revenue data with known percentages
        mock_get_revenue.return_value = {
            'Library': {'count': 100, 'total': 1000.00, 'average': 10.00, 'min': 5.00, 'max': 20.00},
            'Housing': {'count': 100, 'total': 4000.00, 'average': 40.00, 'min': 20.00, 'max': 80.00}
        }

        # Setup mocks
        self.manager.revenue_tree = Mock()
        self.manager.revenue_tree.get_children.return_value = []
        self.manager.summary_label = Mock()
        self.manager.start_date_var.set('2024-01-01')
        self.manager.end_date_var.set('2024-12-31')

        self.manager.load_revenue_data()

        # Get all insert calls
        insert_calls = self.manager.revenue_tree.insert.call_args_list

        # Find Library entry (should be 20% of total 5000)
        for call in insert_calls:
            values = call[1]['values']
            if values[0] == 'Library':
                self.assertIn('20.0%', values[6])
            elif values[0] == 'Housing':
                self.assertIn('80.0%', values[6])


if __name__ == '__main__':
    unittest.main()
