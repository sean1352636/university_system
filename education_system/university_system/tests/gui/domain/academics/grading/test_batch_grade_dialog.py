"""
Tests for Batch Grade Dialog

This module tests the BatchGradeDialog class which provides
a dialog for batch grade entry for multiple students.
"""

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, MagicMock, patch, call
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

from education_system.university_system.modules.domain.academics.gui.grade_tracking.dialogs.batch_grade_dialog import (
    BatchGradeDialog, percentage_to_letter
)

@pytest.fixture
def root_window():
    """Create a root Tkinter window for testing"""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except Exception:
        pass

@pytest.fixture
def mock_connection():
    """Create a mock database connection and cursor"""
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value = cursor
    conn.commit = Mock()
    return conn, cursor

class TestBatchGradeDialog:
    """Test suite for BatchGradeDialog"""

    def test_initialization(self, root_window, mock_connection):
        """Test dialog initialization"""
        conn, cursor = mock_connection

        dialog = BatchGradeDialog(root_window, cursor, conn)

        assert dialog.dialog is not None
        assert dialog.cursor == cursor
        assert dialog.conn == conn
        assert dialog.result is None
        assert dialog.assessment_id is None
        assert dialog.max_points == 0

    def test_dialog_widgets_created(self, root_window, mock_connection):
        """Test that all dialog widgets are created"""
        conn, cursor = mock_connection

        dialog = BatchGradeDialog(root_window, cursor, conn)

        assert hasattr(dialog, 'assessment_var')
        assert hasattr(dialog, 'students_tree')
        assert hasattr(dialog, 'quick_score_var')

    def test_load_assessments(self, root_window, mock_connection):
        """Test loading assessments into combobox"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            (1, 'Midterm Exam', 'CS101'),
            (2, 'Final Project', 'CS102'),
            (3, 'Quiz 1', 'MATH201')
        ]

        dialog = BatchGradeDialog(root_window, cursor, conn)

        # Create a mock combobox
        combo = Mock()
        combo.__setitem__ = Mock()

        with patch('tkinter.messagebox.showinfo'):
            dialog.load_assessments(combo)

        cursor.execute.assert_called()
        cursor.fetchall.assert_called()

    def test_load_students_success(self, root_window, mock_connection):
        """Test loading students for selected assessment"""
        conn, cursor = mock_connection

        # Mock assessment selection
        cursor.fetchone.return_value = (100, 'CS101')  # max_points, module_code
        cursor.fetchall.side_effect = [
            # Students enrolled in module
            [
                ('student001', 'John', 'Doe'),
                ('student002', 'Jane', 'Smith')
            ]
        ]

        dialog = BatchGradeDialog(root_window, cursor, conn)
        dialog.assessment_var.set('1 - [CS101] Midterm Exam')

        with patch('tkinter.messagebox.showinfo'):
            dialog.load_students()

        # Verify students were loaded
        assert dialog.assessment_id == 1
        assert dialog.max_points == 100
        assert len(dialog.students_tree.get_children()) == 2

    @patch('tkinter.messagebox.showwarning')
    def test_load_students_no_assessment_selected(self, mock_warning, root_window, mock_connection):
        """Test loading students with no assessment selected"""
        conn, cursor = mock_connection

        dialog = BatchGradeDialog(root_window, cursor, conn)

        dialog.load_students()

        mock_warning.assert_called_once()

    def test_apply_quick_score_to_all(self, root_window, mock_connection):
        """Test applying quick score to all students"""
        conn, cursor = mock_connection

        dialog = BatchGradeDialog(root_window, cursor, conn)
        dialog.max_points = 100

        # Add test students to tree
        dialog.students_tree.insert('', 'end', values=('student001', 'John Doe', '', '', '', ''))
        dialog.students_tree.insert('', 'end', values=('student002', 'Jane Smith', '', '', '', ''))

        dialog.quick_score_var.set('85')
        dialog.apply_quick_score()

        # Verify scores were applied
        for item in dialog.students_tree.get_children():
            values = dialog.students_tree.item(item, 'values')
            assert values[3] == '85.0'  # New Score
            assert values[4] == 'A'      # Grade

    def test_apply_quick_score_to_selected(self, root_window, mock_connection):
        """Test applying quick score to selected students only"""
        conn, cursor = mock_connection

        dialog = BatchGradeDialog(root_window, cursor, conn)
        dialog.max_points = 100

        # Add test students
        item1 = dialog.students_tree.insert('', 'end', values=('student001', 'John Doe', '', '', '', ''))
        item2 = dialog.students_tree.insert('', 'end', values=('student002', 'Jane Smith', '', '', '', ''))

        # Select only first student
        dialog.students_tree.selection_set(item1)

        dialog.quick_score_var.set('90')
        dialog.apply_quick_score()

        # Only first student should have score
        values1 = dialog.students_tree.item(item1, 'values')
        values2 = dialog.students_tree.item(item2, 'values')

        assert values1[3] == '90.0'
        assert values2[3] == ''  # Still empty

    @patch('tkinter.messagebox.showerror')
    def test_apply_quick_score_invalid_score(self, mock_error, root_window, mock_connection):
        """Test validation for invalid quick score"""
        conn, cursor = mock_connection

        dialog = BatchGradeDialog(root_window, cursor, conn)
        dialog.max_points = 100

        dialog.quick_score_var.set('invalid')
        dialog.apply_quick_score()

        mock_error.assert_called_once()

    @patch('tkinter.messagebox.showerror')
    def test_apply_quick_score_out_of_range(self, mock_error, root_window, mock_connection):
        """Test validation for score out of range"""
        conn, cursor = mock_connection

        dialog = BatchGradeDialog(root_window, cursor, conn)
        dialog.max_points = 100

        dialog.quick_score_var.set('150')  # Over max_points
        dialog.apply_quick_score()

        mock_error.assert_called_once()

    def test_edit_individual_grade(self, root_window, mock_connection):
        """Test editing individual student grade"""
        conn, cursor = mock_connection

        dialog = BatchGradeDialog(root_window, cursor, conn)
        dialog.max_points = 100

        # Add a student
        item = dialog.students_tree.insert('', 'end', values=(
            'student001', 'John Doe', '', '75', '', 'Good work'
        ))

        # Select the student
        dialog.students_tree.selection_set(item)

        # Simulate double-click event
        event = Mock()
        dialog.edit_individual_grade(event)

        # Dialog should open (we can't easily test the actual editing without more mocking)

    def test_save_all_grades_success(self, root_window, mock_connection):
        """Test saving all grades to database"""
        conn, cursor = mock_connection
        cursor.fetchone.side_effect = [None, None]  # No existing grades

        dialog = BatchGradeDialog(root_window, cursor, conn)
        dialog.assessment_id = 1

        # Add students with grades
        dialog.students_tree.insert('', 'end', values=(
            'student001', 'John Doe', '', '85', 'A', 'Good work'
        ))
        dialog.students_tree.insert('', 'end', values=(
            'student002', 'Jane Smith', '', '92', 'A+', 'Excellent'
        ))

        with patch('tkinter.messagebox.showinfo'):
            dialog.save_all_grades()

        # Verify INSERT queries were executed
        insert_calls = [c for c in cursor.execute.call_args_list if 'INSERT' in str(c)]
        assert len(insert_calls) == 2
        conn.commit.assert_called_once()

    def test_save_all_grades_update_existing(self, root_window, mock_connection):
        """Test updating existing grades"""
        conn, cursor = mock_connection
        cursor.fetchone.side_effect = [(1,), (2,)]  # Existing grade IDs

        dialog = BatchGradeDialog(root_window, cursor, conn)
        dialog.assessment_id = 1

        # Add students with new grades
        dialog.students_tree.insert('', 'end', values=(
            'student001', 'John Doe', '80', '85', 'A', 'Improved'
        ))

        with patch('tkinter.messagebox.showinfo'):
            dialog.save_all_grades()

        # Verify UPDATE query was executed
        update_calls = [c for c in cursor.execute.call_args_list if 'UPDATE' in str(c)]
        assert len(update_calls) == 1
        conn.commit.assert_called_once()

    @patch('tkinter.messagebox.showwarning')
    def test_save_all_grades_no_assessment(self, mock_warning, root_window, mock_connection):
        """Test saving grades without assessment selected"""
        conn, cursor = mock_connection

        dialog = BatchGradeDialog(root_window, cursor, conn)

        dialog.save_all_grades()

        mock_warning.assert_called_once()

    def test_save_all_grades_skip_empty_scores(self, root_window, mock_connection):
        """Test that empty scores are not saved"""
        conn, cursor = mock_connection

        dialog = BatchGradeDialog(root_window, cursor, conn)
        dialog.assessment_id = 1

        # Add student without grade
        dialog.students_tree.insert('', 'end', values=(
            'student001', 'John Doe', '', '', '', ''
        ))

        # Add student with grade
        dialog.students_tree.insert('', 'end', values=(
            'student002', 'Jane Smith', '', '90', 'A+', 'Great'
        ))

        cursor.fetchone.return_value = None

        with patch('tkinter.messagebox.showinfo'):
            dialog.save_all_grades()

        # Only one INSERT should occur (for student002)
        insert_calls = [c for c in cursor.execute.call_args_list if 'INSERT' in str(c)]
        assert len(insert_calls) == 1

    def test_percentage_to_letter_conversion(self):
        """Test percentage to letter grade conversion"""
        assert percentage_to_letter(95) == 'A+'
        assert percentage_to_letter(87) == 'A'
        assert percentage_to_letter(82) == 'A-'
        assert percentage_to_letter(77) == 'B+'
        assert percentage_to_letter(72) == 'B'

    @patch('tkinter.messagebox.showerror')
    def test_save_all_grades_error_handling(self, mock_error, root_window, mock_connection):
        """Test error handling during save"""
        conn, cursor = mock_connection
        cursor.execute.side_effect = sqlite3.Error("Database error")

        dialog = BatchGradeDialog(root_window, cursor, conn)
        dialog.assessment_id = 1

        dialog.students_tree.insert('', 'end', values=(
            'student001', 'John Doe', '', '85', 'A', ''
        ))

        dialog.save_all_grades()

        mock_error.assert_called_once()

    def test_load_students_with_existing_grades(self, root_window, mock_connection):
        """Test loading students shows their existing grades"""
        conn, cursor = mock_connection

        cursor.fetchone.side_effect = [
            (100, 'CS101'),  # max_points, module_code
            (85.0, 'A', 'Good work'),  # Existing grade for student001
            None  # No existing grade for student002
        ]

        cursor.fetchall.return_value = [
            ('student001', 'John', 'Doe'),
            ('student002', 'Jane', 'Smith')
        ]

        dialog = BatchGradeDialog(root_window, cursor, conn)
        dialog.assessment_var.set('1 - [CS101] Midterm Exam')

        with patch('tkinter.messagebox.showinfo'):
            dialog.load_students()

        # Check first student has existing score
        values = dialog.students_tree.item(dialog.students_tree.get_children()[0], 'values')
        assert values[2] == 85.0  # Current score

class TestBatchGradeDialogIntegration:
    """Integration tests for BatchGradeDialog"""

    def test_full_grading_workflow(self, root_window, mock_connection):
        """Test complete workflow of batch grading"""
        conn, cursor = mock_connection

        # Setup assessment data
        cursor.fetchall.side_effect = [
            # Load assessments
            [(1, 'Midterm Exam', 'CS101')],
        ]
        cursor.fetchone.side_effect = [
            # Load students - assessment details
            (100, 'CS101'),
            # Existing grades for each student (none)
            None, None
        ]
        cursor.fetchall.side_effect.append(
            # Students in module
            [
                ('student001', 'John', 'Doe'),
                ('student002', 'Jane', 'Smith')
            ]
        )

        dialog = BatchGradeDialog(root_window, cursor, conn)

        # Load assessments
        combo = Mock()
        combo.__setitem__ = Mock()
        with patch('tkinter.messagebox.showinfo'):
            dialog.load_assessments(combo)

        # Select assessment and load students
        dialog.assessment_var.set('1 - [CS101] Midterm Exam')

        cursor.fetchall.return_value = [
            ('student001', 'John', 'Doe'),
            ('student002', 'Jane', 'Smith')
        ]
        cursor.fetchone.side_effect = [
            (100, 'CS101'),  # Assessment details
            None,  # No existing grade for student001
            None   # No existing grade for student002
        ]

        with patch('tkinter.messagebox.showinfo'):
            dialog.load_students()

        # Apply quick score
        dialog.quick_score_var.set('85')
        dialog.apply_quick_score()

        # Save grades
        cursor.fetchone.side_effect = [None, None]  # No existing grades
        with patch('tkinter.messagebox.showinfo'):
            dialog.save_all_grades()

        # Verify complete workflow
        assert dialog.result is True

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
