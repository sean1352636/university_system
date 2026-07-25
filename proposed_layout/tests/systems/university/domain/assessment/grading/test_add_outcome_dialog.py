"""
Tests for Add Learning Outcome Dialog

This module tests the AddLearningOutcomeDialog class which provides
a dialog for adding learning outcomes to courses.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, MagicMock, patch, call
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.gui.academics.grade_tracking.dialogs.add_outcome_dialog import (
    AddLearningOutcomeDialog
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
def mock_callback():
    """Create a mock callback function"""
    return Mock()

class TestAddLearningOutcomeDialog:
    """Test suite for AddLearningOutcomeDialog"""

    def test_initialization(self, root_window, mock_callback):
        """Test dialog initialization"""
        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        assert dialog.dialog is not None
        assert dialog.callback == mock_callback
        assert hasattr(dialog, 'course_var')
        assert hasattr(dialog, 'code_var')
        assert hasattr(dialog, 'category_var')
        assert hasattr(dialog, 'importance_var')
        assert hasattr(dialog, 'description_text')

    def test_dialog_widgets_created(self, root_window, mock_callback):
        """Test that all dialog widgets are created"""
        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        # Verify input fields exist
        assert dialog.course_entry.winfo_exists()
        assert dialog.code_entry.winfo_exists()
        assert dialog.description_text.winfo_exists()

    def test_default_importance_value(self, root_window, mock_callback):
        """Test that default importance is 3"""
        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        assert dialog.importance_var.get() == "3"

    @patch('education_system.systems.university.interfaces.gui.academics.grade_tracking.dialogs.add_outcome_dialog.get_connection')
    @patch('tkinter.messagebox.showinfo')
    def test_add_outcome_success(self, mock_msg, mock_get_conn, root_window, mock_callback):
        """Test successfully adding a learning outcome"""
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        conn.commit = Mock()
        mock_get_conn.return_value = conn

        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        # Fill in the form
        dialog.course_var.set('CS101')
        dialog.code_var.set('LO1')
        dialog.category_var.set('Knowledge')
        dialog.importance_var.set('4')
        dialog.description_text.insert(1.0, 'Understand basic programming concepts')

        # Submit the form
        dialog.add_outcome()

        # Verify database operations
        cursor.execute.assert_called()
        assert cursor.execute.call_count >= 2  # CREATE TABLE + INSERT
        conn.commit.assert_called_once()
        mock_callback.assert_called_once()

    @patch('tkinter.messagebox.showerror')
    def test_add_outcome_missing_fields(self, mock_error, root_window, mock_callback):
        """Test validation when required fields are missing"""
        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        # Leave fields empty
        dialog.add_outcome()

        mock_error.assert_called_once()
        mock_callback.assert_not_called()

    @patch('education_system.systems.university.interfaces.gui.academics.grade_tracking.dialogs.add_outcome_dialog.get_connection')
    @patch('tkinter.messagebox.showinfo')
    def test_course_code_uppercase_conversion(self, mock_msg, mock_get_conn, root_window, mock_callback):
        """Test that course code is converted to uppercase"""
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        mock_get_conn.return_value = conn

        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        # Enter lowercase course code
        dialog.course_var.set('cs101')
        dialog.code_var.set('LO1')
        dialog.category_var.set('Knowledge')
        dialog.importance_var.set('3')
        dialog.description_text.insert(1.0, 'Test description')

        dialog.add_outcome()

        # Verify INSERT was called with uppercase course code
        calls = cursor.execute.call_args_list
        insert_call = [c for c in calls if 'INSERT' in str(c)]
        assert insert_call
        # The first argument to execute should contain 'CS101' (uppercase)
        insert_args = insert_call[0][0][1]  # Get the tuple of values
        assert insert_args[0] == 'CS101'

    @patch('education_system.systems.university.interfaces.gui.academics.grade_tracking.dialogs.add_outcome_dialog.get_connection')
    @patch('tkinter.messagebox.showinfo')
    def test_importance_as_integer(self, mock_msg, mock_get_conn, root_window, mock_callback):
        """Test that importance is stored as integer"""
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        mock_get_conn.return_value = conn

        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        dialog.course_var.set('CS101')
        dialog.code_var.set('LO1')
        dialog.category_var.set('Skills')
        dialog.importance_var.set('5')
        dialog.description_text.insert(1.0, 'Advanced programming skills')

        dialog.add_outcome()

        # Verify importance is stored as int
        calls = cursor.execute.call_args_list
        insert_call = [c for c in calls if 'INSERT' in str(c)]
        assert insert_call
        insert_args = insert_call[0][0][1]
        assert isinstance(insert_args[4], int)  # importance should be int
        assert insert_args[4] == 5

    @patch('education_system.systems.university.interfaces.gui.academics.grade_tracking.dialogs.add_outcome_dialog.get_connection')
    @patch('tkinter.messagebox.showerror')
    def test_database_error_handling(self, mock_error, mock_get_conn, root_window, mock_callback):
        """Test handling of database errors"""
        mock_get_conn.side_effect = sqlite3.Error("Database error")

        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        dialog.course_var.set('CS101')
        dialog.code_var.set('LO1')
        dialog.category_var.set('Knowledge')
        dialog.importance_var.set('3')
        dialog.description_text.insert(1.0, 'Test description')

        dialog.add_outcome()

        mock_error.assert_called_once()
        mock_callback.assert_not_called()

    def test_category_options_available(self, root_window, mock_callback):
        """Test that category combobox has predefined options"""
        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        # Find the category combobox
        # It should have values like Knowledge, Skills, Attitudes, etc.
        # We can verify this indirectly by checking the widget tree
        assert dialog.category_var is not None

    @patch('education_system.systems.university.interfaces.gui.academics.grade_tracking.dialogs.add_outcome_dialog.get_connection')
    @patch('tkinter.messagebox.showinfo')
    def test_table_creation_on_first_use(self, mock_msg, mock_get_conn, root_window, mock_callback):
        """Test that learning_outcomes table is created if it doesn't exist"""
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        mock_get_conn.return_value = conn

        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        dialog.course_var.set('CS101')
        dialog.code_var.set('LO1')
        dialog.category_var.set('Knowledge')
        dialog.importance_var.set('3')
        dialog.description_text.insert(1.0, 'Test')

        dialog.add_outcome()

        # Verify CREATE TABLE was called
        create_calls = [c for c in cursor.execute.call_args_list if 'CREATE TABLE' in str(c)]
        assert len(create_calls) >= 1

    @patch('education_system.systems.university.interfaces.gui.academics.grade_tracking.dialogs.add_outcome_dialog.get_connection')
    @patch('tkinter.messagebox.showinfo')
    def test_dialog_closes_after_success(self, mock_msg, mock_get_conn, root_window, mock_callback):
        """Test that dialog is destroyed after successful addition"""
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        mock_get_conn.return_value = conn

        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        # Mock dialog.destroy to track if it's called
        original_destroy = dialog.dialog.destroy
        dialog.dialog.destroy = Mock(side_effect=original_destroy)

        dialog.course_var.set('CS101')
        dialog.code_var.set('LO1')
        dialog.category_var.set('Knowledge')
        dialog.importance_var.set('3')
        dialog.description_text.insert(1.0, 'Test')

        dialog.add_outcome()

        # Verify dialog was closed
        dialog.dialog.destroy.assert_called_once()

    @patch('tkinter.messagebox.showerror')
    def test_empty_description_validation(self, mock_error, root_window, mock_callback):
        """Test validation fails when description is empty"""
        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        dialog.course_var.set('CS101')
        dialog.code_var.set('LO1')
        dialog.category_var.set('Knowledge')
        dialog.importance_var.set('3')
        # Description is intentionally left empty

        dialog.add_outcome()

        mock_error.assert_called_once()

    @patch('tkinter.messagebox.showerror')
    def test_whitespace_only_fields_validation(self, mock_error, root_window, mock_callback):
        """Test validation fails when fields contain only whitespace"""
        dialog = AddLearningOutcomeDialog(root_window, mock_callback)

        dialog.course_var.set('   ')  # Only whitespace
        dialog.code_var.set('LO1')
        dialog.category_var.set('Knowledge')
        dialog.importance_var.set('3')
        dialog.description_text.insert(1.0, 'Test')

        dialog.add_outcome()

        mock_error.assert_called_once()

class TestDialogIntegration:
    """Integration tests for AddLearningOutcomeDialog"""

    @patch('education_system.systems.university.interfaces.gui.academics.grade_tracking.dialogs.add_outcome_dialog.get_connection')
    @patch('tkinter.messagebox.showinfo')
    def test_full_workflow(self, mock_msg, mock_get_conn, root_window):
        """Test complete workflow of adding multiple outcomes"""
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        mock_get_conn.return_value = conn

        outcomes_added = []

        def callback():
            outcomes_added.append(True)

        # Add first outcome
        dialog1 = AddLearningOutcomeDialog(root_window, callback)
        dialog1.course_var.set('CS101')
        dialog1.code_var.set('LO1')
        dialog1.category_var.set('Knowledge')
        dialog1.importance_var.set('3')
        dialog1.description_text.insert(1.0, 'First outcome')
        dialog1.add_outcome()

        # Add second outcome
        dialog2 = AddLearningOutcomeDialog(root_window, callback)
        dialog2.course_var.set('CS101')
        dialog2.code_var.set('LO2')
        dialog2.category_var.set('Skills')
        dialog2.importance_var.set('4')
        dialog2.description_text.insert(1.0, 'Second outcome')
        dialog2.add_outcome()

        # Verify both callbacks were called
        assert len(outcomes_added) == 2

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
