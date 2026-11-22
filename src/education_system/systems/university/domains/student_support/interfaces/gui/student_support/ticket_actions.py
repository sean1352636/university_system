
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

from ._dialogs import make_toplevel, messagebox, simpledialog, filedialog
from . import common as _c
import tkinter.font as tkFont
from datetime import datetime, timedelta
import json
import os
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from education_system.systems.university.infrastructure.database.db import sqlite3
from pathlib import Path
import logging
from education_system import paths

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import activity logger for audit trail
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import email service for notifications
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    from education_system.systems.university.infrastructure.email.templates import load_template, render_template
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    send_email = lambda *args, **kwargs: False
    load_template = lambda *args, **kwargs: None
    render_template = lambda *args, **kwargs: (None, None)

# Use centralized path configuration
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH


# Import all functionality from student_support module (it's a single monolithic file)
try:
    # Import everything from the single student_support module
    from education_system.systems.university.domains.student_support.domain.student_support import (
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
        from education_system.systems.university.domains.student_support.domain.student_support import (
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

    def assign_ticket_to_me(self, ticket_id, window=None):
        """Take the ticket: from the queue when nobody has it
        (``caseload.take``), else ``service.assign`` to the signed-in user."""
        if not self.is_staff():
            messagebox.showwarning(_t('gui.pastoral.student_support.ticket_actions.dialogs.permission_denied', default="Permission Denied"), _t('gui.pastoral.student_support.ticket_actions.dialogs.only_staff_members_can_self_assign_tickets', default="Only staff members can self-assign tickets."))
            return
        try:
            ticket = _c.ss('service').get_ticket(_c.actor(self), ticket_id)
        except (PermissionError, ValueError) as exc:
            messagebox.showwarning(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), str(exc))
            return
        if ticket.get('assigned_to') == _c.username(self):
            messagebox.showinfo(_t('gui.pastoral.student_support.ticket_actions.dialogs.information', default="Information"), _t('gui.pastoral.student_support.ticket_actions.dialogs.you_are_already_assigned_to_this_ticket', default="You are already assigned to this ticket."))
            return
        if not ticket.get('assigned_to'):
            result = _c.run(window, _c.ss('caseload').take, _c.actor(self), ticket_id)
        else:
            result = _c.run(window, _c.ss('service').assign, _c.actor(self), ticket_id, _c.username(self))
        if result is None:
            return
        messagebox.showinfo(_t('gui.pastoral.student_support.ticket_actions.dialogs.success', default="Success"), f"Ticket #{ticket_id} assigned to you.")
        if window is not None:
            self._reopen_ticket(ticket_id, window)
        self.refresh_data()

    def show_add_response_dialog(self, ticket):
        """Reply to a ticket (``service.post_response``). The internal-note
        option is there only for the staff working the ticket."""
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_actions.dialogs.invalid_ticket_data', default="Invalid ticket data"))
            return
        self._response_dialog(ticket)

    def _response_dialog(self, ticket, *, text='', template=None, internal_only=False):
        ticket_id = ticket.get('ticket_id')
        title = (f"Add Internal Note - Ticket #{ticket_id}" if internal_only
                 else f"💬 Add Response to Ticket #{ticket_id}")
        response_dialog = _c.dialog(self, title, 1000, 640, modal=True)
        btn_frame = ttk.Frame(response_dialog, padding=10)
        btn_frame.pack(side="bottom", fill="x")
        form_frame = ttk.Frame(response_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        heading = (_t('gui.pastoral.student_support.ticket_actions.labels.internal_note_staff_only', default="Internal Note (Staff Only)")
                   if internal_only else
                   (f"Using template: {template.get('name')}" if template else f"Adding response to: {ticket.get('subject') or ''}"))
        ttk.Label(form_frame, text=heading, style='Heading.TLabel').pack(anchor="w", pady=(0, 15))
        if not internal_only:
            ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.response', default="Response:")).pack(anchor="w")
        response_text = scrolledtext.ScrolledText(form_frame, height=12, wrap=tk.WORD)
        response_text.pack(fill="both", expand=True, pady=(5, 15))
        if text:
            response_text.insert(1.0, text)

        internal_var = tk.BooleanVar(value=internal_only)
        if not internal_only and _c.can_see_internal(self, ticket):
            ttk.Checkbutton(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.buttons.internal_note_staff_only_variant_2', default="🔒 Internal note (staff only)"),
                            variable=internal_var).pack(anchor="w")

        def submit_response():
            body = response_text.get(1.0, tk.END).strip()
            if not body:
                messagebox.showerror(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_actions.dialogs.response_cannot_be_empty', default="Response cannot be empty"), parent=response_dialog)
                return
            result = _c.run(response_dialog, _c.ss('service').post_response, _c.actor(self), ticket_id, body,
                            internal=bool(internal_var.get()),
                            template_id=(template or {}).get('template_id'))
            if result is None:
                return
            response_dialog.destroy()
            if result.get('crisis'):
                _c.show_crisis(self, result['crisis'])
            else:
                messagebox.showinfo(_t('gui.pastoral.student_support.ticket_actions.dialogs.success', default="Success"),
                                    _t('gui.pastoral.student_support.ticket_actions.dialogs.internal_note_added_successfully', default="Internal note added successfully!")
                                    if internal_var.get() else
                                    _t('gui.pastoral.student_support.ticket_actions.dialogs.response_added_successfully', default="Response added successfully!"))
            self._refresh_open_ticket(ticket_id)
            self.refresh_data()

        label = (_t('gui.pastoral.student_support.ticket_actions.buttons.add_note', default="Add Note") if internal_only
                 else _t('gui.pastoral.student_support.ticket_actions.buttons.add_response_variant_2', default="💬 Add Response"))
        ttk.Button(btn_frame, text=label, command=submit_response, style='Primary.TButton').pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_actions.buttons.cancel_variant_2', default="❌ Cancel"), command=response_dialog.destroy).pack(side="left")
        response_text.focus_set()

    def _refresh_open_ticket(self, ticket_id):
        """Reopen the ticket's detail window, if one is showing, so the new
        reply (and any crisis banner) appears."""
        for win in self.root.winfo_children():
            if isinstance(win, tk.Toplevel) and getattr(win, 'ticket_id', None) == ticket_id:
                self._reopen_ticket(ticket_id, win)
                return

    def show_add_response_dialog_by_id(self, ticket_id):
        """Show add response dialog by ticket ID"""
        ticket = _c.run(None, _c.ss('service').get_ticket, _c.actor(self), ticket_id)
        if ticket:
            self.show_add_response_dialog(ticket)

    def can_respond_to_ticket(self, ticket):
        """The requester (until the ticket is closed) and the staff working it."""
        if not isinstance(ticket, dict) or not _c.actor(self):
            return False
        if _c.can_work(self, ticket):
            return True
        return ticket.get('access') == 'owner' and str(ticket.get('status') or '') != 'closed'

    def escalate_ticket(self, ticket_id, window=None):
        """Escalate with a reason (``service.escalate``; the assignee is told)."""
        reason = simpledialog.askstring(
            _t('gui.pastoral.student_support.ticket_actions.dialogs.escalate', default="Escalate ticket"),
            _t('gui.pastoral.student_support.ticket_actions.dialogs.escalate_reason', default="Why is ticket #{ticket_id} being escalated?").format(ticket_id=ticket_id),
            **({'parent': window} if window else {}))
        if not reason or not reason.strip():
            return
        result = _c.run(window, _c.ss('service').escalate, _c.actor(self), ticket_id, reason.strip())
        if result is not None:
            messagebox.showinfo(_t('gui.pastoral.student_support.ticket_actions.dialogs.success', default="Success"), f"Ticket #{ticket_id} escalated successfully!")
            if window is not None:
                self._reopen_ticket(ticket_id, window)
            self.refresh_data()

    def show_merge_dialog(self, ticket):
        """Merge duplicates raised by the same person (``service.merge``)."""
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_actions.dialogs.invalid_ticket_data', default="Invalid ticket data"))
            return
        ticket_id = ticket.get('ticket_id')
        merge_dialog = _c.dialog(self, _t('gui.pastoral.student_support.ticket_actions.windows.merge_tickets', default="Merge Tickets"), 900, 640, modal=True)
        btn_frame = ttk.Frame(merge_dialog, padding=10)
        btn_frame.pack(side="bottom", fill="x")
        form_frame = ttk.Frame(merge_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        ttk.Label(form_frame, text=f"Merge into Ticket #{ticket_id}", style='Heading.TLabel').pack(pady=(0, 10))

        # The same requester's other tickets, to pick from.
        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.pick_duplicates', default="Tickets from the same requester (select the duplicates):")).pack(anchor="w")
        tree = _c.tree_with_scroll(form_frame, ('ID', 'Title', 'Status', 'Created'),
                                   widths={'ID': 60, 'Title': 420, 'Status': 130, 'Created': 140},
                                   height=8, selectmode='extended')
        requester = ticket.get('requester_username') or ticket.get('student_id')
        if requester and _c.is_case_worker(self):
            listing = _c.run(merge_dialog, _c.ss('service').list_tickets_for_requester,
                             _c.actor(self), requester, page=1, per_page=200) or {}
            for t in listing.get('tickets') or []:
                if t['ticket_id'] != ticket_id:
                    tree.insert('', 'end', values=(t['ticket_id'], t.get('subject') or '',
                                                   t.get('status_label') or '', str(t.get('created_at') or '')[:16]))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.merge_reason', default="Merge reason:")).pack(anchor="w", pady=(10, 0))
        reason_text = scrolledtext.ScrolledText(form_frame, height=4, wrap=tk.WORD)
        reason_text.pack(fill="x", pady=(5, 0))

        def perform_merge():
            ids = [int(tree.item(i, 'values')[0]) for i in tree.selection()]
            reason = reason_text.get(1.0, tk.END).strip()
            if not ids or not reason:
                messagebox.showerror(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_actions.dialogs.please_provide_secondary_ticket_ids_and_reason', default="Please select the tickets to merge and give a reason"), parent=merge_dialog)
                return
            merged = _c.run(merge_dialog, _c.ss('service').merge, _c.actor(self), ticket_id, ids, reason)
            if merged:
                messagebox.showinfo(_t('gui.pastoral.student_support.ticket_actions.dialogs.success', default="Success"), _t('gui.pastoral.student_support.ticket_actions.dialogs.tickets_merged_successfully', default="Tickets merged successfully!"))
                merge_dialog.destroy()
                self._refresh_open_ticket(ticket_id)
                self.refresh_data()

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_actions.buttons.merge_tickets', default="Merge Tickets"), command=perform_merge).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_actions.buttons.cancel', default="Cancel"), command=merge_dialog.destroy).pack(side="left")

    def export_ticket(self, ticket):
        """Save the ticket as the viewer sees it (``service.get_ticket``)."""
        if ticket is None or not isinstance(ticket, dict) or not ticket.get('ticket_id'):
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_actions.dialogs.invalid_ticket_data', default="Invalid ticket data"))
            return
        filename = filedialog.asksaveasfilename(
            title=_t('gui.pastoral.student_support.ticket_actions.dialogs.export_ticket', default="Export Ticket"),
            defaultextension=".json", initialfile=f"ticket_{ticket['ticket_id']}.json",
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt")])
        if not filename:
            return
        details = _c.run(None, _c.ss('service').get_ticket, _c.actor(self), ticket['ticket_id'])
        if not details:
            return
        try:
            with open(filename, 'w', encoding='utf-8', newline='') as f:
                if filename.lower().endswith('.json'):
                    json.dump(details, f, indent=2, default=str)
                else:
                    f.write(f"Ticket #{details.get('ticket_id')}\n" + "=" * 50 + "\n")
                    f.write(f"Title: {details.get('subject') or ''}\n")
                    f.write(f"Requester: {details.get('student_id') or details.get('requester_username') or ''}\n")
                    f.write(f"Status: {details.get('status_label') or ''}\n")
                    f.write(f"Priority: {details.get('priority') or ''}\n")
                    f.write(f"Category: {_c.category_label(details.get('category'))}\n")
                    f.write(f"Team: {_c.team_label(details.get('team'))}\n")
                    f.write(f"Confidentiality: {_c.tier_label(_c.tier_of(details))}\n")
                    f.write(f"Created: {details.get('created_at') or ''}\n")
                    f.write(f"\nDescription:\n{details.get('description') or ''}\n")
                    responses = details.get('responses') or []
                    if responses:
                        f.write("\nResponses:\n")
                        for r in responses:
                            flag = " [INTERNAL]" if r.get('is_internal') else ""
                            f.write(f"\n[{r.get('response_datetime') or ''}] "
                                    f"{r.get('responder_username') or r.get('responder_role') or ''}{flag}:\n")
                            f.write(f"{r.get('response_text') or ''}\n")
        except OSError as e:
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), f"Could not export ticket: {e}")
            return
        messagebox.showinfo(_t('gui.pastoral.student_support.ticket_actions.dialogs.success', default="Success"), f"Ticket exported to {filename}")

    def show_ticket_history(self, ticket_id):
        """The ticket's timeline as the viewer may see it (``ticket_history``)."""
        history = _c.run(None, _c.ss('service').ticket_history, _c.actor(self), ticket_id)
        if not history:
            return
        history_window = _c.dialog(self, f"Ticket #{ticket_id} History", 1100, 800)
        canvas, scrollbar, timeline_frame = self._create_scrollable_frame(history_window)
        title_frame = ttk.Frame(timeline_frame, padding="10")
        title_frame.pack(fill="x")
        ttk.Label(title_frame, text=f"Complete History for Ticket #{ticket_id}", style='Title.TLabel').pack()

        for event in history['timeline']:
            event_frame = ttk.LabelFrame(timeline_frame, padding="10")
            event_frame.pack(fill="x", padx=10, pady=5)
            data = event['data']
            if event['type'] == 'creation':
                event_frame.config(text=f"Created - {event['datetime']}")
                ttk.Label(event_frame, text=f"Title: {data.get('subject') or ''}").pack(anchor="w")
                ttk.Label(event_frame, text=f"Description: {str(data.get('description') or '')[:200]}", wraplength=1000).pack(anchor="w")
            elif event['type'] == 'response':
                tags = [t for t, on in (("INTERNAL", data.get('is_internal')), ("AUTO", data.get('is_auto_generated'))) if on]
                who = data.get('responder_username') or data.get('responder_role') or ''
                event_frame.config(text=f"Response by {who}{' [' + ', '.join(tags) + ']' if tags else ''} - {event['datetime']}")
                ttk.Label(event_frame, text=str(data.get('response_text') or '')[:300], wraplength=1000).pack(anchor="w")
            elif event['type'] == 'attachment':
                event_frame.config(text=f"Attachment Added - {event['datetime']}")
                ttk.Label(event_frame, text=f"File: {data.get('original_filename') or ''}").pack(anchor="w")
            elif event['type'] == 'audit':
                event_frame.config(text=f"System Event - {event['datetime']}")
                ttk.Label(event_frame, text=f"Action: {data.get('action') or ''} by {data.get('user_id') or data.get('username') or ''}").pack(anchor="w")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def show_add_internal_note_dialog(self, ticket):
        """An internal note — for the staff working the ticket only."""
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_actions.dialogs.invalid_ticket_data', default="Invalid ticket data"))
            return
        if not _c.can_see_internal(self, ticket):
            messagebox.showwarning(_t('gui.pastoral.student_support.ticket_actions.dialogs.permission_denied', default="Permission Denied"),
                                   _t('gui.pastoral.student_support.ticket_actions.dialogs.internal_staff_only', default="Only staff working this ticket can add internal notes."))
            return
        self._response_dialog(ticket, internal_only=True)

    def show_response_template_dialog(self, ticket):
        """Show dialog to use response template"""
        try:
            templates = self.support.get_response_templates() if self.support else []
        except Exception:
            logger.warning("Response templates unavailable", exc_info=True)
            templates = []
        template_dialog = _c.dialog(self, _t('gui.pastoral.student_support.ticket_actions.windows.use_response_template', default="Use Response Template"), 1000, 640, modal=True)
        btn_frame = ttk.Frame(template_dialog, padding=10)
        btn_frame.pack(side="bottom", fill="x")
        form_frame = ttk.Frame(template_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.select_response_template', default="Select Response Template"),
                  style='Heading.TLabel').pack(pady=(0, 15))

        if not templates:
            ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.no_response_templates_available', default="No response templates available")).pack()
            ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_actions.buttons.close', default="Close"), command=template_dialog.destroy).pack(pady=10)
            return

        template_frame = ttk.LabelFrame(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.templates', default="Templates"), padding="10")
        template_frame.pack(fill="x", pady=(0, 10))
        template_combo = ttk.Combobox(template_frame, state="readonly",
                                      values=[f"{t['name']} - {t.get('category') or 'General'}" for t in templates])
        template_combo.pack(fill="x")
        preview_frame = ttk.LabelFrame(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.preview', default="Preview"), padding="10")
        preview_frame.pack(fill="both", expand=True, pady=(0, 10))
        preview_text = scrolledtext.ScrolledText(preview_frame, height=8, wrap=tk.WORD, state='disabled')
        preview_text.pack(fill="both", expand=True)

        def update_preview(event=None):
            selection = template_combo.current()
            if selection >= 0:
                preview_text.config(state='normal')
                preview_text.delete(1.0, tk.END)
                preview_text.insert(1.0, templates[selection].get('content') or '')
                preview_text.config(state='disabled')

        template_combo.bind('<<ComboboxSelected>>', update_preview)

        def use_template():
            selection = template_combo.current()
            if selection < 0:
                messagebox.showerror(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_actions.dialogs.please_select_a_template', default="Please select a template"), parent=template_dialog)
                return
            template = templates[selection]
            template_dialog.destroy()
            self.show_add_response_dialog_with_template(ticket, template)

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_actions.buttons.use_template', default="Use Template"), command=use_template).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_actions.buttons.cancel', default="Cancel"), command=template_dialog.destroy).pack(side="left")

    def show_add_response_dialog_with_template(self, ticket, template):
        """Show add response dialog with template pre-filled"""
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_actions.dialogs.invalid_ticket_data', default="Invalid ticket data"))
            return
        if template is None or not isinstance(template, dict):
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_actions.dialogs.invalid_template_data', default="Invalid template data"))
            return
        self._response_dialog(ticket, text=template.get('content') or '', template=template)

    def show_satisfaction_rating(self):
        """Rate a resolved or closed ticket of your own (``rate_ticket``)."""
        if not _c.actor(self):
            return
        listing = _c.run(None, _c.ss('service').list_my_tickets, _c.actor(self),
                         {'status': ['resolved', 'closed']}, page=1, per_page=200)
        if listing is None:
            return
        rating_dialog = _c.dialog(self, _t('gui.pastoral.student_support.ticket_actions.windows.submit_satisfaction_rating', default="Submit Satisfaction Rating"), 900, 640, modal=True)
        btn_frame = ttk.Frame(rating_dialog, padding=10)
        btn_frame.pack(side="bottom", fill="x")
        form_frame = ttk.Frame(rating_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.rate_your_support_experience', default="Rate Your Support Experience"),
                  style='Title.TLabel').pack(pady=(0, 20))

        resolved_tickets = listing.get('tickets') or []
        if not resolved_tickets:
            ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.no_resolved_tickets_to_rate', default="No resolved tickets to rate")).pack()
            ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_actions.buttons.close', default="Close"), command=rating_dialog.destroy).pack(pady=10)
            return

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.select_ticket', default="Select Ticket:")).pack(anchor="w")
        ticket_combo = ttk.Combobox(form_frame, state="readonly", values=[
            f"#{t['ticket_id']} - {t.get('subject') or ''}" + (f" (rated {t['satisfaction_rating']}/5)" if t.get('satisfaction_rating') else '')
            for t in resolved_tickets])
        ticket_combo.pack(fill="x", pady=(5, 10))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.rating_1_5_stars', default="Rating (1-5 stars):")).pack(anchor="w")
        rating_var = tk.IntVar(value=5)
        rating_frame = ttk.Frame(form_frame)
        rating_frame.pack(anchor="w", pady=(5, 10))
        for i in range(1, 6):
            ttk.Radiobutton(rating_frame, text=f"{i} star{'s' if i > 1 else ''}", variable=rating_var, value=i).pack(side="left", padx=(0, 10))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_actions.labels.additional_feedback_optional', default="Additional Feedback (optional):")).pack(anchor="w")
        feedback_text = scrolledtext.ScrolledText(form_frame, height=6, wrap=tk.WORD)
        feedback_text.pack(fill="both", expand=True, pady=(5, 15))

        def submit_rating():
            selection = ticket_combo.current()
            if selection < 0:
                messagebox.showerror(_t('gui.pastoral.student_support.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_actions.dialogs.please_select_a_ticket', default="Please select a ticket"), parent=rating_dialog)
                return
            ticket_id = resolved_tickets[selection]['ticket_id']
            if _c.run(rating_dialog, _c.ss('service').rate_ticket, _c.actor(self), ticket_id,
                      rating_var.get(), feedback_text.get(1.0, tk.END).strip() or None):
                messagebox.showinfo(_t('gui.pastoral.student_support.ticket_actions.dialogs.success', default="Success"), _t('gui.pastoral.student_support.ticket_actions.dialogs.thank_you_for_your_feedback', default="Thank you for your feedback!"))
                rating_dialog.destroy()

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_actions.buttons.submit_rating', default="Submit Rating"), command=submit_rating).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_actions.buttons.cancel', default="Cancel"), command=rating_dialog.destroy).pack(side="left")
