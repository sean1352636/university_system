"""Tests for grade tracking main application"""

import unittest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
import sqlite3
import tempfile
import os

from university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app import GradeTrackingApp


class TestGradeTrackingApp(unittest.TestCase):
    """Test GradeTrackingApp class"""

    def setUp(self):
        """Set up test environment"""
        self.root = tk.Tk()
        self.root.withdraw()

        # Create mock auth
        self.auth = Mock()
        self.auth.current_user = {'role': 'admin'}

        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')

    def tearDown(self):
        """Clean up test environment"""
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except (OSError, IOError):
            pass

        try:
            self.root.destroy()
        except (OSError, IOError):
            pass

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_app_initialization(self, mock_get_connection):
        """Test app initialization"""
        # Mock database connection
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        app = GradeTrackingApp(self.root, auth=self.auth)

        self.assertIsNotNone(app)
        self.assertEqual(app.root, self.root)
        self.assertEqual(app.auth, self.auth)
        self.assertIsNotNone(app.conn)

        app.root.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_app_has_managers(self, mock_get_connection):
        """Test app has all required managers"""
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        app = GradeTrackingApp(self.root, auth=self.auth)

        # Check managers exist
        self.assertTrue(hasattr(app, 'layout'))
        self.assertTrue(hasattr(app, 'students'))
        self.assertTrue(hasattr(app, 'modules'))
        self.assertTrue(hasattr(app, 'assessments'))
        self.assertTrue(hasattr(app, 'grades'))
        self.assertTrue(hasattr(app, 'analytics'))

        app.root.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_get_user_role(self, mock_get_connection):
        """Test get_user_role method"""
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        app = GradeTrackingApp(self.root, auth=self.auth)

        role = app.get_user_role()
        self.assertEqual(role, 'admin')

        app.root.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_is_admin(self, mock_get_connection):
        """Test is_admin method"""
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        app = GradeTrackingApp(self.root, auth=self.auth)

        self.assertTrue(app.is_admin())

        app.root.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_is_staff(self, mock_get_connection):
        """Test is_staff method"""
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        # Change role to staff
        self.auth.current_user = {'role': 'staff'}

        app = GradeTrackingApp(self.root, auth=self.auth)

        self.assertTrue(app.is_staff())
        self.assertFalse(app.is_admin())

        app.root.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_is_student(self, mock_get_connection):
        """Test is_student method"""
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        # Change role to student
        self.auth.current_user = {'role': 'student'}

        app = GradeTrackingApp(self.root, auth=self.auth)

        self.assertTrue(app.is_student())
        self.assertFalse(app.is_admin())

        app.root.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_percentage_to_letter(self, mock_get_connection):
        """Test percentage_to_letter method"""
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        app = GradeTrackingApp(self.root, auth=self.auth)

        self.assertEqual(app.percentage_to_letter(95), 'A+')
        self.assertEqual(app.percentage_to_letter(80), 'B')
        self.assertEqual(app.percentage_to_letter(50), 'F')

        app.root.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_letter_to_gpa(self, mock_get_connection):
        """Test letter_to_gpa method"""
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        app = GradeTrackingApp(self.root, auth=self.auth)

        self.assertEqual(app.letter_to_gpa('A+'), 4.3)
        self.assertEqual(app.letter_to_gpa('A'), 4.0)
        self.assertEqual(app.letter_to_gpa('B'), 3.0)

        app.root.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_widget_exists(self, mock_get_connection):
        """Test _widget_exists method"""
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        app = GradeTrackingApp(self.root, auth=self.auth)

        # Test with None
        self.assertFalse(app._widget_exists(None))

        # Test with valid widget
        label = tk.Label(self.root)
        self.assertTrue(app._widget_exists(label))

        # Test with destroyed widget
        label.destroy()
        self.assertFalse(app._widget_exists(label))

        app.root.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_update_status(self, mock_get_connection):
        """Test update_status method"""
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        app = GradeTrackingApp(self.root, auth=self.auth)

        # Should not raise exception
        app.update_status("Test message")

        app.root.destroy()


class TestGradeTrackingAppNoAuth(unittest.TestCase):
    """Test GradeTrackingApp without authentication"""

    def setUp(self):
        """Set up test environment"""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Clean up test environment"""
        try:
            self.root.destroy()
        except (OSError, IOError):
            pass

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_app_without_auth(self, mock_get_connection):
        """Test app initialization without auth"""
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        app = GradeTrackingApp(self.root, auth=None)

        self.assertIsNotNone(app)
        self.assertIsNone(app.auth)

        # get_user_role should return None
        self.assertIsNone(app.get_user_role())

        app.root.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app.get_connection')
    def test_role_checks_without_auth(self, mock_get_connection):
        """Test role checking methods without auth"""
        conn = sqlite3.connect(':memory:')
        mock_get_connection.return_value = conn

        app = GradeTrackingApp(self.root, auth=None)

        self.assertFalse(app.is_admin())
        self.assertFalse(app.is_staff())
        self.assertFalse(app.is_student())

        app.root.destroy()


if __name__ == '__main__':
    unittest.main()
