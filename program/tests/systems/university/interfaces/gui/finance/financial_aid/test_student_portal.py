"""
Tests for Student Portal GUI

This module contains unit tests for the student-facing financial aid portal.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch
import json

from education_system.systems.university.interfaces.gui.finance.financial_aid.student_portal import StudentPortal

_PORTAL = 'education_system.systems.university.interfaces.gui.finance.financial_aid.student_portal.portal'
_DASHBOARD = 'education_system.systems.university.interfaces.gui.finance.financial_aid.student_portal.dashboard'
_SCHOLARSHIPS = 'education_system.systems.university.interfaces.gui.finance.financial_aid.student_portal.scholarships'


class TestStudentPortalInit:
    """Test StudentPortal initialization"""

    @patch(f'{_PORTAL}.get_student_id')
    @patch(f'{_PORTAL}.get_current_user')
    def test_init_with_auth(self, mock_get_user, mock_get_id):
        """Test initialization with auth instance"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        auth_mock = Mock()
        mock_get_id.return_value = 'S12345'
        mock_get_user.return_value = Mock(student_id='S12345')

        portal = StudentPortal(parent_frame, auth_mock)

        assert portal.parent_frame == parent_frame
        assert portal.auth == auth_mock
        assert portal.student_id == 'S12345'

        root.destroy()


class TestDashboard:
    """Test student dashboard"""

    @patch(f'{_DASHBOARD}.get_connection')
    @patch(f'{_PORTAL}.get_student_id')
    def test_show_dashboard(self, mock_get_id, mock_get_conn):
        """Test show_dashboard method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        mock_get_id.return_value = 'S12345'

        mock_conn = Mock()
        mock_conn.execute.return_value.fetchone.return_value = {'total': 5000.0, 'count': 3}
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        portal = StudentPortal(parent_frame, Mock())
        portal.show_dashboard()

        # Method should complete without error
        assert portal.parent_frame == parent_frame

        root.destroy()


class TestScholarshipBrowsing:
    """Test scholarship browsing functionality"""

    @patch(f'{_SCHOLARSHIPS}.get_connection')
    @patch(f'{_PORTAL}.get_student_id')
    def test_show_scholarships(self, mock_get_id, mock_get_conn):
        """Test show_scholarships method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        mock_get_id.return_value = 'S12345'

        mock_conn = Mock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        portal = StudentPortal(parent_frame, Mock())
        portal.scholarship_manager = Mock()
        portal.scholarship_manager.get_available_scholarships.return_value = []

        portal.show_scholarships()

        # Method should complete without error
        assert portal.parent_frame == parent_frame

        root.destroy()


class TestApplicationSubmission:
    """Test application submission"""

    @patch(f'{_PORTAL}.get_student_id')
    @patch(f'{_SCHOLARSHIPS}.log_activity')
    @patch(f'{_SCHOLARSHIPS}.show_success')
    def test_submit_scholarship_application(self, mock_success, mock_log, mock_get_id):
        """Test scholarship application submission"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        mock_get_id.return_value = 'S12345'

        portal = StudentPortal(parent_frame, Mock())
        portal.scholarship_manager = Mock()
        portal.scholarship_manager.submit_application.return_value = 'APP123'
        portal.current_user = {'email': 'test@example.com'}

        fields = {
            'essay': Mock(get=Mock(return_value='Test essay')),
            'gpa': Mock(get=Mock(return_value='3.5')),
            'graduation': Mock(get=Mock(return_value='2025-05-15')),
            'reference_name': Mock(get=Mock(return_value='Dr. Smith')),
            'reference_email': Mock(get=Mock(return_value='smith@example.com'))
        }

        result = portal._validate_and_submit_application('SCH123', fields, Mock())

        assert result is True
        mock_success.assert_called_once()

        root.destroy()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
