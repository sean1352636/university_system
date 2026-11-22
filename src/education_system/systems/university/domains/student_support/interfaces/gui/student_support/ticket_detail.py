
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



# Referral fields shown as a text box, and those offered as a choice.
_LONG_FIELDS = ('description', 'circumstances', 'impact_statement', 'requested_remedy')
_READ_ONLY_FIELDS = ('student_id', 'student_name', 'student_email', 'username')
_REFERRAL_PRIORITIES = ('low', 'medium', 'high', 'critical')


class TicketDetailMixin:
    # ── opening a ticket ─────────────────────────────────────────────────

    def view_ticket_details(self, ticket_id):
        """Open a ticket through the service (the one access gate). A case
        worker refused a restricted ticket is offered break-glass access."""
        service = _c.ss('service')
        try:
            ticket = service.get_ticket(_c.actor(self), ticket_id)
        except PermissionError as exc:
            if _c.is_case_worker(self):
                self._offer_break_glass(ticket_id, str(exc))
            else:
                messagebox.showwarning(_t('gui.pastoral.student_support.ticket_detail.dialogs.no_access', default="No access"), str(exc))
            return
        except ValueError as exc:
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_detail.dialogs.error', default="Error"), str(exc))
            return
        except Exception as e:
            logger.exception("Ticket %s could not be opened", ticket_id)
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_detail.dialogs.error', default="Error"), f"Could not load ticket details: {e}")
            return
        self.show_ticket_detail_window(ticket)

    def _offer_break_glass(self, ticket_id, message):
        """Refused: explain, and let a case worker open the ticket in an
        emergency with a written reason (audited; the admins are told)."""
        win = _c.dialog(self, _t('gui.pastoral.student_support.ticket_detail.windows.break_glass', default="Restricted ticket #{ticket_id}").format(ticket_id=ticket_id), 720, 420, modal=True)
        frame = ttk.Frame(win, padding=15)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=message, style='Heading.TLabel', wraplength=660).pack(anchor="w")
        ttk.Label(frame, wraplength=660, text=_t(
            'gui.pastoral.student_support.ticket_detail.labels.break_glass_explain',
            default="This ticket belongs to another team or is confidential. In an emergency you "
                    "can open it for {minutes} minutes with break-glass access: your reason is "
                    "recorded, noted on the ticket and sent to the administrators.").format(
                        minutes=_c.ss('confidentiality').BREAK_GLASS_MINUTES)).pack(anchor="w", pady=(10, 10))
        ttk.Label(frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.break_glass_reason', default="Reason (at least a sentence):")).pack(anchor="w")
        reason = scrolledtext.ScrolledText(frame, height=5, wrap=tk.WORD)
        reason.pack(fill="both", expand=True, pady=(4, 10))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")

        def open_anyway():
            text = reason.get(1.0, tk.END).strip()
            if len(text) < 15:
                messagebox.showerror(_t('gui.pastoral.student_support.ticket_detail.dialogs.reason_needed', default="Reason needed"),
                                     _t('gui.pastoral.student_support.ticket_detail.dialogs.reason_15', default="Explain the emergency in at least 15 characters."), parent=win)
                return
            grant = _c.run(win, _c.ss('confidentiality').break_glass, _c.actor(self), ticket_id, text)
            if grant:
                win.destroy()
                messagebox.showinfo(_t('gui.pastoral.student_support.ticket_detail.dialogs.break_glass_granted', default="Break-glass access"),
                                    _t('gui.pastoral.student_support.ticket_detail.dialogs.break_glass_until', default="Access granted until {expires}. {notified} administrator(s) have been told.").format(
                                        expires=grant['expires_at'], notified=grant.get('notified', 0)))
                self.view_ticket_details(ticket_id)

        ttk.Button(buttons, text=_t('gui.pastoral.student_support.ticket_detail.buttons.break_glass', default="🔓 Open with break-glass access"),
                   command=open_anyway).pack(side="left")
        ttk.Button(buttons, text=_t('gui.pastoral.student_support.ticket_detail.buttons.cancel', default="Cancel"),
                   command=win.destroy).pack(side="left", padx=8)

    def _reopen_ticket(self, ticket_id, window=None):
        """Close ``window`` and show the ticket again (after a change)."""
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass
        self.view_ticket_details(ticket_id)

    def show_ticket_detail_window(self, ticket):
        """Show ticket details in a new window"""
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_detail.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_detail.dialogs.invalid_ticket_data', default="Invalid ticket data"))
            return

        ticket_id = ticket.get('ticket_id', 'N/A')
        ticket_title = ticket.get('subject') or ''
        detail_window = _c.dialog(self, f"🎫 Ticket #{ticket_id} - {ticket_title}", 1400, 900)
        detail_window.ticket_id = ticket_id

        # The crisis contacts stay on the requester's crisis ticket.
        if ticket.get('crisis_support'):
            _c.crisis_banner(detail_window, ticket['crisis_support']).pack(fill="x", padx=10, pady=(10, 0))
        elif ticket.get('crisis_flag') and _c.can_work(self, ticket):
            tk.Label(detail_window, text=_t('gui.pastoral.student_support.ticket_detail.labels.crisis_flag', default="⚠ Crisis language was detected on this ticket: it is a safeguarding ticket and a concern was raised."),
                     bg='#fee2e2', fg='#991b1b', anchor='w', padx=10, pady=6,
                     font=('Segoe UI', 10, 'bold')).pack(fill="x", padx=10, pady=(10, 0))

        detail_notebook = ttk.Notebook(detail_window, padding="10")
        detail_notebook.pack(fill="both", expand=True)

        overview_frame = ttk.Frame(detail_notebook, padding="10")
        detail_notebook.add(overview_frame, text=_t('gui.pastoral.student_support.ticket_detail.tabs.overview', default="📋 Overview"))
        self.create_ticket_overview(overview_frame, ticket)

        responses_frame = ttk.Frame(detail_notebook, padding="10")
        detail_notebook.add(responses_frame, text=f"💬 Responses ({len(ticket.get('responses', []))})")
        self.create_ticket_responses(responses_frame, ticket)

        attachments = ticket.get('attachments', [])
        if attachments:
            attachments_frame = ttk.Frame(detail_notebook, padding="10")
            detail_notebook.add(attachments_frame, text=f"📎 Attachments ({len(attachments)})")
            self.create_ticket_attachments(attachments_frame, attachments)

        # Actions and referrals: the staff working this ticket.
        if _c.can_work(self, ticket):
            actions_frame = ttk.Frame(detail_notebook, padding="10")
            detail_notebook.add(actions_frame, text=_t('gui.pastoral.student_support.ticket_detail.tabs.actions', default="🔧 Actions"))
            self.create_ticket_actions(actions_frame, ticket, detail_window)

            referrals_frame = ttk.Frame(detail_notebook, padding="10")
            detail_notebook.add(referrals_frame, text=_t('gui.pastoral.student_support.ticket_detail.tabs.referrals', default="➡️ Referrals"))
            self.create_ticket_referrals(referrals_frame, ticket, detail_window)

        if ticket.get('access') == 'owner':
            detail_window.after(200, lambda: self._ask_share_consent(ticket, detail_window))

    def _ask_share_consent(self, ticket, window, force=False):
        """The requester of a confidential ticket is asked once whether it
        may be shared with other services (``consent.consent_state``)."""
        consent = _c.ss('consent')
        try:
            state = consent.consent_state(_c.actor(self), ticket['ticket_id'])
        except (PermissionError, ValueError):
            return
        if not (state.get('prompt') or force):
            return
        answer = messagebox.askyesnocancel(
            _t('gui.pastoral.student_support.ticket_detail.dialogs.share_consent', default="Sharing your request"),
            state['question'] + "\n\n" + _t('gui.pastoral.student_support.ticket_detail.dialogs.share_consent_buttons',
                                             default="Yes: it may be shared.  No: keep it to the support team.  Cancel: ask me later."),
            parent=window)
        if answer is None:
            return
        if _c.run(window, consent.record_share_consent, _c.actor(self), ticket['ticket_id'], bool(answer)):
            self._reopen_ticket(ticket['ticket_id'], window)

    def create_ticket_overview(self, parent, ticket):
        """Create ticket overview section"""
        ticket_id = ticket.get('ticket_id', 'N/A')
        staff = _c.can_work(self, ticket)

        header_frame = ttk.Frame(parent)
        header_frame.pack(fill="x", pady=(0, 15))
        ttk.Label(header_frame, text=f"🎫 #{ticket_id}: {ticket.get('subject') or ''}",
                  style='Title.TLabel').pack(side="left")
        _c.tier_badge(header_frame, _c.tier_of(ticket)).pack(side="left", padx=10)

        details_frame = ttk.LabelFrame(parent, text=_t('gui.pastoral.student_support.ticket_detail.labels.ticket_details', default="📊 Ticket Details"), padding="15")
        details_frame.pack(fill="x", pady=(0, 10))
        details_grid = ttk.Frame(details_frame)
        details_grid.pack(fill="x")
        left_frame = ttk.Frame(details_grid)
        left_frame.pack(side="left", fill="both", expand=True)
        right_frame = ttk.Frame(details_grid)
        right_frame.pack(side="right", fill="both", expand=True)

        requester = ticket.get('student_id') or ticket.get('requester_username') or ''
        consent = {None: 'Not asked', 'granted': 'May be shared', 'declined': 'Not to be shared'}
        left = [
            ("👤 Requester:", requester),
            ("📊 Status:", ticket.get('status_label') or _c.status_label(ticket.get('status'))),
            ("🔥 Priority:", ticket.get('priority') or ''),
            ("📂 Category:", _c.category_label(ticket.get('category'))),
            ("👥 Team:", _c.team_label(ticket.get('team'))),
            ("📅 Created:", ticket.get('created_at') or ''),
        ]
        right = [
            ("👨‍💼 Assigned to:", ticket.get('assigned_to') or 'Unassigned'),
            ("⏰ Last Updated:", ticket.get('updated_at') or ''),
            ("🔒 Sharing:", consent.get(ticket.get('share_consent'), ticket.get('share_consent'))),
            ("⭐ Satisfaction:", f"{ticket['satisfaction_rating']}/5" if ticket.get('satisfaction_rating') else 'N/A'),
        ]
        if staff:
            right.insert(2, ("😊 Sentiment:", str(ticket.get('sentiment') or 'neutral').title()))
        for frame, rows in ((left_frame, left), (right_frame, right)):
            for i, (label, value) in enumerate(rows):
                ttk.Label(frame, text=label, font=('Segoe UI', 9, 'bold')).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 10))
                ttk.Label(frame, text=str(value)).grid(row=i, column=1, sticky="w", pady=2)

        if staff:
            state = _c.sla_state(ticket)
            sla_row = ttk.Frame(details_frame)
            sla_row.pack(fill="x", pady=(10, 0))
            ttk.Label(sla_row, text=_t('gui.pastoral.student_support.ticket_detail.labels.sla', default="⏱️ Service level:"), font=('Segoe UI', 9, 'bold')).pack(side="left")
            tk.Label(sla_row, text=_c.sla_text(state), fg=_c.sla_colour(state),
                     font=('Segoe UI', 9, 'bold')).pack(side="left", padx=(10, 0))
            if state and state.get('first_response_due'):
                ttk.Label(sla_row, foreground=self.colors['text_secondary'],
                          text=f"  first response due {state['first_response_due']}, resolution due {state['resolution_due']}").pack(side="left")

        if ticket.get('access') == 'owner' and _c.tier_of(ticket) != 'standard':
            consent_row = ttk.Frame(details_frame)
            consent_row.pack(fill="x", pady=(8, 0))
            ttk.Button(consent_row, text=_t('gui.pastoral.student_support.ticket_detail.buttons.change_sharing', default="Change my sharing answer"),
                       command=lambda: self._ask_share_consent(ticket, parent.winfo_toplevel(), force=True)).pack(side="left")

        tags = ticket.get('tags') or []
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except ValueError:
                tags = []
        if tags:
            tags_frame = ttk.Frame(details_frame)
            tags_frame.pack(fill="x", pady=(10, 0))
            ttk.Label(tags_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.tags', default="🏷️ Tags:"), font=('Segoe UI', 9, 'bold')).pack(side="left")
            for tag in tags:
                tk.Label(tags_frame, text=tag, bg="#e5e7eb", fg="#374151", padx=8, pady=2,
                         relief="solid", borderwidth=1).pack(side="left", padx=(5, 0))

        desc_frame = ttk.LabelFrame(parent, text=_t('gui.pastoral.student_support.ticket_detail.labels.description_variant_2', default="📄 Description"), padding="15")
        desc_frame.pack(fill="both", expand=True)
        desc_text = scrolledtext.ScrolledText(desc_frame, height=10, wrap=tk.WORD)
        desc_text.pack(fill="both", expand=True)
        desc_text.insert(1.0, ticket.get('description') or '')
        if ticket.get('resolution'):
            desc_text.insert(tk.END, f"\n\nResolution:\n{ticket['resolution']}")
        desc_text.config(state='disabled')

    def create_ticket_responses(self, parent, ticket):
        """The replies the service returned for this viewer — it leaves out
        internal notes for anyone not working the ticket."""
        responses = [r for r in ticket.get('responses') or [] if isinstance(r, dict)]

        # Reply button first so it stays visible.
        if self.can_respond_to_ticket(ticket):
            ttk.Button(parent, text=_t('gui.pastoral.student_support.ticket_detail.buttons.add_response', default="💬 Add Response"),
                       command=lambda: self.show_add_response_dialog(ticket)).pack(side="bottom", pady=(10, 0))

        if not responses:
            ttk.Label(parent, text=_t('gui.pastoral.student_support.ticket_detail.labels.no_responses_yet', default="💬 No responses yet"), style='Heading.TLabel').pack(pady=20)
            return

        canvas, scrollbar, scrollable_frame = self._create_scrollable_frame(parent)
        role_color = {"staff": "#3b82f6", "admin": "#dc2626", "student": "#16a34a", "system": "#6b7280"}
        for response in responses:
            responder_role = str(response.get('responder_role') or 'staff').lower()
            who = response.get('responder_username') or responder_role
            response_frame = ttk.LabelFrame(scrollable_frame, padding="10")
            response_frame.pack(fill="x", padx=5, pady=5)

            header_frame = ttk.Frame(response_frame)
            header_frame.pack(fill="x", pady=(0, 6))
            tk.Label(header_frame, text=responder_role.upper(), bg=role_color.get(responder_role, "#6b7280"),
                     fg="white", padx=8, pady=2, font=('Segoe UI', 8, 'bold')).pack(side="left")
            ttk.Label(header_frame, text=f" {who}").pack(side="left")
            if response.get('is_auto_generated'):
                tk.Label(header_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.auto', default="🤖 AUTO"), bg="#f59e0b", fg="white",
                         padx=6, pady=2, font=('Segoe UI', 8, 'bold')).pack(side="left", padx=(5, 0))
            if response.get('is_internal'):
                tk.Label(header_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.internal', default="🔒 INTERNAL"), bg="#ef4444", fg="white",
                         padx=6, pady=2, font=('Segoe UI', 8, 'bold')).pack(side="left", padx=(5, 0))
            ttk.Label(header_frame, text=str(response.get('response_datetime') or ''),
                      font=('Segoe UI', 9), foreground=self.colors['text_secondary']).pack(side="right")

            text = str(response.get('response_text') or '')
            body = tk.Text(response_frame, height=min(max(text.count('\n') + 2, 3), 10), wrap=tk.WORD)
            body.pack(fill="x", pady=(4, 0))
            body.insert(1.0, text)
            body.config(state='disabled')

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def create_ticket_attachments(self, parent, attachments):
        """The attachments the service returned for this viewer."""
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            att_frame = ttk.Frame(parent)
            att_frame.pack(fill="x", pady=5)
            file_size = attachment.get('file_size', 0) or 0
            name = attachment.get('original_filename') or 'file'
            private = '' if attachment.get('is_public', 1) else ' 🔒 staff only'
            ttk.Label(att_frame, text=f"📎 {name} ({file_size / (1024 * 1024):.1f}MB){private}").pack(side="left")
            ttk.Label(att_frame, text=f"Uploaded by {attachment.get('uploaded_by') or ''} on {attachment.get('created_at') or ''}",
                      font=('Segoe UI', 9), foreground=self.colors['text_secondary']).pack(side="left", padx=(10, 0))
            ttk.Button(att_frame, text=_t('gui.pastoral.student_support.ticket_detail.buttons.download', default="📥 Download"),
                       command=lambda a=attachment: self.download_attachment(a)).pack(side="right")

    # ── staff actions ────────────────────────────────────────────────────

    def create_ticket_actions(self, parent, ticket, window):
        """Status, assignment, confidentiality and the quick actions — for
        the staff working this ticket (the service checks again)."""
        ticket_id = ticket.get('ticket_id')

        status_frame = ttk.LabelFrame(parent, text=_t('gui.pastoral.student_support.ticket_detail.labels.update_status', default="📊 Update Status"), padding="10")
        status_frame.pack(fill="x", pady=(0, 10))
        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill="x")
        ttk.Label(status_grid, text=_t('gui.pastoral.student_support.ticket_detail.labels.new_status', default="New Status:")).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.new_status_var = tk.StringVar(value=ticket.get('status_label') or _c.status_label(ticket.get('status')))
        ttk.Combobox(status_grid, textvariable=self.new_status_var, state="readonly",
                     values=[label for label, _v in _c.status_choices()]).grid(row=0, column=1, sticky="ew", padx=(0, 10))
        ttk.Button(status_grid, text=_t('gui.pastoral.student_support.ticket_detail.buttons.update_status', default="Update Status"),
                   command=lambda: self.update_ticket_status_action(ticket_id, window)).grid(row=0, column=2)
        status_grid.columnconfigure(1, weight=1)

        # Assignment: a real team member (with load/capacity), not free text.
        assign_frame = ttk.LabelFrame(parent, text=_t('gui.pastoral.student_support.ticket_detail.labels.assignment', default="👨‍💼 Assignment"), padding="10")
        assign_frame.pack(fill="x", pady=(0, 10))
        assign_grid = ttk.Frame(assign_frame)
        assign_grid.pack(fill="x")
        ttk.Label(assign_grid, text=_t('gui.pastoral.student_support.ticket_detail.labels.assign_to', default="Assign to:")).grid(row=0, column=0, sticky="w", padx=(0, 10))
        try:
            choices = _c.team_assignees(ticket.get('team'))
        except Exception:
            logger.warning("Team members unavailable for ticket %s", ticket_id, exc_info=True)
            choices = []
        self._assignee_choices = {label: name for name, label in choices}
        self._assignee_choices[_t('gui.pastoral.student_support.ticket_detail.values.unassigned', default="(unassigned)")] = ''
        current = next((label for label, name in self._assignee_choices.items()
                        if name == (ticket.get('assigned_to') or '')), '')
        self.assign_to_var = tk.StringVar(value=current)
        ttk.Combobox(assign_grid, textvariable=self.assign_to_var, state="readonly", width=40,
                     values=list(self._assignee_choices)).grid(row=0, column=1, sticky="ew", padx=(0, 10))
        ttk.Button(assign_grid, text=_t('gui.pastoral.student_support.ticket_detail.buttons.assign_to_me', default="Assign to Me"),
                   command=lambda: self.assign_ticket_to_me(ticket_id, window)).grid(row=0, column=2, padx=(0, 10))
        ttk.Button(assign_grid, text=_t('gui.pastoral.student_support.ticket_detail.buttons.update_assignment', default="Update Assignment"),
                   command=lambda: self.update_ticket_assignment(ticket_id, window)).grid(row=0, column=3)
        ttk.Button(assign_grid, text=_t('gui.pastoral.student_support.ticket_detail.buttons.reassign', default="🔁 Hand over (with reason)"),
                   command=lambda: self.reassign_ticket(ticket, window)).grid(row=1, column=1, sticky="w", pady=(6, 0))
        if not ticket.get('assigned_to'):
            ttk.Button(assign_grid, text=_t('gui.pastoral.student_support.ticket_detail.buttons.take', default="✋ Take ticket"),
                       command=lambda: self.take_ticket(ticket_id, window)).grid(row=1, column=2, sticky="w", pady=(6, 0))
        assign_grid.columnconfigure(1, weight=1)

        tier_frame = ttk.LabelFrame(parent, text=_t('gui.pastoral.student_support.ticket_detail.labels.confidentiality', default="🔒 Confidentiality"), padding="10")
        tier_frame.pack(fill="x", pady=(0, 10))
        _c.tier_badge(tier_frame, _c.tier_of(ticket)).pack(side="left")
        ttk.Button(tier_frame, text=_t('gui.pastoral.student_support.ticket_detail.buttons.set_tier', default="Change tier (with reason)"),
                   command=lambda: self.set_ticket_tier(ticket, window)).pack(side="left", padx=10)

        actions_frame = ttk.LabelFrame(parent, text=_t('gui.pastoral.student_support.ticket_detail.labels.quick_actions', default="⚡ Quick Actions"), padding="10")
        actions_frame.pack(fill="x", pady=(0, 10))
        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack(fill="x")
        buttons = [
            (_t('gui.pastoral.student_support.ticket_detail.buttons.add_internal_note', default="📝 Add Internal Note"), lambda: self.show_add_internal_note_dialog(ticket)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.use_template', default="📋 Use Template"), lambda: self.show_response_template_dialog(ticket)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.view_history', default="📊 View History"), lambda: self.show_ticket_history(ticket_id)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.merge_ticket', default="🔗 Merge Ticket"), lambda: self.show_merge_dialog(ticket)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.escalate', default="⚡ Escalate"), lambda: self.escalate_ticket(ticket_id, window)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.export', default="📤 Export"), lambda: self.export_ticket(ticket)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.edit_ticket', default="✏️ Edit Ticket"), lambda: self.edit_ticket(ticket, window)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.close_ticket', default="🗂️ Close Ticket"), lambda: self.delete_ticket(ticket_id, window)),
        ]
        buttons += [
            (_t('gui.pastoral.student_support.ticket_detail.buttons.link', default="🔗 Link Ticket"),
             lambda: self._support_tool('link_dialog', ticket_id)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.links', default="🧷 Linked Tickets"),
             lambda: self._support_tool('open_links', ticket_id, open_ticket=self.view_ticket_details)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.log_time', default="⏲️ Log Time"),
             lambda: self._support_tool('time_dialog', ticket_id)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.time', default="🕒 Time Spent"),
             lambda: self._support_tool('open_time', ticket_id)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.followers', default="👁️ Followers"),
             lambda: self._support_tool('open_followers', ticket_id)),
            (_t('gui.pastoral.student_support.ticket_detail.buttons.incident', default="🚨 Add to Incident"),
             lambda: self._support_tool('add_to_incident', ticket_id)),
        ]
        if _c.is_admin(self):
            buttons.append((_t('gui.pastoral.student_support.ticket_detail.buttons.delete_permanently', default="🗑️ Delete Permanently"),
                            lambda: self.delete_ticket_permanently(ticket, window)))
        if ticket.get('student_id') and _c.is_support_staff(self):
            buttons.append((_t('gui.pastoral.student_support.ticket_detail.buttons.student_360', default="🧭 Student 360"),
                            lambda: self.show_student_360(ticket.get('student_id'))))
        for i, (text, command) in enumerate(buttons):
            ttk.Button(actions_grid, text=text, command=command).grid(row=i // 3, column=i % 3, padx=(0, 5), pady=2, sticky="ew")

    def update_ticket_status_action(self, ticket_id, window):
        """Status from the Actions tab (``service.set_status``)."""
        value = _c.status_value(self.new_status_var.get())
        if not value:
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_detail.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_detail.dialogs.please_select_a_status', default="Please select a status"))
            return
        result = _c.run(window, _c.ss('service').set_status, _c.actor(self), ticket_id, value)
        if result:
            self.update_status(f"Ticket #{ticket_id}: {_c.status_label(result['old'])} → {_c.status_label(result['new'])}")
            self._reopen_ticket(ticket_id, window)
            self.refresh_data()

    def update_ticket_assignment(self, ticket_id, window):
        """Give the ticket to the chosen team member (``service.assign``)."""
        assignee = self._assignee_choices.get(self.assign_to_var.get(), self.assign_to_var.get())
        result = _c.run(window, _c.ss('service').assign, _c.actor(self), ticket_id, assignee or None)
        if result is not None:
            messagebox.showinfo(_t('gui.pastoral.student_support.ticket_detail.dialogs.success', default="Success"),
                                _t('gui.pastoral.student_support.ticket_detail.dialogs.assigned_to', default="Ticket #{ticket_id} is now with {who}.").format(
                                    ticket_id=ticket_id, who=result['new'] or 'nobody'), parent=window)
            self._reopen_ticket(ticket_id, window)
            self.refresh_data()

    def reassign_ticket(self, ticket, window):
        """Hand the ticket over with a reason (``caseload.reassign``)."""
        ticket_id = ticket['ticket_id']
        win = _c.dialog(self, _t('gui.pastoral.student_support.ticket_detail.windows.reassign', default="Hand over ticket #{ticket_id}").format(ticket_id=ticket_id), 640, 420, modal=True)
        frame = ttk.Frame(win, padding=15)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.hand_to', default="Hand over to:")).pack(anchor="w")
        choices = {label: name for name, label in _c.team_assignees(ticket.get('team'))}
        who = ttk.Combobox(frame, values=list(choices), state="readonly", width=45)
        who.pack(anchor="w", pady=(4, 10))
        ttk.Label(frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.handover_reason', default="Reason for the handover:")).pack(anchor="w")
        reason = scrolledtext.ScrolledText(frame, height=5, wrap=tk.WORD)
        reason.pack(fill="both", expand=True, pady=(4, 10))
        force = tk.BooleanVar(value=False)
        if _c.can_manage_team(self, ticket.get('team')):
            ttk.Checkbutton(frame, variable=force, text=_t('gui.pastoral.student_support.ticket_detail.buttons.force', default="Override team membership / capacity (leads and admins)")).pack(anchor="w")

        def save():
            if not who.get():
                messagebox.showerror(_t('gui.pastoral.student_support.ticket_detail.dialogs.error', default="Error"),
                                     _t('gui.pastoral.student_support.ticket_detail.dialogs.choose_adviser', default="Choose who to hand the ticket to."), parent=win)
                return
            result = _c.run(win, _c.ss('caseload').reassign, _c.actor(self), ticket_id, choices[who.get()],
                            reason.get(1.0, tk.END).strip(), force=force.get())
            if result:
                win.destroy()
                self._reopen_ticket(ticket_id, window)
                self.refresh_data()

        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=(10, 0))
        ttk.Button(bar, text=_t('gui.pastoral.student_support.ticket_detail.buttons.hand_over', default="Hand over"), command=save).pack(side="left")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.ticket_detail.buttons.cancel', default="Cancel"), command=win.destroy).pack(side="left", padx=8)

    def take_ticket(self, ticket_id, window=None):
        """Pick an unassigned ticket up (``caseload.take``)."""
        result = _c.run(window, _c.ss('caseload').take, _c.actor(self), ticket_id)
        if result:
            self.update_status(f"Ticket #{ticket_id} taken")
            if window is not None:
                self._reopen_ticket(ticket_id, window)
            self.refresh_data()
        return result

    def set_ticket_tier(self, ticket, window):
        """Change the confidentiality tier with a reason (``set_tier``)."""
        ticket_id = ticket['ticket_id']
        tiers = _c.ss('confidentiality').TIERS
        win = _c.dialog(self, _t('gui.pastoral.student_support.ticket_detail.windows.set_tier', default="Confidentiality of ticket #{ticket_id}").format(ticket_id=ticket_id), 640, 420, modal=True)
        frame = ttk.Frame(win, padding=15)
        frame.pack(fill="both", expand=True)
        tier = tk.StringVar(value=_c.tier_of(ticket))
        for value in tiers:
            ttk.Radiobutton(frame, text=_c.tier_label(value), variable=tier, value=value).pack(anchor="w")
        ttk.Label(frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.tier_reason', default="Reason (a sentence):")).pack(anchor="w", pady=(10, 0))
        reason = scrolledtext.ScrolledText(frame, height=5, wrap=tk.WORD)
        reason.pack(fill="both", expand=True, pady=(4, 10))

        def save():
            result = _c.run(win, _c.ss('confidentiality').set_tier, _c.actor(self), ticket_id,
                            tier.get(), reason.get(1.0, tk.END).strip())
            if result:
                win.destroy()
                self._reopen_ticket(ticket_id, window)

        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.ticket_detail.buttons.save', default="Save"), command=save).pack(side="left")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.ticket_detail.buttons.cancel', default="Cancel"), command=win.destroy).pack(side="left", padx=8)

    # ── referrals ────────────────────────────────────────────────────────

    def create_ticket_referrals(self, parent, ticket, window):
        """"Refer to…" (``referrals.options``) and the referrals made."""
        ticket_id = ticket['ticket_id']
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 10))
        menu_button = ttk.Menubutton(bar, text=_t('gui.pastoral.student_support.ticket_detail.buttons.refer_to', default="➡️ Refer to…"))
        menu = tk.Menu(menu_button, tearoff=0)
        menu_button['menu'] = menu
        menu_button.pack(side="left")
        note = ttk.Label(bar, foreground=self.colors['text_secondary'])
        note.pack(side="left", padx=10)

        try:
            options = _c.ss('referrals').options(_c.actor(self), ticket_id)
        except (PermissionError, ValueError) as exc:
            note.config(text=str(exc))
            options = None
        except Exception as exc:
            logger.warning("Referral options unavailable for ticket %s", ticket_id, exc_info=True)
            note.config(text=f"Referrals unavailable: {exc}")
            options = None
        if options:
            for kind, entry in options['kinds'].items():
                if entry['allowed']:
                    menu.add_command(label=entry['label'],
                                     command=lambda k=kind: self.show_refer_dialog(ticket, k, options, window))
                else:
                    menu.add_command(label=f"{entry['label']} — {entry['blocked_reason']}", state='disabled')
            consent = {None: 'not asked', 'granted': 'granted', 'declined': 'declined'}
            note.config(text=_t('gui.pastoral.student_support.ticket_detail.labels.consent_state', default="Requester's consent to share: {state}").format(
                state=consent.get(options.get('share_consent'), options.get('share_consent'))))

        tree = _c.tree_with_scroll(parent, ('id', 'kind', 'reference', 'status', 'basis', 'by', 'at', 'error'),
                                   {'id': '#', 'kind': 'Referred to', 'reference': 'Reference', 'status': 'Status',
                                    'basis': 'Consent basis', 'by': 'By', 'at': 'When', 'error': 'Problem'},
                                   {'id': 40, 'kind': 200, 'reference': 100, 'status': 90, 'basis': 120,
                                    'by': 100, 'at': 140, 'error': 220}, height=8)
        kinds = _c.ss('referrals').KINDS
        for r in (options or {}).get('referrals') or []:
            tree.insert('', 'end', values=(r['referral_id'], kinds.get(r['kind'], r['kind']),
                                           r.get('target_ref') or '', r.get('status') or '',
                                           r.get('consent_basis') or '', r.get('created_by') or '',
                                           r.get('created_at') or '', r.get('error') or ''))

    def show_refer_dialog(self, ticket, kind, options, window):
        """The fields a referral of ``kind`` needs, pre-filled from the ticket."""
        ticket_id = ticket['ticket_id']
        entry = options['kinds'][kind]
        choices = options.get('choices') or {}
        win = _c.dialog(self, f"{entry['label']} — ticket #{ticket_id}", 820, 700, modal=True)
        bar = ttk.Frame(win, padding=10)
        bar.pack(side="bottom", fill="x")
        form = ttk.Frame(win, padding=15)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=entry['label'], style='Heading.TLabel').grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        if entry.get('basis'):
            ttk.Label(form, text=f"Consent basis: {entry['basis']}", foreground=self.colors['text_secondary']).grid(
                row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        funds = {f"{f.get('name') or f.get('fund_name') or f['fund_id']} (#{f['fund_id']})": f['fund_id']
                 for f in choices.get('hardship_funds') or []}
        picks = {'grounds': list(choices.get('mitigating_grounds') or ()),
                 'accommodation_type': list(choices.get('accommodation_types') or ()),
                 'priority': list(_REFERRAL_PRIORITIES), 'fund_id': list(funds)}
        widgets = {}
        row = 2
        for key, value in (entry.get('values') or {}).items():
            ttk.Label(form, text=key.replace('_', ' ').capitalize() + ":").grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=3)
            if key in _LONG_FIELDS:
                widget = scrolledtext.ScrolledText(form, height=6 if key == 'description' else 3, wrap=tk.WORD, width=70)
                widget.insert(1.0, value or '')
            elif key in picks and picks[key]:
                widget = ttk.Combobox(form, values=picks[key], width=50,
                                      state="readonly" if key != 'priority' else "normal")
                if key == 'fund_id':
                    widget.set(next((label for label, fid in funds.items() if fid == value), ''))
                else:
                    widget.set(value or '')
            else:
                widget = ttk.Entry(form, width=52)
                widget.insert(0, '' if value is None else str(value))
                if key in _READ_ONLY_FIELDS:
                    widget.config(state='readonly')
            widget.grid(row=row, column=1, sticky="ew", pady=3)
            widgets[key] = widget
            row += 1
        form.columnconfigure(1, weight=1)

        def submit():
            fields = {}
            for key, widget in widgets.items():
                if key in _READ_ONLY_FIELDS:
                    continue
                if isinstance(widget, scrolledtext.ScrolledText):
                    value = widget.get(1.0, tk.END).strip()
                else:
                    value = widget.get().strip()
                if key == 'fund_id':
                    value = funds.get(value)
                fields[key] = value if value not in ('',) else None
            result = _c.run(win, _c.ss('referrals').refer, _c.actor(self), ticket_id, kind, **fields)
            if result:
                win.destroy()
                messagebox.showinfo(_t('gui.pastoral.student_support.ticket_detail.dialogs.referred', default="Referred"),
                                    _t('gui.pastoral.student_support.ticket_detail.dialogs.referred_ref', default="{label} created (reference {reference}).").format(
                                        label=entry['label'], reference=result.get('reference')))
                self._reopen_ticket(ticket_id, window)

        ttk.Button(bar, text=_t('gui.pastoral.student_support.ticket_detail.buttons.refer', default="Refer"), command=submit).pack(side="left")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.ticket_detail.buttons.cancel', default="Cancel"), command=win.destroy).pack(side="left", padx=8)

    # ── edit / close ─────────────────────────────────────────────────────

    def edit_ticket(self, ticket, parent_window=None):
        """Change a ticket's title, description, team, category, priority and
        status through the service. Title / description / team changes need
        a reason; they are audited and noted on the ticket."""
        if ticket is None or not isinstance(ticket, dict):
            messagebox.showerror(_t('gui.pastoral.student_support.ticket_detail.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_detail.dialogs.invalid_ticket_data', default="Invalid ticket data"))
            return
        ticket_id = ticket.get('ticket_id')
        edit_window = _c.dialog(self, f"✏️ Edit Ticket #{ticket_id}", 900, 820, modal=True)
        btn_frame = ttk.Frame(edit_window, padding=10)
        btn_frame.pack(side="bottom", fill="x")
        form_frame = ttk.Frame(edit_window, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text=f"Edit Ticket #{ticket_id}: {ticket.get('subject') or ''}",
                  style='Title.TLabel', wraplength=680).pack(anchor="w", pady=(0, 15))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.title', default="Title:"), font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        old_subject = ticket.get('subject') or ''
        edit_subject_var = tk.StringVar(value=old_subject)
        ttk.Entry(form_frame, textvariable=edit_subject_var, width=80).pack(anchor="w", fill="x", pady=(0, 10))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.description', default="Description:"), font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        old_description = ticket.get('description') or ''
        edit_description = scrolledtext.ScrolledText(form_frame, height=7, wrap=tk.WORD)
        edit_description.insert("1.0", old_description)
        edit_description.pack(fill="x", pady=(0, 10))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.team', default="Team:"), font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        routing = _c.ss('routing')
        team_keys = [k for k in routing.TEAMS]
        old_team_label = _c.team_label(ticket.get('team')) if ticket.get('team') else ''
        edit_team_var = tk.StringVar(value=old_team_label)
        ttk.Combobox(form_frame, textvariable=edit_team_var, state="readonly", width=40,
                     values=[routing.team_label(k) for k in team_keys]).pack(anchor="w", pady=(0, 10))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.category', default="Category:"), font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        edit_category_var = tk.StringVar(value=_c.category_label(ticket.get('category')))
        ttk.Combobox(form_frame, textvariable=edit_category_var, values=_c.categories(),
                     state="readonly", width=40).pack(anchor="w", pady=(0, 10))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.priority', default="Priority:"), font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        edit_priority_var = tk.StringVar(value=str(ticket.get('priority') or 'Medium').title())
        ttk.Combobox(form_frame, textvariable=edit_priority_var, values=_c.priorities(),
                     state="readonly", width=40).pack(anchor="w", pady=(0, 10))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.status', default="Status:"), font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        old_status_label = ticket.get('status_label') or _c.status_label(ticket.get('status'))
        edit_status_var = tk.StringVar(value=old_status_label)
        ttk.Combobox(form_frame, textvariable=edit_status_var, state="readonly", width=40,
                     values=[label for label, _v in _c.status_choices()]).pack(anchor="w", pady=(0, 10))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.edit_reason', default="Reason (needed to change the title, description or team):"), font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        edit_reason_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=edit_reason_var, width=80).pack(anchor="w", fill="x", pady=(0, 10))

        def save_ticket_changes():
            service = _c.ss('service')
            reason = edit_reason_var.get().strip()
            new_subject = edit_subject_var.get().strip()
            new_description = edit_description.get("1.0", tk.END).strip()
            text_changed = new_subject != old_subject or new_description != old_description.strip()
            if text_changed:
                result = _c.run(edit_window, service.edit_ticket, _c.actor(self), ticket_id,
                                subject=new_subject if new_subject != old_subject else None,
                                description=(new_description if new_description != old_description.strip()
                                             else None),
                                reason=reason)
                if result is None:
                    return
                if result.get('crisis'):
                    _c.show_crisis(self, result['crisis'], parent=edit_window)
            if edit_team_var.get() and edit_team_var.get() != old_team_label:
                if _c.run(edit_window, service.set_team, _c.actor(self), ticket_id,
                          edit_team_var.get(), reason) is None:
                    return
            changes = {}
            if edit_category_var.get() != _c.category_label(ticket.get('category')):
                changes['category'] = edit_category_var.get()
            if edit_priority_var.get().lower() != str(ticket.get('priority') or '').lower():
                changes['priority'] = edit_priority_var.get()
            if changes and _c.run(edit_window, service.bulk_update, _c.actor(self), [ticket_id], changes) is None:
                return
            if edit_status_var.get() != old_status_label:
                if _c.run(edit_window, service.set_status, _c.actor(self), ticket_id,
                          _c.status_value(edit_status_var.get())) is None:
                    return
            edit_window.destroy()
            self._reopen_ticket(ticket_id, parent_window)
            self.refresh_data()

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_detail.buttons.save_changes', default="💾 Save Changes"), command=save_ticket_changes,
                   style='Primary.TButton').pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_detail.buttons.cancel_variant_2', default="❌ Cancel"), command=edit_window.destroy).pack(side="left")

    def delete_ticket(self, ticket_id, parent_window=None):
        """Close the ticket (the service has no delete: support records are
        kept, and removed only by the retention policy or an approved
        erasure request)."""
        note = simpledialog.askstring(
            _t('gui.pastoral.student_support.ticket_detail.dialogs.confirm_close', default="Close ticket"),
            _t('gui.pastoral.student_support.ticket_detail.dialogs.close_note', default="Close ticket #{ticket_id}? The record is kept (removed only under the retention policy or an approved erasure request).\n\nClosing note (optional):").format(ticket_id=ticket_id),
            **({'parent': parent_window} if parent_window else {}))
        if note is None:
            return
        result = _c.run(parent_window, _c.ss('service').set_status, _c.actor(self), ticket_id,
                        'closed', note=note.strip() or None)
        if result:
            messagebox.showinfo(_t('gui.pastoral.student_support.ticket_detail.dialogs.success', default="Success"),
                                _t('gui.pastoral.student_support.ticket_detail.dialogs.closed', default="Ticket #{ticket_id} has been closed.").format(ticket_id=ticket_id))
            if parent_window:
                parent_window.destroy()
            self.refresh_data()

    def delete_ticket_permanently(self, ticket, parent_window=None):
        """Administrators: delete a ticket created in error, a duplicate, spam
        or a test — with its replies and attachments (``gdpr.delete_ticket``).
        Safeguarding tickets and tickets under a legal hold are refused."""
        gdpr = _c.ss('gdpr')
        ticket_id = ticket.get('ticket_id')
        win = _c.dialog(self, f"🗑️ Delete Ticket #{ticket_id}", 640, 460, modal=True)
        btn_frame = ttk.Frame(win, padding=10)
        btn_frame.pack(side="bottom", fill="x")
        form = ttk.Frame(win, padding=20)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=_t('gui.pastoral.student_support.ticket_detail.labels.delete_warning',
                                default="This permanently removes ticket #{ticket_id}, its replies and its attachments. "
                                        "It cannot be undone. To keep the record, close the ticket instead.").format(ticket_id=ticket_id),
                  wraplength=580, foreground="#b91c1c").pack(anchor="w", pady=(0, 12))
        ttk.Label(form, text=_t('gui.pastoral.student_support.ticket_detail.labels.delete_reason', default="Reason:"),
                  font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        reason_var = tk.StringVar(value=gdpr.DELETE_REASONS[0])
        ttk.Combobox(form, textvariable=reason_var, values=list(gdpr.DELETE_REASONS), state="readonly",
                     width=30).pack(anchor="w", pady=(0, 10))
        ttk.Label(form, text=_t('gui.pastoral.student_support.ticket_detail.labels.delete_detail', default="Details (required for 'other'):")).pack(anchor="w")
        detail_var = tk.StringVar()
        ttk.Entry(form, textvariable=detail_var, width=70).pack(anchor="w", fill="x", pady=(0, 10))
        ttk.Label(form, text=_t('gui.pastoral.student_support.ticket_detail.labels.delete_confirm',
                                default="Type the ticket number ({ticket_id}) to confirm:").format(ticket_id=ticket_id),
                  font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        confirm_var = tk.StringVar()
        ttk.Entry(form, textvariable=confirm_var, width=12).pack(anchor="w")

        def do_delete():
            result = _c.run(win, gdpr.delete_ticket, _c.actor(self), ticket_id, reason_var.get(),
                            confirm_ticket_id=confirm_var.get(), detail=detail_var.get())
            if result is None:
                return
            win.destroy()
            messagebox.showinfo(_t('gui.pastoral.student_support.ticket_detail.dialogs.success', default="Success"),
                                _t('gui.pastoral.student_support.ticket_detail.dialogs.deleted', default="Ticket #{ticket_id} was deleted.").format(ticket_id=ticket_id))
            if parent_window:
                parent_window.destroy()
            self.refresh_data()

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_detail.buttons.delete', default="🗑️ Delete"),
                   command=do_delete).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_detail.buttons.cancel_variant_2', default="❌ Cancel"),
                   command=win.destroy).pack(side="left")

    def show_status_update_dialog(self, ticket_id):
        """Show dialog to update ticket status"""
        status_dialog = _c.dialog(self, f"Update Status - Ticket #{ticket_id}", 700, 420, modal=True)
        btn_frame = ttk.Frame(status_dialog, padding=10)
        btn_frame.pack(side="bottom", fill="x")
        form_frame = ttk.Frame(status_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.update_ticket_status', default="Update Ticket Status"),
                  style='Heading.TLabel').pack(pady=(0, 15))
        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.new_status', default="New Status:")).pack(anchor="w")
        status_var = tk.StringVar()
        ttk.Combobox(form_frame, textvariable=status_var, state="readonly",
                     values=[label for label, _v in _c.status_choices()]).pack(fill="x", pady=(5, 10))
        ttk.Label(form_frame, text=_t('gui.pastoral.student_support.ticket_detail.labels.resolution_notes_optional', default="Resolution Notes (optional):")).pack(anchor="w")
        notes_text = scrolledtext.ScrolledText(form_frame, height=4, wrap=tk.WORD)
        notes_text.pack(fill="both", expand=True, pady=(5, 15))

        def update_status():
            new_status = _c.status_value(status_var.get())
            if not new_status:
                messagebox.showerror(_t('gui.pastoral.student_support.ticket_detail.dialogs.error', default="Error"), _t('gui.pastoral.student_support.ticket_detail.dialogs.please_select_a_status', default="Please select a status"), parent=status_dialog)
                return
            notes = notes_text.get(1.0, tk.END).strip() or None
            if _c.run(status_dialog, _c.ss('service').set_status, _c.actor(self), ticket_id, new_status, note=notes):
                messagebox.showinfo(_t('gui.pastoral.student_support.ticket_detail.dialogs.success', default="Success"), f"Status updated to {_c.status_label(new_status)}")
                status_dialog.destroy()
                self.refresh_data()

        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_detail.buttons.update_status', default="Update Status"), command=update_status).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_support.ticket_detail.buttons.cancel', default="Cancel"), command=status_dialog.destroy).pack(side="left")
