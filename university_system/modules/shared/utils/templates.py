"""
Template utilities for the university system
"""

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
        print(f"Missing template variable: {e}")
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
            print(f"Warning: Could not create templates directory {dir_path}: {e}")

    # Create default templates.json if it doesn't exist
    templates_json = os.path.join(config_templates_dir, 'templates.json')
    if not os.path.exists(templates_json):
        try:
            import json
            with open(templates_json, 'w') as f:
                json.dump(DEFAULT_TEMPLATES, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not create default templates.json: {e}")

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
        file_path = input("Enter path to templates file: ").strip()
        if file_path:
            return import_templates_from_path(auth, file_path)

    return None

def import_templates_from_path(auth=None, source_path=None):
    """Import templates from specified path"""
    if not source_path:
        print("No source path provided")
        return None

    try:
        import json
        import os

        if not os.path.exists(source_path):
            print(f"File not found: {source_path}")
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

        print(f"Successfully imported templates from {source_path}")
        return imported_templates

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        return None
    except Exception as e:
        print(f"Error importing templates: {e}")
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

        print(f"Templates saved to {templates_file}")
        return True

    except Exception as e:
        print(f"Error saving templates: {e}")
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
        print(f"Template '{name}' not found")
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
        print(f"Template '{template_name}' not found")
        return f"Template '{template_name}' not found"

    return format_template(template, **variables)

def template_management_menu():
    """Display template management menu (console-based)"""
    print("\n" + "="*50)
    print("         TEMPLATE MANAGEMENT MENU")
    print("="*50)
    print("1. List all templates")
    print("2. View template")
    print("3. Create template")
    print("4. Update template")
    print("5. Delete template")
    print("6. Import templates")
    print("7. Save templates")
    print("8. Template categories")
    print("9. Back to main menu")
    print("="*50)

    try:
        choice = input("\nEnter your choice (1-9): ").strip()

        if choice == '1':
            templates = list_templates()
            print(f"\nAvailable templates ({len(templates)}):")
            for i, template in enumerate(templates, 1):
                print(f"  {i}. {template}")

        elif choice == '2':
            name = input("Enter template name to view: ").strip()
            if template_exists(name):
                template = DEFAULT_TEMPLATES[name]
                print(f"\nTemplate '{name}':")
                print("-" * 30)
                if isinstance(template, dict):
                    for key, value in template.items():
                        print(f"{key}: {value}")
                else:
                    print(template)
            else:
                print(f"Template '{name}' not found")

        elif choice == '3':
            name = input("Enter new template name: ").strip()
            template_type = input("Enter template type (text/dict): ").strip().lower()

            if template_type == 'dict':
                print("Enter key-value pairs (press Enter twice to finish):")
                template_data = {}
                while True:
                    key = input("Key (or press Enter to finish): ").strip()
                    if not key:
                        break
                    value = input(f"Value for '{key}': ").strip()
                    template_data[key] = value
            else:
                template_data = input("Enter template content: ").strip()

            if create_template(name, template_data):
                print(f"Template '{name}' created successfully")
            else:
                print(f"Failed to create template '{name}'")

        elif choice == '4':
            name = input("Enter template name to update: ").strip()
            if template_exists(name):
                print(f"Current template '{name}':")
                template = DEFAULT_TEMPLATES[name]
                if isinstance(template, dict):
                    for key, value in template.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"  {template}")

                confirm = input("\nProceed with update? (y/n): ").strip().lower()
                if confirm == 'y':
                    template_type = input("Enter template type (text/dict): ").strip().lower()

                    if template_type == 'dict':
                        print("Enter key-value pairs (press Enter twice to finish):")
                        template_data = {}
                        while True:
                            key = input("Key (or press Enter to finish): ").strip()
                            if not key:
                                break
                            value = input(f"Value for '{key}': ").strip()
                            template_data[key] = value
                    else:
                        template_data = input("Enter new template content: ").strip()

                    if update_template(name, template_data):
                        print(f"Template '{name}' updated successfully")
                    else:
                        print(f"Failed to update template '{name}'")
            else:
                print(f"Template '{name}' not found")

        elif choice == '5':
            name = input("Enter template name to delete: ").strip()
            if template_exists(name):
                confirm = input(f"Are you sure you want to delete '{name}'? (y/n): ").strip().lower()
                if confirm == 'y':
                    if delete_template(name):
                        print(f"Template '{name}' deleted successfully")
                    else:
                        print(f"Failed to delete template '{name}'")
            else:
                print(f"Template '{name}' not found")

        elif choice == '6':
            import_templates()

        elif choice == '7':
            if save_templates():
                print("Templates saved successfully")
            else:
                print("Failed to save templates")

        elif choice == '8':
            categories = get_template_categories()
            print(f"\nTemplate categories ({len(categories)}):")
            for i, category in enumerate(categories, 1):
                print(f"  {i}. {category}")

        elif choice == '9':
            return

        else:
            print("Invalid choice. Please enter 1-9.")

    except KeyboardInterrupt:
        print("\n\nExiting template management menu...")
        return
    except Exception as e:
        print(f"Error in template management menu: {e}")
        return