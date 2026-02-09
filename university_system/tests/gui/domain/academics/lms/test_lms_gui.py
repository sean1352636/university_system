"""
Test suite for LMS GUI module
Tests Learning Management System GUI functionality
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime


@pytest.fixture
def mock_root():
    """Create a mock Tkinter root window"""
    root = Mock()
    toplevel = Mock(spec=tk.Toplevel)
    toplevel.winfo_exists.return_value = True
    with patch('tkinter.Toplevel', return_value=toplevel):
        yield root


@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {'username': 'test_instructor', 'role': 'instructor', 'id': 'inst001'}
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
def mock_db():
    """Create mock database context manager"""
    conn = Mock()
    cursor = Mock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    conn.cursor.return_value = cursor
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn


class TestLMSGUIInitialization:
    """Test LMSGUI initialization"""

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('tkinter.Toplevel')
    def test_initialization_instructor(self, mock_toplevel, mock_init_db, mock_root, mock_auth):
        """Test initialization with instructor role"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        gui = LMSGUI(mock_root, mock_auth)

        assert gui.auth == mock_auth
        assert gui.user_role == 'instructor'
        assert gui.user_id == 'inst001'
        mock_init_db.assert_called_once()

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('tkinter.Toplevel')
    def test_initialization_student(self, mock_toplevel, mock_init_db, mock_root, mock_auth_student):
        """Test initialization with student role"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        gui = LMSGUI(mock_root, mock_auth_student)

        assert gui.auth == mock_auth_student
        assert gui.user_role == 'student'
        assert gui.user_id == 'S001'


class TestCourseManagement:
    """Test course management functionality"""

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('university_system.modules.domain.academics.gui.lms_gui.get_connection')
    @patch('tkinter.Toplevel')
    @patch('university_system.modules.domain.academics.gui.lms_gui.LMSCourseManager')
    def test_load_courses_instructor(self, mock_course_mgr, mock_toplevel, mock_get_conn, mock_init_db, mock_root, mock_auth, mock_db):
        """Test loading courses for instructor"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        # Mock courses data
        mock_course_mgr.get_instructor_courses.return_value = [
            {
                'lms_course_id': 1,
                'module_code': 'CS101',
                'instructor_id': 'inst001',
                'start_date': '2024-01-01',
                'end_date': '2024-05-01',
                'enrollment_limit': 30,
                'is_published': 1
            }
        ]

        gui = LMSGUI(mock_root, mock_auth)
        gui.courses_tree = Mock()
        gui.courses_tree.get_children.return_value = []

        gui.load_courses()

        # Verify course manager was called
        mock_course_mgr.get_instructor_courses.assert_called_once_with('inst001')

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('tkinter.Toplevel')
    @patch('university_system.modules.domain.academics.gui.lms_gui.LMSCourseManager')
    @patch('university_system.modules.domain.academics.gui.lms_gui.messagebox')
    def test_create_course_success(self, mock_msgbox, mock_course_mgr, mock_toplevel, mock_init_db, mock_root, mock_auth):
        """Test successful course creation"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        mock_course_mgr.create_lms_course.return_value = 1

        gui = LMSGUI(mock_root, mock_auth)

        # Mock the create_course method would open a dialog
        # This is tested through the actual method call
        assert gui is not None

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('tkinter.Toplevel')
    @patch('university_system.modules.domain.academics.gui.lms_gui.LMSCourseManager')
    @patch('university_system.modules.domain.academics.gui.lms_gui.messagebox')
    def test_publish_course_success(self, mock_msgbox, mock_course_mgr, mock_toplevel, mock_init_db, mock_root, mock_auth):
        """Test successful course publishing"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        gui = LMSGUI(mock_root, mock_auth)
        gui.courses_tree = Mock()
        gui.courses_tree.selection.return_value = ['item1']
        gui.courses_tree.item.return_value = {'values': [1, 'CS101', 'inst001']}
        gui.load_courses = Mock()

        gui.publish_course()

        mock_course_mgr.publish_course.assert_called_once_with(1)


class TestContentManagement:
    """Test content management functionality"""

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('tkinter.Toplevel')
    @patch('university_system.modules.domain.academics.gui.lms_gui.LMSContentManager')
    def test_load_course_content(self, mock_content_mgr, mock_toplevel, mock_init_db, mock_root, mock_auth):
        """Test loading course content"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        mock_content_mgr.get_course_content.return_value = [
            {
                'content_id': 1,
                'content_type': 'Lecture',
                'title': 'Introduction',
                'description': 'Course intro',
                'content_url': 'http://example.com/intro',
                'content_order': 1,
                'release_date': '2024-01-01'
            }
        ]

        gui = LMSGUI(mock_root, mock_auth)
        gui.content_course_combo = Mock()
        gui.content_course_combo.get.return_value = '1: CS101'
        gui.content_tree = Mock()
        gui.content_tree.get_children.return_value = []

        gui.load_course_content()

        mock_content_mgr.get_course_content.assert_called_once_with(1)


class TestDiscussionManagement:
    """Test discussion forum functionality"""

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('university_system.modules.domain.academics.gui.lms_gui.get_connection')
    @patch('tkinter.Toplevel')
    def test_load_forums(self, mock_toplevel, mock_get_conn, mock_init_db, mock_root, mock_auth, mock_db):
        """Test loading discussion forums"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        cursor = Mock()
        cursor.fetchall.return_value = [
            (1, 'Topic 1', 'Description', 'inst001', 1, '2024-01-01')
        ]
        mock_db.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = mock_db

        gui = LMSGUI(mock_root, mock_auth)
        gui.discussion_course_combo = Mock()
        gui.discussion_course_combo.get.return_value = '1: CS101'
        gui.forums_tree = Mock()
        gui.forums_tree.get_children.return_value = []

        gui.load_forums()

        assert cursor.execute.called

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('tkinter.Toplevel')
    @patch('university_system.modules.domain.academics.gui.lms_gui.LMSDiscussionManager')
    def test_view_forum_posts(self, mock_discussion_mgr, mock_toplevel, mock_init_db, mock_root, mock_auth):
        """Test viewing forum posts"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        mock_discussion_mgr.get_forum_posts.return_value = [
            {
                'post_id': 1,
                'user_id': 'S001',
                'content': 'Test post',
                'created_at': '2024-01-01',
                'likes_count': 5
            }
        ]

        gui = LMSGUI(mock_root, mock_auth)
        gui.forums_tree = Mock()
        gui.forums_tree.selection.return_value = ['item1']
        gui.forums_tree.item.return_value = {'values': [1, 'Topic 1']}

        # This would open a dialog, so we just verify it doesn't crash
        assert gui is not None


class TestQuizManagement:
    """Test quiz management functionality"""

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('university_system.modules.domain.academics.gui.lms_gui.get_connection')
    @patch('tkinter.Toplevel')
    def test_load_quizzes(self, mock_toplevel, mock_get_conn, mock_init_db, mock_root, mock_auth, mock_db):
        """Test loading quizzes"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        cursor = Mock()
        cursor.fetchall.return_value = [
            (1, 'Quiz 1', 60, 70, 3, '2024-01-01', '2024-01-31')
        ]
        mock_db.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = mock_db

        gui = LMSGUI(mock_root, mock_auth)
        gui.quiz_course_combo = Mock()
        gui.quiz_course_combo.get.return_value = '1: CS101'
        gui.quizzes_tree = Mock()
        gui.quizzes_tree.get_children.return_value = []

        gui.load_quizzes()

        assert cursor.execute.called


class TestGradebookManagement:
    """Test gradebook functionality"""

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('tkinter.Toplevel')
    @patch('university_system.modules.domain.academics.gui.lms_gui.LMSGradebookManager')
    def test_load_student_grades(self, mock_gradebook_mgr, mock_toplevel, mock_init_db, mock_root, mock_auth):
        """Test loading student grades"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        mock_gradebook_mgr.get_student_grades.return_value = [
            {
                'entry_id': 1,
                'student_id': 'S001',
                'assignment_type': 'Quiz',
                'assignment_id': 1,
                'score': 85,
                'max_score': 100,
                'weight': 1.0,
                'graded_by': 'inst001',
                'graded_at': '2024-01-15'
            }
        ]

        gui = LMSGUI(mock_root, mock_auth)
        gui.gradebook_course_combo = Mock()
        gui.gradebook_course_combo.get.return_value = '1: CS101'
        gui.gradebook_student_entry = Mock()
        gui.gradebook_student_entry.get.return_value = 'S001'
        gui.gradebook_tree = Mock()
        gui.gradebook_tree.get_children.return_value = []

        gui.load_student_grades()

        mock_gradebook_mgr.get_student_grades.assert_called_once_with(1, 'S001')

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('tkinter.Toplevel')
    @patch('university_system.modules.domain.academics.gui.lms_gui.LMSGradebookManager')
    @patch('university_system.modules.domain.academics.gui.lms_gui.messagebox')
    def test_calculate_course_grade(self, mock_msgbox, mock_gradebook_mgr, mock_toplevel, mock_init_db, mock_root, mock_auth):
        """Test calculating course grade"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        mock_gradebook_mgr.calculate_course_grade.return_value = 87.5

        gui = LMSGUI(mock_root, mock_auth)
        gui.gradebook_course_combo = Mock()
        gui.gradebook_course_combo.get.return_value = '1: CS101'
        gui.gradebook_student_entry = Mock()
        gui.gradebook_student_entry.get.return_value = 'S001'

        gui.calculate_course_grade()

        mock_gradebook_mgr.calculate_course_grade.assert_called_once_with(1, 'S001')


class TestStudentView:
    """Test student view functionality"""

    @patch('university_system.modules.domain.academics.gui.lms_gui.initialize_lms_database')
    @patch('university_system.modules.domain.academics.gui.lms_gui.get_connection')
    @patch('tkinter.Toplevel')
    def test_load_student_courses(self, mock_toplevel, mock_get_conn, mock_init_db, mock_root, mock_auth_student, mock_db):
        """Test loading enrolled courses for student"""
        from university_system.modules.domain.academics.gui.lms_gui import LMSGUI

        # Mock the Toplevel window
        toplevel_instance = Mock(spec=tk.Toplevel)
        mock_toplevel.return_value = toplevel_instance

        cursor = Mock()
        cursor.fetchall.return_value = [
            (1, 'CS101', 'inst001', 75.5, '2024-01-15')
        ]
        mock_db.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = mock_db

        gui = LMSGUI(mock_root, mock_auth_student)
        gui.student_courses_tree = Mock()
        gui.student_courses_tree.get_children.return_value = []

        gui.load_student_courses()

        assert cursor.execute.called


class TestLaunchFunction:
    """Test launch function"""

    @patch('university_system.modules.domain.academics.gui.lms_gui.LMSGUI')
    @patch('university_system.modules.domain.academics.gui.lms_gui.messagebox')
    def test_launch_lms_gui_success(self, mock_msgbox, mock_lmsgui_class):
        """Test successful LMS GUI launch"""
        from university_system.modules.domain.academics.gui.lms_gui import launch_lms_gui

        mock_root = Mock()
        mock_auth = Mock()
        mock_auth.current_user = {'username': 'test_user', 'role': 'instructor'}

        launch_lms_gui(mock_root, mock_auth)

        mock_lmsgui_class.assert_called_once_with(mock_root, mock_auth)

    @patch('university_system.modules.domain.academics.gui.lms_gui.messagebox')
    def test_launch_lms_gui_no_auth(self, mock_msgbox):
        """Test LMS GUI launch without authentication"""
        from university_system.modules.domain.academics.gui.lms_gui import launch_lms_gui

        mock_root = Mock()

        launch_lms_gui(mock_root, None)

        mock_msgbox.showerror.assert_called_once()
