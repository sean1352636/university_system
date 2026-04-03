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

class TicketDetailMixin:
    def view_ticket_details(self, ticket_id):
        """View detailed ticket information"""
        try:
            ticket = self.support.get_ticket_details(ticket_id)
            self.show_ticket_detail_window(ticket)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load ticket details: {e}")

    def show_ticket_detail_window(self, ticket):
        """Show ticket details in a new window"""
        # Handle None or invalid ticket
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror("Error", "Invalid ticket data")
            return

        ticket_id = ticket.get('ticket_id', 'N/A')
        ticket_title = ticket.get('title', 'Untitled')

        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"🎫 Ticket #{ticket_id} - {ticket_title}")
        detail_window.geometry("1600x950")
        detail_window.transient(self.root)

        # Create notebook for different sections
        detail_notebook = ttk.Notebook(detail_window, padding="10")
        detail_notebook.pack(fill="both", expand=True)

        # Overview tab
        overview_frame = ttk.Frame(detail_notebook, padding="10")
        detail_notebook.add(overview_frame, text="📋 Overview")

        self.create_ticket_overview(overview_frame, ticket)

        # Responses tab
        responses_frame = ttk.Frame(detail_notebook, padding="10")
        detail_notebook.add(responses_frame, text=f"💬 Responses ({len(ticket.get('responses', []))})")

        self.create_ticket_responses(responses_frame, ticket)

        # Attachments tab
        attachments = ticket.get('attachments', [])
        if attachments:
            attachments_frame = ttk.Frame(detail_notebook, padding="10")
            detail_notebook.add(attachments_frame, text=f"📎 Attachments ({len(attachments)})")

            self.create_ticket_attachments(attachments_frame, attachments)

        # Actions tab (for staff)
        if self.auth.current_user['role'] in ('staff', 'admin'):
            actions_frame = ttk.Frame(detail_notebook, padding="10")
            detail_notebook.add(actions_frame, text="🔧 Actions")

            self.create_ticket_actions(actions_frame, ticket, detail_window)

    def create_ticket_overview(self, parent, ticket):
        """Create ticket overview section"""
        # Safe access to ticket fields
        ticket_id = ticket.get('ticket_id', 'N/A') if ticket else 'N/A'
        ticket_title = ticket.get('title', 'Untitled') if ticket else 'Untitled'
        ticket_student_id = ticket.get('student_id', 'Unknown') if ticket else 'Unknown'
        ticket_status = ticket.get('status', 'Unknown') if ticket else 'Unknown'
        ticket_priority = ticket.get('priority', 'Normal') if ticket else 'Normal'
        ticket_category = ticket.get('category', 'General') if ticket else 'General'
        ticket_created = ticket.get('created_datetime', 'N/A') if ticket else 'N/A'

        # Header info
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill="x", pady=(0, 20))

        title_label = ttk.Label(header_frame, text=f"🎫 #{ticket_id}: {ticket_title}",
                               style='Title.TLabel')
        title_label.pack(anchor="w")

        # Details grid
        details_frame = ttk.LabelFrame(parent, text="📊 Ticket Details", padding="15")
        details_frame.pack(fill="x", pady=(0, 10))

        details_grid = ttk.Frame(details_frame)
        details_grid.pack(fill="x")

        # Left column
        left_frame = ttk.Frame(details_grid)
        left_frame.pack(side="left", fill="both", expand=True)

        details = [
            ("👤 Student ID:", ticket_student_id),
            ("📊 Status:", ticket_status),
            ("🔥 Priority:", ticket_priority),
            ("📂 Category:", ticket_category),
            ("📅 Created:", ticket_created),
        ]

        for i, (label, value) in enumerate(details):
            ttk.Label(left_frame, text=label, font=('Segoe UI', 9, 'bold')).grid(
                row=i, column=0, sticky="w", pady=2, padx=(0, 10))
            ttk.Label(left_frame, text=str(value)).grid(
                row=i, column=1, sticky="w", pady=2)

        # Right column
        right_frame = ttk.Frame(details_grid)
        right_frame.pack(side="right", fill="both", expand=True)

        right_details = [
            ("👨‍💼 Assigned to:", ticket.get('assigned_to', 'Unassigned')),
            ("⏰ Last Updated:", ticket.get('last_updated_datetime', 'N/A')),
            ("🎯 Resolution ETA:", ticket.get('estimated_resolution', 'N/A')),
            ("😊 Sentiment:", ticket.get('sentiment', 'neutral').title()),
            ("⭐ Satisfaction:", f"{ticket.get('satisfaction_rating', 'N/A')}/5" if ticket.get('satisfaction_rating') else 'N/A'),
        ]

        for i, (label, value) in enumerate(right_details):
            ttk.Label(right_frame, text=label, font=('Segoe UI', 9, 'bold')).grid(
                row=i, column=0, sticky="w", pady=2, padx=(0, 10))
            ttk.Label(right_frame, text=str(value)).grid(
                row=i, column=1, sticky="w", pady=2)

        # Tags
        if ticket.get('tags'):
            ticket_tags = ticket.get('tags', [])
            tags = json.loads(ticket_tags) if isinstance(ticket_tags, str) else ticket_tags
            if tags:
                tags_frame = ttk.Frame(details_frame)
                tags_frame.pack(fill="x", pady=(10, 0))

                ttk.Label(tags_frame, text="🏷️ Tags:", font=('Segoe UI', 9, 'bold')).pack(side="left")
                for tag in tags:
                    tag_label = tk.Label(tags_frame, text=tag, bg="#e5e7eb", fg="#374151",
                                       padx=8, pady=2, relief="solid", borderwidth=1)
                    tag_label.pack(side="left", padx=(5, 0))

        # Description
        desc_frame = ttk.LabelFrame(parent, text="📄 Description", padding="15")
        desc_frame.pack(fill="both", expand=True)

        desc_text = scrolledtext.ScrolledText(desc_frame, height=10, wrap=tk.WORD, state='disabled')
        desc_text.pack(fill="both", expand=True)

        desc_text.config(state='normal')
        desc_text.insert(1.0, ticket.get('description', 'No description available') if ticket else 'No description available')
        desc_text.config(state='disabled')

    def create_ticket_responses(self, parent, ticket):
        """Create ticket responses section"""
        responses = ticket.get('responses', [])

        if not responses:
            ttk.Label(parent, text="💬 No responses yet", style='Heading.TLabel').pack(pady=20)
            return

        # Create scrollable responses
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Add responses
        for i, response in enumerate(responses):
            # Skip None or invalid response entries
            if response is None or not isinstance(response, dict):
                continue

            responder_role = response.get('responder_role', 'unknown')
            response_datetime = response.get('response_datetime', 'N/A')
            response_content = response.get('response_text', '')

            response_frame = ttk.LabelFrame(scrollable_frame, padding="10")
            response_frame.pack(fill="x", padx=5, pady=5)

            # Response header
            header_frame = ttk.Frame(response_frame)
            header_frame.pack(fill="x", pady=(0, 10))

            # Role badge
            role_color = {"staff": "#3b82f6", "admin": "#dc2626", "student": "#16a34a", "system": "#6b7280"}
            role_bg = role_color.get(responder_role, "#6b7280")

            role_label = tk.Label(header_frame, text=responder_role.upper(),
                                bg=role_bg, fg="white", padx=8, pady=2,
                                font=('Segoe UI', 8, 'bold'))
            role_label.pack(side="left")

            # Auto-generated and internal indicators
            if response.get('is_auto_generated'):
                auto_label = tk.Label(header_frame, text="🤖 AUTO", bg="#f59e0b", fg="white",
                                    padx=6, pady=2, font=('Segoe UI', 8, 'bold'))
                auto_label.pack(side="left", padx=(5, 0))

            if response.get('is_internal'):
                internal_label = tk.Label(header_frame, text="🔒 INTERNAL", bg="#ef4444", fg="white",
                                        padx=6, pady=2, font=('Segoe UI', 8, 'bold'))
                internal_label.pack(side="left", padx=(5, 0))

            # Timestamp
            ttk.Label(header_frame, text=response_datetime,
                     font=('Segoe UI', 9), foreground=self.colors['text_secondary']).pack(side="right")

            # Response text
            response_text_widget = scrolledtext.ScrolledText(response_frame, height=6, wrap=tk.WORD, state='disabled')
            response_text_widget.pack(fill="x", pady=(5, 0))

            response_text_widget.config(state='normal')
            response_text_widget.insert(1.0, response_content)
            response_text_widget.config(state='disabled')

        # Configure grid weights for proper resizing
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Add response button (if permitted) - use grid to match canvas/scrollbar
        if self.can_respond_to_ticket(ticket):
            add_response_btn = ttk.Button(parent, text="💬 Add Response",
                                        command=lambda: self.show_add_response_dialog(ticket))
            add_response_btn.grid(row=1, column=0, columnspan=2, pady=(10, 0))

    def create_ticket_attachments(self, parent, attachments):
        """Create ticket attachments section"""
        # Attachments list
        for attachment in attachments:
            # Skip None or invalid attachment entries
            if attachment is None or not isinstance(attachment, dict):
                continue

            att_frame = ttk.Frame(parent)
            att_frame.pack(fill="x", pady=5)

            # File icon based on type
            file_icons = {
                'image': '🖼️',
                'document': '📄',
                'video': '🎥',
                'other': '📎'
            }
            icon = file_icons.get(attachment.get('file_type', 'other'), '📎')

            # Safe access to attachment fields
            file_size = attachment.get('file_size', 0) or 0
            original_filename = attachment.get('original_filename', 'Unknown File')
            uploaded_by = attachment.get('uploaded_by', 'Unknown')
            uploaded_datetime = attachment.get('uploaded_datetime', 'N/A')

            # File info
            size_mb = file_size / (1024 * 1024)
            file_info = f"{icon} {original_filename} ({size_mb:.1f}MB)"

            ttk.Label(att_frame, text=file_info).pack(side="left")

            # Upload info
            upload_info = f"Uploaded by {uploaded_by} on {uploaded_datetime}"
            ttk.Label(att_frame, text=upload_info, font=('Segoe UI', 9),
                     foreground=self.colors['text_secondary']).pack(side="left", padx=(10, 0))

            # Download button
            ttk.Button(att_frame, text="📥 Download",
                      command=lambda a=attachment: self.download_attachment(a)).pack(side="right")

    def create_ticket_actions(self, parent, ticket, window):
        """Create ticket actions section for staff"""
        # Safe access to ticket fields
        ticket_status = ticket.get('status', 'Open') if ticket else 'Open'
        ticket_id = ticket.get('ticket_id', 'N/A') if ticket else 'N/A'

        # Status update
        status_frame = ttk.LabelFrame(parent, text="📊 Update Status", padding="10")
        status_frame.pack(fill="x", pady=(0, 10))

        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill="x")

        ttk.Label(status_grid, text="New Status:").grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.new_status_var = tk.StringVar(value=ticket_status)
        status_combo = ttk.Combobox(status_grid, textvariable=self.new_status_var,
                                   values=TICKET_STATUSES, state="readonly")
        status_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        ttk.Button(status_grid, text="Update Status",
                  command=lambda: self.update_ticket_status_action(ticket_id, window)).grid(row=0, column=2)

        status_grid.columnconfigure(1, weight=1)

        # Assignment
        assign_frame = ttk.LabelFrame(parent, text="👨‍💼 Assignment", padding="10")
        assign_frame.pack(fill="x", pady=(0, 10))

        assign_grid = ttk.Frame(assign_frame)
        assign_grid.pack(fill="x")

        ttk.Label(assign_grid, text="Assign to:").grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.assign_to_var = tk.StringVar(value=ticket.get('assigned_to', ''))
        assign_entry = ttk.Entry(assign_grid, textvariable=self.assign_to_var)
        assign_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        ttk.Button(assign_grid, text="Assign to Me",
                  command=lambda: self.assign_to_var.set(self.auth.current_user['username'])).grid(row=0, column=2, padx=(0, 10))

        ttk.Button(assign_grid, text="Update Assignment",
                  command=lambda: self.update_ticket_assignment(ticket_id, window)).grid(row=0, column=3)

        assign_grid.columnconfigure(1, weight=1)

        # Quick actions
        actions_frame = ttk.LabelFrame(parent, text="⚡ Quick Actions", padding="10")
        actions_frame.pack(fill="x", pady=(0, 10))

        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack(fill="x")

        ttk.Button(actions_grid, text="📝 Add Internal Note",
                  command=lambda: self.show_add_internal_note_dialog(ticket)).grid(row=0, column=0, padx=(0, 5), pady=2)

        ttk.Button(actions_grid, text="📋 Use Template",
                  command=lambda: self.show_response_template_dialog(ticket)).grid(row=0, column=1, padx=5, pady=2)

        ttk.Button(actions_grid, text="📊 View History",
                  command=lambda: self.show_ticket_history(ticket_id)).grid(row=0, column=2, padx=5, pady=2)

        ttk.Button(actions_grid, text="🔗 Merge Ticket",
                  command=lambda: self.show_merge_dialog(ticket)).grid(row=1, column=0, padx=(0, 5), pady=2)

        ttk.Button(actions_grid, text="⚡ Escalate",
                  command=lambda: self.escalate_ticket(ticket_id)).grid(row=1, column=1, padx=5, pady=2)

        ttk.Button(actions_grid, text="📤 Export",
                  command=lambda: self.export_ticket(ticket)).grid(row=1, column=2, padx=5, pady=2)

        # Edit and Delete buttons
        ttk.Button(actions_grid, text="✏️ Edit Ticket",
                  command=lambda: self.edit_ticket(ticket, window)).grid(row=2, column=0, padx=(0, 5), pady=2)

        ttk.Button(actions_grid, text="🗑️ Delete Ticket",
                  command=lambda: self.delete_ticket(ticket_id, window)).grid(row=2, column=1, padx=5, pady=2)

    def edit_ticket(self, ticket, parent_window=None):
        """Edit an existing support ticket"""
        # Handle None or invalid ticket
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror("Error", "Invalid ticket data")
            return

        ticket_id = ticket.get('ticket_id', 'N/A')

        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"✏️ Edit Ticket #{ticket_id}")
        edit_window.geometry("900x700")
        edit_window.transient(self.root)
        edit_window.grab_set()

        main_frame = ttk.Frame(edit_window, padding="20")
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text=f"Edit Ticket #{ticket_id}",
                 style='Title.TLabel').pack(pady=(0, 20))

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill="both", expand=True)

        # Title
        ttk.Label(form_frame, text="Title:", font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        edit_title_var = tk.StringVar(value=ticket.get('title', ''))
        title_entry = ttk.Entry(form_frame, textvariable=edit_title_var, width=80, font=('Segoe UI', 10))
        title_entry.pack(fill="x", pady=(0, 10))

        # Category
        ttk.Label(form_frame, text="Category:", font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        edit_category_var = tk.StringVar(value=ticket.get('category', 'Other'))
        category_combo = ttk.Combobox(form_frame, textvariable=edit_category_var,
                                      values=SUPPORT_CATEGORIES if SUPPORT_CATEGORIES else ['Academic', 'Technical', 'Financial', 'Housing', 'Other'],
                                      state="readonly", width=40)
        category_combo.pack(anchor="w", pady=(0, 10))

        # Priority
        ttk.Label(form_frame, text="Priority:", font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        edit_priority_var = tk.StringVar(value=ticket.get('priority', 'Medium'))
        priority_combo = ttk.Combobox(form_frame, textvariable=edit_priority_var,
                                      values=TICKET_PRIORITIES if TICKET_PRIORITIES else ['Low', 'Medium', 'High', 'Urgent'],
                                      state="readonly", width=40)
        priority_combo.pack(anchor="w", pady=(0, 10))

        # Status (staff only)
        if self.auth and self.auth.current_user and self.auth.current_user.get('role') in ('staff', 'admin'):
            ttk.Label(form_frame, text="Status:", font=('Segoe UI', 10, 'bold')).pack(anchor="w")
            edit_status_var = tk.StringVar(value=ticket.get('status', 'Open'))
            status_combo = ttk.Combobox(form_frame, textvariable=edit_status_var,
                                        values=TICKET_STATUSES if TICKET_STATUSES else ['Open', 'In Progress', 'Resolved', 'Closed'],
                                        state="readonly", width=40)
            status_combo.pack(anchor="w", pady=(0, 10))
        else:
            edit_status_var = tk.StringVar(value=ticket.get('status', 'Open'))

        # Description
        ttk.Label(form_frame, text="Description:", font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        description_text = scrolledtext.ScrolledText(form_frame, height=12, wrap=tk.WORD, font=('Segoe UI', 10))
        description_text.pack(fill="both", expand=True, pady=(0, 10))
        description_text.insert(1.0, ticket.get('description', ''))

        # Tags
        ttk.Label(form_frame, text="Tags (comma-separated):", font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        tags_str = ''
        if ticket.get('tags'):
            try:
                ticket_tags = ticket.get('tags', [])
                tags_list = json.loads(ticket_tags) if isinstance(ticket_tags, str) else ticket_tags
                tags_str = ', '.join(tags_list) if isinstance(tags_list, list) else str(tags_list)
            except (ValueError, json.JSONDecodeError):
                tags_str = str(ticket.get('tags', ''))
        edit_tags_var = tk.StringVar(value=tags_str)
        tags_entry = ttk.Entry(form_frame, textvariable=edit_tags_var, width=80, font=('Segoe UI', 10))
        tags_entry.pack(fill="x", pady=(0, 15))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")

        def save_ticket_changes():
            try:
                new_title = edit_title_var.get().strip()
                new_description = description_text.get(1.0, tk.END).strip()

                if not new_title:
                    messagebox.showerror("Validation Error", "Title is required")
                    return
                if not new_description:
                    messagebox.showerror("Validation Error", "Description is required")
                    return

                # Parse tags
                tags_text = edit_tags_var.get().strip()
                tags = json.dumps([tag.strip() for tag in tags_text.split(',') if tag.strip()]) if tags_text else '[]'

                # Update ticket in database
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()

                    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute('''
                        UPDATE support_tickets
                        SET title = ?, description = ?, category = ?, priority = ?,
                            status = ?, tags = ?, last_updated_datetime = ?, updated_at = ?
                        WHERE ticket_id = ?
                    ''', (new_title, new_description, edit_category_var.get(),
                          edit_priority_var.get(), edit_status_var.get(), tags,
                          update_time, update_time, ticket_id))

                    conn.commit()
                finally:
                    conn.close()

                # Log activity
                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('update', 'support_ticket', ticket_id=ticket_id,
                               details={'title': new_title, 'category': edit_category_var.get()})

                # Send email notification to user about ticket update
                old_status = ticket.get('status', 'Open')
                new_status = edit_status_var.get()

                # Build update details message
                update_details = "The following changes were made to your ticket:\n"
                if new_title != ticket.get('title', ''):
                    update_details += f"- Title updated\n"
                if edit_category_var.get() != ticket.get('category', ''):
                    update_details += f"- Category changed to: {edit_category_var.get()}\n"
                if edit_priority_var.get() != ticket.get('priority', ''):
                    update_details += f"- Priority changed to: {edit_priority_var.get()}\n"
                if old_status != new_status:
                    update_details += f"- Status changed from {old_status} to {new_status}\n"
                    # Send specific status change notification
                    self._send_ticket_status_change_notification(
                        ticket_id, old_status, new_status,
                        self.auth.current_user.get('username', 'Support Staff') if self.auth and self.auth.current_user else 'Support Staff'
                    )
                else:
                    # Send general update notification
                    self._send_ticket_update_notification(
                        ticket_id,
                        'Ticket Updated',
                        update_details
                    )

                messagebox.showinfo("Success", f"Ticket #{ticket_id} updated successfully!")
                edit_window.destroy()

                # Refresh parent window if exists
                if parent_window:
                    parent_window.destroy()
                    self.view_ticket_details(ticket_id)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update ticket: {e}")

        ttk.Button(btn_frame, text="💾 Save Changes", command=save_ticket_changes,
                  style='Primary.TButton').pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=edit_window.destroy).pack(side="left")

    def delete_ticket(self, ticket_id, parent_window=None):
        """Delete a support ticket"""
        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete ticket #{ticket_id}?\n\n"
            "This action cannot be undone. All associated responses and attachments will also be deleted.",
            icon='warning'
        )

        if not confirm:
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Delete associated responses first
            cursor.execute('DELETE FROM ticket_responses WHERE ticket_id = ?', (ticket_id,))

            # Delete associated attachments
            cursor.execute('DELETE FROM ticket_attachments WHERE ticket_id = ?', (ticket_id,))

            # Delete the ticket
            cursor.execute('DELETE FROM support_tickets WHERE ticket_id = ?', (ticket_id,))

            conn.commit()
            conn.close()

            # Log activity
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('delete', 'support_ticket', ticket_id=ticket_id)

            messagebox.showinfo("Success", f"Ticket #{ticket_id} has been deleted.")

            # Close parent window and refresh list
            if parent_window:
                parent_window.destroy()

            # Refresh the tickets view
            if hasattr(self, 'my_tickets_frame'):
                self.refresh_my_tickets()
            elif hasattr(self, 'all_tickets_frame'):
                self.refresh_all_tickets()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete ticket: {e}")

    def _send_ticket_created_admin_notification(self, ticket_id, title, description, category, priority, student_id):
        """Send email notification to admin when a new ticket is created"""
        if not EMAIL_SERVICE_AVAILABLE:
            return

        def send_notification():
            import time
            time.sleep(1)  # Wait for database transaction to complete

            try:
                # Get student information with timeout
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=10)
                cursor = conn.cursor()

                # Get student details
                cursor.execute('''
                    SELECT u.email, u.first_name, u.last_name, u.username
                    FROM users u
                    WHERE u.student_id = ? OR u.id = (SELECT id FROM users WHERE student_id = ?)
                ''', (student_id, student_id))
                student_result = cursor.fetchone()

                student_email = student_result[0] if student_result else 'unknown@university.edu'
                student_name = f"{student_result[1] or ''} {student_result[2] or ''}".strip() if student_result else student_result[3] if student_result else 'Unknown Student'
                if not student_name:
                    student_name = student_result[3] if student_result else 'Unknown Student'

                # Get all admin email addresses
                cursor.execute("SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL AND email != ''")
                admin_emails = [row[0] for row in cursor.fetchall()]

                conn.close()

                if not admin_emails:
                    # Fallback to default admin email
                    admin_emails = ['admin@university.edu']

                # Prepare template variables
                template_vars = {
                    'ticket_id': str(ticket_id),
                    'ticket_title': title,
                    'category': category,
                    'priority': priority,
                    'status': 'Open',
                    'student_id': student_id,
                    'student_name': student_name,
                    'student_email': student_email,
                    'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'description': description[:500] + '...' if len(description) > 500 else description,
                    'portal_link': '/support',
                    'signature': 'University Student Support System'
                }

                # Render the email template
                subject, body = render_template('ticket_created_admin_notification', template_vars)

                if subject and body:
                    # Send to all admins
                    for admin_email in admin_emails:
                        try:
                            send_email(admin_email, subject, body)
                        except Exception as e:
                            logging.warning(f"Failed to send ticket notification to {admin_email}: {e}")
                else:
                    # Try template-based fallback email
                    fallback_template_vars = {
                        'ticket_id': str(ticket_id),
                        'title': title,
                        'category': category,
                        'priority': priority,
                        'student_id': student_id,
                        'created_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'description': description[:500] + ('...' if len(description) > 500 else '')
                    }

                    subject, body = render_template('support_ticket_created_admin', fallback_template_vars)

                    if not subject or not body:
                        # Final fallback to basic email if template also fails
                        subject = f"New Support Ticket Created - #{ticket_id} [{priority} Priority]"
                        body = f"""A new support ticket has been submitted.

Ticket ID: #{ticket_id}
Title: {title}
Category: {category}
Priority: {priority}
Student ID: {student_id}
Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Description:
{description[:500]}{'...' if len(description) > 500 else ''}

Please log into the Student Support Portal to review this ticket.
"""

                    for admin_email in admin_emails:
                        try:
                            send_email(admin_email, subject, body)
                        except Exception as e:
                            logging.warning(f"Failed to send ticket notification to {admin_email}: {e}")

            except Exception as e:
                logging.error(f"Error sending ticket creation notification: {e}")

        # Run in background thread to avoid database locking
        thread = threading.Thread(target=send_notification, daemon=True)
        thread.start()

    def _send_ticket_update_notification(self, ticket_id, update_type, update_details=''):
        """Send email notification to user when their ticket is updated"""
        if not EMAIL_SERVICE_AVAILABLE:
            return

        def send_notification():
            import time
            time.sleep(1)  # Wait for database transaction to complete

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=10)
                cursor = conn.cursor()

                # Get ticket and user details
                cursor.execute('''
                    SELECT st.title, st.category, st.status, st.priority, st.student_id,
                           u.email, u.first_name, u.last_name, u.username
                    FROM support_tickets st
                    LEFT JOIN users u ON st.student_id = u.student_id
                    WHERE st.ticket_id = ?
                ''', (ticket_id,))
                result = cursor.fetchone()

                conn.close()

                if not result:
                    return

                ticket_title, category, status, priority, student_id, user_email, first_name, last_name, username = result

                if not user_email:
                    return

                student_name = f"{first_name or ''} {last_name or ''}".strip()
                if not student_name:
                    student_name = username or 'Student'

                # Prepare template variables
                template_vars = {
                    'ticket_id': str(ticket_id),
                    'ticket_title': ticket_title or 'Support Ticket',
                    'category': category or 'General',
                    'status': status or 'Open',
                    'priority': priority or 'Medium',
                    'student_name': student_name,
                    'update_type': update_type,
                    'update_details': update_details,
                    'updated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'signature': 'University Student Support Team'
                }

                # Render the email template
                subject, body = render_template('ticket_update_user_notification', template_vars)

                if subject and body:
                    try:
                        send_email(user_email, subject, body)
                    except Exception as e:
                        logging.warning(f"Failed to send ticket update notification to {user_email}: {e}")
                else:
                    # Try template-based fallback email
                    fallback_template_vars = {
                        'ticket_id': str(ticket_id),
                        'ticket_title': ticket_title,
                        'update_type': update_type,
                        'status': status,
                        'student_name': student_name,
                        'update_details': update_details
                    }

                    subject, body = render_template('support_ticket_update_user', fallback_template_vars)

                    if not subject or not body:
                        # Final fallback to basic email if template also fails
                        subject = f"Update on Your Support Ticket #{ticket_id} - {update_type}"
                        body = f"""Dear {student_name},

There has been an update to your support ticket.

Ticket ID: #{ticket_id}
Title: {ticket_title}
Update Type: {update_type}
Current Status: {status}

{update_details}

To view the full ticket details, please log into the Student Portal.

Best regards,
University Student Support Team
"""

                    try:
                        send_email(user_email, subject, body)
                    except Exception as e:
                        logging.warning(f"Failed to send ticket update notification to {user_email}: {e}")

            except Exception as e:
                logging.error(f"Error sending ticket update notification: {e}")

        # Run in background thread to avoid database locking
        thread = threading.Thread(target=send_notification, daemon=True)
        thread.start()

    def _send_ticket_status_change_notification(self, ticket_id, old_status, new_status, changed_by='Support Staff'):
        """Send email notification when ticket status changes"""
        if not EMAIL_SERVICE_AVAILABLE:
            return

        def send_notification():
            import time
            time.sleep(1)  # Wait for database transaction to complete

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=10)
                cursor = conn.cursor()

                # Get ticket and user details
                cursor.execute('''
                    SELECT st.title, st.category, st.priority, st.student_id,
                           u.email, u.first_name, u.last_name, u.username
                    FROM support_tickets st
                    LEFT JOIN users u ON st.student_id = u.student_id
                    WHERE st.ticket_id = ?
                ''', (ticket_id,))
                result = cursor.fetchone()

                conn.close()

                if not result:
                    return

                ticket_title, category, priority, student_id, user_email, first_name, last_name, username = result

                if not user_email:
                    return

                student_name = f"{first_name or ''} {last_name or ''}".strip()
                if not student_name:
                    student_name = username or 'Student'

                # Status explanations
                status_explanations = {
                    'Open': 'Your ticket is now open and awaiting review by our support team.',
                    'In Progress': 'A support staff member is actively working on your request.',
                    'Pending': 'Your ticket is awaiting additional information or action.',
                    'Resolved': 'Your issue has been addressed. Please let us know if you need further assistance.',
                    'Closed': 'Your ticket has been closed. Thank you for contacting support.'
                }

                template_vars = {
                    'ticket_id': str(ticket_id),
                    'ticket_title': ticket_title or 'Support Ticket',
                    'old_status': old_status,
                    'new_status': new_status,
                    'changed_by': changed_by,
                    'updated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'student_name': student_name,
                    'status_message': f'Status changed from "{old_status}" to "{new_status}"',
                    'status_explanation': status_explanations.get(new_status, 'Your ticket status has been updated.'),
                    'signature': 'University Student Support Team'
                }

                subject, body = render_template('ticket_status_changed_notification', template_vars)

                if subject and body:
                    try:
                        send_email(user_email, subject, body)
                    except Exception as e:
                        logging.warning(f"Failed to send status change notification: {e}")

            except Exception as e:
                logging.error(f"Error sending status change notification: {e}")

        # Run in background thread to avoid database locking
        thread = threading.Thread(target=send_notification, daemon=True)
        thread.start()

    def show_status_update_dialog(self, ticket_id):
        """Show dialog to update ticket status"""
        status_dialog = tk.Toplevel(self.root)
        status_dialog.title(f"Update Status - Ticket #{ticket_id}")
        status_dialog.geometry("900x550")
        status_dialog.transient(self.root)
        status_dialog.grab_set()

        form_frame = ttk.Frame(status_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="Update Ticket Status",
                 style='Heading.TLabel').pack(pady=(0, 15))

        # Status selection
        ttk.Label(form_frame, text="New Status:").pack(anchor="w")
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                   values=TICKET_STATUSES, state="readonly")
        status_combo.pack(fill="x", pady=(5, 10))

        # Resolution notes
        ttk.Label(form_frame, text="Resolution Notes (optional):").pack(anchor="w")
        notes_text = scrolledtext.ScrolledText(form_frame, height=4, wrap=tk.WORD)
        notes_text.pack(fill="both", expand=True, pady=(5, 15))

        def update_status():
            new_status = status_var.get()
            if not new_status:
                messagebox.showerror("Error", "Please select a status")
                return

            notes = notes_text.get(1.0, tk.END).strip() or None

            try:
                self.support.update_ticket_status(ticket_id, new_status, notes)
                messagebox.showinfo("Success", f"Status updated to {new_status}")
                status_dialog.destroy()
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", f"Could not update status: {e}")

        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Update Status", command=update_status).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=status_dialog.destroy).pack(side="left")

