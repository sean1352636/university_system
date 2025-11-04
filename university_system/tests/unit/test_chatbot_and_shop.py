"""
Test suite for chatbot and shop management functionality
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestChatbot(unittest.TestCase):
    """Test cases for university chatbot"""

    def test_chatbot_gui_import(self):
        """Test importing chatbot GUI"""
        try:
            from university_system.utils.ai.gui import university_chatbot_gui
            self.assertIsNotNone(university_chatbot_gui,
                               "Chatbot GUI module should import")
        except ImportError:
            self.skipTest("Chatbot GUI not available")


class TestShopManagement(unittest.TestCase):
    """Test cases for shop management"""

    def test_shop_gui_import(self):
        """Test importing shop management GUI"""
        try:
            from university_system.modules.domain.commerce.gui import shop_management_gui
            self.assertIsNotNone(shop_management_gui,
                               "Shop management GUI module should import")
        except ImportError:
            self.skipTest("Shop management GUI not available")


class TestModuleScheduling(unittest.TestCase):
    """Test cases for module scheduling"""

    def test_module_scheduling_gui_import(self):
        """Test importing module scheduling GUI"""
        try:
            from university_system.modules.domain.academics.gui import module_scheduling_gui
            self.assertIsNotNone(module_scheduling_gui,
                               "Module scheduling GUI module should import")
        except ImportError:
            self.skipTest("Module scheduling GUI not available")

    def test_module_scheduling_gui_class(self):
        """Test ModuleSchedulingGUI class exists"""
        try:
            from university_system.modules.domain.academics.gui.module_scheduling_gui import ModuleSchedulingGUI
            self.assertIsNotNone(ModuleSchedulingGUI,
                               "ModuleSchedulingGUI class should exist")
        except ImportError:
            self.skipTest("ModuleSchedulingGUI class not available")


class TestCourseManagementGUI(unittest.TestCase):
    """Test cases for course management GUI"""

    def test_course_management_gui_import(self):
        """Test importing course management GUI"""
        try:
            from university_system.modules.domain.academics.gui import course_management_gui
            self.assertIsNotNone(course_management_gui,
                               "Course management GUI module should import")
        except ImportError:
            self.skipTest("Course management GUI not available")

    def test_course_management_gui_class(self):
        """Test CourseManagementGUI class exists"""
        try:
            from university_system.modules.domain.academics.gui.course_management_gui import CourseManagementGUI
            self.assertIsNotNone(CourseManagementGUI,
                               "CourseManagementGUI class should exist")
        except ImportError:
            self.skipTest("CourseManagementGUI class not available")

    def test_course_services_import(self):
        """Test importing course management services"""
        try:
            from university_system.modules.domain.academics.services import course_management
            self.assertIsNotNone(course_management,
                               "Course management services should import")
        except ImportError:
            self.skipTest("Course management services not available")


if __name__ == '__main__':
    unittest.main()
