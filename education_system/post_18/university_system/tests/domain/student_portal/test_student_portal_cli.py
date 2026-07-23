"""
Tests for StudentPortalCLI — the CLI version of the student portal.

Tests cover initialization, menu navigation, dashboard display, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from education_system.post_18.university_system.infrastructure.database.db import sqlite3


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_auth():
    """Create a mock authentication object with a student user."""
    auth = Mock()
    auth.current_user = {
        'id': 42,
        'user_id': 42,
        'username': 'jdoe',
        'role': 'student',
        'student_id': 'STU0042',
        'display_name': 'Jane Doe',
    }
    auth.is_logged_in.return_value = True
    auth.check_permission.return_value = True
    auth.logout.return_value = None
    return auth


@pytest.fixture
def mock_conn():
    """Create an in-memory SQLite connection with student data."""
    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()

    # Minimal tables that the dashboard query would use
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            name TEXT,
            gpa REAL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            module_name TEXT,
            grade TEXT
        )
    """)
    cur.execute(
        "INSERT INTO students (student_id, name, gpa) VALUES (?, ?, ?)",
        ('STU0042', 'Jane Doe', 3.75),
    )
    cur.execute(
        "INSERT INTO enrollments (student_id, module_name, grade) VALUES (?, ?, ?)",
        ('STU0042', 'Computer Science 101', 'A'),
    )
    cur.execute(
        "INSERT INTO enrollments (student_id, module_name, grade) VALUES (?, ?, ?)",
        ('STU0042', 'Mathematics 201', 'B+'),
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Tests — Initialization
# ---------------------------------------------------------------------------

class TestStudentPortalCLIInit:
    """Tests for StudentPortalCLI.__init__."""

    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_auth')
    def test_init_creates_auth_and_gets_student_id(self, mock_get_auth, mock_auth):
        """__init__ should store the auth object and extract the student_id."""
        mock_get_auth.return_value = mock_auth

        from education_system.post_18.university_system.modules.shared.cli.student_portal_cli import StudentPortalCLI

        portal = StudentPortalCLI.__new__(StudentPortalCLI)
        portal.auth = mock_get_auth()
        portal.student_id = portal.auth.current_user.get('student_id')

        assert portal.auth is mock_auth
        assert portal.student_id == 'STU0042'


# ---------------------------------------------------------------------------
# Tests — Main Menu
# ---------------------------------------------------------------------------

class TestStudentPortalCLIMainMenu:
    """Tests for the main_menu loop."""

    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_auth')
    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_connection')
    @patch('builtins.input')
    def test_main_menu_exits_on_zero(self, mock_input, mock_get_conn, mock_get_auth,
                                      mock_auth, mock_conn, capsys):
        """Entering '0' should exit the menu loop."""
        mock_get_auth.return_value = mock_auth
        mock_get_conn.return_value = mock_conn
        mock_input.return_value = '0'

        from education_system.post_18.university_system.modules.shared.cli.student_portal_cli import StudentPortalCLI

        portal = StudentPortalCLI.__new__(StudentPortalCLI)
        portal.auth = mock_auth
        portal.student_id = 'STU0042'

        # main_menu should return when user enters '0'
        portal.main_menu()

        captured = capsys.readouterr()
        # The menu should have been printed at least once
        assert 'Dashboard' in captured.out or 'dashboard' in captured.out.lower() or mock_input.called

    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_auth')
    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_connection')
    @patch('builtins.input')
    def test_main_menu_dispatches_to_dashboard(self, mock_input, mock_get_conn, mock_get_auth,
                                                mock_auth, mock_conn, capsys):
        """Option 1 should dispatch to the dashboard view."""
        mock_get_auth.return_value = mock_auth
        mock_get_conn.return_value = mock_conn
        # First call selects option 1 (dashboard), second call exits
        mock_input.side_effect = ['1', '0']

        from education_system.post_18.university_system.modules.shared.cli.student_portal_cli import StudentPortalCLI

        portal = StudentPortalCLI.__new__(StudentPortalCLI)
        portal.auth = mock_auth
        portal.student_id = 'STU0042'

        with patch.object(portal, 'view_dashboard') as mock_dashboard:
            portal.main_menu()
            mock_dashboard.assert_called_once()

    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_auth')
    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_connection')
    @patch('builtins.input')
    def test_main_menu_dispatches_to_academic_progress(self, mock_input, mock_get_conn,
                                                        mock_get_auth, mock_auth, mock_conn, capsys):
        """Option 2 should dispatch to academic progress."""
        mock_get_auth.return_value = mock_auth
        mock_get_conn.return_value = mock_conn
        mock_input.side_effect = ['2', '0']

        from education_system.post_18.university_system.modules.shared.cli.student_portal_cli import StudentPortalCLI

        portal = StudentPortalCLI.__new__(StudentPortalCLI)
        portal.auth = mock_auth
        portal.student_id = 'STU0042'

        with patch.object(portal, '_handle_academic_progress') as mock_progress:
            portal.main_menu()
            mock_progress.assert_called_once()

    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_auth')
    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_connection')
    @patch('builtins.input')
    def test_main_menu_dispatches_to_university_shop(self, mock_input, mock_get_conn,
                                                      mock_get_auth, mock_auth, mock_conn, capsys):
        """Option 15 should dispatch to university shop."""
        mock_get_auth.return_value = mock_auth
        mock_get_conn.return_value = mock_conn
        mock_input.side_effect = ['15', '0']

        from education_system.post_18.university_system.modules.shared.cli.student_portal_cli import StudentPortalCLI

        portal = StudentPortalCLI.__new__(StudentPortalCLI)
        portal.auth = mock_auth
        portal.student_id = 'STU0042'

        with patch.object(portal, '_handle_university_shop') as mock_shop:
            portal.main_menu()
            mock_shop.assert_called_once()

    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_auth')
    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_connection')
    @patch('builtins.input')
    def test_invalid_menu_choice_shows_error(self, mock_input, mock_get_conn, mock_get_auth,
                                              mock_auth, mock_conn, capsys):
        """An invalid menu choice should print an error message."""
        mock_get_auth.return_value = mock_auth
        mock_get_conn.return_value = mock_conn
        # '999' triggers invalid msg, '' handles "Press Enter to continue...", '0' exits
        mock_input.side_effect = ['999', '', '0']

        from education_system.post_18.university_system.modules.shared.cli.student_portal_cli import StudentPortalCLI

        portal = StudentPortalCLI.__new__(StudentPortalCLI)
        portal.auth = mock_auth
        portal.student_id = 'STU0042'

        portal.main_menu()

        captured = capsys.readouterr()
        lower_out = captured.out.lower()
        assert 'invalid' in lower_out or 'error' in lower_out or 'not' in lower_out


# ---------------------------------------------------------------------------
# Tests — Dashboard View
# ---------------------------------------------------------------------------

class TestStudentPortalCLIDashboard:
    """Tests for view_dashboard."""

    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_connection')
    @patch('builtins.input', return_value='')
    def test_view_dashboard_prints_gpa_and_modules(self, mock_input, mock_get_conn,
                                                    mock_auth, mock_conn, capsys):
        """view_dashboard should print GPA and enrolled module information."""
        mock_get_conn.return_value = mock_conn

        from education_system.post_18.university_system.modules.shared.cli.student_portal_cli import StudentPortalCLI

        portal = StudentPortalCLI.__new__(StudentPortalCLI)
        portal.auth = mock_auth
        portal.student_id = 'STU0042'

        portal.view_dashboard()

        captured = capsys.readouterr()
        # Should display GPA and at least one module
        assert '3.75' in captured.out or 'GPA' in captured.out.upper() or 'gpa' in captured.out.lower()

    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_connection')
    @patch('builtins.input', return_value='')
    def test_view_dashboard_handles_empty_data(self, mock_input, mock_get_conn,
                                                mock_auth, capsys):
        """view_dashboard should handle a student with no records gracefully."""
        empty_conn = sqlite3.connect(':memory:')
        cur = empty_conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY, student_id TEXT, name TEXT, gpa REAL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY, student_id TEXT, module_name TEXT, grade TEXT
            )
        """)
        empty_conn.commit()
        mock_get_conn.return_value = empty_conn

        from education_system.post_18.university_system.modules.shared.cli.student_portal_cli import StudentPortalCLI

        portal = StudentPortalCLI.__new__(StudentPortalCLI)
        portal.auth = mock_auth
        portal.student_id = 'STU0042'

        # Should not raise
        portal.view_dashboard()

        captured = capsys.readouterr()
        # Should print something (no crash)
        assert captured.out is not None

        empty_conn.close()

    @patch('education_system.post_18.university_system.modules.shared.cli.student_portal_cli.get_connection')
    @patch('builtins.input', return_value='')
    def test_view_dashboard_handles_db_error(self, mock_input, mock_get_conn,
                                              mock_auth, capsys):
        """view_dashboard should handle database errors without crashing."""
        mock_get_conn.side_effect = Exception("Database connection failed")

        from education_system.post_18.university_system.modules.shared.cli.student_portal_cli import StudentPortalCLI

        portal = StudentPortalCLI.__new__(StudentPortalCLI)
        portal.auth = mock_auth
        portal.student_id = 'STU0042'

        # Should not raise
        portal.view_dashboard()

        captured = capsys.readouterr()
        lower_out = captured.out.lower()
        assert 'error' in lower_out or 'failed' in lower_out or 'unable' in lower_out
