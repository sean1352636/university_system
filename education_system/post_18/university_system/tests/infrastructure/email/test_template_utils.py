"""
Comprehensive test suite for infrastructure/email/template_utils.py
Tests template management, rendering, and file operations with proper mocking
"""

import sys
import os
import json
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from pathlib import Path
from string import Template

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from education_system.post_18.university_system.infrastructure.email import template_utils


@pytest.fixture(autouse=True)
def reset_mapping_cache():
    """Reset the module-level _MAPPING_CACHE between tests"""
    template_utils._MAPPING_CACHE = None
    yield
    template_utils._MAPPING_CACHE = None


class TestDefaultTemplates:
    """Test suite for DEFAULT_TEMPLATES dictionary"""

    def test_default_templates_exists(self):
        """Test that DEFAULT_TEMPLATES dictionary exists"""
        assert hasattr(template_utils, 'DEFAULT_TEMPLATES')
        assert isinstance(template_utils.DEFAULT_TEMPLATES, dict)

    def test_default_templates_empty(self):
        """Test that DEFAULT_TEMPLATES is empty (backward compatibility)"""
        # As per the code comments, templates are now stored as JSON files
        assert template_utils.DEFAULT_TEMPLATES == {}


class TestInitializeAnalyticsTemplates:
    """Test suite for initialize_analytics_templates() function"""

    def test_initialize_analytics_templates_exists(self):
        """Test that initialize_analytics_templates function exists"""
        assert hasattr(template_utils, 'initialize_analytics_templates')
        assert callable(template_utils.initialize_analytics_templates)

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_initialize_analytics_templates_logs_info(self, mock_log):
        """Test that initialize_analytics_templates logs appropriate message"""
        template_utils.initialize_analytics_templates()
        mock_log.assert_called_once()
        args = mock_log.call_args[0]
        assert args[0] == 'info'
        assert 'JSON files' in args[1]


class TestEnsureTemplatesDirectory:
    """Test suite for ensure_templates_directory() function"""

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_ensure_templates_directory_exists(self, mock_log):
        """Test ensure_templates_directory when directory exists"""
        mock_templates_dir = MagicMock()
        mock_templates_dir.exists.return_value = True

        with patch('education_system.post_18.university_system.infrastructure.email.template_utils.paths') as mock_paths:
            mock_paths.EMAIL_TEMPLATES_DIR = mock_templates_dir
            result = template_utils.ensure_templates_directory()

            assert result == mock_templates_dir
            mock_templates_dir.exists.assert_called_once()
            mock_templates_dir.mkdir.assert_not_called()

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_ensure_templates_directory_creates_new(self, mock_log):
        """Test ensure_templates_directory creates directory when missing"""
        mock_templates_dir = MagicMock()
        mock_templates_dir.exists.return_value = False
        mock_templates_dir.__str__ = MagicMock(return_value='/path/to/templates')

        with patch('education_system.post_18.university_system.infrastructure.email.template_utils.paths') as mock_paths:
            mock_paths.EMAIL_TEMPLATES_DIR = mock_templates_dir
            result = template_utils.ensure_templates_directory()

            assert result == mock_templates_dir
            mock_templates_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_log.assert_called()

    def test_ensure_templates_directory_exception_handling(self):
        """Test ensure_templates_directory handles exceptions properly"""
        with patch('education_system.post_18.university_system.infrastructure.email.template_utils.paths') as mock_paths:
            mock_paths.EMAIL_TEMPLATES_DIR = MagicMock()
            mock_paths.EMAIL_TEMPLATES_DIR.exists.side_effect = Exception("Filesystem error")

            # Function is decorated with @handle_exception, so it should return False on error
            result = template_utils.ensure_templates_directory()
            assert result is False


class TestSaveDefaultTemplates:
    """Test suite for save_default_templates() function"""

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_save_default_templates_success(self, mock_log, mock_ensure_dir):
        """Test save_default_templates returns True"""
        mock_dir = MagicMock()
        mock_dir.__str__ = MagicMock(return_value='/templates')
        mock_ensure_dir.return_value = mock_dir

        result = template_utils.save_default_templates()

        assert result is True
        mock_ensure_dir.assert_called_once()
        assert mock_log.call_count >= 1

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    def test_save_default_templates_exception_handling(self, mock_ensure_dir):
        """Test save_default_templates handles exceptions"""
        mock_ensure_dir.side_effect = Exception("Directory error")

        # @handle_exception decorator should catch exception
        result = template_utils.save_default_templates()
        assert result is False


class TestListTemplates:
    """Test suite for list_templates() function"""

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    def test_list_templates_empty_directory(self, mock_ensure_dir):
        """Test list_templates with no template files"""
        mock_dir = MagicMock()
        # iterdir returns no subdirectories
        mock_dir.iterdir.return_value = []
        # glob returns no root-level json files
        mock_dir.glob.return_value = []
        mock_ensure_dir.return_value = mock_dir

        result = template_utils.list_templates()

        assert result == []

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_list_templates_with_files(self, mock_log, mock_ensure_dir):
        """Test list_templates with template files in a category subdirectory"""
        # Create mock template files inside a category dir
        mock_file1 = MagicMock()
        mock_file1.stem = 'welcome_email'
        mock_file1.name = 'welcome_email.json'
        mock_file1.__lt__ = lambda self, other: self.name < other.name
        mock_file2 = MagicMock()
        mock_file2.stem = 'reminder_email'
        mock_file2.name = 'reminder_email.json'
        mock_file2.__lt__ = lambda self, other: self.name < other.name

        mock_category_dir = MagicMock()
        mock_category_dir.is_dir.return_value = True
        mock_category_dir.name = 'general'
        mock_category_dir.glob.return_value = [mock_file1, mock_file2]
        mock_category_dir.__lt__ = lambda self, other: self.name < other.name

        mock_dir = MagicMock()
        mock_dir.iterdir.return_value = [mock_category_dir]
        # No root-level json files
        mock_dir.glob.return_value = []
        mock_ensure_dir.return_value = mock_dir

        # Mock JSON data for template files
        template_data = {
            'subject': 'Test Subject',
            'body': 'This is a test email body with some content'
        }

        with patch('builtins.open', mock_open(read_data=json.dumps(template_data))):
            result = template_utils.list_templates()

        assert len(result) == 2
        assert result[0]['name'] in ['welcome_email', 'reminder_email']
        assert 'subject' in result[0]
        assert 'body_preview' in result[0]
        assert 'is_default' in result[0]
        assert 'category' in result[0]
        assert result[0]['category'] == 'general'

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_list_templates_with_long_body(self, mock_log, mock_ensure_dir):
        """Test list_templates truncates long body preview"""
        mock_file_obj = MagicMock()
        mock_file_obj.stem = 'long_email'
        mock_file_obj.name = 'long_email.json'

        mock_category_dir = MagicMock()
        mock_category_dir.is_dir.return_value = True
        mock_category_dir.name = 'general'
        mock_category_dir.glob.return_value = [mock_file_obj]

        mock_dir = MagicMock()
        mock_dir.iterdir.return_value = [mock_category_dir]
        mock_dir.glob.return_value = []
        mock_ensure_dir.return_value = mock_dir

        # Create template with body > 100 chars
        long_body = 'A' * 150
        template_data = {
            'subject': 'Test',
            'body': long_body
        }

        with patch('builtins.open', mock_open(read_data=json.dumps(template_data))):
            result = template_utils.list_templates()

        assert len(result) == 1
        assert len(result[0]['body_preview']) <= 104  # 100 chars + "..."

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_list_templates_handles_json_error(self, mock_log, mock_ensure_dir):
        """Test list_templates handles invalid JSON gracefully"""
        mock_file = MagicMock()
        mock_file.stem = 'invalid_template'
        mock_file.name = 'invalid_template.json'

        mock_category_dir = MagicMock()
        mock_category_dir.is_dir.return_value = True
        mock_category_dir.name = 'general'
        mock_category_dir.glob.return_value = [mock_file]

        mock_dir = MagicMock()
        mock_dir.iterdir.return_value = [mock_category_dir]
        mock_dir.glob.return_value = []
        mock_ensure_dir.return_value = mock_dir

        with patch('builtins.open', mock_open(read_data='{ invalid json')):
            result = template_utils.list_templates()

            # Should return empty list on JSON error
            assert result == []
            # Should log error
            error_calls = [c for c in mock_log.call_args_list if c[0][0] == 'error']
            assert len(error_calls) > 0


class TestLoadTemplate:
    """Test suite for load_template() function"""

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils._load_mapping')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_load_template_success(self, mock_log, mock_ensure_dir, mock_mapping):
        """Test load_template successfully loads existing template via root (legacy)"""
        mock_mapping.return_value = {}

        mock_dir = MagicMock()
        # iterdir for strategy 3 - no subdirectories
        mock_dir.iterdir.return_value = []
        mock_ensure_dir.return_value = mock_dir

        template_data = {
            'subject': 'Test Subject',
            'body': 'Test Body'
        }

        # Strategy 4: root directory lookup
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = True
        mock_dir.__truediv__ = MagicMock(return_value=mock_template_path)

        with patch('builtins.open', mock_open(read_data=json.dumps(template_data))):
            result = template_utils.load_template('test_template')

        assert result == template_data

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils._load_mapping')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_load_template_not_found(self, mock_log, mock_ensure_dir, mock_mapping):
        """Test load_template returns None when template doesn't exist"""
        mock_mapping.return_value = {}

        mock_dir = MagicMock()
        mock_dir.iterdir.return_value = []
        mock_ensure_dir.return_value = mock_dir

        # All path lookups return non-existent
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_template_path)

        result = template_utils.load_template('nonexistent')

        assert result is None
        # Should log warning
        warning_calls = [c for c in mock_log.call_args_list if c[0][0] == 'warning']
        assert len(warning_calls) > 0

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils._load_mapping')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.DEFAULT_TEMPLATES', {'test_default': {'subject': 'Default', 'body': 'Default body'}})
    def test_load_template_falls_back_to_default(self, mock_log, mock_ensure_dir, mock_mapping):
        """Test load_template falls back to DEFAULT_TEMPLATES"""
        mock_mapping.return_value = {}

        mock_dir = MagicMock()
        mock_dir.iterdir.return_value = []
        mock_ensure_dir.return_value = mock_dir

        # All path lookups return non-existent
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_template_path)

        # Mock the general_dir creation for saving default
        mock_general_dir = MagicMock()
        mock_general_path = MagicMock()
        mock_general_dir.__truediv__ = MagicMock(return_value=mock_general_path)
        # First call is for root lookup, subsequent for general dir
        mock_dir.__truediv__ = MagicMock(side_effect=lambda arg: mock_general_dir if arg == "general" else mock_template_path)

        with patch('builtins.open', mock_open()):
            result = template_utils.load_template('test_default')

        assert result is not None
        assert result['subject'] == 'Default'
        assert result['body'] == 'Default body'

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils._load_mapping')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.DEFAULT_TEMPLATES', {'test_default': {'subject': 'Default', 'body': 'Default body'}})
    @patch('builtins.open', new_callable=mock_open)
    def test_load_template_saves_default_on_first_use(self, mock_file, mock_log, mock_ensure_dir, mock_mapping):
        """Test load_template saves default template on first use"""
        mock_mapping.return_value = {}

        mock_dir = MagicMock()
        mock_dir.iterdir.return_value = []
        mock_ensure_dir.return_value = mock_dir

        # All path lookups return non-existent
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = False
        mock_general_dir = MagicMock()
        mock_dir.__truediv__ = MagicMock(side_effect=lambda arg: mock_general_dir if arg == "general" else mock_template_path)

        result = template_utils.load_template('test_default')

        # Should attempt to save the default template
        mock_file.assert_called()

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils._load_mapping')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_load_template_handles_json_error(self, mock_log, mock_ensure_dir, mock_mapping):
        """Test load_template handles invalid JSON"""
        mock_mapping.return_value = {}

        mock_dir = MagicMock()
        mock_dir.iterdir.return_value = []
        mock_ensure_dir.return_value = mock_dir

        # Root directory lookup finds the file
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = True
        mock_dir.__truediv__ = MagicMock(return_value=mock_template_path)

        with patch('builtins.open', mock_open(read_data='{ invalid json')):
            result = template_utils.load_template('invalid')

        assert result is None
        # Should log error
        error_calls = [c for c in mock_log.call_args_list if c[0][0] == 'error']
        assert len(error_calls) > 0


class TestCreateTemplate:
    """Test suite for create_template() function"""

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    @patch('builtins.open', new_callable=mock_open)
    def test_create_template_success(self, mock_file, mock_log, mock_ensure_dir):
        """Test create_template successfully creates new template"""
        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir

        # category_dir / template_name.json
        mock_category_dir = MagicMock()
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = False
        mock_category_dir.__truediv__ = MagicMock(return_value=mock_template_path)
        mock_dir.__truediv__ = MagicMock(return_value=mock_category_dir)

        result = template_utils.create_template(
            'new_template',
            'New Subject',
            'New Body'
        )

        assert result is True
        mock_file.assert_called()

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_create_template_empty_name(self, mock_log):
        """Test create_template rejects empty name"""
        result = template_utils.create_template('', 'Subject', 'Body')

        assert result is False
        # Should log error
        error_calls = [c for c in mock_log.call_args_list if c[0][0] == 'error']
        assert len(error_calls) > 0

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_create_template_empty_subject(self, mock_log):
        """Test create_template rejects empty subject"""
        result = template_utils.create_template('name', '', 'Body')

        assert result is False

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_create_template_empty_body(self, mock_log):
        """Test create_template rejects empty body"""
        result = template_utils.create_template('name', 'Subject', '')

        assert result is False

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_create_template_already_exists(self, mock_log, mock_ensure_dir):
        """Test create_template rejects duplicate template names"""
        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir

        mock_category_dir = MagicMock()
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = True
        mock_category_dir.__truediv__ = MagicMock(return_value=mock_template_path)
        mock_dir.__truediv__ = MagicMock(return_value=mock_category_dir)

        result = template_utils.create_template(
            'existing_template',
            'Subject',
            'Body'
        )

        assert result is False
        # Should log error about existing template
        error_calls = [c for c in mock_log.call_args_list if c[0][0] == 'error']
        assert any('already exists' in str(c[0][1]) for c in error_calls)

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    @patch('builtins.open', new_callable=mock_open)
    def test_create_template_sanitizes_name(self, mock_file, mock_log, mock_ensure_dir):
        """Test create_template sanitizes template name"""
        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir

        mock_category_dir = MagicMock()
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = False
        mock_category_dir.__truediv__ = MagicMock(return_value=mock_template_path)
        mock_dir.__truediv__ = MagicMock(return_value=mock_category_dir)

        # Name with special characters
        result = template_utils.create_template(
            'test-template@2024!',
            'Subject',
            'Body'
        )

        # Should succeed with sanitized name
        assert result is True

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('builtins.open', new_callable=mock_open)
    def test_create_template_exception_handling(self, mock_file, mock_ensure_dir):
        """Test create_template handles exceptions"""
        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir

        mock_category_dir = MagicMock()
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = False
        mock_category_dir.__truediv__ = MagicMock(return_value=mock_template_path)
        mock_dir.__truediv__ = MagicMock(return_value=mock_category_dir)

        mock_file.side_effect = IOError("Write error")

        # @handle_exception should catch error
        result = template_utils.create_template('name', 'Subject', 'Body')
        assert result is False


class TestUpdateTemplate:
    """Test suite for update_template() function"""

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils._load_mapping')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    @patch('builtins.open', new_callable=mock_open)
    def test_update_template_subject(self, mock_file, mock_log, mock_ensure_dir, mock_load, mock_mapping):
        """Test update_template updates subject only"""
        mock_mapping.return_value = {}
        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir
        mock_load.return_value = {
            'subject': 'Old Subject',
            'body': 'Old Body'
        }

        # Path finding: iterdir returns empty, root path exists
        mock_dir.iterdir.return_value = []
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = True
        mock_template_path.relative_to.return_value = 'test.json'
        mock_dir.__truediv__ = MagicMock(return_value=mock_template_path)

        result = template_utils.update_template('test', subject='New Subject')

        assert result is True
        mock_file.assert_called()

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils._load_mapping')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('builtins.open', new_callable=mock_open)
    def test_update_template_body(self, mock_file, mock_ensure_dir, mock_load, mock_mapping):
        """Test update_template updates body only"""
        mock_mapping.return_value = {}
        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir
        mock_load.return_value = {
            'subject': 'Subject',
            'body': 'Old Body'
        }

        mock_dir.iterdir.return_value = []
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = True
        mock_template_path.relative_to.return_value = 'test.json'
        mock_dir.__truediv__ = MagicMock(return_value=mock_template_path)

        result = template_utils.update_template('test', body='New Body')

        assert result is True

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils._load_mapping')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('builtins.open', new_callable=mock_open)
    def test_update_template_both_fields(self, mock_file, mock_ensure_dir, mock_load, mock_mapping):
        """Test update_template updates both subject and body"""
        mock_mapping.return_value = {}
        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir
        mock_load.return_value = {
            'subject': 'Old Subject',
            'body': 'Old Body'
        }

        mock_dir.iterdir.return_value = []
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = True
        mock_template_path.relative_to.return_value = 'test.json'
        mock_dir.__truediv__ = MagicMock(return_value=mock_template_path)

        result = template_utils.update_template(
            'test',
            subject='New Subject',
            body='New Body'
        )

        assert result is True

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_update_template_not_found(self, mock_log, mock_load):
        """Test update_template handles missing template"""
        mock_load.return_value = None

        result = template_utils.update_template('nonexistent', subject='New')

        assert result is False
        # Should log error
        error_calls = [c for c in mock_log.call_args_list if c[0][0] == 'error']
        assert len(error_calls) > 0

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils._load_mapping')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('builtins.open', new_callable=mock_open)
    def test_update_template_no_changes(self, mock_file, mock_ensure_dir, mock_load, mock_mapping):
        """Test update_template with no kwargs"""
        mock_mapping.return_value = {}
        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir
        mock_load.return_value = {
            'subject': 'Subject',
            'body': 'Body'
        }

        mock_dir.iterdir.return_value = []
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = True
        mock_template_path.relative_to.return_value = 'test.json'
        mock_dir.__truediv__ = MagicMock(return_value=mock_template_path)

        result = template_utils.update_template('test')

        # Should still save (no changes but valid operation)
        assert result is True


class TestDeleteTemplate:
    """Test suite for delete_template() function"""

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils._load_mapping')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_delete_template_success(self, mock_log, mock_ensure_dir, mock_mapping):
        """Test delete_template successfully deletes template"""
        mock_mapping.return_value = {}

        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir

        mock_dir.iterdir.return_value = []
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = True
        mock_template_path.relative_to.return_value = 'test_template.json'
        mock_dir.__truediv__ = MagicMock(return_value=mock_template_path)

        result = template_utils.delete_template('test_template')

        assert result is True
        mock_template_path.unlink.assert_called_once()

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.DEFAULT_TEMPLATES', {'default_template': {}})
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_delete_template_prevents_default_deletion(self, mock_log):
        """Test delete_template prevents deletion of default templates"""
        result = template_utils.delete_template('default_template')

        assert result is False
        # Should log warning
        warning_calls = [c for c in mock_log.call_args_list if c[0][0] == 'warning']
        assert any('Cannot delete default' in str(c[0][1]) for c in warning_calls)

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils._load_mapping')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_delete_template_not_found(self, mock_log, mock_ensure_dir, mock_mapping):
        """Test delete_template handles missing template"""
        mock_mapping.return_value = {}

        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir

        mock_dir.iterdir.return_value = []
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_template_path)

        result = template_utils.delete_template('nonexistent')

        assert result is False
        # Should log warning
        warning_calls = [c for c in mock_log.call_args_list if c[0][0] == 'warning']
        assert len(warning_calls) > 0


class TestRenderTemplate:
    """Test suite for render_template() function"""

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.config')
    def test_render_template_success(self, mock_config, mock_load):
        """Test render_template successfully renders template"""
        mock_config.__getitem__ = MagicMock(return_value='Best regards,\nUniversity Team')

        mock_load.return_value = {
            'subject': 'Hello $name',
            'body': 'Welcome $name to $course'
        }

        template_vars = {
            'name': 'John',
            'course': 'CS101'
        }

        subject, body = template_utils.render_template('welcome', template_vars)

        assert subject == 'Hello John'
        assert 'Welcome John to CS101' in body

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    def test_render_template_not_found(self, mock_load):
        """Test render_template returns None for missing template"""
        mock_load.return_value = None

        subject, body = template_utils.render_template('nonexistent', {})

        assert subject is None
        assert body is None

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.config')
    def test_render_template_adds_signature(self, mock_config, mock_load):
        """Test render_template adds signature if not provided"""
        signature = 'Test Signature'
        mock_config.__getitem__ = MagicMock(return_value=signature)

        mock_load.return_value = {
            'subject': 'Subject',
            'body': 'Body $signature'
        }

        # Don't provide signature in vars
        template_vars = {}

        subject, body = template_utils.render_template('test', template_vars)

        assert signature in body

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.config')
    def test_render_template_preserves_custom_signature(self, mock_config, mock_load):
        """Test render_template preserves custom signature"""
        mock_config.__getitem__ = MagicMock(return_value='Default Signature')

        mock_load.return_value = {
            'subject': 'Subject',
            'body': 'Body $signature'
        }

        # Provide custom signature
        template_vars = {'signature': 'Custom Signature'}

        subject, body = template_utils.render_template('test', template_vars)

        assert 'Custom Signature' in body
        assert 'Default Signature' not in body

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.config')
    def test_render_template_safe_substitute(self, mock_config, mock_load):
        """Test render_template uses safe_substitute (doesn't error on missing vars)"""
        mock_config.__getitem__ = MagicMock(return_value='')

        mock_load.return_value = {
            'subject': 'Hello $name',
            'body': 'Your score: $score, Grade: $grade'
        }

        # Only provide partial variables
        template_vars = {'name': 'John'}

        subject, body = template_utils.render_template('test', template_vars)

        # Should not raise exception, missing vars should remain as-is
        assert subject == 'Hello John'
        assert '$score' in body
        assert '$grade' in body

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.log_event')
    def test_render_template_handles_errors(self, mock_log, mock_load):
        """Test render_template handles rendering errors"""
        mock_load.return_value = {
            'subject': 'Subject',
            'body': 'Body'
        }

        # Force an error by mocking Template to raise exception
        with patch('education_system.post_18.university_system.infrastructure.email.template_utils.Template', side_effect=Exception("Template error")):
            subject, body = template_utils.render_template('test', {})

            assert subject is None
            assert body is None
            # Should log error
            error_calls = [c for c in mock_log.call_args_list if c[0][0] == 'error']
            assert len(error_calls) > 0


class TestTemplateManagementMenu:
    """Test suite for template_management_menu() function (integration test)"""

    def test_template_management_menu_exists(self):
        """Test that template_management_menu function exists"""
        assert hasattr(template_utils, 'template_management_menu')
        assert callable(template_utils.template_management_menu)

    @patch('builtins.input', side_effect=['5'])  # Exit immediately
    @patch('builtins.print')
    def test_template_management_menu_exit(self, mock_print, mock_input):
        """Test template_management_menu exits properly"""
        template_utils.template_management_menu()

        # Should have printed menu
        assert mock_print.called

    @patch('builtins.input', side_effect=['1', '', '5'])  # List templates, press enter, then exit
    @patch('builtins.print')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.list_templates')
    def test_template_management_menu_list_empty(self, mock_list, mock_print, mock_input):
        """Test template_management_menu lists templates when empty"""
        mock_list.return_value = []

        template_utils.template_management_menu()

        mock_list.assert_called()

    @patch('builtins.input', side_effect=['2', '', '5'])  # Create with empty name, then exit
    @patch('builtins.print')
    def test_template_management_menu_create_empty_name(self, mock_print, mock_input):
        """Test template_management_menu rejects empty template name"""
        template_utils.template_management_menu()

        # The _t function returns the key when i18n is not available
        # The code calls print(_t("email.templates.name_required"))
        print_calls = [str(c) for c in mock_print.call_args_list]
        assert any('name_required' in c.lower() or 'cannot be empty' in c.lower() or 'name is required' in c.lower() for c in print_calls)


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions"""

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('builtins.open', new_callable=mock_open)
    def test_template_with_unicode_characters(self, mock_file, mock_ensure_dir):
        """Test templates handle Unicode characters correctly"""
        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir

        mock_category_dir = MagicMock()
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = False
        mock_category_dir.__truediv__ = MagicMock(return_value=mock_template_path)
        mock_dir.__truediv__ = MagicMock(return_value=mock_category_dir)

        result = template_utils.create_template(
            'unicode_test',
            'Subject with emojis',
            'Body with special chars: n, u, o'
        )

        # Should handle Unicode properly
        assert result is True

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.ensure_templates_directory')
    @patch('builtins.open', new_callable=mock_open)
    def test_template_with_very_long_content(self, mock_file, mock_ensure_dir):
        """Test templates handle very long content"""
        mock_dir = MagicMock()
        mock_ensure_dir.return_value = mock_dir

        long_subject = 'A' * 1000
        long_body = 'B' * 10000

        mock_category_dir = MagicMock()
        mock_template_path = MagicMock()
        mock_template_path.exists.return_value = False
        mock_category_dir.__truediv__ = MagicMock(return_value=mock_template_path)
        mock_dir.__truediv__ = MagicMock(return_value=mock_category_dir)

        result = template_utils.create_template(
            'long_test',
            long_subject,
            long_body
        )

        assert result is True

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.config')
    def test_render_template_with_empty_vars(self, mock_config, mock_load):
        """Test render_template with empty variables dictionary"""
        mock_config.__getitem__ = MagicMock(return_value='Signature')
        mock_load.return_value = {
            'subject': 'Plain subject',
            'body': 'Plain body'
        }

        subject, body = template_utils.render_template('test', {})

        assert subject == 'Plain subject'
        assert body == 'Plain body'

    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.load_template')
    @patch('education_system.post_18.university_system.infrastructure.email.template_utils.config')
    def test_render_template_with_special_characters_in_vars(self, mock_config, mock_load):
        """Test render_template with special characters in variable values"""
        mock_config.__getitem__ = MagicMock(return_value='')
        mock_load.return_value = {
            'subject': 'Message for $name',
            'body': 'Content: $content'
        }

        template_vars = {
            'name': 'John O\'Brien',
            'content': 'Special chars: $, {}, [], \\'
        }

        subject, body = template_utils.render_template('test', template_vars)

        assert 'John O\'Brien' in subject
        assert 'Special chars' in body


class TestModuleIntegration:
    """Test suite for module-level integration"""

    def test_module_imports(self):
        """Test that all necessary imports are available"""
        assert hasattr(template_utils, 'json')
        assert hasattr(template_utils, 're')
        assert hasattr(template_utils, 'Path')
        assert hasattr(template_utils, 'Template')

    def test_all_public_functions_exist(self):
        """Test that all public functions are accessible"""
        expected_functions = [
            'initialize_analytics_templates',
            'ensure_templates_directory',
            'save_default_templates',
            'list_templates',
            'load_template',
            'create_template',
            'update_template',
            'delete_template',
            'render_template',
            'template_management_menu'
        ]

        for func_name in expected_functions:
            assert hasattr(template_utils, func_name)
            assert callable(getattr(template_utils, func_name))


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '--cov=university_system.infrastructure.email.template_utils', '--cov-report=term-missing'])
