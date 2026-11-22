
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

def create_all_tickets_tab(self):
    """Create all tickets tab (admin only)"""
    if not self.has_permission('view_all_tickets'):
        return

    all_tickets_frame = ttk.Frame(self.notebook)
    self.notebook.add(all_tickets_frame, text=_t('gui.pastoral.helpdesk.tickets_all.tabs.all_tickets', default="All Tickets"))

    # Toolbar
    toolbar = ttk.Frame(all_tickets_frame)
    toolbar.pack(fill='x', padx=10, pady=5)

    ttk.Button(toolbar, text=_t('gui.pastoral.helpdesk.tickets_all.buttons.refresh', default="Refresh"), command=self.refresh_all_tickets).pack(side='left', padx=5)
    ttk.Button(toolbar, text=_t('gui.pastoral.helpdesk.tickets_all.buttons.bulk_actions', default="Bulk Actions"), command=self.show_bulk_actions).pack(side='left', padx=5)

    # Filters
    filter_frame = ttk.LabelFrame(all_tickets_frame, text=_t('gui.pastoral.helpdesk.tickets_all.labels.filters', default="Filters"))
    filter_frame.pack(fill='x', padx=10, pady=5)

    filter_grid = ttk.Frame(filter_frame)
    filter_grid.pack(fill='x', padx=5, pady=5)

    # Status filter
    ttk.Label(filter_grid, text=_t('gui.pastoral.helpdesk.tickets_all.labels.status', default="Status:")).grid(row=0, column=0, padx=5)
    self.all_tickets_status_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.tickets_all.values.all', default="all"))
    status_combo = ttk.Combobox(filter_grid, textvariable=self.all_tickets_status_var,
                               values=T.status_labels(with_all=True),
                               state="readonly")
    status_combo.grid(row=0, column=1, padx=5)

    # Priority filter
    ttk.Label(filter_grid, text=_t('gui.pastoral.helpdesk.tickets_all.labels.priority', default="Priority:")).grid(row=0, column=2, padx=5)
    self.all_tickets_priority_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.tickets_all.values.all', default="all"))
    priority_combo = ttk.Combobox(filter_grid, textvariable=self.all_tickets_priority_var,
                                 values=["all", "low", "medium", "high"],
                                 state="readonly")
    priority_combo.grid(row=0, column=3, padx=5)

    # Assignment filter
    ttk.Label(filter_grid, text=_t('gui.pastoral.helpdesk.tickets_all.labels.assignment', default="Assignment:")).grid(row=0, column=4, padx=5)
    self.all_tickets_assignment_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.tickets_all.values.all', default="all"))
    assignment_combo = ttk.Combobox(filter_grid, textvariable=self.all_tickets_assignment_var,
                                   values=["all", "assigned", "unassigned"],
                                   state="readonly")
    assignment_combo.grid(row=0, column=5, padx=5)

    # Bind filter changes
    for combo in [status_combo, priority_combo, assignment_combo]:
        combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_all_tickets())

    # Apply filters button
    ttk.Button(filter_grid, text=_t('gui.pastoral.helpdesk.tickets_all.buttons.apply_filters', default="Apply Filters"),
              command=self.refresh_all_tickets).grid(row=0, column=6, padx=10)

    # Tickets list
    self.all_tickets_frame = ttk.Frame(all_tickets_frame)
    self.all_tickets_frame.pack(fill='both', expand=True, padx=10, pady=5)

    self.create_all_tickets_list()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_all_tickets_tab = create_all_tickets_tab

def create_all_tickets_list(self):
    """Create all tickets list"""
    # Clear existing widgets
    for widget in self.all_tickets_frame.winfo_children():
        widget.destroy()

    # Create treeview with checkboxes for selection
    columns = ('Select', 'ID', 'Subject', 'Submitter', 'Assignee', 'Category', 'Status', 'Priority', 'Tier', 'SLA', 'Created', 'Updated')
    self.all_tickets_tree = ttk.Treeview(self.all_tickets_frame, columns=columns, show='headings')

    # Configure columns
    column_widths = {'Select': 50, 'ID': 50, 'Subject': 200, 'Submitter': 100, 'Assignee': 100,
                    'Category': 120, 'Status': 120, 'Priority': 80, 'Tier': 100, 'SLA': 120,
                    'Created': 120, 'Updated': 120}

    for col in columns:
        self.all_tickets_tree.heading(col, text=col)
        self.all_tickets_tree.column(col, width=column_widths.get(col, 100))

    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(self.all_tickets_frame, orient='vertical',
                               command=self.all_tickets_tree.yview)
    h_scrollbar = ttk.Scrollbar(self.all_tickets_frame, orient='horizontal',
                               command=self.all_tickets_tree.xview)

    self.all_tickets_tree.configure(yscrollcommand=v_scrollbar.set,
                                   xscrollcommand=h_scrollbar.set)

    # Pack widgets
    self.all_tickets_tree.grid(row=0, column=0, sticky='nsew')
    v_scrollbar.grid(row=0, column=1, sticky='ns')
    h_scrollbar.grid(row=1, column=0, sticky='ew')

    self.all_tickets_frame.grid_rowconfigure(0, weight=1)
    self.all_tickets_frame.grid_columnconfigure(0, weight=1)

    # Bind events
    self.all_tickets_tree.bind('<Double-1>', self.on_all_ticket_double_click)
    self.all_tickets_tree.bind('<Button-1>', self.on_all_ticket_click)

    # Context menu
    self.create_all_tickets_context_menu()

    # Track selected items
    self.selected_tickets = set()

    # Load data
    self.refresh_all_tickets()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_all_tickets_list = create_all_tickets_list

def create_all_tickets_context_menu(self):
    """Create context menu for all tickets"""
    self.all_tickets_context_menu = tk.Menu(self.root, tearoff=0)
    self.all_tickets_context_menu.add_command(label=_t('gui.pastoral.helpdesk.tickets_all.menus.view_details', default="View Details"), command=self.view_selected_all_ticket)
    self.all_tickets_context_menu.add_command(label=_t('gui.pastoral.helpdesk.tickets_all.menus.assign', default="Assign"), command=self.assign_selected_ticket)
    self.all_tickets_context_menu.add_command(label=_t('gui.pastoral.helpdesk.tickets_all.menus.change_status', default="Change Status"), command=self.change_status_selected_ticket)
    self.all_tickets_context_menu.add_separator()
    self.all_tickets_context_menu.add_command(label=_t('gui.pastoral.helpdesk.tickets_all.menus.select_all', default="Select All"), command=self.select_all_tickets)
    self.all_tickets_context_menu.add_command(label=_t('gui.pastoral.helpdesk.tickets_all.menus.deselect_all', default="Deselect All"), command=self.deselect_all_tickets)
    self.all_tickets_context_menu.add_separator()
    self.all_tickets_context_menu.add_command(label=_t('gui.pastoral.helpdesk.tickets_all.menus.refresh', default="Refresh"), command=self.refresh_all_tickets)

    self.all_tickets_tree.bind('<Button-3>', self.show_all_tickets_context_menu)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_all_tickets_context_menu = create_all_tickets_context_menu

def show_all_tickets_context_menu(self, event):
    """Show context menu for all tickets"""
    try:
        self.all_tickets_context_menu.tk_popup(event.x_root, event.y_root)
    finally:
        self.all_tickets_context_menu.grab_release()

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_all_tickets_context_menu = show_all_tickets_context_menu

def on_all_ticket_click(self, event):
    """Handle click on all tickets tree"""
    region = self.all_tickets_tree.identify("region", event.x, event.y)
    if region == "cell":
        column = self.all_tickets_tree.identify_column(event.x)
        if column == '#1':  # Select column
            item = self.all_tickets_tree.identify_row(event.y)
            if item:
                self.toggle_ticket_selection(item)

# Attach method to HelpdeskGUI class
HelpdeskGUI.on_all_ticket_click = on_all_ticket_click

def toggle_ticket_selection(self, item):
    """Toggle ticket selection"""
    values = list(self.all_tickets_tree.item(item, 'values'))
    ticket_id = values[1]

    if values[0] == '☐':  # Not selected
        values[0] = '☑'
        self.selected_tickets.add(ticket_id)
    else:  # Selected
        values[0] = '☐'
        self.selected_tickets.discard(ticket_id)

    self.all_tickets_tree.item(item, values=values)

# Attach method to HelpdeskGUI class
HelpdeskGUI.toggle_ticket_selection = toggle_ticket_selection

def select_all_tickets(self):
    """Select all visible tickets"""
    for item in self.all_tickets_tree.get_children():
        values = list(self.all_tickets_tree.item(item, 'values'))
        if values[0] == '☐':
            values[0] = '☑'
            self.selected_tickets.add(values[1])
            self.all_tickets_tree.item(item, values=values)

# Attach method to HelpdeskGUI class
HelpdeskGUI.select_all_tickets = select_all_tickets

def deselect_all_tickets(self):
    """Deselect all tickets"""
    for item in self.all_tickets_tree.get_children():
        values = list(self.all_tickets_tree.item(item, 'values'))
        if values[0] == '☑':
            values[0] = '☐'
            self.all_tickets_tree.item(item, values=values)
    self.selected_tickets.clear()

# Attach method to HelpdeskGUI class
HelpdeskGUI.deselect_all_tickets = deselect_all_tickets

def refresh_all_tickets(self):
    """Refresh all tickets list"""
    try:
        # Clear existing items and selections
        for item in self.all_tickets_tree.get_children():
            self.all_tickets_tree.delete(item)
        self.selected_tickets.clear()

        # Get tickets from database
        tickets = self.get_all_tickets()

        # Populate treeview
        for ticket in tickets:
            # Safely get values with defaults for None
            subject = ticket.get('subject') or 'No Subject'
            submitter = T.requester_of(ticket)
            assignee = ticket.get('assigned_to') or 'Unassigned'
            category = ticket.get('category') or 'General'
            priority = ticket.get('priority') or 'medium'
            created_at = ticket.get('created_at') or ''
            updated_at = ticket.get('updated_at') or ''

            # Format dates
            created = created_at[:16] if created_at else ''
            updated = updated_at[:16] if updated_at else ''

            self.all_tickets_tree.insert('', 'end', values=(
                '☐',  # Checkbox
                ticket.get('ticket_id', 'N/A'),
                subject[:40] if subject else 'No Subject',
                submitter[:15] if submitter else 'Unknown',
                assignee[:15] if assignee else 'Unassigned',
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
HelpdeskGUI.refresh_all_tickets = refresh_all_tickets

def get_all_tickets(self):
    """Every ticket the signed-in staff member may work (their teams and
    tiers — the ticket service decides), filtered as the bar asks.
    Confidential text stays sealed in lists."""
    try:
        filters = {}
        status = T.status_from_label(self.all_tickets_status_var.get())
        if status:
            filters['status'] = status
        priority_filter = self.all_tickets_priority_var.get()
        if priority_filter and priority_filter != "all":
            filters['priority'] = priority_filter
        assignment_filter = self.all_tickets_assignment_var.get()
        if assignment_filter == "unassigned":
            filters['unassigned'] = True
        tickets = list(T.hd.iter_tickets(T.actor(self), filters or None))
        if assignment_filter == "assigned":
            tickets = [t for t in tickets if t.get('assigned_to')]
        tickets.sort(key=lambda t: str(t.get('updated_at') or t.get('created_at') or ''),
                     reverse=True)
        return tickets
    except Exception as e:
        T.show_error(e)
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_all_tickets = get_all_tickets

def on_all_ticket_double_click(self, event):
    """Handle double-click on all tickets"""
    region = self.all_tickets_tree.identify("region", event.x, event.y)
    if region == "cell":
        column = self.all_tickets_tree.identify_column(event.x)
        if column != '#1':  # Not the select column
            self.view_selected_all_ticket()

# Attach method to HelpdeskGUI class
HelpdeskGUI.on_all_ticket_double_click = on_all_ticket_double_click

def view_selected_all_ticket(self):
    """View selected ticket from all tickets"""
    selection = self.all_tickets_tree.selection()
    if not selection:
        messagebox.showwarning(_t('gui.pastoral.helpdesk.tickets_all.dialogs.warning', default="Warning"), _t('gui.pastoral.helpdesk.tickets_all.dialogs.please_select_a_ticket', default="Please select a ticket"))
        return

    item = self.all_tickets_tree.item(selection[0])
    ticket_id = item['values'][1]

    self.show_ticket_details(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_selected_all_ticket = view_selected_all_ticket

def assign_selected_ticket(self):
    """Assign selected ticket"""
    selection = self.all_tickets_tree.selection()
    if not selection:
        messagebox.showwarning(_t('gui.pastoral.helpdesk.tickets_all.dialogs.warning', default="Warning"), _t('gui.pastoral.helpdesk.tickets_all.dialogs.please_select_a_ticket', default="Please select a ticket"))
        return

    item = self.all_tickets_tree.item(selection[0])
    ticket_id = item['values'][1]

    self.show_assign_dialog(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.assign_selected_ticket = assign_selected_ticket

def change_status_selected_ticket(self):
    """Change status of selected ticket"""
    selection = self.all_tickets_tree.selection()
    if not selection:
        messagebox.showwarning(_t('gui.pastoral.helpdesk.tickets_all.dialogs.warning', default="Warning"), _t('gui.pastoral.helpdesk.tickets_all.dialogs.please_select_a_ticket', default="Please select a ticket"))
        return

    item = self.all_tickets_tree.item(selection[0])
    ticket_id = item['values'][1]

    self.show_status_dialog(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.change_status_selected_ticket = change_status_selected_ticket

def show_bulk_actions(self):
    """Show bulk actions dialog"""
    if not self.selected_tickets:
        messagebox.showwarning(_t('gui.pastoral.helpdesk.tickets_all.dialogs.warning', default="Warning"), _t('gui.pastoral.helpdesk.tickets_all.dialogs.please_select_some_tickets_first', default="Please select some tickets first"))
        return

    bulk_window = tk.Toplevel(self.root)
    bulk_window.title(_t('gui.pastoral.helpdesk.tickets_all.windows.bulk_actions', default="Bulk Actions"))
    bulk_window.geometry("400x300")
    bulk_window.transient(self.root)
    bulk_window.grab_set()

    # Title
    ttk.Label(bulk_window, text=f"Bulk Actions ({len(self.selected_tickets)} tickets selected)",
             style='Heading.TLabel').pack(pady=10)

    # Actions frame
    actions_frame = ttk.LabelFrame(bulk_window, text=_t('gui.pastoral.helpdesk.tickets_all.labels.available_actions', default="Available Actions"))
    actions_frame.pack(fill='both', expand=True, padx=10, pady=10)

    # Bulk assign
    assign_frame = ttk.Frame(actions_frame)
    assign_frame.pack(fill='x', padx=5, pady=5)

    ttk.Label(assign_frame, text=_t('gui.pastoral.helpdesk.tickets_all.labels.assign_to', default="Assign to:")).pack(side='left')

    staff_list = self.get_available_staff()
    assign_var = tk.StringVar()
    assign_combo = ttk.Combobox(assign_frame, textvariable=assign_var, state="readonly")
    assign_combo['values'] = ["Unassigned"] + [f"{s['username']} ({s['role']})" for s in staff_list]
    assign_combo.pack(side='left', padx=5)

    ttk.Button(assign_frame, text=_t('gui.pastoral.helpdesk.tickets_all.buttons.assign', default="Assign"),
              command=lambda: self.bulk_assign_tickets(assign_var.get(), staff_list, bulk_window)).pack(side='left', padx=5)

    # Bulk status change
    status_frame = ttk.Frame(actions_frame)
    status_frame.pack(fill='x', padx=5, pady=5)

    ttk.Label(status_frame, text=_t('gui.pastoral.helpdesk.tickets_all.labels.change_status_to', default="Change status to:")).pack(side='left')

    status_var = tk.StringVar()
    status_combo = ttk.Combobox(status_frame, textvariable=status_var, state="readonly")
    status_combo['values'] = T.status_labels()
    status_combo.pack(side='left', padx=5)

    ttk.Button(status_frame, text=_t('gui.pastoral.helpdesk.tickets_all.buttons.change_status', default="Change Status"),
              command=lambda: self.bulk_change_status(status_var.get(), bulk_window)).pack(side='left', padx=5)

    # Close button
    ttk.Button(bulk_window, text=_t('gui.pastoral.helpdesk.tickets_all.buttons.close', default="Close"), command=bulk_window.destroy).pack(pady=10)

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_bulk_actions = show_bulk_actions

def bulk_assign_tickets(self, assign_text, staff_list, window):
    """Bulk assign tickets (by username) through the ticket service."""
    if not assign_text:
        messagebox.showerror(_t('gui.pastoral.helpdesk.tickets_all.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.tickets_all.dialogs.please_select_an_assignee', default="Please select an assignee"))
        return

    assignee = None
    if assign_text != "Unassigned":
        assignee = assign_text.split(' (')[0]

    ids = sorted(self.selected_tickets, key=str)
    try:
        done = T.svc.bulk_update(T.actor(self), ids, {'assigned_to': assignee})
    except Exception as e:
        T.show_error(e)
        return
    self._report_bulk(done, len(ids))
    window.destroy()
    self.refresh_all_tickets()

# Attach method to HelpdeskGUI class
HelpdeskGUI.bulk_assign_tickets = bulk_assign_tickets

def bulk_change_status(self, new_status, window):
    """Bulk change ticket status through the ticket service (``new_status``
    a label from the list)."""
    if not new_status:
        messagebox.showerror(_t('gui.pastoral.helpdesk.tickets_all.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.tickets_all.dialogs.please_select_a_status', default="Please select a status"))
        return

    ids = sorted(self.selected_tickets, key=str)
    try:
        done = T.svc.bulk_update(T.actor(self), ids, {'status': T.status_from_label(new_status)})
    except Exception as e:
        T.show_error(e)
        return
    self._report_bulk(done, len(ids))
    window.destroy()
    self.refresh_all_tickets()


def _report_bulk(self, done, asked):
    """Say how many tickets a bulk change reached (the rest were refused:
    not in the staff member's teams / tiers, or not found)."""
    if done == asked:
        messagebox.showinfo(_t('gui.pastoral.helpdesk.tickets_all.dialogs.success', default="Success"),
                            _t('gui.pastoral.helpdesk.tickets_all.dialogs.bulk_done', default="{count} tickets updated successfully!").format(count=done))
    else:
        messagebox.showwarning(_t('gui.pastoral.helpdesk.tickets_all.dialogs.warning', default="Warning"),
                               _t('gui.pastoral.helpdesk.tickets_all.dialogs.bulk_partial', default="{count} of {asked} tickets were updated; the others could not be changed by you.").format(count=done, asked=asked))

HelpdeskGUI._report_bulk = _report_bulk

# Attach method to HelpdeskGUI class
HelpdeskGUI.bulk_change_status = bulk_change_status

def bulk_status_change_gui(self):
    """Bulk change status of multiple selected tickets"""
    if not self.has_permission('manage_tickets'):
        messagebox.showerror(_t('gui.pastoral.helpdesk.tickets_all.dialogs.permission_denied', default="Permission Denied"), _t('gui.pastoral.helpdesk.tickets_all.dialogs.you_don_t_have_permission_to_change_ticket_status', default="You don't have permission to change ticket status."))
        return

    # Get selected tickets from all tickets view
    if not hasattr(self, 'all_tickets_tree'):
        messagebox.showerror(_t('gui.pastoral.helpdesk.tickets_all.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.tickets_all.dialogs.please_navigate_to_all_tickets_tab_first', default="Please navigate to All Tickets tab first"))
        return

    selection = self.all_tickets_tree.selection()
    if not selection:
        messagebox.showerror(_t('gui.pastoral.helpdesk.tickets_all.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.tickets_all.dialogs.please_select_one_or_more_tickets', default="Please select one or more tickets"))
        return

    ticket_ids = [self.all_tickets_tree.item(item)['values'][1] for item in selection]

    # Create bulk status change dialog
    dialog = tk.Toplevel(self.root)
    dialog.title(_t('gui.pastoral.helpdesk.tickets_all.windows.bulk_status_change', default="Bulk Status Change"))
    dialog.geometry("400x300")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text=f"Update {len(ticket_ids)} Tickets",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    ttk.Label(main_frame, text=f"Ticket IDs: {', '.join(map(str, ticket_ids))}").pack(pady=(0, 10))

    # Status selection
    status_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.helpdesk.tickets_all.labels.select_new_status', default="Select New Status"), padding="10")
    status_frame.pack(fill='x', pady=(0, 10))

    status_var = tk.StringVar(value='open')

    for status, label in T.status_choices():
        ttk.Radiobutton(status_frame, text=label,
                       variable=status_var, value=status).pack(anchor='w')

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x')

    def perform_bulk_update():
        new_status = status_var.get()
        try:
            done = T.svc.bulk_update(T.actor(self), ticket_ids, {'status': new_status})
        except Exception as e:
            T.show_error(e, parent=dialog)
            return
        self._report_bulk(done, len(ticket_ids))
        dialog.destroy()
        self.refresh_all_tickets()

    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.tickets_all.buttons.update_all', default="Update All"), command=perform_bulk_update).pack(side='right', padx=5)
    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.tickets_all.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.bulk_status_change_gui = bulk_status_change_gui

def show_all_tickets(self):
    """Switch to all tickets tab"""
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') == 'All Tickets':
            self.notebook.select(i)
            break

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_all_tickets = show_all_tickets

def view_all_tickets_enhanced_gui(self):
    """Enhanced view of all tickets with advanced filtering"""
    if not self.auth.has_permission('view_all_tickets'):
        messagebox.showerror(_t('gui.pastoral.helpdesk.tickets_all.dialogs.permission_denied', default="Permission Denied"), _t('gui.pastoral.helpdesk.tickets_all.dialogs.you_don_t_have_permission_to_view_all_tickets', default="You don't have permission to view all tickets."))
        return

    window = tk.Toplevel(self.root)
    window.title(_t('gui.pastoral.helpdesk.tickets_all.windows.all_tickets_enhanced_view', default="All Tickets - Enhanced View"))
    T.size_window(window)

    main_frame = ttk.Frame(window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Filter frame
    filter_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.helpdesk.tickets_all.labels.filters', default="Filters"), padding="10")
    filter_frame.pack(fill=tk.X, pady=5)

    ttk.Label(filter_frame, text=_t('gui.pastoral.helpdesk.tickets_all.labels.filter', default="Filter:")).pack(side=tk.LEFT, padx=5)

    filter_var = tk.StringVar(value=_t('gui.pastoral.helpdesk.tickets_all.values.all', default="all"))
    filters = [
        ("All tickets", "all"),
        ("Unassigned", "unassigned"),
        ("My assigned", "my_assigned"),
        ("Overdue", "overdue"),
        ("High priority", "high_priority"),
        ("Escalated", "escalated")
    ]

    for label, value in filters:
        ttk.Radiobutton(filter_frame, text=label, variable=filter_var, value=value).pack(side=tk.LEFT, padx=5)

    # Tickets treeview
    columns = ('id', 'subject', 'category', 'status', 'priority', 'tier', 'sla', 'submitter', 'assignee', 'created', 'due')
    tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

    tree.heading('id', text=_t('gui.pastoral.helpdesk.tickets_all.headings.id', default='ID'))
    tree.heading('subject', text=_t('gui.pastoral.helpdesk.tickets_all.headings.subject', default='Subject'))
    tree.heading('category', text=_t('gui.pastoral.helpdesk.tickets_all.headings.category', default='Category'))
    tree.heading('status', text=_t('gui.pastoral.helpdesk.tickets_all.headings.status', default='Status'))
    tree.heading('priority', text=_t('gui.pastoral.helpdesk.tickets_all.headings.priority', default='Priority'))
    tree.heading('tier', text=_t('gui.pastoral.helpdesk.tickets_all.headings.tier', default='Tier'))
    tree.heading('sla', text=_t('gui.pastoral.helpdesk.tickets_all.headings.sla', default='SLA'))
    tree.heading('submitter', text=_t('gui.pastoral.helpdesk.tickets_all.headings.submitter', default='Submitter'))
    tree.heading('assignee', text=_t('gui.pastoral.helpdesk.tickets_all.headings.assignee', default='Assignee'))
    tree.heading('created', text=_t('gui.pastoral.helpdesk.tickets_all.headings.created', default='Created'))
    tree.heading('due', text=_t('gui.pastoral.helpdesk.tickets_all.headings.due_date', default='Due Date'))

    tree.column('id', width=50)
    tree.column('subject', width=250)
    tree.column('category', width=120)
    tree.column('status', width=100)
    tree.column('priority', width=80)
    tree.column('tier', width=100)
    tree.column('sla', width=120)
    tree.column('submitter', width=100)
    tree.column('assignee', width=100)
    tree.column('created', width=130)
    tree.column('due', width=130)

    scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    # The action buttons are packed (at the bottom) before the table expands.
    bottom_bar = ttk.Frame(main_frame)
    bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=10)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

    def load_tickets():
        # Clear existing
        for item in tree.get_children():
            tree.delete(item)

        try:
            filters = {}
            filter_val = filter_var.get()
            if filter_val == "unassigned":
                filters['unassigned'] = True
            elif filter_val == "my_assigned":
                filters['assigned_to'] = T.username(self)
            elif filter_val == "high_priority":
                filters['priority'] = 'high'
            elif filter_val in ("overdue", "escalated"):
                filters['active_only'] = True
            tickets = list(T.hd.iter_tickets(T.actor(self), filters or None))
        except Exception as e:
            T.show_error(e, parent=window)
            return

        for ticket in tickets:
            sla = T.sla_label(ticket)
            if filter_val == "overdue" and not sla.startswith(('Overdue', 'Breached')):
                continue
            if filter_val == "escalated" and not (ticket.get('status') == 'escalated'
                                                  or (ticket.get('escalation_level') or 0) > 0):
                continue
            subject = ticket.get('subject') or 'No Subject'
            tree.insert('', tk.END, values=(
                ticket['ticket_id'],
                subject[:40],
                ticket.get('category') or 'General',
                ticket.get('status_label') or T.status_label(ticket.get('status')),
                str(ticket.get('priority') or 'medium').upper(),
                T.tier_badge(ticket),
                sla,
                T.requester_of(ticket),
                ticket.get('assigned_to') or 'Unassigned',
                ticket.get('created_at') or '',
                ticket.get('sla_due_at') or ticket.get('due_date') or 'N/A'
            ))

    ttk.Button(filter_frame, text=_t('gui.pastoral.helpdesk.tickets_all.buttons.apply_filter', default="Apply Filter"), command=load_tickets).pack(side=tk.LEFT, padx=5)
    ttk.Button(bottom_bar, text=_t('gui.pastoral.helpdesk.tickets_all.buttons.view_details', default="View Details"), command=lambda: self.view_ticket_from_tree(tree)).pack(side=tk.LEFT, padx=5, pady=5)
    ttk.Button(bottom_bar, text=_t('gui.pastoral.helpdesk.tickets_all.buttons.close', default="Close"), command=window.destroy).pack(side=tk.RIGHT, padx=5, pady=5)

    tree.bind('<Double-1>', lambda e: self.view_ticket_from_tree(tree))

    # Initial load
    load_tickets()

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_all_tickets_enhanced_gui = view_all_tickets_enhanced_gui

