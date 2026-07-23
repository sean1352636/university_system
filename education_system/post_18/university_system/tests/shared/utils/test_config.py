"""
Comprehensive tests for config.py

Tests email configuration management, validation,
loading/saving, and interactive configuration.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch, mock_open, call
from pathlib import Path


class _PathProxy:
    def __init__(self, path):
        self._path = Path(path)
        self.exists = MagicMock(return_value=self._path.exists())
        self.parent = MagicMock()
        self.parent.mkdir = MagicMock()

    def __fspath__(self):
        return str(self._path)

    def __str__(self):
        return str(self._path)


@pytest.fixture
def mock_paths():
    """Mock paths module"""
    with patch('education_system.post_18.university_system.modules.shared.utils.config.paths') as mock:
        mock.EMAIL_CONFIG_PATH = _PathProxy('/tmp/email_config.json')
        mock.EMAIL_TEMPLATES_DIR = Path('/tmp/templates')
        yield mock


@pytest.fixture
def sample_config():
    """Sample valid configuration"""
    return {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender_email": "test@university.edu",
        "sender_name": "Test University",
        "use_tls": True,
        "use_authentication": True,
        "username": "testuser",
        "password": "testpass",
        "email_signature": "\n\nRegards,\nTest University",
        "send_delay": 1.0,
        "max_threads": 1,
        "templates_dir": "/tmp/templates",
        "database_only_mode": True
    }


class TestEmailConfigValidation:
    """Test email configuration validation"""

    def test_validate_email_config_valid(self, sample_config):
        """Test validation with valid config"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_email_config

        errors = validate_email_config(sample_config)
        assert len(errors) == 0

    def test_validate_email_config_missing_sender_email(self, sample_config):
        """Test validation with missing sender_email"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_email_config

        sample_config['sender_email'] = ''
        errors = validate_email_config(sample_config)

        assert len(errors) > 0
        assert any('sender_email' in error for error in errors)

    def test_validate_email_config_missing_sender_name(self, sample_config):
        """Test validation with missing sender_name"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_email_config

        sample_config['sender_name'] = ''
        errors = validate_email_config(sample_config)

        assert len(errors) > 0
        assert any('sender_name' in error for error in errors)

    def test_validate_email_config_invalid_email_format(self, sample_config):
        """Test validation with invalid email format"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_email_config

        sample_config['sender_email'] = 'invalid-email'
        errors = validate_email_config(sample_config)

        assert len(errors) > 0
        assert any('email format' in error.lower() for error in errors)

    def test_validate_email_config_smtp_mode_missing_server(self, sample_config):
        """Test validation in SMTP mode with missing server"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_email_config

        sample_config['database_only_mode'] = False
        sample_config['smtp_server'] = ''
        errors = validate_email_config(sample_config)

        assert len(errors) > 0
        assert any('smtp_server' in error for error in errors)

    def test_validate_email_config_smtp_mode_invalid_port(self, sample_config):
        """Test validation with invalid SMTP port"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_email_config

        sample_config['database_only_mode'] = False
        sample_config['smtp_port'] = 70000  # Invalid port

        errors = validate_email_config(sample_config)

        assert len(errors) > 0
        assert any('port' in error.lower() for error in errors)

    def test_validate_email_config_smtp_mode_negative_port(self, sample_config):
        """Test validation with negative SMTP port"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_email_config

        sample_config['database_only_mode'] = False
        sample_config['smtp_port'] = -1

        errors = validate_email_config(sample_config)

        assert len(errors) > 0

    def test_validate_email_config_database_mode_skips_smtp(self, sample_config):
        """Test validation in database mode skips SMTP checks"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_email_config

        sample_config['database_only_mode'] = True
        sample_config['smtp_server'] = ''  # Missing but should be OK in database mode

        errors = validate_email_config(sample_config)

        # Should only complain about sender_email/sender_name if missing
        assert not any('smtp_server' in error for error in errors)


class TestConfigLoading:
    """Test configuration loading"""

    @patch('builtins.open', new_callable=mock_open)
    def test_load_config_success(self, mock_file, mock_paths, sample_config):
        """Test successful config loading"""
        from education_system.post_18.university_system.modules.shared.utils.config import load_config, config

        # Mock file read
        mock_file.return_value.read.return_value = json.dumps(sample_config)
        mock_paths.EMAIL_CONFIG_PATH.exists.return_value = True

        with patch('json.load', return_value=sample_config):
            result = load_config()

        assert result is not None
        assert result['smtp_server'] == 'smtp.gmail.com'
        # Check forced settings
        assert result['max_threads'] == 1
        assert result['send_delay'] >= 2.0

    @patch('education_system.post_18.university_system.modules.shared.utils.config.save_config')
    def test_load_config_file_not_found(self, mock_save, mock_paths):
        """Test loading config when file doesn't exist"""
        from education_system.post_18.university_system.modules.shared.utils.config import load_config

        mock_paths.EMAIL_CONFIG_PATH.exists.return_value = False

        result = load_config()

        assert result is not None
        mock_save.assert_called_once()  # Should save defaults

    @patch('builtins.open', side_effect=Exception("Read error"))
    def test_load_config_read_error(self, mock_file, mock_paths):
        """Test loading config with read error"""
        from education_system.post_18.university_system.modules.shared.utils.config import load_config

        mock_paths.EMAIL_CONFIG_PATH.exists.return_value = True

        result = load_config()

        # Should still return config (with defaults)
        assert result is not None

    def test_load_config_forces_single_thread(self, mock_paths, sample_config):
        """Test that load_config forces single thread"""
        from education_system.post_18.university_system.modules.shared.utils.config import load_config

        sample_config['max_threads'] = 10  # Try to set multiple threads
        mock_paths.EMAIL_CONFIG_PATH.exists.return_value = True

        with patch('builtins.open', mock_open(read_data=json.dumps(sample_config))):
            with patch('json.load', return_value=sample_config):
                result = load_config()

        # Should be forced to 1
        assert result['max_threads'] == 1

    def test_load_config_enforces_minimum_delay(self, mock_paths, sample_config):
        """Test that load_config enforces minimum delay"""
        from education_system.post_18.university_system.modules.shared.utils.config import load_config

        sample_config['send_delay'] = 0.1  # Try to set very small delay
        mock_paths.EMAIL_CONFIG_PATH.exists.return_value = True

        with patch('builtins.open', mock_open(read_data=json.dumps(sample_config))):
            with patch('json.load', return_value=sample_config):
                result = load_config()

        # Should be forced to at least 2.0
        assert result['send_delay'] >= 2.0


class TestConfigSaving:
    """Test configuration saving"""

    @patch('builtins.open', new_callable=mock_open)
    def test_save_config_success(self, mock_file, mock_paths, sample_config):
        """Test successful config saving"""
        from education_system.post_18.university_system.modules.shared.utils.config import save_config, config

        mock_paths.EMAIL_CONFIG_PATH.parent.mkdir = MagicMock()

        # Set config
        config.update(sample_config)

        with patch('json.dump') as mock_dump:
            result = save_config()

        assert result is True
        mock_dump.assert_called_once()

    @patch('builtins.open', new_callable=mock_open)
    def test_save_config_strips_password(self, mock_file, mock_paths, sample_config):
        """Test that save_config strips password by default"""
        from education_system.post_18.university_system.modules.shared.utils.config import save_config, config

        mock_paths.EMAIL_CONFIG_PATH.parent.mkdir = MagicMock()
        config.update(sample_config)
        config['save_password'] = False

        with patch('json.dump') as mock_dump:
            save_config()

        # Check that dumped config has empty password
        call_args = mock_dump.call_args[0][0]
        assert call_args['password'] == ''

    @patch('builtins.open', new_callable=mock_open)
    def test_save_config_saves_password_if_requested(self, mock_file, mock_paths, sample_config):
        """Test that save_config saves password if requested"""
        from education_system.post_18.university_system.modules.shared.utils.config import save_config, config

        mock_paths.EMAIL_CONFIG_PATH.parent.mkdir = MagicMock()
        config.update(sample_config)
        config['save_password'] = True

        with patch('json.dump') as mock_dump:
            save_config()

        # Check that dumped config has password
        call_args = mock_dump.call_args[0][0]
        assert call_args['password'] == 'testpass'

    @patch('builtins.open', side_effect=Exception("Write error"))
    def test_save_config_write_error(self, mock_file, mock_paths):
        """Test save_config with write error"""
        from education_system.post_18.university_system.modules.shared.utils.config import save_config

        mock_paths.EMAIL_CONFIG_PATH.parent.mkdir = MagicMock()

        result = save_config()

        assert result is False


class TestConfigValidation:
    """Test validate_config function"""

    @patch('jsonschema.validate')
    def test_validate_config_success(self, mock_validate, sample_config):
        """Test successful config validation"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_config, config

        config.update(sample_config)
        config['database_only_mode'] = True

        result = validate_config()

        assert result is True
        mock_validate.assert_called_once()

    @patch('jsonschema.validate', side_effect=Exception("Schema error"))
    def test_validate_config_schema_error(self, mock_validate, sample_config):
        """Test validate_config with schema validation error"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_config, config

        config.update(sample_config)

        result = validate_config()

        assert result is False

    @patch('builtins.open', new_callable=mock_open)
    @patch('jsonschema.validate')
    def test_validate_config_from_file(self, mock_validate, mock_file, sample_config):
        """Test validating config from file"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_config

        with patch('json.load', return_value=sample_config):
            result = validate_config('/tmp/test_config.json')

        assert result is True

    @patch('jsonschema.validate')
    def test_validate_config_database_mode_skips_smtp(self, mock_validate, sample_config):
        """Test that database mode skips SMTP validation"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_config, config

        config.update(sample_config)
        config['database_only_mode'] = True

        result = validate_config()

        assert result is True
        # Should not try to connect to SMTP

    @patch('jsonschema.validate')
    def test_validate_config_smtp_mode_missing_credentials(self, mock_validate, sample_config):
        """Test SMTP mode with missing credentials"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_config, config

        config.update(sample_config)
        config['database_only_mode'] = False
        config['use_authentication'] = True
        config['username'] = ''
        config['password'] = ''

        result = validate_config()

        assert result is False

    @patch('jsonschema.validate')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.send_email_via_smtp')
    def test_validate_config_smtp_test_success(self, mock_smtp, mock_validate, sample_config):
        """Test SMTP connection test succeeds"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_config, config

        config.update(sample_config)
        config['database_only_mode'] = False

        mock_smtp.return_value = True

        result = validate_config()

        assert result is True
        mock_smtp.assert_called_once()

    @patch('jsonschema.validate')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.send_email_via_smtp')
    def test_validate_config_smtp_test_failure(self, mock_smtp, mock_validate, sample_config):
        """Test SMTP connection test fails"""
        from education_system.post_18.university_system.modules.shared.utils.config import validate_config, config

        config.update(sample_config)
        config['database_only_mode'] = False

        mock_smtp.return_value = False

        result = validate_config()

        assert result is False


class TestInteractiveConfiguration:
    """Test interactive configuration function"""

    @patch('builtins.input')
    @patch('education_system.post_18.university_system.modules.shared.utils.config.save_config')
    def test_configure_email_settings_database_mode(self, mock_save, mock_input, sample_config):
        """Test configuring email settings in database mode"""
        from education_system.post_18.university_system.modules.shared.utils.config import configure_email_settings, config

        config.update(sample_config)

        # Simulate user input
        mock_input.side_effect = [
            '1',  # Database mode
            'test@university.edu',  # Sender email
            'Test University',  # Sender name
            '',  # Keep current signature
            '',  # Keep current delay
            ''   # Keep current threads
        ]

        configure_email_settings()

        assert config['database_only_mode'] is True
        mock_save.assert_called_once()

    @patch('builtins.input')
    @patch('education_system.post_18.university_system.modules.shared.utils.config.save_config')
    @patch('education_system.post_18.university_system.modules.shared.utils.config.validate_config')
    @patch('education_system.post_18.university_system.modules.shared.utils.config.test_email_configuration')
    def test_configure_email_settings_smtp_mode(self, mock_test, mock_validate, mock_save, mock_input, sample_config):
        """Test configuring email settings in SMTP mode"""
        from education_system.post_18.university_system.modules.shared.utils.config import configure_email_settings, config

        config.update(sample_config)

        # Simulate user input
        mock_input.side_effect = [
            '2',  # SMTP mode
            'smtp.gmail.com',  # SMTP server
            '587',  # SMTP port
            'y',  # Use TLS
            'y',  # Use auth
            'testuser',  # Username
            'testpass',  # Password
            'n',  # Don't save password
            'sender@university.edu',  # Sender email
            'Test University',  # Sender name
            '',  # Keep signature
            '',  # Keep delay
            '',  # Keep threads
            'n'   # Don't send test email
        ]

        mock_validate.return_value = True

        configure_email_settings()

        assert config['database_only_mode'] is False
        assert config['smtp_server'] == 'smtp.gmail.com'
        mock_validate.assert_called_once()

    @patch('builtins.input')
    @patch('education_system.post_18.university_system.modules.shared.utils.config.save_config')
    def test_configure_email_settings_invalid_port(self, mock_save, mock_input, sample_config, capsys):
        """Test configuring with invalid port"""
        from education_system.post_18.university_system.modules.shared.utils.config import configure_email_settings, config

        config.update(sample_config)
        original_port = config['smtp_port']

        mock_input.side_effect = [
            '2',  # SMTP mode
            '',  # Keep server
            'invalid',  # Invalid port
            '',  # Keep TLS
            '',  # Keep auth
            '',  # Sender email
            '',  # Sender name
            '',  # Signature
            '',  # Delay
            '',  # Threads
            'n'  # No test
        ]

        configure_email_settings()

        # Port should remain unchanged
        assert config['smtp_port'] == original_port

    @patch('builtins.input')
    @patch('education_system.post_18.university_system.modules.shared.utils.config.save_config')
    def test_configure_email_settings_out_of_range_port(self, mock_save, mock_input, sample_config):
        """Test configuring with out-of-range port"""
        from education_system.post_18.university_system.modules.shared.utils.config import configure_email_settings, config

        config.update(sample_config)
        original_port = config['smtp_port']

        mock_input.side_effect = [
            '2',  # SMTP mode
            '',  # Keep server
            '70000',  # Out of range port
            '',  # Keep TLS
            '',  # Keep auth
            '',  # Sender email
            '',  # Sender name
            '',  # Signature
            '',  # Delay
            '',  # Threads
            'n'  # No test
        ]

        configure_email_settings()

        # Port should remain unchanged
        assert config['smtp_port'] == original_port

    @patch('builtins.input')
    @patch('education_system.post_18.university_system.modules.shared.utils.config.save_config')
    def test_configure_email_settings_invalid_delay(self, mock_save, mock_input, sample_config):
        """Test configuring with invalid delay"""
        from education_system.post_18.university_system.modules.shared.utils.config import configure_email_settings, config

        config.update(sample_config)
        original_delay = config['send_delay']

        mock_input.side_effect = [
            '1',  # Database mode
            '',  # Sender email
            '',  # Sender name
            '',  # Signature
            'invalid',  # Invalid delay
            ''   # Threads
        ]

        configure_email_settings()

        # Delay should remain unchanged
        assert config['send_delay'] == original_delay

    @patch('builtins.input')
    @patch('education_system.post_18.university_system.modules.shared.utils.config.save_config')
    def test_configure_email_settings_negative_delay(self, mock_save, mock_input, sample_config):
        """Test configuring with negative delay"""
        from education_system.post_18.university_system.modules.shared.utils.config import configure_email_settings, config

        config.update(sample_config)
        original_delay = config['send_delay']

        mock_input.side_effect = [
            '1',  # Database mode
            '',  # Sender email
            '',  # Sender name
            '',  # Signature
            '-1.0',  # Negative delay
            ''   # Threads
        ]

        configure_email_settings()

        # Delay should remain unchanged
        assert config['send_delay'] == original_delay

    @patch('builtins.input')
    @patch('education_system.post_18.university_system.modules.shared.utils.config.save_config')
    @patch('education_system.post_18.university_system.modules.shared.utils.config.test_email_configuration')
    @patch('education_system.post_18.university_system.modules.shared.utils.config.validate_config')
    def test_configure_email_settings_with_test_email(self, mock_validate, mock_test, mock_save, mock_input, sample_config):
        """Test configuring with test email"""
        from education_system.post_18.university_system.modules.shared.utils.config import configure_email_settings, config

        config.update(sample_config)

        mock_input.side_effect = [
            '2',  # SMTP mode
            '',  # Server
            '',  # Port
            '',  # TLS
            '',  # Auth
            '',  # Username
            '',  # Password
            '',  # Save password
            '',  # Sender email
            '',  # Sender name
            '',  # Signature
            '',  # Delay
            '',  # Threads
            'y',  # Send test
            'test@example.com'  # Test recipient
        ]

        mock_validate.return_value = True

        configure_email_settings()

        mock_test.assert_called_once_with('test@example.com')


class TestEmailConfiguration:
    """Test test_email_configuration function"""

    @patch('education_system.post_18.university_system.modules.shared.utils.email_service.send_email')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.render_template')
    def test_test_email_configuration_success(self, mock_render, mock_send, sample_config):
        """Test sending test email successfully"""
        from education_system.post_18.university_system.modules.shared.utils.config import test_email_configuration, config

        config.update(sample_config)

        mock_render.return_value = ('Test Subject', 'Test Body')
        mock_send.return_value = True

        result = test_email_configuration('test@example.com')

        assert result is True
        mock_send.assert_called_once()

    @patch('education_system.post_18.university_system.modules.shared.utils.email_service.send_email')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.render_template')
    def test_test_email_configuration_no_recipient(self, mock_render, mock_send, sample_config):
        """Test sending test email to self when no recipient"""
        from education_system.post_18.university_system.modules.shared.utils.config import test_email_configuration, config

        config.update(sample_config)

        mock_render.return_value = ('Test Subject', 'Test Body')
        mock_send.return_value = True

        result = test_email_configuration()

        assert result is True
        # Should send to sender_email
        call_args = mock_send.call_args
        assert call_args[0][0] == config['sender_email']

    @patch('education_system.post_18.university_system.modules.shared.utils.email_service.send_email')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.render_template')
    def test_test_email_configuration_template_error(self, mock_render, mock_send, sample_config):
        """Test test email with template rendering error"""
        from education_system.post_18.university_system.modules.shared.utils.config import test_email_configuration, config

        config.update(sample_config)

        mock_render.side_effect = Exception("Template error")
        mock_send.return_value = True

        result = test_email_configuration('test@example.com')

        # Should fallback to hardcoded message
        assert result is True
        mock_send.assert_called_once()

    @patch('education_system.post_18.university_system.modules.shared.utils.email_service.send_email')
    def test_test_email_configuration_no_sender(self, mock_send):
        """Test test email with no sender configured"""
        from education_system.post_18.university_system.modules.shared.utils.config import test_email_configuration, config

        config['sender_email'] = ''

        result = test_email_configuration('test@example.com')

        assert result is False
        mock_send.assert_not_called()

    @patch('education_system.post_18.university_system.modules.shared.utils.email_service.send_email')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.render_template')
    def test_test_email_configuration_send_failure(self, mock_render, mock_send, sample_config):
        """Test test email send failure"""
        from education_system.post_18.university_system.modules.shared.utils.config import test_email_configuration, config

        config.update(sample_config)

        mock_render.return_value = ('Test Subject', 'Test Body')
        mock_send.return_value = False

        result = test_email_configuration('test@example.com')

        assert result is False


class TestEnsureDatabaseMode:
    """Test ensure_email_config_for_database_mode function"""

    def test_ensure_database_mode_sets_defaults(self):
        """Test that ensure function sets defaults in database mode"""
        from education_system.post_18.university_system.modules.shared.utils.config import ensure_email_config_for_database_mode, config

        config['database_only_mode'] = True
        config['sender_email'] = ''
        config['sender_name'] = ''

        result = ensure_email_config_for_database_mode()

        assert result is True
        assert config['sender_email'] == 'noreply@university.edu'
        assert config['sender_name'] == 'University System'

    def test_ensure_database_mode_keeps_existing(self):
        """Test that ensure function keeps existing values"""
        from education_system.post_18.university_system.modules.shared.utils.config import ensure_email_config_for_database_mode, config

        config['database_only_mode'] = True
        config['sender_email'] = 'custom@example.com'
        config['sender_name'] = 'Custom Name'

        ensure_email_config_for_database_mode()

        assert config['sender_email'] == 'custom@example.com'
        assert config['sender_name'] == 'Custom Name'

    def test_ensure_database_mode_not_in_database_mode(self):
        """Test ensure function when not in database mode"""
        from education_system.post_18.university_system.modules.shared.utils.config import ensure_email_config_for_database_mode, config

        config['database_only_mode'] = False
        original_email = config.get('sender_email', '')

        ensure_email_config_for_database_mode()

        # Should not modify in SMTP mode
        if original_email:
            assert config.get('sender_email') == original_email


class TestConfigConstants:
    """Test configuration constants"""

    def test_default_config_has_required_fields(self):
        """Test that DEFAULT_CONFIG has all required fields"""
        from education_system.post_18.university_system.modules.shared.utils.config import DEFAULT_CONFIG

        required_fields = [
            'smtp_server', 'smtp_port', 'sender_email', 'sender_name',
            'use_tls', 'use_authentication', 'database_only_mode'
        ]

        for field in required_fields:
            assert field in DEFAULT_CONFIG

    def test_config_schema_defines_required_fields(self):
        """Test that CONFIG_SCHEMA defines required fields"""
        from education_system.post_18.university_system.modules.shared.utils.config import CONFIG_SCHEMA

        assert 'required' in CONFIG_SCHEMA
        assert 'smtp_server' in CONFIG_SCHEMA['required']
        assert 'smtp_port' in CONFIG_SCHEMA['required']
        assert 'sender_email' in CONFIG_SCHEMA['required']

    def test_config_schema_validates_types(self):
        """Test that CONFIG_SCHEMA validates field types"""
        from education_system.post_18.university_system.modules.shared.utils.config import CONFIG_SCHEMA

        properties = CONFIG_SCHEMA['properties']

        assert properties['smtp_server']['type'] == 'string'
        assert properties['smtp_port']['type'] == 'integer'
        assert properties['use_tls']['type'] == 'boolean'

    def test_config_schema_validates_port_range(self):
        """Test that CONFIG_SCHEMA validates port range"""
        from education_system.post_18.university_system.modules.shared.utils.config import CONFIG_SCHEMA

        port_spec = CONFIG_SCHEMA['properties']['smtp_port']

        assert port_spec['minimum'] == 1
        assert port_spec['maximum'] == 65535


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
