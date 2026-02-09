import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

class SupportGroupsDialog:
    """Dialog for browsing support groups"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Peer Support Groups")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Peer Support Groups", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="Filter by Type:").pack(side='left', padx=(0, 10))
        self.type_var = tk.StringVar(value="All")
        type_combo = ttk.Combobox(filter_frame, textvariable=self.type_var, width=20)
        type_combo['values'] = ('All', 'Mental Health', 'Academic', 'Career', 'Social', 'Wellness')
        type_combo.pack(side='left', padx=(0, 10))
        type_combo.bind('<<ComboboxSelected>>', lambda e: self.load_data())

        ttk.Button(filter_frame, text="Create New Group", command=self.create_group).pack(side='right')

        # Groups list
        list_frame = ttk.LabelFrame(main_frame, text="Available Support Groups")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Type', 'Facilitator', 'Members', 'Max', 'Schedule', 'Status')
        self.groups_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.groups_tree.heading(col, text=col)
            if col == 'Name':
                self.groups_tree.column(col, width=200)
            elif col == 'Schedule':
                self.groups_tree.column(col, width=150)
            else:
                self.groups_tree.column(col, width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=scrollbar.set)

        self.groups_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Group Description")
        details_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=6, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        self.groups_tree.bind('<<TreeviewSelect>>', self.show_details)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Join Selected Group", command=self.join_group).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="My Groups", command=self.view_my_groups).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load support groups"""
        for item in self.groups_tree.get_children():
            self.groups_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            type_filter = self.type_var.get()
            if type_filter == "All":
                cursor.execute('''
                SELECT psg.group_id, psg.group_name, psg.support_type,
                       s.first_name || ' ' || s.last_name, psg.current_members,
                       psg.max_members, psg.meeting_schedule, psg.status
                FROM peer_support_groups psg
                INNER JOIN students s ON psg.facilitator_id = s.student_id
                WHERE psg.status = 'active'
                ORDER BY psg.group_name
                ''')
            else:
                cursor.execute('''
                SELECT psg.group_id, psg.group_name, psg.support_type,
                       s.first_name || ' ' || s.last_name, psg.current_members,
                       psg.max_members, psg.meeting_schedule, psg.status
                FROM peer_support_groups psg
                INNER JOIN students s ON psg.facilitator_id = s.student_id
                WHERE psg.status = 'active' AND psg.support_type = ?
                ORDER BY psg.group_name
                ''', (type_filter,))

            groups = cursor.fetchall()

            for group in groups:
                self.groups_tree.insert('', 'end', values=group)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load groups: {str(e)}")

    def show_details(self, event):
        """Show group details"""
        selection = self.groups_tree.selection()
        if not selection:
            return

        item = self.groups_tree.item(selection[0])
        group_id = item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT description FROM peer_support_groups WHERE group_id = ?', (group_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(1.0, result[0] or "No description available.")
        except sqlite3.Error as e:
            pass

    def join_group(self):
        """Join selected support group"""
        selection = self.groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to join.")
            return

        item = self.groups_tree.item(selection[0])
        group_id = item['values'][0]
        group_name = item['values'][1]
        current_members = item['values'][4]
        max_members = item['values'][5]

        if current_members >= max_members:
            messagebox.showwarning("Warning", "This group is full.")
            return

        if messagebox.askyesno("Confirm", f"Join '{group_name}'?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                student_id = cursor.fetchone()[0]

                # Generate anonymous ID
                import hashlib
                anonymous_id = hashlib.md5(f"{student_id}{group_id}".encode()).hexdigest()[:8]

                cursor.execute('''
                INSERT INTO support_group_members (group_id, student_id, join_date, anonymous_id)
                VALUES (?, ?, ?, ?)
                ''', (group_id, student_id, datetime.now().isoformat(), anonymous_id))

                cursor.execute('''
                UPDATE peer_support_groups SET current_members = current_members + 1
                WHERE group_id = ?
                ''', (group_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Successfully joined the support group!")
                self.load_data()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to join group: {str(e)}")

    def create_group(self):
        """Create new support group"""
        dialog = CreateSupportGroupDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_data()

    def view_my_groups(self):
        """View groups user is member of"""
        dialog = MySupportGroupsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class CreateSupportGroupDialog:
    """Dialog for creating a new support group"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Support Group")
        self.dialog.geometry("600x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Create New Support Group", font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 20))

        # Group name
        ttk.Label(main_frame, text="Group Name:").pack(anchor='w', pady=(0, 5))
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=50).pack(fill='x', pady=(0, 10))

        # Support type
        ttk.Label(main_frame, text="Support Type:").pack(anchor='w', pady=(0, 5))
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=47)
        type_combo['values'] = ('Mental Health', 'Academic', 'Career', 'Social', 'Wellness', 'Other')
        type_combo.pack(fill='x', pady=(0, 10))

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(0, 5))
        self.description_text = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD)
        self.description_text.pack(fill='both', expand=True, pady=(0, 10))

        # Max members
        ttk.Label(main_frame, text="Maximum Members:").pack(anchor='w', pady=(0, 5))
        self.max_var = tk.StringVar(value="10")
        ttk.Entry(main_frame, textvariable=self.max_var, width=10).pack(anchor='w', pady=(0, 10))

        # Meeting schedule
        ttk.Label(main_frame, text="Meeting Schedule:").pack(anchor='w', pady=(0, 5))
        self.schedule_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.schedule_var, width=50).pack(fill='x', pady=(0, 10))
        ttk.Label(main_frame, text="(e.g., 'Every Monday 6:00 PM')", font=('Arial', 8)).pack(anchor='w', pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Create", command=self.create).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def create(self):
        """Create the support group"""
        name = self.name_var.get().strip()
        support_type = self.type_var.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()
        max_members = self.max_var.get().strip()
        schedule = self.schedule_var.get().strip()

        if not all([name, support_type, description, max_members, schedule]):
            messagebox.showwarning("Warning", "Please fill in all fields.")
            return

        try:
            max_members = int(max_members)
            if max_members < 2:
                messagebox.showwarning("Warning", "Maximum members must be at least 2.")
                return
        except ValueError:
            messagebox.showwarning("Warning", "Maximum members must be a number.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            facilitator_id = cursor.fetchone()[0]

            cursor.execute('''
            INSERT INTO peer_support_groups (group_name, description, support_type, facilitator_id,
                                            max_members, current_members, meeting_schedule, status, created_date)
            VALUES (?, ?, ?, ?, ?, 1, ?, 'active', ?)
            ''', (name, description, support_type, facilitator_id, max_members, schedule, datetime.now().isoformat()))

            group_id = cursor.lastrowid

            # Add facilitator as member
            cursor.execute('''
            INSERT INTO support_group_members (group_id, student_id, join_date, anonymous_id)
            VALUES (?, ?, ?, ?)
            ''', (group_id, facilitator_id, datetime.now().isoformat(), 'facilitator'))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Support group created successfully!")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to create group: {str(e)}")



class MySupportGroupsDialog:
    """Dialog for viewing user's support groups"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Support Groups")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="My Support Groups", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Groups list
        list_frame = ttk.LabelFrame(main_frame, text="My Groups")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Group Name', 'Type', 'Role', 'Join Date', 'Schedule', 'Members')
        self.groups_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.groups_tree.heading(col, text=col)
            if col in ('Group Name', 'Schedule'):
                self.groups_tree.column(col, width=200)
            else:
                self.groups_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=scrollbar.set)

        self.groups_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Leave Selected Group", command=self.leave_group).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load user's support groups"""
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT psg.group_name, psg.support_type,
                   CASE WHEN psg.facilitator_id = ? THEN 'Facilitator' ELSE 'Member' END,
                   sgm.join_date, psg.meeting_schedule, psg.current_members
            FROM support_group_members sgm
            INNER JOIN peer_support_groups psg ON sgm.group_id = psg.group_id
            WHERE sgm.student_id = ? AND sgm.status = 'active'
            ORDER BY sgm.join_date DESC
            ''', (student_id, student_id))

            groups = cursor.fetchall()

            for group in groups:
                self.groups_tree.insert('', 'end', values=group)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load groups: {str(e)}")

    def leave_group(self):
        """Leave selected group"""
        selection = self.groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to leave.")
            return

        if messagebox.askyesno("Confirm", "Are you sure you want to leave this support group?"):
            # In a full implementation, would update the database
            messagebox.showinfo("Success", "Left the support group.")
            self.load_data()



class BrowseSupportGroupsDialog:
    """Browse available support groups"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Browse Support Groups")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_groups()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📋 Support Group Directory",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Topic:").pack(side='left', padx=(0, 5))
        self.topic_var = tk.StringVar()
        topic_combo = ttk.Combobox(filter_frame, textvariable=self.topic_var, width=20, state='readonly')
        topic_combo['values'] = ('All', 'Anxiety', 'Depression', 'Stress Management',
                                 'Academic Pressure', 'Social Connection', 'Grief & Loss', 'Self-Care')
        topic_combo.current(0)
        topic_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text="Filter", command=self.load_groups).pack(side='left')

        # Groups list
        list_frame = ttk.LabelFrame(main_frame, text="Available Groups")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Group Name', 'Topic', 'Meeting Schedule', 'Members', 'Privacy', 'Status')
        self.groups_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.groups_tree.heading(col, text=col)
            if col == 'Group Name':
                self.groups_tree.column(col, width=200)
            elif col == 'Meeting Schedule':
                self.groups_tree.column(col, width=150)
            else:
                self.groups_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=scrollbar.set)

        self.groups_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.groups_tree.bind('<<TreeviewSelect>>', self.on_select)

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Group Details")
        details_frame.pack(fill='x', pady=(0, 15))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=6, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Join Group", command=self.join_group).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Details", command=self.view_full_details).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_groups(self):
        for item in self.groups_tree.get_children():
            self.groups_tree.delete(item)

        # Sample support groups
        groups = [
            ("Stress Busters", "Stress Management", "Mon/Wed 6PM", "12/15", "Closed", "Active",
             "Weekly peer support for managing academic and life stress. Share coping strategies and support each other."),
            ("Anxiety Support Circle", "Anxiety", "Tuesday 7PM", "8/12", "Closed", "Active",
             "Safe space to discuss anxiety, share experiences, and learn from peers dealing with similar challenges."),
            ("First Year Friends", "Social Connection", "Thursday 5PM", "15/20", "Open", "Active",
             "Connect with other first-year students, make friends, and navigate university life together."),
            ("Academic Success Group", "Academic Pressure", "Friday 4PM", "10/15", "Open", "Active",
             "Support for students dealing with academic pressure. Share study tips and encourage each other."),
            ("Mindfulness Together", "Self-Care", "Saturday 10AM", "6/10", "Open", "Active",
             "Practice mindfulness, meditation, and self-care techniques together in a supportive environment.")
        ]

        for group in groups:
            self.groups_tree.insert('', 'end', values=group[:6], tags=(group[6],))

    def on_select(self, event):
        selection = self.groups_tree.selection()
        if not selection:
            return

        item = self.groups_tree.item(selection[0])
        details = item['tags'][0] if item['tags'] else "No details available."

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)

    def join_group(self):
        selection = self.groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to join.")
            return

        item = self.groups_tree.item(selection[0])
        group_name = item['values'][0]
        privacy = item['values'][4]

        if privacy == "Closed":
            if messagebox.askyesno("Join Request",
                                  f"'{group_name}' is a closed group.\n\nSubmit a join request?"):
                messagebox.showinfo("Success",
                                   f"Join request submitted for '{group_name}'.\n\n"
                                   "The group moderator will review your request.")
        else:
            if messagebox.askyesno("Confirm", f"Join '{group_name}'?"):
                messagebox.showinfo("Success",
                                   f"You've joined '{group_name}'!\n\n"
                                   "You'll receive meeting reminders and can access group resources.")

    def view_full_details(self):
        selection = self.groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group.")
            return

        item = self.groups_tree.item(selection[0])
        values = item['values']
        details = item['tags'][0] if item['tags'] else ""

        info = f"""Group: {values[0]}
Topic: {values[1]}
Schedule: {values[2]}
Members: {values[3]}
Privacy: {values[4]}
Status: {values[5]}

Description:
{details}

Moderator: Anonymous (for privacy)
Established: 3 months ago
Meeting Location: Private (shared with members)
"""
        messagebox.showinfo("Group Details", info)



def create_support_tab(self):
    """Create peer support tab"""
    support_frame = ttk.Frame(self.notebook)
    self.notebook.add(support_frame, text="Peer Support")
    
    # Left panel
    left_panel = ttk.LabelFrame(support_frame, text="Support Actions")
    left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
    
    ttk.Button(left_panel, text="Browse Support Groups", 
              command=self.browse_support_groups).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Join Support Group", 
              command=self.join_support_group_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="My Support Groups", 
              command=self.view_my_support_groups).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Create Support Group", 
              command=self.create_support_group_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Wellness Resources", 
              command=self.view_wellness_resources).pack(fill='x', pady=2)
    
    # Right panel
    right_panel = ttk.LabelFrame(support_frame, text="Support Information")
    right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
    
    self.support_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, 
                                                 height=30, width=80)
    self.support_text.pack(fill='both', expand=True, padx=5, pady=5)


def browse_support_groups(self):
    """Browse support groups"""
    try:
        dialog = SupportGroupsDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def join_support_group_gui(self):
    """Join a support group"""
    try:
        dialog = SupportGroupsDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def view_my_support_groups(self):
    """View my support groups"""
    try:
        dialog = MySupportGroupsDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def create_support_group_gui(self):
    """Create a new support group"""
    try:
        dialog = CreateSupportGroupDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


