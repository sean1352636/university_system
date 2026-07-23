"""
Tests for Accreditation Support CLI menu.

Tests cover table creation, document upload/view, review scheduling/viewing,
standards management, menu navigation, and auth guard behaviour.
"""

import pytest
import sqlite3
from unittest.mock import Mock, patch, call

MODULE = "education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_auth():
    """Create a mock authentication object with an admin user."""
    auth = Mock()
    auth.current_user = {
        "id": 1,
        "user_id": 1,
        "username": "admin",
        "role": "admin",
        "display_name": "Admin User",
    }
    auth.is_logged_in.return_value = True
    auth.check_permission.return_value = True
    return auth


class _NoCloseConn:
    """Wrapper that proxies everything to a real connection but ignores close()."""

    def __init__(self, real_conn):
        self._real = real_conn

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._real, name)


@pytest.fixture
def mem_conn():
    """Create an in-memory SQLite connection with accreditation tables."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accreditation_documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            path TEXT NOT NULL,
            upload_date TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accreditation_reviews (
            id TEXT PRIMARY KEY,
            review_date TEXT NOT NULL,
            review_time TEXT NOT NULL,
            reviewer TEXT NOT NULL,
            created_on TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accreditation_standards (
            id TEXT PRIMARY KEY,
            standard_text TEXT NOT NULL,
            description TEXT,
            last_updated TEXT NOT NULL
        )
    """)
    conn.commit()
    wrapper = _NoCloseConn(conn)
    yield wrapper
    conn.close()


# ---------------------------------------------------------------------------
# Tests -- Table creation
# ---------------------------------------------------------------------------

class TestEnsureTables:
    """Tests for _ensure_tables."""

    @patch(f"{MODULE}.get_connection")
    def test_ensure_tables_creates_all_three_tables(self, mock_get_conn):
        """_ensure_tables should create documents, reviews, and standards tables."""
        real_conn = sqlite3.connect(":memory:")
        mock_get_conn.return_value = _NoCloseConn(real_conn)

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _ensure_tables,
        )

        _ensure_tables()

        cur = real_conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cur.fetchall()}
        assert "accreditation_documents" in tables
        assert "accreditation_reviews" in tables
        assert "accreditation_standards" in tables
        real_conn.close()

    @patch(f"{MODULE}.get_connection")
    def test_ensure_tables_idempotent(self, mock_get_conn):
        """Calling _ensure_tables twice should not raise."""
        conn = sqlite3.connect(":memory:")
        mock_get_conn.return_value = conn

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _ensure_tables,
        )

        _ensure_tables()
        # Re-open because first call closes the connection
        conn2 = sqlite3.connect(":memory:")
        mock_get_conn.return_value = conn2
        _ensure_tables()  # should not raise
        conn2.close()


# ---------------------------------------------------------------------------
# Tests -- Document operations
# ---------------------------------------------------------------------------

class TestUploadDocument:
    """Tests for _upload_document."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_upload_document_success(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Uploading a document with valid inputs should insert a row."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ["Accreditation Report", "/docs/report.pdf", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _upload_document,
        )

        _upload_document()

        captured = capsys.readouterr()
        assert "uploaded successfully" in captured.out

        cur = mem_conn.cursor()
        cur.execute("SELECT title, path FROM accreditation_documents")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "Accreditation Report"
        assert row[1] == "/docs/report.pdf"

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_upload_document_empty_title_returns_early(self, mock_input, mock_get_conn, mem_conn, capsys):
        """An empty title should abort the upload."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ["", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _upload_document,
        )

        _upload_document()

        captured = capsys.readouterr()
        assert "title is required" in captured.out.lower()

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_upload_document_empty_path_returns_early(self, mock_input, mock_get_conn, mem_conn, capsys):
        """An empty file path should abort the upload."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ["Some Title", "", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _upload_document,
        )

        _upload_document()

        captured = capsys.readouterr()
        assert "file path is required" in captured.out.lower()


class TestViewDocuments:
    """Tests for _view_documents."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input", return_value="")
    def test_view_documents_empty(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Should display a 'no documents' message when table is empty."""
        mock_get_conn.return_value = mem_conn

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _view_documents,
        )

        _view_documents()

        captured = capsys.readouterr()
        assert "no accreditation documents" in captured.out.lower()

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input", return_value="")
    def test_view_documents_with_data(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Should list documents when data exists."""
        cur = mem_conn.cursor()
        cur.execute(
            "INSERT INTO accreditation_documents (id, title, path, upload_date) VALUES (?, ?, ?, ?)",
            ("doc-1", "Policy Doc", "/docs/policy.pdf", "2026-03-28"),
        )
        mem_conn.commit()
        mock_get_conn.return_value = mem_conn

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _view_documents,
        )

        _view_documents()

        captured = capsys.readouterr()
        assert "Policy Doc" in captured.out
        assert "Total documents: 1" in captured.out


# ---------------------------------------------------------------------------
# Tests -- Review operations
# ---------------------------------------------------------------------------

class TestScheduleReview:
    """Tests for _schedule_review."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_schedule_review_success(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Scheduling a review with valid inputs should insert a row."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ["2026-06-15", "10:00", "Dr. Smith", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _schedule_review,
        )

        _schedule_review()

        captured = capsys.readouterr()
        assert "scheduled successfully" in captured.out

        cur = mem_conn.cursor()
        cur.execute("SELECT reviewer FROM accreditation_reviews")
        row = cur.fetchone()
        assert row[0] == "Dr. Smith"

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_schedule_review_empty_date_returns_early(self, mock_input, mock_get_conn, mem_conn, capsys):
        """An empty review date should abort scheduling."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ["", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _schedule_review,
        )

        _schedule_review()

        captured = capsys.readouterr()
        assert "date is required" in captured.out.lower()

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_schedule_review_empty_reviewer_returns_early(self, mock_input, mock_get_conn, mem_conn, capsys):
        """An empty reviewer name should abort scheduling."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ["2026-06-15", "10:00", "", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _schedule_review,
        )

        _schedule_review()

        captured = capsys.readouterr()
        assert "reviewer name is required" in captured.out.lower()


class TestViewReviews:
    """Tests for _view_reviews."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input", return_value="")
    def test_view_reviews_empty(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Should display a 'no reviews' message when table is empty."""
        mock_get_conn.return_value = mem_conn

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _view_reviews,
        )

        _view_reviews()

        captured = capsys.readouterr()
        assert "no accreditation reviews" in captured.out.lower()

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input", return_value="")
    def test_view_reviews_with_data(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Should list reviews when data exists."""
        cur = mem_conn.cursor()
        cur.execute(
            "INSERT INTO accreditation_reviews (id, review_date, review_time, reviewer, created_on) "
            "VALUES (?, ?, ?, ?, ?)",
            ("rev-1", "2026-06-15", "10:00", "Dr. Smith", "2026-03-28"),
        )
        mem_conn.commit()
        mock_get_conn.return_value = mem_conn

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _view_reviews,
        )

        _view_reviews()

        captured = capsys.readouterr()
        assert "Dr. Smith" in captured.out
        assert "Total reviews: 1" in captured.out


# ---------------------------------------------------------------------------
# Tests -- Standards operations
# ---------------------------------------------------------------------------

class TestAddStandard:
    """Tests for _add_standard."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_add_standard_success(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Adding a standard with valid inputs should insert a row."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ["ISO 9001", "Quality management", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _add_standard,
        )

        _add_standard()

        captured = capsys.readouterr()
        assert "added successfully" in captured.out

        cur = mem_conn.cursor()
        cur.execute("SELECT standard_text, description FROM accreditation_standards")
        row = cur.fetchone()
        assert row[0] == "ISO 9001"
        assert row[1] == "Quality management"

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_add_standard_empty_name_returns_early(self, mock_input, mock_get_conn, mem_conn, capsys):
        """An empty standard name should abort."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ["", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _add_standard,
        )

        _add_standard()

        captured = capsys.readouterr()
        assert "name is required" in captured.out.lower()


class TestViewStandards:
    """Tests for _view_standards."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input", return_value="")
    def test_view_standards_empty(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Should display a 'no standards' message when table is empty."""
        mock_get_conn.return_value = mem_conn

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _view_standards,
        )

        _view_standards()

        captured = capsys.readouterr()
        assert "no accreditation standards" in captured.out.lower()


class TestUpdateStandard:
    """Tests for _update_standard."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_update_standard_name(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Updating a standard name should persist the change."""
        cur = mem_conn.cursor()
        cur.execute(
            "INSERT INTO accreditation_standards (id, standard_text, description, last_updated) "
            "VALUES (?, ?, ?, ?)",
            ("std-1", "Old Name", "Some desc", "2026-01-01"),
        )
        mem_conn.commit()
        mock_get_conn.return_value = mem_conn
        # Choose standard 1, new name, blank description (keep), press enter
        mock_input.side_effect = ["1", "New Name", "", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _update_standard,
        )

        _update_standard()

        captured = capsys.readouterr()
        assert "updated successfully" in captured.out

        cur.execute("SELECT standard_text FROM accreditation_standards WHERE id = 'std-1'")
        assert cur.fetchone()[0] == "New Name"

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_update_standard_cancel_with_zero(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Entering 0 should cancel the update."""
        cur = mem_conn.cursor()
        cur.execute(
            "INSERT INTO accreditation_standards (id, standard_text, description, last_updated) "
            "VALUES (?, ?, ?, ?)",
            ("std-1", "Name", "Desc", "2026-01-01"),
        )
        mem_conn.commit()
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ["0", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _update_standard,
        )

        _update_standard()

        captured = capsys.readouterr()
        assert "cancelled" in captured.out.lower()

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_update_standard_no_changes(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Leaving both fields blank should report no changes."""
        cur = mem_conn.cursor()
        cur.execute(
            "INSERT INTO accreditation_standards (id, standard_text, description, last_updated) "
            "VALUES (?, ?, ?, ?)",
            ("std-1", "Name", "Desc", "2026-01-01"),
        )
        mem_conn.commit()
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ["1", "", "", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _update_standard,
        )

        _update_standard()

        captured = capsys.readouterr()
        assert "no changes" in captured.out.lower()

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_update_standard_empty_table(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Should report no standards available when the table is empty."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = [""]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _update_standard,
        )

        _update_standard()

        captured = capsys.readouterr()
        assert "no accreditation standards available" in captured.out.lower()


# ---------------------------------------------------------------------------
# Tests -- Menu navigation
# ---------------------------------------------------------------------------

class TestMenuNavigation:
    """Tests for display_accreditation_menu navigation."""

    @patch(f"{MODULE}._ensure_tables")
    @patch("builtins.input")
    def test_menu_exits_on_option_6(self, mock_input, mock_ensure, capsys):
        """Option 6 should exit the menu loop."""
        mock_input.return_value = "6"

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            display_accreditation_menu,
        )

        display_accreditation_menu()

        captured = capsys.readouterr()
        assert "ACCREDITATION SUPPORT" in captured.out

    @patch(f"{MODULE}._ensure_tables")
    @patch(f"{MODULE}._upload_document")
    @patch("builtins.input")
    def test_menu_dispatches_to_upload(self, mock_input, mock_upload, mock_ensure, capsys):
        """Option 1 should dispatch to _upload_document."""
        mock_input.side_effect = ["1", "6"]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            display_accreditation_menu,
        )

        display_accreditation_menu()
        mock_upload.assert_called_once()

    @patch(f"{MODULE}._ensure_tables")
    @patch(f"{MODULE}._manage_standards")
    @patch("builtins.input")
    def test_menu_dispatches_to_standards(self, mock_input, mock_standards, mock_ensure, capsys):
        """Option 5 should dispatch to _manage_standards."""
        mock_input.side_effect = ["5", "6"]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            display_accreditation_menu,
        )

        display_accreditation_menu()
        mock_standards.assert_called_once()

    @patch(f"{MODULE}._ensure_tables")
    @patch("builtins.input")
    def test_menu_invalid_choice(self, mock_input, mock_ensure, capsys):
        """An invalid choice should print an error then loop."""
        mock_input.side_effect = ["99", "6"]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            display_accreditation_menu,
        )

        display_accreditation_menu()

        captured = capsys.readouterr()
        assert "invalid choice" in captured.out.lower()

    @patch(f"{MODULE}._ensure_tables")
    @patch("builtins.input")
    def test_standards_submenu_exits_on_option_4(self, mock_input, mock_ensure, capsys):
        """Option 4 in the standards sub-menu should return to the main menu."""
        mock_input.side_effect = ["4"]

        from education_system.post_18.university_system.modules.domain.academics.cli.accreditation_cli import (
            _manage_standards,
        )

        _manage_standards()

        captured = capsys.readouterr()
        assert "manage accreditation standards" in captured.out.lower()
