"""Tests for the Exam Portal GUI.

Tests GUI component creation, widget presence, and interaction logic
without requiring a display (uses withdraw to hide the window).
"""

import pytest
import tkinter as tk
from unittest.mock import patch, MagicMock, PropertyMock
from contextlib import contextmanager

from education_system.university_system.infrastructure.database.db import sqlite3


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _suppress_activity_logger():
    with patch(
        "education_system.university_system.modules.shared.utils.simple_activity_logger.module_api.logger"
    ) as mock_logger:
        mock_logger.log_activity = MagicMock()
        yield


@pytest.fixture()
def db_path(tmp_path):
    """Create a temp database for the service."""
    path = str(tmp_path / "test_gui.db")
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()
    return path


@pytest.fixture()
def mock_get_connection(db_path):
    """Patch get_connection to use temp DB."""
    @contextmanager
    def _fake():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    with patch(
        "education_system.university_system.modules.domain.academics.services.exam_portal.exam_service.get_connection",
        _fake,
    ):
        yield


@pytest.fixture()
def mock_auth():
    auth = MagicMock()
    auth.current_user = {
        "id": 1,
        "user_id": 1,
        "username": "testadmin",
        "role": "admin",
        "display_name": "Test Admin",
    }
    return auth


@pytest.fixture()
def svc(mock_get_connection):
    from education_system.university_system.modules.domain.academics.services.exam_portal import ExamPortalService
    return ExamPortalService()


# ── GUI Instantiation ──────────────────────────────────────────────

@pytest.mark.gui
class TestExamPortalGUICreation:
    def test_gui_creates_without_error(self, svc, mock_auth, mock_get_connection):
        """GUI should instantiate and build all tabs without raising."""
        root = tk.Tk()
        root.withdraw()
        try:
            from education_system.university_system.modules.domain.academics.gui.exam_portal import ExamPortalGUI
            gui = ExamPortalGUI(parent=root, auth=mock_auth)

            # Should have a notebook with tabs
            assert gui.notebook is not None
            tabs = gui.notebook.tabs()
            assert len(tabs) >= 2  # At minimum: browse + results
        finally:
            root.destroy()

    def test_admin_sees_management_tabs(self, svc, mock_auth, mock_get_connection):
        """Admin role should see manage, grading, and analytics tabs."""
        root = tk.Tk()
        root.withdraw()
        try:
            from education_system.university_system.modules.domain.academics.gui.exam_portal import ExamPortalGUI
            gui = ExamPortalGUI(parent=root, auth=mock_auth)

            tab_names = [gui.notebook.tab(t, "text") for t in gui.notebook.tabs()]
            assert "Available Exams" in tab_names
            assert "My Results" in tab_names
            assert "Manage Exams" in tab_names
            assert "Grading" in tab_names
            assert "Analytics" in tab_names
        finally:
            root.destroy()

    def test_student_sees_only_student_tabs(self, svc, mock_get_connection):
        """Student role should only see browse and results tabs."""
        root = tk.Tk()
        root.withdraw()
        try:
            student_auth = MagicMock()
            student_auth.current_user = {
                "id": 2, "username": "student1", "role": "student",
            }
            from education_system.university_system.modules.domain.academics.gui.exam_portal import ExamPortalGUI
            gui = ExamPortalGUI(parent=root, auth=student_auth)

            tab_names = [gui.notebook.tab(t, "text") for t in gui.notebook.tabs()]
            assert "Available Exams" in tab_names
            assert "My Results" in tab_names
            assert "Manage Exams" not in tab_names
            assert "Grading" not in tab_names
        finally:
            root.destroy()


# ── Browse Tab ──────────────────────────────────────────────────────

@pytest.mark.gui
class TestBrowseTab:
    def test_browse_tree_columns(self, svc, mock_auth, mock_get_connection):
        root = tk.Tk()
        root.withdraw()
        try:
            from education_system.university_system.modules.domain.academics.gui.exam_portal import ExamPortalGUI
            gui = ExamPortalGUI(parent=root, auth=mock_auth)
            cols = gui.browse_tree["columns"]
            assert "Title" in cols
            assert "Duration" in cols
            assert "Status" in cols
        finally:
            root.destroy()

    def test_refresh_browse_shows_published_exams(self, svc, mock_auth, mock_get_connection):
        root = tk.Tk()
        root.withdraw()
        try:
            # Create and publish an exam
            eid = svc.create_exam("Visible Exam", "testadmin", duration_minutes=60)
            svc.add_question(eid, "mcq", "Q?", options=["A", "B"], correct_answer="A")
            svc.publish_exam(eid)

            from education_system.university_system.modules.domain.academics.gui.exam_portal import ExamPortalGUI
            gui = ExamPortalGUI(parent=root, auth=mock_auth)
            gui._refresh_browse()

            items = gui.browse_tree.get_children()
            assert len(items) >= 1
        finally:
            root.destroy()


# ── Manage Tab ──────────────────────────────────────────────────────

@pytest.mark.gui
class TestManageTab:
    def test_manage_tree_populates(self, svc, mock_auth, mock_get_connection):
        root = tk.Tk()
        root.withdraw()
        try:
            svc.create_exam("Admin Exam", "testadmin")

            from education_system.university_system.modules.domain.academics.gui.exam_portal import ExamPortalGUI
            gui = ExamPortalGUI(parent=root, auth=mock_auth)
            gui._refresh_manage()

            items = gui.manage_tree.get_children()
            assert len(items) >= 1
        finally:
            root.destroy()


# ── Results Tab ─────────────────────────────────────────────────────

@pytest.mark.gui
class TestResultsTab:
    def test_results_tree_exists(self, svc, mock_auth, mock_get_connection):
        root = tk.Tk()
        root.withdraw()
        try:
            from education_system.university_system.modules.domain.academics.gui.exam_portal import ExamPortalGUI
            gui = ExamPortalGUI(parent=root, auth=mock_auth)
            assert gui.results_tree is not None
            cols = gui.results_tree["columns"]
            assert "Score" in cols
            assert "Percentage" in cols
        finally:
            root.destroy()

    def test_results_show_completed_attempts(self, svc, mock_auth, mock_get_connection):
        root = tk.Tk()
        root.withdraw()
        try:
            eid = svc.create_exam("Result Exam", "inst", max_attempts=5)
            svc.add_question(eid, "mcq", "Q?", options=["A"], correct_answer="A", marks=10)
            svc.publish_exam(eid)

            attempt = svc.start_attempt(eid, "testadmin")
            qs = svc.get_questions(eid)
            svc.save_answer(attempt["id"], qs[0]["id"], "A")
            svc.submit_attempt(attempt["id"])

            from education_system.university_system.modules.domain.academics.gui.exam_portal import ExamPortalGUI
            gui = ExamPortalGUI(parent=root, auth=mock_auth)
            gui._refresh_results()

            items = gui.results_tree.get_children()
            assert len(items) >= 1
        finally:
            root.destroy()


# ── Grading Tab ─────────────────────────────────────────────────────

@pytest.mark.gui
class TestGradingTab:
    def test_grading_tree_shows_ungraded(self, svc, mock_auth, mock_get_connection):
        root = tk.Tk()
        root.withdraw()
        try:
            eid = svc.create_exam("Grade Me", "testadmin")
            svc.add_question(eid, "essay", "Discuss...", marks=20)
            svc.publish_exam(eid)

            attempt = svc.start_attempt(eid, "student1")
            qs = svc.get_questions(eid)
            svc.save_answer(attempt["id"], qs[0]["id"], "My essay")
            svc.submit_attempt(attempt["id"])

            from education_system.university_system.modules.domain.academics.gui.exam_portal import ExamPortalGUI
            gui = ExamPortalGUI(parent=root, auth=mock_auth)
            gui._refresh_grading()

            items = gui.grading_tree.get_children()
            assert len(items) >= 1
        finally:
            root.destroy()
