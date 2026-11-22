"""
Tests for Degree Audit & Academic Advising GUI

This module tests the DegreeAuditGUI class which provides a comprehensive
interface for degree progress tracking, prerequisites, what-if scenarios,
advising appointments, and graduation audits.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime

_GUI_MOD = 'education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.degree_audit_gui'

from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.degree_audit_gui import (
    DegreeAuditGUI, launch_degree_audit_gui
)
from education_system.systems.university.infrastructure.auth import UserAuth

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
def gui_patches():
    """Patch tkinter modules in the GUI to prevent real widget creation"""
    with patch(f'{_GUI_MOD}.tk') as mock_tk, \
         patch(f'{_GUI_MOD}.ttk'), \
         patch(f'{_GUI_MOD}.messagebox') as mock_msgbox, \
         patch(f'{_GUI_MOD}.scrolledtext'):
        yield mock_tk, mock_msgbox


@pytest.fixture
def make_gui(gui_patches, mock_auth):
    """Factory fixture to create a DegreeAuditGUI with mocked DB"""
    def _make(cursor_fetchone=None, cursor_fetchall=None):
        conn = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = cursor_fetchone
        cursor.fetchall.return_value = cursor_fetchall or []
        conn.cursor.return_value = cursor
        # The GUI queries via both conn.cursor() and conn.execute(...);
        # route conn.execute() through the same cursor so .fetchall() /
        # .fetchone() return the configured (iterable) results rather than
        # an unconfigured Mock.
        conn.execute.return_value = cursor
        conn.__enter__ = Mock(return_value=conn)
        conn.__exit__ = Mock(return_value=False)

        with patch(f'{_GUI_MOD}.get_connection', return_value=conn), \
             patch(f'{_GUI_MOD}.initialize_degree_audit_database'):
            root = MagicMock()
            gui = DegreeAuditGUI(root, mock_auth)

        return gui, conn, cursor

    return _make


class TestDegreeAuditGUI:
    """Test suite for DegreeAuditGUI"""

    def test_initialization(self, make_gui, mock_auth):
        """Test GUI initialization"""
        gui, conn, cursor = make_gui()

        assert gui.auth == mock_auth
        assert gui.root is not None
        assert hasattr(gui, 'notebook')

    def test_load_student_progress(self, make_gui):
        """Test loading student degree progress"""
        gui, conn, cursor = make_gui()

        # Configure entry mock to return a student ID
        gui.progress_student_entry = MagicMock()
        gui.progress_student_entry.get.return_value = 'student001'

        # Reconfigure get_connection for the method call
        inner_conn = Mock()
        inner_cursor = Mock()
        inner_cursor.fetchone.side_effect = [
            ('student001', 'John', 'Doe', 'CS', '2021-09-01', '2021-09-01'),  # student
            (1, 'Computer Science', 'CS'),  # course
        ]
        inner_cursor.fetchall.return_value = [
            ('CS101', 'Intro to CS', 'completed', 'A', 15),
        ]
        inner_conn.cursor.return_value = inner_cursor
        inner_conn.__enter__ = Mock(return_value=inner_conn)
        inner_conn.__exit__ = Mock(return_value=False)

        with patch(f'{_GUI_MOD}.get_connection', return_value=inner_conn):
            gui.load_student_progress()

        inner_cursor.execute.assert_called()

    def test_update_progress(self, make_gui):
        """Test updating student progress (calls load_student_progress)"""
        gui, conn, cursor = make_gui()

        gui.progress_student_entry = MagicMock()
        gui.progress_student_entry.get.return_value = 'student001'

        with patch.object(gui, 'load_student_progress') as mock_load, \
             patch(f'{_GUI_MOD}.log_activity'), \
             patch(f'{_GUI_MOD}.messagebox'):
            gui.update_progress()

        mock_load.assert_called_once()

    def test_check_prerequisites(self, make_gui):
        """Test checking course prerequisites"""
        gui, conn, cursor = make_gui()

        gui.prereq_student_entry = MagicMock()
        gui.prereq_student_entry.get.return_value = 'student001'
        gui.prereq_module_entry = MagicMock()
        gui.prereq_module_entry.get.return_value = 'CS201'
        gui.prereq_results_text = MagicMock()

        inner_conn = Mock()
        inner_cursor = Mock()
        inner_cursor.fetchone.side_effect = [
            ('student001',),  # student exists
            ('CS201', 'completed', 'B', 'Algorithms', 'CS101'),  # module enrollment
        ]
        inner_cursor.fetchall.return_value = []
        inner_conn.cursor.return_value = inner_cursor
        inner_conn.__enter__ = Mock(return_value=inner_conn)
        inner_conn.__exit__ = Mock(return_value=False)

        with patch(f'{_GUI_MOD}.get_connection', return_value=inner_conn):
            gui.check_prerequisites()

        inner_cursor.execute.assert_called()

    def test_create_whatif_scenario(self, make_gui):
        """Test creating what-if scenario"""
        gui, conn, cursor = make_gui()

        gui.whatif_student_entry = MagicMock()
        gui.whatif_student_entry.get.return_value = 'student001'
        gui.whatif_name_entry = MagicMock()
        gui.whatif_name_entry.get.return_value = 'Switch to Math Major'
        gui.whatif_program_combo = MagicMock()
        gui.whatif_program_combo.get.return_value = '2: MATH - Mathematics BSc'
        gui.whatif_notes_text = MagicMock()
        gui.whatif_notes_text.get.return_value = 'Exploring options'
        gui.whatif_results_text = MagicMock()

        inner_conn = Mock()
        inner_cursor = Mock()
        inner_cursor.fetchone.side_effect = [
            ('CS',),  # student's current course
            (2,),     # target course id
        ]
        inner_cursor.fetchall.return_value = [
            ('MATH101', 'Calculus I', 15, None),
        ]
        inner_cursor.lastrowid = 1
        inner_conn.cursor.return_value = inner_cursor
        inner_conn.__enter__ = Mock(return_value=inner_conn)
        inner_conn.__exit__ = Mock(return_value=False)

        with patch(f'{_GUI_MOD}.get_connection', return_value=inner_conn), \
             patch(f'{_GUI_MOD}.log_activity'), \
             patch(f'{_GUI_MOD}.messagebox'):
            gui.create_whatif_scenario()

        inner_cursor.execute.assert_called()

    def test_run_graduation_audit(self, make_gui):
        """Test running graduation audit"""
        gui, conn, cursor = make_gui()

        gui.grad_student_entry = MagicMock()
        gui.grad_student_entry.get.return_value = 'student001'
        gui.grad_program_combo = MagicMock()
        gui.grad_program_combo.get.return_value = '1: CS - Computer Science BSc'
        gui.grad_results_text = MagicMock()

        inner_conn = Mock()
        inner_cursor = Mock()
        inner_cursor.fetchone.side_effect = [
            ('student001', 'John', 'Doe', 'CS'),  # student info
            (10, 120, 3.5),  # module_count, total_credits, gpa
        ]
        inner_cursor.fetchall.return_value = []
        inner_conn.cursor.return_value = inner_cursor
        inner_conn.__enter__ = Mock(return_value=inner_conn)
        inner_conn.__exit__ = Mock(return_value=False)

        with patch(f'{_GUI_MOD}.get_connection', return_value=inner_conn), \
             patch(f'{_GUI_MOD}.log_activity'), \
             patch(f'{_GUI_MOD}.messagebox'):
            gui.run_graduation_audit()

        inner_cursor.execute.assert_called()

    def test_approve_graduation(self, make_gui):
        """Approving now confers the award in absentia through the graduation
        rules (never a direct students.status update)."""
        from education_system.systems.university.application.graduation import conferral as gc
        part = ('education_system.systems.university.domains.curriculum.interfaces.'
                'gui.course_management_gui.degree_audit_gui_parts.degreeauditgui_run_graduation_audit')
        common = ('education_system.systems.university.domains.research.interfaces.gui.'
                  'research.research_portal.common')
        gui, conn, cursor = make_gui()

        gui.grad_student_entry = MagicMock()
        gui.grad_student_entry.get.return_value = 'student001'
        gui.grad_date_entry = MagicMock()
        gui.grad_date_entry.get.return_value = '2025-05-15'
        office = Mock(is_office=True, username='registry')
        conferred = {'conferral_id': 1, 'student_id': 'student001',
                     'certificate_number': 'CERT-1', 'verification_code': 'code',
                     'history_id': None, 'emails': []}

        with patch.object(DegreeAuditGUI, '_grad_officer', return_value=office), \
             patch(f'{common}.call', return_value=conferred) as mock_call, \
             patch.object(gc, 'after_commit') as mock_after, \
             patch(f'{part}.log_activity'), \
             patch(f'{part}.messagebox') as mock_msgbox:
            mock_msgbox.askyesnocancel.return_value = True
            gui.approve_graduation()

        rule = mock_call.call_args.args[1]
        assert rule is gc.confer
        assert mock_call.call_args.kwargs['mode'] == 'in_absentia'
        assert mock_call.call_args.kwargs['conferral_date'] == '2025-05-15'
        mock_after.assert_called_once_with(conferred)
        assert not any('UPDATE students' in str(c) for c in cursor.execute.call_args_list)

    def test_approve_graduation_refused_for_non_office(self, make_gui):
        part = ('education_system.systems.university.domains.curriculum.interfaces.'
                'gui.course_management_gui.degree_audit_gui_parts.degreeauditgui_run_graduation_audit')
        gui, conn, cursor = make_gui()
        gui.grad_student_entry = MagicMock()
        gui.grad_student_entry.get.return_value = 'student001'
        with patch.object(DegreeAuditGUI, '_grad_officer', return_value=Mock(is_office=False)), \
             patch(f'{part}.messagebox') as mock_msgbox:
            gui.approve_graduation()
        mock_msgbox.showerror.assert_called_once()
        mock_msgbox.askyesnocancel.assert_not_called()


class TestLaunchDegreeAuditGUI:
    """Test the launch function"""

    def test_launch_with_auth(self, gui_patches):
        """Test launching GUI with authenticated user"""
        with patch(f'{_GUI_MOD}.DegreeAuditGUI') as mock_gui_class:
            root = MagicMock()
            auth = Mock(spec=UserAuth)
            auth.current_user = {'username': 'student001'}

            launch_degree_audit_gui(root, auth)

            mock_gui_class.assert_called_once_with(root, auth)

    def test_launch_without_auth(self, gui_patches):
        """Test launching GUI without authentication"""
        _, mock_msgbox = gui_patches
        root = MagicMock()

        launch_degree_audit_gui(root, None)

        mock_msgbox.showerror.assert_called_once()

    def test_launch_with_error(self, gui_patches):
        """Test launching GUI with error"""
        _, mock_msgbox = gui_patches
        root = MagicMock()
        auth = Mock()
        auth.current_user = {'username': 'student001'}

        with patch(f'{_GUI_MOD}.DegreeAuditGUI', side_effect=Exception("Test error")):
            launch_degree_audit_gui(root, auth)

        mock_msgbox.showerror.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
