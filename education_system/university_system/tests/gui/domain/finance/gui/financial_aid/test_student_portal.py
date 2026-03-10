"""
Tests for Student Portal GUI

This module contains unit tests for the student-facing financial aid portal.
"""

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch
import json

from education_system.university_system.modules.domain.finance.gui.financial_aid.student_portal import StudentPortal


class TestStudentPortalInit:
    """Test StudentPortal initialization"""

    @patch('university_system.modules.domain.finance.gui.financial_aid.student_portal.get_student_id')
    @patch('university_system.modules.domain.finance.gui.financial_aid.student_portal.get_current_user')
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

    @patch('university_system.modules.domain.finance.gui.financial_aid.student_portal.get_connection')
    @patch('university_system.modules.domain.finance.gui.financial_aid.student_portal.get_student_id')
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

        assert len(parent_frame.winfo_children()) > 0

        root.destroy()


class TestScholarshipBrowsing:
    """Test scholarship browsing functionality"""

    @patch('university_system.modules.domain.finance.gui.financial_aid.student_portal.get_student_id')
    def test_show_scholarships(self, mock_get_id):
        """Test show_scholarships method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        mock_get_id.return_value = 'S12345'

        portal = StudentPortal(parent_frame, Mock())
        portal.scholarship_manager = Mock()
        portal.scholarship_manager.get_available_scholarships.return_value = []

        portal.show_scholarships()

        assert len(parent_frame.winfo_children()) > 0

        root.destroy()


class TestApplicationSubmission:
    """Test application submission"""

    @patch('university_system.modules.domain.finance.gui.financial_aid.student_portal.get_student_id')
    @patch('university_system.modules.domain.finance.gui.financial_aid.student_portal.log_activity')
    @patch('university_system.modules.domain.finance.gui.financial_aid.student_portal.show_success')
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
