"""GUI tests for the Secondary School Management System.

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
# Student GUI
# ---------------------------------------------------------------------------

@pytest.mark.gui
class TestStudentGUI:
    """Tests for StudentFrame import and underlying services."""

    def test_student_frame_importable(self, mock_tk):
        """Student GUI module can be imported with tkinter mocked."""
        from education_system.secondary_school.modules.domain.academics.students.gui import student_gui
        assert hasattr(student_gui, "StudentFrame")

    def test_student_frame_class_exists(self, mock_tk):
        """StudentFrame class is defined in the module."""
        from education_system.secondary_school.modules.domain.academics.students.gui.student_gui import StudentFrame
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
            first_name="Emily",
            last_name="Brown",
            email="emily.brown@school.local",
            year_group="8",
            form_group="8C",
        )
        assert result["first_name"] == "Emily"
        assert "id" in result


# ---------------------------------------------------------------------------
# Homework GUI
# ---------------------------------------------------------------------------

@pytest.mark.gui
class TestHomeworkGUI:
    """Tests for HomeworkFrame import and underlying services."""

    def test_homework_frame_importable(self, mock_tk):
        """Homework GUI module can be imported with tkinter mocked."""
        from education_system.secondary_school.modules.domain.academics.homework.gui import homework_gui
        assert hasattr(homework_gui, "HomeworkFrame")

    def test_homework_frame_class_exists(self, mock_tk):
        """HomeworkFrame class is defined in the module."""
        from education_system.secondary_school.modules.domain.academics.homework.gui.homework_gui import HomeworkFrame
        assert HomeworkFrame is not None

    def test_homework_service_list_for_gui(self, homework_service, sample_homework):
        """Verify the service call that HomeworkFrame uses to load homework."""
        items = homework_service.list_homework()
        assert len(items) >= 1
        assert any(h["title"] == "Algebra Practice" for h in items)

    def test_homework_service_list_filtered(self, homework_service, sample_homework, sample_subject):
        """Verify list_homework with subject filter (used by filter dropdown)."""
        items = homework_service.list_homework(subject_id=sample_subject["id"])
        assert len(items) >= 1
        assert all(h["subject_id"] == sample_subject["id"] for h in items)

    def test_homework_create_for_gui(self, homework_service, sample_subject):
        """Verify the service call behind the 'Set Homework' dialog."""
        result = homework_service.create_homework(
            subject_id=sample_subject["id"],
            title="Reading Comprehension",
            due_date="2025-12-22",
            year_group="9",
            description="Read chapter 5 and answer questions",
            max_marks=30,
        )
        assert result["title"] == "Reading Comprehension"
        assert "id" in result


# ---------------------------------------------------------------------------
# Admissions GUI
# ---------------------------------------------------------------------------

@pytest.mark.gui
class TestAdmissionsGUI:
    """Tests for AdmissionsFrame import and underlying services."""

    def test_admissions_frame_importable(self, mock_tk):
        """Admissions GUI module can be imported with tkinter mocked."""
        from education_system.secondary_school.modules.domain.admin.admissions.gui import admissions_gui
        assert hasattr(admissions_gui, "AdmissionsFrame")

    def test_admissions_frame_class_exists(self, mock_tk):
        """AdmissionsFrame class is defined in the module."""
        from education_system.secondary_school.modules.domain.admin.admissions.gui.admissions_gui import AdmissionsFrame
        assert AdmissionsFrame is not None

    def test_admissions_service_list_for_gui(self, admissions_service):
        """Verify list_applications returns a list (may be empty initially)."""
        apps = admissions_service.list_applications()
        assert isinstance(apps, list)

    def test_admissions_create_for_gui(self, admissions_service):
        """Verify the service call behind the 'New Application' dialog."""
        result = admissions_service.create_application(
            first_name="Tom",
            last_name="Wilson",
            year_group="7",
            parent_name="Sarah Wilson",
            parent_email="sarah.wilson@example.com",
        )
        assert result.get("first_name") or result.get("applicant_first_name") == "Tom"
        assert "id" in result or "application_id" in result

    def test_admissions_list_after_create(self, admissions_service):
        """After creating an application, it appears in list_applications."""
        admissions_service.create_application(
            first_name="Lucy",
            last_name="Taylor",
            year_group="8",
            parent_name="Mark Taylor",
        )
        apps = admissions_service.list_applications()
        assert any(
            a.get("first_name") == "Lucy" or a.get("applicant_first_name") == "Lucy"
            for a in apps
        )
