"""Tests for grade tracking layout manager"""

import pytest
pytestmark = pytest.mark.gui

import unittest
import tkinter as tk
from unittest.mock import Mock, patch
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.layout_manager import LayoutManager

class TestLayoutManager(unittest.TestCase):
    """Test LayoutManager class"""

    def setUp(self):
        """Set up test environment"""
        self.root = tk.Tk()
        self.root.withdraw()

        # Create mock app with required managers
        self.app = Mock()
        self.app.root = self.root
        self.app.auth = Mock()
        self.app.conn = Mock()

        # Mock managers
        self.app.students = Mock()
        self.app.modules = Mock()
        self.app.assessments = Mock()
        self.app.grades = Mock()
        self.app.analytics = Mock()

        # Create layout manager
        self.layout = LayoutManager(self.app)

    def tearDown(self):
        """Clean up test environment"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_layout_manager_initialization(self):
        """Test layout manager initialization"""
        self.assertIsNotNone(self.layout)
        self.assertEqual(self.layout.app, self.app)
        self.assertEqual(self.layout.root, self.root)
        self.assertEqual(self.layout.conn, self.app.conn)

    def test_setup_ui(self):
        """Test setup_ui method creates UI components"""
        # Set up mock methods
        self.app.is_admin = Mock(return_value=True)
        self.app.is_staff = Mock(return_value=False)
        self.app.is_student = Mock(return_value=False)

        self.layout.setup_ui()

        # Check content_frame is created
        self.assertIsNotNone(self.layout.content_frame)
        self.assertTrue(hasattr(self.layout, 'content_frame'))

        # Check status_var is created
        self.assertTrue(hasattr(self.layout, 'status_var'))

    def test_clear_content(self):
        """Test _clear_content method"""
        # Set up UI first
        self.app.is_admin = Mock(return_value=True)
        self.app.is_staff = Mock(return_value=False)
        self.app.is_student = Mock(return_value=False)

        self.layout.setup_ui()

        # Add a widget to content frame
        test_label = tk.Label(self.layout.content_frame, text="Test")
        test_label.pack()

        # Clear content
        self.layout._clear_content()

        # Check widget is destroyed
        children = self.layout.content_frame.winfo_children()
        self.assertEqual(len(children), 0)

    def test_show_student_view(self):
        """Test show_student_view method"""
        self.app.is_admin = Mock(return_value=True)
        self.app.is_staff = Mock(return_value=False)
        self.app.is_student = Mock(return_value=False)
        self.app.students.create_student_content = Mock()

        self.layout.setup_ui()
        # setup_ui() already shows the student view as the default admin/staff
        # view, so reset the mock before exercising show_student_view directly.
        self.app.students.create_student_content.reset_mock()
        self.layout.show_student_view()

        # Should set current_view
        self.assertEqual(self.layout.current_view, "Students")

        # Should call create_student_content
        self.app.students.create_student_content.assert_called_once()

    def test_show_grades_view(self):
        """Test show_grades_view method"""
        self.app.is_admin = Mock(return_value=True)
        self.app.is_staff = Mock(return_value=False)
        self.app.is_student = Mock(return_value=False)
        self.app.grades.create_grades_content = Mock()

        self.layout.setup_ui()
        self.layout.show_grades_view()

        # Should set current_view
        self.assertEqual(self.layout.current_view, "Grades")

        # Should call create_grades_content
        self.app.grades.create_grades_content.assert_called_once()

    def test_widget_exists(self):
        """Test _widget_exists method"""
        # Test with None
        self.assertFalse(self.layout._widget_exists(None))

        # Test with valid widget
        label = tk.Label(self.root)
        self.assertTrue(self.layout._widget_exists(label))

        # Test with destroyed widget
        label.destroy()
        self.assertFalse(self.layout._widget_exists(label))

    def test_update_status(self):
        """Test update_status method"""
        self.app.is_admin = Mock(return_value=True)
        self.app.is_staff = Mock(return_value=False)
        self.app.is_student = Mock(return_value=False)

        self.layout.setup_ui()

        # Should update status_var
        self.layout.update_status("Test message")
        self.assertEqual(self.layout.status_var.get(), "Test message")

class TestLayoutManagerRoleBasedAccess(unittest.TestCase):
    """Test role-based access control in LayoutManager"""

    def setUp(self):
        """Set up test environment"""
        self.root = tk.Tk()
        self.root.withdraw()

        self.app = Mock()
        self.app.root = self.root
        self.app.auth = Mock()
        self.app.conn = Mock()

        # Mock managers
        self.app.students = Mock()
        self.app.modules = Mock()
        self.app.assessments = Mock()
        self.app.grades = Mock()
        self.app.analytics = Mock()

    def tearDown(self):
        """Clean up test environment"""
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_admin_has_all_buttons(self):
        """Test admin users see all navigation buttons"""
        self.app.is_admin = Mock(return_value=True)
        self.app.is_staff = Mock(return_value=False)
        self.app.is_student = Mock(return_value=False)

        layout = LayoutManager(self.app)
        layout.setup_ui()

        # Admin should have many buttons
        self.assertGreater(len(layout.view_buttons), 10)

    def test_student_has_limited_buttons(self):
        """Test student users see limited navigation buttons"""
        self.app.is_admin = Mock(return_value=False)
        self.app.is_staff = Mock(return_value=False)
        self.app.is_student = Mock(return_value=True)

        layout = LayoutManager(self.app)
        layout.setup_ui()

        # Students should have fewer buttons
        self.assertLess(len(layout.view_buttons), 5)

    def test_staff_has_moderate_buttons(self):
        """Test staff users see moderate navigation buttons"""
        self.app.is_admin = Mock(return_value=False)
        self.app.is_staff = Mock(return_value=True)
        self.app.is_student = Mock(return_value=False)

        layout = LayoutManager(self.app)
        layout.setup_ui()

        # Staff should have moderate number of buttons
        button_count = len(layout.view_buttons)
        self.assertGreater(button_count, 5)
        self.assertLess(button_count, 20)

if __name__ == '__main__':
    unittest.main()
