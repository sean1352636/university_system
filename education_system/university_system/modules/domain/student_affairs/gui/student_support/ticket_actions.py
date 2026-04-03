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

class TicketActionsMixin:
    def show_staff_ticket_context_menu(self, event, tree):
        """Show staff-specific context menu"""
        self.show_ticket_context_menu(event, tree)  # Use same menu for now

    def assign_ticket_to_me(self, ticket_id):
        """Assign ticket to current user"""
        user_id, username = self._get_current_user_identity()
        if not user_id or not username:
            messagebox.showerror("Error", "You must be signed in to assign tickets.")
            return

        role = self.auth.current_user.get('role') if self.auth and self.auth.current_user else None
        if role not in ('staff', 'admin'):
            messagebox.showwarning("Permission Denied", "Only staff members can self-assign tickets.")
            return

        try:
            def assign(conn):
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT assigned_to, status
                    FROM support_tickets
                    WHERE ticket_id = ?
                    ''',
                    (ticket_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return {'updated': False, 'reason': 'not_found'}

                current_assignee, status = row
                if current_assignee == username:
                    return {'updated': False, 'reason': 'already_assigned'}

                if status in ('Resolved', 'Closed'):
                    return {'updated': False, 'reason': 'closed'}

                new_status = status
                if status is None or status.lower() in ('open', 'new', 'unassigned', 'pending'):
                    new_status = 'In Progress'

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''
                    UPDATE support_tickets
                    SET assigned_to = ?, status = ?, last_updated_datetime = ?
                    WHERE ticket_id = ?
                    ''',
                    (username, new_status, timestamp, ticket_id)
                )
                return {'updated': cursor.rowcount > 0, 'new_status': new_status}

            result = self._safe_db_call(assign)

            if not result['updated']:
                reason = result.get('reason')
                if reason == 'not_found':
                    messagebox.showerror("Error", f"Ticket #{ticket_id} was not found.")
                elif reason == 'already_assigned':
                    messagebox.showinfo("Information", "You are already assigned to this ticket.")
                elif reason == 'closed':
                    messagebox.showwarning("Ticket Closed", "Closed or resolved tickets cannot be reassigned.")
                else:
                    messagebox.showwarning("No Changes", "Ticket assignment was not updated.")
                return

            messagebox.showinfo("Success", f"Ticket #{ticket_id} assigned to you (status: {result['new_status']}).")
            self.refresh_data()
        except Exception as e:
            messagebox.showerror("Error", f"Could not assign ticket: {e}")

    def show_add_response_dialog(self, ticket):
        """Show dialog to add response to ticket"""
        # Handle None or invalid ticket
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror("Error", "Invalid ticket data")
            return

        ticket_id = ticket.get('ticket_id', 'N/A')
        ticket_title = ticket.get('title', 'Untitled')

        response_dialog = tk.Toplevel(self.root)
        response_dialog.title(f"💬 Add Response to Ticket #{ticket_id}")
        response_dialog.geometry("1400x800")
        response_dialog.transient(self.root)
        response_dialog.grab_set()

        # Dialog content
        form_frame = ttk.Frame(response_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text=f"Adding response to: {ticket_title}",
                 style='Heading.TLabel').pack(anchor="w", pady=(0, 15))

        # Response text
        ttk.Label(form_frame, text="Response:").pack(anchor="w")
        response_text = scrolledtext.ScrolledText(form_frame, height=12, wrap=tk.WORD)
        response_text.pack(fill="both", expand=True, pady=(5, 15))

        # Options
        options_frame = ttk.Frame(form_frame)
        options_frame.pack(fill="x", pady=(0, 15))

        # Internal note checkbox (for staff)
        if self.auth.current_user['role'] in ('staff', 'admin'):
            self.is_internal_var = tk.BooleanVar()
            ttk.Checkbutton(options_frame, text="🔒 Internal note (staff only)",
                           variable=self.is_internal_var).pack(side="left")

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")

        def submit_response():
            text = response_text.get(1.0, tk.END).strip()
            if not text:
                messagebox.showerror("Error", "Response cannot be empty")
                return

            try:
                is_internal = getattr(self, 'is_internal_var', tk.BooleanVar()).get()
                self.support.add_ticket_response(ticket_id, text, is_internal=is_internal)
                messagebox.showinfo("Success", "Response added successfully!")
                response_dialog.destroy()
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", f"Could not add response: {e}")

        ttk.Button(btn_frame, text="💬 Add Response", command=submit_response,
                  style='Primary.TButton').pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=response_dialog.destroy).pack(side="left")

    def show_add_response_dialog_by_id(self, ticket_id):
        """Show add response dialog by ticket ID"""
        try:
            ticket = self.support.get_ticket_details(ticket_id)
            self.show_add_response_dialog(ticket)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load ticket: {e}")

    def can_respond_to_ticket(self, ticket):
        """Check if current user can respond to ticket"""
        if not self.auth or not self.auth.current_user:
            return False

        # Handle None or invalid ticket
        if ticket is None or not isinstance(ticket, dict):
            return False

        user_role = self.auth.current_user.get('role', '')

        # Staff can always respond
        if user_role in ('staff', 'admin'):
            return True

        # Students can respond to their own tickets
        if user_role == 'student':
            conn = None
            try:
                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user.get('id'),))
                result = cursor.fetchone()

                ticket_student_id = ticket.get('student_id')
                if result and result[0] == ticket_student_id:
                    return True
            except Exception:
                pass
            finally:
                if conn:
                    conn.close()

        return False

    def escalate_ticket(self, ticket_id):
        """Escalate a ticket"""
        try:
            # Update ticket status to escalated
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            escalation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            UPDATE support_tickets
            SET status = 'Escalated', escalated_at = ?, last_updated_datetime = ?
            WHERE ticket_id = ?
            ''', (escalation_time, escalation_time, ticket_id))

            # Add escalation response
            cursor.execute('''
            INSERT INTO ticket_responses (
                ticket_id, responder_id, responder_role, response_text,
                response_datetime, is_auto_generated
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                ticket_id, auth.current_user['id'], auth.current_user['role'],
                f'Ticket escalated to supervisor by {auth.current_user["username"]}',
                escalation_time, 1
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Ticket #{ticket_id} escalated successfully!")
            self.refresh_data()

        except Exception as e:
            messagebox.showerror("Error", f"Could not escalate ticket: {e}")

    def show_merge_dialog(self, ticket):
        """Show dialog to merge tickets"""
        # Handle None or invalid ticket
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror("Error", "Invalid ticket data")
            return

        ticket_id = ticket.get('ticket_id', 'N/A')

        merge_dialog = tk.Toplevel(self.root)
        merge_dialog.title("Merge Tickets")
        merge_dialog.geometry("1000x650")
        merge_dialog.transient(self.root)
        merge_dialog.grab_set()

        form_frame = ttk.Frame(merge_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text=f"Merge into Ticket #{ticket_id}",
                 style='Heading.TLabel').pack(pady=(0, 15))

        ttk.Label(form_frame, text="Secondary ticket IDs (comma-separated):").pack(anchor="w")
        secondary_ids_entry = ttk.Entry(form_frame, width=40)
        secondary_ids_entry.pack(fill="x", pady=(5, 10))

        ttk.Label(form_frame, text="Merge reason:").pack(anchor="w")
        reason_text = scrolledtext.ScrolledText(form_frame, height=4, wrap=tk.WORD)
        reason_text.pack(fill="both", expand=True, pady=(5, 15))

        def perform_merge():
            secondary_ids = secondary_ids_entry.get().strip()
            reason = reason_text.get(1.0, tk.END).strip()

            if not secondary_ids or not reason:
                messagebox.showerror("Error", "Please provide secondary ticket IDs and reason")
                return

            try:
                ids = [int(id.strip()) for id in secondary_ids.split(',')]
                self.support.merge_tickets(ticket_id, ids, reason)
                messagebox.showinfo("Success", "Tickets merged successfully!")
                merge_dialog.destroy()
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", f"Could not merge tickets: {e}")

        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Merge Tickets", command=perform_merge).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=merge_dialog.destroy).pack(side="left")

    def export_ticket(self, ticket):
        """Export individual ticket data"""
        # Handle None or invalid ticket
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror("Error", "Invalid ticket data")
            return

        ticket_id = ticket.get('ticket_id')
        if not ticket_id:
            messagebox.showerror("Error", "No ticket ID found")
            return

        try:
            filename = filedialog.asksaveasfilename(
                title="Export Ticket",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("Text files", "*.txt")]
            )

            if not filename:
                return

            # Get full ticket details
            ticket_details = self.support.get_ticket_details(ticket_id)

            if filename.endswith('.json'):
                with open(filename, 'w') as f:
                    json.dump(ticket_details, f, indent=2, default=str)
            else:
                # Export as formatted text with safe access
                if not ticket_details or not isinstance(ticket_details, dict):
                    messagebox.showerror("Error", "Could not retrieve ticket details")
                    return

                with open(filename, 'w') as f:
                    f.write(f"Ticket #{ticket_details.get('ticket_id', 'N/A')}\n")
                    f.write("=" * 50 + "\n")
                    f.write(f"Title: {ticket_details.get('title', 'N/A')}\n")
                    f.write(f"Student: {ticket_details.get('student_id', 'N/A')}\n")
                    f.write(f"Status: {ticket_details.get('status', 'N/A')}\n")
                    f.write(f"Priority: {ticket_details.get('priority', 'N/A')}\n")
                    f.write(f"Category: {ticket_details.get('category', 'N/A')}\n")
                    f.write(f"Created: {ticket_details.get('created_datetime', 'N/A')}\n")
                    f.write(f"\nDescription:\n{ticket_details.get('description', 'N/A')}\n")

                    responses = ticket_details.get('responses', []) or []
                    if responses:
                        f.write(f"\nResponses:\n")
                        for response in responses:
                            if response and isinstance(response, dict):
                                f.write(f"\n[{response.get('response_datetime', 'N/A')}] {response.get('responder_role', 'N/A')}:\n")
                                f.write(f"{response.get('response_text', '')}\n")

            messagebox.showinfo("Success", f"Ticket exported to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Could not export ticket: {e}")

    def show_ticket_history(self, ticket_id):
        """Show complete ticket history in a new window"""
        try:
            history = self.support.get_ticket_history(ticket_id)

            history_window = tk.Toplevel(self.root)
            history_window.title(f"Ticket #{ticket_id} History")
            history_window.geometry("1500x900")
            history_window.transient(self.root)

            # Create scrollable timeline
            canvas = tk.Canvas(history_window)
            scrollbar = ttk.Scrollbar(history_window, orient="vertical", command=canvas.yview)
            timeline_frame = ttk.Frame(canvas)

            timeline_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=timeline_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Title
            title_frame = ttk.Frame(timeline_frame, padding="10")
            title_frame.pack(fill="x")

            ttk.Label(title_frame, text=f"Complete History for Ticket #{ticket_id}",
                     style='Title.TLabel').pack()

            # Timeline events
            timeline = history['timeline']
            for event in timeline:
                event_frame = ttk.LabelFrame(timeline_frame, padding="10")
                event_frame.pack(fill="x", padx=10, pady=5)

                event_type = event['type']
                data = event['data']

                if event_type == 'creation':
                    event_frame.config(text=f"Created - {event['datetime']}")
                    ttk.Label(event_frame, text=f"Title: {data['title']}").pack(anchor="w")
                    ttk.Label(event_frame, text=f"Description: {data['description'][:100]}...").pack(anchor="w")

                elif event_type == 'response':
                    responder = data['responder_role']
                    is_internal = data.get('is_internal', False)
                    is_auto = data.get('is_auto_generated', False)

                    tags = []
                    if is_internal:
                        tags.append("INTERNAL")
                    if is_auto:
                        tags.append("AUTO")

                    tag_text = f" [{', '.join(tags)}]" if tags else ""
                    event_frame.config(text=f"Response by {responder}{tag_text} - {event['datetime']}")

                    ttk.Label(event_frame, text=data['response_text'][:150] + "...").pack(anchor="w")

                elif event_type == 'attachment':
                    event_frame.config(text=f"Attachment Added - {event['datetime']}")
                    ttk.Label(event_frame, text=f"File: {data['original_filename']}").pack(anchor="w")

                elif event_type == 'audit':
                    event_frame.config(text=f"System Event - {event['datetime']}")
                    ttk.Label(event_frame, text=f"Action: {data['action']}").pack(anchor="w")

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        except Exception as e:
            messagebox.showerror("Error", f"Could not load ticket history: {e}")

    def show_add_internal_note_dialog(self, ticket):
        """Show dialog to add internal note"""
        # Handle None or invalid ticket
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror("Error", "Invalid ticket data")
            return

        ticket_id = ticket.get('ticket_id', 'N/A')

        note_dialog = tk.Toplevel(self.root)
        note_dialog.title(f"Add Internal Note - Ticket #{ticket_id}")
        note_dialog.geometry("1200x700")
        note_dialog.transient(self.root)
        note_dialog.grab_set()

        form_frame = ttk.Frame(note_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="Internal Note (Staff Only)",
                 style='Heading.TLabel').pack(pady=(0, 15))

        note_text = scrolledtext.ScrolledText(form_frame, height=8, wrap=tk.WORD)
        note_text.pack(fill="both", expand=True, pady=(0, 15))

        def add_note():
            text = note_text.get(1.0, tk.END).strip()
            if not text:
                messagebox.showerror("Error", "Note cannot be empty")
                return

            try:
                self.support.add_ticket_response(ticket_id, text, is_internal=True)
                messagebox.showinfo("Success", "Internal note added successfully!")
                note_dialog.destroy()
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", f"Could not add note: {e}")

        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Add Note", command=add_note).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=note_dialog.destroy).pack(side="left")

    def show_response_template_dialog(self, ticket):
        """Show dialog to use response template"""
        template_dialog = tk.Toplevel(self.root)
        template_dialog.title("Use Response Template")
        template_dialog.geometry("1400x800")
        template_dialog.transient(self.root)
        template_dialog.grab_set()

        form_frame = ttk.Frame(template_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="Select Response Template",
                 style='Heading.TLabel').pack(pady=(0, 15))

        # Get templates
        templates = self.support.get_response_templates()

        if not templates:
            ttk.Label(form_frame, text="No response templates available").pack()
            ttk.Button(form_frame, text="Close", command=template_dialog.destroy).pack(pady=10)
            return

        # Template selection
        template_frame = ttk.LabelFrame(form_frame, text="Templates", padding="10")
        template_frame.pack(fill="x", pady=(0, 10))

        template_var = tk.StringVar()
        template_combo = ttk.Combobox(template_frame, textvariable=template_var, state="readonly")
        template_combo['values'] = [f"{t['name']} - {t.get('category', 'General')}" for t in templates]
        template_combo.pack(fill="x")

        # Preview area
        preview_frame = ttk.LabelFrame(form_frame, text="Preview", padding="10")
        preview_frame.pack(fill="both", expand=True, pady=(0, 10))

        preview_text = scrolledtext.ScrolledText(preview_frame, height=8, wrap=tk.WORD, state='disabled')
        preview_text.pack(fill="both", expand=True)

        def update_preview(event=None):
            selection = template_combo.current()
            if selection >= 0:
                template = templates[selection]
                preview_text.config(state='normal')
                preview_text.delete(1.0, tk.END)
                preview_text.insert(1.0, template['content'])
                preview_text.config(state='disabled')

        template_combo.bind('<<ComboboxSelected>>', update_preview)

        def use_template():
            selection = template_combo.current()
            if selection < 0:
                messagebox.showerror("Error", "Please select a template")
                return

            template = templates[selection]
            template_dialog.destroy()

            # Show add response dialog with template pre-filled
            self.show_add_response_dialog_with_template(ticket, template)

        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Use Template", command=use_template).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=template_dialog.destroy).pack(side="left")

    def show_add_response_dialog_with_template(self, ticket, template):
        """Show add response dialog with template pre-filled"""
        # Handle None or invalid ticket
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror("Error", "Invalid ticket data")
            return
        if template is None or not isinstance(template, dict):
            messagebox.showerror("Error", "Invalid template data")
            return

        ticket_id = ticket.get('ticket_id', 'N/A')
        template_name = template.get('name', 'Unknown')
        template_content = template.get('content', '')
        template_id = template.get('template_id')

        response_dialog = tk.Toplevel(self.root)
        response_dialog.title(f"Add Response - Ticket #{ticket_id}")
        response_dialog.geometry("1400x800")
        response_dialog.transient(self.root)
        response_dialog.grab_set()

        form_frame = ttk.Frame(response_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text=f"Using template: {template_name}",
                 style='Heading.TLabel').pack(anchor="w", pady=(0, 15))

        # Response text with template content
        ttk.Label(form_frame, text="Response:").pack(anchor="w")
        response_text = scrolledtext.ScrolledText(form_frame, height=12, wrap=tk.WORD)
        response_text.pack(fill="both", expand=True, pady=(5, 15))
        response_text.insert(1.0, template_content)

        # Options
        options_frame = ttk.Frame(form_frame)
        options_frame.pack(fill="x", pady=(0, 15))

        if self.auth and self.auth.current_user and self.auth.current_user.get('role') in ('staff', 'admin'):
            self.is_internal_var = tk.BooleanVar()
            ttk.Checkbutton(options_frame, text="Internal note (staff only)",
                           variable=self.is_internal_var).pack(side="left")

        def submit_response():
            text = response_text.get(1.0, tk.END).strip()
            if not text:
                messagebox.showerror("Error", "Response cannot be empty")
                return

            try:
                is_internal = getattr(self, 'is_internal_var', tk.BooleanVar()).get()
                self.support.add_ticket_response(
                    ticket_id, text,
                    template_id=template_id,
                    is_internal=is_internal
                )
                messagebox.showinfo("Success", "Response added successfully!")
                response_dialog.destroy()
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", f"Could not add response: {e}")

        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Add Response", command=submit_response).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=response_dialog.destroy).pack(side="left")

    def show_satisfaction_rating(self):
        """Show satisfaction rating dialog for resolved tickets"""
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] != 'student':
            messagebox.showerror("Error", "Only students can submit satisfaction ratings")
            return

        rating_dialog = tk.Toplevel(self.root)
        rating_dialog.title("Submit Satisfaction Rating")
        rating_dialog.geometry("1300x800")
        rating_dialog.transient(self.root)
        rating_dialog.grab_set()

        form_frame = ttk.Frame(rating_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="Rate Your Support Experience",
                 style='Title.TLabel').pack(pady=(0, 20))

        # Get resolved tickets for this student
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showerror("Error", "No student ID found")
                rating_dialog.destroy()
                return

            student_id = result[0]
            filters = {'status': 'Resolved'}
            result = self.support.get_student_tickets(student_id, filters, page=1, per_page=50)

            # Handle None or invalid result
            if result is None:
                ttk.Label(form_frame, text="No resolved tickets to rate").pack()
                ttk.Button(form_frame, text="Close", command=rating_dialog.destroy).pack(pady=10)
                return

            resolved_tickets = result.get('tickets', []) if isinstance(result, dict) else []

            if not resolved_tickets:
                ttk.Label(form_frame, text="No resolved tickets to rate").pack()
                ttk.Button(form_frame, text="Close", command=rating_dialog.destroy).pack(pady=10)
                return

            # Ticket selection
            ttk.Label(form_frame, text="Select Ticket:").pack(anchor="w")
            ticket_var = tk.StringVar()
            ticket_combo = ttk.Combobox(form_frame, textvariable=ticket_var, state="readonly")
            ticket_combo['values'] = [f"#{t['ticket_id']} - {t['title']}" for t in resolved_tickets]
            ticket_combo.pack(fill="x", pady=(5, 10))

            # Rating
            ttk.Label(form_frame, text="Rating (1-5 stars):").pack(anchor="w")
            rating_var = tk.IntVar(value=5)
            rating_frame = ttk.Frame(form_frame)
            rating_frame.pack(anchor="w", pady=(5, 10))

            for i in range(1, 6):
                ttk.Radiobutton(rating_frame, text=f"{i} star{'s' if i > 1 else ''}",
                               variable=rating_var, value=i).pack(side="left", padx=(0, 10))

            # Feedback
            ttk.Label(form_frame, text="Additional Feedback (optional):").pack(anchor="w")
            feedback_text = scrolledtext.ScrolledText(form_frame, height=6, wrap=tk.WORD)
            feedback_text.pack(fill="both", expand=True, pady=(5, 15))

            def submit_rating():
                selection = ticket_combo.current()
                if selection < 0:
                    messagebox.showerror("Error", "Please select a ticket")
                    return

                ticket = resolved_tickets[selection]
                # Handle None or invalid ticket
                if ticket is None or not isinstance(ticket, dict):
                    messagebox.showerror("Error", "Invalid ticket data")
                    return

                ticket_id = ticket.get('ticket_id')
                if not ticket_id:
                    messagebox.showerror("Error", "No ticket ID found")
                    return

                rating = rating_var.get()
                feedback = feedback_text.get(1.0, tk.END).strip() or None

                try:
                    self.support.submit_satisfaction_rating(ticket_id, rating, feedback)
                    messagebox.showinfo("Success", "Thank you for your feedback!")
                    rating_dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Could not submit rating: {e}")

            btn_frame = ttk.Frame(form_frame)
            btn_frame.pack(fill="x")

            ttk.Button(btn_frame, text="Submit Rating", command=submit_rating).pack(side="left", padx=(0, 10))
            ttk.Button(btn_frame, text="Cancel", command=rating_dialog.destroy).pack(side="left")

        except Exception as e:
            messagebox.showerror("Error", f"Could not load tickets: {e}")
            rating_dialog.destroy()

    def update_ticket_assignment(self, ticket_id, window):
        """Update ticket assignment"""
        try:
            assigned_to = self.assign_to_var.get().strip()

            # Update in database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                UPDATE support_tickets
                SET assigned_to = ?, last_updated_datetime = ?
                WHERE ticket_id = ?
                ''', (assigned_to, update_time, ticket_id))

                # Add system response
                cursor.execute('''
                INSERT INTO ticket_responses (
                    ticket_id, responder_id, responder_role, response_text,
                    response_datetime, is_auto_generated
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    ticket_id, auth.current_user['id'], auth.current_user['role'],
                    f"Ticket assigned to {assigned_to}" if assigned_to else "Ticket unassigned",
                    update_time, 1
                ))

                conn.commit()
            finally:
                conn.close()

            # Send email notification to user about assignment
            if assigned_to:
                self._send_ticket_update_notification(
                    ticket_id,
                    'Ticket Assigned',
                    f"Your ticket has been assigned to {assigned_to}. They will review your request and respond shortly."
                )

            messagebox.showinfo("Success", f"Ticket assignment updated")
            window.destroy()
            self.refresh_data()

        except Exception as e:
            messagebox.showerror("Error", f"Could not update assignment: {e}")

    def update_ticket_status_action(self, ticket_id, window):
        """Update ticket status from actions tab"""
        try:
            new_status = self.new_status_var.get()
            if not new_status:
                messagebox.showerror("Error", "Please select a status")
                return

            # Get current status before update
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('SELECT status FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
                result = cursor.fetchone()
                old_status = result[0] if result else 'Open'
            finally:
                conn.close()

            self.support.update_ticket_status(ticket_id, new_status)

            # Send email notification if status actually changed
            if old_status != new_status:
                changed_by = self.auth.current_user.get('username', 'Support Staff') if self.auth and self.auth.current_user else 'Support Staff'
                self._send_ticket_status_change_notification(ticket_id, old_status, new_status, changed_by)

            messagebox.showinfo("Success", f"Status updated to {new_status}")
            window.destroy()
            self.refresh_data()

        except Exception as e:
            messagebox.showerror("Error", f"Could not update status: {e}")

