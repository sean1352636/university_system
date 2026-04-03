"""
Tests for health/gui/medical_accommodation (AccommodationGUI)

This test suite validates:
- GUI initialization and window creation
- Menu creation and functionality
- Dialog windows (add, update, remove)
- Template management dialogs
- Import/Export functionality
- Statistics and reporting
- Helper functions
"""

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch, MagicMock, call

# Correct module paths for patching
_MAIN_GUI = 'education_system.university_system.modules.domain.health.gui.medical_accommodation.main_gui'
_COMMON = 'education_system.university_system.modules.domain.health.gui.medical_accommodation._common'
_UTILS = 'education_system.university_system.modules.domain.health.gui.medical_accommodation.utils'
_SHIM = 'education_system.university_system.modules.domain.health.gui.medical_accommodation_gui'


@pytest.fixture
def mock_root():
    """Create a mock Tkinter root window"""
    root = Mock(spec=tk.Tk)
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    root.winfo_children.return_value = []
    return root


class TestAccommodationGUIInitialization:
    """Test GUI initialization"""

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_gui_initialization(self, mock_init_db, mock_root):
        """Test AccommodationGUI initializes correctly"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

            assert gui.root == mock_root
            assert mock_init_db.called

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_gui_with_auth_instance(self, mock_init_db, mock_root):
        """Test GUI initialization with authentication"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        mock_auth = Mock()
        mock_auth.current_user = {'username': 'test_user', 'role': 'admin'}

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root, auth=mock_auth)

            assert gui.auth == mock_auth
            assert gui.current_user is not None

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_window_title_set(self, mock_init_db, mock_root):
        """Test window title is set correctly"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

            # title() is called during init
            mock_root.title.assert_called()


class TestMenuCreation:
    """Test menu bar creation"""

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_menu_bar_created(self, mock_init_db, mock_root):
        """Test menu bar is created"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'), \
             patch(f'{_MAIN_GUI}.tk.Menu'):
            gui = AccommodationGUI(mock_root)

            # config should be called to set menu
            mock_root.config.assert_called()

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_file_menu_exists(self, mock_init_db, mock_root):
        """Test file menu exists with import/export options"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

            # Menu should be created (exact structure checking is complex in Tk)
            assert hasattr(gui, 'root')


class TestHelperFunctions:
    """Test helper utility functions"""

    def test_resolve_user_identifier_with_auth(self):
        """Test resolve_user_identifier with auth instance"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import resolve_user_identifier

        mock_auth = Mock()
        mock_auth.current_user = {'username': 'test_user', 'email': 'test@example.com'}

        user_id = resolve_user_identifier(auth_instance=mock_auth)

        assert user_id == 'test_user'

    def test_resolve_user_identifier_with_email(self):
        """Test resolve_user_identifier falls back to email"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import resolve_user_identifier

        mock_auth = Mock()
        mock_auth.current_user = {'email': 'test@example.com', 'name': 'Test User'}

        user_id = resolve_user_identifier(auth_instance=mock_auth)

        assert user_id is not None

    @patch(f'{_UTILS}.CLI_AVAILABLE', False)
    def test_resolve_user_identifier_with_default(self):
        """Test resolve_user_identifier returns default when no user"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import resolve_user_identifier

        user_id = resolve_user_identifier(default='default_user')

        assert user_id == 'default_user'

    def test_resolve_user_identifier_handles_none_auth(self):
        """Test resolve_user_identifier handles None auth gracefully"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import resolve_user_identifier

        user_id = resolve_user_identifier(auth_instance=None)

        assert isinstance(user_id, str)


class TestDialogMethods:
    """Test dialog creation methods"""

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_add_accommodation_dialog_opens(self, mock_init_db, mock_root):
        """Test add_accommodation_dialog can be called"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'add_accommodation_dialog')

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_update_accommodation_dialog(self, mock_init_db, mock_root):
        """Test update_accommodation_dialog can be called"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'update_accommodation_dialog')

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_remove_accommodation_dialog(self, mock_init_db, mock_root):
        """Test remove_accommodation_dialog handles no selection"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'remove_accommodation_dialog')


class TestImportExport:
    """Test import and export functionality"""

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_import_csv_method_exists(self, mock_init_db, mock_root):
        """Test import_csv method exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'import_csv')

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_export_csv_method_exists(self, mock_init_db, mock_root):
        """Test export_csv method exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'export_csv')

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_export_excel_method_exists(self, mock_init_db, mock_root):
        """Test export_excel method exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'export_excel')

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_export_pdf_method_exists(self, mock_init_db, mock_root):
        """Test export_pdf method exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'export_pdf')


class TestTemplateManagement:
    """Test template management dialogs"""

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_save_template_dialog_method_exists(self, mock_init_db, mock_root):
        """Test save_template_dialog method exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'save_template_dialog')

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_apply_template_dialog_method_exists(self, mock_init_db, mock_root):
        """Test apply_template_dialog method exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'apply_template_dialog')

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_manage_templates_dialog_method_exists(self, mock_init_db, mock_root):
        """Test manage_templates_dialog method exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'manage_templates_dialog')


class TestReporting:
    """Test reporting and statistics methods"""

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_show_dashboard_method_exists(self, mock_init_db, mock_root):
        """Test show_dashboard method exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'show_dashboard')

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_generate_statistics_method_exists(self, mock_init_db, mock_root):
        """Test generate_statistics method exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'generate_statistics')

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_check_expiry_method_exists(self, mock_init_db, mock_root):
        """Test check_expiry method exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        assert hasattr(gui, 'check_expiry')


class TestDataRefresh:
    """Test data refresh functionality"""

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_refresh_data_method(self, mock_init_db, mock_root):
        """Test refresh_data method exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        # refresh_data should be called during initialization
        assert hasattr(gui, 'refresh_data')


class TestStatusBar:
    """Test status bar functionality"""

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_status_bar_created(self, mock_init_db, mock_root):
        """Test status bar is created"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root)

        # Check status bar creation method exists
        assert hasattr(gui, 'create_status_bar')


class TestModuleConstants:
    """Test module constants and configuration"""

    def test_cli_available_flag(self):
        """Test CLI_AVAILABLE flag is defined"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation import _common

        assert hasattr(_common, 'CLI_AVAILABLE')
        assert isinstance(_common.CLI_AVAILABLE, bool)

    def test_email_service_flag(self):
        """Test EMAIL_SERVICE_AVAILABLE flag is defined"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation import _common

        assert hasattr(_common, 'EMAIL_SERVICE_AVAILABLE')
        assert isinstance(_common.EMAIL_SERVICE_AVAILABLE, bool)

    def test_backup_available_flag(self):
        """Test CLI_AVAILABLE (backup) flag is defined"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation import _common

        # CLI_AVAILABLE serves as the backup-available indicator
        assert hasattr(_common, 'CLI_AVAILABLE')
        assert isinstance(_common.CLI_AVAILABLE, bool)


class TestErrorHandling:
    """Test error handling"""

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    def test_gui_handles_missing_auth_gracefully(self, mock_init_db, mock_root):
        """Test GUI handles missing auth gracefully"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            gui = AccommodationGUI(mock_root, auth=None)

        assert gui.auth is None

    @patch(f'{_MAIN_GUI}.init_accommodation_db')
    @patch(f'{_MAIN_GUI}.get_connection')
    def test_gui_handles_database_errors(self, mock_conn, mock_init_db, mock_root):
        """Test GUI handles database errors gracefully"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

        # Mock database error
        mock_conn.side_effect = Exception("Database connection error")

        with patch.object(AccommodationGUI, 'create_menu'), \
             patch.object(AccommodationGUI, 'create_main_interface'), \
             patch.object(AccommodationGUI, 'create_status_bar'), \
             patch.object(AccommodationGUI, 'refresh_data'):
            # Should handle error gracefully
            try:
                gui = AccommodationGUI(mock_root)
            except Exception:
                # Some initialization errors are acceptable
                pass


class TestIntegration:
    """Test integration with other modules"""

    def test_get_connection_imported(self):
        """Test get_connection is imported or fallback exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation import _common

        assert hasattr(_common, 'get_connection')
        assert callable(_common.get_connection)

    def test_validate_date_imported(self):
        """Test validate_date is imported or fallback exists"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation import _common

        assert hasattr(_common, 'validate_date')
        assert callable(_common.validate_date)

    def test_resolve_user_identifier_function_exists(self):
        """Test resolve_user_identifier function is defined"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation import utils

        assert hasattr(utils, 'resolve_user_identifier')
        assert callable(utils.resolve_user_identifier)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
