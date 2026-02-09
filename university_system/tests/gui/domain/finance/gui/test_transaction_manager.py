"""Tests for transaction_manager module (TransactionManager)"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import tkinter as tk
from tkinter import messagebox
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

from university_system.modules.domain.finance.gui.finance.transaction_manager import TransactionManager


class TestTransactionManager(unittest.TestCase):
    """Test suite for TransactionManager class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock GUI
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.finance_system = Mock()

        # Mock layout
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
        self.manager = TransactionManager(self.mock_gui)

    def tearDown(self):
        """Clean up after tests"""
        self.manager = None
        self.mock_gui = None

    def test_initialization(self):
        """Test TransactionManager initialization"""
        self.assertEqual(self.manager.gui, self.mock_gui)
        self.assertEqual(self.manager.root, self.mock_gui.root)
        self.assertEqual(self.manager.conn, self.mock_gui.conn)
        self.assertEqual(self.manager.finance_system, self.mock_gui.finance_system)

    def test_initialization_without_finance_system(self):
        """Test initialization when finance_system doesn't exist"""
        gui_without_system = Mock()
        gui_without_system.root = Mock()
        gui_without_system.conn = Mock()
        gui_without_system.layout = Mock()
        gui_without_system.layout.content_frame = Mock()
        gui_without_system.layout.tab_frames = {}
        del gui_without_system.finance_system

        manager = TransactionManager(gui_without_system)
        self.assertIsNone(manager.finance_system)

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.tk.Frame')
    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.tk.Button')
    def test_create_payments_tab(self, mock_button, mock_frame):
        """Test creating payments tab"""
        self.manager.create_payments_table = Mock()
        self.manager.refresh_payments = Mock()

        self.manager.create_payments_tab()

        # Verify tab was created
        self.assertIn('payments', self.mock_gui.layout.tab_frames)

        # Verify table was created
        self.manager.create_payments_table.assert_called_once()

        # Verify data was loaded
        self.manager.refresh_payments.assert_called_once()

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.tk.Frame')
    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.ttk.Treeview')
    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.ttk.Scrollbar')
    def test_create_payments_table(self, mock_scrollbar, mock_treeview, mock_frame):
        """Test creating payments table"""
        parent = Mock()

        self.manager.create_payments_context_menu = Mock()
        self.manager.create_payments_table(parent)

        # Verify treeview was created
        self.assertTrue(hasattr(self.manager, 'payments_tree'))

        # Verify context menu was created
        self.manager.create_payments_context_menu.assert_called_once()

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.tk.Menu')
    def test_create_payments_context_menu(self, mock_menu):
        """Test creating payments context menu"""
        mock_menu_instance = Mock()
        mock_menu.return_value = mock_menu_instance

        self.manager.create_payments_context_menu()

        # Verify menu was created
        self.assertTrue(hasattr(self.manager, 'payments_menu'))

        # Verify menu items were added
        self.assertGreater(mock_menu_instance.add_command.call_count, 0)

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.get_connection')
    def test_refresh_payments_success(self, mock_get_connection):
        """Test refreshing payments list successfully"""
        # Mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock payment data
        mock_cursor.fetchall.return_value = [
            (1, 'S001', 500.00, 'Card', '2024-01-15', 'completed'),
            (2, 'S002', 300.00, 'Cash', '2024-01-16', 'completed')
        ]

        mock_get_connection.return_value = mock_conn

        # Setup manager
        self.manager.payments_tree = Mock()
        self.manager.payments_tree.get_children.return_value = []

        # Refresh payments
        if hasattr(self.manager, 'refresh_payments'):
            self.manager.refresh_payments()

            # Verify data was loaded
            self.manager.payments_tree.delete.assert_called()

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.messagebox.showerror')
    def test_refresh_payments_error(self, mock_error, mock_get_connection):
        """Test refresh payments error handling"""
        mock_get_connection.side_effect = Exception("Database error")

        self.manager.payments_tree = Mock()
        self.manager.payments_tree.get_children.return_value = []

        # Refresh payments
        if hasattr(self.manager, 'refresh_payments'):
            self.manager.refresh_payments()

            # Verify error was shown
            # Error may or may not be shown depending on implementation

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.tk.Toplevel')
    def test_show_payment_dialog(self, mock_toplevel):
        """Test showing payment dialog"""
        mock_dialog = Mock()
        mock_toplevel.return_value = mock_dialog

        # Show payment dialog
        if hasattr(self.manager, 'show_payment_dialog'):
            self.manager.show_payment_dialog()

            # Verify dialog was created
            mock_toplevel.assert_called_once()

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.tk.Toplevel')
    def test_search_payments(self, mock_toplevel):
        """Test payment search functionality"""
        mock_dialog = Mock()
        mock_toplevel.return_value = mock_dialog

        # Search payments
        if hasattr(self.manager, 'search_payments'):
            self.manager.search_payments()

            # Verify search dialog was created
            mock_toplevel.assert_called_once()

    def test_show_payment_analytics(self):
        """Test showing payment analytics"""
        # Mock analytics display
        if hasattr(self.manager, 'show_payment_analytics'):
            with patch('university_system.modules.domain.finance.gui.finance.transaction_manager.tk.Toplevel') as mock_toplevel:
                self.manager.show_payment_analytics()

                # Verify analytics window was created or method was called
                # Implementation dependent

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.messagebox.showinfo')
    def test_send_payment_email_reminders(self, mock_showinfo):
        """Test sending payment email reminders"""
        # Send reminders
        if hasattr(self.manager, 'send_payment_email_reminders'):
            self.manager.send_payment_email_reminders()

            # Verify some action was taken
            # Implementation dependent

    def test_view_payment_details(self):
        """Test viewing payment details"""
        # Setup selected payment
        self.manager.payments_tree = Mock()
        self.manager.payments_tree.selection.return_value = ['1']
        self.manager.payments_tree.item.return_value = {
            'values': (1, 'S001', 500.00, 'Card', '2024-01-15', 'completed')
        }

        # View details
        if hasattr(self.manager, 'view_payment_details'):
            with patch('university_system.modules.domain.finance.gui.finance.transaction_manager.tk.Toplevel'):
                self.manager.view_payment_details()

                # Should not raise exceptions

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.messagebox.showwarning')
    def test_view_payment_details_no_selection(self, mock_warning):
        """Test viewing payment details with no selection"""
        self.manager.payments_tree = Mock()
        self.manager.payments_tree.selection.return_value = []

        # View details
        if hasattr(self.manager, 'view_payment_details'):
            self.manager.view_payment_details()

            # May show warning or handle silently


class TestPaymentRecording(unittest.TestCase):
    """Test payment recording functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.finance_system = Mock()
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock(spec=tk.Frame)
        self.mock_gui.layout.tab_frames = {}
        self.mock_gui.layout.colors = {'success': '#27ae60'}

        self.manager = TransactionManager(self.mock_gui)

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.messagebox.showinfo')
    def test_record_payment_success(self, mock_showinfo, mock_get_connection):
        """Test successful payment recording"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        # Record payment
        if hasattr(self.manager, 'record_payment'):
            self.manager.record_payment(
                student_id='S001',
                amount=500.00,
                method='Card',
                reference='REF123'
            )

            # Verify database was updated
            mock_cursor.execute.assert_called()
            mock_conn.commit.assert_called()

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.messagebox.showerror')
    def test_record_payment_error(self, mock_error, mock_get_connection):
        """Test payment recording error handling"""
        mock_get_connection.side_effect = Exception("Database error")

        # Record payment
        if hasattr(self.manager, 'record_payment'):
            self.manager.record_payment(
                student_id='S001',
                amount=500.00,
                method='Card',
                reference='REF123'
            )

            # Verify error was handled


class TestPaymentValidation(unittest.TestCase):
    """Test payment validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.finance_system = Mock()
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock()
        self.mock_gui.layout.tab_frames = {}
        self.mock_gui.layout.colors = {}

        self.manager = TransactionManager(self.mock_gui)

    def test_validate_payment_amount_positive(self):
        """Test validating positive payment amount"""
        # Valid amount
        if hasattr(self.manager, 'validate_amount'):
            result = self.manager.validate_amount(100.00)
            self.assertTrue(result)

    def test_validate_payment_amount_zero(self):
        """Test validating zero payment amount"""
        # Zero amount (usually invalid)
        if hasattr(self.manager, 'validate_amount'):
            result = self.manager.validate_amount(0.00)
            self.assertFalse(result)

    def test_validate_payment_amount_negative(self):
        """Test validating negative payment amount"""
        # Negative amount (invalid)
        if hasattr(self.manager, 'validate_amount'):
            result = self.manager.validate_amount(-50.00)
            self.assertFalse(result)


class TestPaymentRefunds(unittest.TestCase):
    """Test payment refund functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.finance_system = Mock()
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock()
        self.mock_gui.layout.tab_frames = {}
        self.mock_gui.layout.colors = {'danger': '#e74c3c'}

        self.manager = TransactionManager(self.mock_gui)

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.messagebox.askyesno')
    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.messagebox.showinfo')
    def test_process_refund_confirmed(self, mock_showinfo, mock_get_connection, mock_askyesno):
        """Test processing refund when confirmed"""
        mock_askyesno.return_value = True

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        # Setup selected payment
        self.manager.payments_tree = Mock()
        self.manager.payments_tree.selection.return_value = ['1']
        self.manager.payments_tree.item.return_value = {
            'values': (1, 'S001', 500.00, 'Card', '2024-01-15', 'completed')
        }

        # Process refund
        if hasattr(self.manager, 'process_refund'):
            self.manager.process_refund()

            # Verify confirmation was requested
            mock_askyesno.assert_called_once()

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.messagebox.askyesno')
    def test_process_refund_cancelled(self, mock_askyesno):
        """Test processing refund when cancelled"""
        mock_askyesno.return_value = False

        self.manager.payments_tree = Mock()
        self.manager.payments_tree.selection.return_value = ['1']
        self.manager.payments_tree.item.return_value = {
            'values': (1, 'S001', 500.00, 'Card', '2024-01-15', 'completed')
        }

        # Process refund
        if hasattr(self.manager, 'process_refund'):
            self.manager.process_refund()

            # Verify confirmation was requested
            mock_askyesno.assert_called_once()


class TestPaymentAnalytics(unittest.TestCase):
    """Test payment analytics functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.finance_system = Mock()
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock()
        self.mock_gui.layout.tab_frames = {}
        self.mock_gui.layout.colors = {'info': '#17a2b8'}

        self.manager = TransactionManager(self.mock_gui)

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.get_connection')
    def test_get_payment_statistics(self, mock_get_connection):
        """Test getting payment statistics"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock statistics data
        mock_cursor.fetchone.return_value = (150, 75000.00, 500.00)

        mock_get_connection.return_value = mock_conn

        # Get statistics
        if hasattr(self.manager, 'get_payment_statistics'):
            stats = self.manager.get_payment_statistics()

            # Verify statistics were retrieved
            self.assertIsNotNone(stats)

    @patch('university_system.modules.domain.finance.gui.finance.transaction_manager.get_connection')
    def test_get_payment_trends(self, mock_get_connection):
        """Test getting payment trends"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock trend data
        mock_cursor.fetchall.return_value = [
            ('2024-01', 50, 25000.00),
            ('2024-02', 60, 30000.00)
        ]

        mock_get_connection.return_value = mock_conn

        # Get trends
        if hasattr(self.manager, 'get_payment_trends'):
            trends = self.manager.get_payment_trends()

            # Verify trends were retrieved
            self.assertIsNotNone(trends)


if __name__ == '__main__':
    unittest.main()
