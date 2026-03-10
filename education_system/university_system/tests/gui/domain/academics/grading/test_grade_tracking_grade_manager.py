"""Tests for grade tracking grade manager"""

import unittest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch, MagicMock
from education_system.university_system.infrastructure.database.db import sqlite3
import tempfile
import os

from education_system.university_system.modules.domain.academics.gui.grade_tracking.grade_manager import GradeManager

class TestGradeManager(unittest.TestCase):
    """Test GradeManager class"""

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

        # Create grade manager
        self.grade_manager = GradeManager(self.app)

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
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                course TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT,
                credits INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE assessments (
                assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_name TEXT,
                module_code TEXT,
                max_points REAL,
                FOREIGN KEY (module_code) REFERENCES modules(module_code)
            )
        ''')

        cursor.execute('''
            CREATE TABLE grades (
                grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                assessment_id INTEGER,
                score REAL,
                letter_grade TEXT,
                submission_date TEXT,
                comments TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id)
            )
        ''')

        # Insert test data
        cursor.execute("INSERT INTO students VALUES ('STU001', 'John', 'Doe', 'CS')")
        cursor.execute("INSERT INTO modules VALUES ('CS101', 'Intro to CS', 3)")
        cursor.execute("INSERT INTO assessments (assessment_name, module_code, max_points) VALUES ('Test 1', 'CS101', 100)")
        cursor.execute("INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date) VALUES ('STU001', 1, 85, 'A', '2024-01-15')")

        self.conn.commit()

    def test_grade_manager_initialization(self):
        """Test grade manager initialization"""
        self.assertIsNotNone(self.grade_manager)
        self.assertEqual(self.grade_manager.app, self.app)
        self.assertEqual(self.grade_manager.root, self.root)
        self.assertEqual(self.grade_manager.conn, self.conn)

    def test_content_frame_property(self):
        """Test content_frame property"""
        content_frame = self.grade_manager.content_frame

        self.assertIsNotNone(content_frame)
        self.assertEqual(content_frame, self.app.layout.content_frame)

    def test_get_safe_cursor(self):
        """Test get_safe_cursor method"""
        cursor = self.grade_manager.get_safe_cursor()

        self.assertIsNotNone(cursor)

    def test_get_safe_cursor_no_connection(self):
        """Test get_safe_cursor raises error when connection is None"""
        self.grade_manager.conn = None
        self.app.conn = None

        with self.assertRaises(ConnectionError):
            self.grade_manager.get_safe_cursor()

    def test_percentage_to_letter(self):
        """Test percentage_to_letter conversion"""
        self.assertEqual(self.grade_manager.percentage_to_letter(95), 'A+')
        self.assertEqual(self.grade_manager.percentage_to_letter(87), 'A-')
        self.assertEqual(self.grade_manager.percentage_to_letter(80), 'B')
        self.assertEqual(self.grade_manager.percentage_to_letter(60), 'D')
        self.assertEqual(self.grade_manager.percentage_to_letter(50), 'F')

    def test_letter_to_gpa(self):
        """Test letter_to_gpa conversion"""
        self.assertEqual(self.grade_manager.letter_to_gpa('A+'), 4.3)
        self.assertEqual(self.grade_manager.letter_to_gpa('A'), 4.0)
        self.assertEqual(self.grade_manager.letter_to_gpa('B'), 3.0)
        self.assertEqual(self.grade_manager.letter_to_gpa('F'), 0.0)

    def test_create_grades_content(self):
        """Test create_grades_content method"""
        self.grade_manager.create_grades_content()

        # Check that grades_tree was created
        self.assertTrue(hasattr(self.grade_manager, 'grades_tree'))
        self.assertIsNotNone(self.grade_manager.grades_tree)

    @patch('tkinter.messagebox.showwarning')
    def test_delete_grade_no_selection(self, mock_warning):
        """Test delete_grade with no selection"""
        self.grade_manager.create_grades_content()

        self.grade_manager.delete_grade()

        # Should show warning
        mock_warning.assert_called()

    @patch('tkinter.messagebox.showwarning')
    def test_edit_grade_dialog_no_selection(self, mock_warning):
        """Test edit_grade_dialog with no selection"""
        self.grade_manager.create_grades_content()

        self.grade_manager.edit_grade_dialog()

        # Should show warning
        mock_warning.assert_called()

    def test_refresh_grades(self):
        """Test refresh_grades method"""
        self.grade_manager.create_grades_content()

        # Should not raise exception
        self.grade_manager.refresh_grades()

        # Check that tree has items
        items = self.grade_manager.grades_tree.get_children()
        # Should have at least 1 grade from test data
        self.assertGreaterEqual(len(items), 1)

    def test_clear_grade_filters(self):
        """Test clear_grade_filters method"""
        self.grade_manager.create_grades_content()

        # Set some filter
        if hasattr(self.grade_manager, 'grade_student_filter_var'):
            self.grade_manager.grade_student_filter_var.set('TEST')

        # Clear filters
        self.grade_manager.clear_grade_filters()

        # Should be empty
        if hasattr(self.grade_manager, 'grade_student_filter_var'):
            self.assertEqual(self.grade_manager.grade_student_filter_var.get(), '')

    def test_filter_grades(self):
        """Test filter_grades method"""
        self.grade_manager.create_grades_content()

        # Should not raise exception
        self.grade_manager.filter_grades()

    def test_populate_filter_combos(self):
        """Test populate_filter_combos method"""
        self.grade_manager.create_grades_content()

        # Should not raise exception
        self.grade_manager.populate_filter_combos()

    @patch('tkinter.filedialog.askopenfilename')
    def test_import_grades_no_file(self, mock_filedialog):
        """Test import_grades with no file selected"""
        mock_filedialog.return_value = ''

        self.grade_manager.import_grades()

        # Should just return without error
        mock_filedialog.assert_called_once()

    def test_calculate_all_gpas(self):
        """Test calculate_all_gpas method"""
        # Should open a dialog showing results
        # We'll just test it doesn't crash
        with patch('tkinter.Toplevel'):
            self.grade_manager.calculate_all_gpas()

    def test_show_grade_statistics(self):
        """Test show_grade_statistics method"""
        # Should open a dialog showing statistics
        with patch('tkinter.Toplevel'):
            self.grade_manager.show_grade_statistics()

class TestGradeManagerEdgeCases(unittest.TestCase):
    """Test edge cases for GradeManager"""

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

        grade_manager = GradeManager(self.app)

        # Should return None
        self.assertIsNone(grade_manager.content_frame)

    def test_content_frame_layout_no_content_frame(self):
        """Test content_frame property when layout has no content_frame"""
        self.app.layout = Mock(spec=[])  # Layout without content_frame

        grade_manager = GradeManager(self.app)

        # Should return None
        self.assertIsNone(grade_manager.content_frame)

if __name__ == '__main__':
    unittest.main()
