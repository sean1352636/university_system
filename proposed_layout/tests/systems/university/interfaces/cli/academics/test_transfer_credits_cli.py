"""
Tests for the Transfer Credits CLI menu.

Tests cover table creation, CRUD operations, search, approve/reject,
report generation, menu navigation, and auth guard behaviour.
"""

import pytest
import sqlite3
from unittest.mock import Mock, patch, call

MODULE_PATH = (
    "education_system.systems.university.interfaces.cli.academics.transfer_credits_cli"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_table_flag():
    """Reset the module-level _TABLE_INITIALISED flag before each test."""
    import education_system.systems.university.interfaces.cli.academics.transfer_credits_cli as mod
    mod._TABLE_INITIALISED = False
    yield
    mod._TABLE_INITIALISED = False


@pytest.fixture
def mock_auth():
    """Create a mock authentication object with an admin user."""
    auth = Mock()
    auth.current_user = {
        'id': 1,
        'user_id': 1,
        'username': 'admin_user',
        'role': 'admin',
        'display_name': 'Admin User',
    }
    auth.is_logged_in.return_value = True
    return auth


@pytest.fixture
def mock_auth_student():
    """Create a mock authentication object with a student user."""
    auth = Mock()
    auth.current_user = {
        'id': 10,
        'user_id': 10,
        'username': 'stu_jane',
        'role': 'student',
        'display_name': 'Jane Doe',
        'student_id': 'STU0010',
    }
    auth.is_logged_in.return_value = True
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
    """Create an in-memory SQLite connection with the transfer_credits table."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transfer_credits (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            institution TEXT,
            course_name TEXT,
            grade TEXT,
            credits REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            date_requested TEXT NOT NULL,
            date_approved TEXT,
            approved_by TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    wrapper = _NoCloseConn(conn)
    yield wrapper
    conn.close()


def _insert_record(conn, record_id='rec-001', student_id='STU0010',
                    institution='MIT', course_name='Intro CS',
                    grade='A', credits=3.0, status='Pending',
                    date_requested='2026-01-15', notes=None):
    """Insert a transfer credit record into the in-memory DB."""
    conn.execute(
        "INSERT INTO transfer_credits "
        "(id, student_id, institution, course_name, grade, credits, "
        "status, date_requested, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (record_id, student_id, institution, course_name, grade,
         credits, status, date_requested, notes),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests -- Table creation
# ---------------------------------------------------------------------------

class TestEnsureTable:
    """Tests for _ensure_table."""

    @patch(f'{MODULE_PATH}.get_connection')
    def test_ensure_table_creates_table(self, mock_get_conn):
        """_ensure_table should execute CREATE TABLE and set the flag."""
        real_conn = sqlite3.connect(':memory:')
        real_conn.row_factory = sqlite3.Row
        mock_get_conn.return_value = _NoCloseConn(real_conn)

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _ensure_table,
        )

        _ensure_table()

        # Table should exist
        rows = real_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='transfer_credits'"
        ).fetchall()
        assert len(rows) == 1
        real_conn.close()

    @patch(f'{MODULE_PATH}.get_connection')
    def test_ensure_table_skips_when_already_initialised(self, mock_get_conn):
        """_ensure_table should be a no-op when the flag is already set."""
        import education_system.systems.university.interfaces.cli.academics.transfer_credits_cli as mod
        mod._TABLE_INITIALISED = True

        mod._ensure_table()

        mock_get_conn.assert_not_called()


# ---------------------------------------------------------------------------
# Tests -- Add transfer credit
# ---------------------------------------------------------------------------

class TestAddTransferCredit:
    """Tests for _add_transfer_credit."""

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_add_transfer_credit_success(self, mock_input, mock_get_conn, mem_conn):
        """Adding a valid transfer credit should insert a row."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = [
            'STU0010',          # Student ID
            'MIT',              # Institution
            'Intro CS',         # Course Name
            'A',                # Grade
            '3.0',              # Credits
            'Transfer from MIT',  # Notes
            '',                 # Press Enter to continue
        ]

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _add_transfer_credit,
        )

        _add_transfer_credit()

        rows = mem_conn.execute("SELECT * FROM transfer_credits").fetchall()
        assert len(rows) == 1
        assert rows[0]['student_id'] == 'STU0010'
        assert rows[0]['institution'] == 'MIT'
        assert rows[0]['status'] == 'Pending'

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_add_transfer_credit_empty_student_id(self, mock_input, mock_get_conn,
                                                   mem_conn, capsys):
        """An empty student ID should abort the add operation."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['', '']  # empty student_id, press enter

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _add_transfer_credit,
        )

        _add_transfer_credit()

        captured = capsys.readouterr()
        assert 'Student ID is required' in captured.out

        rows = mem_conn.execute("SELECT * FROM transfer_credits").fetchall()
        assert len(rows) == 0

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_add_transfer_credit_invalid_credits(self, mock_input, mock_get_conn,
                                                  mem_conn, capsys):
        """Non-numeric or negative credits should abort."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = [
            'STU0010', 'MIT', 'Intro CS', 'A',
            'abc',  # invalid credits
            '',     # press enter
        ]

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _add_transfer_credit,
        )

        _add_transfer_credit()

        captured = capsys.readouterr()
        assert 'Invalid credits' in captured.out

        rows = mem_conn.execute("SELECT * FROM transfer_credits").fetchall()
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Tests -- View transfer credits
# ---------------------------------------------------------------------------

class TestViewTransferCredits:
    """Tests for _view_transfer_credits."""

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_view_all_transfer_credits(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Viewing with blank filter should show all records."""
        _insert_record(mem_conn, record_id='rec-001', student_id='STU0010')
        _insert_record(mem_conn, record_id='rec-002', student_id='STU0020',
                        institution='Stanford', course_name='Data Science')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['', '']  # no filter, press enter

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _view_transfer_credits,
        )

        _view_transfer_credits()

        captured = capsys.readouterr()
        assert 'STU0010' in captured.out
        assert 'STU0020' in captured.out

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_view_transfer_credits_filtered_by_student(self, mock_input, mock_get_conn,
                                                        mem_conn, capsys):
        """Filtering by student ID should only show that student's records."""
        _insert_record(mem_conn, record_id='rec-001', student_id='STU0010')
        _insert_record(mem_conn, record_id='rec-002', student_id='STU0020')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['STU0010', '']  # filter by STU0010, press enter

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _view_transfer_credits,
        )

        _view_transfer_credits()

        captured = capsys.readouterr()
        assert 'STU0010' in captured.out
        assert 'STU0020' not in captured.out

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_view_transfer_credits_empty(self, mock_input, mock_get_conn,
                                          mem_conn, capsys):
        """Viewing when no records exist should show a 'not found' message."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['', '']

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _view_transfer_credits,
        )

        _view_transfer_credits()

        captured = capsys.readouterr()
        assert 'No transfer credit records found' in captured.out


# ---------------------------------------------------------------------------
# Tests -- Search transfer credits
# ---------------------------------------------------------------------------

class TestSearchTransferCredits:
    """Tests for _search_transfer_credits."""

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_search_by_student_id(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Searching by student ID should return matching records."""
        _insert_record(mem_conn, record_id='rec-001', student_id='STU0010')
        _insert_record(mem_conn, record_id='rec-002', student_id='STU0020')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['1', 'STU0010', '']  # option 1, search term, enter

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _search_transfer_credits,
        )

        _search_transfer_credits()

        captured = capsys.readouterr()
        assert 'STU0010' in captured.out

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_search_by_institution(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Searching by institution should return matching records."""
        _insert_record(mem_conn, record_id='rec-001', institution='MIT')
        _insert_record(mem_conn, record_id='rec-002', institution='Stanford')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['2', 'Stanford', '']

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _search_transfer_credits,
        )

        _search_transfer_credits()

        captured = capsys.readouterr()
        assert 'Stanford' in captured.out

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_search_invalid_choice(self, mock_input, mock_get_conn, mem_conn, capsys):
        """An invalid search choice should show an error."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['9', '']

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _search_transfer_credits,
        )

        _search_transfer_credits()

        captured = capsys.readouterr()
        assert 'Invalid choice' in captured.out


# ---------------------------------------------------------------------------
# Tests -- Approve transfer credit
# ---------------------------------------------------------------------------

class TestApproveTransferCredit:
    """Tests for _approve_transfer_credits."""

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_approve_pending_record(self, mock_input, mock_get_conn, mem_conn,
                                     mock_auth, capsys):
        """Approving a pending record should set status to 'Approved'."""
        _insert_record(mem_conn, record_id='rec-001', status='Pending')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['1', '']  # select record 1, press enter

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _approve_transfer_credits,
        )

        _approve_transfer_credits(mock_auth)

        row = mem_conn.execute(
            "SELECT * FROM transfer_credits WHERE id = 'rec-001'"
        ).fetchone()
        assert row['status'] == 'Approved'
        assert row['approved_by'] == 'admin_user'

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_approve_no_pending_records(self, mock_input, mock_get_conn, mem_conn,
                                         mock_auth, capsys):
        """When no pending records exist, show an appropriate message."""
        _insert_record(mem_conn, record_id='rec-001', status='Approved')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['']

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _approve_transfer_credits,
        )

        _approve_transfer_credits(mock_auth)

        captured = capsys.readouterr()
        assert 'No pending' in captured.out

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_approve_cancel(self, mock_input, mock_get_conn, mem_conn,
                             mock_auth, capsys):
        """Entering 0 should cancel approval."""
        _insert_record(mem_conn, record_id='rec-001', status='Pending')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['0', '']

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _approve_transfer_credits,
        )

        _approve_transfer_credits(mock_auth)

        row = mem_conn.execute(
            "SELECT * FROM transfer_credits WHERE id = 'rec-001'"
        ).fetchone()
        assert row['status'] == 'Pending'

        captured = capsys.readouterr()
        assert 'cancelled' in captured.out.lower()


# ---------------------------------------------------------------------------
# Tests -- Reject transfer credit
# ---------------------------------------------------------------------------

class TestRejectTransferCredit:
    """Tests for _reject_transfer_credits."""

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_reject_pending_record(self, mock_input, mock_get_conn, mem_conn,
                                    mock_auth, capsys):
        """Rejecting a pending record should set status to 'Rejected'."""
        _insert_record(mem_conn, record_id='rec-001', status='Pending')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['1', 'Not equivalent', '']  # select 1, reason, enter

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _reject_transfer_credits,
        )

        _reject_transfer_credits(mock_auth)

        row = mem_conn.execute(
            "SELECT * FROM transfer_credits WHERE id = 'rec-001'"
        ).fetchone()
        assert row['status'] == 'Rejected'
        assert row['approved_by'] == 'admin_user'

        captured = capsys.readouterr()
        assert 'rejected' in captured.out.lower()


# ---------------------------------------------------------------------------
# Tests -- Delete transfer credit
# ---------------------------------------------------------------------------

class TestDeleteTransferCredit:
    """Tests for _delete_transfer_credit."""

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_delete_record_confirmed(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Confirming deletion should remove the record."""
        _insert_record(mem_conn, record_id='rec-001')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['rec-001', 'yes', '']  # id, confirm, enter

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _delete_transfer_credit,
        )

        _delete_transfer_credit()

        rows = mem_conn.execute("SELECT * FROM transfer_credits").fetchall()
        assert len(rows) == 0

        captured = capsys.readouterr()
        assert 'deleted successfully' in captured.out.lower()

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_delete_record_cancelled(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Declining deletion should keep the record."""
        _insert_record(mem_conn, record_id='rec-001')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['rec-001', 'no', '']  # id, decline, enter

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _delete_transfer_credit,
        )

        _delete_transfer_credit()

        rows = mem_conn.execute("SELECT * FROM transfer_credits").fetchall()
        assert len(rows) == 1

        captured = capsys.readouterr()
        assert 'cancelled' in captured.out.lower()

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_delete_record_not_found(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Deleting a non-existent record should show a not-found message."""
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['nonexistent-id', '']

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _delete_transfer_credit,
        )

        _delete_transfer_credit()

        captured = capsys.readouterr()
        assert 'No transfer credit record found' in captured.out


# ---------------------------------------------------------------------------
# Tests -- Generate report
# ---------------------------------------------------------------------------

class TestGenerateReport:
    """Tests for _generate_transfer_credit_report."""

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_report_shows_approved_credits(self, mock_input, mock_get_conn,
                                            mem_conn, capsys):
        """Report should display approved records with totals."""
        _insert_record(mem_conn, record_id='rec-001', credits=3.0, status='Approved')
        _insert_record(mem_conn, record_id='rec-002', credits=4.0, status='Approved',
                        student_id='STU0020')
        _insert_record(mem_conn, record_id='rec-003', credits=2.0, status='Pending')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['', '']  # all students, press enter

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _generate_transfer_credit_report,
        )

        _generate_transfer_credit_report()

        captured = capsys.readouterr()
        assert '7.0' in captured.out  # total of approved credits
        assert '2' in captured.out    # number of approved records

    @patch(f'{MODULE_PATH}.get_connection')
    @patch('builtins.input')
    def test_report_no_approved_records(self, mock_input, mock_get_conn,
                                         mem_conn, capsys):
        """Report with no approved records should say so."""
        _insert_record(mem_conn, record_id='rec-001', status='Pending')
        mock_get_conn.return_value = mem_conn
        mock_input.side_effect = ['', '']

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            _generate_transfer_credit_report,
        )

        _generate_transfer_credit_report()

        captured = capsys.readouterr()
        assert 'No approved transfer credits' in captured.out


# ---------------------------------------------------------------------------
# Tests -- Menu navigation
# ---------------------------------------------------------------------------

class TestMenuNavigation:
    """Tests for display_transfer_credits_menu navigation."""

    @patch(f'{MODULE_PATH}._ensure_table')
    @patch('builtins.input')
    def test_menu_return_exits(self, mock_input, mock_ensure, mock_auth, capsys):
        """Choosing the return option should exit the menu loop."""
        # For admin: options 1-7, where 8 is return
        mock_input.side_effect = ['8']

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            display_transfer_credits_menu,
        )

        display_transfer_credits_menu(auth=mock_auth)

        captured = capsys.readouterr()
        assert 'TRANSFER CREDITS MANAGEMENT' in captured.out

    @patch(f'{MODULE_PATH}._ensure_table')
    @patch('builtins.input')
    def test_menu_invalid_choice(self, mock_input, mock_ensure, mock_auth, capsys):
        """An invalid choice should print an error and loop back."""
        mock_input.side_effect = ['99', '8']  # invalid, then return

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            display_transfer_credits_menu,
        )

        display_transfer_credits_menu(auth=mock_auth)

        captured = capsys.readouterr()
        assert 'Invalid choice' in captured.out

    @patch(f'{MODULE_PATH}._ensure_table')
    @patch('builtins.input')
    def test_student_menu_has_fewer_options(self, mock_input, mock_ensure,
                                             mock_auth_student, capsys):
        """Students should not see approve/reject/delete options."""
        # For student: options 1-4 (add, view, search, report, return=5)
        mock_input.side_effect = ['5']

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            display_transfer_credits_menu,
        )

        display_transfer_credits_menu(auth=mock_auth_student)

        captured = capsys.readouterr()
        assert 'Approve' not in captured.out
        assert 'Reject' not in captured.out
        assert 'Delete' not in captured.out


# ---------------------------------------------------------------------------
# Tests -- Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    """Tests for auth guard behaviour."""

    @patch(f'{MODULE_PATH}._ensure_table')
    @patch('builtins.input', return_value='')
    def test_no_auth_returns_early(self, mock_input, mock_ensure, capsys):
        """Passing None auth should print a login message and return."""
        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            display_transfer_credits_menu,
        )

        display_transfer_credits_menu(auth=None)

        captured = capsys.readouterr()
        assert 'Please log in' in captured.out

    @patch(f'{MODULE_PATH}._ensure_table')
    @patch('builtins.input', return_value='')
    def test_no_current_user_returns_early(self, mock_input, mock_ensure, capsys):
        """An auth object with no current_user should print a login message."""
        auth = Mock()
        auth.current_user = None

        from education_system.systems.university.interfaces.cli.academics.transfer_credits_cli import (
            display_transfer_credits_menu,
        )

        display_transfer_credits_menu(auth=auth)

        captured = capsys.readouterr()
        assert 'Please log in' in captured.out
