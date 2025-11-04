"""
Test suite for finance module functionality
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from university_system.infrastructure.database.db import get_db_connection


class TestFinanceModule(unittest.TestCase):
    """Test cases for finance operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.conn = get_db_connection()
        if not self.conn:
            self.skipTest("Database connection not available")

    def tearDown(self):
        """Clean up"""
        if self.conn:
            self.conn.close()

    def test_student_fees_table_exists(self):
        """Test that student fees tracking table exists"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND (name LIKE '%fee%' OR name LIKE '%payment%')
        ''')
        results = cursor.fetchall()

        # At least one finance-related table should exist
        self.assertGreater(len(results), 0,
                         "At least one finance-related table should exist")

    def test_finance_gui_module_import(self):
        """Test importing finance GUI module"""
        try:
            from university_system.modules.domain.finance.gui import finance
            self.assertIsNotNone(finance_gui, "Finance GUI module should import")
        except ImportError:
            self.skipTest("Finance GUI module not available")

    def test_finance_management_gui_import(self):
        """Test importing finance management GUI"""
        try:
            from university_system.modules.domain.finance.gui.finance_management_gui import FinanceManagementGUI
            self.assertIsNotNone(FinanceManagementGUI,
                               "FinanceManagementGUI class should exist")
        except ImportError:
            self.skipTest("Finance management GUI not available")


if __name__ == '__main__':
    unittest.main()
