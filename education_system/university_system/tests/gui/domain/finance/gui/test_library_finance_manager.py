"""Tests for LibraryFinanceManager"""

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta

from education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager import LibraryFinanceManager


class MockGUI:
    """Mock GUI for testing"""
    def __init__(self):
        self.root = Mock()  # Mock Tk root to avoid display issues
        self.conn = None
        self.layout = Mock()
        self.layout.content_frame = Mock()
        self.layout.tab_frames = {}


@pytest.fixture
def mock_gui():
    """Create mock GUI"""
    gui = MockGUI()
    yield gui


@pytest.fixture
def library_manager(mock_gui):
    """Create LibraryFinanceManager instance"""
    return LibraryFinanceManager(mock_gui)


class TestLibraryFinanceManagerInit:
    """Test LibraryFinanceManager initialization"""

    def test_init_with_valid_gui(self, mock_gui):
        """Test initialization with valid GUI"""
        manager = LibraryFinanceManager(mock_gui)
        assert manager.gui == mock_gui
        assert manager.root == mock_gui.root
        assert manager.conn == mock_gui.conn

    def test_init_colors_defined(self, mock_gui):
        """Test that colors are defined during init"""
        manager = LibraryFinanceManager(mock_gui)
        assert hasattr(manager, 'colors')
        assert 'library' in manager.colors
        assert manager.colors['library'] == '#9b59b6'


class TestEmailHelpers:
    """Test email notification helper methods"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    def test_get_user_email_success(self, mock_get_conn, library_manager):
        """Test getting user email"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = ('test@test.com', 'John', 'Doe')

        result = library_manager.get_user_email('user123')

        assert result is not None
        assert result['email'] == 'test@test.com'
        assert result['first_name'] == 'John'
        assert result['last_name'] == 'Doe'
        assert result['full_name'] == 'John Doe'

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    def test_get_user_email_not_found(self, mock_get_conn, library_manager):
        """Test getting user email when user not found"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = None

        result = library_manager.get_user_email('nonexistent')

        assert result is None

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.send_email_as_system')
    def test_send_fine_notification_email(self, mock_send_email, library_manager):
        """Test sending fine notification email"""
        user_info = {
            'email': 'test@test.com',
            'full_name': 'John Doe'
        }

        result = library_manager.send_fine_notification_email(
            user_info=user_info,
            fine_amount=25.0,
            book_title='Test Book',
            due_date='2024-01-01',
            days_overdue=5
        )

        mock_send_email.assert_called_once()
        assert result is True

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.send_email_as_system')
    def test_send_payment_receipt_email(self, mock_send_email, library_manager):
        """Test sending payment receipt email"""
        user_info = {
            'email': 'test@test.com',
            'full_name': 'John Doe'
        }

        result = library_manager.send_payment_receipt_email(
            user_info=user_info,
            fine_amount=25.0,
            payment_amount=25.0,
            payment_method='Cash',
            book_title='Test Book',
            transaction_id='LIB-123',
            payment_date='2024-01-01'
        )

        mock_send_email.assert_called_once()
        assert result is True

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.send_email_as_system')
    def test_send_fine_waived_email(self, mock_send_email, library_manager):
        """Test sending fine waived email"""
        user_info = {
            'email': 'test@test.com',
            'full_name': 'John Doe'
        }

        result = library_manager.send_fine_waived_email(
            user_info=user_info,
            fine_amount=25.0,
            book_title='Test Book',
            waiver_reason='Administrative action'
        )

        mock_send_email.assert_called_once()
        assert result is True


class TestFineManagement:
    """Test fine management operations"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    def test_load_all_fines(self, mock_get_conn, library_manager):
        """Test loading all fines"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock fines data
        mock_cursor.fetchall.return_value = [
            (1, 'USER001', 'John Doe', 'BOOK001', 'Test Book', 5, 25.0, 'overdue'),
        ]

        # Create mock treeview
        library_manager.fines_tree = Mock()
        library_manager.fines_tree.get_children.return_value = []
        library_manager.fines_summary_label = Mock()

        library_manager.load_all_fines()

        library_manager.fines_tree.insert.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    def test_search_fines(self, mock_get_conn, library_manager):
        """Test searching fines"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchall.return_value = [
            (1, 'USER001', 'John Doe', 'BOOK001', 'Test Book', 5, 25.0, 'overdue'),
        ]

        library_manager.fines_tree = Mock()
        library_manager.fines_tree.get_children.return_value = []
        library_manager.fines_summary_label = Mock()
        library_manager.search_var = tk.StringVar(value='USER001')

        library_manager.search_fines()

        library_manager.fines_tree.insert.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.messagebox')
    def test_create_fine_dialog(self, mock_msgbox, mock_get_conn, library_manager):
        """Test creating fine dialog"""
        library_manager.create_fine_dialog()
        # Dialog created without errors

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.messagebox')
    def test_delete_fine_cancelled(self, mock_msgbox, mock_get_conn, library_manager):
        """Test deleting fine cancelled by user"""
        library_manager.fines_tree = Mock()
        library_manager.fines_tree.selection.return_value = []

        library_manager.delete_fine()

        mock_msgbox.showwarning.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.messagebox')
    def test_delete_fine_confirmed(self, mock_msgbox, mock_get_conn, library_manager):
        """Test deleting fine confirmed"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock loan details
        mock_cursor.fetchone.return_value = ('USER001', 'Test Book')

        library_manager.fines_tree = Mock()
        library_manager.fines_tree.selection.return_value = ['item1']
        library_manager.fines_tree.item.return_value = {
            'values': (1, 'USER001', 'John Doe', 'BOOK001', 'Test Book', 5, '£25.00', 'overdue')
        }
        library_manager.load_all_fines = Mock()

        mock_msgbox.askyesno.return_value = True

        library_manager.delete_fine()

        mock_conn.commit.assert_called_once()


class TestPaymentProcessing:
    """Test payment processing"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.messagebox')
    def test_process_payment_dialog_no_selection(self, mock_msgbox, mock_get_conn, library_manager):
        """Test process payment with no selection"""
        library_manager.fines_tree = Mock()
        library_manager.fines_tree.selection.return_value = []

        library_manager.process_payment_dialog()

        mock_msgbox.showwarning.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    def test_process_payment_dialog_with_selection(self, mock_get_conn, library_manager):
        """Test process payment dialog with selection"""
        library_manager.fines_tree = Mock()
        library_manager.fines_tree.selection.return_value = ['item1']
        library_manager.fines_tree.item.return_value = {
            'values': (1, 'USER001', 'John Doe', 'BOOK001', 'Test Book', 5, '£25.00', 'overdue')
        }

        library_manager.process_payment_dialog()
        # Dialog created without errors


class TestRevenueAnalytics:
    """Test revenue analytics"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.messagebox')
    def test_generate_revenue_report_no_dates(self, mock_msgbox, mock_get_conn, library_manager):
        """Test revenue report with missing dates"""
        library_manager.start_date_var = tk.StringVar(value='')
        library_manager.end_date_var = tk.StringVar(value='')

        library_manager.generate_revenue_report()

        mock_msgbox.showwarning.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    def test_generate_revenue_report_success(self, mock_get_conn, library_manager):
        """Test successful revenue report generation"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock stats
        mock_cursor.fetchone.return_value = (10, 250.0, 25.0)
        # Mock monthly data
        mock_cursor.fetchall.return_value = [
            ('2024-01', 5, 125.0),
            ('2024-02', 5, 125.0),
        ]

        library_manager.start_date_var = tk.StringVar(value='2024-01-01')
        library_manager.end_date_var = tk.StringVar(value='2024-02-29')
        library_manager.revenue_stats_text = Mock()

        library_manager.generate_revenue_report()

        library_manager.revenue_stats_text.delete.assert_called_once()
        library_manager.revenue_stats_text.insert.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.filedialog')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.messagebox')
    def test_export_revenue_csv(self, mock_msgbox, mock_get_conn, mock_filedialog, library_manager):
        """Test exporting revenue to CSV"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchall.return_value = [
            ('2024-01-01', 'ST001', 25.0, 'Cash', 'Payment note'),
        ]

        library_manager.start_date_var = tk.StringVar(value='2024-01-01')
        library_manager.end_date_var = tk.StringVar(value='2024-01-31')
        mock_filedialog.asksaveasfilename.return_value = '/tmp/test.csv'

        with patch('builtins.open', create=True) as mock_open:
            library_manager.export_revenue_csv()

            mock_msgbox.showinfo.assert_called_once()


class TestBookCosts:
    """Test book costs management"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    def test_load_book_costs(self, mock_get_conn, library_manager):
        """Test loading book costs"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock table info
        mock_cursor.fetchall.side_effect = [
            [(0, 'book_id'), (1, 'title'), (2, 'purchase_price')],  # table info
            [('BOOK001', 'Test Book', 'Author', 'ISBN123', 50.0, '2024-01-01', 'Supplier', 1)],  # books
        ]

        library_manager.costs_tree = Mock()
        library_manager.costs_tree.get_children.return_value = []
        library_manager.costs_summary_label = Mock()

        library_manager.load_book_costs()

        library_manager.costs_tree.insert.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    def test_add_book_cost_dialog(self, mock_get_conn, library_manager):
        """Test add book cost dialog"""
        library_manager.add_book_cost_dialog()
        # Dialog created without errors

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.messagebox')
    def test_show_cost_analysis(self, mock_msgbox, mock_get_conn, library_manager):
        """Test showing cost analysis"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = (100, 5000.0, 50.0, 150.0, 10.0)

        library_manager.show_cost_analysis()

        mock_msgbox.showinfo.assert_called_once()


class TestOverviewDashboard:
    """Test overview dashboard"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    def test_refresh_overview(self, mock_get_conn, library_manager):
        """Test refreshing overview dashboard"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock all queries
        mock_cursor.fetchone.side_effect = [
            (500.0,),  # outstanding fines
            (250.0,),  # this month
            (1000.0,),  # YTD
            (10000.0,)  # book investment
        ]

        library_manager.outstanding_fines_label = Mock()
        library_manager.collected_this_month_label = Mock()
        library_manager.total_revenue_ytd_label = Mock()
        library_manager.book_investment_label = Mock()
        library_manager.overview_chart_frame = tk.Frame()
        library_manager.create_overview_chart = Mock()

        library_manager.refresh_overview()

        library_manager.outstanding_fines_label.config.assert_called_once()
        library_manager.collected_this_month_label.config.assert_called_once()
        library_manager.total_revenue_ytd_label.config.assert_called_once()
        library_manager.book_investment_label.config.assert_called_once()
        library_manager.create_overview_chart.assert_called_once()


class TestTabCreation:
    """Test tab creation methods"""

    def test_create_library_finance_tab(self, library_manager):
        """Test creating library finance tab"""
        library_manager.create_fines_section = Mock()
        library_manager.create_revenue_section = Mock()
        library_manager.create_costs_section = Mock()
        library_manager.create_overview_section = Mock()

        library_manager.create_library_finance_tab()

        assert 'library_finance' in library_manager.gui.layout.tab_frames
        library_manager.create_fines_section.assert_called_once()
        library_manager.create_revenue_section.assert_called_once()
        library_manager.create_costs_section.assert_called_once()
        library_manager.create_overview_section.assert_called_once()

    def test_create_metric_card(self, library_manager):
        """Test creating metric card"""
        parent = tk.Frame(library_manager.root)
        library_manager.create_metric_card(parent, "Test Metric", "£100.00", "#3498db")

        # Metric label should be created
        assert hasattr(library_manager, 'test_metric_label')


class TestFineEditing:
    """Test fine editing operations"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.messagebox')
    def test_edit_fine_dialog_no_selection(self, mock_msgbox, library_manager):
        """Test edit fine with no selection"""
        library_manager.fines_tree = Mock()
        library_manager.fines_tree.selection.return_value = []

        library_manager.edit_fine_dialog()

        mock_msgbox.showwarning.assert_called_once()

    def test_edit_fine_dialog_with_selection(self, library_manager):
        """Test edit fine dialog with selection"""
        library_manager.fines_tree = Mock()
        library_manager.fines_tree.selection.return_value = ['item1']
        library_manager.fines_tree.item.return_value = {
            'values': (1, 'USER001', 'John Doe', 'BOOK001', 'Test Book', 5, '£25.00', 'overdue')
        }

        library_manager.edit_fine_dialog()
        # Dialog created without errors


class TestChartGeneration:
    """Test chart generation"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.messagebox')
    def test_show_revenue_charts_no_dates(self, mock_msgbox, mock_get_conn, library_manager):
        """Test showing charts with no dates"""
        library_manager.start_date_var = tk.StringVar(value='')
        library_manager.end_date_var = tk.StringVar(value='')

        library_manager.show_revenue_charts()

        mock_msgbox.showwarning.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.library_finance_manager.messagebox')
    def test_show_revenue_charts_no_data(self, mock_msgbox, mock_get_conn, library_manager):
        """Test showing charts with no data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchall.return_value = []

        library_manager.start_date_var = tk.StringVar(value='2024-01-01')
        library_manager.end_date_var = tk.StringVar(value='2024-01-31')
        library_manager.revenue_chart_frame = tk.Frame()

        library_manager.show_revenue_charts()

        mock_msgbox.showinfo.assert_called_once()
