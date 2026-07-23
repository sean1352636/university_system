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


class ClubJoinDialog:
    """Dialog for joining a club"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Join Club")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_clubs()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Join a Club", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Club list
        list_frame = ttk.LabelFrame(main_frame, text="Available Clubs")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        # Treeview for clubs
        columns = ('ID', 'Name', 'Category', 'Members')
        self.clubs_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            self.clubs_tree.heading(col, text=col)
            self.clubs_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.clubs_tree.yview)
        self.clubs_tree.configure(yscrollcommand=scrollbar.set)

        self.clubs_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Join Selected Club",
                  command=self.join_selected_club).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel",
                  command=self.cancel).pack(side='left')

    def load_clubs(self):
        """Load available clubs into the treeview"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT club_id, club_name, category, member_count
            FROM student_clubs
            WHERE status = 'active'
            ORDER BY club_name
            ''')

            clubs = cursor.fetchall()

            for club in clubs:
                self.clubs_tree.insert('', 'end', values=club)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load clubs: {str(e)}")

    def join_selected_club(self):
        """Join the selected club"""
        selection = self.clubs_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a club to join.")
            return

        item = self.clubs_tree.item(selection[0])
        club_id = item['values'][0]
        club_name = item['values'][1]

        # Confirm join
        if messagebox.askyesno("Confirm", f"Do you want to join {club_name}?"):
            try:
                # Call CLI function to join club
                # In a full implementation, you'd extract the join logic from the CLI function
                self.result = {'club_id': club_id, 'club_name': club_name}
                messagebox.showinfo("Success", f"Successfully joined {club_name}!")
                self.dialog.destroy()
            except (tk.TclError, AttributeError) as e:
                messagebox.showerror("Error", f"Failed to join club: {str(e)}")

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()



class ClubCreateDialog:
    """Dialog for creating a new club"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Club")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Create New Club", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 20))

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='x', pady=(0, 20))

        # Club name
        ttk.Label(form_frame, text="Club Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.name_var, width=40).grid(row=0, column=1, sticky='ew', pady=5)

        # Description
        ttk.Label(form_frame, text="Description:").grid(row=1, column=0, sticky='nw', pady=5)
        self.description_text = tk.Text(form_frame, height=4, width=40)
        self.description_text.grid(row=1, column=1, sticky='ew', pady=5)

        # Category
        ttk.Label(form_frame, text="Category:").grid(row=2, column=0, sticky='w', pady=5)
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=self.category_var, width=37)
        category_combo['values'] = ('Academic', 'Sports', 'Cultural', 'Technology', 'Service', 'Other')
        category_combo.grid(row=2, column=1, sticky='ew', pady=5)

        # Officers
        officer_frame = ttk.LabelFrame(form_frame, text="Club Officers")
        officer_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(officer_frame, text="President ID:").grid(row=0, column=0, sticky='w', pady=2)
        self.president_var = tk.StringVar()
        ttk.Entry(officer_frame, textvariable=self.president_var, width=20).grid(row=0, column=1, sticky='ew', pady=2)

        ttk.Label(officer_frame, text="Treasurer ID:").grid(row=1, column=0, sticky='w', pady=2)
        self.treasurer_var = tk.StringVar()
        ttk.Entry(officer_frame, textvariable=self.treasurer_var, width=20).grid(row=1, column=1, sticky='ew', pady=2)

        ttk.Label(officer_frame, text="Secretary ID:").grid(row=2, column=0, sticky='w', pady=2)
        self.secretary_var = tk.StringVar()
        ttk.Entry(officer_frame, textvariable=self.secretary_var, width=20).grid(row=2, column=1, sticky='ew', pady=2)

        # Configure grid weights
        form_frame.columnconfigure(1, weight=1)
        officer_frame.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Create Club",
                  command=self.create_club).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel",
                  command=self.cancel).pack(side='left')

    def create_club(self):
        """Create the club with provided information"""
        # Validate inputs
        if not self.name_var.get().strip():
            messagebox.showwarning("Warning", "Club name is required.")
            return

        if not self.category_var.get().strip():
            messagebox.showwarning("Warning", "Category is required.")
            return

        if not all([self.president_var.get().strip(),
                   self.treasurer_var.get().strip(),
                   self.secretary_var.get().strip()]):
            messagebox.showwarning("Warning", "All officer positions must be filled.")
            return

        try:
            # In a full implementation, you'd call the actual database function
            club_data = {
                'name': self.name_var.get().strip(),
                'description': self.description_text.get(1.0, tk.END).strip(),
                'category': self.category_var.get().strip(),
                'president_id': self.president_var.get().strip(),
                'treasurer_id': self.treasurer_var.get().strip(),
                'secretary_id': self.secretary_var.get().strip()
            }

            self.result = club_data
            messagebox.showinfo("Success", f"Club '{club_data['name']}' created successfully!")
            self.dialog.destroy()

        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Failed to create club: {str(e)}")

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()



class ClubManageDialog:
    """Dialog for managing clubs"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Clubs")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_manageable_clubs()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Club Management", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Club selection
        select_frame = ttk.LabelFrame(main_frame, text="Select Club to Manage")
        select_frame.pack(fill='x', pady=(0, 10))

        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(select_frame, textvariable=self.club_var, width=50)
        self.club_combo.pack(side='left', padx=5, pady=5)
        self.club_combo.bind('<<ComboboxSelected>>', self.on_club_selected)

        ttk.Button(select_frame, text="Refresh",
                  command=self.load_manageable_clubs).pack(side='left', padx=5)

        # Management options
        options_frame = ttk.LabelFrame(main_frame, text="Management Options")
        options_frame.pack(fill='both', expand=True, pady=(0, 10))

        # Create notebook for management tabs
        self.manage_notebook = ttk.Notebook(options_frame)
        self.manage_notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Members tab
        members_frame = ttk.Frame(self.manage_notebook)
        self.manage_notebook.add(members_frame, text="Members")

        self.members_tree = ttk.Treeview(members_frame, columns=('ID', 'Name', 'Role', 'Join Date'),
                                        show='tree headings', height=10)
        for col in ('ID', 'Name', 'Role', 'Join Date'):
            self.members_tree.heading(col, text=col)
            self.members_tree.column(col, width=150)
        self.members_tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Events tab
        events_frame = ttk.Frame(self.manage_notebook)
        self.manage_notebook.add(events_frame, text="Events")

        ttk.Label(events_frame, text="Club events management would go here").pack(pady=20)

        # Finances tab
        finances_frame = ttk.Frame(self.manage_notebook)
        self.manage_notebook.add(finances_frame, text="Finances")

        ttk.Label(finances_frame, text="Financial management would go here").pack(pady=20)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Close",
                  command=self.dialog.destroy).pack(side='right')

    def load_manageable_clubs(self):
        """Load clubs that the current user can manage"""
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            # Get student ID
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                return

            student_id = result[0]

            # Get clubs where user is an officer
            cursor.execute('''
            SELECT c.club_id, c.club_name
            FROM student_clubs c
            WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
            AND c.status = 'active'
            ORDER BY c.club_name
            ''', (student_id, student_id, student_id))

            clubs = cursor.fetchall()

            club_options = [f"{club[1]} (ID: {club[0]})" for club in clubs]
            self.club_combo['values'] = club_options

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load clubs: {str(e)}")

    def on_club_selected(self, event=None):
        """Handle club selection"""
        selection = self.club_var.get()
        if not selection:
            return

        # Extract club ID from selection
        try:
            club_id = selection.split("ID: ")[1].rstrip(")")
            self.load_club_members(club_id)
        except (ValueError, IndexError, AttributeError):
            pass

    def load_club_members(self, club_id):
        """Load members for the selected club"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT m.student_id, s.first_name, s.last_name, m.role, m.join_date
            FROM club_members m
            JOIN students s ON m.student_id = s.student_id
            WHERE m.club_id = ?
            ORDER BY m.role, m.join_date
            ''', (club_id,))

            members = cursor.fetchall()

            # Clear existing items
            for item in self.members_tree.get_children():
                self.members_tree.delete(item)

            # Add members to tree
            for member in members:
                name = f"{member[1]} {member[2]}"
                self.members_tree.insert('', 'end', values=(member[0], name, member[3], member[4]))

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load members: {str(e)}")



