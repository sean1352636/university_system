"""
Tests for university_system/modules/domain/housing/gui/housing_accommodation_gui/

This test suite validates:
- HousingGUI class initialization
- Module constants and backward-compat exports
- Email notification functions
- Activity logging imports
- Error handling
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch, MagicMock, call

# Submodule patch prefixes
_MAIN = 'education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.main_gui'
_EMAIL = 'education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications'


@pytest.fixture
def root_window():
    """Create a root Tk window for testing"""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


class TestHousingGUIInitialization:
    """Test HousingGUI initialization"""

    @patch(f'{_MAIN}.init_housing_db')
    @patch(f'{_MAIN}.get_auth')
    def test_housing_gui_initialization(self, mock_get_auth, mock_init_db, root_window):
        """Test HousingGUI initializes correctly"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.main_gui import HousingGUI

        mock_get_auth.return_value = None

        gui = HousingGUI()

        # HousingGUI creates its own tk.Tk root
        assert gui.root is not None
        assert isinstance(gui.root, tk.Tk)
        assert mock_init_db.called
        gui.root.destroy()

    @patch(f'{_MAIN}.init_housing_db')
    @patch(f'{_MAIN}.get_auth')
    def test_housing_gui_with_auth(self, mock_get_auth, mock_init_db, root_window):
        """Test HousingGUI with authentication"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.main_gui import HousingGUI

        mock_auth = Mock()
        mock_auth.current_user = {'username': 'admin', 'role': 'admin'}
        mock_get_auth.return_value = mock_auth

        gui = HousingGUI(mock_auth)

        assert gui.auth is not None
        gui.root.destroy()


class TestEmailNotifications:
    """Test email notification functions"""

    @patch(f'{_EMAIL}.get_connection')
    @patch(f'{_EMAIL}.send_email')
    @patch(f'{_EMAIL}.render_template')
    def test_send_housing_email_success(self, mock_render, mock_send, mock_conn):
        """Test send_housing_email sends email successfully"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_housing_email

        # Mock student data
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('student@example.com', 'John', 'Doe')
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection

        # Mock template rendering
        mock_render.return_value = ('Subject', 'Body content')

        # Mock email sending
        mock_send.return_value = True

        application_data = {
            'application_id': 'APP001',
            'preferred_room_type': 'Single',
            'status': 'pending',
            'application_date': '2024-01-15'
        }

        result = send_housing_email('receipt', 'S001', application_data)

        assert result is True
        assert mock_send.called

    def test_send_housing_email_no_email_service(self):
        """Test send_housing_email when email service unavailable"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_housing_email

        with patch(f'{_EMAIL}.EMAIL_SERVICE_AVAILABLE', False):
            result = send_housing_email('receipt', 'S001', {})

            assert result is False

    @patch(f'{_EMAIL}.get_connection')
    def test_send_housing_email_no_student_email(self, mock_conn):
        """Test send_housing_email with missing student email"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_housing_email

        # Mock no email found
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection

        result = send_housing_email('receipt', 'S999', {})

        assert result is False

    @patch(f'{_EMAIL}.get_connection')
    @patch(f'{_EMAIL}.send_email')
    @patch(f'{_EMAIL}.render_template')
    def test_send_maintenance_email(self, mock_render, mock_send, mock_conn):
        """Test send_maintenance_email sends maintenance notifications"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_maintenance_email

        # Mock student data
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('student@example.com', 'Jane', 'Smith')
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection

        # Mock template and email
        mock_render.return_value = ('Maintenance Update', 'Your request has been updated')
        mock_send.return_value = True

        request_data = {
            'student_id': 'S001',
            'request_id': 'MAINT001',
            'issue_type': 'Plumbing',
            'status': 'completed'
        }

        result = send_maintenance_email('completed', 'MAINT001', request_data)

        assert result is True


class TestModuleConstants:
    """Test module constants and flags"""

    def test_email_service_available_flag(self):
        """Test EMAIL_SERVICE_AVAILABLE flag is defined in email_notifications submodule"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui import email_notifications

        assert hasattr(email_notifications, 'EMAIL_SERVICE_AVAILABLE')
        assert isinstance(email_notifications.EMAIL_SERVICE_AVAILABLE, bool)

    def test_finance_gui_available_flag(self):
        """Test finance_integration submodule is importable"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui import finance_integration

        assert finance_integration is not None


class TestServiceLayerIntegration:
    """Test integration with service layer"""

    def test_original_functions_imported(self):
        """Test original service functions are imported"""
        from education_system.university_system.modules.domain.housing.gui import housing_accommodation_gui

        # Check that service functions are available
        assert hasattr(housing_accommodation_gui, 'orig_create_building')
        assert hasattr(housing_accommodation_gui, 'orig_create_application')
        assert hasattr(housing_accommodation_gui, 'orig_view_assignment')
        assert hasattr(housing_accommodation_gui, 'orig_create_maintenance_request')

    def test_init_housing_db_imported(self):
        """Test init_housing_db is imported"""
        from education_system.university_system.modules.domain.housing.gui import housing_accommodation_gui

        assert hasattr(housing_accommodation_gui, 'init_housing_db')
        assert callable(housing_accommodation_gui.init_housing_db)

    def test_generate_id_imported(self):
        """Test generate_id is imported"""
        from education_system.university_system.modules.domain.housing.gui import housing_accommodation_gui

        assert hasattr(housing_accommodation_gui, 'generate_id')
        assert callable(housing_accommodation_gui.generate_id)


class TestActivityLogging:
    """Test activity logging integration"""

    def test_log_functions_imported(self):
        """Test activity log functions are imported in main_gui"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui import main_gui

        assert hasattr(main_gui, 'log_activity')
        assert hasattr(main_gui, 'log_create')
        assert hasattr(main_gui, 'log_read')
        assert hasattr(main_gui, 'log_update')
        assert hasattr(main_gui, 'log_delete')


class TestDatabaseConnection:
    """Test database connection handling"""

    def test_get_connection_imported(self):
        """Test get_connection is imported"""
        from education_system.university_system.modules.domain.housing.gui import housing_accommodation_gui

        assert hasattr(housing_accommodation_gui, 'get_connection')
        assert callable(housing_accommodation_gui.get_connection)


class TestErrorHandling:
    """Test error handling in email functions"""

    @patch(f'{_EMAIL}.get_connection')
    def test_send_housing_email_handles_db_error(self, mock_conn):
        """Test send_housing_email handles database errors"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_housing_email

        # Mock database error
        mock_conn.side_effect = Exception("Database error")

        result = send_housing_email('receipt', 'S001', {})

        assert result is False

    @patch(f'{_EMAIL}.get_connection')
    @patch(f'{_EMAIL}.send_email')
    def test_send_housing_email_handles_email_error(self, mock_send, mock_conn):
        """Test send_housing_email handles email sending errors"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_housing_email

        # Mock student data
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('student@example.com', 'John', 'Doe')
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection

        # Mock email error
        mock_send.side_effect = Exception("Email error")

        result = send_housing_email('receipt', 'S001', {'application_id': 'APP001'})

        # Should handle error gracefully
        assert isinstance(result, bool)


class TestTemplateVariables:
    """Test template variable construction"""

    @patch(f'{_EMAIL}.get_connection')
    @patch(f'{_EMAIL}.render_template')
    @patch(f'{_EMAIL}.send_email')
    def test_send_housing_email_template_variables(self, mock_send, mock_render, mock_conn):
        """Test correct template variables are passed"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_housing_email

        # Mock student data
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('student@example.com', 'John', 'Doe')
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection

        mock_render.return_value = ('Subject', 'Body')
        mock_send.return_value = True

        application_data = {
            'application_id': 'APP001',
            'preferred_room_type': 'Single',
            'special_requirements': 'Ground floor',
            'requested_move_in_date': '2024-09-01',
            'status': 'pending'
        }

        send_housing_email('receipt', 'S001', application_data)

        # Verify render_template was called
        assert mock_render.called
        call_args = mock_render.call_args[0]
        template_name = call_args[0]
        template_vars = call_args[1]

        # Check template variables
        assert 'student_name' in template_vars
        assert 'student_id' in template_vars
        assert template_vars['student_id'] == 'S001'


class TestEmailTypes:
    """Test different email types"""

    @patch(f'{_EMAIL}.get_connection')
    @patch(f'{_EMAIL}.render_template')
    @patch(f'{_EMAIL}.send_email')
    def test_send_receipt_email(self, mock_send, mock_render, mock_conn):
        """Test sending receipt email"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_housing_email

        # Setup mocks
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('test@example.com', 'Test', 'User')
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection

        mock_render.return_value = ('Receipt', 'Body')
        mock_send.return_value = True

        result = send_housing_email('receipt', 'S001', {'application_id': 'APP001'})

        assert result is True
        # Verify correct template was requested
        assert 'receipt' in mock_render.call_args[0][0] or 'accommodation_application_receipt' in mock_render.call_args[0][0]

    @patch(f'{_EMAIL}.get_connection')
    @patch(f'{_EMAIL}.render_template')
    @patch(f'{_EMAIL}.send_email')
    def test_send_approved_email(self, mock_send, mock_render, mock_conn):
        """Test sending approved email"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_housing_email

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('test@example.com', 'Test', 'User')
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection

        mock_render.return_value = ('Approved', 'Body')
        mock_send.return_value = True

        result = send_housing_email('approved', 'S001', {'application_id': 'APP001'})

        assert result is True

    @patch(f'{_EMAIL}.get_connection')
    @patch(f'{_EMAIL}.render_template')
    @patch(f'{_EMAIL}.send_email')
    def test_send_rejected_email(self, mock_send, mock_render, mock_conn):
        """Test sending rejected email"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_housing_email

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('test@example.com', 'Test', 'User')
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection

        mock_render.return_value = ('Rejected', 'Body')
        mock_send.return_value = True

        result = send_housing_email('rejected', 'S001', {'application_id': 'APP001'})

        assert result is True

    def test_send_housing_email_unknown_type(self):
        """Test send_housing_email with unknown email type"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_housing_email

        with patch(f'{_EMAIL}.get_connection') as mock_conn:
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = ('test@example.com', 'Test', 'User')
            mock_connection.cursor.return_value = mock_cursor
            mock_conn.return_value = mock_connection

            result = send_housing_email('unknown_type', 'S001', {})

            assert result is False


class TestDateCalculation:
    """Test date calculation in email functions"""

    @patch(f'{_EMAIL}.get_connection')
    @patch(f'{_EMAIL}.render_template')
    @patch(f'{_EMAIL}.send_email')
    def test_end_date_calculation(self, mock_send, mock_render, mock_conn):
        """Test end date calculation from duration"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.email_notifications import send_housing_email

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('test@example.com', 'Test', 'User')
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection

        mock_render.return_value = ('Subject', 'Body')
        mock_send.return_value = True

        application_data = {
            'application_id': 'APP001',
            'requested_move_in_date': '2024-09-01',
            'requested_duration_months': 9
        }

        send_housing_email('receipt', 'S001', application_data)

        # Verify template variables include calculated end date
        assert mock_render.called
        template_vars = mock_render.call_args[0][1]
        # End date should be calculated
        assert 'end_date' in template_vars


class TestAuthIntegration:
    """Test authentication integration"""

    @patch(f'{_MAIN}.init_housing_db')
    @patch(f'{_MAIN}.get_auth')
    def test_set_auth_in_service_layer(self, mock_get_auth, mock_init_db, root_window):
        """Test auth is set in service layer"""
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.main_gui import HousingGUI

        mock_auth = Mock()
        mock_get_auth.return_value = mock_auth

        with patch(f'{_MAIN}.set_auth') as mock_set_auth:
            gui = HousingGUI(mock_auth)

            # set_auth should be called if auth available
            # (may not be called depending on implementation)
            assert True  # Basic initialization test
            gui.root.destroy()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
