#!/usr/bin/env python3
"""
Security Desk - A modern Python GUI application for security assistance
Features: Help requests, issue reporting, emergency contacts, status monitoring,
          user authentication, email notifications, and admin ticket management
Uses the central database for data persistence.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import json
import logging

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

# Color palette - Dark industrial theme with amber accents
COLORS = {
    'bg_dark': '#0d1117',
    'bg_panel': '#161b22',
    'bg_card': '#21262d',
    'bg_input': '#0d1117',
    'border': '#30363d',
    'border_highlight': '#f0883e',
    'text_primary': '#e6edf3',
    'text_secondary': '#8b949e',
    'text_muted': '#6e7681',
    'accent_amber': '#f0883e',
    'accent_amber_hover': '#f4a261',
    'success': '#3fb950',
    'warning': '#d29922',
    'danger': '#f85149',
    'info': '#58a6ff',
}

# Database schema for security desk tickets
SECURITY_DESK_SCHEMA = """
CREATE TABLE IF NOT EXISTS security_desk_tickets (
    id TEXT PRIMARY KEY,
    type TEXT,
    category TEXT,
    priority TEXT DEFAULT 'Normal',
    status TEXT DEFAULT 'Open',
    subject TEXT,
    description TEXT,
    location TEXT,
    user_id TEXT,
    user_name TEXT,
    user_email TEXT,
    admin_notes TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS security_desk_counter (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    counter INTEGER DEFAULT 1000
);

INSERT OR IGNORE INTO security_desk_counter (id, counter) VALUES (1, 1000);
"""


def init_security_desk_database():
    """Initialize security desk database tables."""
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            conn.executescript(SECURITY_DESK_SCHEMA)
            conn.commit()
        logger.info("Security desk database tables initialized")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize security desk database: {e}")
        return False


def get_current_user():
    """Get the current authenticated user from the system."""
    try:
        from education_system.systems.university.infrastructure.shared_context import get_current_user as get_user
        user = get_user()
        if user:
            return user
    except ImportError:
        pass
    return {"username": "guest", "role": "guest", "email": "", "id": None, "name": "Guest User"}


def get_admin_emails():
    """Get list of admin user emails for notifications."""
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL AND email != ''"
            )
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.debug(f"Could not fetch admin emails: {e}")
    return []


def send_ticket_email(recipient_email, subject, body, ticket_id=None):
    """Send email notification about a ticket."""
    try:
        from education_system.systems.university.infrastructure.email.email_service import send_email_as_system
        send_email_as_system(
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            system_name="Security Desk"
        )
        logger.info(f"Email sent to {recipient_email} for ticket {ticket_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to send email: {e}")
        return False


class HelpFormDialog(tk.Toplevel):
    """Dialog for filling out help request details."""

    def __init__(self, parent, help_type, icon, current_user):
        super().__init__(parent)
        self.title(f"{icon} {_t('security_desk.request_header', help_type=help_type)}")
        self.geometry("500x600")
        self.resizable(False, True)
        self.transient(parent)
        self.configure(bg=COLORS['bg_panel'])

        self.help_type = help_type
        self.current_user = current_user
        self.result = None

        self.setup_ui()

        # Center and grab focus
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{x}+{y}")
        self.wait_visibility()
        self.grab_set()

    def setup_ui(self):
        # Header
        header = tk.Frame(self, bg=COLORS['accent_amber'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text=f"  {_t('security_desk.request_header', help_type=self.help_type)}",
                font=('Segoe UI', 16, 'bold'),
                bg=COLORS['accent_amber'], fg=COLORS['bg_dark']).pack(side=tk.LEFT, padx=15, pady=15)

        # Scrollable form container
        canvas_frame = tk.Frame(self, bg=COLORS['bg_panel'])
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame, bg=COLORS['bg_panel'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)

        form = tk.Frame(canvas, bg=COLORS['bg_panel'], padx=25, pady=20)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas_window = canvas.create_window((0, 0), window=form, anchor="nw")

        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def configure_width(event):
            canvas.itemconfig(canvas_window, width=event.width)

        form.bind("<Configure>", configure_scroll)
        canvas.bind("<Configure>", configure_width)

        # Mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        # User info (read-only)
        tk.Label(form, text=_t("security_desk.form.requester"), font=('Segoe UI', 10, 'bold'),
                bg=COLORS['bg_panel'], fg=COLORS['text_secondary']).pack(anchor='w')

        user_display = self.current_user.get('name') or self.current_user.get('username', 'Unknown')
        tk.Label(form, text=user_display, font=('Segoe UI', 11),
                bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                padx=10, pady=8, anchor='w').pack(fill=tk.X, pady=(5, 15))

        # Dynamic fields based on help type
        self.fields = {}
        self.create_type_specific_fields(form)

        # Priority
        tk.Label(form, text=_t("security_desk.form.priority"), font=('Segoe UI', 10, 'bold'),
                bg=COLORS['bg_panel'], fg=COLORS['text_secondary']).pack(anchor='w', pady=(15, 5))

        self.priority_var = tk.StringVar(value=_t("security_desk.form.priority_medium"))
        priority_frame = tk.Frame(form, bg=COLORS['bg_panel'])
        priority_frame.pack(fill=tk.X)

        priorities = [
            (_t("security_desk.form.priority_low"), "Low"),
            (_t("security_desk.form.priority_medium"), "Medium"),
            (_t("security_desk.form.priority_high"), "High"),
            (_t("security_desk.form.priority_critical"), "Critical")
        ]
        for label, priority in priorities:
            color = {'Low': COLORS['text_muted'], 'Medium': COLORS['warning'],
                    'High': COLORS['accent_amber'], 'Critical': COLORS['danger']}[priority]
            rb = tk.Radiobutton(priority_frame, text=label, variable=self.priority_var,
                               value=priority, bg=COLORS['bg_panel'], fg=color,
                               selectcolor=COLORS['bg_input'], activebackground=COLORS['bg_panel'],
                               font=('Segoe UI', 10))
            rb.pack(side=tk.LEFT, padx=(0, 15))

        # Additional Details
        tk.Label(form, text=_t("security_desk.form.additional_details"), font=('Segoe UI', 10, 'bold'),
                bg=COLORS['bg_panel'], fg=COLORS['text_secondary']).pack(anchor='w', pady=(15, 5))

        self.details_text = scrolledtext.ScrolledText(form, height=5,
                                                      bg=COLORS['bg_input'], fg=COLORS['text_primary'],
                                                      insertbackground=COLORS['accent_amber'],
                                                      font=('Segoe UI', 10), relief='flat')
        self.details_text.pack(fill=tk.X)

        # Buttons
        btn_frame = tk.Frame(form, bg=COLORS['bg_panel'])
        btn_frame.pack(fill=tk.X, pady=(25, 10))

        tk.Button(btn_frame, text=_t("security_desk.form.cancel"), command=self.destroy,
                 bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                 font=('Segoe UI', 11), relief='flat', padx=25, pady=8,
                 cursor='hand2').pack(side=tk.RIGHT)

        tk.Button(btn_frame, text=_t("security_desk.form.submit_request"), command=self.submit,
                 bg=COLORS['accent_amber'], fg=COLORS['bg_dark'],
                 font=('Segoe UI', 11, 'bold'), relief='flat', padx=25, pady=8,
                 cursor='hand2').pack(side=tk.RIGHT, padx=(0, 10))

    def create_type_specific_fields(self, parent):
        """Create fields specific to the help type."""
        if self.help_type == "Access Issue":
            self.add_field(parent, "Building/Location", "entry", "e.g., Main Building, Room 101")
            self.add_field(parent, "Access Type", "combo",
                          values=["Door Lock", "Card Reader", "Key Issue", "Elevator Access", "Gate/Barrier"])
            self.add_field(parent, "Issue Description", "combo",
                          values=["Locked Out", "Card Not Working", "Lost Key/Card", "Access Denied", "Other"])

        elif self.help_type == "Parking Help":
            self.add_field(parent, "Vehicle Info", "entry", "License plate, make/model")
            self.add_field(parent, "Parking Location", "entry", "Lot name or area")
            self.add_field(parent, "Issue Type", "combo",
                          values=["Permit Issue", "Violation Dispute", "Vehicle Problem", "Space Availability", "Other"])

        elif self.help_type == "Lost & Found":
            self.add_field(parent, "Item Type", "combo",
                          values=["Electronics", "Wallet/Purse", "Keys", "Clothing", "Documents", "Jewelry", "Other"])
            self.add_field(parent, "Action", "combo", values=["Report Lost Item", "Claim Found Item", "Report Found Item"])
            self.add_field(parent, "Item Description", "entry", "Color, brand, distinguishing features")
            self.add_field(parent, "Last Seen Location", "entry", "Where you lost/found the item")

        elif self.help_type == "Visitor Badge":
            self.add_field(parent, "Visitor Name", "entry", "Full name of visitor")
            self.add_field(parent, "Company/Organization", "entry", "Optional")
            self.add_field(parent, "Visit Purpose", "combo",
                          values=["Meeting", "Interview", "Delivery", "Contractor Work", "Tour", "Other"])
            self.add_field(parent, "Expected Duration", "combo",
                          values=["1 Hour", "Half Day", "Full Day", "Multiple Days"])

        elif self.help_type == "Key Request":
            self.add_field(parent, "Key Type", "combo",
                          values=["Office Key", "Building Key", "Access Card", "Master Key", "Cabinet Key"])
            self.add_field(parent, "Location/Room", "entry", "Room or area requiring access")
            self.add_field(parent, "Reason", "combo",
                          values=["New Assignment", "Lost Key", "Damaged Key", "Additional Copy", "Temporary Access"])

        elif self.help_type == "Facility Issue":
            self.add_field(parent, "Issue Category", "combo",
                          values=["Lighting", "HVAC/Temperature", "Plumbing", "Electrical", "Cleaning", "Other"])
            self.add_field(parent, "Location", "entry", "Building, floor, room")
            self.add_field(parent, "Urgency", "combo",
                          values=["Not Urgent", "Needs Attention Today", "Urgent - Safety Concern"])

        else:
            self.add_field(parent, "Subject", "entry", "Brief description of your request")

    def add_field(self, parent, label, field_type, placeholder=None, values=None):
        """Add a form field."""
        tk.Label(parent, text=label, font=('Segoe UI', 10, 'bold'),
                bg=COLORS['bg_panel'], fg=COLORS['text_secondary']).pack(anchor='w', pady=(10, 5))

        if field_type == "combo":
            widget = ttk.Combobox(parent, values=values, state='readonly', font=('Segoe UI', 10))
            widget.pack(fill=tk.X)
            if values:
                widget.set(values[0])
        else:
            widget = tk.Entry(parent, bg=COLORS['bg_input'], fg=COLORS['text_primary'],
                             insertbackground=COLORS['accent_amber'], font=('Segoe UI', 10), relief='flat')
            widget.pack(fill=tk.X, ipady=8)
            if placeholder:
                widget.insert(0, placeholder)
                widget.config(fg=COLORS['text_muted'])
                widget.bind('<FocusIn>', lambda e: self.clear_placeholder(widget, placeholder))
                widget.bind('<FocusOut>', lambda e: self.restore_placeholder(widget, placeholder))

        self.fields[label] = widget

    def clear_placeholder(self, widget, placeholder):
        if widget.get() == placeholder:
            widget.delete(0, tk.END)
            widget.config(fg=COLORS['text_primary'])

    def restore_placeholder(self, widget, placeholder):
        if not widget.get():
            widget.insert(0, placeholder)
            widget.config(fg=COLORS['text_muted'])

    def submit(self):
        """Collect form data and close dialog."""
        self.result = {
            'help_type': self.help_type,
            'priority': self.priority_var.get(),
            'details': self.details_text.get("1.0", tk.END).strip(),
            'fields': {}
        }

        for label, widget in self.fields.items():
            value = widget.get() if hasattr(widget, 'get') else ""
            # Don't include placeholder text
            if value and value not in ["e.g.,", "License", "Lot", "Color", "Where", "Full", "Room", "Building", "Brief"]:
                self.result['fields'][label] = value

        self.destroy()


class TicketDetailsDialog(tk.Toplevel):
    """Dialog for viewing and managing ticket details."""

    def __init__(self, parent, ticket, current_user, on_update=None):
        super().__init__(parent)
        self.title(_t("security_desk.ticket_details.ticket_id", id=ticket['id']))
        self.geometry("550x650")
        self.resizable(False, False)
        self.transient(parent)
        self.configure(bg=COLORS['bg_panel'])

        self.ticket = ticket
        self.current_user = current_user
        self.on_update = on_update
        self.is_admin = current_user.get('role') == 'admin'

        self.setup_ui()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 550) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 650) // 2
        self.geometry(f"+{x}+{y}")
        self.wait_visibility()
        self.grab_set()

    def setup_ui(self):
        # Header
        status_color = {
            'Open': COLORS['info'], 'Under Review': COLORS['warning'],
            'In Progress': COLORS['accent_amber'], 'Resolved': COLORS['success'],
            'Closed': COLORS['text_muted']
        }.get(self.ticket.get('status', 'Open'), COLORS['info'])

        header = tk.Frame(self, bg=status_color, height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text=f"  {self.ticket['id']}", font=('Consolas', 18, 'bold'),
                bg=status_color, fg='white').pack(side=tk.LEFT, padx=15, pady=15)

        tk.Label(header, text=f"● {self.ticket.get('status', 'Open')}",
                font=('Segoe UI', 12, 'bold'), bg=status_color, fg='white').pack(side=tk.RIGHT, padx=20)

        # Content with scrollbar
        canvas = tk.Canvas(self, bg=COLORS['bg_panel'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=COLORS['bg_panel'])

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        inner = tk.Frame(content, bg=COLORS['bg_panel'], padx=25, pady=20)
        inner.pack(fill=tk.BOTH, expand=True)

        # Ticket details
        self.add_detail_row(inner, _t("security_desk.tickets.type"), self.ticket.get('type', 'N/A'))
        self.add_detail_row(inner, _t("security_desk.tickets.priority"), self.ticket.get('priority', 'Medium'))
        self.add_detail_row(inner, _t("security_desk.tickets.created"), self.ticket.get('created', 'N/A'))
        self.add_detail_row(inner, _t("security_desk.tickets.requester"), self.ticket.get('requester_name', 'Unknown'))

        if self.ticket.get('location'):
            self.add_detail_row(inner, _t("security_desk.tickets.location"), self.ticket['location'])

        # Description
        if self.ticket.get('description') or self.ticket.get('details'):
            tk.Label(inner, text=_t("security_desk.tickets.description"), font=('Segoe UI', 10, 'bold'),
                    bg=COLORS['bg_panel'], fg=COLORS['text_secondary']).pack(anchor='w', pady=(15, 5))

            desc_frame = tk.Frame(inner, bg=COLORS['bg_card'])
            desc_frame.pack(fill=tk.X)
            tk.Label(desc_frame, text=self.ticket.get('description') or self.ticket.get('details', ''),
                    font=('Segoe UI', 10), bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                    wraplength=450, justify='left', padx=15, pady=10).pack(anchor='w')

        # Form fields if any
        if self.ticket.get('form_fields'):
            tk.Label(inner, text=_t("security_desk.tickets.request_details"), font=('Segoe UI', 10, 'bold'),
                    bg=COLORS['bg_panel'], fg=COLORS['text_secondary']).pack(anchor='w', pady=(15, 5))

            fields_frame = tk.Frame(inner, bg=COLORS['bg_card'])
            fields_frame.pack(fill=tk.X)
            for field, value in self.ticket['form_fields'].items():
                row = tk.Frame(fields_frame, bg=COLORS['bg_card'])
                row.pack(fill=tk.X, padx=15, pady=3)
                tk.Label(row, text=f"{field}:", font=('Segoe UI', 9, 'bold'),
                        bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(side=tk.LEFT)
                tk.Label(row, text=value, font=('Segoe UI', 9),
                        bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(side=tk.LEFT, padx=(5, 0))

        # Notes/History
        if self.ticket.get('notes'):
            tk.Label(inner, text=_t("security_desk.tickets.notes_updates"), font=('Segoe UI', 10, 'bold'),
                    bg=COLORS['bg_panel'], fg=COLORS['text_secondary']).pack(anchor='w', pady=(20, 5))

            for note in self.ticket['notes']:
                note_frame = tk.Frame(inner, bg=COLORS['bg_card'])
                note_frame.pack(fill=tk.X, pady=3)

                note_header = tk.Frame(note_frame, bg=COLORS['bg_card'])
                note_header.pack(fill=tk.X, padx=10, pady=(10, 0))
                tk.Label(note_header, text=note.get('author', 'System'),
                        font=('Segoe UI', 9, 'bold'), bg=COLORS['bg_card'],
                        fg=COLORS['accent_amber']).pack(side=tk.LEFT)
                tk.Label(note_header, text=note.get('timestamp', ''),
                        font=('Segoe UI', 8), bg=COLORS['bg_card'],
                        fg=COLORS['text_muted']).pack(side=tk.RIGHT)

                tk.Label(note_frame, text=note.get('text', ''), font=('Segoe UI', 10),
                        bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                        wraplength=450, justify='left', padx=10, pady=(5, 10)).pack(anchor='w')

        # Admin controls
        if self.is_admin:
            admin_frame = tk.Frame(inner, bg=COLORS['bg_card'])
            admin_frame.pack(fill=tk.X, pady=(20, 0), ipady=15)

            tk.Label(admin_frame, text=_t("security_desk.admin.actions"), font=('Segoe UI', 11, 'bold'),
                    bg=COLORS['bg_card'], fg=COLORS['accent_amber']).pack(anchor='w', padx=15, pady=(10, 10))

            # Status update
            status_row = tk.Frame(admin_frame, bg=COLORS['bg_card'])
            status_row.pack(fill=tk.X, padx=15, pady=5)

            tk.Label(status_row, text=_t("security_desk.admin.update_status"), font=('Segoe UI', 10),
                    bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(side=tk.LEFT)

            self.status_var = tk.StringVar(value=self.ticket.get('status', 'Open'))
            status_combo = ttk.Combobox(status_row, textvariable=self.status_var,
                                        values=["Open", "Under Review", "In Progress", "Resolved", "Closed"],
                                        state='readonly', width=15)
            status_combo.pack(side=tk.LEFT, padx=10)

            # Add note
            tk.Label(admin_frame, text=_t("security_desk.admin.add_note"), font=('Segoe UI', 10),
                    bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(anchor='w', padx=15, pady=(10, 5))

            self.note_text = scrolledtext.ScrolledText(admin_frame, height=3,
                                                       bg=COLORS['bg_input'], fg=COLORS['text_primary'],
                                                       insertbackground=COLORS['accent_amber'],
                                                       font=('Segoe UI', 10), relief='flat')
            self.note_text.pack(fill=tk.X, padx=15)

            # Email notification checkbox
            self.email_notify_var = tk.BooleanVar(value=True)
            tk.Checkbutton(admin_frame, text=_t("security_desk.admin.email_notify"),
                          variable=self.email_notify_var, bg=COLORS['bg_card'],
                          fg=COLORS['text_secondary'], selectcolor=COLORS['bg_input'],
                          activebackground=COLORS['bg_card'], font=('Segoe UI', 9)).pack(anchor='w', padx=15, pady=10)

            # Save button
            tk.Button(admin_frame, text=_t("security_desk.admin.save_changes"),
                     command=self.save_changes, bg=COLORS['success'], fg='white',
                     font=('Segoe UI', 11, 'bold'), relief='flat', padx=20, pady=8,
                     cursor='hand2').pack(anchor='e', padx=15, pady=(5, 15))

        # Close button
        tk.Button(inner, text=_t("security_desk.buttons.close"), command=self.destroy,
                 bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                 font=('Segoe UI', 11), relief='flat', padx=30, pady=8,
                 cursor='hand2').pack(anchor='e', pady=(20, 0))

    def add_detail_row(self, parent, label, value):
        row = tk.Frame(parent, bg=COLORS['bg_panel'])
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text=f"{label}:", font=('Segoe UI', 10, 'bold'),
                bg=COLORS['bg_panel'], fg=COLORS['text_secondary'], width=12, anchor='w').pack(side=tk.LEFT)
        tk.Label(row, text=value, font=('Segoe UI', 10),
                bg=COLORS['bg_panel'], fg=COLORS['text_primary']).pack(side=tk.LEFT)

    def save_changes(self):
        """Save admin changes and send notification."""
        new_status = self.status_var.get()
        note_text = self.note_text.get("1.0", tk.END).strip()

        # Update ticket
        old_status = self.ticket.get('status', 'Open')
        self.ticket['status'] = new_status

        if note_text:
            if 'notes' not in self.ticket:
                self.ticket['notes'] = []
            self.ticket['notes'].append({
                'author': self.current_user.get('name') or self.current_user.get('username', 'Admin'),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'text': note_text
            })
            # Also persist to admin_notes for DB storage
            existing_notes = self.ticket.get('admin_notes') or ''
            author = self.current_user.get('name') or self.current_user.get('username', 'Admin')
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_note = f"[{timestamp}] {author}: {note_text}"
            self.ticket['admin_notes'] = f"{existing_notes}\n{new_note}".strip()

        # Send email notification (use requester_email or user_email from DB)
        recipient_email = self.ticket.get('requester_email') or self.ticket.get('user_email')
        if self.email_notify_var.get() and recipient_email:
            # Use email template
            try:
                from education_system.systems.university.infrastructure.email.template_utils import render_template
                security_message = f"Message from Security:\n{note_text}\n\n" if note_text else ""
                security_message_html = f"<div style='background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;'><p style='margin: 0 0 10px 0; font-weight: bold;'>Message from Security:</p><p style='margin: 0;'>{note_text}</p></div>" if note_text else ""

                subject, body = render_template("security_ticket_status_update", {
                    "ticket_id": self.ticket['id'],
                    "ticket_type": self.ticket.get('type', 'N/A'),
                    "old_status": old_status,
                    "new_status": new_status,
                    "security_message": security_message,
                    "security_message_html": security_message_html
                })
                if not subject or not body:
                    raise ValueError("Template returned empty subject/body")
            except Exception:
                # Fallback to hardcoded email
                subject = f"Security Ticket {self.ticket['id']} - Status Update"
                body = f"""Your security ticket has been updated.

Ticket ID: {self.ticket['id']}
Type: {self.ticket.get('type', 'N/A')}
Status: {old_status} -> {new_status}

"""
                if note_text:
                    body += f"Message from Security:\n{note_text}\n\n"

                body += "If you have any questions, please reply to this email or contact the Security Desk."

            send_ticket_email(recipient_email, subject, body, self.ticket['id'])

        if self.on_update:
            self.on_update()

        messagebox.showinfo(_t("security_desk.messages.saved"),
                           _t("security_desk.messages.ticket_updated", id=self.ticket['id']))
        self.destroy()


class SecurityDesk:
    def __init__(self, root):
        self.root = root
        # When ``root`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), it has no ``wm_title`` — skip
        # window-chrome calls. Same shape as Library (8.117.34).
        if hasattr(self.root, "wm_title"):
            self.root.title(_t("security_desk.title"))
            self.root.geometry("1000x750")
            self.root.minsize(900, 650)
        try:
            self.root.configure(bg=COLORS['bg_dark'])
        except tk.TclError:
            pass

        # Get current user
        self.current_user = get_current_user()

        # Data storage
        self.tickets = []
        self.ticket_counter = 1000
        self.load_tickets()

        # Configure styles
        self.setup_styles()

        # Build the interface
        self.build_ui()

        # Center window
        self.center_window()

    def center_window(self):
        # ``geometry("+x+y")`` only applies to a Tk/Toplevel — skip
        # when embedded in a workspace Frame.
        if not hasattr(self.root, "wm_title"):
            return
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")

    def load_tickets(self):
        """Load tickets from database."""
        init_security_desk_database()
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                # Load tickets
                cursor = conn.execute("SELECT * FROM security_desk_tickets ORDER BY created_at DESC")
                self.tickets = [dict(row) for row in cursor.fetchall()]

                # Load counter
                cursor = conn.execute("SELECT counter FROM security_desk_counter WHERE id = 1")
                row = cursor.fetchone()
                self.ticket_counter = row['counter'] if row else 1000
        except Exception as e:
            logger.error(f"Failed to load tickets from database: {e}")
            self.tickets = []
            self.ticket_counter = 1000

    def save_tickets(self):
        """Save is handled immediately on each operation."""
        pass

    def _db_save_ticket(self, ticket):
        """Save a ticket to the database."""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO security_desk_tickets
                    (id, type, category, priority, status, subject, description, location,
                     user_id, user_name, user_email, admin_notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticket.get('id'), ticket.get('type'), ticket.get('category'),
                    ticket.get('priority', 'Normal'), ticket.get('status', 'Open'),
                    ticket.get('subject'), ticket.get('description'), ticket.get('location'),
                    ticket.get('user_id'), ticket.get('user_name'), ticket.get('user_email'),
                    ticket.get('admin_notes'), ticket.get('created_at'),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save ticket: {e}")
            return False

    def _db_delete_ticket(self, ticket_id):
        """Delete a ticket from the database."""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM security_desk_tickets WHERE id = ?", (ticket_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete ticket: {e}")
            return False

    def _db_get_next_ticket_id(self):
        """Get the next ticket ID and increment counter."""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT counter FROM security_desk_counter WHERE id = 1")
                row = cursor.fetchone()
                counter = row['counter'] if row else 1000
                new_counter = counter + 1
                conn.execute("UPDATE security_desk_counter SET counter = ? WHERE id = 1", (new_counter,))
                conn.commit()
                self.ticket_counter = new_counter
                return f"SEC-{counter}"
        except Exception as e:
            logger.error(f"Failed to get next ticket ID: {e}")
            self.ticket_counter += 1
            return f"SEC-{self.ticket_counter - 1}"

    def setup_styles(self):
        style = ttk.Style()

        style.configure('Dark.TFrame', background=COLORS['bg_dark'])
        style.configure('Panel.TFrame', background=COLORS['bg_panel'])
        style.configure('Card.TFrame', background=COLORS['bg_card'])

        style.configure('Title.TLabel', background=COLORS['bg_dark'],
                       foreground=COLORS['text_primary'], font=('Segoe UI', 24, 'bold'))
        style.configure('Subtitle.TLabel', background=COLORS['bg_dark'],
                       foreground=COLORS['text_secondary'], font=('Segoe UI', 11))
        style.configure('Header.TLabel', background=COLORS['bg_panel'],
                       foreground=COLORS['accent_amber'], font=('Segoe UI', 14, 'bold'))
        style.configure('CardTitle.TLabel', background=COLORS['bg_card'],
                       foreground=COLORS['text_primary'], font=('Segoe UI', 12, 'bold'))
        style.configure('CardText.TLabel', background=COLORS['bg_card'],
                       foreground=COLORS['text_secondary'], font=('Segoe UI', 10))
        style.configure('Status.TLabel', background=COLORS['bg_panel'],
                       foreground=COLORS['success'], font=('Segoe UI', 10, 'bold'))

        style.configure('Dark.TNotebook', background=COLORS['bg_dark'], borderwidth=0)
        style.configure('Dark.TNotebook.Tab', background=COLORS['bg_panel'],
                       foreground=COLORS['text_secondary'], padding=(20, 10), font=('Segoe UI', 10, 'bold'))
        style.map('Dark.TNotebook.Tab',
                 background=[('selected', COLORS['bg_card'])],
                 foreground=[('selected', COLORS['accent_amber'])])

    def build_ui(self):
        main_frame = ttk.Frame(self.root, style='Dark.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.build_header(main_frame)
        self.build_content(main_frame)
        self.build_status_bar(main_frame)

    def build_header(self, parent):
        header_frame = ttk.Frame(parent, style='Dark.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 20))

        # Left side - title
        title_frame = ttk.Frame(header_frame, style='Dark.TFrame')
        title_frame.pack(side=tk.LEFT)

        tk.Label(title_frame, text=_t("security_desk.title"), font=('Segoe UI', 24, 'bold'),
                bg=COLORS['bg_dark'], fg=COLORS['text_primary']).pack(anchor='w')

        # User info
        user_name = self.current_user.get('name') or self.current_user.get('username', 'Guest')
        user_role = self.current_user.get('role', 'guest').title()
        tk.Label(title_frame, text=_t("security_desk.welcome", user_name=user_name, role=user_role),
                font=('Segoe UI', 11), bg=COLORS['bg_dark'],
                fg=COLORS['text_secondary']).pack(anchor='w')

        # Right side buttons
        buttons_frame = ttk.Frame(header_frame, style='Dark.TFrame')
        buttons_frame.pack(side=tk.RIGHT)

        # Refresh button
        refresh_btn = tk.Button(buttons_frame, text=_t("security_desk.buttons.refresh"),
                               command=self.refresh_all_data, bg=COLORS['info'], fg='white',
                               font=('Segoe UI', 10, 'bold'), relief='flat', padx=15, pady=8,
                               cursor='hand2')
        refresh_btn.pack(side=tk.LEFT, padx=(0, 15))
        refresh_btn.bind('<Enter>', lambda e: e.widget.configure(bg='#7ab8ff'))
        refresh_btn.bind('<Leave>', lambda e: e.widget.configure(bg=COLORS['info']))

        # Emergency button
        emergency_btn = tk.Button(buttons_frame, text=_t("security_desk.buttons.emergency"),
                                 command=self.emergency_call, bg=COLORS['danger'], fg='white',
                                 font=('Segoe UI', 12, 'bold'), relief='flat', padx=25, pady=10,
                                 cursor='hand2')
        emergency_btn.pack(side=tk.LEFT)
        emergency_btn.bind('<Enter>', lambda e: e.widget.configure(bg='#ff6b6b'))
        emergency_btn.bind('<Leave>', lambda e: e.widget.configure(bg=COLORS['danger']))

    def build_content(self, parent):
        notebook = ttk.Notebook(parent, style='Dark.TNotebook')
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Request Help
        help_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(help_frame, text=_t("security_desk.tabs.request_help"))
        self.build_help_tab(help_frame)

        # Tab 2: Report Issue (with scrollbar)
        report_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(report_frame, text=_t("security_desk.tabs.report_issue"))
        self.build_report_tab(report_frame)

        # Tab 3: My Tickets
        tickets_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(tickets_frame, text=_t("security_desk.tabs.my_tickets"))
        self.build_tickets_tab(tickets_frame)

        # Tab 4: Quick Contacts
        contacts_frame = ttk.Frame(notebook, style='Panel.TFrame')
        notebook.add(contacts_frame, text=_t("security_desk.tabs.quick_contacts"))
        self.build_contacts_tab(contacts_frame)

        # Tab 5: Admin (if admin user)
        if self.current_user.get('role') == 'admin':
            admin_frame = ttk.Frame(notebook, style='Panel.TFrame')
            notebook.add(admin_frame, text=_t("security_desk.tabs.admin_panel"))
            self.build_admin_tab(admin_frame)

    def build_help_tab(self, parent):
        container = ttk.Frame(parent, style='Panel.TFrame')
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        ttk.Label(container, text=_t("security_desk.help.header"),
                 style='Header.TLabel').pack(anchor='w', pady=(0, 20))

        buttons_frame = ttk.Frame(container, style='Panel.TFrame')
        buttons_frame.pack(fill=tk.X, pady=(0, 30))

        help_options = [
            ("", _t("security_desk.help.access_issue"), _t("security_desk.help.access_issue_desc")),
            ("", _t("security_desk.help.parking_help"), _t("security_desk.help.parking_help_desc")),
            ("", _t("security_desk.help.lost_found"), _t("security_desk.help.lost_found_desc")),
            ("", _t("security_desk.help.visitor_badge"), _t("security_desk.help.visitor_badge_desc")),
            ("", _t("security_desk.help.key_request"), _t("security_desk.help.key_request_desc")),
            ("", _t("security_desk.help.facility_issue"), _t("security_desk.help.facility_issue_desc")),
        ]

        for i, (icon, title, desc) in enumerate(help_options):
            row = i // 3
            col = i % 3
            self.create_help_card(buttons_frame, icon, title, desc, row, col)

        # Custom request section
        custom_frame = ttk.Frame(container, style='Card.TFrame')
        custom_frame.pack(fill=tk.X, pady=(20, 0), ipady=15)

        tk.Label(custom_frame, text=_t("security_desk.help.other_request"), font=('Segoe UI', 12, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(anchor='w', padx=15, pady=(15, 10))

        self.custom_help_text = scrolledtext.ScrolledText(custom_frame, height=4,
                                                          bg=COLORS['bg_input'], fg=COLORS['text_primary'],
                                                          insertbackground=COLORS['accent_amber'],
                                                          font=('Segoe UI', 10), relief='flat', wrap=tk.WORD)
        self.custom_help_text.pack(fill=tk.X, padx=15, pady=(0, 10))

        tk.Button(custom_frame, text=_t("security_desk.form.submit_request"),
                 command=lambda: self.submit_custom_request(),
                 bg=COLORS['accent_amber'], fg=COLORS['bg_dark'],
                 font=('Segoe UI', 11, 'bold'), relief='flat', padx=20, pady=8,
                 cursor='hand2').pack(anchor='e', padx=15, pady=(0, 15))

    def create_help_card(self, parent, icon, title, desc, row, col):
        card = tk.Frame(parent, bg=COLORS['bg_card'], cursor='hand2')
        card.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
        parent.grid_columnconfigure(col, weight=1)

        inner = tk.Frame(card, bg=COLORS['bg_card'])
        inner.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        tk.Label(inner, text=title, font=('Segoe UI', 13, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(pady=(5, 5))

        tk.Label(inner, text=desc, font=('Segoe UI', 9),
                bg=COLORS['bg_card'], fg=COLORS['text_secondary'], wraplength=150).pack()

        # Bind click to open form dialog
        for widget in [card, inner] + inner.winfo_children():
            widget.bind('<Button-1>', lambda e, t=title, i=icon: self.open_help_form(t, i))
            widget.bind('<Enter>', lambda e, c=card: c.configure(bg=COLORS['border']))
            widget.bind('<Leave>', lambda e, c=card: c.configure(bg=COLORS['bg_card']))

    def open_help_form(self, help_type, icon):
        """Open the form dialog for a help request."""
        dialog = HelpFormDialog(self.root, help_type, icon, self.current_user)
        self.root.wait_window(dialog)

        if dialog.result:
            self.create_ticket_from_form(dialog.result)

    def create_ticket_from_form(self, form_data):
        """Create a ticket from form dialog data."""
        ticket_id = self._db_get_next_ticket_id()
        ticket = {
            'id': ticket_id,
            'type': form_data['help_type'],
            'status': 'Open',
            'created': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'priority': form_data['priority'],
            'details': form_data.get('details', ''),
            'description': form_data.get('details', ''),
            'subject': form_data['help_type'],
            'category': form_data['help_type'],
            'user_id': self.current_user.get('id'),
            'user_name': self.current_user.get('name') or self.current_user.get('username', 'Unknown'),
            'user_email': self.current_user.get('email', ''),
            'requester_id': self.current_user.get('id'),
            'requester_name': self.current_user.get('name') or self.current_user.get('username', 'Unknown'),
            'requester_email': self.current_user.get('email', ''),
            'notes': []
        }
        if self._db_save_ticket(ticket):
            self.tickets.append(ticket)

        # Send email to admins
        admin_emails = get_admin_emails()
        for email in admin_emails:
            # Use email template
            try:
                from education_system.systems.university.infrastructure.email.template_utils import render_template
                subject, body = render_template("security_ticket_new", {
                    "ticket_id": ticket['id'],
                    "ticket_type": ticket['type'],
                    "priority": ticket['priority'],
                    "requester_name": ticket.get('requester_name') or ticket.get('user_name', 'Unknown'),
                    "created_at": ticket.get('created') or ticket.get('created_at', 'Unknown'),
                    "details": ticket.get('details', 'No additional details')
                })
            except Exception:
                # Fallback to hardcoded email
                subject = f"New Security Ticket: {ticket['id']} - {ticket['type']}"
                body = f"""A new security request has been submitted.

Ticket ID: {ticket['id']}
Type: {ticket['type']}
Priority: {ticket['priority']}
Requester: {ticket.get('requester_name') or ticket.get('user_name', 'Unknown')}
Created: {ticket.get('created') or ticket.get('created_at', 'Unknown')}

Details: {ticket.get('details', 'No additional details')}

Please log in to the Security Desk to review and respond to this ticket."""

            send_ticket_email(email, subject, body, ticket['id'])

        messagebox.showinfo(_t("security_desk.messages.request_submitted"),
                           f"{_t('security_desk.messages.request_submitted')}\n\n"
                           f"{_t('security_desk.messages.ticket_id', id=ticket['id'])}\n"
                           f"{_t('security_desk.messages.ticket_type', type=ticket['type'])}\n\n"
                           f"{_t('security_desk.messages.assist_shortly')}")

        self.refresh_tickets()

    def submit_custom_request(self):
        """Submit a custom help request."""
        details = self.custom_help_text.get("1.0", tk.END).strip()
        if not details:
            messagebox.showwarning(_t("security_desk.messages.missing_description").split(".")[0],
                                  _t("security_desk.messages.missing_description"))
            return

        ticket_id = self._db_get_next_ticket_id()
        ticket = {
            'id': ticket_id,
            'type': 'Custom Request',
            'status': 'Open',
            'created': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'priority': 'Medium',
            'details': details,
            'description': details,
            'subject': 'Custom Request',
            'category': 'Custom Request',
            'user_id': self.current_user.get('id'),
            'user_name': self.current_user.get('name') or self.current_user.get('username', 'Unknown'),
            'user_email': self.current_user.get('email', ''),
            'requester_id': self.current_user.get('id'),
            'requester_name': self.current_user.get('name') or self.current_user.get('username', 'Unknown'),
            'requester_email': self.current_user.get('email', ''),
            'notes': []
        }
        if self._db_save_ticket(ticket):
            self.tickets.append(ticket)
        self.custom_help_text.delete("1.0", tk.END)

        # Notify admins
        for email in get_admin_emails():
            send_ticket_email(email,
                            f"New Security Ticket: {ticket['id']}",
                            f"New custom request from {ticket.get('requester_name') or ticket.get('user_name', 'Unknown')}:\n\n{details}",
                            ticket['id'])

        messagebox.showinfo(_t("security_desk.messages.request_submitted"),
                           f"{_t('security_desk.messages.request_submitted')}\n\n{_t('security_desk.messages.ticket_id', id=ticket['id'])}")
        self.refresh_tickets()

    def build_report_tab(self, parent):
        # Create scrollable container
        canvas = tk.Canvas(parent, bg=COLORS['bg_panel'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS['bg_panel'])

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def configure_width(event):
            canvas.itemconfig(canvas_window, width=event.width)

        scrollable_frame.bind("<Configure>", configure_scroll)
        canvas.bind("<Configure>", configure_width)

        # Mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Content
        container = tk.Frame(scrollable_frame, bg=COLORS['bg_panel'], padx=30, pady=30)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(container, text=_t("security_desk.report.header"), font=('Segoe UI', 14, 'bold'),
                bg=COLORS['bg_panel'], fg=COLORS['accent_amber']).pack(anchor='w', pady=(0, 20))

        form_frame = tk.Frame(container, bg=COLORS['bg_card'])
        form_frame.pack(fill=tk.BOTH, expand=True, ipadx=20, ipady=20)

        # Issue Type
        self.create_form_field(form_frame, _t("security_desk.report.issue_type"), "combo",
                              values=[_t("security_desk.report.suspicious_activity"),
                                     _t("security_desk.report.safety_hazard"),
                                     _t("security_desk.report.theft_loss"),
                                     _t("security_desk.report.vandalism"),
                                     _t("security_desk.report.harassment"),
                                     _t("security_desk.report.unauthorized_access"),
                                     _t("security_desk.report.noise_complaint"),
                                     _t("security_desk.report.fire_safety"),
                                     _t("security_desk.report.medical_emergency"),
                                     _t("security_desk.report.structural_damage"),
                                     _t("security_desk.report.water_leak"),
                                     _t("security_desk.report.gas_smell"),
                                     _t("security_desk.form.issue_other")])

        # Location
        self.create_form_field(form_frame, _t("security_desk.report.location"), "entry",
                              placeholder=_t("security_desk.report.location_placeholder"))

        # Date/Time of Incident
        self.create_form_field(form_frame, _t("security_desk.report.when_occurred"), "combo",
                              values=[_t("security_desk.report.time_just_now"),
                                     _t("security_desk.report.time_last_hour"),
                                     _t("security_desk.report.time_today"),
                                     _t("security_desk.report.time_yesterday"),
                                     _t("security_desk.report.time_this_week"),
                                     _t("security_desk.report.time_earlier")])

        # People Involved
        self.create_form_field(form_frame, _t("security_desk.report.people_involved"), "entry",
                              placeholder=_t("security_desk.report.people_placeholder"))

        # Priority
        self.create_form_field(form_frame, _t("security_desk.form.priority"), "combo",
                              values=[_t("security_desk.form.priority_low"),
                                     _t("security_desk.form.priority_medium"),
                                     _t("security_desk.form.priority_high"),
                                     _t("security_desk.form.priority_critical")])

        # Description
        tk.Label(form_frame, text=_t("security_desk.report.detailed_description"), font=('Segoe UI', 10, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(anchor='w', padx=20, pady=(15, 5))

        self.report_desc = scrolledtext.ScrolledText(form_frame, height=6,
                                                     bg=COLORS['bg_input'], fg=COLORS['text_primary'],
                                                     insertbackground=COLORS['accent_amber'],
                                                     font=('Segoe UI', 10), relief='flat', wrap=tk.WORD)
        self.report_desc.pack(fill=tk.X, padx=20)

        # Witness Info
        self.create_form_field(form_frame, _t("security_desk.report.witness_contact"), "entry",
                              placeholder=_t("security_desk.report.witness_placeholder"))

        # Anonymous option
        self.anonymous_var = tk.BooleanVar()
        tk.Checkbutton(form_frame, text=_t("security_desk.report.anonymous"),
                      variable=self.anonymous_var, bg=COLORS['bg_card'],
                      fg=COLORS['text_secondary'], selectcolor=COLORS['bg_input'],
                      activebackground=COLORS['bg_card'], font=('Segoe UI', 10)).pack(anchor='w', padx=20, pady=(15, 5))

        # Attachment note
        tk.Label(form_frame, text=_t("security_desk.report.attachment_note"),
                font=('Segoe UI', 9), bg=COLORS['bg_card'],
                fg=COLORS['text_muted']).pack(anchor='w', padx=20, pady=(10, 0))

        # Submit button
        tk.Button(form_frame, text=_t("security_desk.report.submit_report"), command=self.submit_report,
                 bg=COLORS['accent_amber'], fg=COLORS['bg_dark'],
                 font=('Segoe UI', 12, 'bold'), relief='flat', padx=30, pady=10,
                 cursor='hand2').pack(anchor='e', padx=20, pady=20)

    def create_form_field(self, parent, label, field_type, values=None, placeholder=None):
        tk.Label(parent, text=label, font=('Segoe UI', 10, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(anchor='w', padx=20, pady=(15, 5))

        if field_type == "combo":
            combo = ttk.Combobox(parent, values=values, state='readonly', font=('Segoe UI', 10))
            combo.pack(fill=tk.X, padx=20)
            combo.set(values[0] if values else "")
            setattr(self, f"{label.lower().replace(' ', '_').replace('/', '_')}_combo", combo)
        else:
            entry = tk.Entry(parent, bg=COLORS['bg_input'], fg=COLORS['text_primary'],
                           insertbackground=COLORS['accent_amber'], font=('Segoe UI', 10), relief='flat')
            entry.pack(fill=tk.X, padx=20, ipady=8)
            if placeholder:
                entry.insert(0, placeholder)
                entry.configure(fg=COLORS['text_muted'])
                entry.bind('<FocusIn>', lambda e: self.clear_placeholder(e, placeholder))
                entry.bind('<FocusOut>', lambda e: self.restore_placeholder(e, placeholder))
            setattr(self, f"{label.lower().replace(' ', '_').replace('/', '_')}_entry", entry)

    def clear_placeholder(self, event, placeholder):
        if event.widget.get() == placeholder:
            event.widget.delete(0, tk.END)
            event.widget.configure(fg=COLORS['text_primary'])

    def restore_placeholder(self, event, placeholder):
        if not event.widget.get():
            event.widget.insert(0, placeholder)
            event.widget.configure(fg=COLORS['text_muted'])

    def submit_report(self):
        issue_type = self.issue_type_combo.get()
        location = getattr(self, 'location_entry', None)
        location_val = location.get() if location else ""
        priority = self.priority_combo.get()
        description = self.report_desc.get("1.0", tk.END).strip()

        if not description:
            messagebox.showwarning(_t("security_desk.messages.missing_report_description").split(".")[0],
                                  _t("security_desk.messages.missing_report_description"))
            return

        ticket_id = self._db_get_next_ticket_id()
        is_anon = self.anonymous_var.get()
        ticket = {
            'id': ticket_id,
            'type': f"Report: {issue_type}",
            'status': 'Under Review',
            'created': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'priority': priority,
            'location': location_val if location_val and "Building" not in location_val else "",
            'description': description,
            'subject': f"Report: {issue_type}",
            'category': issue_type,
            'anonymous': is_anon,
            'user_id': None if is_anon else self.current_user.get('id'),
            'user_name': 'Anonymous' if is_anon else (
                self.current_user.get('name') or self.current_user.get('username', 'Unknown')),
            'user_email': '' if is_anon else self.current_user.get('email', ''),
            'requester_id': None if is_anon else self.current_user.get('id'),
            'requester_name': 'Anonymous' if is_anon else (
                self.current_user.get('name') or self.current_user.get('username', 'Unknown')),
            'requester_email': '' if is_anon else self.current_user.get('email', ''),
            'notes': []
        }
        if self._db_save_ticket(ticket):
            self.tickets.append(ticket)

        # Clear form
        self.report_desc.delete("1.0", tk.END)
        if location:
            location.delete(0, tk.END)
        self.anonymous_var.set(False)

        # Notify admins
        for email in get_admin_emails():
            send_ticket_email(email,
                            f"Security Report: {ticket['id']} - {issue_type} [{priority}]",
                            f"A new security report has been filed.\n\n"
                            f"Type: {issue_type}\nPriority: {priority}\nLocation: {location_val}\n\n"
                            f"Description:\n{description}",
                            ticket['id'])

        messagebox.showinfo(_t("security_desk.messages.report_submitted"),
                           f"{_t('security_desk.messages.report_submitted')}\n\n"
                           f"{_t('security_desk.messages.ticket_id', id=ticket['id'])}\n"
                           f"{_t('security_desk.messages.ticket_priority', priority=priority)}\n\n"
                           f"{_t('security_desk.messages.thank_you_safe')}")
        self.refresh_tickets()

    def build_tickets_tab(self, parent):
        container = ttk.Frame(parent, style='Panel.TFrame')
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        header = ttk.Frame(container, style='Panel.TFrame')
        header.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header, text=_t("security_desk.tickets.header"), style='Header.TLabel').pack(side=tk.LEFT)

        tk.Button(header, text=_t("security_desk.buttons.refresh"), command=self.refresh_tickets,
                 bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                 font=('Segoe UI', 10), relief='flat', padx=15, pady=5,
                 cursor='hand2').pack(side=tk.RIGHT)

        # Scrollable tickets list
        canvas = tk.Canvas(container, bg=COLORS['bg_panel'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)

        self.tickets_container = tk.Frame(canvas, bg=COLORS['bg_panel'])

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tickets_canvas = canvas
        self.tickets_canvas_window = canvas.create_window((0, 0), window=self.tickets_container, anchor="nw")

        self.tickets_container.bind("<Configure>",
                                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                   lambda e: canvas.itemconfig(self.tickets_canvas_window, width=e.width))

        self.refresh_tickets()

    def refresh_tickets(self):
        """Refresh the tickets display."""
        for widget in self.tickets_container.winfo_children():
            widget.destroy()

        # Filter tickets for current user (or all if admin)
        user_id = self.current_user.get('id')
        is_admin = self.current_user.get('role') == 'admin'

        if is_admin:
            user_tickets = self.tickets
        else:
            user_tickets = [t for t in self.tickets if t.get('requester_id') == user_id or
                           (user_id is None and t.get('requester_name') == self.current_user.get('username'))]

        if not user_tickets:
            tk.Label(self.tickets_container, text=_t("security_desk.tickets.no_tickets"),
                    font=('Segoe UI', 11), bg=COLORS['bg_panel'],
                    fg=COLORS['text_muted']).pack(pady=50)
        else:
            for ticket in reversed(user_tickets):
                self.create_ticket_card(ticket)

        # Update admin stats if admin
        self.update_admin_stats()

    def create_ticket_card(self, ticket):
        card = tk.Frame(self.tickets_container, bg=COLORS['bg_card'], cursor='hand2')
        card.pack(fill=tk.X, pady=5)

        inner = tk.Frame(card, bg=COLORS['bg_card'])
        inner.pack(fill=tk.X, padx=20, pady=15)

        # Left side - ticket info
        left = tk.Frame(inner, bg=COLORS['bg_card'])
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        header = tk.Frame(left, bg=COLORS['bg_card'])
        header.pack(fill=tk.X)

        tk.Label(header, text=ticket['id'], font=('Consolas', 11, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['accent_amber']).pack(side=tk.LEFT)

        priority_colors = {'Low': COLORS['text_muted'], 'Medium': COLORS['warning'],
                          'High': COLORS['accent_amber'], 'Critical': COLORS['danger']}
        priority_color = priority_colors.get(ticket.get('priority', 'Medium'), COLORS['text_muted'])

        tk.Label(header, text=f" [{ticket.get('priority', 'Medium')}]", font=('Segoe UI', 9),
                bg=COLORS['bg_card'], fg=priority_color).pack(side=tk.LEFT)

        tk.Label(left, text=ticket['type'], font=('Segoe UI', 11),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(anchor='w')

        tk.Label(left, text=f"Created: {ticket.get('created') or ticket.get('created_at', 'Unknown')}", font=('Segoe UI', 9),
                bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(anchor='w')

        # Right side - status
        status_colors = {'Open': COLORS['info'], 'Under Review': COLORS['warning'],
                        'In Progress': COLORS['accent_amber'], 'Resolved': COLORS['success'],
                        'Closed': COLORS['text_muted']}
        status_color = status_colors.get(ticket.get('status', 'Open'), COLORS['text_muted'])

        tk.Label(inner, text=f"  {ticket.get('status', 'Open')}",
                font=('Segoe UI', 10, 'bold'), bg=COLORS['bg_card'],
                fg=status_color).pack(side=tk.RIGHT)

        # Bind click to open details
        for widget in [card, inner, left, header] + left.winfo_children() + header.winfo_children():
            widget.bind('<Button-1>', lambda e, t=ticket: self.show_ticket_details(t))

    def show_ticket_details(self, ticket):
        """Show ticket details dialog."""
        def on_update():
            self._db_save_ticket(ticket)
            self.refresh_tickets()
        TicketDetailsDialog(self.root, ticket, self.current_user, on_update=on_update)

    def build_contacts_tab(self, parent):
        container = ttk.Frame(parent, style='Panel.TFrame')
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        ttk.Label(container, text=_t("security_desk.contacts.header"), style='Header.TLabel').pack(anchor='w', pady=(0, 20))

        contacts = [
            (_t("security_desk.contacts.security_control"), _t("security_desk.contacts.security_desc"), "555-0100", COLORS['accent_amber']),
            (_t("security_desk.contacts.emergency"), _t("security_desk.contacts.emergency_desc"), "911", COLORS['danger']),
            (_t("security_desk.contacts.medical"), _t("security_desk.contacts.medical_desc"), "555-0120", COLORS['success']),
            (_t("security_desk.contacts.facilities"), _t("security_desk.contacts.facilities_desc"), "555-0130", COLORS['info']),
            (_t("security_desk.contacts.hr"), _t("security_desk.contacts.hr_desc"), "555-0140", COLORS['warning']),
            (_t("security_desk.contacts.it"), _t("security_desk.contacts.it_desc"), "555-0150", COLORS['info']),
        ]

        for name, desc, phone, color in contacts:
            self.create_contact_card(container, name, desc, phone, color)

    def create_contact_card(self, parent, name, desc, phone, accent_color):
        card = tk.Frame(parent, bg=COLORS['bg_card'])
        card.pack(fill=tk.X, pady=5)

        inner = tk.Frame(card, bg=COLORS['bg_card'])
        inner.pack(fill=tk.X, padx=20, pady=15)

        info_frame = tk.Frame(inner, bg=COLORS['bg_card'])
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(info_frame, text=name, font=('Segoe UI', 12, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(anchor='w')
        tk.Label(info_frame, text=desc, font=('Segoe UI', 10),
                bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(anchor='w')

        tk.Button(inner, text=_t("security_desk.contacts.call", number=phone), command=lambda p=phone: self.dial_number(p),
                 bg=accent_color, fg='white' if accent_color != COLORS['warning'] else COLORS['bg_dark'],
                 font=('Segoe UI', 10, 'bold'), relief='flat', padx=15, pady=8,
                 cursor='hand2').pack(side=tk.RIGHT)

    def build_admin_tab(self, parent):
        """Build admin panel for managing all tickets."""
        container = ttk.Frame(parent, style='Panel.TFrame')
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        header = tk.Frame(container, bg=COLORS['bg_panel'])
        header.pack(fill=tk.X, pady=(0, 20))

        tk.Label(header, text=_t("security_desk.admin.header"), font=('Segoe UI', 14, 'bold'),
                bg=COLORS['bg_panel'], fg=COLORS['accent_amber']).pack(side=tk.LEFT)

        # Stats label (stored for updates)
        self.admin_stats_label = tk.Label(header, text="", font=('Segoe UI', 11),
                                          bg=COLORS['bg_panel'], fg=COLORS['warning'])
        self.admin_stats_label.pack(side=tk.RIGHT)

        # Filter
        filter_frame = tk.Frame(container, bg=COLORS['bg_panel'])
        filter_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(filter_frame, text=_t("security_desk.admin.filter"), font=('Segoe UI', 10),
                bg=COLORS['bg_panel'], fg=COLORS['text_secondary']).pack(side=tk.LEFT)

        self.admin_filter_var = tk.StringVar(value=_t("security_desk.admin.filter_all"))
        filter_options = [
            (_t("security_desk.admin.filter_all"), "All"),
            (_t("security_desk.ticket_details.status_open"), "Open"),
            (_t("security_desk.ticket_details.status_under_review"), "Under Review"),
            (_t("security_desk.ticket_details.status_in_progress"), "In Progress"),
            (_t("security_desk.ticket_details.status_resolved"), "Resolved")
        ]
        for label, status in filter_options:
            tk.Radiobutton(filter_frame, text=label, variable=self.admin_filter_var,
                          value=status, command=self.refresh_admin_tickets,
                          bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                          selectcolor=COLORS['bg_input'], activebackground=COLORS['bg_panel'],
                          font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

        tk.Label(container, text=_t("security_desk.tickets.click_to_view"),
                font=('Segoe UI', 10), bg=COLORS['bg_panel'],
                fg=COLORS['text_muted']).pack(anchor='w', pady=(0, 10))

        # Scrollable tickets list for admin
        canvas = tk.Canvas(container, bg=COLORS['bg_panel'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)

        self.admin_tickets_container = tk.Frame(canvas, bg=COLORS['bg_panel'])

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.admin_tickets_canvas = canvas
        self.admin_tickets_canvas_window = canvas.create_window((0, 0), window=self.admin_tickets_container, anchor="nw")

        self.admin_tickets_container.bind("<Configure>",
                                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                   lambda e: canvas.itemconfig(self.admin_tickets_canvas_window, width=e.width))

        # Update stats and tickets initially
        self.update_admin_stats()
        self.refresh_admin_tickets()

    def refresh_admin_tickets(self):
        """Refresh the admin tickets display."""
        for widget in self.admin_tickets_container.winfo_children():
            widget.destroy()

        # Filter based on selected status
        filter_status = self.admin_filter_var.get() if hasattr(self, 'admin_filter_var') else "All"

        if filter_status == "All":
            filtered_tickets = self.tickets
        else:
            filtered_tickets = [t for t in self.tickets if t.get('status') == filter_status]

        if not filtered_tickets:
            tk.Label(self.admin_tickets_container, text=_t("security_desk.tickets.no_tickets_filter"),
                    font=('Segoe UI', 11), bg=COLORS['bg_panel'],
                    fg=COLORS['text_muted']).pack(pady=50)
        else:
            for ticket in reversed(filtered_tickets):
                self.create_admin_ticket_card(ticket)

        # Update stats
        self.update_admin_stats()

    def create_admin_ticket_card(self, ticket):
        """Create a ticket card for the admin panel."""
        card = tk.Frame(self.admin_tickets_container, bg=COLORS['bg_card'], cursor='hand2')
        card.pack(fill=tk.X, pady=5)

        inner = tk.Frame(card, bg=COLORS['bg_card'])
        inner.pack(fill=tk.X, padx=20, pady=15)

        # Left side - ticket info
        left = tk.Frame(inner, bg=COLORS['bg_card'])
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        header = tk.Frame(left, bg=COLORS['bg_card'])
        header.pack(fill=tk.X)

        tk.Label(header, text=ticket['id'], font=('Consolas', 11, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['accent_amber']).pack(side=tk.LEFT)

        priority_colors = {'Low': COLORS['text_muted'], 'Medium': COLORS['warning'],
                          'High': COLORS['accent_amber'], 'Critical': COLORS['danger']}
        priority_color = priority_colors.get(ticket.get('priority', 'Medium'), COLORS['text_muted'])

        tk.Label(header, text=f" [{ticket.get('priority', 'Medium')}]", font=('Segoe UI', 9),
                bg=COLORS['bg_card'], fg=priority_color).pack(side=tk.LEFT)

        # Requester name for admin view
        tk.Label(header, text=f"  - {ticket.get('requester_name', 'Unknown')}", font=('Segoe UI', 9),
                bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(side=tk.LEFT)

        tk.Label(left, text=ticket['type'], font=('Segoe UI', 11),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(anchor='w')

        tk.Label(left, text=f"Created: {ticket.get('created') or ticket.get('created_at', 'Unknown')}", font=('Segoe UI', 9),
                bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(anchor='w')

        # Right side - status
        status_colors = {'Open': COLORS['info'], 'Under Review': COLORS['warning'],
                        'In Progress': COLORS['accent_amber'], 'Resolved': COLORS['success'],
                        'Closed': COLORS['text_muted']}
        status_color = status_colors.get(ticket.get('status', 'Open'), COLORS['text_muted'])

        tk.Label(inner, text=f"  {ticket.get('status', 'Open')}",
                font=('Segoe UI', 10, 'bold'), bg=COLORS['bg_card'],
                fg=status_color).pack(side=tk.RIGHT)

        # Bind click to open details
        for widget in [card, inner, left, header] + left.winfo_children() + header.winfo_children():
            widget.bind('<Button-1>', lambda e, t=ticket: self.show_ticket_details(t))

    def update_admin_stats(self):
        """Update the admin panel statistics."""
        if hasattr(self, 'admin_stats_label'):
            open_count = len([t for t in self.tickets if t.get('status') in ['Open', 'Under Review']])
            in_progress = len([t for t in self.tickets if t.get('status') == 'In Progress'])
            total = len(self.tickets)
            stats_text = f"{_t('security_desk.admin.stats_open', count=open_count)} | {_t('security_desk.admin.stats_in_progress', count=in_progress)} | {_t('security_desk.admin.stats_total', count=total)}"
            self.admin_stats_label.config(text=stats_text)

    def build_status_bar(self, parent):
        status_frame = ttk.Frame(parent, style='Dark.TFrame')
        status_frame.pack(fill=tk.X, pady=(20, 0))

        tk.Label(status_frame, text="*", font=('Segoe UI', 12),
                bg=COLORS['bg_dark'], fg=COLORS['success']).pack(side=tk.LEFT)

        ttk.Label(status_frame, text=_t("security_desk.system_online"),
                 style='Status.TLabel').pack(side=tk.LEFT, padx=(5, 0))

        self.time_label = ttk.Label(status_frame, text="", style='Subtitle.TLabel')
        self.time_label.pack(side=tk.RIGHT)
        self.update_time()

    def update_time(self):
        current_time = datetime.now().strftime("%A, %B %d, %Y  |  %I:%M:%S %p")
        self.time_label.configure(text=current_time)
        self.root.after(1000, self.update_time)

    def dial_number(self, number):
        messagebox.showinfo(_t("security_desk.messages.dialing"),
                           f"{_t('security_desk.messages.calling', number=number)}\n\n{_t('security_desk.messages.call_note')}")

    def refresh_all_data(self):
        """Refresh all data from storage and update current user."""
        # Reload current user
        self.current_user = get_current_user()

        # Reload tickets from file
        self.load_tickets()

        # Refresh the tickets display
        self.refresh_tickets()

        # Refresh admin tickets if admin
        if hasattr(self, 'admin_tickets_container'):
            self.refresh_admin_tickets()

        # Show confirmation
        messagebox.showinfo(_t("security_desk.buttons.refresh"), _t("security_desk.messages.refreshed"))

    def emergency_call(self):
        result = messagebox.askyesno(_t("security_desk.emergency.confirmation_title"),
                                    _t("security_desk.emergency.confirmation_message"), icon='warning')
        if result:
            # Log emergency
            ticket_id = self._db_get_next_ticket_id().replace("SEC-", "EMG-")
            ticket = {
                'id': ticket_id,
                'type': _t("security_desk.emergency.alert_type"),
                'status': 'In Progress',
                'created': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'priority': 'Critical',
                'subject': _t("security_desk.emergency.alert_type"),
                'category': 'Emergency',
                'description': _t("security_desk.emergency.alert_triggered"),
                'user_id': self.current_user.get('id'),
                'user_name': self.current_user.get('name') or self.current_user.get('username', 'Unknown'),
                'user_email': self.current_user.get('email', ''),
                'requester_id': self.current_user.get('id'),
                'requester_name': self.current_user.get('name') or self.current_user.get('username', 'Unknown'),
                'requester_email': self.current_user.get('email', ''),
                'notes': [{'author': 'System', 'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
                          'text': _t("security_desk.emergency.alert_triggered")}]
            }
            if self._db_save_ticket(ticket):
                self.tickets.append(ticket)

            # Notify all admins
            for email in get_admin_emails():
                send_ticket_email(email,
                                f"EMERGENCY ALERT - {ticket['id']}",
                                f"EMERGENCY ALERT TRIGGERED\n\n"
                                f"User: {ticket.get('requester_name') or ticket.get('user_name', 'Unknown')}\n"
                                f"Time: {ticket.get('created') or ticket.get('created_at', 'Unknown')}\n\n"
                                f"Immediate response required!",
                                ticket['id'])

            messagebox.showinfo(_t("security_desk.emergency.alert_type"),
                              f"{_t('security_desk.emergency.alert_sent')}\n\n"
                              f"{_t('security_desk.emergency.team_notified')}\n"
                              f"{_t('security_desk.emergency.help_coming')}\n\n"
                              f"{_t('security_desk.emergency.stay_calm')}")
            self.refresh_tickets()


def main():
    root = tk.Tk()
    app = SecurityDesk(root)
    root.mainloop()


if __name__ == "__main__":
    main()
