"""
Updated template_utils.py with support for categorized email templates.

This file shows the changes needed to support the new categorized structure
while maintaining backward compatibility with existing code.

CHANGES SUMMARY:
1. load_template() - Now searches categorized subdirectories
2. list_templates() - Now lists templates from all categories
3. Added _load_mapping() helper to use the mapping file
4. Added backward compatibility warnings
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from string import Template

from university_system.infrastructure.email.config import config
from university_system.core.logs import handle_exception, log_event
from university_system.core import paths

# i18n support
try:
    from university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key, **kwargs):
        return key


# All email templates are now stored as JSON files in the templates/email directory.
# This dictionary is kept for backward compatibility but should remain empty.
# Templates are loaded dynamically from JSON files using load_template().
DEFAULT_TEMPLATES = {}

# Cache for the mapping file to avoid repeated file reads
_MAPPING_CACHE = None


def _load_mapping():
    """Load the email template mapping file (cached)"""
    global _MAPPING_CACHE

    if _MAPPING_CACHE is not None:
        return _MAPPING_CACHE

    templates_dir = paths.EMAIL_TEMPLATES_DIR
    mapping_file = templates_dir.parent / "email_template_mapping.json"

    if mapping_file.exists():
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                _MAPPING_CACHE = json.load(f)
                log_event('debug', f"Loaded email template mapping with {len(_MAPPING_CACHE)} entries")
        except Exception as e:
            log_event('error', f"Error loading template mapping: {e}")
            _MAPPING_CACHE = {}
    else:
        _MAPPING_CACHE = {}
        log_event('debug', "No template mapping file found")

    return _MAPPING_CACHE


def initialize_analytics_templates():
    """Initialize analytics-specific email templates"""
    # Analytics templates are now stored as JSON files in templates/email/
    # This function is kept for backward compatibility
    log_event('info', 'Analytics templates are loaded from JSON files in templates/email/')



@handle_exception
def ensure_templates_directory():
    """Ensure the email templates directory exists"""
    # Use the centralized EMAIL_TEMPLATES_DIR from paths
    templates_dir = paths.EMAIL_TEMPLATES_DIR

    if not templates_dir.exists():
        templates_dir.mkdir(parents=True, exist_ok=True)
        log_event('info', f"Created email templates directory: {templates_dir}")

    return templates_dir



@handle_exception
def save_default_templates():
    """Save default email templates to files"""
    # All templates are now stored as JSON files in templates/email/
    # This function is kept for backward compatibility
    templates_dir = ensure_templates_directory()
    log_event('info', f"Email templates directory: {templates_dir}")
    return True



@handle_exception
def list_templates():
    """
    List all available email templates from all categories.

    Returns templates from categorized subdirectories with their full paths.
    """
    templates_dir = ensure_templates_directory()
    templates = []

    # Scan all subdirectories for .json files
    for category_dir in sorted(templates_dir.iterdir()):
        if category_dir.is_dir() and not category_dir.name.startswith('_'):
            category_name = category_dir.name

            for template_file in sorted(category_dir.glob("*.json")):
                try:
                    with open(template_file, "r", encoding="utf-8") as f:
                        template_data = json.load(f)

                        # Use relative path from email directory
                        relative_path = f"{category_name}/{template_file.name}"
                        template_name = template_file.stem

                        templates.append({
                            "name": template_name,
                            "path": relative_path,
                            "category": category_name,
                            "is_default": template_name in DEFAULT_TEMPLATES,
                            "subject": template_data.get("subject", ""),
                            "body_preview": (
                                template_data.get("body", "")[:100] + "..."
                                if len(template_data.get("body", "")) > 100
                                else template_data.get("body", "")
                            )
                        })
                except Exception as e:
                    log_event('error', f"Error reading template {template_file}: {e}")

    # Also check for any templates still in the root (legacy location)
    for template_file in sorted(templates_dir.glob("*.json")):
        if template_file.name != '__init__.py':
            try:
                with open(template_file, "r", encoding="utf-8") as f:
                    template_data = json.load(f)
                    templates.append({
                        "name": template_file.stem,
                        "path": template_file.name,
                        "category": "(root - legacy)",
                        "is_default": template_file.stem in DEFAULT_TEMPLATES,
                        "subject": template_data.get("subject", ""),
                        "body_preview": (
                            template_data.get("body", "")[:100] + "..."
                            if len(template_data.get("body", "")) > 100
                            else template_data.get("body", "")
                        )
                    })
            except Exception as e:
                log_event('error', f"Error reading template {template_file}: {e}")

    return templates



@handle_exception
def load_template(template_name):
    """
    Load an email template from file with support for categorized structure.

    Supports multiple lookup strategies for backward compatibility:
    1. If template_name contains "/" (e.g., "academics/assignment_due_reminder"),
       load directly from that path
    2. Otherwise, use the mapping file to find the new location
    3. If not in mapping, search all category subdirectories
    4. Fall back to root directory (legacy location)
    5. Fall back to DEFAULT_TEMPLATES (legacy)

    Args:
        template_name: Template name or path (e.g., "assignment_due_reminder"
                      or "academics/assignment_due_reminder")

    Returns:
        dict: Template data with 'subject' and 'body' keys, or None if not found
    """
    templates_dir = ensure_templates_directory()

    # Strategy 1: Direct path (new approach)
    # Example: "academics/assignment_due_reminder"
    if "/" in template_name:
        template_path = templates_dir / f"{template_name}.json"
        if template_path.exists():
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log_event('error', f"Error loading template {template_name}: {e}")
                return None

    # Strategy 2: Use mapping file (backward compatibility)
    # Example: "assignment_due_reminder" -> "academics/assignment_due_reminder"
    mapping = _load_mapping()
    template_filename = f"{template_name}.json"

    if template_filename in mapping:
        new_path = mapping[template_filename]
        template_path = templates_dir / new_path

        if template_path.exists():
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    # Log deprecation warning (only at debug level to avoid spam)
                    log_event('debug',
                             f"Template '{template_name}' loaded from new location: {new_path}. "
                             f"Consider updating code to use '{new_path.replace('.json', '')}'")
                    return json.load(f)
            except Exception as e:
                log_event('error', f"Error loading template {template_name} from {new_path}: {e}")

    # Strategy 3: Search all category subdirectories
    # This is a fallback for templates not in the mapping
    for category_dir in templates_dir.iterdir():
        if category_dir.is_dir() and not category_dir.name.startswith('_'):
            template_path = category_dir / f"{template_name}.json"
            if template_path.exists():
                try:
                    with open(template_path, "r", encoding="utf-8") as f:
                        log_event('info',
                                 f"Template '{template_name}' found in {category_dir.name}/ "
                                 f"(not in mapping file)")
                        return json.load(f)
                except Exception as e:
                    log_event('error', f"Error loading template {template_name}: {e}")

    # Strategy 4: Check root directory (legacy flat structure)
    template_path = templates_dir / f"{template_name}.json"
    if template_path.exists():
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                log_event('warning',
                         f"Template '{template_name}' loaded from root directory (legacy location). "
                         f"Consider moving to appropriate category.")
                return json.load(f)
        except Exception as e:
            log_event('error', f"Error loading template {template_name}: {e}")

    # Strategy 5: Fall back to DEFAULT_TEMPLATES (legacy)
    if template_name in DEFAULT_TEMPLATES:
        log_event('info', f"Template file not found. Using default template for {template_name}")

        # Save the default template for future use (in general/ category)
        try:
            general_dir = templates_dir / "general"
            general_dir.mkdir(exist_ok=True)
            template_path = general_dir / f"{template_name}.json"

            with open(template_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_TEMPLATES[template_name], f, indent=4)

            log_event('info', f"Saved default template to general/{template_name}.json")
        except Exception as e:
            log_event('error', f"Error saving default template: {e}")

        return DEFAULT_TEMPLATES[template_name]

    # Not found anywhere
    log_event('warning', f"No template found with name: {template_name}")
    return None



@handle_exception
def create_template(name, subject, body, category="general"):
    """
    Create a new email template in the specified category.

    Args:
        name: Template name (without .json extension)
        subject: Email subject line
        body: Email body text
        category: Category subdirectory (default: "general")

    Returns:
        bool: True if created successfully, False otherwise
    """
    # Validate inputs
    if not name or not subject or not body:
        log_event('error', "Template name, subject, and body are required")
        return False

    # Ensure valid template name
    template_name = re.sub(r'[^\w]', '_', name)

    templates_dir = ensure_templates_directory()

    # Create category directory if it doesn't exist
    category_dir = templates_dir / category
    category_dir.mkdir(exist_ok=True)

    template_path = category_dir / f"{template_name}.json"

    # Don't overwrite existing templates
    if template_path.exists():
        log_event('error', f"Template '{template_name}' already exists in {category}/")
        return False

    template_data = {
        "subject": subject,
        "body": body
    }

    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(template_data, f, indent=4)

    log_event('info', f"Created new template: {category}/{template_name}")
    return True



@handle_exception
def update_template(name, **kwargs):
    """
    Update an existing email template.

    Uses load_template() to find the template, so it works with both
    old flat names and new categorized paths.

    Args:
        name: Template name or path
        **kwargs: Fields to update (subject, body)

    Returns:
        bool: True if updated successfully, False otherwise
    """
    # Ensure template exists
    template_data = load_template(name)
    if not template_data:
        log_event('error', f"Template '{name}' not found")
        return False

    # Update fields
    if 'subject' in kwargs:
        template_data['subject'] = kwargs['subject']

    if 'body' in kwargs:
        template_data['body'] = kwargs['body']

    # Find the actual file path
    templates_dir = ensure_templates_directory()

    # If name contains /, it's a path
    if "/" in name:
        template_path = templates_dir / f"{name}.json"
    else:
        # Use mapping to find the file
        mapping = _load_mapping()
        template_filename = f"{name}.json"

        if template_filename in mapping:
            template_path = templates_dir / mapping[template_filename]
        else:
            # Search for it
            template_path = None
            for category_dir in templates_dir.iterdir():
                if category_dir.is_dir():
                    candidate = category_dir / f"{name}.json"
                    if candidate.exists():
                        template_path = candidate
                        break

            if not template_path:
                # Try root directory
                template_path = templates_dir / f"{name}.json"

    if template_path and template_path.exists():
        with open(template_path, "w", encoding="utf-8") as f:
            json.dump(template_data, f, indent=4)

        log_event('info', f"Updated template: {template_path.relative_to(templates_dir)}")
        return True
    else:
        log_event('error', f"Could not locate template file for '{name}'")
        return False



@handle_exception
def delete_template(name):
    """
    Delete an email template.

    Args:
        name: Template name or path

    Returns:
        bool: True if deleted successfully, False otherwise
    """
    # Cannot delete default templates
    if name in DEFAULT_TEMPLATES:
        log_event('warning', f"Cannot delete default template: {name}")
        return False

    templates_dir = ensure_templates_directory()

    # Find the template file
    if "/" in name:
        template_path = templates_dir / f"{name}.json"
    else:
        # Use mapping to find the file
        mapping = _load_mapping()
        template_filename = f"{name}.json"

        if template_filename in mapping:
            template_path = templates_dir / mapping[template_filename]
        else:
            # Search for it
            template_path = None
            for category_dir in templates_dir.iterdir():
                if category_dir.is_dir():
                    candidate = category_dir / f"{name}.json"
                    if candidate.exists():
                        template_path = candidate
                        break

            if not template_path:
                template_path = templates_dir / f"{name}.json"

    if template_path and template_path.exists():
        template_path.unlink()
        log_event('info', f"Deleted template: {template_path.relative_to(templates_dir)}")
        return True
    else:
        log_event('warning', f"Template '{name}' not found")
        return False



@handle_exception
def render_template(template_name, template_vars):
    """
    Render an email template with the provided variables.

    Args:
        template_name: Template name or path
        template_vars: Dictionary of variables to substitute

    Returns:
        tuple: (subject, body) or (None, None) if error
    """
    template_data = load_template(template_name)

    if not template_data:
        return None, None

    # Add signature to template variables if not provided
    if 'signature' not in template_vars:
        template_vars['signature'] = config['email_signature']

    # Render subject and body (support both 'body' and 'body_text'/'body_html' keys)
    try:
        subject_template = Template(template_data['subject'])
        body_key = 'body' if 'body' in template_data else 'body_html' if 'body_html' in template_data else 'body_text'
        body_template = Template(template_data[body_key])

        subject = subject_template.safe_substitute(template_vars)
        body = body_template.safe_substitute(template_vars)

        return subject, body
    except Exception as e:
        log_event('error', f"Error rendering template: {e}")
        return None, None



@handle_exception
def template_management_menu():
    """Interactive template management menu (unchanged for compatibility)"""
    while True:
        print(f"\n{_t('email.templates.menu_title')}:")
        print("==========================")
        print(f"1. {_t('email.templates.list')}")
        print(f"2. {_t('email.templates.create')}")
        print(f"3. {_t('email.templates.edit')}")
        print(f"4. {_t('email.templates.delete')}")
        print(f"5. {_t('email.common.return_to_email_menu')}")

        choice = input(_t("email.common.choose_option") + " (1-5): ")

        if choice == '1':
            # List templates
            templates = list_templates()

            if not templates:
                print(_t("email.templates.no_templates_found"))
            else:
                print(f"\n{_t('email.templates.available')}:")
                print(f"{'Category':<20}{'Name':<30}{'Subject':<40}")
                print("-" * 90)

                for template in templates:
                    print(f"{template['category']:<20}{template['name']:<30}{template['subject']:<40}")

            input(f"\n{_t('email.common.press_enter')}...")

        elif choice == '2':
            # Create template
            name = input(_t("email.templates.enter_name") + ": ")

            if not name:
                print(_t("email.templates.name_required"))
                continue

            # Ask for category
            print("\nAvailable categories:")
            print("academics, alumni, authentication, campus_events, clubs, commerce,")
            print("finance, general, health, helpdesk, housing, internships, library,")
            print("maintenance, mentorship, parking, reports, security, system, user_management")
            category = input("\nEnter category (default: general): ").strip() or "general"

            print(f"\n{_t('email.templates.available_variables')}:")
            print("$student_id, $email_address, $title, $first_name, $middle_name, $last_name")
            print("$course, $modules_list, $updated_fields, $signature")
            print(_t("email.templates.custom_variables_note"))

            subject = input(f"\n{_t('email.templates.enter_subject')}: ")

            print(f"\n{_t('email.templates.enter_body')} ({_t('email.templates.type_end')}):")
            body_lines = []
            while True:
                line = input()
                if line == 'END':
                    break
                body_lines.append(line)

            body = "\n".join(body_lines)

            if create_template(name, subject, body, category):
                print(_t("email.templates.created_success", name=name))
            else:
                print(_t("email.templates.created_failed", name=name))

        elif choice == '3':
            # Edit template
            templates = list_templates()

            if not templates:
                print(_t("email.templates.no_templates_found"))
                continue

            print(f"\n{_t('email.templates.available')}:")
            for i, template in enumerate(templates, 1):
                default_label = f" ({_t('email.templates.default')})" if template['is_default'] else ''
                print(f"{i}. [{template['category']}] {template['name']}{default_label}")

            try:
                template_idx = int(input(f"\n{_t('email.templates.enter_number_to_edit')}: "))
                if template_idx == 0:
                    continue

                if 1 <= template_idx <= len(templates):
                    template_info = templates[template_idx - 1]
                    template_name = template_info['path'].replace('.json', '')

                    # Load the template
                    template_data = load_template(template_name)

                    if template_data:
                        print(f"\n{_t('email.templates.editing')}: {template_name}")
                        print(f"\n{_t('email.templates.current_subject')}:")
                        print(template_data['subject'])
                        new_subject = input(f"\n{_t('email.templates.enter_new_subject')}: ")

                        if not new_subject:
                            new_subject = template_data['subject']

                        print(f"\n{_t('email.templates.current_body')}:")
                        print(template_data['body'])
                        print(f"\n{_t('email.templates.available_variables')}:")
                        print("$student_id, $email_address, $title, $first_name, $middle_name, $last_name")
                        print("$course, $modules_list, $updated_fields, $signature")
                        print(_t("email.templates.template_specific_note"))

                        print(f"\n{_t('email.templates.enter_new_body')} ({_t('email.templates.type_end')}):")
                        body_lines = []
                        while True:
                            line = input()
                            if line == 'END':
                                break
                            body_lines.append(line)

                        new_body = "\n".join(body_lines)

                        if not new_body:
                            new_body = template_data['body']

                        # Update the template
                        if update_template(template_name, subject=new_subject, body=new_body):
                            print(_t("email.templates.updated_success", name=template_name))
                        else:
                            print(_t("email.templates.updated_failed", name=template_name))
                    else:
                        print(_t("email.templates.load_failed", name=template_name))
                else:
                    print(_t("email.templates.invalid_number"))

            except ValueError:
                print(_t("email.common.invalid_input_number"))

        elif choice == '4':
            # Delete template
            templates = list_templates()

            if not templates:
                print(_t("email.templates.no_templates_found"))
                continue

            print(f"\n{_t('email.templates.available')}:")
            for i, template in enumerate(templates, 1):
                default_label = f" ({_t('email.templates.default')})" if template['is_default'] else ''
                print(f"{i}. [{template['category']}] {template['name']}{default_label}")

            try:
                template_idx = int(input(f"\n{_t('email.templates.enter_number_to_delete')}: "))
                if template_idx == 0:
                    continue

                if 1 <= template_idx <= len(templates):
                    template_info = templates[template_idx - 1]
                    template_name = template_info['path'].replace('.json', '')

                    # Check if it's a default template
                    if template_info['is_default']:
                        print(_t("email.templates.cannot_delete_default", name=template_name))
                        continue

                    # Confirm deletion
                    confirm = input(_t("email.templates.confirm_delete", name=template_name) + " (y/n): ")

                    if confirm.lower() == 'y':
                        if delete_template(template_name):
                            print(_t("email.templates.deleted_success", name=template_name))
                        else:
                            print(_t("email.templates.deleted_failed", name=template_name))
                    else:
                        print(_t("email.common.cancelled"))
                else:
                    print(_t("email.templates.invalid_number"))

            except ValueError:
                print(_t("email.common.invalid_input_number"))

        elif choice == '5':
            # Return to email menu
            break

        else:
            print(_t("email.common.invalid_choice"))
