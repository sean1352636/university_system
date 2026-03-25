"""
Tests for GradeDialog class from grade_tracking dialogs.
Tests grade creation, UI components, and validation.
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_dialog import (
    GradeDialog,
    GRADE_SYSTEMS
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
def mock_cursor():
    """Mock database cursor"""
    cursor = Mock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return cursor

class TestGradeDialog:
    """Test GradeDialog class"""

    def test_init_creates_dialog_new_grade(self, root, mock_cursor):
        """Test dialog initialization for new grade"""
        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Check dialog was created
        assert dialog.dialog is not None
        assert dialog.cursor == mock_cursor
        assert dialog.result is None

        # Check variables are initialized empty
        assert dialog.score_var.get() == ""

        dialog.dialog.destroy()

    def test_init_creates_dialog_edit_grade(self, root, mock_cursor):
        """Test dialog initialization for editing existing grade"""
        test_data = ("S001", "John Doe", 85.0, 100.0, "2024-01-01", "Good work")

        dialog = GradeDialog(root, "Edit Grade", mock_cursor, data=test_data)

        # Check dialog was created
        assert dialog.dialog is not None

        # Check data is loaded
        assert dialog.score_var.get() == "85.0"
        assert dialog.max_points_var.get() == "100.0"
        assert dialog.submission_date_var.get() == "2024-01-01"

        dialog.dialog.destroy()

    def test_load_students_success(self, root, mock_cursor):
        """Test loading students into combobox"""
        # Mock student data
        mock_cursor.fetchall.return_value = [
            ("S001", "John", "Doe"),
            ("S002", "Jane", "Smith"),
        ]

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Verify students query was executed
        assert mock_cursor.execute.called
        select_calls = [call for call in mock_cursor.execute.call_args_list
                       if "students" in str(call)]
        assert len(select_calls) > 0

        dialog.dialog.destroy()

    def test_load_assessments_success(self, root, mock_cursor):
        """Test loading assessments into combobox"""
        # Mock assessment data
        mock_cursor.fetchall.side_effect = [
            [],  # students
            [("1", "Midterm Exam", "CS101"), ("2", "Final Project", "CS102")],  # assessments
        ]

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Verify assessments query was executed
        assert mock_cursor.execute.called
        assessment_calls = [call for call in mock_cursor.execute.call_args_list
                           if "assessments" in str(call)]
        assert len(assessment_calls) > 0

        dialog.dialog.destroy()

    def test_update_max_points_on_assessment_selection(self, root, mock_cursor):
        """Test that selecting an assessment updates max points"""
        # Mock assessments with different max points
        mock_cursor.fetchall.side_effect = [
            [],  # students
            [("1", "Midterm", "CS101")],  # assessments
        ]
        mock_cursor.fetchone.return_value = (100.0,)  # max_points

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Simulate selecting an assessment
        dialog.assessment_var.set("1 - [CS101] Midterm")
        event = Mock()
        dialog.update_max_points(event)

        # Verify max_points query was executed
        max_points_calls = [call for call in mock_cursor.execute.call_args_list
                           if "max_points" in str(call) and "assessments" in str(call)]
        assert len(max_points_calls) > 0

        # Verify max_points was updated
        assert dialog.max_points_var.get() == "100.0"

        dialog.dialog.destroy()

    def test_update_max_points_assessment_not_found(self, root, mock_cursor):
        """Test handling when assessment is not found"""
        mock_cursor.fetchall.side_effect = [
            [],  # students
            [],  # assessments
        ]
        mock_cursor.fetchone.return_value = None

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Try to update max points with invalid assessment
        dialog.assessment_var.set("999 - Invalid")
        event = Mock()
        dialog.update_max_points(event)

        # Should not crash, max_points stays at default
        assert dialog.max_points_var.get() != ""

        dialog.dialog.destroy()

    @patch('education_system.university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_dialog.messagebox')
    def test_save_grade_missing_required_fields(self, mock_msgbox, root, mock_cursor):
        """Test validation for missing required fields"""
        mock_cursor.fetchall.side_effect = [[], []]  # students, assessments

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Leave fields empty
        dialog.student_var.set("")
        dialog.assessment_var.set("")
        dialog.score_var.set("")

        # Try to save
        dialog.save_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "fill in all required fields" in str(mock_msgbox.showerror.call_args)

        dialog.dialog.destroy()

    @patch('education_system.university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_dialog.messagebox')
    def test_save_grade_invalid_score(self, mock_msgbox, root, mock_cursor):
        """Test validation for non-numeric score"""
        mock_cursor.fetchall.side_effect = [[], []]

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Set invalid score
        dialog.student_var.set("S001 - John Doe")
        dialog.assessment_var.set("1 - Test")
        dialog.score_var.set("abc")  # Non-numeric
        dialog.max_points_var.set("100")

        dialog.save_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "must be numbers" in str(mock_msgbox.showerror.call_args)

        dialog.dialog.destroy()

    @patch('education_system.university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_dialog.messagebox')
    def test_save_grade_score_out_of_range(self, mock_msgbox, root, mock_cursor):
        """Test validation for score exceeding max points"""
        mock_cursor.fetchall.side_effect = [[], []]

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Set score above max
        dialog.student_var.set("S001 - John Doe")
        dialog.assessment_var.set("1 - Test")
        dialog.score_var.set("150")  # Above max
        dialog.max_points_var.set("100")

        dialog.save_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "between 0 and 100" in str(mock_msgbox.showerror.call_args)

        dialog.dialog.destroy()

    def test_save_grade_valid_data(self, root, mock_cursor):
        """Test saving grade with valid data"""
        mock_cursor.fetchall.side_effect = [[], []]

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Set valid data
        dialog.student_var.set("S001 - John Doe")
        dialog.assessment_var.set("1 - Test")
        dialog.score_var.set("85")
        dialog.max_points_var.set("100")
        dialog.submission_date_var.set("2024-01-01")
        dialog.feedback_text.insert(1.0, "Good work")

        # Save grade
        dialog.save_grade()

        # Verify result is set
        assert dialog.result is not None
        student_id, assessment_id, score, max_points, date, feedback = dialog.result
        assert student_id == "S001"
        assert assessment_id == 1
        assert score == 85.0
        assert max_points == 100.0
        assert date == "2024-01-01"
        assert "Good work" in feedback

    def test_ui_components_exist(self, root, mock_cursor):
        """Test all expected UI components are created"""
        mock_cursor.fetchall.side_effect = [[], []]

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Check essential attributes exist
        assert hasattr(dialog, 'student_var')
        assert hasattr(dialog, 'assessment_var')
        assert hasattr(dialog, 'score_var')
        assert hasattr(dialog, 'max_points_var')
        assert hasattr(dialog, 'submission_date_var')
        assert hasattr(dialog, 'feedback_text')

        dialog.dialog.destroy()

    def test_default_submission_date(self, root, mock_cursor):
        """Test that submission date defaults to today"""
        mock_cursor.fetchall.side_effect = [[], []]

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Check default date is today
        today = datetime.now().strftime('%Y-%m-%d')
        assert dialog.submission_date_var.get() == today

        dialog.dialog.destroy()

    def test_boundary_scores(self, root, mock_cursor):
        """Test boundary score values"""
        mock_cursor.fetchall.side_effect = [[], []]

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Set up valid student and assessment
        dialog.student_var.set("S001 - John Doe")
        dialog.assessment_var.set("1 - Test")
        dialog.max_points_var.set("100")
        dialog.submission_date_var.set("2024-01-01")

        # Test minimum valid score
        dialog.score_var.set("0")
        dialog.save_grade()
        assert dialog.result is not None

        # Test maximum valid score
        dialog.score_var.set("100")
        dialog.save_grade()
        assert dialog.result is not None

        dialog.dialog.destroy()

    def test_feedback_optional(self, root, mock_cursor):
        """Test that feedback is optional"""
        mock_cursor.fetchall.side_effect = [[], []]

        dialog = GradeDialog(root, "Add Grade", mock_cursor, data=None)

        # Set valid data without feedback
        dialog.student_var.set("S001 - John Doe")
        dialog.assessment_var.set("1 - Test")
        dialog.score_var.set("85")
        dialog.max_points_var.set("100")
        dialog.submission_date_var.set("2024-01-01")
        # Leave feedback empty

        dialog.save_grade()

        # Should succeed
        assert dialog.result is not None

        dialog.dialog.destroy()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
