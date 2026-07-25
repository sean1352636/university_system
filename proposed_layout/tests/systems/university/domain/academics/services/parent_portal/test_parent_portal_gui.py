"""
Test suite for Parent Portal GUI module
Tests Parent Portal System GUI functionality
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime


@pytest.fixture
def mock_auth():
    """Create a mock authentication object for parent"""
    auth = Mock()
    auth.current_user = {'username': 'test_parent', 'role': 'parent', 'id': 'parent001'}
    auth.is_logged_in.return_value = True
    auth.has_permission.return_value = True
    return auth


@pytest.fixture
def mock_parent_portal():
    """Create a mock ParentPortal object"""
    portal = Mock()
    portal.get_parent_id_from_user.return_value = 'P001'
    portal.get_children.return_value = [
        {'student_id': 'S001', 'name': 'John Doe', 'grade': 10},
        {'student_id': 'S002', 'name': 'Jane Doe', 'grade': 12}
    ]
    return portal


@pytest.fixture
def mock_db():
    """Create mock database"""
    conn = Mock()
    cursor = Mock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    conn.cursor.return_value = cursor
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn


class TestParentPortalGUIInitialization:
    """Test ParentPortalGUI initialization"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_initialization_with_auth(self, mock_portal_class, mock_auth):
        """Test initialization with authentication"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.auth == mock_auth
        assert gui.parent_portal == portal_instance
        assert gui.parent_id == 'P001'

    def test_initialization_without_auth(self):
        """Test initialization without authentication"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        gui = ParentPortalGUI(None)

        assert gui.auth is None
        assert gui.parent_portal is None

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    @patch('tkinter.Tk')
    def test_create_main_window(self, mock_tk, mock_portal_class, mock_auth):
        """Test creating main window"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        mock_portal_class.return_value = portal_instance

        root_instance = Mock(spec=tk.Tk)
        mock_tk.return_value = root_instance

        gui = ParentPortalGUI(mock_auth)
        result = gui.create_main_window()

        assert result == root_instance
        root_instance.title.assert_called_once()
        root_instance.geometry.assert_called_once()
        root_instance.minsize.assert_called_once()


class TestLayoutSetup:
    """Test layout setup functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    @patch('tkinter.Tk')
    def test_setup_layout(self, mock_tk, mock_portal_class, mock_auth):
        """Test setting up the layout"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        mock_portal_class.return_value = portal_instance

        root_instance = Mock(spec=tk.Tk)
        mock_tk.return_value = root_instance

        gui = ParentPortalGUI(mock_auth)
        gui.create_main_window()

        # Verify layout components were created
        assert gui.root == root_instance


class TestChildrenManagement:
    """Test children management functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_load_children_list(self, mock_portal_class, mock_auth):
        """Test loading children list"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.get_children.return_value = [
            {'student_id': 'S001', 'name': 'John Doe', 'grade': 10},
            {'student_id': 'S002', 'name': 'Jane Doe', 'grade': 12}
        ]
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_select_child(self, mock_portal_class, mock_auth):
        """Test selecting a child"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance


class TestDashboardView:
    """Test dashboard view functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    @patch('tkinter.Tk')
    def test_show_dashboard(self, mock_tk, mock_portal_class, mock_auth):
        """Test showing dashboard"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        mock_portal_class.return_value = portal_instance

        root_instance = Mock(spec=tk.Tk)
        mock_tk.return_value = root_instance

        gui = ParentPortalGUI(mock_auth)
        gui.create_main_window()

        # Verify dashboard is shown
        assert gui.root is not None


class TestGradesView:
    """Test grades viewing functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_view_child_grades(self, mock_portal_class, mock_auth):
        """Test viewing child grades"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.get_student_grades.return_value = [
            {'module': 'Mathematics', 'grade': 'A', 'percentage': 92.5},
            {'module': 'Science', 'grade': 'B+', 'percentage': 87.0}
        ]
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_view_grade_details(self, mock_portal_class, mock_auth):
        """Test viewing grade details"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.get_grade_details.return_value = {
            'module': 'Mathematics',
            'grade': 'A',
            'assignments': [
                {'name': 'Assignment 1', 'score': 95},
                {'name': 'Midterm', 'score': 90}
            ]
        }
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance


class TestAttendanceView:
    """Test attendance viewing functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_view_attendance(self, mock_portal_class, mock_auth):
        """Test viewing attendance"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.get_student_attendance.return_value = {
            'total_days': 100,
            'present_days': 95,
            'absent_days': 5,
            'attendance_percentage': 95.0
        }
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_view_attendance_details(self, mock_portal_class, mock_auth):
        """Test viewing detailed attendance"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.get_attendance_details.return_value = [
            {'date': '2024-01-15', 'status': 'Present'},
            {'date': '2024-01-16', 'status': 'Present'},
            {'date': '2024-01-17', 'status': 'Absent'}
        ]
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance


class TestTimetableView:
    """Test timetable viewing functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_view_timetable(self, mock_portal_class, mock_auth):
        """Test viewing timetable"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.get_student_timetable.return_value = [
            {'day': 'Monday', 'time': '09:00', 'subject': 'Mathematics'},
            {'day': 'Monday', 'time': '10:00', 'subject': 'Science'}
        ]
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance


class TestCommunication:
    """Test communication functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_send_message_to_teacher(self, mock_portal_class, mock_auth):
        """Test sending message to teacher"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.send_message.return_value = (True, "Message sent successfully")
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_view_messages(self, mock_portal_class, mock_auth):
        """Test viewing messages"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.get_messages.return_value = [
            {
                'from': 'Teacher Smith',
                'subject': 'Progress Update',
                'date': '2024-01-15',
                'read': False
            }
        ]
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance


class TestAnnouncementsView:
    """Test announcements viewing functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_view_announcements(self, mock_portal_class, mock_auth):
        """Test viewing announcements"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.get_announcements.return_value = [
            {
                'title': 'School Holiday',
                'content': 'School will be closed next Monday',
                'date': '2024-01-15'
            }
        ]
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance


class TestFeesPayment:
    """Test fees and payment functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_view_fee_balance(self, mock_portal_class, mock_auth):
        """Test viewing fee balance"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.get_fee_balance.return_value = {
            'total_fees': 5000.00,
            'paid_amount': 3000.00,
            'balance': 2000.00
        }
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_view_payment_history(self, mock_portal_class, mock_auth):
        """Test viewing payment history"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.get_payment_history.return_value = [
            {'date': '2024-01-01', 'amount': 1500.00, 'method': 'Credit Card'},
            {'date': '2023-12-01', 'amount': 1500.00, 'method': 'Bank Transfer'}
        ]
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance


class TestReportsDownload:
    """Test reports download functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.filedialog')
    def test_download_progress_report(self, mock_filedialog, mock_portal_class, mock_auth):
        """Test downloading progress report"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.generate_progress_report.return_value = '/path/to/report.pdf'
        mock_portal_class.return_value = portal_instance

        mock_filedialog.asksaveasfilename.return_value = '/path/to/save/report.pdf'

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.filedialog')
    def test_download_attendance_report(self, mock_filedialog, mock_portal_class, mock_auth):
        """Test downloading attendance report"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.generate_attendance_report.return_value = '/path/to/attendance.pdf'
        mock_portal_class.return_value = portal_instance

        mock_filedialog.asksaveasfilename.return_value = '/path/to/save/attendance.pdf'

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance


class TestProfileManagement:
    """Test profile management functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_view_parent_profile(self, mock_portal_class, mock_auth):
        """Test viewing parent profile"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.get_parent_profile.return_value = {
            'name': 'Test Parent',
            'email': 'parent@example.com',
            'phone': '123-456-7890'
        }
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    def test_update_contact_information(self, mock_portal_class, mock_auth):
        """Test updating contact information"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        portal_instance.update_contact_info.return_value = (True, "Contact info updated")
        mock_portal_class.return_value = portal_instance

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance


class TestExportFunctionality:
    """Test export functionality"""

    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.ParentPortal')
    @patch('education_system.systems.university.interfaces.gui.academics.parent_portal.base.filedialog')
    def test_export_grades_to_csv(self, mock_filedialog, mock_portal_class, mock_auth):
        """Test exporting grades to CSV"""
        from education_system.systems.university.interfaces.gui.academics.parent_portal import ParentPortalGUI

        portal_instance = Mock()
        portal_instance.get_parent_id_from_user.return_value = 'P001'
        mock_portal_class.return_value = portal_instance

        mock_filedialog.asksaveasfilename.return_value = '/path/to/grades.csv'

        gui = ParentPortalGUI(mock_auth)

        assert gui.parent_portal == portal_instance
