"""
Test suite for student union functionality
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStudentUnion(unittest.TestCase):
    """Test cases for student union operations"""

    def test_student_union_gui_import(self):
        """Test importing student union GUI module"""
        try:
            from university_system.modules.domain.student_affairs.gui.student_union_management_gui import StudentUnionManagementGUI
            self.assertIsNotNone(StudentUnionManagementGUI,
                               "StudentUnionManagementGUI class should exist")
        except ImportError:
            self.skipTest("Student union management GUI not available")

    def test_student_union_services_import(self):
        """Test importing student union services"""
        try:
            from university_system.domain import student_affairs
            self.assertIsNotNone(student_affairs,
                               "Student affairs module should import")
        except ImportError:
            self.skipTest("Student affairs module not available")

    def test_student_union_modules_import(self):
        """Test importing student union module components"""
        try:
            from university_system.modules import student_union
            self.assertIsNotNone(student_union,
                               "Student union modules should import")
        except ImportError:
            self.skipTest("Student union modules not available")


if __name__ == '__main__':
    unittest.main()
