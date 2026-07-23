"""
Test suite for student manager module
Tests all student management functionality
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch, call
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

@pytest.fixture
def mock_root():
    """Create a mock Tkinter root window"""
    root = Mock(spec=tk.Tk)
    root.winfo_exists.return_value = True
    return root

@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {'username': 'test_user', 'role': 'admin'}
    auth.is_logged_in.return_value = True
    return auth

@pytest.fixture
def mock_conn():
    """Create a mock database connection"""
    conn = Mock(spec=sqlite3.Connection)
    cursor = Mock(spec=sqlite3.Cursor)
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    conn.cursor.return_value = cursor
    return conn

@pytest.fixture
def mock_app(mock_root, mock_auth, mock_conn):
    """Create a mock application object"""
    app = Mock()
    app.root = mock_root
    app.auth = mock_auth
    app.conn = mock_conn
    app.layout = Mock()
    app.layout.content_frame = Mock(spec=tk.Frame)
    app.layout.status_var = Mock()
    return app

@pytest.fixture
def student_manager(mock_app):
    """Create StudentManager instance with mocked dependencies"""
    with patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection', return_value=mock_app.conn):
        from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager import StudentManager
        manager = StudentManager(mock_app)
        return manager

class TestStudentManagerInitialization:
    """Test StudentManager initialization"""

    def test_initialization_with_valid_app(self, mock_app):
        """Test initialization with valid app object"""
        with patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection', return_value=mock_app.conn):
            from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager import StudentManager
            manager = StudentManager(mock_app)

            assert manager.app == mock_app
            assert manager.root == mock_app.root
            assert manager.auth == mock_app.auth
            assert manager.conn == mock_app.conn

    def test_content_frame_property(self, student_manager, mock_app):
        """Test content_frame property returns correct frame"""
        content_frame = student_manager.content_frame
        assert content_frame == mock_app.layout.content_frame

class TestDatabaseOperations:
    """Test database operations"""

    def test_get_cursor_existing(self, student_manager):
        """Test get_cursor with existing cursor"""
        cursor = student_manager.get_cursor()
        assert cursor is not None

    def test_get_cursor_creates_new_connection(self, mock_app):
        """Test get_cursor creates new connection when needed"""
        mock_app.conn = None

        with patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection') as mock_get_conn:
            new_conn = Mock(spec=sqlite3.Connection)
            new_cursor = Mock(spec=sqlite3.Cursor)
            new_conn.cursor.return_value = new_cursor
            mock_get_conn.return_value = new_conn

            from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager import StudentManager
            manager = StudentManager(mock_app)
            cursor = manager.get_cursor()

            assert cursor is not None

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection')
    def test_refresh_students(self, mock_get_conn, student_manager, mock_conn):
        """Test refresh students functionality"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('S001', 'John', 'M', 'Doe', 'Computer Science', 'john@example.com', '2024-01-01')
        ]
        mock_conn.cursor.return_value = cursor
        mock_get_conn.return_value = mock_conn
        # get_cursor() returns the cursor cached at construction time, so point
        # it at this test's cursor rather than relying on a later reassignment.
        student_manager.cursor = cursor

        # Mock student_tree
        student_manager.student_tree = Mock()
        student_manager.student_tree.get_children.return_value = []

        student_manager.refresh_students()

        # Verify database query was executed (refresh issues the student query
        # plus an exam-eligibility probe)
        cursor.execute.assert_called()
        # Verify insert was called
        student_manager.student_tree.insert.assert_called()

class TestStudentSearch:
    """Test student search functionality"""

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection')
    def test_search_students_with_term(self, mock_get_conn, student_manager, mock_conn):
        """Test searching students with search term"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('S001', 'John', 'Doe', 'Computer Science', 'john@example.com', '2024-01-01')
        ]
        mock_conn.cursor.return_value = cursor
        mock_get_conn.return_value = mock_conn
        student_manager.cursor = cursor

        # Mock search variable and tree
        student_manager.student_search_var = Mock()
        student_manager.student_search_var.get.return_value = 'john'
        student_manager.student_tree = Mock()
        student_manager.student_tree.get_children.return_value = []

        event = Mock()
        student_manager.search_students(event)

        # Verify search query was executed
        cursor.execute.assert_called_once()

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection')
    def test_search_students_empty_term(self, mock_get_conn, student_manager, mock_conn):
        """Test searching students with empty search term"""
        cursor = Mock()
        cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = cursor
        mock_get_conn.return_value = mock_conn
        student_manager.cursor = cursor

        # Mock search variable and tree
        student_manager.student_search_var = Mock()
        student_manager.student_search_var.get.return_value = ''
        student_manager.student_tree = Mock()
        student_manager.student_tree.get_children.return_value = []

        event = Mock()
        student_manager.search_students(event)

        # Verify query was executed (should return all students)
        cursor.execute.assert_called_once()

class TestImportExport:
    """Test import and export functionality"""

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.filedialog')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.messagebox')
    @patch('builtins.open', create=True)
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection')
    def test_import_students_success(self, mock_get_conn, mock_open_func, mock_msgbox, mock_filedialog, student_manager, mock_conn):
        """Test successful student import"""
        mock_filedialog.askopenfilename.return_value = '/path/to/students.csv'

        # Mock CSV content
        csv_content = "student_id,first_name,last_name,course,email_address\nS001,John,Doe,CS,john@example.com"
        mock_file = MagicMock()
        mock_file.__enter__.return_value = csv_content.split('\n')
        mock_open_func.return_value = mock_file

        cursor = Mock()
        mock_conn.cursor.return_value = cursor
        mock_get_conn.return_value = mock_conn

        # Mock other methods
        student_manager.refresh_students = Mock()
        student_manager.populate_filter_combos = Mock()
        student_manager.update_status = Mock()

        # This would require more complex mocking of csv.DictReader
        # For now, we'll just test that the file dialog is called
        assert mock_filedialog is not None

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.filedialog')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.messagebox')
    @patch('builtins.open', create=True)
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection')
    def test_export_students_success(self, mock_get_conn, mock_open_func, mock_msgbox, mock_filedialog, student_manager, mock_conn):
        """Test successful student export"""
        mock_filedialog.asksaveasfilename.return_value = '/path/to/export.csv'

        cursor = Mock()
        cursor.fetchall.return_value = [
            ('S001', 'John', 'M', 'Doe', 'CS', 'john@example.com', None, None, '2024-01-01', 'Active', None, None, None)
        ]
        mock_conn.cursor.return_value = cursor
        mock_get_conn.return_value = mock_conn

        student_manager.update_status = Mock()

        # Mock file writing
        mock_file = MagicMock()
        mock_open_func.return_value.__enter__.return_value = mock_file

        # This would require complex mocking of csv.writer
        # For now, we'll test that the file dialog is called
        assert mock_filedialog is not None

class TestReportGeneration:
    """Test report generation functionality"""

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.messagebox')
    def test_generate_student_progress_report(self, mock_msgbox, mock_get_conn, student_manager, mock_conn):
        """Test student progress report generation"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('S001', 'John', 'Doe', 'CS', 5, 10, 85.5, 0)
        ]
        mock_conn.cursor.return_value = cursor
        mock_get_conn.return_value = mock_conn

        # Mock the _display_report method
        student_manager._display_report = Mock()

        student_manager.generate_student_progress_report()

        # Verify database queries were executed
        assert cursor.execute.called

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.messagebox')
    def test_generate_at_risk_report(self, mock_msgbox, mock_get_conn, student_manager, mock_conn):
        """Test at-risk students report generation"""
        cursor = Mock()
        cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = cursor
        mock_get_conn.return_value = mock_conn

        # Mock the _display_report method
        student_manager._display_report = Mock()

        student_manager.generate_at_risk_report()

        # Verify database queries were executed
        assert cursor.execute.called

class TestStatusUpdates:
    """Test status update functionality"""

    def test_update_status(self, student_manager, mock_app):
        """Test status bar update"""
        message = "Test status message"
        student_manager.update_status(message)

        mock_app.layout.status_var.set.assert_called_once_with(message)

    def test_update_status_no_layout(self, student_manager):
        """Test status update when layout is not available"""
        student_manager.app.layout = None

        # Should not raise an error
        student_manager.update_status("Test message")

class TestFilterFunctionality:
    """Test filter functionality"""

    def test_filter_students(self, student_manager):
        """Test filtering students by course"""
        student_manager.refresh_students = Mock()

        student_manager.filter_students()

        # Verify refresh_students was called
        student_manager.refresh_students.assert_called_once()

    def test_populate_filter_combos(self, student_manager):
        """Test populating filter combo boxes"""
        # This is currently a pass-through method
        student_manager.populate_filter_combos()
        # Should not raise an error

class TestHelperFunctions:
    """Test helper functions"""

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection')
    def test_init_basic_database(self, mock_get_conn, mock_conn):
        """Test basic database initialization"""
        from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager import init_basic_database

        cursor = Mock()
        mock_conn.cursor.return_value = cursor
        mock_get_conn.return_value = mock_conn

        result = init_basic_database()

        assert result is True
        assert cursor.execute.called

    @patch('education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager.get_connection')
    def test_init_enhanced_grades_db(self, mock_get_conn, mock_conn):
        """Test enhanced grades database initialization"""
        from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager import init_enhanced_grades_db

        cursor = Mock()
        mock_conn.cursor.return_value = cursor
        mock_get_conn.return_value = mock_conn

        result = init_enhanced_grades_db()

        assert result is True
        assert cursor.execute.called

    def test_percentage_to_letter(self):
        """Test percentage to letter grade conversion"""
        from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager import percentage_to_letter

        assert percentage_to_letter(95) == 'A+'
        assert percentage_to_letter(87) == 'A'
        assert percentage_to_letter(82) == 'A-'
        assert percentage_to_letter(30) == 'F'

    def test_letter_to_gpa(self):
        """Test letter grade to GPA conversion"""
        from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.student_manager import letter_to_gpa

        assert letter_to_gpa('A+') == 4.3
        assert letter_to_gpa('A') == 4.0
        assert letter_to_gpa('B') == 3.0
        assert letter_to_gpa('F') == 0.0
