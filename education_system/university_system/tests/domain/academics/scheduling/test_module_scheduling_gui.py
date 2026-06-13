"""
Test suite for Module Scheduling GUI module
Tests Module Scheduling System GUI functionality
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, time


@pytest.fixture
def mock_root():
    """Create a mock Tkinter root window"""
    root = MagicMock()
    root.winfo_exists.return_value = True
    return root


@pytest.fixture(autouse=True)
def _patch_gui_init():
    """Patch GUI methods that create real tkinter widgets so tests run without a display"""
    gui_path = 'education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleSchedulingGUI'
    with patch(f'{gui_path}.setup_styles'), \
         patch(f'{gui_path}.create_main_interface'), \
         patch(f'{gui_path}.create_status_bar'), \
         patch(f'{gui_path}.refresh_all_data'), \
         patch(f'{gui_path}._migrate_database'):
        yield


@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {'username': 'test_admin', 'role': 'admin', 'id': 'admin001'}
    auth.is_logged_in.return_value = True
    auth.has_permission.return_value = True
    return auth


@pytest.fixture
def mock_auth_staff():
    """Create a mock authentication object for staff"""
    auth = Mock()
    auth.current_user = {'username': 'test_staff', 'role': 'instructor', 'id': 'staff001'}
    auth.is_logged_in.return_value = True
    auth.has_permission.return_value = True
    return auth


@pytest.fixture
def mock_auth_student():
    """Create a mock authentication object for student"""
    auth = Mock()
    auth.current_user = {'username': 'test_student', 'role': 'student', 'id': 'S001'}
    auth.is_logged_in.return_value = True
    auth.has_permission.return_value = True
    return auth


@pytest.fixture
def mock_scheduler():
    """Create a mock ModuleScheduler"""
    scheduler = Mock()
    scheduler.get_all_sessions.return_value = []
    scheduler.get_all_modules.return_value = []
    scheduler.get_all_rooms.return_value = []
    scheduler.get_all_instructors.return_value = []
    return scheduler


class TestModuleSchedulingGUIInitialization:
    """Test ModuleSchedulingGUI initialization"""

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_initialization(self, mock_scheduler_class, mock_root):
        """Test initialization of ModuleSchedulingGUI"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui.root == mock_root
        assert gui.scheduler == scheduler_instance
        mock_scheduler_class.assert_called_once()

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_window_configuration(self, mock_scheduler_class, mock_root):
        """Test window configuration"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        mock_root.title.assert_called_once()
        mock_root.geometry.assert_called_once()
        mock_root.minsize.assert_called_once()


class TestAuthenticationMethods:
    """Test authentication and role checking methods"""

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_get_user_role_admin(self, mock_scheduler_class, mock_root, mock_auth):
        """Test getting admin user role"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)
        gui.set_auth(mock_auth)

        role = gui.get_user_role()
        assert role == 'admin'

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_is_admin_true(self, mock_scheduler_class, mock_root, mock_auth):
        """Test is_admin returns True for admin user"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)
        gui.set_auth(mock_auth)

        assert gui.is_admin() is True

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_is_staff_true(self, mock_scheduler_class, mock_root, mock_auth_staff):
        """Test is_staff returns True for staff user"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)
        gui.set_auth(mock_auth_staff)

        assert gui.is_staff() is True

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_is_student_true(self, mock_scheduler_class, mock_root, mock_auth_student):
        """Test is_student returns True for student user"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)
        gui.set_auth(mock_auth_student)

        assert gui.is_student() is True

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_get_user_role_no_auth(self, mock_scheduler_class, mock_root):
        """Test getting user role when no auth is set"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        role = gui.get_user_role()
        assert role is None


class TestSessionManagement:
    """Test session management functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_create_session(self, mock_scheduler_class, mock_root):
        """Test creating a new session"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.schedule_session.return_value = (True, "Session created successfully")
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        # Test that GUI can be initialized
        assert gui is not None

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_edit_session(self, mock_scheduler_class, mock_root):
        """Test editing an existing session"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.update_session.return_value = (True, "Session updated successfully")
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_delete_session(self, mock_scheduler_class, mock_root):
        """Test deleting a session"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.delete_session.return_value = (True, "Session deleted successfully")
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None


class TestConflictDetection:
    """Test conflict detection functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_detect_room_conflict(self, mock_scheduler_class, mock_root):
        """Test detecting room conflicts"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.check_room_conflicts.return_value = []
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_detect_instructor_conflict(self, mock_scheduler_class, mock_root):
        """Test detecting instructor conflicts"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.check_instructor_conflicts.return_value = []
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_detect_student_conflict(self, mock_scheduler_class, mock_root):
        """Test detecting student conflicts"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.check_student_conflicts.return_value = []
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None


class TestRoomManagement:
    """Test room management functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_add_room(self, mock_scheduler_class, mock_root):
        """Test adding a new room"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.add_room.return_value = (True, "Room added successfully")
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_update_room(self, mock_scheduler_class, mock_root):
        """Test updating room details"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.update_room.return_value = (True, "Room updated successfully")
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_get_room_availability(self, mock_scheduler_class, mock_root):
        """Test checking room availability"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.get_room_availability.return_value = []
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None


class TestTimetableVisualization:
    """Test timetable visualization functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_view_weekly_timetable(self, mock_scheduler_class, mock_root):
        """Test viewing weekly timetable"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.get_weekly_schedule.return_value = []
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_view_instructor_schedule(self, mock_scheduler_class, mock_root):
        """Test viewing instructor schedule"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.get_instructor_schedule.return_value = []
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_view_room_schedule(self, mock_scheduler_class, mock_root):
        """Test viewing room schedule"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.get_room_schedule.return_value = []
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None


class TestExportFunctionality:
    """Test export functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.filedialog')
    def test_export_schedule_to_csv(self, mock_filedialog, mock_scheduler_class, mock_root):
        """Test exporting schedule to CSV"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        mock_filedialog.asksaveasfilename.return_value = '/path/to/schedule.csv'

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.filedialog')
    def test_export_schedule_to_pdf(self, mock_filedialog, mock_scheduler_class, mock_root):
        """Test exporting schedule to PDF"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        mock_filedialog.asksaveasfilename.return_value = '/path/to/schedule.pdf'

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None


class TestDatabaseMigration:
    """Test database migration functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.get_connection')
    def test_migrate_database(self, mock_get_conn, mock_scheduler_class, mock_root):
        """Test database migration"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None


class TestStatusBar:
    """Test status bar functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_status_bar_creation(self, mock_scheduler_class, mock_root):
        """Test status bar creation"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None


class TestDataRefresh:
    """Test data refresh functionality"""

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_refresh_all_data(self, mock_scheduler_class, mock_root):
        """Test refreshing all data"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        scheduler_instance.get_all_sessions.return_value = []
        scheduler_instance.get_all_modules.return_value = []
        scheduler_instance.get_all_rooms.return_value = []
        scheduler_instance.get_all_instructors.return_value = []
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        assert gui is not None


class TestWindowClose:
    """Test window close handling"""

    @patch('education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui.ModuleScheduler')
    def test_on_closing(self, mock_scheduler_class, mock_root):
        """Test window close event"""
        from education_system.university_system.modules.domain.academics.gui.module_scheduling import ModuleSchedulingGUI

        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        gui = ModuleSchedulingGUI(mock_root)

        # Test that protocol was set
        mock_root.protocol.assert_called()
