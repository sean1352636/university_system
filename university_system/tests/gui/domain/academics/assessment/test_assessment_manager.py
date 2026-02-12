"""
Tests for Assessment Manager

This module tests the AssessmentManager class which handles assessment
management including CRUD operations, filtering, and synchronization.
"""

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, MagicMock, patch, call
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime

from university_system.modules.domain.academics.gui.grade_tracking.assessment_manager import (
    AssessmentManager, percentage_to_letter, letter_to_percentage, letter_to_gpa
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
def mock_app(root_window):
    """Create a mock app instance"""
    app = Mock()
    app.root = root_window
    app.auth = Mock()
    app.auth.current_user = {'id': 1, 'username': 'instructor01'}

    # Create a mock layout with content_frame
    app.layout = Mock()
    app.layout.content_frame = ttk.Frame(root_window)

    return app

class TestGradeConversions:
    """Test grade conversion functions"""

    def test_percentage_to_letter_a_plus(self):
        """Test converting 95% to A+"""
        assert percentage_to_letter(95) == 'A+'

    def test_percentage_to_letter_a(self):
        """Test converting 87% to A"""
        assert percentage_to_letter(87) == 'A'

    def test_percentage_to_letter_b(self):
        """Test converting 72% to B"""
        assert percentage_to_letter(72) == 'B'

    def test_percentage_to_letter_c(self):
        """Test converting 57% to C"""
        assert percentage_to_letter(57) == 'C'

    def test_percentage_to_letter_f(self):
        """Test converting 30% to F"""
        assert percentage_to_letter(30) == 'F'

    def test_letter_to_gpa_a(self):
        """Test converting A to GPA"""
        assert letter_to_gpa('A') == 4.0

    def test_letter_to_gpa_b_plus(self):
        """Test converting B+ to GPA"""
        assert letter_to_gpa('B+') == 3.3

    def test_letter_to_gpa_f(self):
        """Test converting F to GPA"""
        assert letter_to_gpa('F') == 0.0

class TestAssessmentManager:
    """Test suite for AssessmentManager"""

    def test_initialization(self, mock_app):
        """Test assessment manager initialization"""
        manager = AssessmentManager(mock_app)

        assert manager.app == mock_app
        assert manager.root == mock_app.root
        assert manager.auth == mock_app.auth

    def test_content_frame_property(self, mock_app):
        """Test content_frame property"""
        manager = AssessmentManager(mock_app)

        frame = manager.content_frame

        assert frame == mock_app.layout.content_frame

    def test_create_assessment_content(self, mock_app):
        """Test creating assessment content"""
        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()

        assert hasattr(manager, 'assessment_tree')
        assert hasattr(manager, 'assessment_module_filter_var')
        assert hasattr(manager, 'assessment_module_combo')

    @patch('university_system.modules.domain.academics.gui.grade_tracking.assessment_manager.get_connection')
    def test_refresh_assessments(self, mock_get_conn, mock_app):
        """Test refreshing assessments list"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.side_effect = [
            # Assessments from assessments table
            [
                (1, 'Midterm Exam', 'Exam', 'CS101', 100, 30, '2025-11-15'),
                (2, 'Final Project', 'Project', 'CS101', 200, 40, '2025-12-15')
            ],
            # Assessments from assignments table
            [
                ('A1', 'Assignment 1', 'assignment', 'CS101', 100, 0, '2025-11-01')
            ]
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()
        manager.refresh_assessments()

        # Verify tree was populated
        assert manager.assessment_tree.get_children()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.assessment_manager.sqlite3')
    @patch('tkinter.messagebox.showinfo')
    def test_add_assessment_dialog(self, mock_msg, mock_sqlite, mock_app, root_window):
        """Test opening add assessment dialog"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [('CS101', 'Introduction to CS')]
        conn.cursor.return_value = cursor
        mock_sqlite.connect.return_value = conn

        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()

        # Open dialog (should not raise exception)
        manager.add_assessment_dialog()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.assessment_manager.get_connection')
    @patch('tkinter.messagebox.showinfo')
    def test_delete_assessment(self, mock_msg, mock_get_conn, mock_app):
        """Test deleting an assessment"""
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        conn.commit = Mock()
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()

        # Insert test item
        manager.assessment_tree.insert('', 'end', values=(1, 'Test Assessment', 'Exam', 'CS101', 100, '30%', '2025-11-15'))

        # Select the item
        items = manager.assessment_tree.get_children()
        manager.assessment_tree.selection_set(items[0])

        # Delete with confirmation
        with patch('tkinter.messagebox.askyesno', return_value=True):
            manager.delete_assessment()

        # Verify delete queries were executed
        assert cursor.execute.call_count >= 2
        conn.commit.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.assessment_manager.get_connection')
    @patch('tkinter.messagebox.showinfo')
    def test_copy_assessment(self, mock_msg, mock_get_conn, mock_app):
        """Test copying an assessment"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = (
            'Original Assessment', 'Exam', 'CS101', 100, 30,
            '2025-11-15', 'Test description', 'Test rubric'
        )
        conn.cursor.return_value = cursor
        conn.commit = Mock()
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()

        # Insert test item
        manager.assessment_tree.insert('', 'end', values=(1, 'Test Assessment', 'Exam', 'CS101', 100, '30%', '2025-11-15'))

        # Select the item
        items = manager.assessment_tree.get_children()
        manager.assessment_tree.selection_set(items[0])

        # Copy assessment
        manager.copy_assessment()

        # Verify insert query was executed
        cursor.execute.assert_called()
        conn.commit.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.assessment_manager.get_connection')
    def test_populate_filter_combos(self, mock_get_conn, mock_app):
        """Test populating filter comboboxes"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('CS101',),
            ('CS102',),
            ('MATH201',)
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()
        manager.populate_filter_combos()

        # Verify combo was populated
        assert manager.assessment_module_combo['values']

    @patch('university_system.modules.domain.academics.gui.grade_tracking.assessment_manager.get_connection')
    def test_filter_assessments(self, mock_get_conn, mock_app):
        """Test filtering assessments by module"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.side_effect = [
            # Filtered assessments from assessments table
            [(1, 'Midterm Exam', 'Exam', 'CS101', 100, 30, '2025-11-15')],
            # Filtered assessments from assignments table
            []
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()

        # Set filter
        manager.assessment_module_filter_var.set('CS101')
        manager.filter_assessments()

        # Verify filtered query was executed
        cursor.execute.assert_called()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.assessment_manager.AssessmentAssignmentService')
    @patch('tkinter.messagebox.showinfo')
    def test_sync_from_assignments(self, mock_msg, mock_service, mock_app):
        """Test syncing assessments from assignments table"""
        mock_service.get_all_assessments.return_value = [
            {
                'assessment_id': 1,
                'assessment_name': 'Test Assessment',
                'module_code': 'CS101'
            }
        ]
        mock_service.sync_assessment_to_assignment.return_value = 1

        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()

        with patch.object(manager, 'refresh_assessments'):
            manager.sync_from_assignments()

        mock_service.get_all_assessments.assert_called_once()
        mock_service.sync_assessment_to_assignment.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.assessment_manager.get_connection')
    @patch('tkinter.messagebox.showerror')
    def test_delete_assessment_no_selection(self, mock_error, mock_get_conn, mock_app):
        """Test deleting assessment with no selection"""
        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()

        # Try to delete without selection
        with patch('tkinter.messagebox.showwarning') as mock_warning:
            manager.delete_assessment()
            mock_warning.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.assessment_manager.get_connection')
    def test_generate_assessment_analysis(self, mock_get_conn, mock_app):
        """Test generating assessment analysis report"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            (1, 'Midterm Exam', 'CS101', 'Exam', 100, 30, 75.5, 2),
            (2, 'Final Project', 'CS102', 'Project', 200, 35, 82.0, 1)
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()

        # This method uses a private _display_report method
        # Just verify it doesn't crash
        with patch.object(manager, '_display_report', Mock()):
            manager.generate_assessment_analysis()

        cursor.execute.assert_called()

class TestAssessmentEditing:
    """Test assessment editing functionality"""

    @patch('university_system.modules.domain.academics.gui.grade_tracking.assessment_manager.get_connection')
    def test_edit_assessment_dialog(self, mock_get_conn, mock_app):
        """Test opening edit assessment dialog"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = (
            'Test Assessment', 'Exam', 'CS101', 100, 30,
            '2025-11-15', 'Description', 'Rubric'
        )
        cursor.fetchall.return_value = [('CS101', 'Introduction to CS')]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()

        # Insert test item
        manager.assessment_tree.insert('', 'end', values=(1, 'Test Assessment', 'Exam', 'CS101', 100, '30%', '2025-11-15'))

        # Select the item
        items = manager.assessment_tree.get_children()
        manager.assessment_tree.selection_set(items[0])

        # Open edit dialog (should not raise exception)
        manager.edit_assessment_dialog()

    @patch('tkinter.messagebox.showwarning')
    def test_edit_assessment_no_selection(self, mock_warning, mock_app):
        """Test editing assessment with no selection"""
        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()

        # Try to edit without selection
        manager.edit_assessment_dialog()

        mock_warning.assert_called_once()

class TestAssessmentIntegration:
    """Integration tests for assessment management"""

    @patch('university_system.modules.domain.academics.gui.grade_tracking.assessment_manager.get_connection')
    def test_full_assessment_workflow(self, mock_get_conn, mock_app):
        """Test complete assessment management workflow"""
        conn = Mock()
        cursor = Mock()

        # Set up return values for different queries
        cursor.fetchall.side_effect = [
            # Initial load - assessments table
            [(1, 'Midterm', 'Exam', 'CS101', 100, 30, '2025-11-15')],
            # Initial load - assignments table
            [],
            # After refresh - assessments table
            [
                (1, 'Midterm', 'Exam', 'CS101', 100, 30, '2025-11-15'),
                (2, 'Final', 'Exam', 'CS101', 200, 40, '2025-12-15')
            ],
            # After refresh - assignments table
            []
        ]

        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AssessmentManager(mock_app)
        manager.create_assessment_content()

        # Initial load
        manager.refresh_assessments()

        # Add another assessment (simulated)
        manager.refresh_assessments()

        # Verify multiple database calls were made
        assert cursor.execute.call_count >= 4

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
