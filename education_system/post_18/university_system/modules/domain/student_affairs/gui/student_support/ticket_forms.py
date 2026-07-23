import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import tkinter.font as tkFont
from datetime import datetime, timedelta
import json
import os
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from pathlib import Path
import logging
from education_system.post_18.university_system.core import paths

# Import i18n for language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import activity logger for audit trail
try:
    from education_system.post_18.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import email service for notifications
try:
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email
    from education_system.post_18.university_system.infrastructure.email.templates import load_template, render_template
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
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support import (
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
        from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support import (
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

class TicketFormsMixin:
    def show_create_ticket(self):
        """Show create ticket interface"""
        self.clear_content()

        create_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(create_frame, text="🎫 Create Ticket")

        # Check authentication
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] != 'student':
            ttk.Label(create_frame, text="❌ Only students can create tickets",
                     style='Title.TLabel').pack(pady=20)
            return

        # Create main canvas with scrollbar
        canvas = tk.Canvas(create_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(create_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack scrollbar first (on right), then canvas (fills remaining space)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Create inner frame for form content
        form_frame = ttk.Frame(canvas, padding="15")
        canvas_window = canvas.create_window((0, 0), window=form_frame, anchor="nw")

        # Configure canvas to resize inner frame width
        def configure_canvas(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", configure_canvas)

        # Update scroll region when form content changes
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        form_frame.bind("<Configure>", configure_scroll_region)

        # Bind mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        def _on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        # Bind to canvas and all children
        def bind_scroll_to_widget(widget):
            widget.bind("<MouseWheel>", _on_mousewheel)
            widget.bind("<Button-4>", _on_mousewheel_linux)
            widget.bind("<Button-5>", _on_mousewheel_linux)

        bind_scroll_to_widget(canvas)
        bind_scroll_to_widget(create_frame)

        # Recursively bind scroll to all form children
        def bind_scroll_recursive(widget):
            bind_scroll_to_widget(widget)
            for child in widget.winfo_children():
                bind_scroll_recursive(child)

        # Title
        ttk.Label(form_frame, text="🎫 Create Support Ticket",
                 style='Title.TLabel').pack(pady=(0, 20), anchor="w")

        # Template selection
        template_frame = ttk.LabelFrame(form_frame, text="📋 Templates (Optional)", padding="10")
        template_frame.pack(fill="x", pady=(0, 10))

        self.selected_template = tk.StringVar()
        self.template_combo = ttk.Combobox(template_frame, textvariable=self.selected_template,
                                          state="readonly", width=50)

        # Load templates
        try:
            templates = self.support.get_ticket_templates() if self.support else []
            template_values = ["Create from scratch"] + [f"{t['name']} ({t['category']})" for t in templates]
            self.template_combo['values'] = template_values
            self.template_combo.set("Create from scratch")
            self.template_data = {"Create from scratch": None}
            for t in templates:
                self.template_data[f"{t['name']} ({t['category']})"] = t
        except Exception:
            self.template_combo['values'] = ["Create from scratch"]
            self.template_combo.set("Create from scratch")
            self.template_data = {"Create from scratch": None}

        self.template_combo.pack(fill="x")
        self.template_combo.bind('<<ComboboxSelected>>', self.on_template_selected)

        # Title field
        title_frame = ttk.LabelFrame(form_frame, text="📝 Title *", padding="10")
        title_frame.pack(fill="x", pady=(0, 10))

        self.title_entry = ttk.Entry(title_frame, width=80, font=('Segoe UI', 10))
        self.title_entry.pack(fill="x")

        # Category field
        category_frame = ttk.LabelFrame(form_frame, text="📂 Category *", padding="10")
        category_frame.pack(fill="x", pady=(0, 10))

        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(category_frame, textvariable=self.category_var,
                                          values=SUPPORT_CATEGORIES, state="readonly")
        self.category_combo.set("Other")
        self.category_combo.pack(fill="x")

        # Priority field
        priority_frame = ttk.LabelFrame(form_frame, text="🔥 Priority", padding="10")
        priority_frame.pack(fill="x", pady=(0, 10))

        self.priority_var = tk.StringVar()
        self.priority_combo = ttk.Combobox(priority_frame, textvariable=self.priority_var,
                                          values=TICKET_PRIORITIES, state="readonly")
        self.priority_combo.set("Medium")
        self.priority_combo.pack(fill="x")

        # Description field
        desc_frame = ttk.LabelFrame(form_frame, text="📄 Description *", padding="10")
        desc_frame.pack(fill="x", pady=(0, 10))

        self.description_text = scrolledtext.ScrolledText(desc_frame, height=10, wrap=tk.WORD, font=('Segoe UI', 10))
        self.description_text.pack(fill="x")

        # Tags field
        tags_frame = ttk.LabelFrame(form_frame, text="🏷️ Tags (comma-separated)", padding="10")
        tags_frame.pack(fill="x", pady=(0, 10))

        self.tags_entry = ttk.Entry(tags_frame, width=80, font=('Segoe UI', 10))
        self.tags_entry.pack(fill="x")

        # Attachments
        attachments_frame = ttk.LabelFrame(form_frame, text="📎 Attachments", padding="10")
        attachments_frame.pack(fill="x", pady=(0, 10))

        self.attachments = []
        self.attachments_listbox = tk.Listbox(attachments_frame, height=3)
        self.attachments_listbox.pack(fill="x", pady=(0, 5))

        attach_btn_frame = ttk.Frame(attachments_frame)
        attach_btn_frame.pack(fill="x")

        ttk.Button(attach_btn_frame, text="➕ Add File",
                  command=self.add_attachment).pack(side="left", padx=(0, 5))
        ttk.Button(attach_btn_frame, text="➖ Remove",
                  command=self.remove_attachment).pack(side="left")

        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill="x", pady=(20, 10))

        ttk.Button(button_frame, text="🎫 Create Ticket",
                  command=self.create_ticket, style='Primary.TButton').pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="🔄 Reset Form",
                  command=self.reset_create_form).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="❌ Cancel",
                  command=self.show_dashboard).pack(side="left")

        # Add bottom padding to ensure buttons are fully visible
        ttk.Label(form_frame, text="").pack(pady=30)

        # Bind scroll to all widgets after they're created
        form_frame.after(100, lambda: bind_scroll_recursive(form_frame))

    def on_template_selected(self, event=None):
        """Handle template selection"""
        template_name = self.selected_template.get()
        template = self.template_data.get(template_name)

        if template:
            # Fill form with template data
            self.title_entry.delete(0, tk.END)
            self.title_entry.insert(0, template['subject_template'])

            self.category_var.set(template['category'])
            self.priority_var.set(template['priority'])

            self.description_text.delete(1.0, tk.END)
            self.description_text.insert(1.0, template['message_template'])

    def add_attachment(self):
        """Add file attachment"""
        file_path = filedialog.askopenfilename(
            title="Select File to Attach",
            filetypes=[("All Files", "*.*")]
        )

        if file_path:
            # Check file size (10MB limit)
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:
                messagebox.showerror("File Too Large", "File size must be less than 10MB")
                return

            # Read file data
            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()

                attachment = {
                    'filename': os.path.basename(file_path),
                    'data': file_data,
                    'mime_type': 'application/octet-stream'  # Default MIME type
                }

                self.attachments.append(attachment)
                self.attachments_listbox.insert(tk.END, attachment['filename'])

            except Exception as e:
                messagebox.showerror("File Error", f"Could not read file: {e}")

    def remove_attachment(self):
        """Remove selected attachment"""
        selection = self.attachments_listbox.curselection()
        if selection:
            index = selection[0]
            self.attachments.pop(index)
            self.attachments_listbox.delete(index)

    def create_ticket(self):
        """Create the support ticket"""
        # Validate form
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror("Validation Error", "Title is required")
            return

        description = self.description_text.get(1.0, tk.END).strip()
        if not description:
            messagebox.showerror("Validation Error", "Description is required")
            return

        category = self.category_var.get()
        priority = self.priority_var.get()

        # Parse tags
        tags_text = self.tags_entry.get().strip()
        tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()] if tags_text else []

        # Get student ID
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showerror("Error", "No student ID associated with your account")
                return

            student_id = result[0]

        except Exception as e:
            messagebox.showerror("Database Error", f"Could not get student ID: {e}")
            return

        # Create ticket
        try:
            self.update_status("Creating ticket...")

            # Get template ID if template was used
            template_id = None
            template_name = self.selected_template.get()
            if template_name != "Create from scratch":
                template = self.template_data.get(template_name)
                template_id = template['template_id'] if template else None

            ticket_id = self.support.create_support_ticket(
                student_id=student_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                template_id=template_id,
                attachments=self.attachments,
                tags=tags
            )

            messagebox.showinfo("Success", f"Support ticket #{ticket_id} created successfully!")
            self.update_status(f"Ticket #{ticket_id} created")

            # Send email notification to admin
            self._send_ticket_created_admin_notification(
                ticket_id=ticket_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                student_id=student_id
            )

            # Reset form and show ticket details
            self.reset_create_form()
            self.view_ticket_details(ticket_id)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create ticket: {e}")
            self.update_status("Ticket creation failed")

    def reset_create_form(self):
        """Reset the create ticket form"""
        self.title_entry.delete(0, tk.END)
        self.description_text.delete(1.0, tk.END)
        self.tags_entry.delete(0, tk.END)
        self.category_var.set("Other")
        self.priority_var.set("Medium")
        self.selected_template.set("Create from scratch")
        self.attachments.clear()
        self.attachments_listbox.delete(0, tk.END)

    def show_my_tickets(self):
        """Show student's tickets"""
        self.clear_content()

        tickets_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(tickets_frame, text="📋 My Tickets")

        # Configure frame to expand
        tickets_frame.rowconfigure(0, weight=1)
        tickets_frame.columnconfigure(0, weight=1)

        # Configure frame to expand
        tickets_frame.rowconfigure(0, weight=1)
        tickets_frame.columnconfigure(0, weight=1)

        # Check authentication
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] != 'student':
            ttk.Label(tickets_frame, text="❌ Access denied",
                     style='Title.TLabel').pack(pady=20)
            return

        # Title and filters
        header_frame = ttk.Frame(tickets_frame)
        header_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(header_frame, text="📋 My Support Tickets",
                 style='Title.TLabel').pack(side="left")

        ttk.Button(header_frame, text="🔄 Refresh",
                  command=self.refresh_my_tickets).pack(side="right")

        # Filters
        filter_frame = ttk.LabelFrame(tickets_frame, text="🔍 Filters", padding="10")
        filter_frame.pack(fill="x", pady=(0, 10))

        filter_grid = ttk.Frame(filter_frame)
        filter_grid.pack(fill="x")

        # Status filter
        ttk.Label(filter_grid, text="Status:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.my_tickets_status_filter = ttk.Combobox(filter_grid, values=[
            "All", "Open", "In Progress", "Resolved", "Closed"
        ], state="readonly", width=15)
        self.my_tickets_status_filter.set("All")
        self.my_tickets_status_filter.grid(row=0, column=1, padx=(0, 10))

        # Search filter
        ttk.Label(filter_grid, text="Search:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.my_tickets_search = ttk.Entry(filter_grid, width=30)
        self.my_tickets_search.grid(row=0, column=3, padx=(0, 10))
        self.my_tickets_search.bind('<Return>', lambda e: self.refresh_my_tickets())

        ttk.Button(filter_grid, text="Apply",
                  command=self.refresh_my_tickets).grid(row=0, column=4)

        # Tickets list
        self.my_tickets_frame = ttk.Frame(tickets_frame)
        self.my_tickets_frame.pack(fill="both", expand=True)

        # Load tickets
        self.refresh_my_tickets()

    def refresh_my_tickets(self):
        """Refresh my tickets list"""
        # Clear existing content
        for widget in self.my_tickets_frame.winfo_children():
            widget.destroy()

        # Get student ID
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            conn.close()

            if not result:
                ttk.Label(self.my_tickets_frame, text="❌ No student ID found").pack(pady=20)
                return

            student_id = result[0]

        except Exception as e:
            ttk.Label(self.my_tickets_frame, text=f"❌ Database error: {e}").pack(pady=20)
            return

        # Build filters
        filters = {}
        status_filter = self.my_tickets_status_filter.get()
        if status_filter != "All":
            filters['status'] = status_filter

        search_text = self.my_tickets_search.get().strip()
        if search_text:
            filters['search'] = search_text

        # Get tickets
        try:
            result = self.support.get_student_tickets(student_id, filters, page=1, per_page=50)

            # Handle None or invalid result
            if result is None:
                ttk.Label(self.my_tickets_frame, text="📭 No tickets found").pack(pady=20)
                return

            tickets = result.get('tickets', []) if isinstance(result, dict) else []

            if not tickets:
                ttk.Label(self.my_tickets_frame, text="📭 No tickets found").pack(pady=20)
                return

            # Create tickets table
            columns = ('ID', 'Title', 'Status', 'Priority', 'Category', 'Created', 'Updated')
            tree = ttk.Treeview(self.my_tickets_frame, columns=columns, show='headings', height=20)

            # Configure columns
            for col in columns:
                tree.heading(col, text=col)

            tree.column('ID', width=80)
            tree.column('Title', width=300)
            tree.column('Status', width=100)
            tree.column('Priority', width=100)
            tree.column('Category', width=120)
            tree.column('Created', width=150)
            tree.column('Updated', width=150)

            # Add tickets
            for ticket in tickets:
                # Skip None or invalid ticket entries
                if ticket is None or not isinstance(ticket, dict):
                    continue

                ticket_id = ticket.get('ticket_id', 'N/A')
                ticket_title = ticket.get('subject', 'Untitled')
                ticket_title_display = ticket_title[:50] + ('...' if len(ticket_title) > 50 else '')
                ticket_status = ticket.get('status', 'Unknown')
                ticket_priority = ticket.get('priority', 'Normal')
                ticket_category = ticket.get('category', 'General')
                ticket_created = ticket.get('created_at', 'N/A')
                ticket_updated = ticket.get('updated_at', 'N/A')

                tree.insert('', 'end', values=(
                    ticket_id,
                    ticket_title_display,
                    ticket_status,
                    ticket_priority,
                    ticket_category,
                    ticket_created,
                    ticket_updated
                ))

            # Scrollbar
            scrollbar = ttk.Scrollbar(self.my_tickets_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Double-click to view
            tree.bind('<Double-1>', lambda e: self.on_ticket_double_click(tree))

            # Context menu
            tree.bind('<Button-3>', lambda e: self.show_ticket_context_menu(e, tree))

            self.update_status(f"Loaded {len(tickets)} tickets")

        except Exception as e:
            ttk.Label(self.my_tickets_frame, text=f"❌ Error loading tickets: {e}").pack(pady=20)

    def show_all_tickets(self):
        """Show all tickets (staff only)"""
        self.clear_content()

        tickets_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(tickets_frame, text="🎫 All Tickets")

        # Configure frame to expand
        tickets_frame.rowconfigure(0, weight=1)
        tickets_frame.columnconfigure(0, weight=1)

        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] not in ('staff', 'admin'):
            ttk.Label(tickets_frame, text="❌ Staff access required",
                     style='Title.TLabel').pack(pady=20)
            return

        # Title and controls
        header_frame = ttk.Frame(tickets_frame)
        header_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(header_frame, text="🎫 All Support Tickets",
                 style='Title.TLabel').pack(side="left")

        control_frame = ttk.Frame(header_frame)
        control_frame.pack(side="right")

        ttk.Button(control_frame, text="🔄 Refresh",
                  command=self.refresh_all_tickets).pack(side="left", padx=(0, 5))
        ttk.Button(control_frame, text="📊 Reports",
                  command=self.show_reports).pack(side="left", padx=(0, 5))
        ttk.Button(control_frame, text="📦 Bulk Ops",
                  command=self.show_bulk_operations).pack(side="left")

        # Advanced filters
        filter_frame = ttk.LabelFrame(tickets_frame, text="🔍 Advanced Filters", padding="10")
        filter_frame.pack(fill="x", pady=(0, 10))

        filter_grid = ttk.Frame(filter_frame)
        filter_grid.pack(fill="x")

        # Row 1
        ttk.Label(filter_grid, text="Status:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.all_tickets_status = ttk.Combobox(filter_grid, values=[
            "All"] + TICKET_STATUSES, state="readonly", width=12)
        self.all_tickets_status.set("All")
        self.all_tickets_status.grid(row=0, column=1, padx=(0, 10))

        ttk.Label(filter_grid, text="Priority:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.all_tickets_priority = ttk.Combobox(filter_grid, values=[
            "All"] + TICKET_PRIORITIES, state="readonly", width=12)
        self.all_tickets_priority.set("All")
        self.all_tickets_priority.grid(row=0, column=3, padx=(0, 10))

        ttk.Label(filter_grid, text="Category:").grid(row=0, column=4, sticky="w", padx=(0, 5))
        self.all_tickets_category = ttk.Combobox(filter_grid, values=[
            "All"] + SUPPORT_CATEGORIES, state="readonly", width=15)
        self.all_tickets_category.set("All")
        self.all_tickets_category.grid(row=0, column=5, padx=(0, 10))

        # Row 2
        ttk.Label(filter_grid, text="Assigned to:").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(5, 0))
        self.all_tickets_assigned = ttk.Entry(filter_grid, width=15)
        self.all_tickets_assigned.grid(row=1, column=1, padx=(0, 10), pady=(5, 0))

        ttk.Label(filter_grid, text="Search:").grid(row=1, column=2, sticky="w", padx=(0, 5), pady=(5, 0))
        self.all_tickets_search = ttk.Entry(filter_grid, width=20)
        self.all_tickets_search.grid(row=1, column=3, columnspan=2, sticky="ew", padx=(0, 10), pady=(5, 0))
        self.all_tickets_search.bind('<Return>', lambda e: self.refresh_all_tickets())

        ttk.Button(filter_grid, text="Apply Filters",
                  command=self.refresh_all_tickets).grid(row=1, column=5, pady=(5, 0))

        filter_grid.columnconfigure(4, weight=1)

        # Quick filter buttons
        quick_frame = ttk.Frame(filter_frame)
        quick_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(quick_frame, text="🔥 High Priority",
                  command=lambda: self.apply_quick_filter('priority', 'High')).pack(side="left", padx=(0, 5))
        ttk.Button(quick_frame, text="❌ Unassigned",
                  command=lambda: self.apply_quick_filter('assigned', 'none')).pack(side="left", padx=(0, 5))
        ttk.Button(quick_frame, text="🚨 Escalated",
                  command=lambda: self.apply_quick_filter('status', 'Escalated')).pack(side="left", padx=(0, 5))
        ttk.Button(quick_frame, text="🔄 Clear Filters",
                  command=self.clear_all_filters).pack(side="left", padx=(0, 5))

        # Tickets list
        self.all_tickets_frame = ttk.Frame(tickets_frame)
        self.all_tickets_frame.pack(fill="both", expand=True)

        # Load tickets
        self.refresh_all_tickets()

    def apply_quick_filter(self, filter_type, value):
        """Apply quick filter"""
        if filter_type == 'priority':
            self.all_tickets_priority.set(value)
        elif filter_type == 'status':
            self.all_tickets_status.set(value)
        elif filter_type == 'assigned':
            if value == 'none':
                self.all_tickets_assigned.delete(0, tk.END)
                self.all_tickets_assigned.insert(0, 'UNASSIGNED')

        self.refresh_all_tickets()

    def clear_all_filters(self):
        """Clear all filters"""
        self.all_tickets_status.set("All")
        self.all_tickets_priority.set("All")
        self.all_tickets_category.set("All")
        self.all_tickets_assigned.delete(0, tk.END)
        self.all_tickets_search.delete(0, tk.END)
        self.refresh_all_tickets()

    def refresh_all_tickets(self):
        """Refresh all tickets list"""
        # Clear existing content
        for widget in self.all_tickets_frame.winfo_children():
            widget.destroy()

        # Build filters
        filters = {}

        status = self.all_tickets_status.get()
        if status != "All":
            filters['status'] = status

        priority = self.all_tickets_priority.get()
        if priority != "All":
            filters['priority'] = priority

        category = self.all_tickets_category.get()
        if category != "All":
            filters['category'] = category

        assigned = self.all_tickets_assigned.get().strip()
        if assigned:
            if assigned.upper() == 'UNASSIGNED':
                filters['assigned_to'] = None
            else:
                filters['assigned_to'] = assigned

        search = self.all_tickets_search.get().strip()
        if search:
            filters['search'] = search

        # Get tickets
        try:
            result = self.support.get_student_tickets(None, filters, page=1, per_page=100)

            # Handle None or invalid result
            if result is None:
                ttk.Label(self.all_tickets_frame, text="📭 No tickets found with current filters").pack(pady=20)
                return

            tickets = result.get('tickets', []) if isinstance(result, dict) else []

            if not tickets:
                ttk.Label(self.all_tickets_frame, text="📭 No tickets found with current filters").pack(pady=20)
                return

            # Create tickets table with enhanced columns
            columns = ('ID', 'Title', 'Student', 'Status', 'Priority', 'Category', 'Assigned', 'Created', 'Updated')
            tree = ttk.Treeview(self.all_tickets_frame, columns=columns, show='headings', height=25)

            # Configure columns
            for col in columns:
                tree.heading(col, text=col)

            tree.column('ID', width=60)
            tree.column('Title', width=250)
            tree.column('Student', width=100)
            tree.column('Status', width=100)
            tree.column('Priority', width=80)
            tree.column('Category', width=120)
            tree.column('Assigned', width=100)
            tree.column('Created', width=120)
            tree.column('Updated', width=120)

            # Add tickets with color coding
            for ticket in tickets:
                # Skip None or invalid ticket entries
                if ticket is None or not isinstance(ticket, dict):
                    continue

                # Safe access to ticket fields
                ticket_id = ticket.get('ticket_id', 'N/A')
                ticket_title = ticket.get('subject', 'Untitled')
                ticket_title_display = ticket_title[:40] + ('...' if len(ticket_title) > 40 else '')
                ticket_student_id = ticket.get('user_id', 'Unknown')
                ticket_status = ticket.get('status', 'Unknown')
                ticket_priority = ticket.get('priority', 'Normal')
                ticket_category = ticket.get('category', 'General')
                ticket_assigned = ticket.get('assigned_to', 'Unassigned')
                ticket_created = ticket.get('created_at', 'N/A')
                ticket_created_display = ticket_created[:16] if ticket_created and ticket_created != 'N/A' else 'N/A'
                ticket_updated = ticket.get('updated_at', 'N/A')
                ticket_updated_display = ticket_updated[:16] if ticket_updated and ticket_updated != 'N/A' else 'N/A'

                # Color coding based on priority
                tags = []
                if ticket_priority == 'Critical':
                    tags.append('critical')
                elif ticket_priority == 'Urgent':
                    tags.append('urgent')
                elif ticket_priority == 'High':
                    tags.append('high')

                # Add sentiment tag
                if ticket.get('sentiment') == 'frustrated':
                    tags.append('frustrated')

                tree.insert('', 'end', values=(
                    ticket_id,
                    ticket_title_display,
                    ticket_student_id,
                    ticket_status,
                    ticket_priority,
                    ticket_category,
                    ticket_assigned,
                    ticket_created_display,
                    ticket_updated_display
                ), tags=tags)

            # Configure tag colors
            tree.tag_configure('critical', background='#fee2e2', foreground='#dc2626')
            tree.tag_configure('urgent', background='#fed7aa', foreground='#ea580c')
            tree.tag_configure('high', background='#fef3c7', foreground='#d97706')
            tree.tag_configure('frustrated', background='#fce7f3', foreground='#be185d')

            # Scrollbars
            v_scrollbar = ttk.Scrollbar(self.all_tickets_frame, orient='vertical', command=tree.yview)
            h_scrollbar = ttk.Scrollbar(self.all_tickets_frame, orient='horizontal', command=tree.xview)
            tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

            tree.grid(row=0, column=0, sticky='nsew')
            v_scrollbar.grid(row=0, column=1, sticky='ns')
            h_scrollbar.grid(row=1, column=0, sticky='ew')

            self.all_tickets_frame.columnconfigure(0, weight=1)
            self.all_tickets_frame.rowconfigure(0, weight=1)

            # Bind events
            tree.bind('<Double-1>', lambda e: self.on_ticket_double_click(tree))
            tree.bind('<Button-3>', lambda e: self.show_staff_ticket_context_menu(e, tree))

            self.update_status(f"Loaded {len(tickets)} tickets")

        except Exception as e:
            ttk.Label(self.all_tickets_frame, text=f"❌ Error loading tickets: {e}").pack(pady=20)

    def on_ticket_double_click(self, tree):
        """Handle double-click on ticket in tree view"""
        selection = tree.selection()
        if selection:
            item = tree.item(selection[0])
            ticket_id = item['values'][0]  # First column is ticket ID
            self.view_ticket_details(ticket_id)

    def show_ticket_context_menu(self, event, tree):
        """Show context menu for ticket"""
        # Create context menu
        context_menu = tk.Menu(self.root, tearoff=0)

        # Get selected item
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
            ticket_data = tree.item(item)
            ticket_id = ticket_data['values'][0]

            context_menu.add_command(label="👁️ View Details",
                                   command=lambda: self.view_ticket_details(ticket_id))
            context_menu.add_command(label="💬 Add Response",
                                   command=lambda: self.show_add_response_dialog_by_id(ticket_id))

            if self.auth.current_user['role'] in ('staff', 'admin'):
                context_menu.add_separator()
                context_menu.add_command(label="📊 Update Status",
                                       command=lambda: self.show_status_update_dialog(ticket_id))
                context_menu.add_command(label="👨‍💼 Assign to Me",
                                       command=lambda: self.assign_ticket_to_me(ticket_id))

            # Show menu
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()

