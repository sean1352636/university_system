from education_system.university_system.core.sql_safety import escape_like
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import tkinter.font as tkFont
from datetime import datetime, timedelta
import json
import os
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from education_system.university_system.infrastructure.database.db import sqlite3
from pathlib import Path
import logging
from education_system.university_system.modules.shared.constants import paths

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import activity logger for audit trail
try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import email service for notifications
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.email.templates import load_template, render_template
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    send_email = lambda *args, **kwargs: False
    load_template = lambda *args, **kwargs: None
    render_template = lambda *args, **kwargs: (None, None)

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# --------------------------------------------------------------------
# Override sqlite3.connect for this module when targeting the
# student_records.db database. Many functions within this GUI refer to
# str(DEFAULT_DB_PATH) without specifying a full path. Without this
# override, a new database would be created in the current working
# directory, leading to multiple database files and missing tables. The
# override redirects connections to the shared student_records.db in
# university_system/data/db_files. If a different database name/path is
# supplied, the connection falls back to the original behaviour.

_original_sqlite3_connect = sqlite3.connect  # preserve original

def _patched_sqlite_connect(database, *args, **kwargs):
    """Redirect connections targeting student_records.db to the central path."""
    try:
        # Determine basename; accept Path or str
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name == str(DEFAULT_DB_PATH):
            return _original_sqlite3_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite3_connect(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite_connect

# Import all functionality from student_support module (it's a single monolithic file)
try:
    # Import everything from the single student_support module
    from education_system.university_system.modules.domain.student_affairs.services.student_support import (
        # Core constants and enums
        SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
        NotificationType, TicketSentiment, FileType,
        # Main classes
        EnhancedStudentSupport, SupportConfig,
        # Utility functions
        setup_enhanced_logging, audit_action, set_auth,
        # Display functions
        display_support_menu, display_enhanced_faqs, display_enhanced_resources,
        # Ticket management functions
        view_my_tickets_enhanced, view_all_tickets_enhanced,
        create_enhanced_ticket, display_ticket_details_enhanced,
        # Admin functions
        manage_templates_menu, manage_knowledge_base_menu, show_template_statistics,
        # Helper functions
        format_ticket_status_display, format_priority_display, format_file_size,
        truncate_text, handle_support_error, validate_ticket_permissions
    )

    # Auth handling - auth is now managed differently in the new structure
    auth = None  # Will be set via set_auth_instance()

except ImportError:
    # Backwards compatibility - if module structure changes or imports fail
    try:
        from education_system.university_system.modules.domain.student_affairs.services.student_support import (
            SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
            EnhancedStudentSupport, SupportConfig, display_support_menu, set_auth
        )
        auth = None
    except ImportError:
        # If even the fallback import fails, define minimal stubs
        auth = None
        SUPPORT_CATEGORIES = []
        TICKET_PRIORITIES = []
        TICKET_STATUSES = []
        EnhancedStudentSupport = None
        SupportConfig = None
        display_support_menu = None

    # Define fallback functions if not available
    display_enhanced_faqs = None
    display_enhanced_resources = None
    view_my_tickets_enhanced = None
    view_all_tickets_enhanced = None
    create_enhanced_ticket = None
    display_ticket_details_enhanced = None
    manage_templates_menu = None
    manage_knowledge_base_menu = None
    show_template_statistics = None

    # Define fallback enum types
    from enum import Enum
    class NotificationType(str, Enum):
        INFO = 'info'
        WARNING = 'warning'
        ERROR = 'error'

    class TicketSentiment(str, Enum):
        POSITIVE = 'positive'
        NEUTRAL = 'neutral'
        NEGATIVE = 'negative'

    class FileType(str, Enum):
        IMAGE = 'image'
        DOCUMENT = 'document'
        OTHER = 'other'

    # Define fallback helper functions
    setup_enhanced_logging = lambda: None
    audit_action = lambda *args, **kwargs: None
    set_auth = lambda x: None  # Fallback if set_auth not available
    validate_ticket_permissions = lambda *args, **kwargs: True
    format_ticket_status_display = lambda x: str(x)
    format_priority_display = lambda x: str(x)
    format_file_size = lambda x: f"{x} bytes"
    truncate_text = lambda x, length=100: x[:length] if len(x) > length else x
    handle_support_error = lambda *args, **kwargs: None

class AdminMixin:
    def show_manage_templates(self):
        """Show template management interface (staff only)"""
        self.clear_content()

        templates_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(templates_frame, text="🔧 Manage Templates")

        # Configure frame to expand
        templates_frame.rowconfigure(0, weight=1)
        templates_frame.columnconfigure(0, weight=1)

        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] not in ('staff', 'admin'):
            ttk.Label(templates_frame, text="❌ Staff access required",
                     style='Title.TLabel').pack(pady=20)
            return

        ttk.Label(templates_frame, text="🔧 Template Management",
                 style='Title.TLabel').pack(pady=(0, 20))

        # Create notebook for ticket and response templates
        template_notebook = ttk.Notebook(templates_frame)
        template_notebook.pack(fill=tk.BOTH, expand=True)

        # Ticket Templates Tab
        ticket_template_frame = ttk.Frame(template_notebook, padding=10)
        template_notebook.add(ticket_template_frame, text="🎫 Ticket Templates")

        # Ticket templates controls
        ticket_controls = ttk.Frame(ticket_template_frame)
        ticket_controls.pack(fill=tk.X, pady=10)

        ttk.Button(ticket_controls, text="➕ Create Ticket Template",
                  command=lambda: self.create_ticket_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(ticket_controls, text="✏️ Edit Template",
                  command=lambda: self.edit_ticket_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(ticket_controls, text="🗑️ Delete Template",
                  command=lambda: self.delete_ticket_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(ticket_controls, text="🔄 Refresh",
                  command=lambda: self.refresh_ticket_templates()).pack(side=tk.LEFT, padx=5)

        # Ticket templates list
        ticket_list_frame = ttk.LabelFrame(ticket_template_frame, text="Ticket Templates", padding=10)
        ticket_list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ("ID", "Name", "Category", "Priority", "Created By", "Created Date", "Usage Count")
        self.ticket_templates_tree = ttk.Treeview(ticket_list_frame, columns=columns, show="headings", height=12)

        # Configure columns
        self.ticket_templates_tree.column("ID", width=50)
        self.ticket_templates_tree.column("Name", width=200)
        self.ticket_templates_tree.column("Category", width=120)
        self.ticket_templates_tree.column("Priority", width=80)
        self.ticket_templates_tree.column("Created By", width=100)
        self.ticket_templates_tree.column("Created Date", width=150)
        self.ticket_templates_tree.column("Usage Count", width=100)

        for col in columns:
            self.ticket_templates_tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(ticket_list_frame, orient=tk.VERTICAL, command=self.ticket_templates_tree.yview)
        self.ticket_templates_tree.configure(yscrollcommand=scrollbar.set)
        self.ticket_templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Response Templates Tab
        response_template_frame = ttk.Frame(template_notebook, padding=10)
        template_notebook.add(response_template_frame, text="💬 Response Templates")

        # Response templates controls
        response_controls = ttk.Frame(response_template_frame)
        response_controls.pack(fill=tk.X, pady=10)

        ttk.Button(response_controls, text="➕ Create Response Template",
                  command=lambda: self.create_response_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(response_controls, text="✏️ Edit Template",
                  command=lambda: self.edit_response_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(response_controls, text="🗑️ Delete Template",
                  command=lambda: self.delete_response_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(response_controls, text="🔄 Refresh",
                  command=lambda: self.refresh_response_templates()).pack(side=tk.LEFT, padx=5)

        # Response templates list
        response_list_frame = ttk.LabelFrame(response_template_frame, text="Response Templates", padding=10)
        response_list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ("ID", "Name", "Subject", "Category", "Created By", "Created Date", "Usage Count")
        self.response_templates_tree = ttk.Treeview(response_list_frame, columns=columns, show="headings", height=12)

        # Configure columns
        self.response_templates_tree.column("ID", width=50)
        self.response_templates_tree.column("Name", width=180)
        self.response_templates_tree.column("Subject", width=200)
        self.response_templates_tree.column("Category", width=120)
        self.response_templates_tree.column("Created By", width=100)
        self.response_templates_tree.column("Created Date", width=150)
        self.response_templates_tree.column("Usage Count", width=100)

        for col in columns:
            self.response_templates_tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(response_list_frame, orient=tk.VERTICAL, command=self.response_templates_tree.yview)
        self.response_templates_tree.configure(yscrollcommand=scrollbar.set)
        self.response_templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load templates
        self.refresh_ticket_templates()
        self.refresh_response_templates()

    def refresh_ticket_templates(self):
        """Refresh ticket templates list"""
        try:
            # Clear existing items
            for item in self.ticket_templates_tree.get_children():
                self.ticket_templates_tree.delete(item)

            template_count = 0

            # Load from database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT template_id, name, category, priority, created_by,
                           created_datetime, usage_count
                    FROM ticket_templates
                    ORDER BY created_datetime DESC
                ''')

                templates = cursor.fetchall()
            finally:
                conn.close()

            # Add database templates to tree
            for template in templates:
                self.ticket_templates_tree.insert('', tk.END, values=(
                    template['template_id'],
                    template['name'],
                    template['category'],
                    template['priority'],
                    template['created_by'],
                    template['created_datetime'],
                    template['usage_count'] or 0
                ))
                template_count += 1

            # Load JSON file templates from ticket_templates directory
            try:
                ticket_templates_dir = paths.TICKET_TEMPLATES_DIR
                if ticket_templates_dir.exists():
                    for json_file in ticket_templates_dir.glob("*.json"):
                        try:
                            with open(json_file, 'r', encoding='utf-8') as f:
                                tmpl_data = json.load(f)

                            # Only show active templates
                            if not tmpl_data.get('is_active', True):
                                continue

                            self.ticket_templates_tree.insert('', tk.END, values=(
                                f"FILE:{tmpl_data.get('template_id', json_file.stem)}",
                                tmpl_data.get('name', json_file.stem),
                                tmpl_data.get('category', 'General'),
                                tmpl_data.get('priority', 'Medium'),
                                'System',
                                'Built-in',
                                '-'
                            ))
                            template_count += 1
                        except (json.JSONDecodeError, IOError) as e:
                            logging.warning(f"Failed to load template {json_file}: {e}")
            except Exception as e:
                logging.warning(f"Failed to load file-based templates: {e}")

            self.update_status(f"Loaded {template_count} ticket templates")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load ticket templates: {e}")

    def refresh_response_templates(self):
        """Refresh response templates list"""
        try:
            # Clear existing items
            for item in self.response_templates_tree.get_children():
                self.response_templates_tree.delete(item)

            # Load from database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT template_id, name, subject, category, created_by,
                           created_datetime, usage_count
                    FROM response_templates
                    ORDER BY created_datetime DESC
                ''')

                templates = cursor.fetchall()
            finally:
                conn.close()

            # Add to tree
            for template in templates:
                self.response_templates_tree.insert('', tk.END, values=(
                    template['template_id'],
                    template['name'],
                    template['subject'],
                    template['category'] or 'General',
                    template['created_by'],
                    template['created_datetime'],
                    template['usage_count'] or 0
                ))

            self.update_status(f"Loaded {len(templates)} response templates")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load response templates: {e}")

    def create_ticket_template(self):
        """Create a new ticket template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("➕ Create Ticket Template")
        dialog.geometry("1200x750")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="➕ Create Ticket Template", style='Heading.TLabel').pack(pady=(0, 20))

        # Name
        ttk.Label(form_frame, text="Template Name:").pack(anchor="w")
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=50).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category:").pack(anchor="w")
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=47)
        category_combo.pack(fill="x", pady=(5, 10))
        if SUPPORT_CATEGORIES:
            category_combo.current(0)

        # Priority
        ttk.Label(form_frame, text="Priority:").pack(anchor="w")
        priority_var = tk.StringVar()
        priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, values=TICKET_PRIORITIES, state="readonly", width=47)
        priority_combo.pack(fill="x", pady=(5, 10))
        if TICKET_PRIORITIES:
            priority_combo.current(1)  # Default to Medium

        # Title Template
        ttk.Label(form_frame, text="Title Template:").pack(anchor="w")
        title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=title_var, width=50).pack(fill="x", pady=(5, 10))

        # Description Template
        ttk.Label(form_frame, text="Description Template:").pack(anchor="w")
        desc_text = scrolledtext.ScrolledText(form_frame, height=8, width=50)
        desc_text.pack(fill="both", expand=True, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_template():
            name = name_var.get().strip()
            category = category_var.get()
            priority = priority_var.get()
            title_template = title_var.get().strip()
            description_template = desc_text.get("1.0", tk.END).strip()

            if not all([name, category, priority, title_template, description_template]):
                messagebox.showerror("Error", "All fields are required")
                return

            try:
                template_id = self.support.create_ticket_template(
                    name, title_template, description_template, category, priority
                )
                messagebox.showinfo("Success", f"Ticket template created successfully (ID: {template_id})")
                dialog.destroy()
                self.refresh_ticket_templates()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create template: {e}")

        ttk.Button(btn_frame, text="💾 Save", command=save_template).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def edit_ticket_template(self):
        """Edit selected ticket template"""
        selection = self.ticket_templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to edit")
            return

        item = self.ticket_templates_tree.item(selection[0])
        template_id = item['values'][0]

        # Load template data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ticket_templates WHERE template_id = ?', (template_id,))
            template = cursor.fetchone()
            conn.close()

            if not template:
                messagebox.showerror("Error", "Template not found")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {e}")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"✏️ Edit Ticket Template #{template_id}")
        dialog.geometry("1200x750")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text=f"✏️ Edit Ticket Template #{template_id}", style='Heading.TLabel').pack(pady=(0, 20))

        # Name
        ttk.Label(form_frame, text="Template Name:").pack(anchor="w")
        name_var = tk.StringVar(value=template['name'])
        ttk.Entry(form_frame, textvariable=name_var, width=50).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category:").pack(anchor="w")
        category_var = tk.StringVar(value=template['category'])
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=47)
        category_combo.pack(fill="x", pady=(5, 10))

        # Priority
        ttk.Label(form_frame, text="Priority:").pack(anchor="w")
        priority_var = tk.StringVar(value=template['priority'])
        priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, values=TICKET_PRIORITIES, state="readonly", width=47)
        priority_combo.pack(fill="x", pady=(5, 10))

        # Title Template
        ttk.Label(form_frame, text="Title Template:").pack(anchor="w")
        title_var = tk.StringVar(value=template['title_template'])
        ttk.Entry(form_frame, textvariable=title_var, width=50).pack(fill="x", pady=(5, 10))

        # Description Template
        ttk.Label(form_frame, text="Description Template:").pack(anchor="w")
        desc_text = scrolledtext.ScrolledText(form_frame, height=8, width=50)
        desc_text.insert("1.0", template['description_template'])
        desc_text.pack(fill="both", expand=True, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_changes():
            name = name_var.get().strip()
            category = category_var.get()
            priority = priority_var.get()
            title_template = title_var.get().strip()
            description_template = desc_text.get("1.0", tk.END).strip()

            if not all([name, category, priority, title_template, description_template]):
                messagebox.showerror("Error", "All fields are required")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE ticket_templates
                    SET name = ?, title_template = ?, description_template = ?,
                        category = ?, priority = ?
                    WHERE template_id = ?
                ''', (name, title_template, description_template, category, priority, template_id))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Template updated successfully")
                dialog.destroy()
                self.refresh_ticket_templates()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update template: {e}")

        ttk.Button(btn_frame, text="💾 Save Changes", command=save_changes).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def delete_ticket_template(self):
        """Delete selected ticket template"""
        selection = self.ticket_templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to delete")
            return

        item = self.ticket_templates_tree.item(selection[0])
        template_id = item['values'][0]
        template_name = item['values'][1]

        if not messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to delete template '{template_name}'?\n\nThis action cannot be undone."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ticket_templates WHERE template_id = ?', (template_id,))
            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Template deleted successfully")
            self.refresh_ticket_templates()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete template: {e}")

    def create_response_template(self):
        """Create a new response template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("➕ Create Response Template")
        dialog.geometry("1200x750")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="➕ Create Response Template", style='Heading.TLabel').pack(pady=(0, 20))

        # Name
        ttk.Label(form_frame, text="Template Name:").pack(anchor="w")
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=50).pack(fill="x", pady=(5, 10))

        # Subject
        ttk.Label(form_frame, text="Subject:").pack(anchor="w")
        subject_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=subject_var, width=50).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category (optional):").pack(anchor="w")
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=47)
        category_combo.pack(fill="x", pady=(5, 10))

        # Content
        ttk.Label(form_frame, text="Content:").pack(anchor="w")
        ttk.Label(form_frame, text="Use variables: {student_name}, {ticket_id}, {ticket_title}",
                 font=('Segoe UI', 8), foreground='gray').pack(anchor="w")
        content_text = scrolledtext.ScrolledText(form_frame, height=10, width=50)
        content_text.pack(fill="both", expand=True, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_template():
            name = name_var.get().strip()
            subject = subject_var.get().strip()
            category = category_var.get() or None
            content = content_text.get("1.0", tk.END).strip()

            if not all([name, subject, content]):
                messagebox.showerror("Error", "Name, subject, and content are required")
                return

            try:
                template_id = self.support.create_response_template(
                    name, subject, content, category, ['student_name', 'ticket_id', 'ticket_title']
                )
                messagebox.showinfo("Success", f"Response template created successfully (ID: {template_id})")
                dialog.destroy()
                self.refresh_response_templates()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create template: {e}")

        ttk.Button(btn_frame, text="💾 Save", command=save_template).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def edit_response_template(self):
        """Edit selected response template"""
        selection = self.response_templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to edit")
            return

        item = self.response_templates_tree.item(selection[0])
        template_id = item['values'][0]

        # Load template data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM response_templates WHERE template_id = ?', (template_id,))
            template = cursor.fetchone()
            conn.close()

            if not template:
                messagebox.showerror("Error", "Template not found")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {e}")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"✏️ Edit Response Template #{template_id}")
        dialog.geometry("1200x750")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text=f"✏️ Edit Response Template #{template_id}", style='Heading.TLabel').pack(pady=(0, 20))

        # Name
        ttk.Label(form_frame, text="Template Name:").pack(anchor="w")
        name_var = tk.StringVar(value=template['name'])
        ttk.Entry(form_frame, textvariable=name_var, width=50).pack(fill="x", pady=(5, 10))

        # Subject
        ttk.Label(form_frame, text="Subject:").pack(anchor="w")
        subject_var = tk.StringVar(value=template['subject'])
        ttk.Entry(form_frame, textvariable=subject_var, width=50).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category (optional):").pack(anchor="w")
        category_var = tk.StringVar(value=template['category'] or '')
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=47)
        category_combo.pack(fill="x", pady=(5, 10))

        # Content
        ttk.Label(form_frame, text="Content:").pack(anchor="w")
        content_text = scrolledtext.ScrolledText(form_frame, height=10, width=50)
        content_text.insert("1.0", template['content'])
        content_text.pack(fill="both", expand=True, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_changes():
            name = name_var.get().strip()
            subject = subject_var.get().strip()
            category = category_var.get() or None
            content = content_text.get("1.0", tk.END).strip()

            if not all([name, subject, content]):
                messagebox.showerror("Error", "Name, subject, and content are required")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE response_templates
                    SET name = ?, subject = ?, content = ?, category = ?
                    WHERE template_id = ?
                ''', (name, subject, content, category, template_id))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Template updated successfully")
                dialog.destroy()
                self.refresh_response_templates()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update template: {e}")

        ttk.Button(btn_frame, text="💾 Save Changes", command=save_changes).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def delete_response_template(self):
        """Delete selected response template"""
        selection = self.response_templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to delete")
            return

        item = self.response_templates_tree.item(selection[0])
        template_id = item['values'][0]
        template_name = item['values'][1]

        if not messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to delete template '{template_name}'?\n\nThis action cannot be undone."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM response_templates WHERE template_id = ?', (template_id,))
            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Template deleted successfully")
            self.refresh_response_templates()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete template: {e}")

    def show_manage_kb(self):
        """Show knowledge base management interface (staff only)"""
        self.clear_content()

        kb_mgmt_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(kb_mgmt_frame, text="📖 Manage KB")

        # Configure frame to expand
        kb_mgmt_frame.rowconfigure(0, weight=1)
        kb_mgmt_frame.columnconfigure(0, weight=1)

        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] not in ('staff', 'admin'):
            ttk.Label(kb_mgmt_frame, text="❌ Staff access required",
                     style='Title.TLabel').pack(pady=20)
            return

        ttk.Label(kb_mgmt_frame, text="📖 Knowledge Base Management",
                 style='Title.TLabel').pack(pady=(0, 20))

        # Knowledge base management UI
        kb_controls = ttk.Frame(kb_mgmt_frame)
        kb_controls.pack(fill=tk.X, pady=10)

        ttk.Button(kb_controls, text="➕ Add Article", command=self.add_kb_article).pack(side=tk.LEFT, padx=5)
        ttk.Button(kb_controls, text="✏️ Edit Article", command=self.edit_kb_article).pack(side=tk.LEFT, padx=5)
        ttk.Button(kb_controls, text="📢 Publish Article", command=self.publish_kb_article).pack(side=tk.LEFT, padx=5)
        ttk.Button(kb_controls, text="🗑️ Delete Article", command=self.delete_kb_article).pack(side=tk.LEFT, padx=5)
        ttk.Button(kb_controls, text="🔄 Refresh", command=self.refresh_kb_articles).pack(side=tk.LEFT, padx=5)

        # Search and filter frame
        search_frame = ttk.Frame(kb_mgmt_frame)
        search_frame.pack(fill=tk.X, pady=10)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.kb_search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.kb_search_var, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="🔍 Search", command=self.search_kb_articles).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="🔄 Clear", command=self.clear_kb_search).pack(side=tk.LEFT, padx=5)

        # Show all toggle
        self.kb_show_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(search_frame, text="Show Unpublished", variable=self.kb_show_all_var,
                       command=self.refresh_kb_articles).pack(side=tk.LEFT, padx=10)

        # KB articles list
        kb_list_frame = ttk.LabelFrame(kb_mgmt_frame, text="Knowledge Base Articles", padding=10)
        kb_list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ("ID", "Title", "Category", "Status", "Views", "Helpful", "Author", "Last Updated")
        self.kb_tree = ttk.Treeview(kb_list_frame, columns=columns, show="headings", height=12)

        # Configure columns
        self.kb_tree.column("ID", width=50)
        self.kb_tree.column("Title", width=250)
        self.kb_tree.column("Category", width=120)
        self.kb_tree.column("Status", width=100)
        self.kb_tree.column("Views", width=70)
        self.kb_tree.column("Helpful", width=70)
        self.kb_tree.column("Author", width=100)
        self.kb_tree.column("Last Updated", width=150)

        for col in columns:
            self.kb_tree.heading(col, text=col)

        # Double-click to view
        self.kb_tree.bind('<Double-1>', lambda e: self.view_kb_article_details())

        scrollbar = ttk.Scrollbar(kb_list_frame, orient=tk.VERTICAL, command=self.kb_tree.yview)
        self.kb_tree.configure(yscrollcommand=scrollbar.set)
        self.kb_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load articles
        self.refresh_kb_articles()

    def refresh_kb_articles(self):
        """Refresh KB articles list"""
        try:
            # Clear existing items
            for item in self.kb_tree.get_children():
                self.kb_tree.delete(item)

            # Load from database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Build query based on filters
                show_unpublished = self.kb_show_all_var.get()
                if show_unpublished:
                    query = 'SELECT * FROM kb_articles ORDER BY created_datetime DESC'
                else:
                    query = 'SELECT * FROM kb_articles WHERE is_published = 1 ORDER BY created_datetime DESC'

                cursor.execute(query)
                articles = cursor.fetchall()
            finally:
                conn.close()

            # Add to tree
            for article in articles:
                status = "Published" if article['is_published'] else "Draft"
                self.kb_tree.insert('', tk.END, values=(
                    article['article_id'],
                    article['title'],
                    article['category'],
                    status,
                    article['view_count'] or 0,
                    article['helpful_votes'] or 0,
                    article['author_id'],
                    article['created_datetime']
                ))

            self.update_status(f"Loaded {len(articles)} KB articles")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load KB articles: {e}")

    def search_kb_articles(self):
        """Search KB articles"""
        query = self.kb_search_var.get().strip()
        if not query:
            self.refresh_kb_articles()
            return

        try:
            # Clear existing items
            for item in self.kb_tree.get_children():
                self.kb_tree.delete(item)

            # Search in database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                search_query = f"%{escape_like(query)}%"
                show_unpublished = self.kb_show_all_var.get()

                if show_unpublished:
                    cursor.execute('''
                        SELECT * FROM kb_articles
                        WHERE title LIKE ? OR content LIKE ? OR category LIKE ? OR search_keywords LIKE ?
                        ORDER BY created_datetime DESC
                    ''', (search_query, search_query, search_query, search_query))
                else:
                    cursor.execute('''
                        SELECT * FROM kb_articles
                        WHERE (title LIKE ? OR content LIKE ? OR category LIKE ? OR search_keywords LIKE ?)
                        AND is_published = 1
                        ORDER BY created_datetime DESC
                    ''', (search_query, search_query, search_query, search_query))

                articles = cursor.fetchall()
            finally:
                conn.close()

            # Add to tree
            for article in articles:
                status = "Published" if article['is_published'] else "Draft"
                self.kb_tree.insert('', tk.END, values=(
                    article['article_id'],
                    article['title'],
                    article['category'],
                    status,
                    article['view_count'] or 0,
                    article['helpful_votes'] or 0,
                    article['author_id'],
                    article['created_datetime']
                ))

            self.update_status(f"Found {len(articles)} articles matching '{query}'")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to search KB articles: {e}")

    def clear_kb_search(self):
        """Clear KB search"""
        self.kb_search_var.set('')
        self.refresh_kb_articles()

    def add_kb_article(self):
        """Create a new KB article"""
        dialog = tk.Toplevel(self.root)
        dialog.title("➕ Create KB Article")
        dialog.geometry("1300x800")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="➕ Create Knowledge Base Article", style='Heading.TLabel').pack(pady=(0, 20))

        # Title
        ttk.Label(form_frame, text="Title:").pack(anchor="w")
        title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=title_var, width=60).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category:").pack(anchor="w")
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=57)
        category_combo.pack(fill="x", pady=(5, 10))
        if SUPPORT_CATEGORIES:
            category_combo.current(0)

        # Summary
        ttk.Label(form_frame, text="Summary (optional):").pack(anchor="w")
        summary_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=summary_var, width=60).pack(fill="x", pady=(5, 10))

        # Tags
        ttk.Label(form_frame, text="Tags (comma-separated):").pack(anchor="w")
        tags_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=tags_var, width=60).pack(fill="x", pady=(5, 10))

        # Content
        ttk.Label(form_frame, text="Content:").pack(anchor="w")
        content_text = scrolledtext.ScrolledText(form_frame, height=12, width=60)
        content_text.pack(fill="both", expand=True, pady=(5, 10))

        # Publish immediately checkbox
        publish_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Publish immediately", variable=publish_var).pack(anchor="w", pady=5)

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_article():
            title = title_var.get().strip()
            category = category_var.get()
            summary = summary_var.get().strip() or None
            tags_str = tags_var.get().strip()
            tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else None
            content = content_text.get("1.0", tk.END).strip()
            is_published = publish_var.get()

            if not all([title, category, content]):
                messagebox.showerror("Error", "Title, category, and content are required")
                return

            try:
                article_id = self.support.create_kb_article(
                    title, content, category, summary, tags, is_published
                )
                status = "published" if is_published else "created as draft"
                messagebox.showinfo("Success", f"KB article {status} successfully (ID: {article_id})")
                dialog.destroy()
                self.refresh_kb_articles()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create article: {e}")

        ttk.Button(btn_frame, text="💾 Save", command=save_article).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def edit_kb_article(self):
        """Edit selected KB article"""
        selection = self.kb_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an article to edit")
            return

        item = self.kb_tree.item(selection[0])
        article_id = item['values'][0]

        # Load article data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM kb_articles WHERE article_id = ?', (article_id,))
            article = cursor.fetchone()
            conn.close()

            if not article:
                messagebox.showerror("Error", "Article not found")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load article: {e}")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"✏️ Edit KB Article #{article_id}")
        dialog.geometry("1300x800")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text=f"✏️ Edit KB Article #{article_id}", style='Heading.TLabel').pack(pady=(0, 20))

        # Title
        ttk.Label(form_frame, text="Title:").pack(anchor="w")
        title_var = tk.StringVar(value=article['title'])
        ttk.Entry(form_frame, textvariable=title_var, width=60).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category:").pack(anchor="w")
        category_var = tk.StringVar(value=article['category'])
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=57)
        category_combo.pack(fill="x", pady=(5, 10))

        # Summary
        ttk.Label(form_frame, text="Summary (optional):").pack(anchor="w")
        summary_var = tk.StringVar(value=article['summary'] or '')
        ttk.Entry(form_frame, textvariable=summary_var, width=60).pack(fill="x", pady=(5, 10))

        # Tags
        ttk.Label(form_frame, text="Tags (comma-separated):").pack(anchor="w")
        try:
            tags_list = json.loads(article['tags']) if article['tags'] else []
            tags_str = ', '.join(tags_list)
        except (ValueError, TypeError, KeyError):
            tags_str = ''
        tags_var = tk.StringVar(value=tags_str)
        ttk.Entry(form_frame, textvariable=tags_var, width=60).pack(fill="x", pady=(5, 10))

        # Content
        ttk.Label(form_frame, text="Content:").pack(anchor="w")
        content_text = scrolledtext.ScrolledText(form_frame, height=12, width=60)
        content_text.insert("1.0", article['content'])
        content_text.pack(fill="both", expand=True, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_changes():
            title = title_var.get().strip()
            category = category_var.get()
            summary = summary_var.get().strip() or None
            tags_str = tags_var.get().strip()
            tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []
            content = content_text.get("1.0", tk.END).strip()

            if not all([title, category, content]):
                messagebox.showerror("Error", "Title, category, and content are required")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE kb_articles
                    SET title = ?, content = ?, summary = ?, category = ?, tags = ?
                    WHERE article_id = ?
                ''', (title, content, summary, category, json.dumps(tags), article_id))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Article updated successfully")
                dialog.destroy()
                self.refresh_kb_articles()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update article: {e}")

        ttk.Button(btn_frame, text="💾 Save Changes", command=save_changes).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def publish_kb_article(self):
        """Publish selected KB article"""
        selection = self.kb_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an article to publish")
            return

        item = self.kb_tree.item(selection[0])
        article_id = item['values'][0]
        article_title = item['values'][1]
        status = item['values'][3]

        if status == "Published":
            messagebox.showinfo("Info", "This article is already published")
            return

        if not messagebox.askyesno("Confirm Publish",
                                   f"Publish article '{article_title}'?\n\nThis will make it visible to all users."):
            return

        try:
            self.support.publish_kb_article(article_id)
            messagebox.showinfo("Success", "Article published successfully")
            self.refresh_kb_articles()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to publish article: {e}")

    def delete_kb_article(self):
        """Delete selected KB article"""
        selection = self.kb_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an article to delete")
            return

        item = self.kb_tree.item(selection[0])
        article_id = item['values'][0]
        article_title = item['values'][1]

        if not messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to delete article '{article_title}'?\n\nThis action cannot be undone."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM kb_articles WHERE article_id = ?', (article_id,))
            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Article deleted successfully")
            self.refresh_kb_articles()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete article: {e}")

    def view_kb_article_details(self):
        """View detailed information about a KB article"""
        selection = self.kb_tree.selection()
        if not selection:
            return

        item = self.kb_tree.item(selection[0])
        article_id = item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM kb_articles WHERE article_id = ?', (article_id,))
            article = cursor.fetchone()
            conn.close()

            if not article:
                messagebox.showerror("Error", "Article not found")
                return

            # Create detail window
            detail_window = tk.Toplevel(self.root)
            detail_window.title(f"📖 {article['title']}")
            detail_window.geometry("1400x850")

            # Scrollable frame
            canvas = tk.Canvas(detail_window)
            scrollbar = ttk.Scrollbar(detail_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas, padding="20")

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Article details
            ttk.Label(scrollable_frame, text=article['title'], font=('Segoe UI', 16, 'bold')).pack(anchor="w", pady=(0, 10))

            # Metadata
            meta_frame = ttk.Frame(scrollable_frame)
            meta_frame.pack(fill="x", pady=(0, 20))

            ttk.Label(meta_frame, text=f"📁 Category: {article['category']}", font=('Segoe UI', 10)).pack(anchor="w")
            ttk.Label(meta_frame, text=f"📊 Status: {'Published' if article['is_published'] else 'Draft'}", font=('Segoe UI', 10)).pack(anchor="w")
            ttk.Label(meta_frame, text=f"👀 Views: {article['view_count'] or 0}", font=('Segoe UI', 10)).pack(anchor="w")
            ttk.Label(meta_frame, text=f"👍 Helpful Votes: {article['helpful_votes'] or 0}", font=('Segoe UI', 10)).pack(anchor="w")

            # Tags
            if article['tags']:
                try:
                    tags = json.loads(article['tags'])
                    if tags:
                        tags_text = ', '.join(tags)
                        ttk.Label(meta_frame, text=f"🏷️ Tags: {tags_text}", font=('Segoe UI', 10)).pack(anchor="w")
                except (ValueError, TypeError, KeyError):
                    pass

            # Summary
            if article['summary']:
                ttk.Label(scrollable_frame, text="Summary:", font=('Segoe UI', 11, 'bold')).pack(anchor="w", pady=(10, 5))
                summary_text = tk.Text(scrollable_frame, wrap=tk.WORD, height=3, font=('Segoe UI', 10))
                summary_text.insert("1.0", article['summary'])
                summary_text.config(state='disabled')
                summary_text.pack(fill="x", pady=(0, 10))

            # Content
            ttk.Label(scrollable_frame, text="Content:", font=('Segoe UI', 11, 'bold')).pack(anchor="w", pady=(10, 5))
            content_text = tk.Text(scrollable_frame, wrap=tk.WORD, height=20, font=('Segoe UI', 10))
            content_text.insert("1.0", article['content'])
            content_text.config(state='disabled')
            content_text.pack(fill="both", expand=True)

            # Pack canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load article details: {e}")

    def show_bulk_operations(self):
        """Show bulk operations interface (staff only)"""
        self.clear_content()

        bulk_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(bulk_frame, text="📦 Bulk Operations")

        # Configure frame to expand
        bulk_frame.rowconfigure(0, weight=1)
        bulk_frame.columnconfigure(0, weight=1)

        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] not in ('staff', 'admin'):
            ttk.Label(bulk_frame, text="❌ Staff access required",
                     style='Title.TLabel').pack(pady=20)
            return

        ttk.Label(bulk_frame, text="📦 Bulk Operations",
                 style='Title.TLabel').pack(pady=(0, 20))

        # Bulk operations UI
        bulk_notebook = ttk.Notebook(bulk_frame)
        bulk_notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # Bulk Assign Tab
        bulk_assign_frame = ttk.Frame(bulk_notebook, padding=10)
        bulk_notebook.add(bulk_assign_frame, text="👤 Bulk Assign")

        ttk.Label(bulk_assign_frame, text="Assign multiple tickets to a staff member", font=('Segoe UI', 11, 'bold')).pack(pady=10)

        # Ticket IDs
        ttk.Label(bulk_assign_frame, text="Ticket IDs (comma-separated):").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_assign_tickets_var = tk.StringVar()
        ttk.Entry(bulk_assign_frame, textvariable=self.bulk_assign_tickets_var, width=60).pack(fill=tk.X, padx=10, pady=5)

        # Staff member
        ttk.Label(bulk_assign_frame, text="Assign To (username):").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_assign_staff_var = tk.StringVar()
        ttk.Entry(bulk_assign_frame, textvariable=self.bulk_assign_staff_var, width=60).pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(bulk_assign_frame, text="📋 Assign Tickets", command=self.perform_bulk_assign).pack(pady=20)

        # Bulk Status Update Tab
        bulk_status_frame = ttk.Frame(bulk_notebook, padding=10)
        bulk_notebook.add(bulk_status_frame, text="📊 Bulk Status")

        ttk.Label(bulk_status_frame, text="Update status for multiple tickets", font=('Segoe UI', 11, 'bold')).pack(pady=10)

        # Ticket IDs
        ttk.Label(bulk_status_frame, text="Ticket IDs (comma-separated):").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_status_tickets_var = tk.StringVar()
        ttk.Entry(bulk_status_frame, textvariable=self.bulk_status_tickets_var, width=60).pack(fill=tk.X, padx=10, pady=5)

        # Status
        ttk.Label(bulk_status_frame, text="New Status:").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_status_var = tk.StringVar()
        status_combo = ttk.Combobox(bulk_status_frame, textvariable=self.bulk_status_var, values=TICKET_STATUSES, state="readonly", width=57)
        status_combo.pack(fill=tk.X, padx=10, pady=5)
        if TICKET_STATUSES:
            status_combo.current(0)

        ttk.Button(bulk_status_frame, text="🔄 Update Status", command=self.perform_bulk_status_update).pack(pady=20)

        # Bulk Priority Update Tab
        bulk_priority_frame = ttk.Frame(bulk_notebook, padding=10)
        bulk_notebook.add(bulk_priority_frame, text="⚡ Bulk Priority")

        ttk.Label(bulk_priority_frame, text="Update priority for multiple tickets", font=('Segoe UI', 11, 'bold')).pack(pady=10)

        # Ticket IDs
        ttk.Label(bulk_priority_frame, text="Ticket IDs (comma-separated):").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_priority_tickets_var = tk.StringVar()
        ttk.Entry(bulk_priority_frame, textvariable=self.bulk_priority_tickets_var, width=60).pack(fill=tk.X, padx=10, pady=5)

        # Priority
        ttk.Label(bulk_priority_frame, text="New Priority:").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_priority_var = tk.StringVar()
        priority_combo = ttk.Combobox(bulk_priority_frame, textvariable=self.bulk_priority_var, values=TICKET_PRIORITIES, state="readonly", width=57)
        priority_combo.pack(fill=tk.X, padx=10, pady=5)
        if TICKET_PRIORITIES:
            priority_combo.current(0)

        ttk.Button(bulk_priority_frame, text="⚡ Update Priority", command=self.perform_bulk_priority_update).pack(pady=20)

        # Bulk Category Update Tab
        bulk_category_frame = ttk.Frame(bulk_notebook, padding=10)
        bulk_notebook.add(bulk_category_frame, text="📂 Bulk Category")

        ttk.Label(bulk_category_frame, text="Update category for multiple tickets", font=('Segoe UI', 11, 'bold')).pack(pady=10)

        # Ticket IDs
        ttk.Label(bulk_category_frame, text="Ticket IDs (comma-separated):").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_category_tickets_var = tk.StringVar()
        ttk.Entry(bulk_category_frame, textvariable=self.bulk_category_tickets_var, width=60).pack(fill=tk.X, padx=10, pady=5)

        # Category
        ttk.Label(bulk_category_frame, text="New Category:").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_category_var = tk.StringVar()
        category_combo = ttk.Combobox(bulk_category_frame, textvariable=self.bulk_category_var, values=SUPPORT_CATEGORIES, state="readonly", width=57)
        category_combo.pack(fill=tk.X, padx=10, pady=5)
        if SUPPORT_CATEGORIES:
            category_combo.current(0)

        ttk.Button(bulk_category_frame, text="📂 Update Category", command=self.perform_bulk_category_update).pack(pady=20)

    def perform_bulk_assign(self):
        """Perform bulk ticket assignment"""
        tickets_str = self.bulk_assign_tickets_var.get().strip()
        staff_username = self.bulk_assign_staff_var.get().strip()

        if not tickets_str or not staff_username:
            messagebox.showerror("Error", "Please provide ticket IDs and staff username")
            return

        try:
            # Parse ticket IDs
            ticket_ids = [int(tid.strip()) for tid in tickets_str.split(',')]

            if not messagebox.askyesno("Confirm Bulk Assign",
                                       f"Assign {len(ticket_ids)} tickets to {staff_username}?"):
                return

            # Perform bulk update
            updated_count = self.support.bulk_update_tickets(ticket_ids, {'assigned_to': staff_username})

            messagebox.showinfo("Success", f"Successfully assigned {updated_count} tickets to {staff_username}")
            self.bulk_assign_tickets_var.set('')
            self.bulk_assign_staff_var.set('')

        except ValueError:
            messagebox.showerror("Error", "Invalid ticket IDs. Please use comma-separated numbers.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to perform bulk assign: {e}")

    def perform_bulk_priority_update(self):
        """Perform bulk priority update"""
        tickets_str = self.bulk_priority_tickets_var.get().strip()
        new_priority = self.bulk_priority_var.get()

        if not tickets_str or not new_priority:
            messagebox.showerror("Error", "Please provide ticket IDs and priority")
            return

        try:
            # Parse ticket IDs
            ticket_ids = [int(tid.strip()) for tid in tickets_str.split(',')]

            if not messagebox.askyesno("Confirm Bulk Update",
                                       f"Update priority to '{new_priority}' for {len(ticket_ids)} tickets?"):
                return

            # Perform bulk update
            updated_count = self.support.bulk_update_tickets(ticket_ids, {'priority': new_priority})

            messagebox.showinfo("Success", f"Successfully updated priority for {updated_count} tickets")
            self.bulk_priority_tickets_var.set('')

        except ValueError:
            messagebox.showerror("Error", "Invalid ticket IDs. Please use comma-separated numbers.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to perform bulk priority update: {e}")

    def perform_bulk_category_update(self):
        """Perform bulk category update"""
        tickets_str = self.bulk_category_tickets_var.get().strip()
        new_category = self.bulk_category_var.get()

        if not tickets_str or not new_category:
            messagebox.showerror("Error", "Please provide ticket IDs and category")
            return

        try:
            # Parse ticket IDs
            ticket_ids = [int(tid.strip()) for tid in tickets_str.split(',')]

            if not messagebox.askyesno("Confirm Bulk Update",
                                       f"Update category to '{new_category}' for {len(ticket_ids)} tickets?"):
                return

            # Perform bulk update
            updated_count = self.support.bulk_update_tickets(ticket_ids, {'category': new_category})

            messagebox.showinfo("Success", f"Successfully updated category for {updated_count} tickets")
            self.bulk_category_tickets_var.set('')

        except ValueError:
            messagebox.showerror("Error", "Invalid ticket IDs. Please use comma-separated numbers.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to perform bulk category update: {e}")

    def perform_bulk_status_update(self, support, tickets):
        """Perform bulk status update from ticket list"""
        print("\n📊 BULK STATUS UPDATE FROM LIST")
        print("="*40)
        
        # Status selection
        print("\nNew Status:")
        for i, status in enumerate(TICKET_STATUSES, 1):
            print(f"{i}. {status}")
        
        status_choice = input(f"Select new status (1-{len(TICKET_STATUSES)}): ").strip()
        if not status_choice.isdigit() or not 1 <= int(status_choice) <= len(TICKET_STATUSES):
            print("❌ Invalid status choice.")
            return
        
        new_status = TICKET_STATUSES[int(status_choice) - 1]
        
        # Get ticket IDs to update
        ticket_ids_input = input("Enter ticket numbers to update (comma-separated) or 'all' for all tickets: ").strip()
        
        if ticket_ids_input.lower() == 'all':
            ticket_ids = [t['ticket_id'] for t in tickets]
        else:
            try:
                ticket_ids = [int(id.strip()) for id in ticket_ids_input.split(',')]
                # Validate ticket IDs are in the current list
                valid_ids = [t['ticket_id'] for t in tickets]
                ticket_ids = [tid for tid in ticket_ids if tid in valid_ids]
            except ValueError:
                print("❌ Invalid ticket IDs.")
                return
        
        if not ticket_ids:
            print("❌ No valid ticket IDs provided.")
            return
        
        # Confirm operation
        print(f"\n📋 Updating {len(ticket_ids)} tickets to status '{new_status}'")
        confirm = input("Confirm bulk status update? (y/n): ").lower()
        
        if confirm == 'y':
            try:
                updates = {'status': new_status}
                updated_count = support.bulk_update_tickets(ticket_ids, updates)
                print(f"✅ Successfully updated status for {updated_count} tickets")
            except Exception as e:
                print(f"❌ Error during bulk status update: {e}")
        else:
            print("❌ Bulk status update cancelled.")

    def use_template(self, template):
        """Use a selected template to create a ticket"""
        try:
            # Switch to create ticket tab with template pre-filled
            self.selected_template_data = template
            self.show_create_ticket()
            
            # Pre-fill the form
            if hasattr(self, 'title_entry'):
                self.title_entry.delete(0, tk.END)
                self.title_entry.insert(0, template['title_template'])
            
            if hasattr(self, 'description_text'):
                self.description_text.delete(1.0, tk.END)
                self.description_text.insert(1.0, template['description_template'])
            
            if hasattr(self, 'category_var'):
                self.category_var.set(template['category'])
            
            if hasattr(self, 'priority_var'):
                self.priority_var.set(template['priority'])
            
            messagebox.showinfo("Template Loaded", f"Template '{template['name']}' has been loaded. You can customize it before submitting.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not use template: {e}")

    def show_ticket_templates(self):
        """Show ticket templates for students"""
        self.clear_content()
        
        templates_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(templates_frame, text="📄 Templates")

        # Configure frame to expand
        templates_frame.rowconfigure(0, weight=1)
        templates_frame.columnconfigure(0, weight=1)

        header_frame = ttk.Frame(templates_frame)
        header_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(header_frame, text="📄 Ticket Templates",
                  style='Title.TLabel').pack(side="left")

        search_frame = ttk.Frame(header_frame)
        search_frame.pack(side="right")

        self.template_search_var = tk.StringVar()
        template_search_entry = ttk.Entry(search_frame, width=30,
                                          textvariable=self.template_search_var,
                                          font=('Segoe UI', 10))
        template_search_entry.pack(side="left", padx=(0, 5))
        template_search_entry.bind('<Return>', lambda _: self._load_templates())

        ttk.Button(search_frame, text="🔍 Search",
                   command=self._load_templates).pack(side="left")

        ttk.Button(search_frame, text="🔄 Refresh",
                   command=self._refresh_template_filters).pack(side="left", padx=(5, 0))

        filter_frame = ttk.LabelFrame(templates_frame, text="Filters", padding=10)
        filter_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(filter_frame, text="Category:").grid(row=0, column=0, sticky="w")
        self.template_category_var = tk.StringVar(value="All")
        self.template_category_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.template_category_var,
            state="readonly",
            width=25
        )
        self.template_category_combo.grid(row=0, column=1, padx=(5, 15))
        self.template_category_combo.bind('<<ComboboxSelected>>', lambda _: self._load_templates())

        ttk.Label(filter_frame, text="Priority:").grid(row=0, column=2, sticky="w")
        self.template_priority_var = tk.StringVar(value="All")
        priority_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.template_priority_var,
            values=["All"] + TICKET_PRIORITIES if TICKET_PRIORITIES else ["All"],
            state="readonly",
            width=20
        )
        priority_combo.grid(row=0, column=3, padx=(5, 0))
        priority_combo.bind('<<ComboboxSelected>>', lambda _: self._load_templates())

        ttk.Button(filter_frame, text="Clear Filters",
                   command=self._reset_template_filters).grid(row=0, column=4, padx=(15, 0))

        content_frame = ttk.Frame(templates_frame)
        content_frame.pack(fill="both", expand=True)

        template_columns = ("Name", "Category", "Priority", "Usage", "Created")
        self.templates_tree = ttk.Treeview(content_frame, columns=template_columns, show="headings", height=16)
        for col in template_columns:
            width = 220 if col == "Name" else 140
            self.templates_tree.heading(col, text=col)
            self.templates_tree.column(col, width=width, anchor="w")

        self.templates_tree.pack(side="left", fill="both", expand=True)
        self.templates_tree.bind('<<TreeviewSelect>>', self._on_template_select)

        template_scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=self.templates_tree.yview)
        template_scrollbar.pack(side="right", fill="y")
        self.templates_tree.configure(yscrollcommand=template_scrollbar.set)

        detail_frame = ttk.LabelFrame(templates_frame, text="Template Details", padding=10)
        detail_frame.pack(fill="x", pady=(15, 0))

        self.template_title_var = tk.StringVar(value="Select a template to view details.")
        ttk.Label(detail_frame, textvariable=self.template_title_var,
                  font=('Segoe UI', 10, 'bold')).pack(anchor="w", pady=(0, 8))

        self.template_body_text = scrolledtext.ScrolledText(detail_frame, height=6, wrap=tk.WORD, state='disabled')
        self.template_body_text.pack(fill="x", expand=True, pady=(0, 10))

        template_action_frame = ttk.Frame(detail_frame)
        template_action_frame.pack(fill="x")

        ttk.Button(template_action_frame, text="Copy Title",
                   command=self._copy_template_title).pack(side="left")
        ttk.Button(template_action_frame, text="Copy Description",
                   command=self._copy_template_description).pack(side="left", padx=5)

        self._load_template_categories()
        self._load_templates()

    def _load_template_categories(self):
        """Load template categories into the category combobox."""
        try:
            def fetch(conn):
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT category FROM ticket_templates ORDER BY category')
                return [row[0] for row in cursor.fetchall()]

            categories = self._safe_db_call(fetch)
            values = ["All"] + categories if categories else ["All"]
            self.template_category_combo['values'] = values
            if self.template_category_var.get() not in values:
                self.template_category_var.set("All")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load template categories: {exc}")
            self.template_category_combo['values'] = ["All"]
            self.template_category_var.set("All")

    def _refresh_template_filters(self):
        self._load_template_categories()
        self._load_templates()

    def _reset_template_filters(self):
        self.template_search_var.set("")
        self.template_category_var.set("All")
        self.template_priority_var.set("All")
        self._refresh_template_filters()

    def _load_templates(self):
        """Fetch and display ticket templates."""
        try:
            category = self.template_category_var.get()
            priority = self.template_priority_var.get()
            search = self.template_search_var.get().strip()

            def fetch(conn):
                cursor = conn.cursor()
                query = '''
                    SELECT template_id, name, category, priority, created_datetime,
                           usage_count, title_template, description_template, created_by
                    FROM ticket_templates
                    WHERE is_active = 1
                '''
                conditions = []
                params = []

                if category and category != "All":
                    conditions.append("category = ?")
                    params.append(category)

                if priority and priority != "All":
                    conditions.append("priority = ?")
                    params.append(priority)

                if search:
                    conditions.append("(LOWER(name) LIKE ? OR LOWER(description_template) LIKE ?)")
                    like_term = f"%{escape_like(search.lower())}%"
                    params.extend([like_term, like_term])

                if conditions:
                    query += " AND " + " AND ".join(conditions)

                query += " ORDER BY created_datetime DESC"
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

            templates = self._safe_db_call(fetch) or []
            self.template_records = {tpl['template_id']: tpl for tpl in templates}

            for item in self.templates_tree.get_children():
                self.templates_tree.delete(item)

            for tpl in templates:
                created = tpl.get('created_datetime') or ''
                self.templates_tree.insert(
                    '',
                    tk.END,
                    iid=str(tpl['template_id']),
                    values=(
                        tpl['name'],
                        tpl['category'],
                        tpl['priority'],
                        tpl.get('usage_count', 0),
                        created[:16] if created else '—'
                    )
                )

            if not templates:
                self.template_title_var.set("No templates found.")
                self.template_body_text.config(state='normal')
                self.template_body_text.delete(1.0, tk.END)
                self.template_body_text.insert(1.0, "Adjust your filters or create new templates.")
                self.template_body_text.config(state='disabled')
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load ticket templates: {exc}")

    def _on_template_select(self, event=None):
        """Display details for the selected ticket template."""
        selection = self.templates_tree.selection()
        if not selection:
            self.selected_template_id = None
            return

        template_id = int(selection[0])
        template = self.template_records.get(template_id)
        if not template:
            self.selected_template_id = None
            return

        self.selected_template_id = template_id

        self.template_title_var.set(f"{template['name']} • {template['category']} • {template['priority']}")
        body_text = template.get('description_template') or ''
        title_text = template.get('title_template') or ''

        detail = f"Title Template:\n{title_text}\n\nDescription Template:\n{body_text}"
        self.template_body_text.config(state='normal')
        self.template_body_text.delete(1.0, tk.END)
        self.template_body_text.insert(1.0, detail)
        self.template_body_text.config(state='disabled')

    def _copy_template_title(self):
        """Copy the selected template title to clipboard."""
        if not getattr(self, 'selected_template_id', None):
            messagebox.showwarning("Copy Title", "Select a template first.")
            return
        template = self.template_records.get(self.selected_template_id)
        if not template:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(template.get('title_template', ''))
            self.update_status("Template title copied to clipboard")
        except Exception as exc:
            messagebox.showerror("Error", f"Could not copy title: {exc}")

    def _copy_template_description(self):
        """Copy the selected template description to clipboard."""
        if not getattr(self, 'selected_template_id', None):
            messagebox.showwarning("Copy Description", "Select a template first.")
            return
        template = self.template_records.get(self.selected_template_id)
        if not template:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(template.get('description_template', ''))
            self.update_status("Template description copied to clipboard")
        except Exception as exc:
            messagebox.showerror("Error", f"Could not copy description: {exc}")

