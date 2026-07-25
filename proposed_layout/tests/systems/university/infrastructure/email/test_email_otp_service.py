#!/usr/bin/env python3
"""
Comprehensive tests for Email OTP Service
Tests all email providers, templates, fallback logic, and configuration
"""

import pytest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from education_system.systems.university.infrastructure.auth.email_otp_service import (
    EmailProvider,
    SMTPEmailProvider,
    AWS_SES_Provider,
    MockEmailProvider,
    EmailOTPService,
    load_email_config,
    get_email_service,
    send_otp
)


class TestSMTPEmailProvider:
    """Test SMTP Email Provider"""

    def test_init_with_explicit_credentials(self):
        """Test initialization with explicit credentials"""
        provider = SMTPEmailProvider(
            smtp_server='smtp.test.com',
            smtp_port=587,
            username='test@test.com',
            password='testpass',
            from_email='noreply@test.com',
            from_name='Test System'
        )

        assert provider.smtp_server == 'smtp.test.com'
        assert provider.smtp_port == 587
        assert provider.username == 'test@test.com'
        assert provider.password == 'testpass'
        assert provider.from_email == 'noreply@test.com'
        assert provider.from_name == 'Test System'

    def test_init_with_env_variables(self, monkeypatch):
        """Test initialization with environment variables"""
        monkeypatch.setenv('SMTP_SERVER', 'smtp.env.com')
        monkeypatch.setenv('SMTP_PORT', '465')
        monkeypatch.setenv('SMTP_USERNAME', 'env@test.com')
        monkeypatch.setenv('SMTP_PASSWORD', 'envpass')
        monkeypatch.setenv('SMTP_FROM_EMAIL', 'from@env.com')
        monkeypatch.setenv('SMTP_FROM_NAME', 'Env System')

        # _load_email_config may return values that take precedence in the or-chain,
        # so we patch it to return empty dict so env vars are used
        with patch.object(SMTPEmailProvider, '_load_email_config', return_value={}):
            provider = SMTPEmailProvider()

        assert provider.smtp_server == 'smtp.env.com'
        assert provider.smtp_port == 465
        assert provider.username == 'env@test.com'
        assert provider.password == 'envpass'
        assert provider.from_email == 'from@env.com'
        assert provider.from_name == 'Env System'

    def test_init_missing_credentials_raises_error(self):
        """Test that missing credentials raises ValueError"""
        with patch.object(SMTPEmailProvider, '_load_email_config', return_value={}):
            with pytest.raises(ValueError, match="SMTP credentials not configured"):
                SMTPEmailProvider(smtp_server=None, username=None, password=None)

    @patch('education_system.systems.university.infrastructure.auth.email_otp_service.smtplib.SMTP')
    def test_send_otp_success(self, mock_smtp):
        """Test successful OTP sending"""
        # Setup mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        provider = SMTPEmailProvider(
            smtp_server='smtp.test.com',
            smtp_port=587,
            username='test@test.com',
            password='testpass'
        )

        result = provider.send_otp('recipient@test.com', '123456', 'TestUser')

        assert result['success'] is True
        assert result['provider'] == 'smtp'
        assert 'recipient@test.com' in result['message']

        # Verify SMTP calls
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@test.com', 'testpass')
        mock_server.send_message.assert_called_once()

    @patch('education_system.systems.university.infrastructure.auth.email_otp_service.smtplib.SMTP')
    def test_send_otp_smtp_error(self, mock_smtp):
        """Test OTP sending with SMTP error"""
        mock_smtp.return_value.__enter__.side_effect = Exception("SMTP connection failed")

        provider = SMTPEmailProvider(
            smtp_server='smtp.test.com',
            smtp_port=587,
            username='test@test.com',
            password='testpass'
        )

        result = provider.send_otp('recipient@test.com', '123456')

        assert result['success'] is False
        assert 'SMTP error' in result['error']

    def test_create_text_body_with_username(self):
        """Test plain text email body creation with username"""
        provider = SMTPEmailProvider(
            smtp_server='smtp.test.com',
            smtp_port=587,
            username='test@test.com',
            password='testpass'
        )

        body = provider._create_text_body('123456', 'TestUser')

        assert 'Hello TestUser' in body
        assert '123456' in body
        assert '10 minutes' in body
        assert 'University System' in body

    def test_create_text_body_without_username(self):
        """Test plain text email body creation without username"""
        provider = SMTPEmailProvider(
            smtp_server='smtp.test.com',
            smtp_port=587,
            username='test@test.com',
            password='testpass'
        )

        body = provider._create_text_body('123456')

        assert 'Hello,' in body
        assert 'Hello TestUser' not in body
        assert '123456' in body

    def test_create_html_body_with_username(self):
        """Test HTML email body creation with username"""
        provider = SMTPEmailProvider(
            smtp_server='smtp.test.com',
            smtp_port=587,
            username='test@test.com',
            password='testpass'
        )

        body = provider._create_html_body('123456', 'TestUser')

        assert 'Hello TestUser' in body
        assert '123456' in body
        assert 'DOCTYPE html' in body
        assert 'Security Notice' in body

    def test_create_html_body_without_username(self):
        """Test HTML email body creation without username"""
        provider = SMTPEmailProvider(
            smtp_server='smtp.test.com',
            smtp_port=587,
            username='test@test.com',
            password='testpass'
        )

        body = provider._create_html_body('123456')

        assert 'Hello,' in body
        assert '123456' in body


class TestAWS_SES_Provider:
    """Test AWS SES Email Provider"""

    def test_init_with_explicit_config(self):
        """Test initialization with explicit configuration"""
        provider = AWS_SES_Provider(
            region_name='us-west-2',
            from_email='noreply@aws.com'
        )

        assert provider.region_name == 'us-west-2'
        assert provider.from_email == 'noreply@aws.com'

    def test_init_with_env_variables(self, monkeypatch):
        """Test initialization with environment variables"""
        monkeypatch.setenv('AWS_SES_FROM_EMAIL', 'env@aws.com')

        provider = AWS_SES_Provider()

        assert provider.from_email == 'env@aws.com'
        assert provider.region_name == 'us-east-1'  # default

    def test_init_missing_from_email_raises_error(self):
        """Test that missing from_email raises ValueError"""
        with pytest.raises(ValueError, match="AWS SES from_email not configured"):
            AWS_SES_Provider(from_email=None)

    def test_send_otp_success(self):
        """Test successful OTP sending via AWS SES"""
        mock_boto3 = MagicMock()
        mock_ses = MagicMock()
        mock_boto3.client.return_value = mock_ses
        mock_ses.send_email.return_value = {'MessageId': 'test-message-id'}

        provider = AWS_SES_Provider(from_email='noreply@aws.com')

        # boto3 is imported locally inside send_otp; inject it via sys.modules
        import sys
        with patch.dict(sys.modules, {'boto3': mock_boto3}):
            result = provider.send_otp('recipient@test.com', '123456', 'TestUser')

        assert result['success'] is True
        assert result['provider'] == 'aws_ses'
        assert result['message_id'] == 'test-message-id'

        mock_ses.send_email.assert_called_once()

    def test_send_otp_boto3_not_installed(self):
        """Test OTP sending when boto3 is not installed"""
        provider = AWS_SES_Provider(from_email='noreply@aws.com')

        # boto3 is imported locally; make it raise ImportError
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
        def fake_import(name, *args, **kwargs):
            if name == 'boto3':
                raise ImportError("No module named 'boto3'")
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=fake_import):
            result = provider.send_otp('recipient@test.com', '123456')

        assert result['success'] is False
        assert 'boto3' in result['error']

    def test_send_otp_ses_error(self):
        """Test OTP sending with AWS SES error"""
        mock_boto3 = MagicMock()
        mock_ses = MagicMock()
        mock_boto3.client.return_value = mock_ses
        mock_ses.send_email.side_effect = Exception("SES error")

        provider = AWS_SES_Provider(from_email='noreply@aws.com')

        with patch('builtins.__import__', side_effect=lambda name, *args, **kwargs: mock_boto3 if name == 'boto3' else __import__(name, *args, **kwargs)):
            result = provider.send_otp('recipient@test.com', '123456')

        assert result['success'] is False
        assert 'AWS SES error' in result['error']


class TestMockEmailProvider:
    """Test Mock Email Provider"""

    def test_init_default_log_file(self):
        """Test initialization with default log file"""
        provider = MockEmailProvider()

        assert 'email_otp_log.txt' in provider.log_file

    def test_init_custom_log_file(self):
        """Test initialization with custom log file"""
        provider = MockEmailProvider(log_file='/tmp/custom_log.txt')

        assert provider.log_file == '/tmp/custom_log.txt'

    def test_send_otp_success(self, tmp_path):
        """Test successful OTP logging"""
        log_file = tmp_path / "test_email_log.txt"
        provider = MockEmailProvider(log_file=str(log_file))

        result = provider.send_otp('test@example.com', '123456', 'TestUser')

        assert result['success'] is True
        assert result['provider'] == 'mock'
        assert result['code'] == '123456'
        assert 'development mode' in result['message']

        # Verify log file was created and contains the code
        assert log_file.exists()
        content = log_file.read_text()
        assert '123456' in content
        assert 'test@example.com' in content
        assert 'TestUser' in content

    def test_send_otp_without_username(self, tmp_path):
        """Test OTP logging without username"""
        log_file = tmp_path / "test_email_log.txt"
        provider = MockEmailProvider(log_file=str(log_file))

        result = provider.send_otp('test@example.com', '654321')

        assert result['success'] is True
        assert result['code'] == '654321'

        content = log_file.read_text()
        assert '654321' in content
        assert 'User' in content

    def test_send_otp_multiple_calls(self, tmp_path):
        """Test multiple OTP logging calls"""
        log_file = tmp_path / "test_email_log.txt"
        provider = MockEmailProvider(log_file=str(log_file))

        provider.send_otp('user1@example.com', '111111', 'User1')
        provider.send_otp('user2@example.com', '222222', 'User2')
        provider.send_otp('user3@example.com', '333333', 'User3')

        content = log_file.read_text()
        assert '111111' in content
        assert '222222' in content
        assert '333333' in content
        assert content.count('=' * 80) == 6  # Two separator lines per entry, three entries

    def test_send_otp_file_error(self, tmp_path):
        """Test OTP logging with file write error"""
        # Use an invalid path
        provider = MockEmailProvider(log_file='/invalid/path/log.txt')

        result = provider.send_otp('test@example.com', '123456')

        assert result['success'] is False
        assert 'Mock provider error' in result['error']


class TestEmailOTPService:
    """Test main Email OTP Service"""

    def test_init_with_mock_provider(self):
        """Test initialization with mock provider"""
        service = EmailOTPService(primary_provider='mock', fallback_provider=None)

        assert isinstance(service.primary, MockEmailProvider)
        assert service.fallback is None

    def test_init_with_fallback_provider(self):
        """Test initialization with fallback provider"""
        service = EmailOTPService(
            primary_provider='mock',
            fallback_provider='mock'
        )

        assert isinstance(service.primary, MockEmailProvider)
        assert isinstance(service.fallback, MockEmailProvider)

    def test_create_provider_smtp(self):
        """Test SMTP provider creation"""
        with patch.object(SMTPEmailProvider, '__init__', return_value=None):
            service = EmailOTPService()
            provider = service._create_provider('smtp')
            assert provider is not None

    def test_create_provider_aws_ses(self):
        """Test AWS SES provider creation"""
        with patch.object(AWS_SES_Provider, '__init__', return_value=None):
            service = EmailOTPService()
            provider = service._create_provider('aws_ses')
            assert provider is not None

    def test_create_provider_mock(self):
        """Test mock provider creation"""
        service = EmailOTPService()
        provider = service._create_provider('mock')

        assert isinstance(provider, MockEmailProvider)

    def test_create_provider_unknown_fallback_to_mock(self):
        """Test unknown provider falls back to mock"""
        service = EmailOTPService()
        provider = service._create_provider('unknown_provider')

        assert isinstance(provider, MockEmailProvider)

    def test_create_provider_error_fallback_to_mock(self):
        """Test provider creation error falls back to mock"""
        with patch.object(SMTPEmailProvider, '__init__', side_effect=Exception("Config error")):
            service = EmailOTPService()
            provider = service._create_provider('smtp')

            assert isinstance(provider, MockEmailProvider)

    def test_send_otp_success(self, tmp_path):
        """Test successful OTP sending"""
        service = EmailOTPService(primary_provider='mock', fallback_provider=None)

        result = service.send_otp('test@example.com', '123456', 'TestUser')

        assert result['success'] is True
        assert result['provider'] == 'mock'

    def test_send_otp_invalid_email(self):
        """Test OTP sending with invalid email"""
        service = EmailOTPService(primary_provider='mock', fallback_provider=None)

        # Missing @ symbol
        result = service.send_otp('invalid-email', '123456')
        assert result['success'] is False
        assert 'Invalid email address' in result['error']

        # Empty email
        result = service.send_otp('', '123456')
        assert result['success'] is False
        assert 'Invalid email address' in result['error']

    def test_send_otp_fallback_on_primary_failure(self):
        """Test fallback provider is used when primary fails"""
        # Create service with mock providers
        service = EmailOTPService(primary_provider='mock', fallback_provider='mock')

        # Mock primary to fail
        service.primary = Mock()
        service.primary.send_otp.return_value = {'success': False, 'error': 'Primary failed'}

        # Mock fallback to succeed
        service.fallback.send_otp = Mock(return_value={
            'success': True,
            'provider': 'fallback_mock'
        })

        result = service.send_otp('test@example.com', '123456')

        assert result['success'] is True
        assert result['used_fallback'] is True

    def test_send_otp_no_fallback_on_primary_failure(self):
        """Test behavior when primary fails and no fallback"""
        service = EmailOTPService(primary_provider='mock', fallback_provider=None)

        # Mock primary to fail
        service.primary = Mock()
        service.primary.send_otp.return_value = {'success': False, 'error': 'Primary failed'}

        result = service.send_otp('test@example.com', '123456')

        assert result['success'] is False
        assert 'Primary failed' in result['error']
        assert 'used_fallback' not in result

    def test_get_provider_status(self):
        """Test getting provider status"""
        service = EmailOTPService(primary_provider='mock', fallback_provider='mock')

        status = service.get_provider_status()

        assert status['primary'] == 'MockEmailProvider'
        assert status['fallback'] == 'MockEmailProvider'

    def test_get_provider_status_no_fallback(self):
        """Test getting provider status without fallback"""
        service = EmailOTPService(primary_provider='mock', fallback_provider=None)

        status = service.get_provider_status()

        assert status['primary'] == 'MockEmailProvider'
        assert status['fallback'] is None


class TestEmailConfiguration:
    """Test email configuration loading"""

    def test_load_email_config_from_file(self, tmp_path):
        """Test loading configuration from file"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "email_config.json"

        config_data = {
            'primary_provider': 'smtp',
            'fallback_provider': 'aws_ses'
        }

        with open(config_file, 'w') as f:
            json.dump(config_data, f)

        with patch('education_system.systems.university.infrastructure.auth.email_otp_service.paths') as mock_paths:
            mock_paths.CONFIG_DIR = config_dir
            config = load_email_config()

        assert config['primary_provider'] == 'smtp'
        assert config['fallback_provider'] == 'aws_ses'

    def test_load_email_config_file_not_found(self):
        """Test loading configuration when file doesn't exist"""
        with patch('education_system.systems.university.infrastructure.auth.email_otp_service.paths') as mock_paths:
            mock_paths.CONFIG_DIR = Path('/nonexistent')
            config = load_email_config()

        assert config['primary_provider'] == 'smtp'  # default from env fallback
        assert config['fallback_provider'] == 'mock'

    def test_load_email_config_from_env(self, monkeypatch):
        """Test loading configuration from environment variables"""
        monkeypatch.setenv('EMAIL_PRIMARY_PROVIDER', 'smtp')
        monkeypatch.setenv('EMAIL_FALLBACK_PROVIDER', 'aws_ses')

        with patch('education_system.systems.university.infrastructure.auth.email_otp_service.paths') as mock_paths:
            mock_paths.CONFIG_DIR = Path('/nonexistent')
            config = load_email_config()

        assert config['primary_provider'] == 'smtp'
        assert config['fallback_provider'] == 'aws_ses'

    def test_load_email_config_invalid_json(self, tmp_path):
        """Test loading configuration with invalid JSON"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "email_config.json"

        # Write invalid JSON
        with open(config_file, 'w') as f:
            f.write("{ invalid json }")

        with patch('education_system.systems.university.infrastructure.auth.email_otp_service.paths') as mock_paths:
            mock_paths.CONFIG_DIR = config_dir
            config = load_email_config()

        # Should fall back to defaults (env-based fallback returns 'smtp')
        assert config['primary_provider'] == 'smtp'


class TestConvenienceFunctions:
    """Test module-level convenience functions"""

    def test_get_email_service_singleton(self):
        """Test that get_email_service returns singleton"""
        # Reset the singleton
        import education_system.systems.university.infrastructure.auth.email_otp_service as email_module
        email_module._default_service = None

        with patch.object(email_module, 'load_email_config', return_value={
            'primary_provider': 'mock',
            'fallback_provider': None,
            'smtp_whitelist': []
        }):
            service1 = get_email_service()
            service2 = get_email_service()

        assert service1 is service2

        # Clean up singleton
        email_module._default_service = None

    def test_send_otp_convenience_function(self):
        """Test send_otp convenience function"""
        import education_system.systems.university.infrastructure.auth.email_otp_service as email_module
        email_module._default_service = None

        # Ensure load_email_config returns mock provider so we don't need real SMTP
        with patch.object(email_module, 'load_email_config', return_value={
            'primary_provider': 'mock',
            'fallback_provider': None,
            'smtp_whitelist': []
        }):
            result = send_otp('test@example.com', '123456', 'TestUser')

        assert result['success'] is True
        assert result['provider'] == 'mock'

        # Clean up singleton
        email_module._default_service = None


class TestEmailTemplates:
    """Test email template generation"""

    def test_text_template_formatting(self):
        """Test that text template is properly formatted"""
        provider = SMTPEmailProvider(
            smtp_server='smtp.test.com',
            smtp_port=587,
            username='test@test.com',
            password='testpass'
        )

        body = provider._create_text_body('123456', 'John Doe')

        # Check formatting
        lines = body.split('\n')
        assert any('Hello John Doe' in line for line in lines)
        assert any('123456' in line for line in lines)
        assert any('10 minutes' in line for line in lines)

    def test_html_template_structure(self):
        """Test that HTML template has proper structure"""
        provider = SMTPEmailProvider(
            smtp_server='smtp.test.com',
            smtp_port=587,
            username='test@test.com',
            password='testpass'
        )

        body = provider._create_html_body('123456', 'John Doe')

        # Check HTML structure
        assert '<!DOCTYPE html>' in body
        assert '<html>' in body
        assert '<head>' in body
        assert '<style>' in body
        assert '<body>' in body
        assert '123456' in body
        assert 'John Doe' in body

    def test_html_template_css_styling(self):
        """Test that HTML template includes CSS styling"""
        provider = SMTPEmailProvider(
            smtp_server='smtp.test.com',
            smtp_port=587,
            username='test@test.com',
            password='testpass'
        )

        body = provider._create_html_body('123456')

        # Check for CSS classes
        assert 'class="container"' in body
        assert 'class="header"' in body
        assert 'class="content"' in body
        assert 'class="code-box"' in body
        assert 'class="code"' in body
        assert 'class="warning"' in body

    def test_html_template_security_warnings(self):
        """Test that HTML template includes security warnings"""
        provider = SMTPEmailProvider(
            smtp_server='smtp.test.com',
            smtp_port=587,
            username='test@test.com',
            password='testpass'
        )

        body = provider._create_html_body('123456')

        assert 'Security Notice' in body or 'security' in body.lower()
        assert 'never share' in body.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
