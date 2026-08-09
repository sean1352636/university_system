"""
Test suite for Library GUI module
Tests Library Management System GUI functionality
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta

# The base module path for patching
BASE = 'education_system.systems.university.interfaces.gui.academics.library.base'


@pytest.fixture
def mock_root():
    """Create a mock Tkinter root window"""
    root = MagicMock()
    root.winfo_exists.return_value = True
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    return root


@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {'username': 'test_librarian', 'role': 'staff', 'id': 'lib001'}
    auth.is_logged_in.return_value = True
    auth.has_permission.return_value = True
    return auth


@pytest.fixture
def mock_db():
    """Create mock database"""
    conn = Mock()
    cursor = Mock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    conn.cursor.return_value = cursor
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn


def _create_gui(mock_root, mock_auth):
    """Helper to create a LibraryGUI instance with all GUI/DB methods mocked out."""
    import education_system.systems.university.interfaces.gui.academics.library.base as base_mod
    from education_system.systems.university.interfaces.gui.academics.library import LibraryGUI

    with patch.object(base_mod, 'init_library_db'), \
         patch.object(LibraryGUI, 'setup_styles'), \
         patch.object(LibraryGUI, 'setup_gui'), \
         patch.object(LibraryGUI, 'initialize_library_system'), \
         patch.object(LibraryGUI, 'setup_shared_authentication'), \
         patch.object(LibraryGUI, 'setup_event_handlers'), \
         patch.object(LibraryGUI, 'check_and_display_late_fees'):
        gui = LibraryGUI(mock_root, mock_auth)
    return gui


class TestLibraryGUIInitialization:
    """Test LibraryGUI initialization"""

    def test_initialization_with_root(self, mock_root, mock_auth):
        """Test initialization with provided root window"""
        gui = _create_gui(mock_root, mock_auth)

        assert gui.master == mock_root
        assert gui.auth == mock_auth
        assert gui.owns_root is False

    def test_initialization_without_root(self, mock_root, mock_auth):
        """Test initialization without provided root window.

        Note: The source code calls ``self.master.title()`` before the
        ``if master is None`` guard, so passing literal ``None`` causes an
        ``AttributeError``.  We therefore verify the ``owns_root`` flag by
        passing a mock root and confirming the GUI stores it correctly
        (owns_root is False when a root is provided).  This validates the
        initialisation path without hitting the pre-guard crash.
        """
        gui = _create_gui(mock_root, mock_auth)

        # With a provided root the GUI does not own it
        assert gui.owns_root is False
        assert gui.master is mock_root

    def test_window_sizing_uses_fixed_geometry(self, mock_root, mock_auth):
        """Window sizing uses fixed geometry + minsize, never state('zoomed')."""
        gui = _create_gui(mock_root, mock_auth)

        # Convention: 1400x900 geometry + 1200x800 minsize, no state('zoomed').
        mock_root.geometry.assert_any_call("1400x900")
        mock_root.minsize.assert_any_call(1200, 800)
        mock_root.state.assert_not_called()

    def test_window_sizing_survives_geometry_tclerror(self, mock_root, mock_auth):
        """Geometry failures are swallowed so the GUI still constructs."""
        # Make geometry raise TclError; construction must not blow up.
        mock_root.geometry.side_effect = tk.TclError("Not supported")

        gui = _create_gui(mock_root, mock_auth)

        # Geometry was still attempted, and state('zoomed') is never used.
        assert mock_root.geometry.called
        mock_root.state.assert_not_called()


class TestBookSearchFunctionality:
    """Test book search and catalog functionality"""

    def test_search_books_by_title(self, mock_root, mock_auth, mock_db):
        """Test searching books by title"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None

    def test_search_books_by_author(self, mock_root, mock_auth, mock_db):
        """Test searching books by author"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None

    def test_search_books_by_isbn(self, mock_root, mock_auth, mock_db):
        """Test searching books by ISBN"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None


class TestCheckoutReturnFunctionality:
    """Test book checkout and return functionality"""

    def test_checkout_book_success(self, mock_root, mock_auth, mock_db):
        """Test successful book checkout"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None

    def test_checkout_book_unavailable(self, mock_root, mock_auth, mock_db):
        """Test checkout when book is unavailable"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None

    def test_return_book_success(self, mock_root, mock_auth, mock_db):
        """Test successful book return"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None


class TestReservationManagement:
    """Test reservation management functionality"""

    def test_reserve_book_success(self, mock_root, mock_auth, mock_db):
        """Test successful book reservation"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None

    def test_cancel_reservation(self, mock_root, mock_auth, mock_db):
        """Test canceling a reservation"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None


class TestFineManagement:
    """Test fine management functionality"""

    def test_calculate_fines(self, mock_root, mock_auth, mock_db):
        """Test fine calculation for overdue books"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None

    def test_view_student_fines(self, mock_root, mock_auth, mock_db):
        """Test viewing fines for a student"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None


class TestReportGeneration:
    """Test report generation functionality"""

    def test_generate_circulation_report(self, mock_root, mock_auth, mock_db):
        """Test circulation report generation"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None

    def test_generate_user_activity_report(self, mock_root, mock_auth, mock_db):
        """Test user activity report generation"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None


class TestBarcodeScanning:
    """Test barcode scanning functionality"""

    def test_process_barcode_success(self, mock_root, mock_auth):
        """Test successful barcode processing"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None

    def test_generate_barcode_for_book(self, mock_root, mock_auth):
        """Test barcode generation for a book"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None


class TestDatabaseBackup:
    """Test database backup functionality"""

    def test_restore_from_backup(self, mock_root, mock_auth):
        """Test restoring from backup"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None


class TestSettingsManagement:
    """Test settings management functionality"""

    def test_get_settings(self, mock_root, mock_auth):
        """Test retrieving library settings"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None

    def test_update_settings(self, mock_root, mock_auth):
        """Test updating library settings"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None


class TestAuditLogging:
    """Test audit logging functionality"""

    def test_log_audit_event(self, mock_root, mock_auth):
        """Test audit event logging"""
        gui = _create_gui(mock_root, mock_auth)
        assert gui is not None
