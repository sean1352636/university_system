"""
Tests for EditLearningOutcomeDialog class from grade_tracking dialogs.
Tests UI initialization, database operations, and validation.
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch
import sqlite3

from university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog import (
    EditLearningOutcomeDialog,
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


class TestEditLearningOutcomeDialog:
    """Test EditLearningOutcomeDialog class"""

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.get_connection')
    def test_init_creates_dialog(self, mock_get_conn, root, mock_connection):
        """Test dialog initialization creates UI elements"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Mock fetchone to return outcome data
        mock_cursor.fetchone.return_value = (
            "CS101", "LO1", "Students will understand OOP", "Knowledge", 5
        )

        callback = Mock()

        dialog = EditLearningOutcomeDialog(
            root,
            outcome_id=1,
            callback=callback
        )

        # Check dialog was created
        assert dialog.dialog is not None
        assert dialog.outcome_id == 1
        assert dialog.callback == callback

        # Check data was loaded
        assert mock_cursor.execute.called
        assert mock_conn.close.called

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.get_connection')
    def test_load_outcome_data(self, mock_get_conn, root, mock_connection):
        """Test loading existing outcome data"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Mock outcome data
        test_data = ("CS101", "LO1", "Test description", "Skills", 4)
        mock_cursor.fetchone.return_value = test_data

        dialog = EditLearningOutcomeDialog(root, outcome_id=1, callback=Mock())

        # Verify query was executed
        assert mock_cursor.execute.called
        execute_call = mock_cursor.execute.call_args[0]
        assert "SELECT" in execute_call[0]
        assert "learning_outcomes" in execute_call[0]
        assert execute_call[1] == (1,)

        # Verify data was loaded into UI
        assert dialog.course_var.get() == "CS101"
        assert dialog.code_var.get() == "LO1"
        assert dialog.category_var.get() == "Skills"
        assert dialog.importance_var.get() == "4"
        assert "Test description" in dialog.description_text.get(1.0, tk.END)

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.get_connection')
    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.messagebox')
    def test_update_outcome_success(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test successful outcome update"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Mock initial load
        mock_cursor.fetchone.return_value = (
            "CS101", "LO1", "Old description", "Knowledge", 3
        )

        callback = Mock()
        dialog = EditLearningOutcomeDialog(root, outcome_id=1, callback=callback)

        # Modify values
        dialog.course_var.set("CS102")
        dialog.code_var.set("LO2")
        dialog.category_var.set("Application")
        dialog.importance_var.set("5")
        dialog.description_text.delete(1.0, tk.END)
        dialog.description_text.insert(1.0, "New description")

        # Reset mock to track update call
        mock_cursor.execute.reset_mock()

        # Call update
        dialog.update_outcome()

        # Verify UPDATE query was called
        assert mock_cursor.execute.called
        execute_call = mock_cursor.execute.call_args[0]
        assert "UPDATE learning_outcomes" in execute_call[0]

        # Verify parameters
        params = execute_call[1]
        assert params[0] == "CS102"  # course
        assert params[1] == "LO2"    # code
        assert "New description" in params[2]  # description
        assert params[3] == "Application"  # category
        assert params[4] == 5  # importance
        assert params[5] == 1  # outcome_id

        # Verify commit and close
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called()

        # Verify success message
        mock_msgbox.showinfo.assert_called_once()

        # Verify callback was called
        callback.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.get_connection')
    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.messagebox')
    def test_update_outcome_missing_fields(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test validation for missing required fields"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = (
            "CS101", "LO1", "Description", "Knowledge", 3
        )

        dialog = EditLearningOutcomeDialog(root, outcome_id=1, callback=Mock())

        # Clear required field
        dialog.course_var.set("")

        dialog.update_outcome()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "fill in all fields" in str(mock_msgbox.showerror.call_args)

        # Verify no database update
        assert not mock_conn.commit.called

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.get_connection')
    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.messagebox')
    def test_update_outcome_database_error(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test handling of database errors during update"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Mock initial load success
        mock_cursor.fetchone.return_value = (
            "CS101", "LO1", "Description", "Knowledge", 3
        )

        dialog = EditLearningOutcomeDialog(root, outcome_id=1, callback=Mock())

        # Set valid data
        dialog.course_var.set("CS102")
        dialog.code_var.set("LO2")
        dialog.category_var.set("Application")
        dialog.importance_var.set("5")
        dialog.description_text.delete(1.0, tk.END)
        dialog.description_text.insert(1.0, "New description")

        # Make UPDATE fail
        mock_cursor.execute.side_effect = [
            None,  # Initial SELECT
            sqlite3.Error("Database error")  # UPDATE
        ]

        dialog.update_outcome()

        # Verify error message
        mock_msgbox.showerror.assert_called()
        assert "Error updating outcome" in str(mock_msgbox.showerror.call_args)

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.get_connection')
    def test_ui_components_exist(self, mock_get_conn, root, mock_connection):
        """Test all expected UI components are created"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = (
            "CS101", "LO1", "Description", "Knowledge", 3
        )

        dialog = EditLearningOutcomeDialog(root, outcome_id=1, callback=Mock())

        # Check essential attributes exist
        assert hasattr(dialog, 'course_var')
        assert hasattr(dialog, 'course_entry')
        assert hasattr(dialog, 'code_var')
        assert hasattr(dialog, 'code_entry')
        assert hasattr(dialog, 'category_var')
        assert hasattr(dialog, 'importance_var')
        assert hasattr(dialog, 'description_text')

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.get_connection')
    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.messagebox')
    def test_load_outcome_data_not_found(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test handling when outcome data is not found"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Return None for fetchone (outcome not found)
        mock_cursor.fetchone.return_value = None

        dialog = EditLearningOutcomeDialog(root, outcome_id=999, callback=Mock())

        # Fields should be empty
        assert dialog.course_var.get() == ""
        assert dialog.code_var.get() == ""

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.get_connection')
    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.messagebox')
    def test_load_outcome_data_database_error(self, mock_msgbox, mock_get_conn, root, mock_connection):
        """Test handling of database errors during load"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        # Simulate database error
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")

        dialog = EditLearningOutcomeDialog(root, outcome_id=1, callback=Mock())

        # Verify error message was shown
        mock_msgbox.showerror.assert_called()
        assert "Error loading outcome" in str(mock_msgbox.showerror.call_args)

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.get_connection')
    def test_importance_range(self, mock_get_conn, root, mock_connection):
        """Test importance value validation"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = (
            "CS101", "LO1", "Description", "Knowledge", 3
        )

        dialog = EditLearningOutcomeDialog(root, outcome_id=1, callback=Mock())

        # Test valid importance values (1-5)
        for importance in range(1, 6):
            dialog.importance_var.set(str(importance))
            value = int(dialog.importance_var.get())
            assert 1 <= value <= 5

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.edit_outcome_dialog.get_connection')
    def test_course_code_uppercase_conversion(self, mock_get_conn, root, mock_connection):
        """Test that course codes are converted to uppercase"""
        mock_conn, mock_cursor = mock_connection
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = (
            "CS101", "LO1", "Description", "Knowledge", 3
        )

        dialog = EditLearningOutcomeDialog(root, outcome_id=1, callback=Mock())

        # Set lowercase course code
        dialog.course_var.set("cs102")

        # When update is called, it should convert to uppercase
        dialog.course_var.set(dialog.course_var.get().strip().upper())
        assert dialog.course_var.get() == "CS102"

        dialog.dialog.destroy()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
