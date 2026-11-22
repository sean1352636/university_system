
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
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

def create_my_tickets_tab(self):
    """Create my tickets tab"""
    tickets_frame = ttk.Frame(self.notebook)
    self.notebook.add(tickets_frame, text=_t('gui.pastoral.helpdesk.tickets_my.tabs.my_tickets', default="My Tickets"))

    # Toolbar
    toolbar = ttk.Frame(tickets_frame)
    toolbar.pack(fill='x', padx=10, pady=5)

    ttk.Button(toolbar, text=_t('gui.pastoral.helpdesk.tickets_my.buttons.refresh', default="Refresh"), command=self.refresh_my_tickets).pack(side='left', padx=5)
    ttk.Button(toolbar, text=_t('gui.pastoral.helpdesk.tickets_my.buttons.new_ticket', default="New Ticket"), command=self.show_create_ticket,
              style='Primary.TButton').pack(side='left', padx=5)

    # Filter frame
    filter_frame = ttk.LabelFrame(tickets_frame, text=_t('gui.pastoral.helpdesk.tickets_my.labels.filters', default="Filters"))
    filter_frame.pack(fill='x', padx=10, pady=5)

    filter_grid = ttk.Frame(filter_frame)
    filter_grid.pack(fill='x', padx=5, pady=5)

    ttk.Label(filter_grid, text=_t('gui.pastoral.helpdesk.tickets_my.labels.status', default="Status:")).grid(row=0, column=0, padx=5)
    self.my_tickets_status_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.tickets_my.values.all', default="all"))
    status_combo = ttk.Combobox(filter_grid, textvariable=self.my_tickets_status_var,
                               values=T.status_labels(with_all=True),
                               state="readonly")
    status_combo.grid(row=0, column=1, padx=5)
    status_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_my_tickets())

    # Tickets list
    self.my_tickets_frame = ttk.Frame(tickets_frame)
    self.my_tickets_frame.pack(fill='both', expand=True, padx=10, pady=5)

    self.create_my_tickets_list()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_my_tickets_tab = create_my_tickets_tab

def create_my_tickets_list(self):
    """Create my tickets list"""
    # Clear existing widgets
    for widget in self.my_tickets_frame.winfo_children():
        widget.destroy()

    # Create treeview
    columns = ('ID', 'Subject', 'Category', 'Status', 'Priority', 'Tier', 'SLA', 'Created', 'Updated')
    self.my_tickets_tree = ttk.Treeview(self.my_tickets_frame, columns=columns, show='headings')

    # Configure columns
    column_widths = {'ID': 50, 'Subject': 200, 'Category': 120, 'Status': 120,
                    'Priority': 80, 'Tier': 100, 'SLA': 120, 'Created': 120, 'Updated': 120}

    for col in columns:
        self.my_tickets_tree.heading(col, text=col)
        self.my_tickets_tree.column(col, width=column_widths.get(col, 100))

    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(self.my_tickets_frame, orient='vertical',
                               command=self.my_tickets_tree.yview)
    h_scrollbar = ttk.Scrollbar(self.my_tickets_frame, orient='horizontal',
                               command=self.my_tickets_tree.xview)

    self.my_tickets_tree.configure(yscrollcommand=v_scrollbar.set,
                                  xscrollcommand=h_scrollbar.set)

    # Pack widgets
    self.my_tickets_tree.grid(row=0, column=0, sticky='nsew')
    v_scrollbar.grid(row=0, column=1, sticky='ns')
    h_scrollbar.grid(row=1, column=0, sticky='ew')

    self.my_tickets_frame.grid_rowconfigure(0, weight=1)
    self.my_tickets_frame.grid_columnconfigure(0, weight=1)

    # Bind double-click to view ticket
    self.my_tickets_tree.bind('<Double-1>', self.on_my_ticket_double_click)

    # Context menu
    self.create_my_tickets_context_menu()

    # Load data
    self.refresh_my_tickets()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_my_tickets_list = create_my_tickets_list

def create_my_tickets_context_menu(self):
    """Create context menu for my tickets"""
    self.my_tickets_context_menu = tk.Menu(self.root, tearoff=0)
    self.my_tickets_context_menu.add_command(label=_t('gui.pastoral.helpdesk.tickets_my.menus.view_details', default="View Details"), command=self.view_selected_ticket)
    self.my_tickets_context_menu.add_command(label=_t('gui.pastoral.helpdesk.tickets_my.menus.reply', default="Reply"), command=self.reply_to_selected_ticket)
    self.my_tickets_context_menu.add_separator()
    self.my_tickets_context_menu.add_command(label=_t('gui.pastoral.helpdesk.tickets_my.menus.refresh', default="Refresh"), command=self.refresh_my_tickets)

    self.my_tickets_tree.bind('<Button-3>', self.show_my_tickets_context_menu)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_my_tickets_context_menu = create_my_tickets_context_menu

def show_my_tickets_context_menu(self, event):
    """Show context menu for my tickets"""
    try:
        self.my_tickets_context_menu.tk_popup(event.x_root, event.y_root)
    finally:
        self.my_tickets_context_menu.grab_release()

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_my_tickets_context_menu = show_my_tickets_context_menu

def refresh_my_tickets(self):
    """Refresh my tickets list"""
    try:
        # Clear existing items
        for item in self.my_tickets_tree.get_children():
            self.my_tickets_tree.delete(item)

        # Get tickets from database
        tickets = self.get_my_tickets()

        # Populate treeview
        for ticket in tickets:
            # Safely get values with defaults for None
            subject = ticket.get('subject') or 'No Subject'
            category = ticket.get('category') or 'General'
            priority = ticket.get('priority') or 'medium'
            created_at = ticket.get('created_at') or ''
            updated_at = ticket.get('updated_at') or ''

            # Format dates
            created = created_at[:16] if created_at else ''
            updated = updated_at[:16] if updated_at else ''

            self.my_tickets_tree.insert('', 'end', values=(
                ticket.get('ticket_id', 'N/A'),
                subject[:50] if subject else 'No Subject',
                category,
                ticket.get('status_label') or T.status_label(ticket.get('status')),
                str(priority).title(),
                T.tier_badge(ticket),
                T.sla_label(ticket),
                created,
                updated
            ))

    except Exception as e:
        T.show_error(e)

# Attach method to HelpdeskGUI class
HelpdeskGUI.refresh_my_tickets = refresh_my_tickets

def get_my_tickets(self):
    """The tickets the signed-in person raised (from either front-end), via
    the ticket service — newest first, every page."""
    if self.current_user is None:
        return []
    try:
        status = T.status_from_label(self.my_tickets_status_var.get())
        filters = {'status': status} if status else None
        return list(T.hd.iter_tickets(T.actor(self), filters, mine=True))
    except Exception as e:
        T.show_error(e)
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_my_tickets = get_my_tickets

def on_my_ticket_double_click(self, event):
    """Handle double-click on my ticket"""
    self.view_selected_ticket()

# Attach method to HelpdeskGUI class
HelpdeskGUI.on_my_ticket_double_click = on_my_ticket_double_click

def view_selected_ticket(self):
    """View selected ticket details"""
    selection = self.my_tickets_tree.selection()
    if not selection:
        messagebox.showwarning(_t('gui.pastoral.helpdesk.tickets_my.dialogs.warning', default="Warning"), _t('gui.pastoral.helpdesk.tickets_my.dialogs.please_select_a_ticket', default="Please select a ticket"))
        return

    item = self.my_tickets_tree.item(selection[0])
    ticket_id = item['values'][0]

    self.show_ticket_details(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_selected_ticket = view_selected_ticket

def reply_to_selected_ticket(self):
    """Reply to selected ticket"""
    selection = self.my_tickets_tree.selection()
    if not selection:
        messagebox.showwarning(_t('gui.pastoral.helpdesk.tickets_my.dialogs.warning', default="Warning"), _t('gui.pastoral.helpdesk.tickets_my.dialogs.please_select_a_ticket', default="Please select a ticket"))
        return

    item = self.my_tickets_tree.item(selection[0])
    ticket_id = item['values'][0]

    self.show_reply_dialog(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.reply_to_selected_ticket = reply_to_selected_ticket

def show_my_tickets(self):
    """Switch to my tickets tab"""
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') == 'My Tickets':
            self.notebook.select(i)
            break

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_my_tickets = show_my_tickets

