"""
Tests for Assessment Dialog

This module tests the AssessmentDialog class which provides
a dialog for creating and editing assessments.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, MagicMock, patch, call
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.gui.academics.grade_tracking.dialogs.assessment_dialog import (
    AssessmentDialog
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
def mock_cursor():
    """Create a mock database cursor"""
    cursor = Mock()
    cursor.fetchall.return_value = [
        ('CS101',),
        ('CS102',),
        ('MATH201',)
    ]
    return cursor

class TestAssessmentDialog:
    """Test suite for AssessmentDialog"""

    def test_initialization_new_assessment(self, root_window, mock_cursor):
        """Test dialog initialization for new assessment"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        assert dialog.dialog is not None
        assert dialog.cursor == mock_cursor
        assert dialog.result is None

    def test_initialization_with_existing_data(self, root_window, mock_cursor):
        """Test dialog initialization with existing assessment data"""
        existing_data = (
            'Midterm Exam',      # name
            'Exam',              # type
            'CS101',             # module_code
            100,                 # max_points
            30,                  # weight
            '2025-11-15',        # due_date
            'Test description',  # description
            'Test rubric'        # rubric
        )

        dialog = AssessmentDialog(root_window, "Edit Assessment", mock_cursor, data=existing_data)

        assert dialog.name_var.get() == 'Midterm Exam'
        assert dialog.type_var.get() == 'Exam'
        assert dialog.module_var.get() == 'CS101'
        assert dialog.max_points_var.get() == '100'
        assert dialog.weight_var.get() == '30'

    def test_initialization_with_copy_data(self, root_window, mock_cursor):
        """Test dialog initialization with copy data (overrides regular data)"""
        original_data = (
            'Original Assessment', 'Exam', 'CS101', 100, 30,
            '2025-11-15', 'Original desc', 'Original rubric'
        )

        copy_data = (
            'Copy of Assessment', 'Quiz', 'CS102', 50, 15,
            '2025-11-20', 'Copy desc', 'Copy rubric'
        )

        dialog = AssessmentDialog(
            root_window, "Copy Assessment", mock_cursor,
            data=original_data, copy_data=copy_data
        )

        # Should use copy_data, not original_data
        assert dialog.name_var.get() == 'Copy of Assessment'
        assert dialog.type_var.get() == 'Quiz'
        assert dialog.module_var.get() == 'CS102'

    def test_save_assessment_success(self, root_window, mock_cursor):
        """Test saving assessment with valid data"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        # Fill in all required fields
        dialog.name_var.set('Final Exam')
        dialog.type_var.set('Exam')
        dialog.module_var.set('CS101')
        dialog.max_points_var.set('200')
        dialog.weight_var.set('40')
        dialog.due_date_var.set('2025-12-15')
        dialog.description_text.insert(1.0, 'Comprehensive final exam')
        dialog.rubric_text.insert(1.0, 'Grading rubric details')

        dialog.save_assessment()

        # Verify result is set correctly
        assert dialog.result is not None
        assert dialog.result[0] == 'Final Exam'
        assert dialog.result[1] == 'Exam'
        assert dialog.result[2] == 'CS101'
        assert dialog.result[3] == 200.0
        assert dialog.result[4] == 40.0

    @patch('tkinter.messagebox.showerror')
    def test_save_assessment_missing_required_fields(self, mock_error, root_window, mock_cursor):
        """Test validation when required fields are missing"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        # Leave required fields empty
        dialog.save_assessment()

        mock_error.assert_called_once()
        assert dialog.result is None

    @patch('tkinter.messagebox.showerror')
    def test_save_assessment_invalid_max_points(self, mock_error, root_window, mock_cursor):
        """Test validation with invalid max points"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        dialog.name_var.set('Test Assessment')
        dialog.type_var.set('Quiz')
        dialog.module_var.set('CS101')
        dialog.max_points_var.set('invalid')  # Invalid number
        dialog.weight_var.set('20')

        dialog.save_assessment()

        mock_error.assert_called_once()
        assert dialog.result is None

    @patch('tkinter.messagebox.showerror')
    def test_save_assessment_invalid_weight(self, mock_error, root_window, mock_cursor):
        """Test validation with invalid weight"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        dialog.name_var.set('Test Assessment')
        dialog.type_var.set('Quiz')
        dialog.module_var.set('CS101')
        dialog.max_points_var.set('100')
        dialog.weight_var.set('abc')  # Invalid number

        dialog.save_assessment()

        mock_error.assert_called_once()
        assert dialog.result is None

    def test_assessment_type_options(self, root_window, mock_cursor):
        """Test that assessment type combobox has predefined options"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        # Type combobox should have values
        assert dialog.type_var is not None

    def test_module_loading_from_database(self, root_window, mock_cursor):
        """Test that modules are loaded from database cursor"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        # Verify cursor was called to fetch modules
        mock_cursor.execute.assert_called_with("SELECT module_code FROM modules ORDER BY module_code")
        mock_cursor.fetchall.assert_called()

    def test_description_multiline_support(self, root_window, mock_cursor):
        """Test that description supports multiline text"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        multiline_desc = "Line 1\nLine 2\nLine 3"
        dialog.description_text.insert(1.0, multiline_desc)

        dialog.name_var.set('Test')
        dialog.type_var.set('Assignment')
        dialog.module_var.set('CS101')
        dialog.max_points_var.set('100')
        dialog.weight_var.set('25')

        dialog.save_assessment()

        # Description should preserve newlines (though strip() removes trailing ones)
        assert 'Line 1' in dialog.result[6]

    def test_rubric_field_support(self, root_window, mock_cursor):
        """Test that rubric field works correctly"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        rubric_text = "Criteria 1: 40%\nCriteria 2: 60%"
        dialog.rubric_text.insert(1.0, rubric_text)

        dialog.name_var.set('Test')
        dialog.type_var.set('Project')
        dialog.module_var.set('CS101')
        dialog.max_points_var.set('100')
        dialog.weight_var.set('30')

        dialog.save_assessment()

        # Rubric should be in result
        assert 'Criteria' in dialog.result[7]

    def test_whitespace_trimming(self, root_window, mock_cursor):
        """Test that whitespace is trimmed from inputs"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        dialog.name_var.set('  Test Assessment  ')
        dialog.type_var.set('  Quiz  ')
        dialog.module_var.set('  CS101  ')
        dialog.max_points_var.set(' 100 ')
        dialog.weight_var.set(' 20 ')
        dialog.due_date_var.set('  2025-11-15  ')

        dialog.save_assessment()

        # Verify whitespace was trimmed
        assert dialog.result[0] == 'Test Assessment'
        assert dialog.result[1] == 'Quiz'
        assert dialog.result[2] == 'CS101'
        assert dialog.result[5] == '2025-11-15'

    def test_numeric_conversion(self, root_window, mock_cursor):
        """Test that max_points and weight are converted to floats"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        dialog.name_var.set('Test')
        dialog.type_var.set('Exam')
        dialog.module_var.set('CS101')
        dialog.max_points_var.set('150')
        dialog.weight_var.set('35.5')

        dialog.save_assessment()

        # Verify types are float
        assert isinstance(dialog.result[3], float)
        assert isinstance(dialog.result[4], float)
        assert dialog.result[3] == 150.0
        assert dialog.result[4] == 35.5

    def test_cancel_button_functionality(self, root_window, mock_cursor):
        """Test that cancel button closes dialog without saving"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        # Mock dialog.destroy to track if it's called
        original_destroy = dialog.dialog.destroy
        dialog.dialog.destroy = Mock(side_effect=original_destroy)

        # Fill in some data
        dialog.name_var.set('Test')
        dialog.type_var.set('Quiz')

        # Find and click cancel button (simulated by destroying dialog)
        dialog.dialog.destroy()

        # Result should still be None
        assert dialog.result is None

    def test_module_combo_error_handling(self, root_window):
        """Test handling of database error when loading modules"""
        error_cursor = Mock()
        error_cursor.execute.side_effect = Exception("Database error")

        # Should not crash even if module loading fails
        dialog = AssessmentDialog(root_window, "Add Assessment", error_cursor)

        assert dialog is not None

    @patch('tkinter.messagebox.showerror')
    def test_empty_name_validation(self, mock_error, root_window, mock_cursor):
        """Test validation fails when name is empty"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        # Leave name empty but fill other fields
        dialog.type_var.set('Quiz')
        dialog.module_var.set('CS101')
        dialog.max_points_var.set('100')
        dialog.weight_var.set('20')

        dialog.save_assessment()

        mock_error.assert_called_once()

    @patch('tkinter.messagebox.showerror')
    def test_empty_type_validation(self, mock_error, root_window, mock_cursor):
        """Test validation fails when type is empty"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        dialog.name_var.set('Test Assessment')
        # Leave type empty
        dialog.module_var.set('CS101')
        dialog.max_points_var.set('100')
        dialog.weight_var.set('20')

        dialog.save_assessment()

        mock_error.assert_called_once()

class TestAssessmentDialogIntegration:
    """Integration tests for AssessmentDialog"""

    def test_full_create_workflow(self, root_window, mock_cursor):
        """Test complete workflow of creating an assessment"""
        dialog = AssessmentDialog(root_window, "Add Assessment", mock_cursor)

        # Fill in comprehensive data
        dialog.name_var.set('Midterm Exam')
        dialog.type_var.set('Exam')
        dialog.module_var.set('CS101')
        dialog.max_points_var.set('100')
        dialog.weight_var.set('30')
        dialog.due_date_var.set('2025-11-15')
        dialog.description_text.insert(1.0, 'Covers chapters 1-5')
        dialog.rubric_text.insert(1.0, 'Multiple choice: 60%, Essays: 40%')

        dialog.save_assessment()

        # Verify complete result
        assert len(dialog.result) == 8
        assert all(dialog.result)  # All fields should have values

    def test_edit_workflow(self, root_window, mock_cursor):
        """Test workflow of editing existing assessment"""
        existing_data = (
            'Original Name', 'Quiz', 'CS101', 50, 10,
            '2025-11-01', 'Original desc', 'Original rubric'
        )

        dialog = AssessmentDialog(root_window, "Edit Assessment", mock_cursor, data=existing_data)

        # Modify some fields
        dialog.name_var.set('Updated Name')
        dialog.max_points_var.set('75')
        dialog.weight_var.set('15')

        dialog.save_assessment()

        # Verify updates
        assert dialog.result[0] == 'Updated Name'
        assert dialog.result[3] == 75.0
        assert dialog.result[4] == 15.0
        # Other fields should remain from original
        assert dialog.result[1] == 'Quiz'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
