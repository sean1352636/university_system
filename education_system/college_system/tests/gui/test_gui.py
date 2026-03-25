"""GUI tests for the Sixth Form College Management System.

These tests verify that GUI modules are importable and that the service
layer calls used by each GUI frame work correctly.  tkinter is mocked
so tests run in headless CI environments without a display server.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

# Prepare a mock that will replace tkinter throughout the test session
_tk_mock = MagicMock()


@pytest.fixture
def mock_tk():
    """Patch tkinter so GUI modules can be imported without a display."""
    modules = {
        "tkinter": _tk_mock,
        "tkinter.ttk": _tk_mock,
        "tkinter.messagebox": _tk_mock,
        "tkinter.filedialog": _tk_mock,
        "tkinter.simpledialog": _tk_mock,
    }
    with patch.dict("sys.modules", modules):
        yield _tk_mock


# ---------------------------------------------------------------------------
# Dashboard GUI
# ---------------------------------------------------------------------------

@pytest.mark.gui
class TestDashboardGUI:
    """Tests for DashboardFrame import and underlying services."""

    def test_dashboard_module_importable(self, mock_tk):
        """Dashboard module can be imported with tkinter mocked."""
        from education_system.college_system.modules.shared.gui import dashboard_gui
        assert hasattr(dashboard_gui, "DashboardFrame")

    def test_dashboard_class_exists(self, mock_tk):
        """DashboardFrame class is defined in the module."""
        from education_system.college_system.modules.shared.gui.dashboard_gui import DashboardFrame
        assert DashboardFrame is not None

    def test_student_count_for_dashboard(self, student_service, sample_student):
        """StudentService.list_students returns data the dashboard would display."""
        students = student_service.list_students()
        assert len(students) >= 1
        assert any(s["first_name"] == "John" for s in students)

    def test_course_count_for_dashboard(self, course_service, sample_course):
        """CourseService.list_courses returns data the dashboard would display."""
        courses = course_service.list_courses()
        assert len(courses) >= 1
        assert any(c["course_code"] == "TEST101" for c in courses)

    def test_dashboard_stats_with_empty_db(self, student_service, course_service):
        """Dashboard stats work with a fresh (seeded but no extra) database."""
        students = student_service.list_students()
        courses = course_service.list_courses()
        assert isinstance(students, list)
        assert isinstance(courses, list)


# ---------------------------------------------------------------------------
# Student GUI
# ---------------------------------------------------------------------------

@pytest.mark.gui
class TestStudentGUI:
    """Tests for StudentFrame import and underlying services."""

    def test_student_frame_importable(self, mock_tk):
        """Student GUI module can be imported with tkinter mocked."""
        from education_system.college_system.modules.domain.students.gui import student_gui
        assert hasattr(student_gui, "StudentFrame")

    def test_student_frame_class_exists(self, mock_tk):
        """StudentFrame class is defined in the module."""
        from education_system.college_system.modules.domain.students.gui.student_gui import StudentFrame
        assert StudentFrame is not None

    def test_student_service_list_for_gui(self, student_service, sample_student):
        """Verify the service call that StudentFrame._load_students uses."""
        students = student_service.list_students()
        assert len(students) >= 1
        assert any(s["first_name"] == "John" for s in students)

    def test_student_service_get_for_gui(self, student_service, sample_student):
        """Verify get_student used when a row is selected in the treeview."""
        student = student_service.get_student(sample_student["id"])
        assert student is not None
        assert student["last_name"] == "Doe"

    def test_student_create_for_gui(self, student_service):
        """Verify the service call behind the 'Add Student' dialog."""
        result = student_service.create_student(
            first_name="Alice",
            last_name="Wonder",
            email="alice.wonder@sixthform.ac.uk",
            year_group="13",
            form_group="13B",
        )
        assert result["first_name"] == "Alice"
        assert "id" in result


# ---------------------------------------------------------------------------
# Course GUI
# ---------------------------------------------------------------------------

@pytest.mark.gui
class TestCourseGUI:
    """Tests for CourseFrame import and underlying services."""

    def test_course_frame_importable(self, mock_tk):
        """Course GUI module can be imported with tkinter mocked."""
        from education_system.college_system.modules.domain.courses.gui import course_gui
        assert hasattr(course_gui, "CourseFrame")

    def test_course_frame_class_exists(self, mock_tk):
        """CourseFrame class is defined in the module."""
        from education_system.college_system.modules.domain.courses.gui.course_gui import CourseFrame
        assert CourseFrame is not None

    def test_course_service_list_for_gui(self, course_service, sample_course):
        """Verify the service call that CourseFrame._load_courses uses."""
        courses = course_service.list_courses()
        assert len(courses) >= 1
        assert any(c["title"] == "Intro to Computer Science" for c in courses)

    def test_course_service_get_for_gui(self, course_service, sample_course):
        """Verify get_course used when a row is selected in the treeview."""
        course = course_service.get_course(sample_course["id"])
        assert course is not None
        assert course["course_code"] == "TEST101"

    def test_course_create_for_gui(self, course_service):
        """Verify the service call behind the 'Add Course' dialog."""
        result = course_service.create_course(
            course_code="ENG201",
            title="English Literature",
            guided_learning_hours=4,
            capacity=25,
            subject_area="English",
        )
        assert result["course_code"] == "ENG201"
        assert "id" in result
