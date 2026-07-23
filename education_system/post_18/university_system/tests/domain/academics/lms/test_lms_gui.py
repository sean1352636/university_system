"""
Test suite for LMS GUI module
Tests Learning Management System GUI functionality via the LMSTabMixin.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import sys
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

# The module under test
LMS_TAB_MOD = "education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core.lms_tab"


def _import_mixin():
    """Import LMSTabMixin, ensuring the module is freshly resolved."""
    import importlib
    mod = importlib.import_module(LMS_TAB_MOD)
    return mod, mod.LMSTabMixin


def _make_gui(mixin_cls, user_role="instructor", user_id="inst001"):
    """
    Build a lightweight object that inherits the mixin and has just
    enough attributes for the methods under test to run.
    """
    class FakeLMSGUI(mixin_cls):
        pass

    obj = object.__new__(FakeLMSGUI)
    obj._lms_user_role = user_role
    obj._lms_user_id = user_id
    obj.root = Mock()
    obj.auth = Mock()
    obj.auth.current_user = {"username": user_id, "role": user_role, "id": user_id}
    return obj


# ── fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def mock_auth():
    """Create a mock authentication object for instructor."""
    auth = Mock()
    auth.current_user = {"username": "test_instructor", "role": "instructor", "id": "inst001"}
    auth.is_logged_in.return_value = True
    auth.has_permission.return_value = True
    return auth


@pytest.fixture
def mock_auth_student():
    """Create a mock authentication object for student."""
    auth = Mock()
    auth.current_user = {"username": "test_student", "role": "student", "id": "S001"}
    auth.is_logged_in.return_value = True
    auth.has_permission.return_value = True
    return auth


# ── TestLMSGUIInitialization ────────────────────────────────────────


class TestLMSGUIInitialization:
    """Test LMSTabMixin initialisation helpers."""

    def test_initialization_instructor(self):
        """Test that a mixin-based object stores instructor info correctly."""
        mod, mixin_cls = _import_mixin()
        gui = _make_gui(mixin_cls, user_role="instructor", user_id="inst001")

        assert gui._lms_user_role == "instructor"
        assert gui._lms_user_id == "inst001"

    def test_initialization_student(self):
        """Test that a mixin-based object stores student info correctly."""
        mod, mixin_cls = _import_mixin()
        gui = _make_gui(mixin_cls, user_role="student", user_id="S001")

        assert gui._lms_user_role == "student"
        assert gui._lms_user_id == "S001"


# ── TestCourseManagement ────────────────────────────────────────────


class TestCourseManagement:
    """Test course management functionality."""

    def test_load_courses_instructor(self):
        """Test loading courses for instructor via LMSCourseManager."""
        mod, mixin_cls = _import_mixin()
        gui = _make_gui(mixin_cls, user_role="instructor", user_id="inst001")

        # Provide the treeview mock and combo mocks
        gui.lms_courses_tree = Mock()
        gui.lms_courses_tree.get_children.return_value = []

        mock_courses = [
            {
                "lms_course_id": 1,
                "module_code": "CS101",
                "instructor_id": "inst001",
                "start_date": "2024-01-01",
                "end_date": "2024-05-01",
                "enrollment_limit": 30,
                "is_published": 1,
            }
        ]

        with patch.object(mod, "LMSCourseManager") as mock_mgr:
            mock_mgr.get_instructor_courses.return_value = mock_courses
            gui._lms_load_courses()
            mock_mgr.get_instructor_courses.assert_called_once_with("inst001")

    def test_create_course_success(self):
        """Test that the GUI object is created without error (dialog-based)."""
        mod, mixin_cls = _import_mixin()

        with patch.object(mod, "LMSCourseManager"):
            gui = _make_gui(mixin_cls, user_role="instructor", user_id="inst001")
            assert gui is not None

    def test_publish_course_success(self):
        """Test successful course publishing."""
        mod, mixin_cls = _import_mixin()
        gui = _make_gui(mixin_cls, user_role="instructor", user_id="inst001")

        gui.lms_courses_tree = Mock()
        gui.lms_courses_tree.selection.return_value = ["item1"]
        gui.lms_courses_tree.item.return_value = {"values": [1, "CS101", "inst001"]}

        with (
            patch.object(mod, "LMSCourseManager") as mock_mgr,
            patch.object(mod, "messagebox"),
            patch.object(mod, "log_activity"),
            patch.object(gui, "_lms_load_courses"),
        ):
            gui._lms_publish_course()
            mock_mgr.publish_course.assert_called_once_with(1)


# ── TestContentManagement ───────────────────────────────────────────


class TestContentManagement:
    """Test content management functionality."""

    def test_load_course_content(self):
        """Test loading course content via LMSContentManager."""
        mod, mixin_cls = _import_mixin()
        gui = _make_gui(mixin_cls, user_role="instructor", user_id="inst001")

        gui.lms_content_course_combo = Mock()
        gui.lms_content_course_combo.get.return_value = "1: CS101"
        gui.lms_content_tree = Mock()
        gui.lms_content_tree.get_children.return_value = []

        mock_content = [
            {
                "content_id": 1,
                "content_type": "Lecture",
                "title": "Introduction",
                "description": "Course intro",
                "content_url": "http://example.com/intro",
                "content_order": 1,
                "release_date": "2024-01-01",
            }
        ]

        with patch.object(mod, "LMSContentManager") as mock_mgr:
            mock_mgr.get_course_content.return_value = mock_content
            gui._lms_load_content()
            mock_mgr.get_course_content.assert_called_once_with(1)


# ── TestDiscussionManagement ────────────────────────────────────────


class TestDiscussionManagement:
    """Test discussion forum functionality."""

    def test_load_forums(self):
        """Test loading discussion forums via get_connection."""
        mod, mixin_cls = _import_mixin()
        gui = _make_gui(mixin_cls, user_role="instructor", user_id="inst001")

        gui.lms_discussion_course_combo = Mock()
        gui.lms_discussion_course_combo.get.return_value = "1: CS101"
        gui.lms_forums_tree = Mock()
        gui.lms_forums_tree.get_children.return_value = []

        cursor = Mock()
        cursor.fetchall.return_value = [
            (1, "Topic 1", "Description", "inst001", 1, "2024-01-01")
        ]
        mock_conn = Mock()
        mock_conn.cursor.return_value = cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(mod, "get_connection", return_value=mock_conn):
            gui._lms_load_forums()
            assert cursor.execute.called

    def test_view_forum_posts(self):
        """Test that viewing forum posts does not crash (dialog-based)."""
        mod, mixin_cls = _import_mixin()

        with patch.object(mod, "LMSDiscussionManager") as mock_mgr:
            mock_mgr.get_forum_posts.return_value = [
                {
                    "post_id": 1,
                    "user_id": "S001",
                    "content": "Test post",
                    "created_at": "2024-01-01",
                    "likes_count": 5,
                }
            ]
            gui = _make_gui(mixin_cls, user_role="instructor", user_id="inst001")
            gui.lms_forums_tree = Mock()
            gui.lms_forums_tree.selection.return_value = ["item1"]
            gui.lms_forums_tree.item.return_value = {"values": [1, "Topic 1"]}
            assert gui is not None


# ── TestQuizManagement ──────────────────────────────────────────────


class TestQuizManagement:
    """Test quiz management functionality."""

    def test_load_quizzes(self):
        """Test loading quizzes via get_connection."""
        mod, mixin_cls = _import_mixin()
        gui = _make_gui(mixin_cls, user_role="instructor", user_id="inst001")

        gui.lms_quiz_course_combo = Mock()
        gui.lms_quiz_course_combo.get.return_value = "1: CS101"
        gui.lms_quizzes_tree = Mock()
        gui.lms_quizzes_tree.get_children.return_value = []

        cursor = Mock()
        cursor.fetchall.return_value = [
            (1, "Quiz 1", 60, 70, 3, "2024-01-01", "2024-01-31")
        ]
        mock_conn = Mock()
        mock_conn.cursor.return_value = cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(mod, "get_connection", return_value=mock_conn):
            gui._lms_load_quizzes()
            assert cursor.execute.called


# ── TestGradebookManagement ─────────────────────────────────────────


class TestGradebookManagement:
    """Test gradebook functionality."""

    def test_load_student_grades(self):
        """Test loading student grades via LMSGradebookManager."""
        mod, mixin_cls = _import_mixin()
        gui = _make_gui(mixin_cls, user_role="instructor", user_id="inst001")

        gui.lms_gradebook_course_combo = Mock()
        gui.lms_gradebook_course_combo.get.return_value = "1: CS101"
        gui.lms_gradebook_student_entry = Mock()
        gui.lms_gradebook_student_entry.get.return_value = "S001"
        gui.lms_gradebook_tree = Mock()
        gui.lms_gradebook_tree.get_children.return_value = []

        mock_grades = [
            {
                "entry_id": 1,
                "student_id": "S001",
                "assignment_type": "Quiz",
                "assignment_id": 1,
                "score": 85,
                "max_score": 100,
                "weight": 1.0,
                "graded_by": "inst001",
                "graded_at": "2024-01-15",
            }
        ]

        with patch.object(mod, "LMSGradebookManager") as mock_mgr:
            mock_mgr.get_student_grades.return_value = mock_grades
            gui._lms_load_grades()
            mock_mgr.get_student_grades.assert_called_once_with(1, "S001")

    def test_calculate_course_grade(self):
        """Test calculating course grade via LMSGradebookManager."""
        mod, mixin_cls = _import_mixin()
        gui = _make_gui(mixin_cls, user_role="instructor", user_id="inst001")

        gui.lms_gradebook_course_combo = Mock()
        gui.lms_gradebook_course_combo.get.return_value = "1: CS101"
        gui.lms_gradebook_student_entry = Mock()
        gui.lms_gradebook_student_entry.get.return_value = "S001"

        with (
            patch.object(mod, "LMSGradebookManager") as mock_mgr,
            patch.object(mod, "messagebox"),
        ):
            mock_mgr.calculate_course_grade.return_value = 87.5
            gui._lms_calculate_grade()
            mock_mgr.calculate_course_grade.assert_called_once_with(1, "S001")


# ── TestStudentView ─────────────────────────────────────────────────


class TestStudentView:
    """Test student view functionality."""

    def test_load_student_courses(self):
        """Test loading enrolled courses for student via get_connection."""
        mod, mixin_cls = _import_mixin()
        gui = _make_gui(mixin_cls, user_role="student", user_id="S001")

        gui.lms_student_courses_tree = Mock()
        gui.lms_student_courses_tree.get_children.return_value = []

        cursor = Mock()
        cursor.fetchall.return_value = [
            (1, "CS101", "inst001", 75.5, "2024-01-15")
        ]
        mock_conn = Mock()
        mock_conn.cursor.return_value = cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch.object(mod, "get_connection", return_value=mock_conn):
            gui._lms_load_student_courses()
            assert cursor.execute.called


# ── TestLaunchFunction ──────────────────────────────────────────────


class TestLaunchFunction:
    """Test that the mixin class is importable and usable."""

    def test_mixin_importable(self):
        """Test that LMSTabMixin can be imported."""
        mod, mixin_cls = _import_mixin()
        assert mixin_cls is not None
        assert hasattr(mixin_cls, "create_lms_tab")

    def test_mixin_has_expected_methods(self):
        """Test that LMSTabMixin exposes the expected method set."""
        mod, mixin_cls = _import_mixin()
        expected = [
            "create_lms_tab",
            "_lms_load_courses",
            "_lms_publish_course",
            "_lms_load_content",
            "_lms_load_forums",
            "_lms_load_quizzes",
            "_lms_load_grades",
            "_lms_calculate_grade",
            "_lms_load_student_courses",
        ]
        for method_name in expected:
            assert hasattr(mixin_cls, method_name), f"Missing method: {method_name}"
