"""Email templates module - imports from template_utils for compatibility."""

from education_system.post_18.university_system.infrastructure.email.template_utils import (
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
    DEFAULT_TEMPLATES,
)

__all__ = [
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
    'DEFAULT_TEMPLATES',
]