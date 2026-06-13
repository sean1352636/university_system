"""
Template utilities for the university system
"""

from education_system.university_system.core.i18n import get_text as _t

DEFAULT_TEMPLATES = {
    'email': {
        'welcome': 'Welcome to the university system!',
        'notification': 'You have a new notification.',
        'reminder': 'This is a reminder about your upcoming event.'
    },
    'report': {
        'header': 'University System Report',
        'footer': 'Generated automatically by the system'
    }
}

def get_default_templates():
    """Get default templates for various use cases"""
    return DEFAULT_TEMPLATES

def load_template(template_type, template_name):
    """Load a specific template"""
    templates = get_default_templates()
    return templates.get(template_type, {}).get(template_name, '')

def format_template(template, **kwargs):
    """Format a template with provided variables"""
    try:
        return template.format(**kwargs)
    except KeyError as e:
        print(_t("shared.utils.templates.missing_template_variable", variable=str(e)))
        return template

def initialize_analytics_templates():
    """Initialize analytics templates"""
    analytics_templates = {
        'report_header': 'Analytics Report - {date}',
        'summary_section': 'Summary:\n{summary_text}',
        'chart_caption': 'Figure {number}: {title}',
        'data_table': 'Data Table {number}',
        'footer': 'Report generated on {timestamp}'
    }

    # Add analytics templates to DEFAULT_TEMPLATES
    global DEFAULT_TEMPLATES
    DEFAULT_TEMPLATES['analytics'] = analytics_templates

    return analytics_templates

def ensure_templates_directory():
    """Ensure templates directory exists and is properly set up"""
    import os

    # Default templates directory paths
    templates_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'templates')
    config_templates_dir = os.path.join(os.path.dirname(__file__), '..', 'config', 'templates')

    # Create directories if they don't exist
    for dir_path in [templates_dir, config_templates_dir]:
        try:
            os.makedirs(dir_path, exist_ok=True)
        except OSError as e:
            print(_t("shared.utils.templates.warning_create_directory_failed", path=dir_path, error=str(e)))

    # Create default templates.json if it doesn't exist
    templates_json = os.path.join(config_templates_dir, 'templates.json')
    if not os.path.exists(templates_json):
        try:
            import json
            with open(templates_json, 'w') as f:
                json.dump(DEFAULT_TEMPLATES, f, indent=2)
        except Exception as e:
            print(_t("shared.utils.templates.warning_create_templates_json_failed", error=str(e)))

    return templates_dir

def import_templates(auth=None):
    """Import templates from user-specified path"""
    try:
        import tkinter.filedialog as filedialog
        file_path = filedialog.askopenfilename(
            title="Select Templates File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            return import_templates_from_path(auth, file_path)
    except ImportError:
        # Fallback for CLI environments
        file_path = input(_t("shared.utils.templates.prompt_enter_templates_path")).strip()
        if file_path:
            return import_templates_from_path(auth, file_path)

    return None

def import_templates_from_path(auth=None, source_path=None):
    """Import templates from specified path"""
    if not source_path:
        print(_t("shared.utils.templates.error_no_source_path"))
        return None

    try:
        import json
        import os

        if not os.path.exists(source_path):
            print(_t("shared.utils.templates.error_file_not_found", path=source_path))
            return None

        with open(source_path, 'r') as f:
            imported_templates = json.load(f)

        # Merge with existing templates
        global DEFAULT_TEMPLATES
        if isinstance(imported_templates, dict):
            DEFAULT_TEMPLATES.update(imported_templates)
        elif isinstance(imported_templates, list):
            # Handle array of templates
            for template in imported_templates:
                if isinstance(template, dict) and 'name' in template:
                    DEFAULT_TEMPLATES[template['name']] = template

        print(_t("shared.utils.templates.success_imported_templates", path=source_path))
        return imported_templates

    except json.JSONDecodeError as e:
        print(_t("shared.utils.templates.error_parsing_json", error=str(e)))
        return None
    except Exception as e:
        print(_t("shared.utils.templates.error_importing_templates", error=str(e)))
        return None

def save_templates():
    """Save current templates to default location"""
    try:
        import json
        import os

        ensure_templates_directory()
        config_dir = os.path.join(os.path.dirname(__file__), '..', 'config')
        templates_file = os.path.join(config_dir, 'templates.json')

        with open(templates_file, 'w') as f:
            json.dump(DEFAULT_TEMPLATES, f, indent=2)

        print(_t("shared.utils.templates.success_templates_saved", path=templates_file))
        return True

    except Exception as e:
        print(_t("shared.utils.templates.error_saving_templates", error=str(e)))
        return False

def list_templates():
    """List all available templates"""
    return list(DEFAULT_TEMPLATES.keys())

def create_template(name, template_data):
    """Create a new template"""
    global DEFAULT_TEMPLATES
    DEFAULT_TEMPLATES[name] = template_data
    return True

def delete_template(name):
    """Delete a template"""
    global DEFAULT_TEMPLATES
    if name in DEFAULT_TEMPLATES:
        del DEFAULT_TEMPLATES[name]
        return True
    return False

def template_exists(name):
    """Check if a template exists"""
    return name in DEFAULT_TEMPLATES

def get_template_categories():
    """Get all template categories"""
    return list(DEFAULT_TEMPLATES.keys())

def save_default_templates():
    """Save default templates to the default location"""
    return save_templates()

def update_template(name, template_data):
    """Update an existing template"""
    global DEFAULT_TEMPLATES
    if name in DEFAULT_TEMPLATES:
        DEFAULT_TEMPLATES[name] = template_data
        return True
    else:
        print(_t("shared.utils.templates.error_template_not_found", name=name))
        return False

def render_template(template_name, variables=None):
    """Render a template with provided variables"""
    if variables is None:
        variables = {}

    # Handle nested template access (e.g., 'email.welcome')
    if '.' in template_name:
        category, name = template_name.split('.', 1)
        template_data = DEFAULT_TEMPLATES.get(category, {})
        template = template_data.get(name, '')
    else:
        # Direct template access
        template = DEFAULT_TEMPLATES.get(template_name, '')

    if not template:
        print(_t("shared.utils.templates.error_template_not_found", name=template_name))
        return _t("shared.utils.templates.error_template_not_found", name=template_name)

    return format_template(template, **variables)

def template_management_menu():
    """Display template management menu (console-based)"""
    print("\n" + "="*50)
    print(_t("shared.utils.templates.menu_title"))
    print("="*50)
    print(_t("shared.utils.templates.menu_option_list_templates"))
    print(_t("shared.utils.templates.menu_option_view_template"))
    print(_t("shared.utils.templates.menu_option_create_template"))
    print(_t("shared.utils.templates.menu_option_update_template"))
    print(_t("shared.utils.templates.menu_option_delete_template"))
    print(_t("shared.utils.templates.menu_option_import_templates"))
    print(_t("shared.utils.templates.menu_option_save_templates"))
    print(_t("shared.utils.templates.menu_option_template_categories"))
    print(_t("shared.utils.templates.menu_option_back"))
    print("="*50)

    try:
        choice = input(_t("shared.utils.templates.prompt_enter_choice")).strip()

        if choice == '1':
            templates = list_templates()
            print(_t("shared.utils.templates.available_templates_count", count=len(templates)))
            for i, template in enumerate(templates, 1):
                print(f"  {i}. {template}")

        elif choice == '2':
            name = input(_t("shared.utils.templates.prompt_enter_template_name_view")).strip()
            if template_exists(name):
                template = DEFAULT_TEMPLATES[name]
                print(_t("shared.utils.templates.template_display_header", name=name))
                print("-" * 30)
                if isinstance(template, dict):
                    for key, value in template.items():
                        print(f"{key}: {value}")
                else:
                    print(template)
            else:
                print(_t("shared.utils.templates.error_template_not_found", name=name))

        elif choice == '3':
            name = input(_t("shared.utils.templates.prompt_enter_new_template_name")).strip()
            template_type = input(_t("shared.utils.templates.prompt_enter_template_type")).strip().lower()

            if template_type == 'dict':
                print(_t("shared.utils.templates.prompt_enter_key_value_pairs"))
                template_data = {}
                while True:
                    key = input(_t("shared.utils.templates.prompt_enter_key")).strip()
                    if not key:
                        break
                    value = input(_t("shared.utils.templates.prompt_enter_value", key=key)).strip()
                    template_data[key] = value
            else:
                template_data = input(_t("shared.utils.templates.prompt_enter_template_content")).strip()

            if create_template(name, template_data):
                print(_t("shared.utils.templates.success_template_created", name=name))
            else:
                print(_t("shared.utils.templates.error_template_create_failed", name=name))

        elif choice == '4':
            name = input(_t("shared.utils.templates.prompt_enter_template_name_update")).strip()
            if template_exists(name):
                print(_t("shared.utils.templates.current_template_display", name=name))
                template = DEFAULT_TEMPLATES[name]
                if isinstance(template, dict):
                    for key, value in template.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"  {template}")

                confirm = input(_t("shared.utils.templates.prompt_confirm_update")).strip().lower()
                if confirm == 'y':
                    template_type = input(_t("shared.utils.templates.prompt_enter_template_type")).strip().lower()

                    if template_type == 'dict':
                        print(_t("shared.utils.templates.prompt_enter_key_value_pairs"))
                        template_data = {}
                        while True:
                            key = input(_t("shared.utils.templates.prompt_enter_key")).strip()
                            if not key:
                                break
                            value = input(_t("shared.utils.templates.prompt_enter_value", key=key)).strip()
                            template_data[key] = value
                    else:
                        template_data = input(_t("shared.utils.templates.prompt_enter_new_template_content")).strip()

                    if update_template(name, template_data):
                        print(_t("shared.utils.templates.success_template_updated", name=name))
                    else:
                        print(_t("shared.utils.templates.error_template_update_failed", name=name))
            else:
                print(_t("shared.utils.templates.error_template_not_found", name=name))

        elif choice == '5':
            name = input(_t("shared.utils.templates.prompt_enter_template_name_delete")).strip()
            if template_exists(name):
                confirm = input(_t("shared.utils.templates.prompt_confirm_delete", name=name)).strip().lower()
                if confirm == 'y':
                    if delete_template(name):
                        print(_t("shared.utils.templates.success_template_deleted", name=name))
                    else:
                        print(_t("shared.utils.templates.error_template_delete_failed", name=name))
            else:
                print(_t("shared.utils.templates.error_template_not_found", name=name))

        elif choice == '6':
            import_templates()

        elif choice == '7':
            if save_templates():
                print(_t("shared.utils.templates.success_templates_saved_msg"))
            else:
                print(_t("shared.utils.templates.error_templates_save_failed"))

        elif choice == '8':
            categories = get_template_categories()
            print(_t("shared.utils.templates.template_categories_count", count=len(categories)))
            for i, category in enumerate(categories, 1):
                print(f"  {i}. {category}")

        elif choice == '9':
            return

        else:
            print(_t("shared.utils.templates.error_invalid_choice"))

    except KeyboardInterrupt:
        print(_t("shared.utils.templates.exiting_menu"))
        return
    except Exception as e:
        print(_t("shared.utils.templates.error_menu", error=str(e)))
        return