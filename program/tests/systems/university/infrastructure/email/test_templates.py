"""
Comprehensive test suite for email/templates.py
Tests re-exports from template_utils module
"""

import sys
import os
import pytest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from education_system.systems.university.infrastructure.email import templates


class TestTemplatesModuleExports:
    """Test suite for templates module exports"""

    def test_module_has_all(self):
        """Test that __all__ is defined"""
        assert hasattr(templates, '__all__')
        assert isinstance(templates.__all__, list)

    def test_initialize_analytics_templates_exported(self):
        """Test initialize_analytics_templates is exported"""
        assert hasattr(templates, 'initialize_analytics_templates')
        assert callable(templates.initialize_analytics_templates)
        assert 'initialize_analytics_templates' in templates.__all__

    def test_ensure_templates_directory_exported(self):
        """Test ensure_templates_directory is exported"""
        assert hasattr(templates, 'ensure_templates_directory')
        assert callable(templates.ensure_templates_directory)
        assert 'ensure_templates_directory' in templates.__all__

    def test_save_default_templates_exported(self):
        """Test save_default_templates is exported"""
        assert hasattr(templates, 'save_default_templates')
        assert callable(templates.save_default_templates)
        assert 'save_default_templates' in templates.__all__

    def test_list_templates_exported(self):
        """Test list_templates is exported"""
        assert hasattr(templates, 'list_templates')
        assert callable(templates.list_templates)
        assert 'list_templates' in templates.__all__

    def test_load_template_exported(self):
        """Test load_template is exported"""
        assert hasattr(templates, 'load_template')
        assert callable(templates.load_template)
        assert 'load_template' in templates.__all__

    def test_create_template_exported(self):
        """Test create_template is exported"""
        assert hasattr(templates, 'create_template')
        assert callable(templates.create_template)
        assert 'create_template' in templates.__all__

    def test_update_template_exported(self):
        """Test update_template is exported"""
        assert hasattr(templates, 'update_template')
        assert callable(templates.update_template)
        assert 'update_template' in templates.__all__

    def test_delete_template_exported(self):
        """Test delete_template is exported"""
        assert hasattr(templates, 'delete_template')
        assert callable(templates.delete_template)
        assert 'delete_template' in templates.__all__

    def test_render_template_exported(self):
        """Test render_template is exported"""
        assert hasattr(templates, 'render_template')
        assert callable(templates.render_template)
        assert 'render_template' in templates.__all__

    def test_template_management_menu_exported(self):
        """Test template_management_menu is exported"""
        assert hasattr(templates, 'template_management_menu')
        assert callable(templates.template_management_menu)
        assert 'template_management_menu' in templates.__all__

    def test_default_templates_exported(self):
        """Test DEFAULT_TEMPLATES is exported"""
        assert hasattr(templates, 'DEFAULT_TEMPLATES')
        assert isinstance(templates.DEFAULT_TEMPLATES, dict)
        assert 'DEFAULT_TEMPLATES' in templates.__all__


class TestTemplatesModuleIntegration:
    """Test suite for templates module integration with template_utils"""

    def test_imports_from_template_utils(self):
        """Test that functions are imported from template_utils"""
        from education_system.systems.university.infrastructure.email import template_utils

        # Verify they're the same objects
        assert templates.initialize_analytics_templates is template_utils.initialize_analytics_templates
        assert templates.ensure_templates_directory is template_utils.ensure_templates_directory
        assert templates.save_default_templates is template_utils.save_default_templates
        assert templates.list_templates is template_utils.list_templates
        assert templates.load_template is template_utils.load_template
        assert templates.create_template is template_utils.create_template
        assert templates.update_template is template_utils.update_template
        assert templates.delete_template is template_utils.delete_template
        assert templates.render_template is template_utils.render_template
        assert templates.template_management_menu is template_utils.template_management_menu
        assert templates.DEFAULT_TEMPLATES is template_utils.DEFAULT_TEMPLATES

    def test_all_exports_count(self):
        """Test that __all__ contains all expected exports"""
        expected_count = 11  # 10 functions + 1 constant
        assert len(templates.__all__) == expected_count

    def test_no_extra_exports(self):
        """Test that only intended names are exported"""
        expected_exports = {
            'initialize_analytics_templates',
            'ensure_templates_directory',
            'save_default_templates',
            'list_templates',
            'load_template',
            'create_template',
            'update_template',
            'delete_template',
            'render_template',
            'template_management_menu',
            'DEFAULT_TEMPLATES'
        }
        assert set(templates.__all__) == expected_exports


class TestBackwardCompatibility:
    """Test suite for backward compatibility"""

    def test_can_import_all_functions(self):
        """Test that all functions can be imported from templates module"""
        from education_system.systems.university.infrastructure.email.templates import (
            initialize_analytics_templates,
            ensure_templates_directory,
            save_default_templates,
            list_templates,
            load_template,
            create_template,
            update_template,
            delete_template,
            render_template,
            template_management_menu,
            DEFAULT_TEMPLATES
        )

        # All imports should succeed
        assert callable(initialize_analytics_templates)
        assert callable(ensure_templates_directory)
        assert callable(save_default_templates)
        assert callable(list_templates)
        assert callable(load_template)
        assert callable(create_template)
        assert callable(update_template)
        assert callable(delete_template)
        assert callable(render_template)
        assert callable(template_management_menu)
        assert isinstance(DEFAULT_TEMPLATES, dict)

    def test_module_level_access(self):
        """Test that functions are accessible at module level"""
        import education_system.systems.university.infrastructure.email.templates as tpl

        assert hasattr(tpl, 'initialize_analytics_templates')
        assert hasattr(tpl, 'ensure_templates_directory')
        assert hasattr(tpl, 'save_default_templates')
        assert hasattr(tpl, 'list_templates')
        assert hasattr(tpl, 'load_template')
        assert hasattr(tpl, 'create_template')
        assert hasattr(tpl, 'update_template')
        assert hasattr(tpl, 'delete_template')
        assert hasattr(tpl, 'render_template')
        assert hasattr(tpl, 'template_management_menu')
        assert hasattr(tpl, 'DEFAULT_TEMPLATES')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
