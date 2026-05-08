import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from tkinter.simpledialog import askstring, askinteger
import threading
import json
from datetime import datetime, timedelta
import webbrowser
import os
import subprocess
import sys
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Import internationalisation (i18n) for multi‑language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Add the project root to Python path if not already there
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

class TemplateEditor:
    """Advanced template editor with syntax highlighting"""
    def __init__(self, parent, template_name=None):
        self.template_name = template_name
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Template Editor - {template_name or 'New Template'}")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        if template_name:
            self.load_template()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Template info
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(info_frame, text="Name:").grid(row=0, column=0, sticky=tk.W)
        self.name_entry = ttk.Entry(info_frame, width=30)
        self.name_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

        # Subject
        ttk.Label(main_frame, text="Subject:").pack(anchor=tk.W)
        self.subject_entry = ttk.Entry(main_frame, width=80)
        self.subject_entry.pack(fill=tk.X, pady=5)

        # Body with variable hints
        body_frame = ttk.Frame(main_frame)
        body_frame.pack(fill=tk.BOTH, expand=True)

        # Variables panel
        vars_frame = ttk.LabelFrame(body_frame, text="Available Variables", padding=5)
        vars_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        variables = [
            "$student_id", "$email_address", "$title", "$first_name",
            "$last_name", "$course", "$modules_list", "$signature"
        ]

        for var in variables:
            btn = ttk.Button(vars_frame, text=var, width=15,
                           command=lambda v=var: self.insert_variable(v))
            btn.pack(fill=tk.X, pady=1)

        # Body editor
        editor_frame = ttk.Frame(body_frame)
        editor_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(editor_frame, text="Body:").pack(anchor=tk.W)
        self.body_text = scrolledtext.ScrolledText(editor_frame, wrap=tk.WORD)
        self.body_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Save", command=self.save_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Preview", command=self.preview_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def insert_variable(self, variable):
        """Insert variable at cursor position"""
        self.body_text.insert(tk.INSERT, variable)
        self.body_text.focus()

    def load_template(self):
        """Load existing template"""
        if self.template_name and 'load_template' in globals():
            try:
                template_data = load_template(self.template_name)
                if template_data:
                    body = (template_data.get('body')
                            or template_data.get('body_html')
                            or template_data.get('body_text')
                            or '')
                    self.name_entry.insert(0, self.template_name)
                    self.subject_entry.insert(0, template_data.get('subject', ''))
                    self.body_text.insert(1.0, body)
            except Exception as e:
                messagebox.showerror("Error", f"Error loading template: {e}")

    def save_template(self):
        """Save template"""
        try:
            name = self.name_entry.get().strip()
            subject = self.subject_entry.get().strip()
            body = self.body_text.get(1.0, tk.END).strip()

            if not name or not subject or not body:
                messagebox.showerror("Error", "Please fill in all fields")
                return

            if 'create_template' in globals():
                if create_template(name, subject, body):
                    messagebox.showinfo("Success", f"Template '{name}' saved successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to save template")
            else:
                messagebox.showerror("Error", "Template system not available")

        except Exception as e:
            messagebox.showerror("Error", f"Error saving template: {e}")

    def preview_template(self):
        """Preview template with sample data"""
        subject = self.subject_entry.get()
        body = self.body_text.get(1.0, tk.END).strip()

        # Sample template variables
        sample_vars = {
            'student_id': 'STU12345',
            'email_address': 'john.doe@university.edu',
            'title': 'Mr',
            'first_name': 'John',
            'last_name': 'Doe',
            'course': 'Computer Science',
            'modules_list': '- CS101: Programming\n- CS102: Data Structures',
            'signature': '\n\nBest regards,\nUniversity Administration'
        }

        # Simple variable substitution
        preview_subject = subject
        preview_body = body

        for var, value in sample_vars.items():
            preview_subject = preview_subject.replace(f'£{var}', str(value))
            preview_body = preview_body.replace(f'£{var}', str(value))

        # Show preview
        preview_dialog = tk.Toplevel(self.dialog)
        preview_dialog.title("Template Preview")
        preview_dialog.geometry("500x400")

        preview_frame = ttk.Frame(preview_dialog, padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(preview_frame, text=f"Subject: {preview_subject}", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)

        preview_text = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, state=tk.DISABLED)
        preview_text.pack(fill=tk.BOTH, expand=True)

        preview_text.config(state=tk.NORMAL)
        preview_text.insert(1.0, preview_body)
        preview_text.config(state=tk.DISABLED)

        ttk.Button(preview_frame, text="Close", command=preview_dialog.destroy).pack(pady=10)


class ThemeManager:
    """Manage application themes"""
    def __init__(self):
        self.themes = {
            'default': {
                'bg': '#f0f0f0',
                'fg': '#000000',
                'select_bg': '#0078d4',
                'select_fg': '#ffffff'
            },
            'dark': {
                'bg': '#2d2d2d',
                'fg': '#ffffff',
                'select_bg': '#404040',
                'select_fg': '#ffffff'
            },
            'blue': {
                'bg': '#e6f3ff',
                'fg': '#000080',
                'select_bg': '#0066cc',
                'select_fg': '#ffffff'
            }
        }
        self.current_theme = 'default'

    def apply_theme(self, root, theme_name):
        """Apply theme to application"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            theme = self.themes[theme_name]

            # Apply to ttk styles
            style = ttk.Style()
            style.configure('TLabel', background=theme['bg'], foreground=theme['fg'])
            style.configure('TFrame', background=theme['bg'])

            # Configure root
            root.configure(bg=theme['bg'])


class ConfigManager:
    """Manage application configuration"""
    def __init__(self):
        self.config_file = "gui_config.json"
        self.default_config = {
            'window_geometry': '1200x800',
            'theme': 'default',
            'auto_refresh': True,
            'refresh_interval': 30,
            'show_notifications': True
        }
        self.config = self.load_config()

    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return {**self.default_config, **json.load(f)}
        except Exception as e:
            print(f"Error loading config: {e}")
        return self.default_config.copy()

    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key, value):
        """Set configuration value"""
        self.config[key] = value
        self.save_config()


class SingletonApp:
    """Ensure only one instance of the application runs"""
    def __init__(self):
        self.socket = None
        self.port = 9999

    def is_running(self):
        """Check if another instance is running"""
        try:
            import socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind(('localhost', self.port))
            return False
        except OSError:
            return True

    def cleanup(self):
        """Cleanup socket"""
        if self.socket:
            self.socket.close()


def handle_gui_error(func):
    """Decorator for GUI error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            import traceback
            error_msg = f"Error in {func.__name__}: {e}\n\nTraceback:\n{traceback.format_exc()}"
            print(error_msg)

            # Show error dialog if GUI is available
            try:
                messagebox.showerror("Error", f"An error occurred: {e}")
            except Exception:
                print(f"GUI Error: {e}")
    return wrapper



# Import infrastructure functions with fallbacks
try:
    from education_system.university_system.infrastructure.email.email_service import (
        send_email as _real_send_email,
        delete_stored_email as _real_delete_stored_email,
        clear_stored_emails as _real_clear_stored_emails,
        send_registration_confirmation,
        send_assignment_notification,
        send_grade_notification,
        send_extension_notification,
        send_update_confirmation,
        send_password_reset,
        send_appointment_confirmation,
        send_health_notification,
        send_ticket_notification,
        send_reply_notification,
        send_internship_notification,
        send_alumni_welcome_email,
        send_mentorship_notification,
        send_event_invitation,
        send_donation_receipt,
        send_book_checkout_confirmation,
        send_book_return_reminder,
        send_overdue_notification,
        send_sla_alert,
        send_satisfaction_survey,
        send_bulk_satisfaction_surveys,
        send_application_confirmation,
        send_schedule_change_notification,
        send_permit_confirmation,
        send_permit_update_confirmation,
    )
    send_email = _real_send_email
    delete_stored_email = _real_delete_stored_email
    clear_stored_emails = _real_clear_stored_emails
except ImportError:
    # Keep fallback implementations defined above if real ones cannot be imported
    pass

try:
    from education_system.university_system.infrastructure.email.email_db_utilities import (
        optimize_database as _real_optimize_database,
        execute_db_operation as _real_execute_db_operation,
    )
    optimize_database = _real_optimize_database
    execute_db_operation = _real_execute_db_operation
except ImportError:
    pass

try:
    from education_system.university_system.infrastructure.email.template_utils import (
        list_templates as _real_list_templates,
        load_template as _real_load_template,
        create_template as _real_create_template,
    )
    list_templates = _real_list_templates
    load_template = _real_load_template
    create_template = _real_create_template
except ImportError:
    pass

try:
    from education_system.university_system.infrastructure.email.reports import (
        get_system_health_info as _real_get_system_health_info,
    )
    get_system_health_info = _real_get_system_health_info
except ImportError:
    pass

try:
    from education_system.university_system.infrastructure.email.announcements import (
        send_batch_announcement as _real_send_batch_announcement,
    )
    send_batch_announcement = _real_send_batch_announcement
except ImportError:
    pass

try:
    from education_system.university_system.infrastructure.email.admin import (
        search_users as _real_search_users,
        list_all_users as _real_list_all_users,
    )
    search_users = _real_search_users
    list_all_users = _real_list_all_users
except ImportError:
    pass

try:
    from education_system.university_system.infrastructure.email.admin import (
        initialize_communication_system as _real_initialize_communication_system,
        cleanup_communication_system as _real_cleanup_communication_system,
    )
    initialize_communication_system = _real_initialize_communication_system
    cleanup_communication_system = _real_cleanup_communication_system
except ImportError:
    pass

try:
    from education_system.university_system.infrastructure.email.config import (
        config as real_config,
        save_config as real_save_config,
    )
    config = real_config
    save_config = real_save_config
except ImportError:
    # Use fallback config defined above if the real one cannot be imported
    pass
