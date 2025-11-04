"""Email template utilities and management helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from string import Template

from university_system.infrastructure.email.config import config
from university_system.modules.shared.utils.logs import handle_exception, log_event
from university_system.modules.shared.constants import paths


# All email templates are now stored as JSON files in the templates/email directory.
# This dictionary is kept for backward compatibility but should remain empty.
# Templates are loaded dynamically from JSON files using load_template().
DEFAULT_TEMPLATES = {}



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
    """List all available email templates"""
    templates_dir = ensure_templates_directory()
    
    # Get all .json files in templates directory
    template_files = list(templates_dir.glob("*.json"))
    
    # Extract template names (without extension)
    templates = []
    for file in template_files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                template_data = json.load(f)
                templates.append({
                    "name": file.stem,
                    "is_default": file.stem in DEFAULT_TEMPLATES,
                    "subject": template_data.get("subject", ""),
                    "body_preview": template_data.get("body", "")[:100] + "..." if len(template_data.get("body", "")) > 100 else template_data.get("body", "")
                })
        except Exception as e:
            log_event('error', f"Error reading template {file}: {e}")
    
    return templates



@handle_exception
def load_template(template_name):
    """Load an email template from file"""
    templates_dir = ensure_templates_directory()
    template_path = templates_dir / f"{template_name}.json"
    
    if template_path.exists():
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log_event('error', f"Error loading template {template_name}: {e}")
            
            # Fall back to default if available
            if template_name in DEFAULT_TEMPLATES:
                log_event('info', f"Using default template for {template_name}")
                return DEFAULT_TEMPLATES[template_name]
            return None
    else:
        # Check if default template exists
        if template_name in DEFAULT_TEMPLATES:
            log_event('info', f"Template file not found. Using default template for {template_name}")
            
            # Save the default template for future use
            try:
                with open(template_path, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_TEMPLATES[template_name], f, indent=4)
            except Exception as e:
                log_event('error', f"Error saving default template: {e}")
                
            return DEFAULT_TEMPLATES[template_name]
        else:
            log_event('warning', f"No template found with name: {template_name}")
            return None



@handle_exception
def create_template(name, subject, body):
    """Create a new email template"""
    # Validate inputs
    if not name or not subject or not body:
        log_event('error', "Template name, subject, and body are required")
        return False
    
    # Ensure valid template name
    template_name = re.sub(r'[^\w]', '_', name)
    
    templates_dir = ensure_templates_directory()
    template_path = templates_dir / f"{template_name}.json"
    
    # Don't overwrite existing templates
    if template_path.exists():
        log_event('error', f"Template '{template_name}' already exists")
        return False
    
    template_data = {
        "subject": subject,
        "body": body
    }
    
    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(template_data, f, indent=4)
    
    log_event('info', f"Created new template: {template_name}")
    return True



@handle_exception
def update_template(name, **kwargs):
    """Update an existing email template"""
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
    
    # Save updated template
    templates_dir = ensure_templates_directory()
    template_path = templates_dir / f"{name}.json"
    
    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(template_data, f, indent=4)
    
    log_event('info', f"Updated template: {name}")
    return True



@handle_exception
def delete_template(name):
    """Delete an email template"""
    # Cannot delete default templates
    if name in DEFAULT_TEMPLATES:
        log_event('warning', f"Cannot delete default template: {name}")
        return False
    
    templates_dir = ensure_templates_directory()
    template_path = templates_dir / f"{name}.json"
    
    if template_path.exists():
        template_path.unlink()
        log_event('info', f"Deleted template: {name}")
        return True
    else:
        log_event('warning', f"Template '{name}' not found")
        return False



@handle_exception
def render_template(template_name, template_vars):
    """Render an email template with the provided variables"""
    template_data = load_template(template_name)
    
    if not template_data:
        return None, None
    
    # Add signature to template variables if not provided
    if 'signature' not in template_vars:
        template_vars['signature'] = config['email_signature']
    
    # Render subject and body
    try:
        subject_template = Template(template_data['subject'])
        body_template = Template(template_data['body'])
        
        subject = subject_template.safe_substitute(template_vars)
        body = body_template.safe_substitute(template_vars)
        
        return subject, body
    except Exception as e:
        log_event('error', f"Error rendering template: {e}")
        return None, None



@handle_exception
def template_management_menu():
    """Interactive template management menu"""
    while True:
        print("\nEmail Template Management:")
        print("==========================")
        print("1. List Templates")
        print("2. Create Template")
        print("3. Edit Template")
        print("4. Delete Template")
        print("5. Return to Email Menu")
        
        choice = input("Choose an option (1-5): ")
        
        if choice == '1':
            # List templates
            templates = list_templates()
            
            if not templates:
                print("No templates found.")
            else:
                print("\nAvailable Templates:")
                print(f"{'Name':<30}{'Default':<10}{'Subject':<40}")
                print("-" * 80)
                
                for template in templates:
                    print(f"{template['name']:<30}{'Yes' if template['is_default'] else 'No':<10}{template['subject']:<40}")
            
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            # Create template
            name = input("Enter name for the new template: ")
            
            if not name:
                print("Template name cannot be empty.")
                continue
            
            # Check if template already exists
            existing_templates = [t['name'] for t in list_templates()]
            if name in existing_templates:
                print(f"Template '{name}' already exists.")
                continue
            
            print("\nAvailable variables:")
            print("$student_id, $email_address, $title, $first_name, $middle_name, $last_name")
            print("$course, $modules_list, $updated_fields, $signature")
            print("You can also define your own variables to use when sending emails.")
            
            subject = input("\nEnter email subject template: ")
            
            print("\nEnter email body template (type 'END' on a new line to finish):")
            body_lines = []
            while True:
                line = input()
                if line == 'END':
                    break
                body_lines.append(line)
            
            body = "\n".join(body_lines)
            
            if create_template(name, subject, body):
                print(f"Template '{name}' created successfully.")
            else:
                print(f"Failed to create template '{name}'.")
        
        elif choice == '3':
            # Edit template
            templates = list_templates()
            
            if not templates:
                print("No templates found.")
                continue
            
            print("\nAvailable Templates:")
            for i, template in enumerate(templates, 1):
                print(f"{i}. {template['name']} {'(Default)' if template['is_default'] else ''}")
            
            try:
                template_idx = int(input("\nEnter template number to edit (0 to cancel): "))
                if template_idx == 0:
                    continue
                
                if 1 <= template_idx <= len(templates):
                    template_name = templates[template_idx - 1]['name']
                    
                    # Load the template
                    template_data = load_template(template_name)
                    
                    if template_data:
                        print(f"\nEditing template: {template_name}")
                        print("\nCurrent Subject:")
                        print(template_data['subject'])
                        new_subject = input("\nEnter new subject (leave empty to keep current): ")
                        
                        if not new_subject:
                            new_subject = template_data['subject']
                        
                        print("\nCurrent Body:")
                        print(template_data['body'])
                        print("\nAvailable variables:")
                        print("$student_id, $email_address, $title, $first_name, $middle_name, $last_name")
                        print("$course, $modules_list, $updated_fields, $signature")
                        print("Template-specific variables may also be available.")
                        
                        print("\nEnter new body (type 'END' on a new line to finish, leave empty to keep current):")
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
                            print(f"Template '{template_name}' updated successfully.")
                        else:
                            print(f"Failed to update template '{template_name}'.")
                    else:
                        print(f"Failed to load template: {template_name}")
                else:
                    print("Invalid template number.")
            
            except ValueError:
                print("Invalid input. Please enter a number.")
        
        elif choice == '4':
            # Delete template
            templates = list_templates()
            
            if not templates:
                print("No templates found.")
                continue
            
            print("\nAvailable Templates:")
            for i, template in enumerate(templates, 1):
                print(f"{i}. {template['name']} {'(Default)' if template['is_default'] else ''}")
            
            try:
                template_idx = int(input("\nEnter template number to delete (0 to cancel): "))
                if template_idx == 0:
                    continue
                
                if 1 <= template_idx <= len(templates):
                    template_name = templates[template_idx - 1]['name']
                    
                    # Check if it's a default template
                    if templates[template_idx - 1]['is_default']:
                        print(f"Cannot delete default template: {template_name}")
                        continue
                    
                    # Confirm deletion
                    confirm = input(f"Are you sure you want to delete template '{template_name}'? (y/n): ")
                    
                    if confirm.lower() == 'y':
                        if delete_template(template_name):
                            print(f"Template '{template_name}' deleted successfully.")
                        else:
                            print(f"Failed to delete template '{template_name}'.")
                    else:
                        print("Deletion cancelled.")
                else:
                    print("Invalid template number.")
            
            except ValueError:
                print("Invalid input. Please enter a number.")
        
        elif choice == '5':
            # Return to email menu
            break
        
        else:
            print("Invalid choice. Please try again.")
