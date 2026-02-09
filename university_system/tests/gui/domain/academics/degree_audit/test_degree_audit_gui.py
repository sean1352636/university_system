"""
Tests for Degree Audit & Academic Advising GUI

This module tests the DegreeAuditGUI class which provides a comprehensive
interface for degree progress tracking, prerequisites, what-if scenarios,
advising appointments, and graduation audits.
"""

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, MagicMock, patch, call
import sqlite3
from datetime import datetime

from university_system.modules.domain.academics.gui.degree_audit_gui import (
    DegreeAuditGUI, launch_degree_audit_gui
)
from university_system.infrastructure.auth import UserAuth


@pytest.fixture
def mock_auth():
    """Create a mock authentication system"""
    auth = Mock()
    auth.current_user = {
        'id': 1,
        'username': 'student001',
        'email': 'student@example.com',
        'role': 'student'
    }
    auth.is_logged_in.return_value = True
    return auth


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
def mock_db_connection():
    """Create a mock database connection"""
    conn = Mock(spec=sqlite3.Connection)
    cursor = Mock(spec=sqlite3.Cursor)
    conn.cursor.return_value = cursor
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cursor


class TestDegreeAuditGUI:
    """Test suite for DegreeAuditGUI"""

    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.initialize_degree_audit_database')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.get_connection')
    def test_initialization(self, mock_get_conn, mock_init_db, root_window, mock_auth):
        """Test GUI initialization"""
        conn, cursor = Mock(), Mock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        gui = DegreeAuditGUI(root_window, mock_auth)

        assert gui.auth == mock_auth
        assert gui.root is not None
        assert hasattr(gui, 'notebook')
        mock_init_db.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.get_connection')
    def test_load_programs(self, mock_get_conn, root_window, mock_auth):
        """Test loading degree programs"""
        conn, cursor = Mock(), Mock()
        cursor.fetchall.return_value = [
            (1, 'CS', 'Computer Science BSc'),
            (2, 'MATH', 'Mathematics BSc'),
            (3, 'ENG', 'Engineering BEng')
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        with patch('university_system.modules.domain.academics.gui.degree_audit_gui.initialize_degree_audit_database'):
            gui = DegreeAuditGUI(root_window, mock_auth)
            gui.load_programs()

        cursor.execute.assert_called()
        assert cursor.fetchall.called

    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.DegreeProgressManager')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.get_connection')
    def test_load_student_progress(self, mock_get_conn, mock_progress_mgr, root_window, mock_auth):
        """Test loading student degree progress"""
        # Mock progress data
        mock_progress_mgr.get_student_progress.return_value = {
            'program_id': 1,
            'program_name': 'Computer Science BSc',
            'total_credits_earned': 90,
            'total_credits_required': 120,
            'current_gpa': 3.5,
            'completion_percentage': 75.0,
            'enrollment_year': 2021,
            'expected_graduation_date': '2025-06-01'
        }

        conn, cursor = Mock(), Mock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        with patch('university_system.modules.domain.academics.gui.degree_audit_gui.initialize_degree_audit_database'):
            gui = DegreeAuditGUI(root_window, mock_auth)
            gui.progress_student_entry.insert(0, 'student001')
            gui.load_student_progress()

        mock_progress_mgr.get_student_progress.assert_called_with('student001')

    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.DegreeProgressManager')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.get_connection')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.log_activity')
    def test_update_progress(self, mock_log, mock_get_conn, mock_progress_mgr, root_window, mock_auth):
        """Test updating student progress"""
        mock_progress_mgr.get_student_progress.return_value = {'program_id': 1}

        conn, cursor = Mock(), Mock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        with patch('university_system.modules.domain.academics.gui.degree_audit_gui.initialize_degree_audit_database'):
            with patch('tkinter.messagebox.showinfo'):
                gui = DegreeAuditGUI(root_window, mock_auth)
                gui.progress_student_entry.insert(0, 'student001')
                gui.update_progress()

        mock_progress_mgr.update_progress.assert_called_once()
        mock_log.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.DegreeProgressManager')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.get_connection')
    def test_check_prerequisites(self, mock_get_conn, mock_progress_mgr, root_window, mock_auth):
        """Test checking course prerequisites"""
        mock_progress_mgr.check_prerequisite_completion.return_value = (True, [])

        conn, cursor = Mock(), Mock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        with patch('university_system.modules.domain.academics.gui.degree_audit_gui.initialize_degree_audit_database'):
            with patch('university_system.modules.domain.academics.gui.degree_audit_gui.log_activity'):
                gui = DegreeAuditGUI(root_window, mock_auth)
                gui.prereq_student_entry.insert(0, 'student001')
                gui.prereq_module_entry.insert(0, 'CS201')
                gui.check_prerequisites()

        mock_progress_mgr.check_prerequisite_completion.assert_called_with('student001', 'CS201')

    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.WhatIfScenarioManager')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.get_connection')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.log_activity')
    def test_create_whatif_scenario(self, mock_log, mock_get_conn, mock_scenario_mgr, root_window, mock_auth):
        """Test creating what-if scenario"""
        mock_scenario_mgr.create_scenario.return_value = 1

        conn, cursor = Mock(), Mock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        with patch('university_system.modules.domain.academics.gui.degree_audit_gui.initialize_degree_audit_database'):
            with patch('tkinter.messagebox.showinfo'):
                gui = DegreeAuditGUI(root_window, mock_auth)
                gui.whatif_student_entry.insert(0, 'student001')
                gui.whatif_name_entry.insert(0, 'Switch to Math Major')
                gui.whatif_program_combo.set('2: MATH - Mathematics BSc')
                gui.create_whatif_scenario()

        mock_scenario_mgr.create_scenario.assert_called_once()
        mock_log.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.AdvisingAppointmentManager')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.get_connection')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.log_activity')
    def test_schedule_appointment(self, mock_log, mock_get_conn, mock_appt_mgr, root_window, mock_auth):
        """Test scheduling advising appointment"""
        mock_appt_mgr.schedule_appointment.return_value = 1

        conn, cursor = Mock(), Mock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        with patch('university_system.modules.domain.academics.gui.degree_audit_gui.initialize_degree_audit_database'):
            with patch('tkinter.messagebox.showinfo'):
                gui = DegreeAuditGUI(root_window, mock_auth)
                gui.appointment_fields['student'].insert(0, 'student001')
                gui.appointment_fields['advisor'].insert(0, 'advisor01')
                gui.appointment_fields['date'].delete(0, tk.END)
                gui.appointment_fields['date'].insert(0, '2025-12-01')
                gui.appointment_fields['time'].delete(0, tk.END)
                gui.appointment_fields['time'].insert(0, '10:00')
                gui.schedule_appointment()

        mock_appt_mgr.schedule_appointment.assert_called_once()
        mock_log.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.GraduationAuditManager')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.get_connection')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.log_activity')
    def test_run_graduation_audit(self, mock_log, mock_get_conn, mock_grad_mgr, root_window, mock_auth):
        """Test running graduation audit"""
        mock_grad_mgr.run_graduation_audit.return_value = {
            'total_requirements': 40,
            'completed_requirements': 38,
            'all_requirements_met': False,
            'gpa_requirement_met': True,
            'credit_requirement_met': True,
            'can_graduate': False
        }

        conn, cursor = Mock(), Mock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        with patch('university_system.modules.domain.academics.gui.degree_audit_gui.initialize_degree_audit_database'):
            with patch('tkinter.messagebox.showinfo'):
                gui = DegreeAuditGUI(root_window, mock_auth)
                gui.grad_student_entry.insert(0, 'student001')
                gui.grad_program_combo.set('1: CS - Computer Science BSc')
                gui.run_graduation_audit()

        mock_grad_mgr.run_graduation_audit.assert_called_once()
        mock_log.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.GraduationAuditManager')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.get_connection')
    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.log_activity')
    def test_approve_graduation(self, mock_log, mock_get_conn, mock_grad_mgr, root_window, mock_auth):
        """Test approving student for graduation"""
        mock_grad_mgr.approve_graduation.return_value = True

        conn, cursor = Mock(), Mock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        with patch('university_system.modules.domain.academics.gui.degree_audit_gui.initialize_degree_audit_database'):
            with patch('tkinter.messagebox.askyesno', return_value=True):
                with patch('tkinter.messagebox.showinfo'):
                    gui = DegreeAuditGUI(root_window, mock_auth)
                    gui.grad_student_entry.insert(0, 'student001')
                    gui.grad_program_combo.set('1: CS - Computer Science BSc')
                    gui.approve_graduation()

        mock_grad_mgr.approve_graduation.assert_called_once()
        mock_log.assert_called_once()


class TestLaunchDegreeAuditGUI:
    """Test the launch function"""

    @patch('university_system.modules.domain.academics.gui.degree_audit_gui.DegreeAuditGUI')
    def test_launch_with_auth(self, mock_gui_class, root_window):
        """Test launching GUI with authenticated user"""
        auth = Mock(spec=UserAuth)
        auth.current_user = {'username': 'student001'}

        launch_degree_audit_gui(root_window, auth)

        mock_gui_class.assert_called_once_with(root_window, auth)

    @patch('tkinter.messagebox.showerror')
    def test_launch_without_auth(self, mock_error, root_window):
        """Test launching GUI without authentication"""
        launch_degree_audit_gui(root_window, None)

        mock_error.assert_called_once()

    @patch('tkinter.messagebox.showerror')
    def test_launch_with_error(self, mock_error, root_window):
        """Test launching GUI with error"""
        auth = Mock()
        auth.current_user = {'username': 'student001'}

        with patch('university_system.modules.domain.academics.gui.degree_audit_gui.DegreeAuditGUI',
                   side_effect=Exception("Test error")):
            launch_degree_audit_gui(root_window, auth)

        mock_error.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
