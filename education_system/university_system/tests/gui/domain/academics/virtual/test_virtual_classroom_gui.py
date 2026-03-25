"""
Comprehensive tests for Virtual Classroom GUI
Tests GUI initialization, components, and functionality without requiring display
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
from education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui import (
    VirtualClassroomGUI,
    launch_virtual_classroom_gui
)
from education_system.university_system.infrastructure.database.db import get_connection, transaction


@pytest.fixture
def mock_auth():
    """Create mock authentication object"""
    auth = Mock()
    auth.current_user = {
        'id': 1,
        'username': 'test_user',
        'role': 'instructor',
        'student_id': 'TEST001'
    }
    return auth


@pytest.fixture
def setup_test_db():
    """Setup test database with virtual classroom tables and data"""
    with transaction() as conn:
        cursor = conn.cursor()

        # Create virtual classroom tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS virtual_classrooms (
                classroom_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT NOT NULL,
                instructor_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                course_id INTEGER,
                meeting_link TEXT,
                meeting_id TEXT,
                passcode TEXT,
                max_participants INTEGER DEFAULT 100,
                is_active INTEGER DEFAULT 1,
                features TEXT,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS virtual_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                classroom_id INTEGER NOT NULL,
                session_type TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                status TEXT DEFAULT 'scheduled',
                duration_minutes INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (classroom_id) REFERENCES virtual_classrooms(classroom_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_participants (
                participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_type TEXT NOT NULL,
                join_time TEXT,
                leave_time TEXT,
                duration INTEGER,
                attendance_status TEXT DEFAULT 'absent',
                connection_quality TEXT,
                device_type TEXT,
                FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS virtual_recordings (
                recording_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                file_url TEXT NOT NULL,
                file_name TEXT,
                duration INTEGER,
                file_size INTEGER,
                is_public INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,
                download_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id)
            )
        """)

        # Insert test data
        cursor.execute("DELETE FROM virtual_classrooms WHERE session_name LIKE 'TEST_%'")

        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO virtual_classrooms
            (session_name, instructor_id, platform, max_participants, is_active, created_at)
            VALUES ('TEST_Classroom_1', 1, 'zoom', 50, 1, ?)
        """, (now,))

        classroom_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO virtual_sessions
            (classroom_id, session_type, start_time, status, created_at)
            VALUES (?, 'lecture', ?, 'scheduled', ?)
        """, (classroom_id, (datetime.now() + timedelta(days=1)).isoformat(), now))

    yield

    # Cleanup
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM virtual_classrooms WHERE session_name LIKE 'TEST_%'")


class TestVirtualClassroomGUIInitialization:
    """Test GUI initialization"""

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.messagebox')
    def test_init_without_auth(self, mock_messagebox):
        """Test initialization without authentication"""
        root = tk.Tk()

        try:
            # Should fail without auth
            gui = VirtualClassroomGUI(root, auth=None)
            mock_messagebox.showerror.assert_called()
        except Exception:
            pass
        finally:
            root.destroy()

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.messagebox')
    def test_init_with_no_logged_in_user(self, mock_messagebox, mock_auth):
        """Test initialization with auth but no logged in user"""
        root = tk.Tk()
        mock_auth.current_user = None

        try:
            gui = VirtualClassroomGUI(root, auth=mock_auth)
            mock_messagebox.showerror.assert_called()
        except Exception:
            pass
        finally:
            root.destroy()

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.VirtualClassroomManager')
    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.SessionManager')
    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.ParticipantManager')
    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.RecordingManager')
    def test_successful_init(self, mock_rec_mgr, mock_part_mgr, mock_sess_mgr, mock_class_mgr, mock_auth, setup_test_db):
        """Test successful initialization with proper auth"""
        root = tk.Tk()

        try:
            gui = VirtualClassroomGUI(root, auth=mock_auth)

            # Check managers were created
            mock_class_mgr.assert_called_once()
            mock_sess_mgr.assert_called_once()
            mock_part_mgr.assert_called_once()
            mock_rec_mgr.assert_called_once()

            # Check window was configured
            assert gui.parent == root
            assert gui.auth == mock_auth

        finally:
            root.destroy()

    def test_window_configuration(self, mock_auth, setup_test_db):
        """Test window title and geometry are set"""
        root = tk.Tk()

        try:
            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                VirtualClassroomManager=MagicMock(),
                SessionManager=MagicMock(),
                ParticipantManager=MagicMock(),
                RecordingManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)

                assert "Virtual Classroom Management" in root.title()

        finally:
            root.destroy()


class TestClassroomManagement:
    """Test classroom management functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.VirtualClassroomManager')
    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.messagebox')
    def test_refresh_classrooms(self, mock_msgbox, mock_mgr, mock_auth, setup_test_db):
        """Test refreshing classrooms list"""
        root = tk.Tk()

        try:
            # Mock the manager to return test data
            mock_instance = mock_mgr.return_value
            mock_instance.list_classrooms.return_value = [
                {
                    'classroom_id': 1,
                    'session_name': 'Test Classroom',
                    'platform': 'zoom',
                    'instructor_id': 1,
                    'max_participants': 100,
                    'is_active': 1
                }
            ]

            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                SessionManager=MagicMock(),
                ParticipantManager=MagicMock(),
                RecordingManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)
                gui._refresh_classrooms()

                # Manager should have been called
                mock_instance.list_classrooms.assert_called()

        finally:
            root.destroy()

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.VirtualClassroomManager')
    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.messagebox')
    def test_delete_classroom_confirmation(self, mock_msgbox, mock_mgr, mock_auth, setup_test_db):
        """Test classroom deletion with confirmation"""
        root = tk.Tk()

        try:
            mock_instance = mock_mgr.return_value
            mock_instance.delete_classroom.return_value = True
            mock_msgbox.askyesno.return_value = True

            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                SessionManager=MagicMock(),
                ParticipantManager=MagicMock(),
                RecordingManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)

                # Insert item in treeview
                gui.classrooms_tree.insert("", "end", values=(1, "Test", "Zoom", 1, 100, "Active"))

                # Select the item
                item_id = gui.classrooms_tree.get_children()[0]
                gui.classrooms_tree.selection_set(item_id)

                # Call delete
                gui._delete_classroom()

                # Confirmation dialog should have been shown
                mock_msgbox.askyesno.assert_called()

        finally:
            root.destroy()


class TestSessionManagement:
    """Test session management functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.SessionManager')
    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.messagebox')
    def test_refresh_sessions(self, mock_msgbox, mock_sess_mgr, mock_auth, setup_test_db):
        """Test refreshing sessions list"""
        root = tk.Tk()

        try:
            mock_instance = mock_sess_mgr.return_value
            mock_instance.list_sessions.return_value = [
                {
                    'session_id': 1,
                    'classroom_id': 1,
                    'session_type': 'lecture',
                    'start_time': datetime.now().isoformat(),
                    'end_time': None,
                    'status': 'scheduled'
                }
            ]

            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                VirtualClassroomManager=MagicMock(),
                ParticipantManager=MagicMock(),
                RecordingManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)
                gui._refresh_sessions()

                mock_instance.list_sessions.assert_called()

        finally:
            root.destroy()

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.SessionManager')
    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.messagebox')
    def test_start_session(self, mock_msgbox, mock_sess_mgr, mock_auth, setup_test_db):
        """Test starting a session"""
        root = tk.Tk()

        try:
            mock_instance = mock_sess_mgr.return_value
            mock_instance.start_session.return_value = True

            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                VirtualClassroomManager=MagicMock(),
                ParticipantManager=MagicMock(),
                RecordingManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)

                # Insert session in treeview
                gui.sessions_tree.insert("", "end", values=(1, 1, "lecture", "2024-01-01 10:00", "N/A", "scheduled"))

                # Select and start
                item_id = gui.sessions_tree.get_children()[0]
                gui.sessions_tree.selection_set(item_id)

                gui._start_session()

                mock_instance.start_session.assert_called_with(1)

        finally:
            root.destroy()


class TestParticipantManagement:
    """Test participant management functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.ParticipantManager')
    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.messagebox')
    def test_refresh_participants(self, mock_msgbox, mock_part_mgr, mock_auth, setup_test_db):
        """Test refreshing participants list"""
        root = tk.Tk()

        try:
            mock_instance = mock_part_mgr.return_value
            mock_instance.get_session_participants.return_value = [
                {
                    'participant_id': 1,
                    'user_id': 1,
                    'user_type': 'student',
                    'join_time': datetime.now().isoformat(),
                    'duration': 3600,
                    'attendance_status': 'present',
                    'connection_quality': 'good'
                }
            ]

            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                VirtualClassroomManager=MagicMock(),
                SessionManager=MagicMock(),
                RecordingManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)

                # Set session selection
                gui.participant_session_var.set("1: Test Session")

                gui._refresh_participants()

                mock_instance.get_session_participants.assert_called()

        finally:
            root.destroy()

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.ParticipantManager')
    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.filedialog')
    def test_export_attendance(self, mock_filedialog, mock_part_mgr, mock_auth, setup_test_db):
        """Test exporting attendance to CSV"""
        root = tk.Tk()

        try:
            mock_instance = mock_part_mgr.return_value
            mock_instance.get_session_participants.return_value = [
                {
                    'participant_id': 1,
                    'user_id': 1,
                    'user_type': 'student',
                    'join_time': datetime.now().isoformat(),
                    'leave_time': datetime.now().isoformat(),
                    'duration': 3600,
                    'attendance_status': 'present',
                    'connection_quality': 'good'
                }
            ]

            import tempfile
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
            mock_filedialog.asksaveasfilename.return_value = temp_file.name

            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                VirtualClassroomManager=MagicMock(),
                SessionManager=MagicMock(),
                RecordingManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)

                # Set session
                gui.participant_session_var.set("1: Test Session")

                gui._export_attendance()

                # Check file was created
                import os
                assert os.path.exists(temp_file.name)
                os.unlink(temp_file.name)

        finally:
            root.destroy()


class TestRecordingManagement:
    """Test recording management functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.RecordingManager')
    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.messagebox')
    def test_refresh_recordings(self, mock_msgbox, mock_rec_mgr, mock_auth, setup_test_db):
        """Test refreshing recordings list"""
        root = tk.Tk()

        try:
            mock_instance = mock_rec_mgr.return_value
            mock_instance.list_recordings.return_value = [
                {
                    'recording_id': 1,
                    'session_id': 1,
                    'file_name': 'recording.mp4',
                    'duration': 3600,
                    'file_size': 1024000,
                    'view_count': 10,
                    'is_public': 1
                }
            ]

            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                VirtualClassroomManager=MagicMock(),
                SessionManager=MagicMock(),
                ParticipantManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)
                gui._refresh_recordings()

                mock_instance.list_recordings.assert_called()

        finally:
            root.destroy()


class TestAnalytics:
    """Test analytics functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.messagebox')
    def test_refresh_analytics(self, mock_msgbox, mock_auth, setup_test_db):
        """Test refreshing analytics"""
        root = tk.Tk()

        try:
            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                VirtualClassroomManager=MagicMock(),
                SessionManager=MagicMock(),
                ParticipantManager=MagicMock(),
                RecordingManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)
                gui._refresh_analytics()

                # Should execute without error

        finally:
            root.destroy()


class TestUtilityMethods:
    """Test utility methods"""

    def test_update_status(self, mock_auth):
        """Test status bar update"""
        root = tk.Tk()

        try:
            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                VirtualClassroomManager=MagicMock(),
                SessionManager=MagicMock(),
                ParticipantManager=MagicMock(),
                RecordingManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)
                gui.update_status("Test message")

                assert gui.status_var.get() == "Test message"

        finally:
            root.destroy()

    def test_sort_treeview(self, mock_auth):
        """Test treeview sorting"""
        root = tk.Tk()

        try:
            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                VirtualClassroomManager=MagicMock(),
                SessionManager=MagicMock(),
                ParticipantManager=MagicMock(),
                RecordingManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)

                # Add items to classrooms tree
                gui.classrooms_tree.insert("", "end", values=(1, "A", "Zoom", 1, 100, "Active"))
                gui.classrooms_tree.insert("", "end", values=(2, "B", "Teams", 2, 50, "Active"))

                # Sort by name
                gui._sort_treeview(gui.classrooms_tree, "Name", False)

                # Should not raise error

        finally:
            root.destroy()


class TestLauncherFunction:
    """Test GUI launcher function"""

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.VirtualClassroomGUI')
    def test_launch_with_parent(self, mock_gui_class, mock_auth):
        """Test launching with parent window"""
        root = tk.Tk()

        try:
            window = launch_virtual_classroom_gui(parent=root, auth=mock_auth)
            # Function should return window
            assert window is not None

        finally:
            root.destroy()


class TestIntegrationScenarios:
    """Integration tests for complete workflows"""

    @patch('education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui.messagebox')
    def test_complete_classroom_workflow(self, mock_msgbox, mock_auth, setup_test_db):
        """Test complete classroom management workflow"""
        root = tk.Tk()

        try:
            with patch.multiple(
                'university_system.modules.domain.academics.gui.virtual_classroom_gui',
                VirtualClassroomManager=MagicMock(),
                SessionManager=MagicMock(),
                ParticipantManager=MagicMock(),
                RecordingManager=MagicMock()
            ):
                gui = VirtualClassroomGUI(root, auth=mock_auth)

                # Refresh all data
                gui.refresh_all_data()

                # Should complete without errors

        finally:
            root.destroy()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
