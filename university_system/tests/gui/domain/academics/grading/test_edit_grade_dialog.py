"""
Tests for EditGradeDialog class from grade_tracking dialogs.
Tests UI initialization, database operations, and validation.
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
import sqlite3

from university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog import (
    EditGradeDialog,
    GRADE_SYSTEMS,
    percentage_to_letter,
    letter_to_percentage,
    letter_to_gpa,
    safe_grab_set
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


class TestGradeSystemFunctions:
    """Test grade conversion helper functions"""

    def test_percentage_to_letter_A_plus(self):
        """Test conversion of high percentage to A+"""
        assert percentage_to_letter(95) == "A+"
        assert percentage_to_letter(90) == "A+"
        assert percentage_to_letter(100) == "A+"

    def test_percentage_to_letter_A(self):
        """Test conversion to A grade"""
        assert percentage_to_letter(87) == "A"
        assert percentage_to_letter(85) == "A"

    def test_percentage_to_letter_B_range(self):
        """Test conversion to B grades"""
        assert percentage_to_letter(77) == "B+"
        assert percentage_to_letter(72) == "B"
        assert percentage_to_letter(67) == "B-"

    def test_percentage_to_letter_F(self):
        """Test conversion to F grade"""
        assert percentage_to_letter(30) == "F"
        assert percentage_to_letter(0) == "F"

    def test_letter_to_percentage(self):
        """Test converting letter grade to percentage"""
        result = letter_to_percentage("A+")
        assert 90 <= result <= 100

        result = letter_to_percentage("B")
        assert 70 <= result <= 75

        result = letter_to_percentage("F")
        assert 0 <= result <= 35

    def test_letter_to_gpa(self):
        """Test converting letter grade to GPA"""
        assert letter_to_gpa("A+") == 4.3
        assert letter_to_gpa("A") == 4.0
        assert letter_to_gpa("B") == 3.0
        assert letter_to_gpa("F") == 0.0
        assert letter_to_gpa("INVALID") == 0


class TestSafeGrabSet:
    """Test safe_grab_set helper function"""

    def test_safe_grab_set_success(self, root):
        """Test successful grab set"""
        dialog = tk.Toplevel(root)
        dialog.update_idletasks()
        safe_grab_set(dialog)
        # Should not raise exception
        dialog.destroy()

    def test_safe_grab_set_with_tcl_error(self, root):
        """Test grab set handles TclError gracefully"""
        dialog = tk.Toplevel(root)
        # Should not raise exception even if grab fails
        safe_grab_set(dialog)
        dialog.destroy()


class TestEditGradeDialog:
    """Test EditGradeDialog class"""

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.get_connection')
    def test_init_creates_dialog(self, mock_get_conn, root, mock_connection):
        """Test dialog initialization creates UI elements"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn
        callback = Mock()

        dialog = EditGradeDialog(
            root,
            grade_id=1,
            student_id="S001",
            assessment_id=1,
            current_score=85.0,
            current_grade="A",
            max_points=100.0,
            current_feedback="Good work",
            callback=callback
        )

        # Check dialog was created
        assert dialog.dialog is not None
        assert dialog.grade_id == 1
        assert dialog.student_id == "S001"
        assert dialog.assessment_id == 1
        assert dialog.max_points == 100.0
        assert dialog.callback == callback

        # Check variables are set
        assert dialog.score_var.get() == "85.0"
        assert dialog.grade_var.get() == "A"
        assert "Good work" in dialog.feedback_text.get(1.0, tk.END)

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.get_connection')
    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.messagebox')
    def test_update_grade_success(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test successful grade update"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn
        callback = Mock()

        dialog = EditGradeDialog(
            root,
            grade_id=1,
            student_id="S001",
            assessment_id=1,
            current_score=85.0,
            current_grade="A",
            max_points=100.0,
            current_feedback="Good work",
            callback=callback
        )

        # Update values
        dialog.score_var.set("90.0")
        dialog.grade_var.set("A+")
        dialog.feedback_text.delete(1.0, tk.END)
        dialog.feedback_text.insert(1.0, "Excellent work!")

        # Call update
        dialog.update_grade()

        # Verify database update was called
        assert mock_cursor.execute.called
        execute_call = mock_cursor.execute.call_args[0]
        assert "UPDATE grades" in execute_call[0]
        assert execute_call[1][0] == 90.0  # score
        assert execute_call[1][1] == "A+"  # letter_grade
        assert "Excellent work!" in execute_call[1][2]  # comments

        # Verify commit and close
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

        # Verify success message
        mock_msgbox.showinfo.assert_called_once()

        # Verify callback was called
        callback.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.get_connection')
    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.messagebox')
    def test_update_grade_invalid_score(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test validation for invalid score"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        dialog = EditGradeDialog(
            root,
            grade_id=1,
            student_id="S001",
            assessment_id=1,
            current_score=85.0,
            current_grade="A",
            max_points=100.0,
            current_feedback="Good work",
            callback=Mock()
        )

        # Set invalid score (above max)
        dialog.score_var.set("150.0")
        dialog.grade_var.set("A+")

        dialog.update_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "Score must be between 0 and 100.0" in str(mock_msgbox.showerror.call_args)

        # Verify no database update
        assert not mock_conn.commit.called

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.get_connection')
    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.messagebox')
    def test_update_grade_non_numeric_score(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test validation for non-numeric score"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        dialog = EditGradeDialog(
            root,
            grade_id=1,
            student_id="S001",
            assessment_id=1,
            current_score=85.0,
            current_grade="A",
            max_points=100.0,
            current_feedback="Good work",
            callback=Mock()
        )

        # Set non-numeric score
        dialog.score_var.set("abc")
        dialog.grade_var.set("A+")

        dialog.update_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "valid numeric score" in str(mock_msgbox.showerror.call_args)

        # Verify no database update
        assert not mock_conn.commit.called

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.get_connection')
    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.messagebox')
    def test_update_grade_invalid_letter_grade(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test validation for invalid letter grade"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        dialog = EditGradeDialog(
            root,
            grade_id=1,
            student_id="S001",
            assessment_id=1,
            current_score=85.0,
            current_grade="A",
            max_points=100.0,
            current_feedback="Good work",
            callback=Mock()
        )

        # Set invalid letter grade
        dialog.score_var.set("90.0")
        dialog.grade_var.set("INVALID")

        dialog.update_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "valid letter grade" in str(mock_msgbox.showerror.call_args)

        # Verify no database update
        assert not mock_conn.commit.called

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.get_connection')
    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.messagebox')
    def test_update_grade_database_error(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test handling of database errors"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")

        dialog = EditGradeDialog(
            root,
            grade_id=1,
            student_id="S001",
            assessment_id=1,
            current_score=85.0,
            current_grade="A",
            max_points=100.0,
            current_feedback="Good work",
            callback=Mock()
        )

        dialog.score_var.set("90.0")
        dialog.grade_var.set("A+")

        dialog.update_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "Error updating grade" in str(mock_msgbox.showerror.call_args)

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.get_connection')
    def test_ui_components_exist(self, mock_get_conn, root, mock_connection):
        """Test all expected UI components are created"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        dialog = EditGradeDialog(
            root,
            grade_id=1,
            student_id="S001",
            assessment_id=1,
            current_score=85.0,
            current_grade="A",
            max_points=100.0,
            current_feedback="Good work",
            callback=Mock()
        )

        # Check essential attributes exist
        assert hasattr(dialog, 'score_var')
        assert hasattr(dialog, 'score_entry')
        assert hasattr(dialog, 'grade_var')
        assert hasattr(dialog, 'grade_combo')
        assert hasattr(dialog, 'feedback_text')

        # Check grade combo has correct values
        expected_grades = list(GRADE_SYSTEMS["letter"].keys())
        assert dialog.grade_combo['values'] == expected_grades

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_grade_dialog.get_connection')
    def test_boundary_score_values(self, mock_get_conn, root, mock_connection):
        """Test boundary values for score validation"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        dialog = EditGradeDialog(
            root,
            grade_id=1,
            student_id="S001",
            assessment_id=1,
            current_score=85.0,
            current_grade="A",
            max_points=100.0,
            current_feedback="Good work",
            callback=Mock()
        )

        # Test minimum valid score
        dialog.score_var.set("0")
        dialog.grade_var.set("F")
        dialog.update_grade()
        assert mock_cursor.execute.called

        # Reset mock
        mock_cursor.execute.reset_mock()

        # Test maximum valid score
        dialog.score_var.set("100.0")
        dialog.grade_var.set("A+")
        dialog.update_grade()
        assert mock_cursor.execute.called

        dialog.dialog.destroy()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
