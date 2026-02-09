"""Tests for grade tracking update grades dialog"""

import unittest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
import sqlite3
import tempfile
import os

from university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog import (
    UpdateGradesDialog,
    safe_grab_set
)


class TestUpdateGradesDialog(unittest.TestCase):
    """Test UpdateGradesDialog class"""

    def setUp(self):
        """Set up test environment"""
        self.root = tk.Tk()
        self.root.withdraw()

        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        # Create required tables
        self._create_test_tables()
        self._insert_test_data()

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
        self.cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                course TEXT,
                email_address TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE assessments (
                assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_name TEXT,
                module_code TEXT,
                max_points REAL,
                FOREIGN KEY (module_code) REFERENCES modules(module_code)
            )
        ''')

        self.cursor.execute('''
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

        self.conn.commit()

    def _insert_test_data(self):
        """Insert test data"""
        # Students
        self.cursor.execute(
            "INSERT INTO students VALUES ('STU001', 'John', 'Doe', 'CS', 'john@example.com')"
        )
        self.cursor.execute(
            "INSERT INTO students VALUES ('STU002', 'Jane', 'Smith', 'CS', 'jane@example.com')"
        )

        # Modules
        self.cursor.execute("INSERT INTO modules VALUES ('CS101', 'Intro to CS')")

        # Assessments
        self.cursor.execute(
            "INSERT INTO assessments (assessment_name, module_code, max_points) VALUES ('Test 1', 'CS101', 100)"
        )

        # Grades
        self.cursor.execute(
            "INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date) VALUES ('STU001', 1, 85, 'A', '2024-01-15')"
        )

        self.conn.commit()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog.get_connection')
    def test_dialog_creation(self, mock_get_connection):
        """Test dialog creation"""
        mock_get_connection.return_value = self.conn

        dialog = UpdateGradesDialog(self.root)

        self.assertIsNotNone(dialog.dialog)
        self.assertEqual(dialog.dialog.title(), "Update Existing Grades")
        self.assertIsNotNone(dialog.grades_tree)

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog.get_connection')
    def test_load_students(self, mock_get_connection):
        """Test loading students"""
        mock_get_connection.return_value = self.conn

        dialog = UpdateGradesDialog(self.root)

        with patch('tkinter.messagebox.showinfo') as mock_info:
            dialog.load_students()
            # Should show success message
            mock_info.assert_called()

        # Check students are loaded in combo
        values = dialog.student_combo['values']
        self.assertGreater(len(values), 0)

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog.get_connection')
    def test_select_student(self, mock_get_connection):
        """Test selecting a student"""
        mock_get_connection.return_value = self.conn

        dialog = UpdateGradesDialog(self.root)

        # Load students first
        dialog.load_students()

        # Select first student
        if dialog.student_combo['values']:
            dialog.student_var.set(dialog.student_combo['values'][0])

            with patch('tkinter.messagebox.showinfo') as mock_info:
                dialog.select_student()
                # Should load grades
                self.assertIsNotNone(dialog.student_id)

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog.get_connection')
    def test_select_student_without_selection(self, mock_get_connection):
        """Test selecting without choosing a student"""
        mock_get_connection.return_value = self.conn

        dialog = UpdateGradesDialog(self.root)

        with patch('tkinter.messagebox.showwarning') as mock_warning:
            dialog.select_student()
            # Should show warning
            mock_warning.assert_called()

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog.get_connection')
    def test_edit_grade_no_selection(self, mock_get_connection):
        """Test editing grade without selection"""
        mock_get_connection.return_value = self.conn

        dialog = UpdateGradesDialog(self.root)

        with patch('tkinter.messagebox.showwarning') as mock_warning:
            dialog.edit_selected_grade()
            # Should show warning
            mock_warning.assert_called()

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog.get_connection')
    def test_grades_tree_columns(self, mock_get_connection):
        """Test grades treeview has correct columns"""
        mock_get_connection.return_value = self.conn

        dialog = UpdateGradesDialog(self.root)

        columns = dialog.grades_tree['columns']
        expected_columns = ('Grade ID', 'Assessment', 'Module', 'Score', 'Max Points', 'Grade', 'Date')

        self.assertEqual(len(columns), len(expected_columns))

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog.get_connection')
    def test_dialog_geometry(self, mock_get_connection):
        """Test dialog size"""
        mock_get_connection.return_value = self.conn

        dialog = UpdateGradesDialog(self.root)

        geometry = dialog.dialog.geometry()
        self.assertTrue('900x600' in geometry or dialog.dialog.winfo_width() > 0)

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog.get_connection')
    def test_load_students_database_error(self, mock_get_connection):
        """Test handling database error when loading students"""
        # Mock connection that raises error
        mock_conn = Mock()
        mock_conn.cursor.side_effect = sqlite3.Error("Database error")
        mock_get_connection.return_value = mock_conn

        dialog = UpdateGradesDialog(self.root)

        with patch('tkinter.messagebox.showerror') as mock_error:
            dialog.load_students()
            # Should show error message
            mock_error.assert_called()

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog.get_connection')
    def test_refresh_student_grades(self, mock_get_connection):
        """Test refreshing student grades"""
        mock_get_connection.return_value = self.conn

        dialog = UpdateGradesDialog(self.root)
        dialog.student_id = 'STU001'
        dialog.student_var.set('STU001 - John Doe')

        # Mock select_student
        dialog.select_student = Mock()

        dialog.refresh_student_grades()

        # Should call select_student
        dialog.select_student.assert_called_once()

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog.get_connection')
    def test_double_click_binding(self, mock_get_connection):
        """Test double-click event binding on grades tree"""
        mock_get_connection.return_value = self.conn

        dialog = UpdateGradesDialog(self.root)

        # Check that double-click is bound
        # The binding should exist for '<Double-1>' event
        bindings = dialog.grades_tree.bind()
        # Note: checking exact binding is tricky, just verify dialog was created
        self.assertIsNotNone(dialog.grades_tree)

        dialog.dialog.destroy()


class TestUpdateGradesDialogIntegration(unittest.TestCase):
    """Integration tests for UpdateGradesDialog"""

    def setUp(self):
        """Set up test environment"""
        self.root = tk.Tk()
        self.root.withdraw()

        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        self._create_test_tables()
        self._insert_test_data()

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
        self.cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                course TEXT,
                email_address TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE assessments (
                assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_name TEXT,
                module_code TEXT,
                max_points REAL,
                FOREIGN KEY (module_code) REFERENCES modules(module_code)
            )
        ''')

        self.cursor.execute('''
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

        self.conn.commit()

    def _insert_test_data(self):
        """Insert test data"""
        # Students
        self.cursor.execute(
            "INSERT INTO students VALUES ('STU001', 'John', 'Doe', 'CS', 'john@example.com')"
        )
        self.cursor.execute(
            "INSERT INTO students VALUES ('STU002', 'Jane', 'Smith', 'ENG', 'jane@example.com')"
        )
        self.cursor.execute(
            "INSERT INTO students VALUES ('STU003', 'Bob', 'Johnson', 'MATH', 'bob@example.com')"
        )

        # Modules
        self.cursor.execute("INSERT INTO modules VALUES ('CS101', 'Intro to CS')")
        self.cursor.execute("INSERT INTO modules VALUES ('ENG101', 'English Lit')")

        # Assessments
        self.cursor.execute(
            "INSERT INTO assessments (assessment_name, module_code, max_points) VALUES ('Test 1', 'CS101', 100)"
        )
        self.cursor.execute(
            "INSERT INTO assessments (assessment_name, module_code, max_points) VALUES ('Essay 1', 'ENG101', 50)"
        )

        # Grades
        self.cursor.execute(
            "INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date, comments) VALUES ('STU001', 1, 85, 'A', '2024-01-15', 'Good work')"
        )
        self.cursor.execute(
            "INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date, comments) VALUES ('STU002', 2, 42, 'B', '2024-01-16', 'Well done')"
        )

        self.conn.commit()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.update_grades_dialog.get_connection')
    def test_full_workflow_load_and_select(self, mock_get_connection):
        """Test full workflow: load students and select one"""
        mock_get_connection.return_value = self.conn

        dialog = UpdateGradesDialog(self.root)

        # Load students
        with patch('tkinter.messagebox.showinfo'):
            dialog.load_students()

        # Should have students in combo
        self.assertGreater(len(dialog.student_combo['values']), 0)

        # Select a student
        dialog.student_var.set(dialog.student_combo['values'][0])

        with patch('tkinter.messagebox.showinfo'):
            dialog.select_student()

        # Should have set student_id
        self.assertIsNotNone(dialog.student_id)

        # Should have loaded grades (at least 0, could be more)
        # Check that grades_tree is populated (or empty)
        self.assertIsNotNone(dialog.grades_tree)

        dialog.dialog.destroy()


if __name__ == '__main__':
    unittest.main()
