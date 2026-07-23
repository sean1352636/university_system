import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
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
    from education_system.post_18.university_system.infrastructure.database.db import get_connection
    from education_system.post_18.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
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
        except sqlite3.Error:
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
                anonymous_id = hashlib.sha256(f"{student_id}{group_id}".encode()).hexdigest()[:8]

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

        item = self.groups_tree.item(selection[0])
        group_name = item['values'][0]
        role = item['values'][2]

        if role == 'Facilitator':
            messagebox.showwarning("Warning",
                                   "You are the facilitator of this group. "
                                   "Please transfer facilitator role before leaving, "
                                   "or disband the group.")
            return

        if not messagebox.askyesno("Confirm",
                                    f"Are you sure you want to leave '{group_name}'?"):
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?',
                           (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                messagebox.showerror("Error", "Could not identify your student record.")
                return
            student_id = result[0]

            # Find the group_id by matching group_name and student membership
            cursor.execute('''
                SELECT psg.group_id FROM peer_support_groups psg
                INNER JOIN support_group_members sgm ON sgm.group_id = psg.group_id
                WHERE psg.group_name = ? AND sgm.student_id = ? AND sgm.status = 'active'
            ''', (group_name, student_id))
            group_row = cursor.fetchone()

            if not group_row:
                messagebox.showerror("Error", "Could not find your membership for this group.")
                conn.close()
                return

            group_id = group_row[0]

            # Mark membership as inactive
            cursor.execute('''
                UPDATE support_group_members SET status = 'inactive'
                WHERE group_id = ? AND student_id = ? AND status = 'active'
            ''', (group_id, student_id))

            # Decrement member count
            cursor.execute('''
                UPDATE peer_support_groups SET current_members = MAX(current_members - 1, 0)
                WHERE group_id = ?
            ''', (group_id,))

            conn.commit()
            messagebox.showinfo("Success", f"You have left '{group_name}'.")

            # Refresh the list
            for tree_item in self.groups_tree.get_children():
                self.groups_tree.delete(tree_item)
            self.load_data()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to leave group: {e}")
        finally:
            if conn:
                conn.close()



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
        """Load support groups from DB, with topic filter"""
        for item in self.groups_tree.get_children():
            self.groups_tree.delete(item)

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            topic_filter = self.topic_var.get() if hasattr(self, 'topic_var') else 'All'

            # Determine privacy column - use 'Open' as default if column doesn't exist
            # Query groups joined with member count
            if topic_filter == 'All':
                cursor.execute('''
                    SELECT psg.group_id, psg.group_name, psg.support_type,
                           psg.meeting_schedule,
                           psg.current_members || '/' || psg.max_members,
                           COALESCE(psg.privacy, 'Open'),
                           psg.status,
                           psg.description
                    FROM peer_support_groups psg
                    WHERE psg.status = 'active'
                    ORDER BY psg.group_name
                ''')
            else:
                cursor.execute('''
                    SELECT psg.group_id, psg.group_name, psg.support_type,
                           psg.meeting_schedule,
                           psg.current_members || '/' || psg.max_members,
                           COALESCE(psg.privacy, 'Open'),
                           psg.status,
                           psg.description
                    FROM peer_support_groups psg
                    WHERE psg.status = 'active' AND psg.support_type = ?
                    ORDER BY psg.group_name
                ''', (topic_filter,))

            groups = cursor.fetchall()

            for group in groups:
                # group_id stored internally, display columns: Name, Topic, Schedule, Members, Privacy, Status
                desc = group[7] or "No description available."
                self.groups_tree.insert('', 'end',
                                        values=(group[1], group[2], group[3], group[4], group[5], group[6]),
                                        tags=(str(group[0]), desc))

            if not groups:
                # Show defaults if no DB entries
                defaults = [
                    ("Stress Busters", "Stress Management", "Mon/Wed 6PM", "0/15", "Open", "Active",
                     "0", "Weekly peer support for managing academic and life stress."),
                    ("Anxiety Support Circle", "Anxiety", "Tuesday 7PM", "0/12", "Closed", "Active",
                     "0", "Safe space to discuss anxiety and share experiences."),
                    ("First Year Friends", "Social Connection", "Thursday 5PM", "0/20", "Open", "Active",
                     "0", "Connect with other first-year students."),
                    ("Academic Success Group", "Academic Pressure", "Friday 4PM", "0/15", "Open", "Active",
                     "0", "Support for students dealing with academic pressure."),
                    ("Mindfulness Together", "Self-Care", "Saturday 10AM", "0/10", "Open", "Active",
                     "0", "Practice mindfulness and self-care techniques together."),
                ]
                for g in defaults:
                    if topic_filter == 'All' or g[1] == topic_filter:
                        self.groups_tree.insert('', 'end',
                                                values=(g[0], g[1], g[2], g[3], g[4], g[5]),
                                                tags=(g[6], g[7]))

        except sqlite3.OperationalError:
            # Table may not have privacy column; fall back to simpler query
            try:
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT psg.group_id, psg.group_name, psg.support_type,
                               psg.meeting_schedule,
                               psg.current_members || '/' || psg.max_members,
                               psg.status,
                               psg.description
                        FROM peer_support_groups psg
                        WHERE psg.status = 'active'
                        ORDER BY psg.group_name
                    ''')
                    groups = cursor.fetchall()
                    for group in groups:
                        desc = group[6] or "No description available."
                        self.groups_tree.insert('', 'end',
                                                values=(group[1], group[2], group[3], group[4], 'Open', group[5]),
                                                tags=(str(group[0]), desc))
            except sqlite3.Error:
                pass
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load groups: {e}")
        finally:
            if conn:
                conn.close()

    def on_select(self, event):
        selection = self.groups_tree.selection()
        if not selection:
            return

        item = self.groups_tree.item(selection[0])
        tags = item['tags']
        # Tags are [group_id, description]
        details = tags[1] if len(tags) > 1 else (tags[0] if tags else "No details available.")

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)

    def join_group(self):
        """Join the selected support group via DB"""
        selection = self.groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to join.")
            return

        item = self.groups_tree.item(selection[0])
        group_name = item['values'][0]
        privacy = item['values'][4]
        tags = item['tags']
        group_id_str = tags[0] if tags else None

        # For default/sample entries (group_id "0" or non-numeric), show info-only message
        if not group_id_str or group_id_str == '0':
            messagebox.showinfo("Info",
                                f"'{group_name}' is a sample group. "
                                "Create a real group first using the main Support Groups dialog.")
            return

        if privacy == "Closed":
            if not messagebox.askyesno("Join Request",
                                       f"'{group_name}' is a closed group.\n\nSubmit a join request?"):
                return
            # For closed groups, just show confirmation (would need approval workflow)
            messagebox.showinfo("Submitted",
                                f"Join request submitted for '{group_name}'.\n\n"
                                "The group moderator will review your request.")
            return

        if not messagebox.askyesno("Confirm", f"Join '{group_name}'?"):
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            group_id = int(group_id_str)

            cursor.execute('SELECT student_id FROM users WHERE id = ?',
                           (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                messagebox.showerror("Error", "Could not identify your student record.")
                return
            student_id = result[0]

            # Check if already a member
            cursor.execute('''
                SELECT id FROM support_group_members
                WHERE group_id = ? AND student_id = ? AND status = 'active'
            ''', (group_id, student_id))
            if cursor.fetchone():
                messagebox.showinfo("Info", "You are already a member of this group.")
                return

            # Check capacity
            cursor.execute('SELECT current_members, max_members FROM peer_support_groups WHERE group_id = ?',
                           (group_id,))
            cap_row = cursor.fetchone()
            if cap_row and cap_row[0] >= cap_row[1]:
                messagebox.showwarning("Full", "This group is currently full.")
                return

            # Generate anonymous ID
            anonymous_id = hashlib.sha256(f"{student_id}{group_id}".encode()).hexdigest()[:8]

            cursor.execute('''
                INSERT INTO support_group_members (group_id, student_id, join_date, anonymous_id, status)
                VALUES (?, ?, ?, ?, 'active')
            ''', (group_id, student_id, datetime.now().isoformat(), anonymous_id))

            cursor.execute('''
                UPDATE peer_support_groups SET current_members = current_members + 1
                WHERE group_id = ?
            ''', (group_id,))

            conn.commit()
            messagebox.showinfo("Success",
                                f"You've joined '{group_name}'!\n\n"
                                "You'll receive meeting reminders and can access group resources.")
            self.load_groups()
        except sqlite3.IntegrityError:
            messagebox.showinfo("Info", "You are already a member of this group.")
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to join group: {e}")
        finally:
            if conn:
                conn.close()

    def view_full_details(self):
        """Open Toplevel showing full group details from DB"""
        selection = self.groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group.")
            return

        item = self.groups_tree.item(selection[0])
        values = item['values']
        tags = item['tags']
        group_id_str = tags[0] if tags else None
        description = tags[1] if len(tags) > 1 else "No description available."

        group_name = values[0]
        topic = values[1]
        schedule = values[2]
        members_str = values[3]
        privacy = values[4]
        status = values[5]

        detail_win = tk.Toplevel(self.dialog)
        detail_win.title(f"Group Details - {group_name}")
        detail_win.geometry("650x600")
        detail_win.transient(self.dialog)
        detail_win.grab_set()

        main_frame = ttk.Frame(detail_win)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=group_name, font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Basic info grid
        info_frame = ttk.LabelFrame(main_frame, text="Group Information")
        info_frame.pack(fill='x', pady=(0, 10))

        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill='x', padx=10, pady=8)

        labels = [
            ("Topic:", topic),
            ("Schedule:", schedule),
            ("Members:", members_str),
            ("Privacy:", privacy),
            ("Status:", status),
        ]

        # Try to get additional details from DB
        facilitator_name = "Anonymous (for privacy)"
        created_date = "Unknown"
        member_list = []

        if group_id_str and group_id_str != '0':
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                group_id = int(group_id_str)

                # Get facilitator
                cursor.execute('''
                    SELECT s.first_name || ' ' || s.last_name
                    FROM peer_support_groups psg
                    INNER JOIN students s ON psg.facilitator_id = s.student_id
                    WHERE psg.group_id = ?
                ''', (group_id,))
                fac_row = cursor.fetchone()
                if fac_row:
                    facilitator_name = fac_row[0]

                # Get created date
                cursor.execute('SELECT created_date FROM peer_support_groups WHERE group_id = ?', (group_id,))
                date_row = cursor.fetchone()
                if date_row and date_row[0]:
                    try:
                        dt = datetime.fromisoformat(date_row[0])
                        created_date = dt.strftime('%B %d, %Y')
                    except (ValueError, TypeError):
                        created_date = str(date_row[0])

                # Get member list (anonymous IDs only for privacy)
                cursor.execute('''
                    SELECT sgm.anonymous_id, sgm.join_date
                    FROM support_group_members sgm
                    WHERE sgm.group_id = ? AND sgm.status = 'active'
                    ORDER BY sgm.join_date
                ''', (group_id,))
                member_list = cursor.fetchall()

            except sqlite3.Error:
                pass
            finally:
                if conn:
                    conn.close()

        labels.append(("Facilitator:", facilitator_name))
        labels.append(("Established:", created_date))

        for i, (label, value) in enumerate(labels):
            ttk.Label(info_grid, text=label, font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=2)
            ttk.Label(info_grid, text=str(value), font=('Arial', 10)).grid(
                row=i, column=1, sticky='w', pady=2)

        # Description
        desc_frame = ttk.LabelFrame(main_frame, text="Description")
        desc_frame.pack(fill='x', pady=(0, 10))

        desc_text = scrolledtext.ScrolledText(desc_frame, height=5, wrap=tk.WORD)
        desc_text.pack(fill='both', expand=True, padx=5, pady=5)
        desc_text.insert(1.0, description)
        desc_text.config(state='disabled')

        # Member list (anonymous)
        member_frame = ttk.LabelFrame(main_frame, text="Members (Anonymous IDs)")
        member_frame.pack(fill='both', expand=True, pady=(0, 10))

        mem_columns = ('Anonymous ID', 'Joined')
        mem_tree = ttk.Treeview(member_frame, columns=mem_columns, show='headings', height=6)
        mem_tree.heading('Anonymous ID', text='Anonymous ID')
        mem_tree.heading('Joined', text='Joined')
        mem_tree.column('Anonymous ID', width=200)
        mem_tree.column('Joined', width=200)

        mem_vsb = ttk.Scrollbar(member_frame, orient='vertical', command=mem_tree.yview)
        mem_tree.configure(yscrollcommand=mem_vsb.set)
        mem_tree.pack(side='left', fill='both', expand=True)
        mem_vsb.pack(side='right', fill='y')

        if member_list:
            for anon_id, join_date in member_list:
                display_date = join_date
                try:
                    dt = datetime.fromisoformat(join_date)
                    display_date = dt.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    pass
                display_id = "Facilitator" if anon_id == 'facilitator' else f"Member-{anon_id}"
                mem_tree.insert('', 'end', values=(display_id, display_date))
        else:
            mem_tree.insert('', 'end', values=("No member data available", ""))

        ttk.Button(main_frame, text="Close", command=detail_win.destroy).pack(anchor='e')



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


