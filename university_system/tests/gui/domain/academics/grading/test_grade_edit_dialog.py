"""
Tests for GradeEditDialog class from grade_tracking dialogs.
Tests grade editing with auto-calculation, UI components, and validation.
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_edit_dialog import (
    GradeEditDialog,
    GRADE_SYSTEMS,
    percentage_to_letter
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

class TestGradeEditDialog:
    """Test GradeEditDialog class"""

    def test_init_creates_dialog(self, root):
        """Test dialog initialization creates UI elements"""
        callback = Mock()

        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="85",
            current_grade="A",
            current_comments="Good work",
            callback=callback
        )

        # Check dialog was created
        assert dialog.dialog is not None
        assert dialog.student_id == "S001"
        assert dialog.max_points == 100.0
        assert dialog.callback == callback

        # Check variables are set
        assert dialog.score_var.get() == "85"
        assert dialog.grade_var.get() == "A"
        assert "Good work" in dialog.comments_text.get(1.0, tk.END)

        dialog.dialog.destroy()

    def test_ui_components_exist(self, root):
        """Test all expected UI components are created"""
        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="85",
            current_grade="A",
            current_comments="Good work",
            callback=Mock()
        )

        # Check essential attributes exist
        assert hasattr(dialog, 'score_var')
        assert hasattr(dialog, 'score_entry')
        assert hasattr(dialog, 'grade_var')
        assert hasattr(dialog, 'grade_combo')
        assert hasattr(dialog, 'comments_text')

        # Check grade combo has correct values
        expected_grades = list(GRADE_SYSTEMS["letter"].keys())
        assert dialog.grade_combo['values'] == expected_grades

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_edit_dialog.messagebox')
    def test_calculate_grade_valid_score(self, mock_msgbox, root):
        """Test automatic grade calculation from score"""
        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="0",
            current_grade="F",
            current_comments="",
            callback=Mock()
        )

        # Set score and calculate
        dialog.score_var.set("90")
        dialog.calculate_grade()

        # Verify grade was calculated (90/100 = 90% = A+)
        assert dialog.grade_var.get() == "A+"

        # Test another score
        dialog.score_var.set("75")
        dialog.calculate_grade()

        # 75/100 = 75% = B+
        assert dialog.grade_var.get() == "B+"

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_edit_dialog.messagebox')
    def test_calculate_grade_invalid_score(self, mock_msgbox, root):
        """Test grade calculation with invalid score"""
        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="85",
            current_grade="A",
            current_comments="",
            callback=Mock()
        )

        # Set non-numeric score
        dialog.score_var.set("abc")
        dialog.calculate_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "valid numeric score" in str(mock_msgbox.showerror.call_args)

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_edit_dialog.messagebox')
    def test_calculate_grade_out_of_range(self, mock_msgbox, root):
        """Test grade calculation with score out of range"""
        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="85",
            current_grade="A",
            current_comments="",
            callback=Mock()
        )

        # Set score above max
        dialog.score_var.set("150")
        dialog.calculate_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "between 0 and 100.0" in str(mock_msgbox.showerror.call_args)

        # Reset mock
        mock_msgbox.reset_mock()

        # Set negative score
        dialog.score_var.set("-10")
        dialog.calculate_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_edit_dialog.messagebox')
    def test_save_grade_missing_fields(self, mock_msgbox, root):
        """Test validation for missing required fields"""
        callback = Mock()

        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="",
            current_grade="",
            current_comments="",
            callback=callback
        )

        # Try to save without score
        dialog.score_var.set("")
        dialog.grade_var.set("A")

        dialog.save_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "enter both score and letter grade" in str(mock_msgbox.showerror.call_args)

        # Verify callback was not called
        callback.assert_not_called()

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_edit_dialog.messagebox')
    def test_save_grade_invalid_score(self, mock_msgbox, root):
        """Test validation for non-numeric score"""
        callback = Mock()

        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="85",
            current_grade="A",
            current_comments="",
            callback=callback
        )

        # Set non-numeric score
        dialog.score_var.set("abc")
        dialog.grade_var.set("A")

        dialog.save_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "valid numeric score" in str(mock_msgbox.showerror.call_args)

        # Verify callback was not called
        callback.assert_not_called()

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_edit_dialog.messagebox')
    def test_save_grade_score_exceeds_max(self, mock_msgbox, root):
        """Test validation for score exceeding max points"""
        callback = Mock()

        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="85",
            current_grade="A",
            current_comments="",
            callback=callback
        )

        # Set score above max
        dialog.score_var.set("150")
        dialog.grade_var.set("A+")

        dialog.save_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "between 0 and 100.0" in str(mock_msgbox.showerror.call_args)

        # Verify callback was not called
        callback.assert_not_called()

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.grade_edit_dialog.messagebox')
    def test_save_grade_invalid_letter_grade(self, mock_msgbox, root):
        """Test validation for invalid letter grade"""
        callback = Mock()

        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="85",
            current_grade="A",
            current_comments="",
            callback=callback
        )

        # Set invalid letter grade
        dialog.score_var.set("85")
        dialog.grade_var.set("INVALID")

        dialog.save_grade()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "valid letter grade" in str(mock_msgbox.showerror.call_args)

        # Verify callback was not called
        callback.assert_not_called()

        dialog.dialog.destroy()

    def test_save_grade_success(self, root):
        """Test successful grade save"""
        callback = Mock()

        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="85",
            current_grade="A",
            current_comments="Good work",
            callback=callback
        )

        # Set valid data
        dialog.score_var.set("90")
        dialog.grade_var.set("A+")
        dialog.comments_text.delete(1.0, tk.END)
        dialog.comments_text.insert(1.0, "Excellent work!")

        # Save grade
        dialog.save_grade()

        # Verify callback was called with correct parameters
        callback.assert_called_once_with("S001", "90", "A+", "Excellent work!")

    def test_boundary_score_values(self, root):
        """Test boundary values for score validation"""
        callback = Mock()

        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="50",
            current_grade="C-",
            current_comments="",
            callback=callback
        )

        # Test minimum valid score
        dialog.score_var.set("0")
        dialog.grade_var.set("F")
        dialog.save_grade()
        assert callback.called

        # Reset callback
        callback.reset_mock()

        # Test maximum valid score
        dialog.score_var.set("100")
        dialog.grade_var.set("A+")
        dialog.save_grade()
        assert callback.called

        dialog.dialog.destroy()

    def test_comments_optional(self, root):
        """Test that comments are optional"""
        callback = Mock()

        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="85",
            current_grade="A",
            current_comments="",
            callback=callback
        )

        # Set valid score and grade, leave comments empty
        dialog.score_var.set("85")
        dialog.grade_var.set("A")
        dialog.comments_text.delete(1.0, tk.END)

        dialog.save_grade()

        # Should succeed
        callback.assert_called_once()

        dialog.dialog.destroy()

    def test_calculate_grade_percentage_conversions(self, root):
        """Test various percentage to letter grade conversions"""
        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="0",
            current_grade="F",
            current_comments="",
            callback=Mock()
        )

        # Test various score percentages
        test_cases = [
            (100, "A+"),
            (90, "A+"),
            (85, "A"),
            (80, "A-"),
            (75, "B+"),
            (70, "B"),
            (65, "B-"),
            (60, "C+"),
            (55, "C"),
            (50, "C-"),
            (30, "F"),
            (0, "F"),
        ]

        for score, expected_grade in test_cases:
            dialog.score_var.set(str(score))
            dialog.calculate_grade()
            assert dialog.grade_var.get() == expected_grade, \
                f"Score {score} should be {expected_grade}, got {dialog.grade_var.get()}"

        dialog.dialog.destroy()

    def test_student_name_displayed_in_title(self, root):
        """Test that student name is displayed in dialog title"""
        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=100.0,
            current_score="85",
            current_grade="A",
            current_comments="",
            callback=Mock()
        )

        # Check title contains student name
        assert "John Doe" in dialog.dialog.title()

        dialog.dialog.destroy()

    def test_max_points_displayed_correctly(self, root):
        """Test that max points is displayed in UI"""
        dialog = GradeEditDialog(
            root,
            student_id="S001",
            student_name="John Doe",
            max_points=150.0,
            current_score="100",
            current_grade="B-",
            current_comments="",
            callback=Mock()
        )

        # Max points should be available for calculations
        assert dialog.max_points == 150.0

        # Test calculation with custom max points
        dialog.score_var.set("135")  # 135/150 = 90% = A+
        dialog.calculate_grade()
        assert dialog.grade_var.get() == "A+"

        dialog.dialog.destroy()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
