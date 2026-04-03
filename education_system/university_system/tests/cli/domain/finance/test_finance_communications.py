"""
Comprehensive tests for finance communications module.
Tests all communication functions including email and SMS services.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from education_system.university_system.modules.domain.finance.core.communications import (
    send_email_smtp,
    send_email_sendgrid,
    send_email_aws_ses,
    setup_email_config,
    setup_sms_config,
    send_sms_twilio,
    send_sms_aws_sns,
    test_email_service,
    test_sms_service,
    send_arrangement_confirmation,
    EMAIL_CONFIG,
    SENDGRID_CONFIG,
    AWS_SNS_CONFIG,
    TWILIO_CONFIG,
)


class TestSendEmailSMTP:
    """Test suite for send_email_smtp function"""

    @patch('education_system.university_system.infrastructure.email.smtp.send_email_via_smtp')
    @patch('builtins.print')
    def test_send_email_smtp_success(self, mock_print, mock_send_email):
        """Test successful email sending via SMTP"""
        mock_send_email.return_value = True

        result = send_email_smtp(
            to_email='test@example.com',
            subject='Test Subject',
            body='Test Body'
        )

        assert result is True
        mock_send_email.assert_called_once()
        # Verify success message printed (get_text returns the i18n key)
        assert any('email_sent_success' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.infrastructure.email.smtp.send_email_via_smtp')
    @patch('builtins.print')
    def test_send_email_smtp_failure(self, mock_print, mock_send_email):
        """Test failed email sending via SMTP"""
        mock_send_email.return_value = False

        result = send_email_smtp(
            to_email='test@example.com',
            subject='Test Subject',
            body='Test Body'
        )

        assert result is False
        # Verify failure message printed (get_text returns the i18n key)
        assert any('email_send_failed' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.infrastructure.email.smtp.send_email_via_smtp')
    @patch('builtins.print')
    def test_send_email_smtp_exception(self, mock_print, mock_send_email):
        """Test email sending with exception"""
        mock_send_email.side_effect = Exception("SMTP error")

        result = send_email_smtp(
            to_email='test@example.com',
            subject='Test Subject',
            body='Test Body'
        )

        assert result is False
        # Verify error message printed (get_text returns the i18n key)
        assert any('smtp_email_failed' in str(call) for call in mock_print.call_args_list)


class TestSendEmailSendgrid:
    """Test suite for send_email_sendgrid function"""

    @patch('education_system.university_system.modules.shared.utils.communication_integration.send_email_unified')
    @patch('builtins.print')
    def test_send_email_sendgrid_success(self, mock_print, mock_send_email):
        """Test successful email sending via SendGrid (deprecated)"""
        mock_send_email.return_value = True

        result = send_email_sendgrid(
            to_email='test@example.com',
            subject='Test Subject',
            body='Test Body'
        )

        assert result is True
        mock_send_email.assert_called_once()
        # Verify deprecation warning (get_text returns the i18n key)
        assert any('deprecated_sendgrid' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.modules.shared.utils.communication_integration.send_email_unified')
    @patch('builtins.print')
    def test_send_email_sendgrid_failure(self, mock_print, mock_send_email):
        """Test failed email sending via SendGrid"""
        mock_send_email.return_value = False

        result = send_email_sendgrid(
            to_email='test@example.com',
            subject='Test Subject',
            body='Test Body'
        )

        assert result is False

    @patch('education_system.university_system.modules.shared.utils.communication_integration.send_email_unified')
    @patch('builtins.print')
    def test_send_email_sendgrid_exception(self, mock_print, mock_send_email):
        """Test email sending via SendGrid with exception"""
        mock_send_email.side_effect = Exception("SendGrid error")

        result = send_email_sendgrid(
            to_email='test@example.com',
            subject='Test Subject',
            body='Test Body'
        )

        assert result is False
        assert any('email_failed' in str(call) for call in mock_print.call_args_list)


class TestSendEmailAWSSES:
    """Test suite for send_email_aws_ses function"""

    @patch('education_system.university_system.modules.shared.utils.communication_integration.send_email_unified')
    @patch('builtins.print')
    def test_send_email_aws_ses_success(self, mock_print, mock_send_email):
        """Test successful email sending via AWS SES (deprecated)"""
        mock_send_email.return_value = True

        result = send_email_aws_ses(
            to_email='test@example.com',
            subject='Test Subject',
            body='Test Body'
        )

        assert result is True
        mock_send_email.assert_called_once()
        # Verify deprecation warning (get_text returns the i18n key)
        assert any('deprecated_aws_ses' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.modules.shared.utils.communication_integration.send_email_unified')
    @patch('builtins.print')
    def test_send_email_aws_ses_failure(self, mock_print, mock_send_email):
        """Test failed email sending via AWS SES"""
        mock_send_email.return_value = False

        result = send_email_aws_ses(
            to_email='test@example.com',
            subject='Test Subject',
            body='Test Body'
        )

        assert result is False


class TestSetupEmailConfig:
    """Test suite for setup_email_config function"""

    @patch('builtins.input', side_effect=['1', 'test@example.com', 'password123', 'Finance Dept', ''])
    @patch('builtins.print')
    def test_setup_email_config_gmail(self, mock_print, mock_input):
        """Test email configuration setup for Gmail"""
        setup_email_config()

        # Verify configuration was updated
        assert EMAIL_CONFIG['sender_email'] == 'test@example.com'
        assert EMAIL_CONFIG['sender_password'] == 'password123'
        assert EMAIL_CONFIG['sender_name'] == 'Finance Dept'

        # Verify success message (get_text returns the i18n key)
        assert any('email_config_updated' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['2', 'sg_api_key', 'finance@uni.ac.uk', 'Finance Dept'])
    @patch('builtins.print')
    def test_setup_email_config_sendgrid(self, mock_print, mock_input):
        """Test email configuration setup for SendGrid"""
        setup_email_config()

        # Verify configuration was updated
        assert SENDGRID_CONFIG['api_key'] == 'sg_api_key'
        assert SENDGRID_CONFIG['from_email'] == 'finance@uni.ac.uk'
        assert SENDGRID_CONFIG['from_name'] == 'Finance Dept'

    @patch('builtins.input', side_effect=['3', 'aws_access_key', 'aws_secret_key', ''])
    @patch('builtins.print')
    def test_setup_email_config_aws(self, mock_print, mock_input):
        """Test email configuration setup for AWS SES"""
        setup_email_config()

        # Verify configuration was updated
        assert AWS_SNS_CONFIG['aws_access_key_id'] == 'aws_access_key'
        assert AWS_SNS_CONFIG['aws_secret_access_key'] == 'aws_secret_key'


class TestSetupSMSConfig:
    """Test suite for setup_sms_config function"""

    @patch('builtins.input', side_effect=['1', 'AC123456', 'auth_token_123', '+447000000000'])
    @patch('builtins.print')
    def test_setup_sms_config_twilio(self, mock_print, mock_input):
        """Test SMS configuration setup for Twilio"""
        setup_sms_config()

        # Verify configuration was updated
        assert TWILIO_CONFIG['account_sid'] == 'AC123456'
        assert TWILIO_CONFIG['auth_token'] == 'auth_token_123'
        assert TWILIO_CONFIG['from_phone'] == '+447000000000'

        # Verify success message (get_text returns the i18n key)
        assert any('sms_config_updated' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['2', 'aws_access_key', 'aws_secret_key', ''])
    @patch('builtins.print')
    def test_setup_sms_config_aws(self, mock_print, mock_input):
        """Test SMS configuration setup for AWS SNS"""
        setup_sms_config()

        # Verify configuration was updated
        assert AWS_SNS_CONFIG['aws_access_key_id'] == 'aws_access_key'
        assert AWS_SNS_CONFIG['aws_secret_access_key'] == 'aws_secret_key'


class TestSendSMSTwilio:
    """Test suite for send_sms_twilio function"""

    @patch('education_system.university_system.modules.shared.utils.communication_integration.send_sms_unified')
    @patch('builtins.print')
    def test_send_sms_twilio_success(self, mock_print, mock_send_sms):
        """Test successful SMS sending via Twilio (deprecated)"""
        mock_send_sms.return_value = True

        result = send_sms_twilio(
            phone_number='+447123456789',
            message='Test message'
        )

        assert result is True
        mock_send_sms.assert_called_once()
        # Verify deprecation warning (get_text returns the i18n key)
        assert any('deprecated_twilio' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.modules.shared.utils.communication_integration.send_sms_unified')
    @patch('builtins.print')
    def test_send_sms_twilio_failure(self, mock_print, mock_send_sms):
        """Test failed SMS sending via Twilio"""
        mock_send_sms.return_value = False

        result = send_sms_twilio(
            phone_number='+447123456789',
            message='Test message'
        )

        assert result is False

    @patch('education_system.university_system.modules.shared.utils.communication_integration.send_sms_unified')
    @patch('builtins.print')
    def test_send_sms_twilio_exception(self, mock_print, mock_send_sms):
        """Test SMS sending via Twilio with exception"""
        mock_send_sms.side_effect = Exception("Twilio error")

        result = send_sms_twilio(
            phone_number='+447123456789',
            message='Test message'
        )

        assert result is False
        assert any('sms_failed' in str(call) for call in mock_print.call_args_list)


class TestSendSMSAWSSNS:
    """Test suite for send_sms_aws_sns function"""

    @patch('education_system.university_system.modules.shared.utils.communication_integration.send_sms_unified')
    @patch('builtins.print')
    def test_send_sms_aws_sns_success(self, mock_print, mock_send_sms):
        """Test successful SMS sending via AWS SNS (deprecated)"""
        mock_send_sms.return_value = True

        result = send_sms_aws_sns(
            phone_number='+447123456789',
            message='Test message'
        )

        assert result is True
        mock_send_sms.assert_called_once()
        # Verify deprecation warning
        assert any('DEPRECATED' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.modules.shared.utils.communication_integration.send_sms_unified')
    @patch('builtins.print')
    def test_send_sms_aws_sns_failure(self, mock_print, mock_send_sms):
        """Test failed SMS sending via AWS SNS"""
        mock_send_sms.return_value = False

        result = send_sms_aws_sns(
            phone_number='+447123456789',
            message='Test message'
        )

        assert result is False


class TestEmailService:
    """Test suite for test_email_service function"""

    @patch('education_system.university_system.modules.domain.finance.core.communications.send_email_notification')
    @patch('education_system.university_system.infrastructure.email.template_utils.render_template')
    @patch('builtins.input', return_value='test@example.com')
    @patch('builtins.print')
    def test_email_service_success(self, mock_print, mock_input, mock_render, mock_send):
        """Test successful email service testing"""
        mock_render.return_value = ('Test Subject', 'Test Body')
        mock_send.return_value = True

        test_email_service()

        mock_send.assert_called_once_with('test@example.com', 'Test Subject', 'Test Body')
        assert any('Email test successful' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.modules.domain.finance.core.communications.send_email_notification')
    @patch('education_system.university_system.infrastructure.email.template_utils.render_template')
    @patch('builtins.input', return_value='test@example.com')
    @patch('builtins.print')
    def test_email_service_failure(self, mock_print, mock_input, mock_render, mock_send):
        """Test failed email service testing"""
        mock_render.return_value = ('Test Subject', 'Test Body')
        mock_send.return_value = False

        test_email_service()

        assert any('Email test failed' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.infrastructure.email.template_utils.render_template')
    @patch('builtins.input', return_value='test@example.com')
    @patch('builtins.print')
    def test_email_service_no_template(self, mock_print, mock_input, mock_render):
        """Test email service testing with missing template"""
        mock_render.return_value = (None, None)

        test_email_service()

        assert any('Failed to load email template' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.infrastructure.email.template_utils.render_template')
    @patch('builtins.input', return_value='')
    @patch('builtins.print')
    def test_email_service_default_email(self, mock_print, mock_input, mock_render):
        """Test email service testing with default email"""
        mock_render.return_value = ('Test Subject', 'Test Body')

        with patch('education_system.university_system.modules.domain.finance.core.communications.send_email_notification') as mock_send:
            mock_send.return_value = True
            test_email_service()

            # Should use default email
            assert mock_send.called


class TestSMSService:
    """Test suite for test_sms_service function"""

    @patch('education_system.university_system.modules.domain.finance.core.communications.send_sms_notification')
    @patch('builtins.input', return_value='STU001')
    @patch('builtins.print')
    def test_sms_service_success(self, mock_print, mock_input, mock_send):
        """Test successful SMS service testing"""
        mock_send.return_value = True

        test_sms_service()

        mock_send.assert_called_once()
        assert any('SMS test successful' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.modules.domain.finance.core.communications.send_sms_notification')
    @patch('builtins.input', return_value='STU001')
    @patch('builtins.print')
    def test_sms_service_failure(self, mock_print, mock_input, mock_send):
        """Test failed SMS service testing"""
        mock_send.return_value = False

        test_sms_service()

        assert any('SMS test failed' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.modules.domain.finance.core.communications.send_sms_notification')
    @patch('builtins.input', return_value='')
    @patch('builtins.print')
    def test_sms_service_default_student(self, mock_print, mock_input, mock_send):
        """Test SMS service testing with default student ID"""
        mock_send.return_value = True

        test_sms_service()

        # Should use default student ID 'STU001'
        assert mock_send.called

    @patch('builtins.input', return_value='STU001')
    @patch('builtins.print')
    def test_sms_service_exception(self, mock_print, mock_input):
        """Test SMS service testing with exception"""
        with patch('education_system.university_system.modules.domain.finance.core.communications.send_sms_notification') as mock_send:
            mock_send.side_effect = Exception("SMS error")
            test_sms_service()

            assert any('SMS test error' in str(call) for call in mock_print.call_args_list)


class TestSendArrangementConfirmation:
    """Test suite for send_arrangement_confirmation function"""

    @patch('education_system.university_system.modules.domain.finance.core.communications.get_connection')
    @patch('education_system.university_system.modules.domain.finance.core.communications.send_email_notification')
    @patch('education_system.university_system.modules.domain.finance.core.communications.render_template')
    @patch('builtins.print')
    def test_send_arrangement_confirmation_success(self, mock_print, mock_render, mock_send, mock_get_conn):
        """Test successful arrangement confirmation sending"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock student data
        mock_cursor.fetchone.return_value = ('John', 'Doe', 'john.doe@example.com')

        mock_render.return_value = ('Confirmation Subject', 'Confirmation Body')
        mock_send.return_value = True

        send_arrangement_confirmation(
            student_id='STU001',
            case_id=123,
            schedule_info='Monthly payments of £100'
        )

        mock_send.assert_called_once()
        assert any('confirmation sent' in str(call) for call in mock_print.call_args_list)
        mock_conn.close.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.core.communications.get_connection')
    @patch('education_system.university_system.modules.domain.finance.core.communications.send_email_notification')
    @patch('education_system.university_system.modules.domain.finance.core.communications.render_template')
    @patch('builtins.print')
    def test_send_arrangement_confirmation_send_failure(self, mock_print, mock_render, mock_send, mock_get_conn):
        """Test arrangement confirmation with send failure"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = ('John', 'Doe', 'john.doe@example.com')
        mock_render.return_value = ('Confirmation Subject', 'Confirmation Body')
        mock_send.return_value = False

        send_arrangement_confirmation(
            student_id='STU001',
            case_id=123,
            schedule_info='Monthly payments of £100'
        )

        assert any('Failed to send arrangement confirmation' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.modules.domain.finance.core.communications.get_connection')
    @patch('builtins.print')
    def test_send_arrangement_confirmation_no_student(self, mock_print, mock_get_conn):
        """Test arrangement confirmation with non-existent student"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock no student found
        mock_cursor.fetchone.return_value = None

        send_arrangement_confirmation(
            student_id='STU999',
            case_id=123,
            schedule_info='Monthly payments of £100'
        )

        # Should close connection even if student not found
        mock_conn.close.assert_called_once()

    @patch('education_system.university_system.modules.domain.finance.core.communications.get_connection')
    @patch('builtins.print')
    def test_send_arrangement_confirmation_exception(self, mock_print, mock_get_conn):
        """Test arrangement confirmation with exception"""
        mock_get_conn.side_effect = Exception("Database error")

        send_arrangement_confirmation(
            student_id='STU001',
            case_id=123,
            schedule_info='Monthly payments of £100'
        )

        assert any('Error sending arrangement confirmation' in str(call) for call in mock_print.call_args_list)


class TestConfigurationConstants:
    """Test suite for configuration constants"""

    def test_email_config_structure(self):
        """Test EMAIL_CONFIG has required keys"""
        assert 'sender_email' in EMAIL_CONFIG
        assert 'sender_password' in EMAIL_CONFIG
        assert 'sender_name' in EMAIL_CONFIG
        assert 'smtp_server' in EMAIL_CONFIG
        assert 'smtp_port' in EMAIL_CONFIG

    def test_sendgrid_config_structure(self):
        """Test SENDGRID_CONFIG has required keys"""
        assert 'api_key' in SENDGRID_CONFIG
        assert 'from_email' in SENDGRID_CONFIG
        assert 'from_name' in SENDGRID_CONFIG

    def test_aws_sns_config_structure(self):
        """Test AWS_SNS_CONFIG has required keys"""
        assert 'aws_access_key_id' in AWS_SNS_CONFIG
        assert 'aws_secret_access_key' in AWS_SNS_CONFIG
        assert 'region_name' in AWS_SNS_CONFIG

    def test_twilio_config_structure(self):
        """Test TWILIO_CONFIG has required keys"""
        assert 'account_sid' in TWILIO_CONFIG
        assert 'auth_token' in TWILIO_CONFIG
        assert 'from_phone' in TWILIO_CONFIG


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
