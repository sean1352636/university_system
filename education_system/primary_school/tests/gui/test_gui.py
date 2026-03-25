"""GUI tests for the Primary School Management System.

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


@pytest.fixture
def homework_service(db_path):
    """Create a HomeworkService instance with the test database."""
    from education_system.primary_school.modules.domain.academics.homework.services.homework_service import HomeworkService
    return HomeworkService(db_path)


@pytest.fixture
def sample_homework(homework_service, sample_class, sample_subject):
    """Create a sample homework for testing."""
    return homework_service.create_homework(
        title="Spelling Practice",
        class_name=sample_class["class_name"],
        due_date="2025-12-20",
        subject_code=sample_subject["subject_code"],
        description="Practise this week's spelling words",
    )


# ---------------------------------------------------------------------------
# Homework GUI — import & module tests
# ---------------------------------------------------------------------------

@pytest.mark.gui
class TestHomeworkGUIImport:
    """Tests for HomeworkFrame import and module attributes."""

    def test_homework_frame_importable(self, mock_tk):
        """Homework GUI module can be imported with tkinter mocked."""
        from education_system.primary_school.modules.domain.academics.homework.gui import homework_gui
        assert hasattr(homework_gui, "HomeworkFrame")

    def test_homework_frame_class_exists(self, mock_tk):
        """HomeworkFrame class is defined in the module."""
        from education_system.primary_school.modules.domain.academics.homework.gui.homework_gui import HomeworkFrame
        assert HomeworkFrame is not None

    def test_homework_dialog_importable(self, mock_tk):
        """The add/edit dialog class is importable."""
        from education_system.primary_school.modules.domain.academics.homework.gui import homework_gui
        assert hasattr(homework_gui, "_HomeworkDialog")

    def test_homework_statuses_constant(self, mock_tk):
        """HOMEWORK_STATUSES constant is defined and non-empty."""
        from education_system.primary_school.modules.domain.academics.homework.gui import homework_gui
        assert hasattr(homework_gui, "HOMEWORK_STATUSES")
        assert len(homework_gui.HOMEWORK_STATUSES) > 0

    def test_sticker_display_constant(self, mock_tk):
        """STICKER_DISPLAY constant is defined with expected keys."""
        from education_system.primary_school.modules.domain.academics.homework.gui import homework_gui
        assert hasattr(homework_gui, "STICKER_DISPLAY")
        assert "gold_star" in homework_gui.STICKER_DISPLAY


# ---------------------------------------------------------------------------
# Homework GUI — service layer tests (data the GUI consumes)
# ---------------------------------------------------------------------------

@pytest.mark.gui
class TestHomeworkGUIServices:
    """Tests for the service calls that HomeworkFrame makes."""

    def test_homework_service_list_for_gui(self, homework_service, sample_homework):
        """Verify the service call that HomeworkFrame uses to load homework."""
        items = homework_service.list_homework()
        assert len(items) >= 1
        assert any(h["title"] == "Spelling Practice" for h in items)

    def test_homework_service_get_for_gui(self, homework_service, sample_homework):
        """Verify get_homework used when a row is selected."""
        hw_id = sample_homework.get("id") or sample_homework.get("homework_id")
        hw = homework_service.get_homework(hw_id)
        assert hw is not None
        assert hw["title"] == "Spelling Practice"

    def test_homework_create_for_gui(self, homework_service, sample_class):
        """Verify the service call behind the 'Add Homework' dialog."""
        result = homework_service.create_homework(
            title="Times Tables",
            class_name=sample_class["class_name"],
            due_date="2025-12-22",
            description="Practise 6, 7, and 8 times tables",
        )
        assert result["title"] == "Times Tables"
        assert "id" in result or "homework_id" in result

    def test_homework_list_by_class(self, homework_service, sample_homework, sample_class):
        """Filtering by class_name works (used by the class filter dropdown)."""
        items = homework_service.list_homework(class_name=sample_class["class_name"])
        assert all(h["class_name"] == sample_class["class_name"] for h in items)

    def test_pupil_service_list_for_gui(self, pupil_service, sample_pupil):
        """PupilService.list_pupils returns data that homework GUI may reference."""
        pupils = pupil_service.list_pupils()
        assert len(pupils) >= 1
        assert any(p["first_name"] == "Oliver" for p in pupils)

    def test_subject_service_list_for_gui(self, subject_service, sample_subject):
        """SubjectService.list_subjects returns data used in homework dropdowns."""
        subjects = subject_service.list_subjects()
        assert len(subjects) >= 1
        assert any(s["subject_code"] == "ENG" for s in subjects)

    def test_class_service_list_for_gui(self, class_service, sample_class):
        """ClassService.list_classes returns data used in homework class filter."""
        classes = class_service.list_classes()
        assert len(classes) >= 1
        assert any(c["class_name"] == "1A" for c in classes)

    def test_homework_service_empty_list(self, homework_service):
        """list_homework on a fresh DB returns an empty list (no crash)."""
        items = homework_service.list_homework()
        assert isinstance(items, list)

    def test_homework_validation_title_required(self, homework_service, sample_class):
        """Creating homework without a title raises an error."""
        from education_system.primary_school.core.exceptions import HomeworkError
        with pytest.raises(HomeworkError):
            homework_service.create_homework(
                title="",
                class_name=sample_class["class_name"],
                due_date="2025-12-25",
            )
