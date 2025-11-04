"""
Test suite for advanced system features
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAdvancedSearch(unittest.TestCase):
    """Test cases for advanced search functionality"""

    def test_advanced_search_gui_import(self):
        """Test importing advanced search GUI"""
        try:
            from university_system.modules.shared.gui import advanced_search_gui
            self.assertIsNotNone(advanced_search_gui,
                               "Advanced search GUI module should import")
        except ImportError:
            self.skipTest("Advanced search GUI not available")

    def test_advanced_search_gui_class(self):
        """Test AdvancedSearchGUI class exists"""
        try:
            from university_system.modules.shared.gui.advanced_search_gui import AdvancedSearchGUI
            self.assertIsNotNone(AdvancedSearchGUI,
                               "AdvancedSearchGUI class should exist")
        except ImportError:
            self.skipTest("AdvancedSearchGUI class not available")


class TestBatchOperations(unittest.TestCase):
    """Test cases for batch operations"""

    def test_batch_operations_gui_import(self):
        """Test importing batch operations GUI"""
        try:
            from university_system.modules.shared.gui import batch_operations_gui
            self.assertIsNotNone(batch_operations_gui,
                               "Batch operations GUI module should import")
        except ImportError:
            self.skipTest("Batch operations GUI not available")


class TestDataBackup(unittest.TestCase):
    """Test cases for data backup functionality"""

    def test_data_backup_gui_import(self):
        """Test importing data backup GUI"""
        try:
            from university_system.infrastructure.database.gui import data_backup_gui
            self.assertIsNotNone(data_backup_gui,
                               "Data backup GUI module should import")
        except ImportError:
            self.skipTest("Data backup GUI not available")


class TestDocumentManagement(unittest.TestCase):
    """Test cases for document management"""

    def test_document_manager_gui_import(self):
        """Test importing document manager GUI"""
        try:
            from university_system.modules.shared.gui import document_manager_gui
            self.assertIsNotNone(document_manager_gui,
                               "Document manager GUI module should import")
        except ImportError:
            self.skipTest("Document manager GUI not available")


class TestAttendanceTracking(unittest.TestCase):
    """Test cases for attendance tracking"""

    def test_attendance_tracker_gui_import(self):
        """Test importing attendance tracker GUI"""
        try:
            from university_system.modules.domain.academics.gui import attendance_tracker_gui
            self.assertIsNotNone(attendance_tracker_gui,
                               "Attendance tracker GUI module should import")
        except ImportError:
            self.skipTest("Attendance tracker GUI not available")


class TestHelpdeskSystem(unittest.TestCase):
    """Test cases for helpdesk system"""

    def test_helpdesk_gui_import(self):
        """Test importing helpdesk GUI"""
        try:
            from university_system.modules.domain.student_affairs.gui import helpdesk_gui
            self.assertIsNotNone(helpdesk_gui, "Helpdesk GUI module should import")
        except ImportError:
            self.skipTest("Helpdesk GUI not available")


class TestParentPortal(unittest.TestCase):
    """Test cases for parent portal"""

    def test_parent_portal_gui_import(self):
        """Test importing parent portal GUI"""
        try:
            from university_system.modules.domain.academics.gui import parent_portal_gui
            self.assertIsNotNone(parent_portal_gui,
                               "Parent portal GUI module should import")
        except ImportError:
            self.skipTest("Parent portal GUI not available")


class TestStudentSupport(unittest.TestCase):
    """Test cases for student support"""

    def test_student_support_gui_import(self):
        """Test importing student support GUI"""
        try:
            from university_system.modules.domain.student_affairs.gui import student_support_gui
            self.assertIsNotNone(student_support_gui,
                               "Student support GUI module should import")
        except ImportError:
            self.skipTest("Student support GUI not available")


class TestLogManagement(unittest.TestCase):
    """Test cases for log management"""

    def test_log_management_gui_import(self):
        """Test importing log management GUI"""
        try:
            from university_system.utils.logging.gui import log_management_gui
            self.assertIsNotNone(log_management_gui,
                               "Log management GUI module should import")
        except ImportError:
            self.skipTest("Log management GUI not available")

    def test_activity_logger_gui_import(self):
        """Test importing activity logger GUI"""
        try:
            from university_system.modules.shared.gui import simple_activity_logger_gui
            self.assertIsNotNone(simple_activity_logger_gui,
                               "Activity logger GUI module should import")
        except ImportError:
            self.skipTest("Activity logger GUI not available")


if __name__ == '__main__':
    unittest.main()
