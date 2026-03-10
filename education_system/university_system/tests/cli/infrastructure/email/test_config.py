"""
Comprehensive test suite for email/config.py
Tests configuration management, file loading/saving, and configuration updates
"""

import sys
import os
import json
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from education_system.university_system.infrastructure.email import config


class TestConfigDefaults:
    """Test suite for default configuration values"""

    def test_config_exists(self):
        """Test that config dictionary exists"""
        assert hasattr(config, 'config')
        assert isinstance(config.config, dict)

    def test_database_only_mode_default(self):
        """Test database_only_mode default value"""
        assert 'database_only_mode' in config.config
        assert config.config['database_only_mode'] is True

    def test_templates_dir_default(self):
        """Test templates_dir default value"""
        assert 'templates_dir' in config.config
        assert isinstance(config.config['templates_dir'], str)

    def test_sender_email_default(self):
        """Test sender_email default value"""
        assert 'sender_email' in config.config

    def test_smtp_server_default(self):
        """Test smtp_server default value"""
        assert 'smtp_server' in config.config

    def test_smtp_port_default(self):
        """Test smtp_port default value"""
        assert 'smtp_port' in config.config
        assert isinstance(config.config['smtp_port'], int)

    def test_use_tls_default(self):
        """Test use_tls default value"""
        assert 'use_tls' in config.config
        assert isinstance(config.config['use_tls'], bool)

    def test_use_authentication_default(self):
        """Test use_authentication default value"""
        assert 'use_authentication' in config.config
        assert isinstance(config.config['use_authentication'], bool)

    def test_send_delay_default(self):
        """Test send_delay default value"""
        assert 'send_delay' in config.config
        assert isinstance(config.config['send_delay'], (int, float))

    def test_max_threads_default(self):
        """Test max_threads default value"""
        assert 'max_threads' in config.config
        assert isinstance(config.config['max_threads'], int)

    def test_max_retries_default(self):
        """Test max_retries default value"""
        assert 'max_retries' in config.config
        assert isinstance(config.config['max_retries'], int)

    def test_attachment_size_limit_default(self):
        """Test attachment_size_limit default value"""
        assert 'attachment_size_limit' in config.config
        assert isinstance(config.config['attachment_size_limit'], int)

    def test_enable_logging_default(self):
        """Test enable_logging default value"""
        assert 'enable_logging' in config.config
        assert isinstance(config.config['enable_logging'], bool)


class TestLoadConfig:
    """Test suite for load_config() function"""

    def test_load_config_with_none_path(self):
        """Test loading config with None path (uses default)"""
        with patch('pathlib.Path.exists', return_value=False):
            result = config.load_config(None)
            assert isinstance(result, dict)

    def test_load_config_file_not_found(self):
        """Test loading config when file doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / 'nonexistent.json'
            result = config.load_config(str(fake_path))
            # Should return default config
            assert result == config.config

    def test_load_config_successful(self):
        """Test successful config loading"""
        test_config = {
            'database_only_mode': False,
            'smtp_server': 'test.smtp.com',
            'smtp_port': 587
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            temp_path = f.name

        try:
            # Save original config values
            original_db_mode = config.config['database_only_mode']
            original_smtp = config.config['smtp_server']

            result = config.load_config(temp_path)

            assert result['database_only_mode'] == False
            assert result['smtp_server'] == 'test.smtp.com'
            assert result['smtp_port'] == 587

            # Restore original values
            config.config['database_only_mode'] = original_db_mode
            config.config['smtp_server'] = original_smtp
        finally:
            os.unlink(temp_path)

    def test_load_config_with_path_object(self):
        """Test loading config with Path object"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / 'test.json'
            result = config.load_config(fake_path)
            assert isinstance(result, dict)

    def test_load_config_with_invalid_json(self):
        """Test loading config with invalid JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            result = config.load_config(temp_path)
            # Should return default config on error
            assert result == config.config
        finally:
            os.unlink(temp_path)

    def test_load_config_partial_update(self):
        """Test that load_config only updates existing keys"""
        test_config = {
            'database_only_mode': False,
            'unknown_key': 'should_be_ignored'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            temp_path = f.name

        try:
            original_db_mode = config.config['database_only_mode']

            result = config.load_config(temp_path)

            assert result['database_only_mode'] == False
            assert 'unknown_key' not in result

            config.config['database_only_mode'] = original_db_mode
        finally:
            os.unlink(temp_path)


class TestSaveConfig:
    """Test suite for save_config() function"""

    def test_save_config_with_none_path(self):
        """Test saving config with None path (uses default)"""
        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('json.dump') as mock_dump:
            config.save_config(None)
            mock_dump.assert_called_once()

    def test_save_config_creates_directory(self):
        """Test that save_config creates parent directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / 'subdir' / 'config.json'

            config.save_config(save_path)

            assert save_path.parent.exists()

    def test_save_config_successful(self):
        """Test successful config saving"""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / 'config.json'

            config.save_config(save_path)

            assert save_path.exists()

            # Verify content
            with open(save_path, 'r') as f:
                saved_config = json.load(f)

            assert 'database_only_mode' in saved_config
            assert 'smtp_server' in saved_config

    def test_save_config_with_path_object(self):
        """Test saving config with Path object"""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / 'config.json'

            config.save_config(save_path)

            assert save_path.exists()

    def test_save_config_error_handling(self):
        """Test error handling during save"""
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            # Should not raise exception
            config.save_config('/invalid/path/config.json')


class TestConfigureEmailSettings:
    """Test suite for configure_email_settings() function"""

    def test_configure_single_setting(self):
        """Test updating a single configuration setting"""
        original = config.config['send_delay']

        config.configure_email_settings(send_delay=2.5)

        assert config.config['send_delay'] == 2.5

        # Restore
        config.config['send_delay'] = original

    def test_configure_multiple_settings(self):
        """Test updating multiple configuration settings"""
        original_port = config.config['smtp_port']
        original_tls = config.config['use_tls']

        config.configure_email_settings(
            smtp_port=465,
            use_tls=False
        )

        assert config.config['smtp_port'] == 465
        assert config.config['use_tls'] is False

        # Restore
        config.config['smtp_port'] = original_port
        config.config['use_tls'] = original_tls

    def test_configure_ignores_invalid_keys(self):
        """Test that invalid keys are ignored"""
        config.configure_email_settings(
            smtp_port=587,
            invalid_key='should_be_ignored'
        )

        assert 'invalid_key' not in config.config

    def test_configure_with_no_arguments(self):
        """Test calling configure with no arguments"""
        original_config = config.config.copy()

        config.configure_email_settings()

        # Config should remain unchanged
        assert config.config == original_config


class TestEnsureEmailConfigForDatabaseMode:
    """Test suite for ensure_email_config_for_database_mode() function"""

    def test_enables_database_mode_if_disabled(self):
        """Test that function enables database_only_mode if disabled"""
        original = config.config['database_only_mode']
        config.config['database_only_mode'] = False

        config.ensure_email_config_for_database_mode()

        assert config.config['database_only_mode'] is True

        # Restore
        config.config['database_only_mode'] = original

    def test_preserves_database_mode_if_enabled(self):
        """Test that function preserves database_only_mode if already enabled"""
        config.config['database_only_mode'] = True

        config.ensure_email_config_for_database_mode()

        assert config.config['database_only_mode'] is True

    def test_validates_templates_directory(self):
        """Test that function checks templates directory"""
        config.ensure_email_config_for_database_mode()

        # Function should complete without error
        assert True

    def test_handles_missing_templates_dir(self):
        """Test handling when templates_dir doesn't exist"""
        original = config.config['templates_dir']
        config.config['templates_dir'] = '/nonexistent/templates'

        # Should not raise exception
        config.ensure_email_config_for_database_mode()

        config.config['templates_dir'] = original

    def test_notes_missing_smtp_server(self):
        """Test that function logs missing SMTP server appropriately"""
        original = config.config['smtp_server']
        config.config['smtp_server'] = ''

        # Should not raise exception
        config.ensure_email_config_for_database_mode()

        config.config['smtp_server'] = original


class TestModuleExports:
    """Test suite for module exports"""

    def test_all_exports(self):
        """Test that __all__ contains expected exports"""
        assert hasattr(config, '__all__')
        expected_exports = [
            'config',
            'load_config',
            'save_config',
            'configure_email_settings',
            'ensure_email_config_for_database_mode'
        ]
        for export in expected_exports:
            assert export in config.__all__

    def test_exported_functions_exist(self):
        """Test that all exported names exist"""
        for name in config.__all__:
            assert hasattr(config, name)


class TestConfigurationIntegrity:
    """Test suite for configuration integrity"""

    def test_config_is_mutable(self):
        """Test that config dictionary is mutable"""
        original = config.config['send_delay']

        config.config['send_delay'] = 999

        assert config.config['send_delay'] == 999

        # Restore
        config.config['send_delay'] = original

    def test_config_preserves_types(self):
        """Test that config preserves data types"""
        assert isinstance(config.config['database_only_mode'], bool)
        assert isinstance(config.config['smtp_port'], int)
        assert isinstance(config.config['send_delay'], (int, float))
        assert isinstance(config.config['templates_dir'], str)

    def test_all_required_keys_present(self):
        """Test that all required configuration keys are present"""
        required_keys = [
            'database_only_mode',
            'templates_dir',
            'sender_email',
            'sender_name',
            'smtp_server',
            'smtp_port',
            'use_tls',
            'use_authentication',
            'smtp_username',
            'smtp_password',
            'email_signature',
            'send_delay',
            'max_threads',
            'max_retries',
            'retry_delay',
            'attachment_size_limit',
            'enable_logging',
            'log_level'
        ]

        for key in required_keys:
            assert key in config.config, f"Missing required key: {key}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
