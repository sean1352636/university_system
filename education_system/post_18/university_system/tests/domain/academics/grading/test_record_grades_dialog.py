"""
Tests for RecordGradesDialog class from grade_tracking dialogs.
Tests bulk grade recording, assessment selection, and database operations.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog import (
    RecordGradesDialog
)
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_edit_dialog import (
    GradeEditDialog
)

@pytest.fixture
def root():
    """Create a tkinter root window for testing"""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except Exception:
        pass

@pytest.fixture
def mock_connection():
    """Mock database connection"""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.commit = Mock()
    mock_conn.close = Mock()
    return mock_conn, mock_cursor

class TestRecordGradesDialog:
    """Test RecordGradesDialog class"""

    def test_init_creates_dialog(self, root):
        """Test dialog initialization creates UI elements"""
        dialog = RecordGradesDialog(root)

        # Check dialog was created
        assert dialog.dialog is not None
        assert dialog.assessment_id is None
        assert dialog.max_points == 0

        # Check essential UI components exist
        assert hasattr(dialog, 'assessment_var')
        assert hasattr(dialog, 'assessment_combo')
        assert hasattr(dialog, 'students_tree')

        dialog.dialog.destroy()

    def test_ui_components_exist(self, root):
        """Test all expected UI components are created"""
        dialog = RecordGradesDialog(root)

        # Check essential attributes exist
        assert hasattr(dialog, 'assessment_combo')
        assert hasattr(dialog, 'students_tree')
        assert hasattr(dialog, 'assessment_var')

        # Verify tree columns
        expected_columns = ('Student ID', 'Name', 'Current Grade', 'Score', 'Letter Grade', 'Comments')
        assert dialog.students_tree['columns'] == expected_columns

        dialog.dialog.destroy()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.messagebox')
    def test_load_assessments_success(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test loading assessments into combobox"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Mock assessment data
        mock_cursor.fetchall.return_value = [
            (1, "Midterm Exam", "CS101"),
            (2, "Final Project", "CS102"),
        ]

        dialog = RecordGradesDialog(root)

        dialog.load_assessments()

        # Verify query was executed
        assert mock_cursor.execute.called
        execute_call = mock_cursor.execute.call_args[0]
        assert "SELECT" in execute_call[0]
        assert "assessments" in execute_call[0]

        # Verify success message
        mock_msgbox.showinfo.assert_called_once()
        assert "Loaded 2 assessments" in str(mock_msgbox.showinfo.call_args)

        dialog.dialog.destroy()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.messagebox')
    def test_load_assessments_empty(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test loading assessments when none exist"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Mock empty assessment data
        mock_cursor.fetchall.return_value = []

        dialog = RecordGradesDialog(root)

        dialog.load_assessments()

        # Verify warning message
        mock_msgbox.showwarning.assert_called_once()
        assert "No assessments found" in str(mock_msgbox.showwarning.call_args)

        dialog.dialog.destroy()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.messagebox')
    def test_load_assessments_database_error(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test handling of database errors during load"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Simulate database error
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")

        dialog = RecordGradesDialog(root)

        dialog.load_assessments()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "Error loading assessments" in str(mock_msgbox.showerror.call_args)

        dialog.dialog.destroy()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.messagebox')
    def test_select_assessment_no_selection(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test selecting assessment without choosing one"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        dialog = RecordGradesDialog(root)

        # Don't set assessment_var
        dialog.assessment_var.set("")

        dialog.select_assessment()

        # Verify warning message
        mock_msgbox.showwarning.assert_called_once()
        assert "select an assessment first" in str(mock_msgbox.showwarning.call_args)

        dialog.dialog.destroy()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.messagebox')
    def test_select_assessment_success(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test successful assessment selection and student loading"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Mock assessment details, then "no existing grade" for each student lookup
        mock_cursor.fetchone.side_effect = [
            ("Midterm Exam", "CS101", 100.0, "Intro to CS"),  # assessment details
            None,  # existing grade for S001
            None,  # existing grade for S002
        ]

        # Mock students enrolled in module
        mock_cursor.fetchall.return_value = [
            ("S001", "John", None, "Doe"),
            ("S002", "Jane", "M", "Smith"),
        ]

        dialog = RecordGradesDialog(root)

        # Set assessment selection
        dialog.assessment_var.set("1 - [CS101] Midterm Exam")

        dialog.select_assessment()

        # Verify assessment_id is set
        assert dialog.assessment_id == 1
        assert dialog.max_points == 100.0

        # Verify students are loaded in tree
        children = dialog.students_tree.get_children()
        assert len(children) == 2

        # Verify success message
        mock_msgbox.showinfo.assert_called_once()
        assert "Loaded 2 students" in str(mock_msgbox.showinfo.call_args)

        dialog.dialog.destroy()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.messagebox')
    def test_select_assessment_with_existing_grades(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test loading students with existing grades"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Mock assessment details
        mock_cursor.fetchone.return_value = ("Midterm Exam", "CS101", 100.0, "Intro to CS")

        # Mock students and existing grades
        mock_cursor.fetchall.return_value = [
            ("S001", "John", None, "Doe"),
        ]

        # Mock existing grade for first student
        def execute_side_effect(*args, **kwargs):
            query = args[0] if args else ""
            if "grades" in query and "WHERE student_id" in query:
                return None  # For fetchone() call
            return None

        mock_cursor.execute.side_effect = execute_side_effect
        mock_cursor.fetchone.side_effect = [
            ("Midterm Exam", "CS101", 100.0, "Intro to CS"),  # Assessment details
            (85.0, "A", "Good work"),  # Existing grade
        ]

        dialog = RecordGradesDialog(root)

        dialog.assessment_var.set("1 - [CS101] Midterm Exam")

        dialog.select_assessment()

        # Verify students are loaded
        children = dialog.students_tree.get_children()
        assert len(children) == 1

        # Verify existing grade is shown
        item = dialog.students_tree.item(children[0])
        assert "A" in item['values'][2]  # Current Grade column

        dialog.dialog.destroy()

    def test_update_student_grade(self, root):
        """Test updating student grade in treeview"""
        dialog = RecordGradesDialog(root)

        dialog.assessment_id = 1
        dialog.max_points = 100.0

        # Add a student to the tree
        dialog.students_tree.insert('', 'end', values=(
            "S001", "John Doe", "Not graded", "", "", ""
        ))

        # Update the grade
        dialog.update_student_grade("S001", "85", "A", "Good work")

        # Verify grade was updated
        children = dialog.students_tree.get_children()
        item = dialog.students_tree.item(children[0])
        values = item['values']

        assert values[0] == "S001"
        assert values[2] == "A (85/100.0)"  # Current Grade
        assert str(values[3]) == "85"  # Score (tkinter coerces numeric strings to int)
        assert values[4] == "A"  # Letter Grade
        assert values[5] == "Good work"  # Comments

        dialog.dialog.destroy()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.messagebox')
    def test_save_all_grades_no_assessment(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test saving grades without selecting assessment"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        dialog = RecordGradesDialog(root)

        # Don't set assessment_id
        dialog.assessment_id = None

        dialog.save_all_grades()

        # Verify warning message
        mock_msgbox.showwarning.assert_called_once()
        assert "select an assessment first" in str(mock_msgbox.showwarning.call_args)

        dialog.dialog.destroy()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.messagebox')
    def test_save_all_grades_success(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test successful saving of all grades"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Mock no existing grades
        mock_cursor.fetchone.return_value = None

        dialog = RecordGradesDialog(root)

        dialog.assessment_id = 1
        dialog.max_points = 100.0

        # Add students with grades
        dialog.students_tree.insert('', 'end', values=(
            "S001", "John Doe", "A (85/100)", "85", "A", "Good work"
        ))
        dialog.students_tree.insert('', 'end', values=(
            "S002", "Jane Smith", "B (75/100)", "75", "B", "Nice job"
        ))

        dialog.save_all_grades()

        # Verify INSERT queries were executed
        insert_calls = [call for call in mock_cursor.execute.call_args_list
                       if "INSERT INTO grades" in str(call)]
        assert len(insert_calls) == 2

        # Verify commit was called
        mock_conn.commit.assert_called_once()

        # Verify success message
        mock_msgbox.showinfo.assert_called_once()
        assert "Saved 2 grades" in str(mock_msgbox.showinfo.call_args)

        dialog.dialog.destroy()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.messagebox')
    def test_save_all_grades_update_existing(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test updating existing grades"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Mock existing grade
        mock_cursor.fetchone.return_value = (1,)  # grade_id

        dialog = RecordGradesDialog(root)

        dialog.assessment_id = 1
        dialog.max_points = 100.0

        # Add student with updated grade
        dialog.students_tree.insert('', 'end', values=(
            "S001", "John Doe", "A+ (90/100)", "90", "A+", "Excellent!"
        ))

        dialog.save_all_grades()

        # Verify UPDATE query was executed
        update_calls = [call for call in mock_cursor.execute.call_args_list
                       if "UPDATE grades" in str(call)]
        assert len(update_calls) == 1

        # Verify commit was called
        mock_conn.commit.assert_called_once()

        dialog.dialog.destroy()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.messagebox')
    def test_save_all_grades_skip_incomplete(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test that incomplete grades are skipped"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # No existing grade -> INSERT path (avoid Mock being treated as a row)
        mock_cursor.fetchone.return_value = None

        dialog = RecordGradesDialog(root)

        dialog.assessment_id = 1
        dialog.max_points = 100.0

        # Add student with complete grade
        dialog.students_tree.insert('', 'end', values=(
            "S001", "John Doe", "A (85/100)", "85", "A", "Good"
        ))

        # Add student with incomplete grade (no score)
        dialog.students_tree.insert('', 'end', values=(
            "S002", "Jane Smith", "Not graded", "", "", ""
        ))

        dialog.save_all_grades()

        # Verify only one grade was saved
        mock_msgbox.showinfo.assert_called_once()
        assert "Saved 1 grade" in str(mock_msgbox.showinfo.call_args)

        dialog.dialog.destroy()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.record_grades_dialog.messagebox')
    def test_save_all_grades_database_error(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test handling of database errors during save"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Simulate database error
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")

        dialog = RecordGradesDialog(root)

        dialog.assessment_id = 1
        dialog.max_points = 100.0

        # Add student with grade
        dialog.students_tree.insert('', 'end', values=(
            "S001", "John Doe", "A (85/100)", "85", "A", "Good"
        ))

        dialog.save_all_grades()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "Error saving grades" in str(mock_msgbox.showerror.call_args)

        dialog.dialog.destroy()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
