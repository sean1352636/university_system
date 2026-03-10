"""
Tests for Scholarship Manager GUI

This module contains unit tests for the scholarship management interface.
"""

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch
import json

from education_system.university_system.modules.domain.finance.gui.financial_aid.scholarship_manager import ScholarshipManagerGUI


class TestScholarshipManagerInit:
    """Test ScholarshipManagerGUI initialization"""

    def test_init_with_auth(self):
        """Test initialization with auth instance"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        auth_mock = Mock()

        manager = ScholarshipManagerGUI(parent_frame, auth_mock)

        assert manager.parent_frame == parent_frame
        assert manager.auth == auth_mock
        assert manager.scholarship_manager is not None

        root.destroy()


class TestScholarshipOperations:
    """Test scholarship CRUD operations"""

    @patch('university_system.modules.domain.finance.gui.financial_aid.scholarship_manager.get_connection')
    def test_show_scholarships(self, mock_get_conn):
        """Test show_scholarships method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)

        mock_conn = Mock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        manager = ScholarshipManagerGUI(parent_frame, Mock())
        manager.show_scholarships()

        assert len(parent_frame.winfo_children()) > 0

        root.destroy()

    @patch('university_system.modules.domain.finance.gui.financial_aid.scholarship_manager.get_connection')
    def test_load_scholarships(self, mock_get_conn):
        """Test _load_all_scholarships method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)

        mock_scholarship = {
            'scholarship_id': 'SCH123',
            'scholarship_name': 'Test Scholarship',
            'amount': 5000.0,
            'academic_year': '2023-2024',
            'deadline': '2023-12-31',
            'is_active': 1
        }

        mock_conn = Mock()
        mock_conn.execute.return_value.fetchall.return_value = [Mock(**mock_scholarship)]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        manager = ScholarshipManagerGUI(parent_frame, Mock())
        manager.show_scholarships()

        root.destroy()


class TestApplicationReview:
    """Test application review functionality"""

    @patch('university_system.modules.domain.finance.gui.financial_aid.scholarship_manager.get_connection')
    def test_review_applications(self, mock_get_conn):
        """Test review_applications method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)

        mock_conn = Mock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        manager = ScholarshipManagerGUI(parent_frame, Mock())
        manager.review_applications()

        assert len(parent_frame.winfo_children()) > 0

        root.destroy()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
