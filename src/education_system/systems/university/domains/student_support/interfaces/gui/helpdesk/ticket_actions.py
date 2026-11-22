
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


def _refresh_ticket_lists(self):
    """Refresh whichever ticket lists this window has open."""
    for name, tree in (('refresh_my_tickets', 'my_tickets_tree'),
                       ('refresh_all_tickets', 'all_tickets_tree')):
        if self.__dict__.get(tree) is not None:
            try:
                getattr(self, name)()
            except tk.TclError:
                pass

HelpdeskGUI._refresh_ticket_lists = _refresh_ticket_lists

def show_reply_dialog(self, ticket_id):
    """Show reply dialog"""
    reply_window = tk.Toplevel(self.root)
    reply_window.title(f"Reply to Ticket #{ticket_id}")
    reply_window.geometry("600x400")
    reply_window.transient(self.root)
    reply_window.grab_set()

    # Title
    ttk.Label(reply_window, text=f"Reply to Ticket #{ticket_id}",
             style='Heading.TLabel').pack(pady=10)

    # Message frame
    message_frame = ttk.LabelFrame(reply_window, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.your_reply', default="Your Reply"))
    message_frame.pack(fill='both', expand=True, padx=10, pady=10)

    # Message text area
    message_text = scrolledtext.ScrolledText(message_frame, height=10, wrap='word')
    message_text.pack(fill='both', expand=True, padx=5, pady=5)

    # Time tracking (if admin)
    time_frame = ttk.Frame(reply_window)
    if self.has_permission('manage_tickets'):
        time_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(time_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.time_spent_hours', default="Time spent (hours):")).pack(side='left')
        time_entry = ttk.Entry(time_frame, width=10)
        time_entry.pack(side='left', padx=5)

    # Buttons
    button_frame = ttk.Frame(reply_window)
    button_frame.pack(fill='x', padx=10, pady=10)

    def send_reply():
        message = message_text.get('1.0', 'end-1c').strip()
        if not message:
            messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.please_enter_a_reply_message', default="Please enter a reply message"))
            return

        time_spent = 0
        if self.has_permission('manage_tickets') and time_entry.get():
            try:
                time_spent = float(time_entry.get())
            except ValueError:
                pass

        if self.add_ticket_reply(ticket_id, message, time_spent):
            messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.success', default="Success"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.reply_added_successfully', default="Reply added successfully!"))
            reply_window.destroy()
            # Refresh the ticket lists and the open conversation
            self._refresh_ticket_lists()
            if self.__dict__.get('replies_frame') is not None:
                try:
                    self.load_ticket_replies(ticket_id)
                except tk.TclError:
                    pass
        # else: add_ticket_reply has shown why

    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.send_reply', default="Send Reply"), command=send_reply,
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.cancel', default="Cancel"), command=reply_window.destroy).pack(side='right')

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_reply_dialog = show_reply_dialog

def add_ticket_reply(self, ticket_id, message, time_spent=0, is_internal=False):
    """Reply to a ticket through the ticket service (staff working it may
    make it an internal note). The service moves the status on, records the
    first response for the SLA, notifies the other side and checks the
    requester's words for crisis language — whose contacts are shown at
    once. Time spent is logged to the ticket's time tracking. Returns True,
    or False after showing why the reply was refused."""
    try:
        result = T.svc.post_response(T.actor(self), ticket_id, message, internal=bool(is_internal))
    except Exception as e:
        T.show_error(e)
        return False
    T.show_crisis(result.get('crisis'))
    if time_spent:
        self.record_time_spent(ticket_id, time_spent, _t('gui.pastoral.helpdesk.ticket_actions.values.reply_time', default="Reply"))
    return True


def record_time_spent(self, ticket_id, hours, description=''):
    """Log ``hours`` against the ticket (Helpdesk time tracking; staff only)."""
    if not T.is_case_worker(self):
        return
    try:
        hours = float(hours)
    except (TypeError, ValueError):
        return
    if hours <= 0:
        return
    from education_system.systems.university.domains.student_support.domain.student_support import (
        collaboration,
    )
    try:
        collaboration.log_time(T.actor(self), ticket_id, hours * 60, description)
    except Exception:
        T.logger.warning("Could not log time on ticket %s", ticket_id, exc_info=True)

HelpdeskGUI.record_time_spent = record_time_spent

# Attach method to HelpdeskGUI class
HelpdeskGUI.add_ticket_reply = add_ticket_reply

def show_status_dialog(self, ticket_id):
    """Show status change dialog"""
    status_window = tk.Toplevel(self.root)
    status_window.title(f"Change Status - Ticket #{ticket_id}")
    status_window.geometry("450x480")
    status_window.transient(self.root)
    status_window.grab_set()

    # Title
    ttk.Label(status_window, text=f"Change Status for Ticket #{ticket_id}",
             style='Heading.TLabel').pack(pady=10)

    # Action bar first, so the form never pushes it off the window
    button_frame = ttk.Frame(status_window)
    button_frame.pack(side='bottom', fill='x', padx=10, pady=10)

    # Status selection
    status_frame = ttk.LabelFrame(status_window, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.new_status', default="New Status"))
    status_frame.pack(fill='x', padx=10, pady=10)

    status_var = tk.StringVar()

    for status, label in T.status_choices():
        ttk.Radiobutton(status_frame, text=label, variable=status_var,
                       value=status).pack(anchor='w', padx=5, pady=2)

    # Resolution field (for resolved/closed)
    resolution_frame = ttk.LabelFrame(status_window, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.resolution_if_resolved_closed', default="Resolution (if resolved/closed)"))
    resolution_frame.pack(fill='both', expand=True, padx=10, pady=10)

    resolution_text = scrolledtext.ScrolledText(resolution_frame, height=5, wrap='word')
    resolution_text.pack(fill='both', expand=True, padx=5, pady=5)


    def update_status():
        new_status = status_var.get()
        if not new_status:
            messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.please_select_a_status', default="Please select a status"))
            return

        resolution = resolution_text.get('1.0', 'end-1c').strip()

        if self.update_ticket_status(ticket_id, new_status, resolution):
            messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.success', default="Success"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.status_updated_successfully', default="Status updated successfully!"))
            status_window.destroy()
            self._refresh_ticket_lists()
        # else: update_ticket_status has shown why

    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.update_status', default="Update Status"), command=update_status,
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.cancel', default="Cancel"), command=status_window.destroy).pack(side='right')

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_status_dialog = show_status_dialog

def update_ticket_status(self, ticket_id, new_status, resolution=None):
    """Move a ticket to ``new_status`` (any spelling; stored lower-case)
    through the ticket service — resolved / closed times, the resolution
    (sealed with a confidential ticket), the requester's notice and the
    satisfaction survey all come from it. Returns True, or False after
    showing why."""
    try:
        T.svc.set_status(T.actor(self), ticket_id, new_status, note=resolution or None)
    except Exception as e:
        T.show_error(e)
        return False
    return True

# Attach method to HelpdeskGUI class
HelpdeskGUI.update_ticket_status = update_ticket_status

def show_assign_dialog(self, ticket_id):
    """Show ticket assignment dialog"""
    assign_window = tk.Toplevel(self.root)
    assign_window.title(f"Assign Ticket #{ticket_id}")
    assign_window.geometry("500x500")
    assign_window.transient(self.root)
    assign_window.grab_set()

    # Title
    ttk.Label(assign_window, text=f"Assign Ticket #{ticket_id}",
             style='Heading.TLabel').pack(pady=10)

    # Action bar first, so a long staff list never pushes it off the window
    button_frame = ttk.Frame(assign_window)
    button_frame.pack(side='bottom', fill='x', padx=10, pady=10)

    # Staff selection
    staff_frame = ttk.LabelFrame(assign_window, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.assign_to', default="Assign To"))
    staff_frame.pack(fill='both', expand=True, padx=10, pady=10)

    # Who can take it: the ticket's team (by load), then the admins
    try:
        team = T.svc.get_ticket(T.actor(self), ticket_id).get('team')
    except Exception as e:
        assign_window.destroy()
        T.show_error(e)
        return
    staff_list = self.get_available_staff(team)

    staff_var = tk.StringVar()

    # Add "Unassigned" option
    ttk.Radiobutton(staff_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.unassigned', default="Unassigned"), variable=staff_var,
                   value="").pack(anchor='w', padx=5, pady=2)

    for staff in staff_list:
        load = '' if staff.get('open') is None else f", {staff['open']} open"
        display_text = f"{staff['username']} ({staff['role']} - {staff.get('department') or 'No Dept'}{load})"
        ttk.Radiobutton(staff_frame, text=display_text, variable=staff_var,
                       value=staff['username']).pack(anchor='w', padx=5, pady=2)


    def assign_ticket():
        assignee = staff_var.get() or None

        if self.assign_ticket_to_user(ticket_id, assignee):
            messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.success', default="Success"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.ticket_assigned_successfully', default="Ticket assigned successfully!"))
            assign_window.destroy()
            self._refresh_ticket_lists()
        # else: assign_ticket_to_user has shown why

    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.assign', default="Assign"), command=assign_ticket,
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.cancel', default="Cancel"), command=assign_window.destroy).pack(side='right')

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_assign_dialog = show_assign_dialog

def get_available_staff(self, team=None):
    """Support staff a ticket can be given to: the members of ``team`` (all
    teams when None) with their open load, then the admins. Each entry's
    ``id`` is the username — assignment is by username."""
    try:
        return T.staff_choices(team)
    except Exception:
        T.logger.warning("Could not load the support staff", exc_info=True)
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_available_staff = get_available_staff

def assign_ticket_to_user(self, ticket_id, assignee):
    """Give the ticket to ``assignee`` (a username; None to unassign) through
    the ticket service, which checks they work tickets and are in the
    ticket's team and tier, notes it and tells them. Returns True, or False
    after showing why."""
    try:
        T.svc.assign(T.actor(self), ticket_id, assignee)
    except Exception as e:
        T.show_error(e)
        return False
    return True

# Attach method to HelpdeskGUI class
HelpdeskGUI.assign_ticket_to_user = assign_ticket_to_user

def show_internal_note_dialog(self, ticket_id):
    """Show internal note dialog"""
    note_window = tk.Toplevel(self.root)
    note_window.title(f"Add Internal Note - Ticket #{ticket_id}")
    note_window.geometry("600x400")
    note_window.transient(self.root)
    note_window.grab_set()

    # Title
    ttk.Label(note_window, text=f"Add Internal Note to Ticket #{ticket_id}",
             style='Heading.TLabel').pack(pady=10)

    # Message frame
    message_frame = ttk.LabelFrame(note_window, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.internal_note_only_visible_to_staff', default="Internal Note (Only visible to staff)"))
    message_frame.pack(fill='both', expand=True, padx=10, pady=10)

    # Message text area
    message_text = scrolledtext.ScrolledText(message_frame, height=10, wrap='word')
    message_text.pack(fill='both', expand=True, padx=5, pady=5)

    # Buttons
    button_frame = ttk.Frame(note_window)
    button_frame.pack(fill='x', padx=10, pady=10)

    def add_note():
        message = message_text.get('1.0', 'end-1c').strip()
        if not message:
            messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.please_enter_a_note', default="Please enter a note"))
            return

        if self.add_ticket_reply(ticket_id, message, 0, is_internal=True):
            messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.success', default="Success"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.internal_note_added_successfully', default="Internal note added successfully!"))
            note_window.destroy()
        # else: add_ticket_reply has shown why

    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.add_note', default="Add Note"), command=add_note,
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.cancel', default="Cancel"), command=note_window.destroy).pack(side='right')

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_internal_note_dialog = show_internal_note_dialog

def escalate_ticket_manual(self, ticket_id):
    """Manually escalate a ticket"""
    escalate_window = tk.Toplevel(self.root)
    escalate_window.title(_t("helpdesk.escalate_ticket_title", default="Escalate Ticket #{ticket_id}").format(ticket_id=ticket_id))
    escalate_window.geometry("400x200")
    escalate_window.transient(self.root)
    escalate_window.grab_set()

    ttk.Label(escalate_window, text=_t("helpdesk.escalate_ticket_title", default="Escalate Ticket #{ticket_id}").format(ticket_id=ticket_id), style='Heading.TLabel').pack(pady=10)

    ttk.Label(escalate_window, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.escalation_reason', default="Escalation Reason:")).pack(pady=5)
    reason_entry = ttk.Entry(escalate_window, width=40)
    reason_entry.pack(pady=5)
    reason_entry.insert(0, "Manual escalation")

    button_frame = ttk.Frame(escalate_window)
    button_frame.pack(pady=20)

    def perform_escalation():
        reason = reason_entry.get().strip()
        if self.escalate_ticket(ticket_id, reason):
            messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.success', default="Success"), f"Ticket #{ticket_id} escalated successfully")
            escalate_window.destroy()
            self._refresh_ticket_lists()
        # else: escalate_ticket has shown why

    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.escalate', default="Escalate"), command=perform_escalation,
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.cancel', default="Cancel"), command=escalate_window.destroy).pack(side='right')

# Attach method to HelpdeskGUI class
HelpdeskGUI.escalate_ticket_manual = escalate_ticket_manual

def escalate_ticket(self, ticket_id, reason='manual'):
    """Escalate through the ticket service (status escalated, level + 1, an
    internal note with the reason, the assignee told). Returns True, or
    False after showing why."""
    try:
        T.svc.escalate(T.actor(self), ticket_id, reason)
    except Exception as e:
        T.show_error(e)
        return False
    return True

# Attach method to HelpdeskGUI class
HelpdeskGUI.escalate_ticket = escalate_ticket

def assign_ticket_enhanced(self, ticket_id):
    """Enhanced ticket assignment with load balancing and skill-based routing"""
    if not self.current_user:
        messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.you_must_be_logged_in_to_assign_tickets', default="You must be logged in to assign tickets."))
        return

    if not self.has_permission('manage_tickets'):
        messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.permission_denied', default="Permission Denied"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.you_don_t_have_permission_to_assign_tickets', default="You don't have permission to assign tickets."))
        return

    # Create assignment dialog
    dialog = tk.Toplevel(self.root)
    dialog.title(_t('gui.pastoral.helpdesk.ticket_actions.windows.enhanced_ticket_assignment', default="Enhanced Ticket Assignment"))
    dialog.geometry("600x500")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text=f"Assign Ticket #{ticket_id}",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    # Assignment options
    option_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.assignment_options', default="Assignment Options"), padding="10")
    option_frame.pack(fill='x', pady=(0, 10))

    assign_option = tk.StringVar(value=_t('gui.pastoral.helpdesk.ticket_actions.values.user', default='user'))
    ttk.Radiobutton(option_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.assign_to_specific_user', default="Assign to specific user"),
                   variable=assign_option, value='user').pack(anchor='w')
    ttk.Radiobutton(option_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.assign_to_department_auto_balance', default="Assign to department (auto-balance)"),
                   variable=assign_option, value='department').pack(anchor='w')
    ttk.Radiobutton(option_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.unassign_ticket', default="Unassign ticket"),
                   variable=assign_option, value='unassign').pack(anchor='w')

    # User selection frame
    user_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.select_user', default="Select User"), padding="10")
    user_frame.pack(fill='both', expand=True, pady=(0, 10))

    # Staff list
    columns = ('Username', 'Role', 'Team', 'Active Tickets', 'Capacity')
    staff_tree = ttk.Treeview(user_frame, columns=columns, show='headings', height=10)

    for col in columns:
        staff_tree.heading(col, text=col)
        staff_tree.column(col, width=100)

    staff_tree.pack(fill='both', expand=True, side='left')

    scrollbar = ttk.Scrollbar(user_frame, orient='vertical', command=staff_tree.yview)
    scrollbar.pack(side='right', fill='y')
    staff_tree.configure(yscrollcommand=scrollbar.set)

    # Load the staff who can take it (the ticket's team by load, then admins)
    try:
        team = T.svc.get_ticket(T.actor(self), ticket_id).get('team')
        staff_members = T.staff_choices(team)
    except Exception as e:
        dialog.destroy()
        T.show_error(e)
        return

    for staff in staff_members:
        staff_tree.insert('', 'end', values=(
            staff['username'], staff['role'], staff['department'] or '',
            '' if staff['open'] is None else staff['open'],
            '' if staff['max'] is None else staff['max']))

    # Department selection (hidden by default)
    dept_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.select_department', default="Select Department"), padding="10")

    dept_var = tk.StringVar()
    dept_combo = ttk.Combobox(dept_frame, textvariable=dept_var, state="readonly", width=40)
    dept_combo.pack(fill='x')

    # Load departments
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM departments WHERE is_active = 1 ORDER BY name')
        departments = [row[0] for row in cursor.fetchall()]
        conn.close()
        dept_combo['values'] = departments
    except Exception:
        dept_combo['values'] = ['IT Support', 'Academic Affairs', 'Financial Services']

    # Show/hide frames based on selection
    def update_frames(*args):
        if assign_option.get() == 'user':
            user_frame.pack(fill='both', expand=True, pady=(0, 10))
            dept_frame.pack_forget()
        elif assign_option.get() == 'department':
            user_frame.pack_forget()
            dept_frame.pack(fill='x', pady=(0, 10))
        else:
            user_frame.pack_forget()
            dept_frame.pack_forget()

    assign_option.trace('w', update_frames)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x')

    def perform_assignment():
        new_assigned = None
        if assign_option.get() == 'user':
            selection = staff_tree.selection()
            if not selection:
                messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.please_select_a_user', default="Please select a user"), parent=dialog)
                return
            new_assigned = str(staff_tree.item(selection[0])['values'][0])

        elif assign_option.get() == 'department':
            new_department = dept_var.get()
            if not new_department:
                messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.please_select_a_department', default="Please select a department"), parent=dialog)
                return
            # Move the ticket to the department's team (tier, SLA and
            # assignee follow the team), then give it to that team's
            # least-loaded free member — or leave it in the team's queue.
            team = T.team_for_department(new_department)
            reason = simpledialog.askstring(
                _t('gui.pastoral.helpdesk.ticket_actions.dialogs.move_reason_title', default="Move Ticket"),
                _t('gui.pastoral.helpdesk.ticket_actions.dialogs.move_reason', default="Why is this ticket moving to {department}?").format(department=new_department),
                parent=dialog)
            if not reason:
                return
            try:
                moved = T.svc.set_team(T.actor(self), ticket_id, team, reason)
            except Exception as e:
                T.show_error(e)
                return
            new_assigned = T.routing.pick_assignee(moved['new'])
            if not new_assigned:
                messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.success', default="Success"),
                                    _t('gui.pastoral.helpdesk.ticket_actions.dialogs.moved_to_queue', default="Ticket #{ticket_id} moved to {department}. Nobody there is free right now, so it waits in their queue.").format(ticket_id=ticket_id, department=new_department), parent=dialog)
                dialog.destroy()
                self._refresh_ticket_lists()
                return

        if self.assign_ticket_to_user(ticket_id, new_assigned):
            messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.success', default="Success"), f"Ticket #{ticket_id} assigned successfully!")
            dialog.destroy()
            self._refresh_ticket_lists()

    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.assign', default="Assign"), command=perform_assignment).pack(side='right', padx=5)
    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.assign_ticket_enhanced = assign_ticket_enhanced

def change_ticket_status_enhanced(self, ticket_id):
    """Enhanced status change with resolution tracking and workflow validation"""
    if not self.current_user:
        messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.you_must_be_logged_in_to_update_ticket_status', default="You must be logged in to update ticket status."))
        return

    if not self.has_permission('manage_tickets'):
        messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.permission_denied', default="Permission Denied"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.you_don_t_have_permission_to_update_ticket_status', default="You don't have permission to update ticket status."))
        return

    # Create status change dialog
    dialog = tk.Toplevel(self.root)
    dialog.title(_t('gui.pastoral.helpdesk.ticket_actions.windows.change_ticket_status', default="Change Ticket Status"))
    dialog.geometry("500x450")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text=f"Change Status for Ticket #{ticket_id}",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    # Get current status
    try:
        ticket = T.svc.get_ticket(T.actor(self), ticket_id)
    except Exception as e:
        dialog.destroy()
        T.show_error(e)
        return
    current_status = T.schema.normalize_status(ticket.get('status'), default='open')
    current_resolution = ticket.get('resolution')

    # Current status display
    status_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.current_status', default="Current Status"), padding="10")
    status_frame.pack(fill='x', pady=(0, 10))
    ttk.Label(status_frame, text=T.status_label(current_status).upper(),
             font=('TkDefaultFont', 10, 'bold')).pack()

    # New status selection
    new_status_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.new_status', default="New Status"), padding="10")
    new_status_frame.pack(fill='x', pady=(0, 10))

    status_var = tk.StringVar(value=current_status)

    for status, label in T.status_choices():
        ttk.Radiobutton(new_status_frame, text=label,
                       variable=status_var, value=status).pack(anchor='w')

    # Resolution frame (shown for resolved/closed)
    resolution_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.resolution_details', default="Resolution Details"), padding="10")
    resolution_frame.pack(fill='both', expand=True, pady=(0, 10))

    ttk.Label(resolution_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.required_for_resolved_closed_tickets', default="Required for Resolved/Closed tickets:")).pack(anchor='w')
    resolution_text = scrolledtext.ScrolledText(resolution_frame, height=8, width=50)
    resolution_text.pack(fill='both', expand=True)

    if current_resolution:
        resolution_text.insert('1.0', current_resolution)

    # Show/hide resolution based on status
    def update_resolution_visibility(*args):
        if status_var.get() in ['resolved', 'closed']:
            resolution_frame.pack(fill='both', expand=True, pady=(0, 10))
        else:
            resolution_frame.pack_forget()

    status_var.trace('w', update_resolution_visibility)
    update_resolution_visibility()

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x')

    def update_status():
        new_status = status_var.get()
        resolution = resolution_text.get('1.0', 'end-1c').strip()

        if new_status == current_status:
            messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.info', default="Info"), "Status is already set to " + T.status_label(new_status).upper(), parent=dialog)
            return

        if new_status in ['resolved', 'closed'] and not resolution:
            messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.error', default="Error"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.resolution_details_are_required_for_resolved_closed_tickets', default="Resolution details are required for resolved/closed tickets"), parent=dialog)
            return

        note = resolution if new_status in ['resolved', 'closed'] else None
        if self.update_ticket_status(ticket_id, new_status, note):
            messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.success', default="Success"), f"Ticket status updated to: {T.status_label(new_status).upper()}")
            dialog.destroy()
            self._refresh_ticket_lists()

    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.update_status', default="Update Status"), command=update_status).pack(side='right', padx=5)
    ttk.Button(button_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.change_ticket_status_enhanced = change_ticket_status_enhanced

def execute_ticket_action_gui(self, ticket_id, action):
    """Execute various ticket actions through unified interface"""
    if action == 'reply':
        self.reply_to_ticket_enhanced_gui(ticket_id)
    elif action == 'assign':
        self.assign_ticket_enhanced(ticket_id)
    elif action == 'change_status':
        self.change_ticket_status_enhanced(ticket_id)
    elif action == 'escalate':
        self.escalate_ticket_manual(ticket_id)
    elif action == 'view':
        self.view_ticket_detail_enhanced_gui(ticket_id)
    elif action == 'close':
        self.change_ticket_status_enhanced(ticket_id)
    elif action == 'internal_note':
        self.reply_to_ticket_enhanced_gui(ticket_id, is_internal=True)
    elif action == 'time_entry':
        self.add_time_entry_gui(ticket_id)
    elif action == 'link':
        self.link_tickets_gui(ticket_id)
    else:
        messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.info', default="Info"), f"Action '{action}' not yet implemented")

# Attach method to HelpdeskGUI class
HelpdeskGUI.execute_ticket_action_gui = execute_ticket_action_gui

def reply_to_ticket_enhanced_gui(self, ticket_id, is_internal=False):
    """Enhanced reply functionality with attachments"""
    # Who may reply (the requester; the staff working the ticket — internal
    # notes for staff only) is the ticket service's decision when saving.
    if is_internal and not T.is_case_worker(self):
        messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.permission_denied', default="Permission Denied"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.staff_only_notes', default="Only support staff can add internal notes"))
        return

    # Create reply dialog
    reply_type = "Internal Note" if is_internal else "Reply"
    dialog = tk.Toplevel(self.root)
    dialog.title(f"Add {reply_type} to Ticket #{ticket_id}")
    dialog.geometry("600x500")

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Message
    ttk.Label(main_frame, text=f"{reply_type} Message:").pack(anchor=tk.W, pady=5)
    message_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=15)
    message_text.pack(fill=tk.BOTH, expand=True, pady=5)

    # Time spent (admin only)
    time_frame = ttk.Frame(main_frame)
    time_var = tk.StringVar(value="0")
    if T.is_case_worker(self):
        time_frame.pack(fill=tk.X, pady=5)
        ttk.Label(time_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.labels.time_spent_hours', default="Time spent (hours):")).pack(side=tk.LEFT, padx=5)
        ttk.Entry(time_frame, textvariable=time_var, width=10).pack(side=tk.LEFT, padx=5)

    def save_reply():
        message = message_text.get('1.0', tk.END).strip()

        if not message:
            messagebox.showerror(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.validation_error', default="Validation Error"), _t('gui.pastoral.helpdesk.ticket_actions.dialogs.reply_message_cannot_be_empty', default="Reply message cannot be empty."))
            return

        try:
            time_spent = float(time_var.get() or 0)
        except ValueError:
            time_spent = 0

        if self.add_ticket_reply(ticket_id, message, time_spent, is_internal=is_internal):
            messagebox.showinfo(_t('gui.pastoral.helpdesk.ticket_actions.dialogs.success', default="Success"), f"{reply_type} added successfully!")
            dialog.destroy()
            self._refresh_ticket_lists()

    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill=tk.X, pady=10)

    ttk.Button(btn_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.save', default="Save"), command=save_reply).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text=_t('gui.pastoral.helpdesk.ticket_actions.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.reply_to_ticket_enhanced_gui = reply_to_ticket_enhanced_gui

def add_time_entry_gui(self, ticket_id):
    """Add time tracking entry (``collaboration.log_time``: staff working the ticket)."""
    from education_system.systems.university.domains.student_support.interfaces.gui.helpdesk import support_tools
    support_tools.time_dialog(self.root, T.actor(self), ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.add_time_entry_gui = add_time_entry_gui

def link_tickets_gui(self, ticket_id):
    """Link tickets together (``collaboration.link_tickets``: both ways, staff
    working both tickets)."""
    from education_system.systems.university.domains.student_support.interfaces.gui.helpdesk import support_tools
    support_tools.link_dialog(self.root, T.actor(self), ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.link_tickets_gui = link_tickets_gui

def log_ticket_action_gui(self, ticket_id, action, old_values=None, new_values=None):
    """Log ticket action to audit trail"""
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        import json

        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO ticket_audit_log
            (ticket_id, user_id, action, old_values, new_values, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id,
            T.local_user_id(self),
            action,
            json.dumps(old_values or {}),
            json.dumps(new_values or {}),
            now
        ))

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Failed to log action: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.log_ticket_action_gui = log_ticket_action_gui

