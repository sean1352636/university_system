"""Tests for DatabaseManager in finance GUI"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3
import sys

# Mock matplotlib and tkinter before importing the module
sys.modules['matplotlib'] = MagicMock()
sys.modules['matplotlib.pyplot'] = MagicMock()
sys.modules['matplotlib.backends'] = MagicMock()
sys.modules['matplotlib.backends.backend_tkagg'] = MagicMock()
sys.modules['seaborn'] = MagicMock()
# NOTE: Do NOT mock tkinter — it poisons sys.modules globally

# Try to import, skip tests if it still fails
try:
    from education_system.university_system.modules.domain.finance.gui.finance.db_manager import DatabaseManager
    IMPORT_SUCCESS = True
except ImportError as e:
    IMPORT_SUCCESS = False
    DatabaseManager = None

pytestmark = pytest.mark.skipif(not IMPORT_SUCCESS, reason="Finance GUI modules not available in headless environment")

class MockGUI:
    """Mock GUI for testing"""
    def __init__(self):
        self.root = Mock()  # Mock Tk root to avoid display issues
        self.conn = None
        self.finance_system = None

@pytest.fixture
def mock_gui():
    """Create mock GUI"""
    gui = MockGUI()
    yield gui

@pytest.fixture
def db_manager(mock_gui):
    """Create DatabaseManager instance"""
    return DatabaseManager(mock_gui)

class TestDatabaseManagerInit:
    """Test DatabaseManager initialization"""

    def test_init_with_valid_gui(self, mock_gui):
        """Test initialization with valid GUI"""
        manager = DatabaseManager(mock_gui)
        assert manager.gui == mock_gui
        assert manager.root == mock_gui.root
        assert manager.conn == mock_gui.conn

    def test_init_with_finance_system(self, mock_gui):
        """Test initialization when finance_system exists"""
        mock_gui.finance_system = Mock()
        manager = DatabaseManager(mock_gui)
        assert manager.finance_system == mock_gui.finance_system

    def test_init_without_finance_system(self, mock_gui):
        """Test initialization when finance_system doesn't exist"""
        delattr(mock_gui, 'finance_system')
        manager = DatabaseManager(mock_gui)
        assert manager.finance_system is None

class TestDatabaseInitialization:
    """Test database initialization methods"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_initialize_database_success(self, mock_msgbox, db_manager):
        """Test successful database initialization"""
        with patch.object(db_manager, 'initialize_database_schema'):
            db_manager.initialize_database()
            db_manager.initialize_database_schema.assert_called_once()
            mock_msgbox.showinfo.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_initialize_database_error(self, mock_msgbox, db_manager):
        """Test database initialization with error"""
        with patch.object(db_manager, 'initialize_database_schema', side_effect=Exception("Test error")):
            db_manager.initialize_database()
            mock_msgbox.showerror.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.get_connection')
    def test_initialize_database_schema(self, mock_get_conn, db_manager):
        """Test database schema initialization"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock empty fee_types table
        mock_cursor.fetchone.return_value = (0,)

        db_manager.initialize_database_schema()

        # Verify tables were created
        assert mock_cursor.execute.call_count > 0
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.get_connection')
    def test_ensure_db_compatibility(self, mock_get_conn, db_manager):
        """Test database compatibility check"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock table info with missing column
        mock_cursor.fetchall.return_value = [(0, 'id'), (1, 'name')]

        db_manager.ensure_db_compatibility()

        mock_conn.commit.assert_called()
        mock_conn.close.assert_called_once()

class TestDatabaseCleaning:
    """Test database cleaning operations"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_clean_database_cancelled(self, mock_msgbox, db_manager):
        """Test database cleaning cancelled by user"""
        mock_msgbox.askyesno.return_value = False
        db_manager.clean_database()
        mock_msgbox.askyesno.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_clean_database_success(self, mock_msgbox, mock_get_conn, db_manager):
        """Test successful database cleaning"""
        mock_msgbox.askyesno.return_value = True

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock deleted rows
        mock_cursor.rowcount = 10

        db_manager.clean_database()

        # Verify cleaning operations
        assert mock_cursor.execute.call_count > 0
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()
        mock_msgbox.showinfo.assert_called_once()

class TestDatabaseBackup:
    """Test database backup operations"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.filedialog')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.os.path.exists')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.paths')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_backup_database_no_db_file(self, mock_msgbox, mock_paths, mock_exists, mock_filedialog, db_manager):
        """Test backup when database file doesn't exist"""
        mock_paths.DEFAULT_DB_PATH = '/test/db.db'
        mock_exists.return_value = False

        db_manager.backup_database()

        mock_msgbox.showerror.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.shutil.copy2')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.filedialog')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.os.path')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.paths')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_backup_database_success(self, mock_msgbox, mock_paths, mock_os_path,
                                     mock_filedialog, mock_copy, db_manager):
        """Test successful database backup"""
        mock_paths.DEFAULT_DB_PATH = '/test/db.db'
        mock_os_path.exists.return_value = True
        mock_os_path.getsize.return_value = 1024 * 1024  # 1MB
        mock_filedialog.asksaveasfilename.return_value = '/backup/test.db'

        db_manager.backup_database()

        mock_copy.assert_called_once()
        mock_msgbox.showinfo.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.filedialog')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.os.path.exists')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.paths')
    def test_backup_database_cancelled(self, mock_paths, mock_exists, mock_filedialog, db_manager):
        """Test backup cancelled by user"""
        mock_paths.DEFAULT_DB_PATH = '/test/db.db'
        mock_exists.return_value = True
        mock_filedialog.asksaveasfilename.return_value = ''

        db_manager.backup_database()

        # Should return without error

class TestDatabaseStats:
    """Test database statistics display"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.get_connection')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.os.path')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.paths')
    def test_show_database_stats(self, mock_paths, mock_os_path, mock_get_conn, db_manager):
        """Test showing database statistics"""
        mock_paths.DEFAULT_DB_PATH = '/test/db.db'
        mock_os_path.exists.return_value = True
        mock_os_path.getsize.return_value = 2048 * 1024  # 2MB
        mock_os_path.getmtime.return_value = datetime.now().timestamp()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock table counts
        mock_cursor.fetchone.side_effect = [(100,), (50,), (75,), (10,), (5,), (3,), (20,), (10,)]

        db_manager.show_database_stats()

        mock_conn.close.assert_called_once()

class TestDatabaseFix:
    """Test database fix operations"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_gui_complete_database_fix_cancelled(self, mock_msgbox, db_manager):
        """Test complete database fix cancelled"""
        mock_msgbox.askyesno.return_value = False
        db_manager.gui_complete_database_fix()
        mock_msgbox.askyesno.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.threading.Thread')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_gui_complete_database_fix_confirmed(self, mock_msgbox, mock_thread, db_manager):
        """Test complete database fix confirmed"""
        mock_msgbox.askyesno.return_value = True
        db_manager.update_status = Mock()

        db_manager.gui_complete_database_fix()

        mock_msgbox.askyesno.assert_called_once()
        mock_thread.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_gui_quick_fix_database_cancelled(self, mock_msgbox, db_manager):
        """Test quick database fix cancelled"""
        mock_msgbox.askyesno.return_value = False
        db_manager.gui_quick_fix_database()
        mock_msgbox.askyesno.assert_called_once()

class TestHelperMethods:
    """Test helper methods"""

    def test_update_status_with_method(self, db_manager):
        """Test update_status when gui has the method"""
        db_manager.gui.update_status = Mock()
        db_manager.update_status("Test message")
        db_manager.gui.update_status.assert_called_once_with("Test message")

    def test_update_status_without_method(self, db_manager, capsys):
        """Test update_status when gui doesn't have the method"""
        db_manager.update_status("Test message")
        captured = capsys.readouterr()
        assert "Status: Test message" in captured.out

    def test_update_system_status_with_method(self, db_manager):
        """Test update_system_status when gui has the method"""
        db_manager.gui.update_system_status = Mock()
        db_manager.update_system_status()
        db_manager.gui.update_system_status.assert_called_once()

    def test_show_text_window(self, db_manager):
        """Test showing text window"""
        # Just verify it doesn't crash
        try:
            db_manager.show_text_window("Test Title", "Test Content")
            # If we get here, window was created successfully
        except Exception as e:
            pytest.fail(f"show_text_window raised exception: {e}")

class TestDatabaseVerification:
    """Test database verification operations"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.ensure_database_exists')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_gui_ensure_database_exists_success(self, mock_msgbox, mock_ensure, db_manager):
        """Test successful database existence verification"""
        db_manager.update_status = Mock()
        db_manager.gui_ensure_database_exists()

        mock_ensure.assert_called_once()
        mock_msgbox.showinfo.assert_called_once()
        db_manager.update_status.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.ensure_database_exists')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_gui_ensure_database_exists_error(self, mock_msgbox, mock_ensure, db_manager):
        """Test database existence verification with error"""
        mock_ensure.side_effect = Exception("Test error")
        db_manager.update_status = Mock()

        db_manager.gui_ensure_database_exists()

        mock_msgbox.showerror.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.verify_fix')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.db_manager.messagebox')
    def test_gui_verify_fix(self, mock_msgbox, mock_verify, db_manager):
        """Test database fix verification"""
        db_manager.update_status = Mock()
        db_manager.show_text_window = Mock()

        db_manager.gui_verify_fix()

        mock_verify.assert_called_once()
        db_manager.show_text_window.assert_called_once()
        db_manager.update_status.assert_called_once()
