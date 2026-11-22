
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
from tkinter.font import Font
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
import json
import os
import threading
from functools import partial
import webbrowser
from education_system.systems.university.infrastructure.email.template_utils import render_template

# Import authentication - REQUIRED (no fallback for security)
from education_system.systems.university.infrastructure.auth import UserAuth, get_global_auth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Import activity logger for audit trail
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

from education_system.systems.university.domains.student_support.interfaces.gui.helpdesk.base import HelpdeskGUI
from education_system.systems.university.domains.student_support.interfaces.gui.helpdesk import _tickets as T

def show_ticket_details(self, ticket_id):
    """Show detailed ticket view"""
    details_window = tk.Toplevel(self.root)
    details_window.title(f"Ticket #{ticket_id} Details")
    T.size_window(details_window)
    details_window.transient(self.root)

    # Load ticket data (the service checks access and records a look at a
    # confidential ticket before revealing it)
    ticket_data = self.get_ticket_details(ticket_id)
    if not ticket_data:
        details_window.destroy()
        return

    # Tier badge, crisis banner and SLA status above the tabs
    T.banner(details_window, ticket_data)

    # Create notebook for different sections
    notebook = ttk.Notebook(details_window)
    notebook.pack(fill='both', expand=True, padx=10, pady=10)

    # Details tab
    details_frame = ttk.Frame(notebook)
    notebook.add(details_frame, text=_t('gui.pastoral.helpdesk.ticket_view.tabs.details', default="Details"))

    # Create scrollable frame for details
    canvas = tk.Canvas(details_frame)
    scrollbar = ttk.Scrollbar(details_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Ticket information
    info_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.pastoral.helpdesk.ticket_view.labels.ticket_information', default="Ticket Information"))
    info_frame.pack(fill='x', padx=10, pady=5)

    # Display ticket fields
    fields = [
        ("Ticket ID:", ticket_data.get('ticket_id')),
        ("Subject:", ticket_data.get('subject')),
        ("Category:", ticket_data.get('category')),
        ("Status:", ticket_data.get('status_label') or T.status_label(ticket_data.get('status'))),
        ("Priority:", str(ticket_data.get('priority') or '').title()),
        ("Impact:", str(ticket_data.get('impact') or '').title()),
        ("Urgency:", str(ticket_data.get('urgency') or '').title()),
        ("Raised By:", T.requester_of(ticket_data)),
        ("Created:", ticket_data.get('created_at')),
        ("Updated:", ticket_data.get('updated_at')),
        ("Assigned To:", ticket_data.get('assigned_to') or 'Unassigned'),
        ("Department:", ticket_data.get('department') or 'None'),
        ("Team:", T.routing.team_label(ticket_data.get('team')) if ticket_data.get('team') else None),
        ("Confidentiality:", T.tier_badge(ticket_data) or 'Standard'),
        ("SLA:", T.sla_label(ticket_data)),
        ("Due:", ticket_data.get('sla_due_at') or ticket_data.get('due_date')),
    ]

    for i, (label, value) in enumerate(fields):
        ttk.Label(info_frame, text=label, style='Heading.TLabel').grid(row=i, column=0, sticky='w', padx=5, pady=2)
        ttk.Label(info_frame, text=str(value) if value else 'N/A').grid(row=i, column=1, sticky='w', padx=20, pady=2)

    # Message frame
    message_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.pastoral.helpdesk.ticket_view.labels.original_message', default="Original Message"))
    message_frame.pack(fill='x', padx=10, pady=5)

    message_text = scrolledtext.ScrolledText(message_frame, height=5, wrap='word', state='disabled')
    message_text.pack(fill='x', padx=5, pady=5)
    message_text.config(state='normal')
    message_text.insert('1.0', ticket_data.get('description', ''))
    message_text.config(state='disabled')

    # Resolution frame (if resolved)
    if ticket_data.get('resolution'):
        resolution_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.pastoral.helpdesk.ticket_view.labels.resolution', default="Resolution"))
        resolution_frame.pack(fill='x', padx=10, pady=5)

        resolution_text = scrolledtext.ScrolledText(resolution_frame, height=3, wrap='word', state='disabled')
        resolution_text.pack(fill='x', padx=5, pady=5)
        resolution_text.config(state='normal')
        resolution_text.insert('1.0', ticket_data.get('resolution', ''))
        resolution_text.config(state='disabled')

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Replies tab
    replies_frame = ttk.Frame(notebook)
    notebook.add(replies_frame, text=_t('gui.pastoral.helpdesk.ticket_view.tabs.conversation', default="Conversation"))

    self.create_replies_view(replies_frame, ticket_id, ticket_data)

    # Actions tab: the requester (replies) and the staff working the ticket
    if (self.has_permission('reply_to_own_ticket') or self.has_permission('manage_tickets')
            or ticket_data.get('access') == 'owner' or T.is_case_worker(self)):
        actions_frame = ttk.Frame(notebook)
        notebook.add(actions_frame, text=_t('gui.pastoral.helpdesk.ticket_view.tabs.actions', default="Actions"))

        self.create_ticket_actions_view(actions_frame, ticket_id, ticket_data)

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_ticket_details = show_ticket_details

def get_ticket_details(self, ticket_id):
    """The ticket with the replies and attachments the signed-in person may
    see (ticket service ``get_ticket``), or None after showing why not."""
    try:
        return T.svc.get_ticket(T.actor(self), ticket_id)
    except Exception as e:
        T.show_error(e)
        return None

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_ticket_details = get_ticket_details

def create_replies_view(self, parent, ticket_id, ticket=None):
    """Create replies/conversation view"""
    # Toolbar
    toolbar = ttk.Frame(parent)
    toolbar.pack(fill='x', padx=5, pady=5)

    ttk.Button(toolbar, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.add_reply', default="Add Reply"), command=lambda: self.show_reply_dialog(ticket_id)).pack(side='left', padx=5)
    ttk.Button(toolbar, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.refresh', default="Refresh"), command=lambda: self.refresh_replies_view(parent, ticket_id)).pack(side='left', padx=5)

    # Replies list
    self.replies_frame = ttk.Frame(parent)
    self.replies_frame.pack(fill='both', expand=True, padx=5, pady=5)

    self.load_ticket_replies(ticket_id, ticket)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_replies_view = create_replies_view

def load_ticket_replies(self, ticket_id, ticket=None):
    """Load ticket replies"""
    try:
        # Clear existing widgets
        for widget in self.replies_frame.winfo_children():
            widget.destroy()

        # Create scrollable frame
        canvas = tk.Canvas(self.replies_frame)
        scrollbar = ttk.Scrollbar(self.replies_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Get replies from database
        replies = self.get_ticket_replies(ticket_id, ticket)

        for i, reply in enumerate(replies):
            reply_frame = ttk.LabelFrame(scrollable_frame,
                                       text=f"{reply['username']} - {reply['created_at']}")
            reply_frame.pack(fill='x', padx=5, pady=5)

            # Reply content
            reply_text = scrolledtext.ScrolledText(reply_frame, height=4, wrap='word', state='disabled')
            reply_text.pack(fill='x', padx=5, pady=5)
            reply_text.config(state='normal')
            reply_text.insert('1.0', reply['message'])
            reply_text.config(state='disabled')

            # Internal note indicator (the service only returns internal
            # notes to the staff working the ticket)
            if reply.get('is_internal'):
                internal_label = ttk.Label(reply_frame, text=_t('gui.pastoral.helpdesk.ticket_view.labels.internal_note', default="(Internal Note)"), style='Warning.TLabel')
                internal_label.pack()

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    except Exception as e:
        ttk.Label(self.replies_frame, text=f"Error loading replies: {str(e)}",
                 style='Error.TLabel').pack()

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_ticket_replies = load_ticket_replies

def get_ticket_replies(self, ticket_id, ticket=None):
    """The conversation the signed-in person may see — Student Support
    replies and Helpdesk replies in one thread, internal notes only for the
    staff working the ticket (ticket service ``get_ticket``)."""
    if ticket is None:
        ticket = T.svc.get_ticket(T.actor(self), ticket_id)
    return [{
        **r,
        'username': r.get('responder_username') or r.get('responder_role') or 'system',
        'created_at': r.get('response_datetime') or '',
        'message': r.get('response_text') or '',
    } for r in ticket.get('responses') or []]

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_ticket_replies = get_ticket_replies

def refresh_replies_view(self, parent, ticket_id):
    """Refresh replies view"""
    self.load_ticket_replies(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.refresh_replies_view = refresh_replies_view

def create_ticket_actions_view(self, parent, ticket_id, ticket_data):
    """Create ticket actions view"""
    actions_frame = ttk.LabelFrame(parent, text=_t('gui.pastoral.helpdesk.ticket_view.labels.available_actions', default="Available Actions"))
    actions_frame.pack(fill='x', padx=10, pady=10)

    # Reply action
    if self.has_permission('reply_to_own_ticket') or self.has_permission('manage_tickets'):
        ttk.Button(actions_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.add_reply', default="Add Reply"),
                  command=lambda: self.show_reply_dialog(ticket_id)).pack(pady=5)

    # Admin actions
    if self.has_permission('manage_tickets'):
        ttk.Button(actions_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.change_status', default="Change Status"),
                  command=lambda: self.show_status_dialog(ticket_id)).pack(pady=5)
        ttk.Button(actions_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.assign_ticket', default="Assign Ticket"),
                  command=lambda: self.show_assign_dialog(ticket_id)).pack(pady=5)
        ttk.Button(actions_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.add_internal_note', default="Add Internal Note"),
                  command=lambda: self.show_internal_note_dialog(ticket_id)).pack(pady=5)

    # Working the ticket together: links, time, followers, major incidents
    if T.is_case_worker(self):
        for label, tool in ((_t('gui.pastoral.helpdesk.ticket_view.buttons.linked_tickets', default="Linked Tickets"), 'links'),
                            (_t('gui.pastoral.helpdesk.ticket_view.buttons.time_spent', default="Time Spent"), 'time'),
                            (_t('gui.pastoral.helpdesk.ticket_view.buttons.followers', default="Followers"), 'followers'),
                            (_t('gui.pastoral.helpdesk.ticket_view.buttons.add_to_incident', default="Add to Incident"), 'incident')):
            ttk.Button(actions_frame, text=label,
                       command=lambda tool=tool: self.show_ticket_tool(ticket_id, tool)).pack(pady=5)

    # Administrators: delete outright (created in error, duplicate, spam, test)
    if T.ss_auth.is_admin(T.actor(self)):
        ttk.Button(actions_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.delete_ticket', default="Delete Ticket Permanently"),
                  command=lambda: self.delete_ticket_permanently(ticket_id, parent)).pack(pady=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_ticket_actions_view = create_ticket_actions_view


def show_ticket_tool(self, ticket_id, tool):
    """One of the shared support tools for a ticket ('links', 'time',
    'followers', 'incident')."""
    from education_system.systems.university.domains.student_support.interfaces.gui.helpdesk import support_tools
    actor = T.actor(self)
    if tool == 'links':
        support_tools.open_links(self.root, actor, ticket_id, open_ticket=self.show_ticket_details)
    elif tool == 'time':
        support_tools.open_time(self.root, actor, ticket_id)
    elif tool == 'followers':
        support_tools.open_followers(self.root, actor, ticket_id)
    elif tool == 'incident':
        support_tools.add_to_incident(self.root, actor, ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_ticket_tool = show_ticket_tool


def delete_ticket_permanently(self, ticket_id, parent=None):
    """Delete a ticket and its replies/attachments (``gdpr.delete_ticket``):
    administrators only; safeguarding tickets and legal holds are refused."""
    from education_system.systems.university.domains.student_support.domain.student_support import gdpr
    owner = parent.winfo_toplevel() if parent is not None else self.root
    reason = simpledialog.askstring(
        _t('gui.pastoral.helpdesk.ticket_view.dialogs.delete_title', default="Delete Ticket"),
        _t('gui.pastoral.helpdesk.ticket_view.dialogs.delete_reason',
           default="Ticket #{ticket_id} and its replies and attachments will be removed for good.\n\n"
                   "Reason ({reasons}):").format(ticket_id=ticket_id, reasons=", ".join(gdpr.DELETE_REASONS)),
        parent=owner)
    if not reason:
        return
    detail = ""
    if reason.strip().lower() == 'other':
        detail = simpledialog.askstring(_t('gui.pastoral.helpdesk.ticket_view.dialogs.delete_title', default="Delete Ticket"),
                                        _t('gui.pastoral.helpdesk.ticket_view.dialogs.delete_detail', default="Why is it being deleted?"),
                                        parent=owner) or ""
    confirm = simpledialog.askstring(
        _t('gui.pastoral.helpdesk.ticket_view.dialogs.delete_title', default="Delete Ticket"),
        _t('gui.pastoral.helpdesk.ticket_view.dialogs.delete_confirm', default="Type the ticket number ({ticket_id}) to confirm:").format(ticket_id=ticket_id),
        parent=owner)
    if confirm is None:
        return
    try:
        gdpr.delete_ticket(T.actor(self), ticket_id, reason, confirm_ticket_id=confirm, detail=detail)
    except Exception as e:
        T.show_error(e, parent=owner)
        return
    messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_view.dialogs.deleted_title', default="Deleted"),
                        _t('gui.pastoral.helpdesk.ticket_view.dialogs.deleted', default="Ticket #{ticket_id} was deleted.").format(ticket_id=ticket_id),
                        parent=owner)
    if parent is not None:
        try:
            parent.winfo_toplevel().destroy()
        except tk.TclError:
            pass
    self._refresh_ticket_lists()

# Attach method to HelpdeskGUI class
HelpdeskGUI.delete_ticket_permanently = delete_ticket_permanently

def view_ticket_detail_enhanced_gui(self, ticket_id):
    """View complete ticket details with all information"""
    try:
        ticket = T.svc.get_ticket(T.actor(self), ticket_id)
    except Exception as e:
        T.show_error(e)
        return
    try:
        # Create detail window
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Ticket #{ticket_id} - {ticket['subject']}")
        T.size_window(detail_window)
        T.banner(detail_window, ticket)

        # Main scrollable frame
        main_canvas = tk.Canvas(detail_window)
        scrollbar = ttk.Scrollbar(detail_window, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        # Ticket header
        header_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.pastoral.helpdesk.ticket_view.labels.ticket_information', default="Ticket Information"), padding="10")
        header_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(header_frame, text=f"Ticket ID: #{ticket['ticket_id']}", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Subject: {ticket['subject']}", font=('Arial', 11)).pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Status: {ticket.get('status_label') or T.status_label(ticket['status'])}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Priority: {str(ticket.get('priority') or '').upper()} | Impact: {str(ticket.get('impact') or '').upper()} | Urgency: {str(ticket.get('urgency') or '').upper()}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Category: {ticket['category']}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Submitted by: {T.requester_of(ticket)}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Assigned to: {ticket.get('assigned_to') or 'Unassigned'}").pack(anchor=tk.W)
        if T.tier_badge(ticket):
            ttk.Label(header_frame, text=f"Confidentiality: {T.tier_badge(ticket)}", style='Warning.TLabel').pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"SLA: {T.sla_label(ticket) or 'N/A'}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Created: {ticket['created_at']}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Updated: {ticket['updated_at']}").pack(anchor=tk.W)

        if ticket.get('sla_due_at') or ticket.get('due_date'):
            ttk.Label(header_frame, text=f"Due Date: {ticket.get('sla_due_at') or ticket.get('due_date')}").pack(anchor=tk.W)

        # Message
        msg_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.pastoral.helpdesk.ticket_view.labels.message', default="Message"), padding="10")
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        msg_text = scrolledtext.ScrolledText(msg_frame, wrap=tk.WORD, height=5)
        msg_text.pack(fill=tk.BOTH, expand=True)
        msg_text.insert('1.0', ticket.get('description') or '')
        msg_text.config(state=tk.DISABLED)

        # Replies
        self.display_ticket_replies_gui(ticket_id, scrollable_frame, ticket)

        # Time tracking
        self.display_time_tracking_gui(ticket_id, scrollable_frame)

        # Escalation history
        self.display_escalation_history_gui(ticket_id, scrollable_frame)

        # Linked tickets
        self.display_linked_tickets_gui(ticket_id, scrollable_frame)

        # Audit trail (admin only)
        if self.auth.has_permission('view_all_tickets'):
            self.display_audit_trail_gui(ticket_id, scrollable_frame)

        # Action buttons
        action_frame = ttk.Frame(scrollable_frame)
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        staff = T.is_case_worker(self)
        if staff or ticket.get('access') == 'owner':
            ttk.Button(action_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.reply', default="Reply"), command=lambda: self.reply_to_ticket_enhanced_gui(ticket_id, False)).pack(side=tk.LEFT, padx=5)

        if staff:
            ttk.Button(action_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.internal_note', default="Internal Note"), command=lambda: self.reply_to_ticket_enhanced_gui(ticket_id, True)).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.add_time_entry', default="Add Time Entry"), command=lambda: self.add_time_entry_gui(ticket_id)).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.link_ticket', default="Link Ticket"), command=lambda: self.link_tickets_gui(ticket_id)).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.followers', default="Followers"), command=lambda: self.show_ticket_tool(ticket_id, 'followers')).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.add_to_incident', default="Add to Incident"), command=lambda: self.show_ticket_tool(ticket_id, 'incident')).pack(side=tk.LEFT, padx=5)

        ttk.Button(action_frame, text=_t('gui.pastoral.helpdesk.ticket_view.buttons.close', default="Close"), command=detail_window.destroy).pack(side=tk.RIGHT, padx=5)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    except Exception as e:
        T.show_error(e)

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_ticket_detail_enhanced_gui = view_ticket_detail_enhanced_gui

def view_ticket_from_tree(self, tree):
    """View ticket details from treeview selection"""
    selection = tree.selection()
    if not selection:
        messagebox.showwarning(_t('gui.pastoral.helpdesk.ticket_view.dialogs.no_selection', default="No Selection"), _t('gui.pastoral.helpdesk.ticket_view.dialogs.please_select_a_ticket_to_view', default="Please select a ticket to view."))
        return

    item = tree.item(selection[0])
    ticket_id = item['values'][0]
    self.view_ticket_detail_enhanced_gui(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_ticket_from_tree = view_ticket_from_tree

def display_ticket_replies_gui(self, ticket_id, parent_frame, ticket=None):
    """Display the conversation (internal notes only reach the staff working
    the ticket — the service filters them)."""
    try:
        replies = self.get_ticket_replies(ticket_id, ticket)
    except Exception as e:
        T.show_error(e)
        return
    if not replies:
        return

    replies_frame = ttk.LabelFrame(parent_frame, text=_t('gui.pastoral.helpdesk.ticket_view.labels.conversation_history', default="Conversation History"), padding="10")
    replies_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    for reply in replies:
        is_internal = bool(reply.get('is_internal'))
        reply_type = "Internal Note" if is_internal else "Reply"

        reply_item_frame = ttk.Frame(replies_frame)
        reply_item_frame.pack(fill=tk.X, pady=5)

        icon = "🔒" if is_internal else "💬"
        header_text = (f"{icon} {reply_type} from {reply['username']} "
                       f"({reply.get('responder_role') or 'staff'}) at {reply['created_at']}")

        ttk.Label(reply_item_frame, text=header_text, font=('Arial', 9, 'bold')).pack(anchor=tk.W)

        msg_text = tk.Text(reply_item_frame, wrap=tk.WORD, height=3, relief=tk.FLAT, bg='#f0f0f0')
        msg_text.pack(fill=tk.X, pady=2)
        msg_text.insert('1.0', reply['message'])
        msg_text.config(state=tk.DISABLED)

        ttk.Separator(replies_frame, orient='horizontal').pack(fill=tk.X, pady=2)

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_ticket_replies_gui = display_ticket_replies_gui

def display_time_tracking_gui(self, ticket_id, parent_frame):
    """Display time tracking information (staff working the ticket)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        collaboration,
    )
    try:
        data = collaboration.time_entries(T.actor(self), ticket_id)
    except (PermissionError, ValueError):
        return
    if not data['entries']:
        return

    time_frame = ttk.LabelFrame(parent_frame, text=_t('gui.pastoral.helpdesk.ticket_view.labels.time_tracking', default="Time Tracking"), padding="10")
    time_frame.pack(fill=tk.X, padx=10, pady=5)

    total_time = 0
    billable_time = 0
    for entry in data['entries']:
        duration = (entry['duration_minutes'] or 0) / 60
        total_time += duration
        if entry['billable']:
            billable_time += duration
        billable_text = " (Billable)" if entry['billable'] else ""
        entry_text = f"⏱️  {entry['username'] or 'Unknown'}: {duration:.2f} hours{billable_text}"
        if entry['description']:
            entry_text += f"\n   Description: {entry['description']}"
        ttk.Label(time_frame, text=entry_text).pack(anchor=tk.W, pady=2)

    ttk.Separator(time_frame, orient='horizontal').pack(fill=tk.X, pady=5)
    ttk.Label(time_frame, text=f"Total Time: {total_time:.2f} hours", font=('Arial', 9, 'bold')).pack(anchor=tk.W)
    ttk.Label(time_frame, text=f"Billable Time: {billable_time:.2f} hours", font=('Arial', 9, 'bold')).pack(anchor=tk.W)

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_time_tracking_gui = display_time_tracking_gui

def display_escalation_history_gui(self, ticket_id, parent_frame):
    """Display escalation history"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT e.*, u1.username as escalated_to_user, u2.username as escalated_by_user
            FROM ticket_escalations e
            LEFT JOIN users u1 ON e.escalated_to = u1.id
            LEFT JOIN users u2 ON e.escalated_by = u2.id
            WHERE e.ticket_id = ?
            ORDER BY e.created_at
        ''', (ticket_id,))

        escalations = cursor.fetchall()
        conn.close()

        if not escalations:
            return

        esc_frame = ttk.LabelFrame(parent_frame, text=_t('gui.pastoral.helpdesk.ticket_view.labels.escalation_history', default="Escalation History"), padding="10")
        esc_frame.pack(fill=tk.X, padx=10, pady=5)

        for esc in escalations:
            status = "Resolved" if esc[6] else "Open"
            escalated_by = esc[-1] or "System"

            esc_text = f"🔺 Level {esc[2]} - Escalated to {esc[-2]} by {escalated_by}\n"
            esc_text += f"   Reason: {esc[4]}\n"
            esc_text += f"   Date: {esc[7]} - Status: {status}"

            ttk.Label(esc_frame, text=esc_text).pack(anchor=tk.W, pady=2)

    except sqlite3.Error as e:
        print(f"Error loading escalation history: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_escalation_history_gui = display_escalation_history_gui

def display_audit_trail_gui(self, ticket_id, parent_frame):
    """Display audit trail for admins"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT al.*, u.username
            FROM ticket_audit_log al
            JOIN users u ON al.user_id = u.id
            WHERE al.ticket_id = ?
            ORDER BY al.created_at DESC
            LIMIT 10
        ''', (ticket_id,))

        audit_entries = cursor.fetchall()
        conn.close()

        if not audit_entries:
            return

        audit_frame = ttk.LabelFrame(parent_frame, text=_t('gui.pastoral.helpdesk.ticket_view.labels.recent_activity_audit_trail', default="Recent Activity (Audit Trail)"), padding="10")
        audit_frame.pack(fill=tk.X, padx=10, pady=5)

        for entry in audit_entries:
            audit_text = f"📋 {entry[3]} by {entry[-1]} at {entry[8]}"

            if entry[4]:  # old_values
                try:
                    old_vals = json.loads(entry[4])
                    if old_vals:
                        audit_text += f"\n   Previous: {old_vals}"
                except json.JSONDecodeError:
                    pass

            if entry[5]:  # new_values
                try:
                    new_vals = json.loads(entry[5])
                    if new_vals:
                        audit_text += f"\n   New: {new_vals}"
                except json.JSONDecodeError:
                    pass

            ttk.Label(audit_frame, text=audit_text).pack(anchor=tk.W, pady=2)

    except sqlite3.Error as e:
        print(f"Error loading audit trail: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_audit_trail_gui = display_audit_trail_gui

def display_linked_tickets_gui(self, ticket_id, parent_frame):
    """Display linked tickets (and the followers) for the staff working the ticket."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        collaboration,
    )
    actor = T.actor(self)
    try:
        links = collaboration.list_links(actor, ticket_id)
    except (PermissionError, ValueError):
        return
    if links:
        links_frame = ttk.LabelFrame(parent_frame, text=_t('gui.pastoral.helpdesk.ticket_view.labels.linked_tickets', default="Linked Tickets"), padding="10")
        links_frame.pack(fill=tk.X, padx=10, pady=5)
        for link in links:
            # The linked ticket's subject only for those who may see it.
            about = (f"{link['subject']} ({link['status']})" if link['visible'] else
                     _t('gui.pastoral.helpdesk.ticket_view.labels.no_access', default="(not available to you)"))
            ttk.Label(links_frame, text=f"🔗 {link['label']} #{link['ticket_id']}: {about}").pack(anchor=tk.W, pady=2)
    try:
        followers = collaboration.list_followers(actor, ticket_id)
    except (PermissionError, ValueError):
        followers = []
    if followers:
        ttk.Label(parent_frame, text="Followers: " + ", ".join(f['username'] for f in followers)).pack(anchor=tk.W, padx=12, pady=2)

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_linked_tickets_gui = display_linked_tickets_gui

