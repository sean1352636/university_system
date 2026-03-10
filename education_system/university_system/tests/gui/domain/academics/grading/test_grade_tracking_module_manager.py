"""Tests for grade tracking module manager"""

import unittest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch, MagicMock
from education_system.university_system.infrastructure.database.db import sqlite3
import tempfile
import os

from education_system.university_system.modules.domain.academics.gui.grade_tracking.module_manager import ModuleManager

class TestModuleManager(unittest.TestCase):
    """Test ModuleManager class"""

    def setUp(self):
        """Set up test environment"""
        self.root = tk.Tk()
        self.root.withdraw()

        # Create mock app
        self.app = Mock()
        self.app.root = self.root
        self.app.auth = Mock()

        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.conn = sqlite3.connect(self.db_path)
        self.app.conn = self.conn

        # Create mock layout with content frame
        self.app.layout = Mock()
        self.app.layout.content_frame = ttk.Frame(self.root)

        # Create module manager
        self.module_manager = ModuleManager(self.app)

        # Create test tables
        self._create_test_tables()

    def tearDown(self):
        """Clean up test environment"""
        try:
            self.conn.close()
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except (OSError, IOError):
            pass

        try:
            self.root.destroy()
        except (OSError, IOError):
            pass

    def _create_test_tables(self):
        """Create test database tables"""
        cursor = self.conn.cursor()

        cursor.execute('''
            CREATE TABLE modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT,
                module_type TEXT,
                credits INTEGER,
                description TEXT,
                course TEXT,
                semester TEXT,
                year INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                course TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE student_modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                module_code TEXT,
                enrollment_date TEXT,
                status TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (module_code) REFERENCES modules(module_code)
            )
        ''')

        # Insert test data
        cursor.execute("INSERT INTO modules VALUES ('CS101', 'Intro to CS', 'Core', 3, 'Basic CS concepts', 'CS', 'Fall', 2024)")
        cursor.execute("INSERT INTO students VALUES ('STU001', 'John', 'Doe', 'CS')")

        self.conn.commit()

    def test_module_manager_initialization(self):
        """Test module manager initialization"""
        self.assertIsNotNone(self.module_manager)
        self.assertEqual(self.module_manager.app, self.app)
        self.assertEqual(self.module_manager.root, self.root)
        self.assertEqual(self.module_manager.conn, self.conn)

    def test_content_frame_property(self):
        """Test content_frame property"""
        content_frame = self.module_manager.content_frame

        self.assertIsNotNone(content_frame)
        self.assertEqual(content_frame, self.app.layout.content_frame)

    def test_create_module_content(self):
        """Test create_module_content method"""
        self.module_manager.create_module_content()

        # Check that module_tree was created
        self.assertTrue(hasattr(self.module_manager, 'module_tree'))
        self.assertIsNotNone(self.module_manager.module_tree)

    def test_refresh_modules(self):
        """Test refresh_modules method"""
        self.module_manager.create_module_content()

        # Should not raise exception
        self.module_manager.refresh_modules()

        # Check that tree has items
        items = self.module_manager.module_tree.get_children()
        # Should have at least 1 module from test data
        self.assertGreaterEqual(len(items), 1)

    @patch('tkinter.messagebox.showwarning')
    def test_delete_module_no_selection(self, mock_warning):
        """Test delete_module with no selection"""
        self.module_manager.create_module_content()

        self.module_manager.delete_module()

        # Should show warning
        mock_warning.assert_called()

    @patch('tkinter.messagebox.showwarning')
    def test_edit_module_dialog_no_selection(self, mock_warning):
        """Test edit_module_dialog with no selection"""
        self.module_manager.create_module_content()

        self.module_manager.edit_module_dialog()

        # Should show warning
        mock_warning.assert_called()

    @patch('tkinter.messagebox.showwarning')
    def test_manage_module_enrollments_no_selection(self, mock_warning):
        """Test manage_module_enrollments with no selection"""
        self.module_manager.create_module_content()

        self.module_manager.manage_module_enrollments()

        # Should show warning
        mock_warning.assert_called()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.module_manager.get_connection')
    def test_load_courses_for_filter(self, mock_get_connection):
        """Test load_courses_for_filter method"""
        mock_get_connection.return_value = self.conn

        combo = ttk.Combobox(self.root)

        self.module_manager.load_courses_for_filter(combo)

        # Should have values including 'All Courses'
        values = combo['values']
        self.assertIn('All Courses', values)

        combo.destroy()

    def test_refresh_modules_no_tree(self):
        """Test refresh_modules when tree doesn't exist"""
        # Should not raise exception
        self.module_manager.refresh_modules()

class TestModuleManagerEdgeCases(unittest.TestCase):
    """Test edge cases for ModuleManager"""

    def setUp(self):
        """Set up test environment"""
        self.root = tk.Tk()
        self.root.withdraw()

        # Create mock app without layout
        self.app = Mock()
        self.app.root = self.root
        self.app.auth = Mock()
        self.app.conn = Mock()

    def tearDown(self):
        """Clean up test environment"""
        try:
            self.root.destroy()
        except (OSError, IOError):
            pass

    def test_content_frame_no_layout(self):
        """Test content_frame property when layout doesn't exist"""
        # Remove layout attribute
        delattr(self.app, 'layout')

        module_manager = ModuleManager(self.app)

        # Should return None
        self.assertIsNone(module_manager.content_frame)

if __name__ == '__main__':
    unittest.main()
