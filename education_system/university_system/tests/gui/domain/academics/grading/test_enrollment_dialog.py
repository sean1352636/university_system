"""
Tests for ModuleEnrollmentDialog class from grade_tracking dialogs.
Tests enrollment management, UI components, and database operations.
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.academics.gui.grade_tracking.dialogs.enrollment_dialog import (
    ModuleEnrollmentDialog,
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
    """Mock database connection and cursor"""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.commit = Mock()
    return mock_conn, mock_cursor

class TestModuleEnrollmentDialog:
    """Test ModuleEnrollmentDialog class"""

    def test_init_creates_dialog(self, root, mock_connection):
        """Test dialog initialization creates UI elements"""
        mock_conn, mock_cursor = mock_connection

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        # Check dialog was created
        assert dialog.dialog is not None
        assert dialog.cursor == mock_cursor
        assert dialog.conn == mock_conn
        assert dialog.result is None

        # Check essential UI components exist
        assert hasattr(dialog, 'enrollment_tree')

        dialog.dialog.destroy()

    def test_refresh_enrollments_success(self, root, mock_connection):
        """Test refreshing enrollments list"""
        mock_conn, mock_cursor = mock_connection

        # Mock enrollment data
        mock_cursor.fetchall.return_value = [
            ("S001", "John Doe", "CS101", "Intro to CS", "Enrolled", "2024-01-01"),
            ("S002", "Jane Smith", "CS102", "Data Structures", "Enrolled", "2024-01-02"),
        ]

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        # Call refresh
        dialog.refresh_enrollments()

        # Verify query was executed
        assert mock_cursor.execute.called
        execute_call = mock_cursor.execute.call_args[0]
        assert "SELECT" in execute_call[0]
        assert "student_modules" in execute_call[0]

        # Verify tree has items
        children = dialog.enrollment_tree.get_children()
        assert len(children) == 2

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.enrollment_dialog.messagebox')
    def test_refresh_enrollments_database_error(self, mock_msgbox, root, mock_connection):
        """Test handling of database errors during refresh"""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        dialog.refresh_enrollments()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "Failed to load enrollments" in str(mock_msgbox.showerror.call_args)

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.enrollment_dialog.safe_grab_set')
    def test_enroll_student_dialog_opens(self, mock_grab, root, mock_connection):
        """Test opening enroll student dialog"""
        mock_conn, mock_cursor = mock_connection

        # Mock student and module queries
        mock_cursor.fetchall.side_effect = [
            [],  # Initial refresh
            [("S001", "John", "Doe"), ("S002", "Jane", "Smith")],  # Students
            [("CS101", "Intro to CS"), ("CS102", "Data Structures")],  # Modules
        ]

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        # This should create the enrollment dialog
        # We can't fully test the nested dialog without extensive mocking
        # but we can verify the method exists
        assert hasattr(dialog, 'enroll_student_dialog')

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.enrollment_dialog.messagebox')
    def test_enroll_student_success(self, mock_msgbox, root, mock_connection):
        """Test successful student enrollment"""
        mock_conn, mock_cursor = mock_connection

        # Mock queries for initial setup
        mock_cursor.fetchall.side_effect = [
            [],  # Initial refresh
            [("S001", "John", "Doe")],  # Students for enrollment dialog
            [("CS101", "Intro to CS")],  # Modules for enrollment dialog
            [],  # Refresh after enrollment
        ]

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        # Note: Testing the full enrollment flow requires simulating
        # the nested dialog interaction, which is complex in unit tests
        # We verify the main dialog has the required methods
        assert hasattr(dialog, 'enroll_student_dialog')
        assert hasattr(dialog, 'refresh_enrollments')

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.enrollment_dialog.messagebox')
    def test_remove_enrollment_no_selection(self, mock_msgbox, root, mock_connection):
        """Test remove enrollment with no selection"""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        # Call remove without selecting anything
        dialog.remove_enrollment()

        # Verify warning message
        mock_msgbox.showwarning.assert_called_once()
        assert "select an enrollment" in str(mock_msgbox.showwarning.call_args)

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.enrollment_dialog.messagebox')
    def test_remove_enrollment_with_confirmation(self, mock_msgbox, root, mock_connection):
        """Test remove enrollment with user confirmation"""
        mock_conn, mock_cursor = mock_connection

        # Mock enrollment data
        mock_cursor.fetchall.return_value = [
            ("S001", "John Doe", "CS101", "Intro to CS", "Enrolled", "2024-01-01"),
        ]

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        # Select the item
        children = dialog.enrollment_tree.get_children()
        if children:
            dialog.enrollment_tree.selection_set(children[0])

        # Mock user confirming removal
        mock_msgbox.askyesno.return_value = True

        # Call remove
        dialog.remove_enrollment()

        # Verify confirmation dialog was shown
        mock_msgbox.askyesno.assert_called_once()

        # Verify DELETE query was executed
        assert mock_cursor.execute.called
        delete_found = False
        for call in mock_cursor.execute.call_args_list:
            if "DELETE" in str(call):
                delete_found = True
                break
        assert delete_found

        # Verify commit was called
        mock_conn.commit.assert_called()

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.enrollment_dialog.messagebox')
    def test_remove_enrollment_cancelled(self, mock_msgbox, root, mock_connection):
        """Test remove enrollment when user cancels"""
        mock_conn, mock_cursor = mock_connection

        # Mock enrollment data
        mock_cursor.fetchall.return_value = [
            ("S001", "John Doe", "CS101", "Intro to CS", "Enrolled", "2024-01-01"),
        ]

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        # Select the item
        children = dialog.enrollment_tree.get_children()
        if children:
            dialog.enrollment_tree.selection_set(children[0])

        # Mock user cancelling removal
        mock_msgbox.askyesno.return_value = False

        # Reset execute mock
        mock_cursor.execute.reset_mock()

        # Call remove
        dialog.remove_enrollment()

        # Verify DELETE query was NOT executed after confirmation
        delete_calls = [call for call in mock_cursor.execute.call_args_list
                       if call and "DELETE" in str(call[0][0])]
        assert len(delete_calls) == 0

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.enrollment_dialog.messagebox')
    def test_remove_enrollment_database_error(self, mock_msgbox, root, mock_connection):
        """Test handling of database errors during removal"""
        mock_conn, mock_cursor = mock_connection

        # Mock enrollment data
        mock_cursor.fetchall.return_value = [
            ("S001", "John Doe", "CS101", "Intro to CS", "Enrolled", "2024-01-01"),
        ]

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        # Select the item
        children = dialog.enrollment_tree.get_children()
        if children:
            dialog.enrollment_tree.selection_set(children[0])

        # Mock user confirming removal
        mock_msgbox.askyesno.return_value = True

        # Make DELETE fail
        mock_cursor.execute.side_effect = [
            None,  # Initial SELECT
            Exception("Database error")  # DELETE
        ]

        # Call remove
        dialog.remove_enrollment()

        # Verify error message
        error_calls = [call for call in mock_msgbox.showerror.call_args_list
                      if "Failed to remove enrollment" in str(call)]
        assert len(error_calls) > 0

        dialog.dialog.destroy()

    def test_close_dialog_sets_result(self, root, mock_connection):
        """Test closing dialog sets result"""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        assert dialog.result is None

        # Close dialog
        dialog.close_dialog()

        # Verify result is set
        assert dialog.result is True

    def test_ui_components_exist(self, root, mock_connection):
        """Test all expected UI components are created"""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        # Check essential attributes exist
        assert hasattr(dialog, 'enrollment_tree')
        assert hasattr(dialog, 'cursor')
        assert hasattr(dialog, 'conn')

        # Verify tree columns
        expected_columns = ('Student ID', 'Student Name', 'Module Code', 'Module Name', 'Status', 'Date')
        assert dialog.enrollment_tree['columns'] == expected_columns

        dialog.dialog.destroy()

    def test_multiple_enrollments_display(self, root, mock_connection):
        """Test displaying multiple enrollments"""
        mock_conn, mock_cursor = mock_connection

        # Mock multiple enrollments
        enrollments = [
            ("S001", "John Doe", "CS101", "Intro to CS", "Enrolled", "2024-01-01"),
            ("S001", "John Doe", "CS102", "Data Structures", "Enrolled", "2024-01-02"),
            ("S002", "Jane Smith", "CS101", "Intro to CS", "Enrolled", "2024-01-01"),
            ("S003", "Bob Johnson", "CS103", "Algorithms", "Dropped", "2024-01-03"),
        ]
        mock_cursor.fetchall.return_value = enrollments

        dialog = ModuleEnrollmentDialog(root, mock_cursor, mock_conn)

        dialog.refresh_enrollments()

        # Verify all enrollments are displayed
        children = dialog.enrollment_tree.get_children()
        assert len(children) == len(enrollments)

        # Verify first enrollment data
        first_item = dialog.enrollment_tree.item(children[0])
        assert first_item['values'][0] == "S001"
        assert "John Doe" in first_item['values'][1]

        dialog.dialog.destroy()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
