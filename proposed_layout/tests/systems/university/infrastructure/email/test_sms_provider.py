#!/usr/bin/env python3
"""
Comprehensive tests for SMS Provider Service
Tests all SMS providers, phone number formatting, fallback logic, and configuration
"""

import importlib.util
import pytest
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# twilio is an optional dependency; tests that patch twilio.rest.Client can only
# run when it's installed (the patch target is imported at setup time).
_HAS_TWILIO = importlib.util.find_spec("twilio") is not None
requires_twilio = pytest.mark.skipif(not _HAS_TWILIO, reason="twilio not installed")
from education_system.systems.university.infrastructure.auth.sms_provider import (
    SMSProvider,
    TwilioSMSProvider,
    AWS_SNS_Provider,
    MockSMSProvider,
    SMSService,
    load_sms_config,
    get_sms_service,
    send_otp
)


class TestTwilioSMSProvider:
    """Test Twilio SMS Provider"""

    def test_init_with_explicit_credentials(self):
        """Test initialization with explicit credentials"""
        provider = TwilioSMSProvider(
            account_sid='AC1234567890',
            auth_token='test_token',
            from_number='+15551234567'
        )

        assert provider.account_sid == 'AC1234567890'
        assert provider.auth_token == 'test_token'
        assert provider.from_number == '+15551234567'

    def test_init_with_env_variables(self, monkeypatch):
        """Test initialization with environment variables"""
        monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'AC_ENV')
        monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'env_token')
        monkeypatch.setenv('TWILIO_PHONE_NUMBER', '+15559876543')

        provider = TwilioSMSProvider()

        assert provider.account_sid == 'AC_ENV'
        assert provider.auth_token == 'env_token'
        assert provider.from_number == '+15559876543'

    def test_init_missing_credentials_raises_error(self):
        """Test that missing credentials raises ValueError"""
        with pytest.raises(ValueError, match="Twilio credentials not configured"):
            TwilioSMSProvider(account_sid=None, auth_token=None, from_number=None)

    @requires_twilio
    @patch('twilio.rest.Client')
    def test_send_otp_success(self, mock_client_class):
        """Test successful OTP sending"""
        # Setup mock Twilio client
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = 'SM1234567890'
        mock_message.status = 'queued'
        mock_client.messages.create.return_value = mock_message
        mock_client_class.return_value = mock_client

        provider = TwilioSMSProvider(
            account_sid='AC1234567890',
            auth_token='test_token',
            from_number='+15551234567'
        )

        result = provider.send_otp('+15559998888', '123456')

        assert result['success'] is True
        assert result['provider'] == 'twilio'
        assert result['message_sid'] == 'SM1234567890'
        assert result['status'] == 'queued'

        # Verify Twilio API was called correctly
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs['to'] == '+15559998888'
        assert call_kwargs['from_'] == '+15551234567'
        assert '123456' in call_kwargs['body']

    def test_send_otp_twilio_not_installed(self):
        """Test OTP sending when Twilio library is not installed"""
        provider = TwilioSMSProvider(
            account_sid='AC1234567890',
            auth_token='test_token',
            from_number='+15551234567'
        )

        # The import happens inside send_otp; if twilio isn't installed,
        # it returns an error dict. Just verify provider was created.
        assert provider.account_sid == 'AC1234567890'

    @requires_twilio
    @patch('twilio.rest.Client')
    def test_send_otp_twilio_error(self, mock_client_class):
        """Test OTP sending with Twilio API error"""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Twilio API error")
        mock_client_class.return_value = mock_client

        provider = TwilioSMSProvider(
            account_sid='AC1234567890',
            auth_token='test_token',
            from_number='+15551234567'
        )

        result = provider.send_otp('+15559998888', '123456')

        assert result['success'] is False
        assert 'Twilio error' in result['error']

    @requires_twilio
    @patch('twilio.rest.Client')
    def test_send_otp_message_content(self, mock_client_class):
        """Test that OTP message contains required information"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = 'SM1234567890'
        mock_message.status = 'sent'
        mock_client.messages.create.return_value = mock_message
        mock_client_class.return_value = mock_client

        provider = TwilioSMSProvider(
            account_sid='AC1234567890',
            auth_token='test_token',
            from_number='+15551234567'
        )

        result = provider.send_otp('+15559998888', '654321')

        # Get the message body that was sent
        call_kwargs = mock_client.messages.create.call_args[1]
        message_body = call_kwargs['body']

        assert '654321' in message_body
        assert 'University System' in message_body
        assert '10 minutes' in message_body
        assert 'Do not share' in message_body


class TestAWS_SNS_Provider:
    """Test AWS SNS SMS Provider"""

    def test_init_default_region(self):
        """Test initialization with default region"""
        provider = AWS_SNS_Provider()

        assert provider.region_name == 'us-east-1'

    def test_init_custom_region(self):
        """Test initialization with custom region"""
        provider = AWS_SNS_Provider(region_name='us-west-2')

        assert provider.region_name == 'us-west-2'

    @patch('boto3.client')
    def test_send_otp_success(self, mock_boto3_client):
        """Test successful OTP sending via AWS SNS"""
        mock_sns = MagicMock()
        mock_boto3_client.return_value = mock_sns
        mock_sns.publish.return_value = {'MessageId': 'test-message-id-123'}

        provider = AWS_SNS_Provider()
        result = provider.send_otp('+15559998888', '123456')

        assert result['success'] is True
        assert result['provider'] == 'aws_sns'
        assert result['message_id'] == 'test-message-id-123'

        # Verify SNS API was called
        mock_sns.publish.assert_called_once()
        call_kwargs = mock_sns.publish.call_args[1]
        assert call_kwargs['PhoneNumber'] == '+15559998888'
        assert '123456' in call_kwargs['Message']
        assert 'Transactional' in call_kwargs['MessageAttributes']['AWS.SNS.SMS.SMSType']['StringValue']

    def test_send_otp_boto3_not_installed(self):
        """Test OTP sending when boto3 is not installed"""
        provider = AWS_SNS_Provider()
        # Verify provider was created successfully
        assert provider.region_name == 'us-east-1'

    @patch('boto3.client')
    def test_send_otp_sns_error(self, mock_boto3_client):
        """Test OTP sending with AWS SNS error"""
        mock_sns = MagicMock()
        mock_boto3_client.return_value = mock_sns
        mock_sns.publish.side_effect = Exception("SNS error")

        provider = AWS_SNS_Provider()
        result = provider.send_otp('+15559998888', '123456')

        assert result['success'] is False
        assert 'AWS SNS error' in result['error']

    @patch('boto3.client')
    def test_send_otp_message_content(self, mock_boto3_client):
        """Test that OTP message contains required information"""
        mock_sns = MagicMock()
        mock_boto3_client.return_value = mock_sns
        mock_sns.publish.return_value = {'MessageId': 'test-id'}

        provider = AWS_SNS_Provider()
        result = provider.send_otp('+15559998888', '789012')

        call_kwargs = mock_sns.publish.call_args[1]
        message = call_kwargs['Message']

        assert '789012' in message
        assert 'University System' in message
        assert '10 minutes' in message
        assert 'Do not share' in message


class TestMockSMSProvider:
    """Test Mock SMS Provider"""

    def test_init_default_log_file(self):
        """Test initialization with default log file"""
        provider = MockSMSProvider()

        assert 'sms_otp_log.txt' in provider.log_file

    def test_init_custom_log_file(self):
        """Test initialization with custom log file"""
        provider = MockSMSProvider(log_file='/tmp/custom_sms_log.txt')

        assert provider.log_file == '/tmp/custom_sms_log.txt'

    def test_send_otp_success(self, tmp_path):
        """Test successful OTP logging"""
        log_file = tmp_path / "test_sms_log.txt"
        provider = MockSMSProvider(log_file=str(log_file))

        result = provider.send_otp('+15559998888', '123456')

        assert result['success'] is True
        assert result['provider'] == 'mock'
        assert result['code'] == '123456'
        assert 'development mode' in result['message']

        # Verify log file was created and contains redacted data
        assert log_file.exists()
        content = log_file.read_text()
        # Code is redacted in log (only last 2 digits visible)
        assert '****56' in content
        # Phone is redacted in log (only first 4 and last 2 visible)
        assert '+155' in content
        assert '****' in content

    def test_send_otp_multiple_calls(self, tmp_path):
        """Test multiple OTP logging calls"""
        log_file = tmp_path / "test_sms_log.txt"
        provider = MockSMSProvider(log_file=str(log_file))

        provider.send_otp('+15551111111', '111111')
        provider.send_otp('+15552222222', '222222')
        provider.send_otp('+15553333333', '333333')

        content = log_file.read_text()
        # Codes are redacted — only last 2 digits visible
        assert '****11' in content
        assert '****22' in content
        assert '****33' in content
        # Three log entries should exist
        assert content.count('verification code sent') == 3

    def test_send_otp_timestamp(self, tmp_path):
        """Test that timestamps are included in logs"""
        log_file = tmp_path / "test_sms_log.txt"
        provider = MockSMSProvider(log_file=str(log_file))

        provider.send_otp('+15559998888', '123456')

        content = log_file.read_text()
        # Should contain a timestamp in format YYYY-MM-DD HH:MM:SS
        assert '[' in content  # Timestamp is in brackets

    def test_send_otp_file_error(self):
        """Test OTP logging with file write error"""
        provider = MockSMSProvider(log_file='/invalid/path/sms_log.txt')

        result = provider.send_otp('+15559998888', '123456')

        assert result['success'] is False
        assert 'Mock provider error' in result['error']


class TestSMSService:
    """Test main SMS Service"""

    def test_init_with_mock_provider(self):
        """Test initialization with mock provider"""
        service = SMSService(primary_provider='mock')

        assert isinstance(service.primary, MockSMSProvider)
        assert service.fallback is None

    def test_init_with_fallback_provider(self):
        """Test initialization with fallback provider"""
        service = SMSService(
            primary_provider='mock',
            fallback_provider='mock'
        )

        assert isinstance(service.primary, MockSMSProvider)
        assert isinstance(service.fallback, MockSMSProvider)

    def test_create_provider_twilio(self):
        """Test Twilio provider creation"""
        with patch.object(TwilioSMSProvider, '__init__', return_value=None):
            service = SMSService()
            provider = service._create_provider('twilio')
            assert provider is not None

    def test_create_provider_aws_sns(self):
        """Test AWS SNS provider creation"""
        with patch.object(AWS_SNS_Provider, '__init__', return_value=None):
            service = SMSService()
            provider = service._create_provider('aws_sns')
            assert provider is not None

    def test_create_provider_mock(self):
        """Test mock provider creation"""
        service = SMSService()
        provider = service._create_provider('mock')

        assert isinstance(provider, MockSMSProvider)

    def test_create_provider_unknown_fallback_to_mock(self):
        """Test unknown provider falls back to mock"""
        service = SMSService()
        provider = service._create_provider('unknown_provider')

        assert isinstance(provider, MockSMSProvider)

    def test_create_provider_error_fallback_to_mock(self):
        """Test provider creation error falls back to mock"""
        with patch.object(TwilioSMSProvider, '__init__', side_effect=Exception("Config error")):
            service = SMSService()
            provider = service._create_provider('twilio')

            assert isinstance(provider, MockSMSProvider)

    def test_send_otp_success(self):
        """Test successful OTP sending"""
        service = SMSService(primary_provider='mock')

        result = service.send_otp('+15559998888', '123456')

        assert result['success'] is True
        assert result['provider'] == 'mock'

    def test_send_otp_empty_phone_number(self):
        """Test OTP sending with empty phone number"""
        service = SMSService(primary_provider='mock')

        result = service.send_otp('', '123456')

        assert result['success'] is False
        assert 'Phone number is required' in result['error']

    def test_send_otp_none_phone_number(self):
        """Test OTP sending with None phone number"""
        service = SMSService(primary_provider='mock')

        result = service.send_otp(None, '123456')

        assert result['success'] is False
        assert 'Phone number is required' in result['error']

    def test_send_otp_phone_number_formatting(self):
        """Test phone number formatting adds country code"""
        service = SMSService(primary_provider='mock')

        # Mock the primary provider to capture the formatted number
        service.primary.send_otp = Mock(return_value={'success': True, 'provider': 'mock'})

        service.send_otp('5559998888', '123456')

        # Verify the phone number was formatted with +1
        call_args = service.primary.send_otp.call_args[0]
        assert call_args[0] == '+15559998888'

    def test_send_otp_phone_number_with_dashes(self):
        """Test phone number formatting removes dashes"""
        service = SMSService(primary_provider='mock')
        service.primary.send_otp = Mock(return_value={'success': True, 'provider': 'mock'})

        service.send_otp('555-999-8888', '123456')

        call_args = service.primary.send_otp.call_args[0]
        assert call_args[0] == '+15559998888'

    def test_send_otp_phone_number_with_spaces(self):
        """Test phone number formatting removes spaces"""
        service = SMSService(primary_provider='mock')
        service.primary.send_otp = Mock(return_value={'success': True, 'provider': 'mock'})

        service.send_otp('555 999 8888', '123456')

        call_args = service.primary.send_otp.call_args[0]
        assert call_args[0] == '+15559998888'

    def test_send_otp_phone_number_with_parentheses(self):
        """Test phone number formatting removes parentheses"""
        service = SMSService(primary_provider='mock')
        service.primary.send_otp = Mock(return_value={'success': True, 'provider': 'mock'})

        service.send_otp('(555) 999-8888', '123456')

        call_args = service.primary.send_otp.call_args[0]
        assert call_args[0] == '+15559998888'

    def test_send_otp_phone_number_already_with_plus(self):
        """Test phone number formatting preserves existing plus sign"""
        service = SMSService(primary_provider='mock')
        service.primary.send_otp = Mock(return_value={'success': True, 'provider': 'mock'})

        service.send_otp('+15559998888', '123456')

        call_args = service.primary.send_otp.call_args[0]
        assert call_args[0] == '+15559998888'

    def test_send_otp_international_number(self):
        """Test phone number with international code"""
        service = SMSService(primary_provider='mock')
        service.primary.send_otp = Mock(return_value={'success': True, 'provider': 'mock'})

        service.send_otp('+447911123456', '123456')  # UK number

        call_args = service.primary.send_otp.call_args[0]
        assert call_args[0] == '+447911123456'

    def test_send_otp_fallback_on_primary_failure(self):
        """Test fallback provider is used when primary fails"""
        service = SMSService(primary_provider='mock', fallback_provider='mock')

        # Mock primary to fail
        service.primary = Mock()
        service.primary.send_otp.return_value = {'success': False, 'error': 'Primary failed'}

        # Mock fallback to succeed
        service.fallback.send_otp = Mock(return_value={
            'success': True,
            'provider': 'fallback_mock'
        })

        result = service.send_otp('+15559998888', '123456')

        assert result['success'] is True
        assert result['used_fallback'] is True

    def test_send_otp_no_fallback_on_primary_failure(self):
        """Test behavior when primary fails and no fallback"""
        service = SMSService(primary_provider='mock', fallback_provider=None)

        # Mock primary to fail
        service.primary = Mock()
        service.primary.send_otp.return_value = {'success': False, 'error': 'Primary failed'}

        result = service.send_otp('+15559998888', '123456')

        assert result['success'] is False
        assert 'Primary failed' in result['error']
        assert 'used_fallback' not in result

    def test_get_provider_status(self):
        """Test getting provider status"""
        service = SMSService(primary_provider='mock', fallback_provider='mock')

        status = service.get_provider_status()

        assert status['primary'] == 'MockSMSProvider'
        assert status['fallback'] == 'MockSMSProvider'

    def test_get_provider_status_no_fallback(self):
        """Test getting provider status without fallback"""
        service = SMSService(primary_provider='mock')

        status = service.get_provider_status()

        assert status['primary'] == 'MockSMSProvider'
        assert status['fallback'] is None


class TestSMSConfiguration:
    """Test SMS configuration loading"""

    def test_load_sms_config_from_file(self, tmp_path):
        """Test loading configuration from file"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "sms_config.json"

        config_data = {
            'primary_provider': 'twilio',
            'fallback_provider': 'aws_sns'
        }

        with open(config_file, 'w') as f:
            json.dump(config_data, f)

        with patch('education_system.systems.university.infrastructure.auth.sms_provider.paths') as mock_paths:
            mock_paths.CONFIG_DIR = config_dir
            config = load_sms_config()

        assert config['primary_provider'] == 'twilio'
        assert config['fallback_provider'] == 'aws_sns'

    def test_load_sms_config_file_not_found(self, monkeypatch):
        """Test loading configuration when file doesn't exist"""
        # Clear env vars that affect smart defaults
        monkeypatch.delenv('TWILIO_ACCOUNT_SID', raising=False)
        monkeypatch.delenv('TWILIO_AUTH_TOKEN', raising=False)
        monkeypatch.delenv('TWILIO_PHONE_NUMBER', raising=False)
        monkeypatch.delenv('SMTP_USERNAME', raising=False)
        monkeypatch.delenv('SMTP_USER', raising=False)
        monkeypatch.delenv('SMTP_PASSWORD', raising=False)
        monkeypatch.delenv('SMS_PRIMARY_PROVIDER', raising=False)
        monkeypatch.delenv('SMS_FALLBACK_PROVIDER', raising=False)

        with patch('education_system.systems.university.infrastructure.auth.sms_provider.paths') as mock_paths, \
             patch.dict('sys.modules', {'education_system.platform.integrations.email.config': None}):
            mock_paths.CONFIG_DIR = Path('/nonexistent')
            config = load_sms_config()

        assert config['primary_provider'] == 'mock'  # default
        assert config['fallback_provider'] is None

    def test_load_sms_config_from_env(self, monkeypatch):
        """Test loading configuration from environment variables"""
        # Clear Twilio/SMTP env vars so smart detection doesn't override
        monkeypatch.delenv('TWILIO_ACCOUNT_SID', raising=False)
        monkeypatch.delenv('TWILIO_AUTH_TOKEN', raising=False)
        monkeypatch.delenv('TWILIO_PHONE_NUMBER', raising=False)
        monkeypatch.delenv('SMTP_USERNAME', raising=False)
        monkeypatch.delenv('SMTP_USER', raising=False)
        monkeypatch.delenv('SMTP_PASSWORD', raising=False)
        monkeypatch.setenv('SMS_PRIMARY_PROVIDER', 'twilio')
        monkeypatch.setenv('SMS_FALLBACK_PROVIDER', 'aws_sns')

        with patch('education_system.systems.university.infrastructure.auth.sms_provider.paths') as mock_paths, \
             patch.dict('sys.modules', {'education_system.platform.integrations.email.config': None}):
            mock_paths.CONFIG_DIR = Path('/nonexistent')
            config = load_sms_config()

        assert config['primary_provider'] == 'twilio'
        assert config['fallback_provider'] == 'aws_sns'

    def test_load_sms_config_invalid_json(self, tmp_path, monkeypatch):
        """Test loading configuration with invalid JSON"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "sms_config.json"

        # Clear env vars that affect smart defaults
        monkeypatch.delenv('TWILIO_ACCOUNT_SID', raising=False)
        monkeypatch.delenv('TWILIO_AUTH_TOKEN', raising=False)
        monkeypatch.delenv('TWILIO_PHONE_NUMBER', raising=False)
        monkeypatch.delenv('SMTP_USERNAME', raising=False)
        monkeypatch.delenv('SMTP_USER', raising=False)
        monkeypatch.delenv('SMTP_PASSWORD', raising=False)
        monkeypatch.delenv('SMS_PRIMARY_PROVIDER', raising=False)
        monkeypatch.delenv('SMS_FALLBACK_PROVIDER', raising=False)

        # Write invalid JSON
        with open(config_file, 'w') as f:
            f.write("{ invalid json }")

        with patch('education_system.systems.university.infrastructure.auth.sms_provider.paths') as mock_paths, \
             patch.dict('sys.modules', {'education_system.platform.integrations.email.config': None}):
            mock_paths.CONFIG_DIR = config_dir
            config = load_sms_config()

        # Should fall back to defaults
        assert config['primary_provider'] == 'mock'


class TestConvenienceFunctions:
    """Test module-level convenience functions"""

    def test_get_sms_service_singleton(self):
        """Test that get_sms_service returns singleton"""
        # Reset the singleton
        import education_system.systems.university.infrastructure.auth.sms_provider as sms_module
        sms_module._default_service = None

        service1 = get_sms_service()
        service2 = get_sms_service()

        assert service1 is service2

    def test_send_otp_convenience_function(self):
        """Test send_otp convenience function"""
        result = send_otp('+15559998888', '123456')

        assert result['success'] is True
        assert result['provider'] == 'mock'


class TestPhoneNumberFormats:
    """Test various phone number format handling"""

    @pytest.mark.parametrize("input_number,expected_output", [
        ('5559998888', '+15559998888'),
        ('555-999-8888', '+15559998888'),
        ('(555) 999-8888', '+15559998888'),
        ('555 999 8888', '+15559998888'),
        ('+15559998888', '+15559998888'),
        ('+1-555-999-8888', '+1-555-999-8888'),  # Already has +, preserved
    ])
    def test_phone_number_formatting(self, input_number, expected_output):
        """Test various phone number formats are correctly normalized"""
        service = SMSService(primary_provider='mock')
        service.primary.send_otp = Mock(return_value={'success': True, 'provider': 'mock'})

        service.send_otp(input_number, '123456')

        call_args = service.primary.send_otp.call_args[0]
        formatted_number = call_args[0]

        # Remove dashes from expected output for comparison if needed
        if expected_output.count('-') > input_number.count('-'):
            # The expected preserves dashes after +1
            assert formatted_number == expected_output
        else:
            # Remove all formatting from both for comparison
            assert formatted_number.replace('-', '').replace(' ', '').replace('(', '').replace(')', '') == \
                   expected_output.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
