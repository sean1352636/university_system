"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import sys
from datetime import datetime, timedelta
import json
from education_system.university_system.infrastructure.database.db import sqlite3
from typing import Dict, List, Optional, Any
import logging
import urllib.request
import urllib.parse
import urllib.error

# Import custom exceptions for better error handling
from education_system.university_system.infrastructure.exceptions import (
    DatabaseError,
    QueryError,
    ValidationError,
    InvalidInputError,
    FileError,
    UniversityFileNotFoundError
)

# Import all original library functions
try:
    # Import from modular library package
    from education_system.university_system.modules.domain.academics.services.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from education_system.university_system.modules.domain.academics.services.library.menu import display_library_menu
    from education_system.university_system.modules.domain.academics.services.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from education_system.university_system.modules.domain.academics.services.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from education_system.university_system.modules.domain.academics.services.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from education_system.university_system.modules.domain.academics.services.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from education_system.university_system.modules.domain.academics.services.library.reading_lists import view_reading_list_details
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

# Import shared authentication system
try:
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None

from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD,
        ensure_student_finance_account_exists,
        top_up_student_finance_account
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Import matplotlib for library finance charts
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: Matplotlib not available for library finance charts")

# Import email service for library finance notifications
try:
    from education_system.university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_email_as_system(*args, **kwargs):
        return False
    print("Warning: Email service not available for library finance")

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None
_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

from .base import LibraryGUI

def show_reading_lists(self):
    """Show reading lists interface"""
    # Check permission instead of user directly
    if not self.check_permission('manage_reading_lists'):
        return

    self.clear_content_area()

    lists_frame = ttk.Frame(self.notebook)
    self.notebook.add(lists_frame, text="Reading Lists")

    title_label = ttk.Label(lists_frame, text="Reading Lists Management", style='Title.TLabel')
    title_label.pack(pady=10)

    # Control buttons
    control_frame = ttk.Frame(lists_frame)
    control_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(control_frame, text="Create New List", command=self.create_reading_list_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text="Import List", command=self.import_reading_list_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text=_("common.refresh"), command=self.refresh_reading_lists).pack(side=tk.LEFT, padx=5)

    # Reading lists table
    table_frame = ttk.Frame(lists_frame)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    columns = ('ID', 'Name', 'Description', 'Items', 'Type', 'Created')
    self.reading_lists_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=25)

    for col in columns:
        self.reading_lists_tree.heading(col, text=col)
        self.reading_lists_tree.column(col, width=120)

    # Add scrollbar
    scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.reading_lists_tree.yview)
    self.reading_lists_tree.configure(yscrollcommand=scrollbar.set)

    self.reading_lists_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Context menu
    self.create_reading_lists_context_menu()

    # Load data
    self.load_reading_lists()

    # Bind double-click
    self.reading_lists_tree.bind('<Double-1>', self.view_reading_list_details)

def create_reading_lists_context_menu(self):
    """Create context menu for reading lists"""
    self.reading_lists_context_menu = tk.Menu(self.master, tearoff=0)
    self.reading_lists_context_menu.add_command(label="View Details", command=self.view_reading_list_details)
    self.reading_lists_context_menu.add_command(label="Add Book", command=self.add_book_to_list)
    self.reading_lists_context_menu.add_command(label="Edit List", command=self.edit_reading_list)
    self.reading_lists_context_menu.add_separator()
    self.reading_lists_context_menu.add_command(label="Share List", command=self.share_reading_list)
    self.reading_lists_context_menu.add_command(label="Delete List", command=self.delete_reading_list)

    self.reading_lists_tree.bind('<Button-3>', self.show_reading_lists_context_menu)

def show_reading_lists_context_menu(self, event):
    """Show context menu for reading lists"""
    item = self.reading_lists_tree.selection()[0] if self.reading_lists_tree.selection() else None
    if item:
        self.reading_lists_context_menu.post(event.x_root, event.y_root)

def load_reading_lists(self):
    """Load reading lists data"""
    # Clear existing data
    for item in self.reading_lists_tree.get_children():
        self.reading_lists_tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
            SELECT rl.list_id, rl.name, rl.description, rl.created_date,
                   rl.is_public, rl.is_collaborative,
                   COUNT(rli.item_id) as item_count
            FROM reading_lists rl
            LEFT JOIN reading_list_items rli ON rl.list_id = rli.list_id
            WHERE rl.creator_id = ? OR rl.is_public = 1
            GROUP BY rl.list_id
            ORDER BY rl.created_date DESC
            ''', (get_current_user_id(),))

            lists = cursor.fetchall()
            conn.close()

            for lst in lists:
                list_id, name, desc, created, is_public, is_collab, count = lst
                list_type = "Public" if is_public else "Private"
                if is_collab:
                    list_type += " + Collab"

                desc_display = (desc[:30] + "...") if desc and len(desc) > 30 else (desc or "")

                self.reading_lists_tree.insert('', 'end', values=(
                    list_id, name, desc_display, count, list_type, created[:10]
                ))
        else:
            # Demo data
            demo_lists = [
                (1, "My Favorites", "Books I love", 5, "Private", "2024-01-15"),
                (2, "Science Fiction", "Best sci-fi books", 12, "Public", "2024-01-10"),
            ]

            for lst in demo_lists:
                self.reading_lists_tree.insert('', 'end', values=lst)

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Error loading reading lists: {str(e)}")

def refresh_reading_lists(self):
    """Refresh reading lists"""
    self.load_reading_lists()

def create_reading_list_dialog(self):
    """Create new reading list dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.create_reading_list"))
    dialog.geometry("400x350")
    dialog.transient(self.master)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Form fields
    ttk.Label(main_frame, text="List Name:").pack(anchor='w', pady=(0, 5))
    name_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=name_var, width=40).pack(anchor='w', pady=(0, 10))

    ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(0, 5))
    desc_text = tk.Text(main_frame, height=4, width=40)
    desc_text.pack(anchor='w', pady=(0, 10))

    ttk.Label(main_frame, text="Category:").pack(anchor='w', pady=(0, 5))
    category_var = tk.StringVar()
    category_combo = ttk.Combobox(main_frame, textvariable=category_var, width=37)
    category_combo['values'] = ('General', 'Fiction', 'Non-Fiction', 'Science', 'History', 'Educational')
    category_combo.pack(anchor='w', pady=(0, 10))

    # Options
    options_frame = ttk.LabelFrame(main_frame, text="Options")
    options_frame.pack(fill=tk.X, pady=(0, 10))

    is_public_var = tk.BooleanVar()
    ttk.Checkbutton(options_frame, text="Make this list public", variable=is_public_var).pack(anchor='w', padx=5, pady=5)

    is_collaborative_var = tk.BooleanVar()
    ttk.Checkbutton(options_frame, text="Allow others to add books", variable=is_collaborative_var).pack(anchor='w', padx=5, pady=5)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)

    def create_list():
        name = name_var.get().strip()
        description = desc_text.get("1.0", tk.END).strip()
        category = category_var.get().strip()

        if not name:
            messagebox.showwarning(_("common.warning"), "Please enter a list name")
            return

        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                success = self.create_reading_list_database(name, description, category, 
                                                          is_public_var.get(), is_collaborative_var.get())
                if success:
                    messagebox.showinfo(_("common.success"), f"Reading list '{name}' created successfully!")
                    dialog.destroy()
                    self.refresh_reading_lists()
                else:
                    messagebox.showerror(_("common.error"), "Failed to create reading list")
            else:
                messagebox.showinfo(_("common.demo"), f"Reading list '{name}' would be created")
                dialog.destroy()
        except tk.TclError as e:
            messagebox.showerror(_("common.error"), f"Error creating reading list: {str(e)}")

    ttk.Button(button_frame, text="Create", command=create_list).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

def create_reading_list_database(self, name, description, category, is_public, is_collaborative):
    """Create reading list in database"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO reading_lists 
        (name, description, creator_id, created_date, is_public, is_collaborative, category)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, get_current_user_id(), now, is_public, is_collaborative, category))

        conn.commit()
        conn.close()

        # Log the action
        if ORIGINAL_LIBRARY_AVAILABLE:
            log_audit_event(get_current_user_id(), f"GUI: Created reading list '{name}'", "reading_lists")

        return True

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error creating reading list: {e}")
        return False

def view_reading_list_details(self, event=None):
    """View reading list details"""
    selection = self.reading_lists_tree.selection()
    if not selection:
        if event:  # Called from double-click
            return
        messagebox.showwarning(_("common.warning"), "Please select a reading list first")
        return

    item = self.reading_lists_tree.item(selection[0])
    list_id = item['values'][0]
    list_name = item['values'][1]

    # Create new tab for list details
    details_frame = ttk.Frame(self.notebook)
    self.notebook.add(details_frame, text=f"List: {list_name}")
    self.notebook.select(details_frame)

    # List info
    info_frame = ttk.LabelFrame(details_frame, text="List Information")
    info_frame.pack(fill=tk.X, padx=10, pady=5)

    # Get and display list details
    list_details = self.get_reading_list_details(list_id)
    if list_details:
        ttk.Label(info_frame, text=f"Name: {list_details['name']}", style='Heading.TLabel').pack(anchor='w', padx=5, pady=2)
        if list_details['description']:
            ttk.Label(info_frame, text=f"Description: {list_details['description']}").pack(anchor='w', padx=5, pady=2)
        ttk.Label(info_frame, text=f"Creator: {list_details['creator_id']}").pack(anchor='w', padx=5, pady=2)
        ttk.Label(info_frame, text=f"Created: {list_details['created_date'][:10]}").pack(anchor='w', padx=5, pady=2)

    # List items
    items_frame = ttk.LabelFrame(details_frame, text="Books in this List")
    items_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # Items table
    items_columns = ('Book ID', 'Title', 'Author', 'Status', 'Added Date')
    items_tree = ttk.Treeview(items_frame, columns=items_columns, show='headings', height=12)

    for col in items_columns:
        items_tree.heading(col, text=col)
        items_tree.column(col, width=120)

    # Scrollbar
    items_scrollbar = ttk.Scrollbar(items_frame, orient=tk.VERTICAL, command=items_tree.yview)
    items_tree.configure(yscrollcommand=items_scrollbar.set)

    items_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    items_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Load list items
    self.load_reading_list_items(items_tree, list_id)

def get_reading_list_details(self, list_id):
    """Get reading list details"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return None

            cursor = conn.cursor()
            cursor.execute('''
            SELECT name, description, creator_id, created_date, is_public, is_collaborative, category
            FROM reading_lists WHERE list_id = ?
            ''', (list_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                columns = ['name', 'description', 'creator_id', 'created_date', 'is_public', 'is_collaborative', 'category']
                return dict(zip(columns, result))
        else:
            return {
                'name': 'Demo List',
                'description': 'Demo reading list',
                'creator_id': 'demo_user',
                'created_date': '2024-01-15',
                'is_public': True,
                'is_collaborative': False,
                'category': 'General'
            }
    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error getting reading list details: {e}")
        return None

def load_reading_list_items(self, tree, list_id):
    """Load reading list items"""
    # Clear existing data
    for item in tree.get_children():
        tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
            SELECT b.book_id, b.title, b.author, b.status, rli.added_date
            FROM reading_list_items rli
            JOIN books b ON rli.book_id = b.book_id
            WHERE rli.list_id = ?
            ORDER BY rli.added_date DESC
            ''', (list_id,))

            items = cursor.fetchall()
            conn.close()

            for item in items:
                book_id, title, author, status, added_date = item
                tree.insert('', 'end', values=(book_id, title, author, status, added_date[:10]))
        else:
            # Demo data
            demo_items = [
                ("B10001", "Sample Book 1", "Author 1", "Available", "2024-01-15"),
                ("B10002", "Sample Book 2", "Author 2", "Checked Out", "2024-01-14"),
            ]

            for item in demo_items:
                tree.insert('', 'end', values=item)

    except tk.TclError as e:
        print(f"Error loading reading list items: {e}")

def manage_reading_lists_gui(self):
    """Manage reading lists"""
    lists_window = tk.Toplevel(self.master)
    lists_window.title("Reading Lists")
    lists_window.geometry("900x600")

    ttk.Label(lists_window, text="Reading Lists Management",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Button frame
    button_frame = ttk.Frame(lists_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Create New List", command=self.create_reading_list_gui).pack(side=tk.LEFT, padx=5)

    # Lists table
    table_frame = ttk.Frame(lists_window)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('ID', 'Name', 'Description', 'Creator', 'Created', 'Public', 'Books')
    lists_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

    for col in columns:
        lists_tree.heading(col, text=col)
        lists_tree.column(col, width=120)

    scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=lists_tree.yview)
    lists_tree.configure(yscrollcommand=scrollbar.set)

    lists_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def load_lists():
        for item in lists_tree.get_children():
            lists_tree.delete(item)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT l.list_id, l.name, l.description, l.creator_id, l.created_date, l.is_public,
                   COUNT(i.item_id) as book_count
            FROM reading_lists l
            LEFT JOIN reading_list_items i ON l.list_id = i.list_id
            GROUP BY l.list_id
            ORDER BY l.created_date DESC
            ''')

            for row in cursor.fetchall():
                lists_tree.insert('', 'end', values=(
                    row[0], row[1], row[2][:30], row[3], row[4][:10],
                    "Yes" if row[5] else "No", row[6]
                ))

            conn.close()

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to load lists: {str(e)}")

    def view_list_details():
        selection = lists_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), "Please select a list")
            return

        item = lists_tree.item(selection[0])
        list_id = item['values'][0]
        self.view_reading_list_details_gui(list_id)

    def delete_list():
        selection = lists_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), "Please select a list to delete")
            return

        item = lists_tree.item(selection[0])
        list_id = item['values'][0]
        list_name = item['values'][1]

        if messagebox.askyesno("Confirm Delete", f"Delete reading list '{list_name}'?"):
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Delete list items first
                cursor.execute('DELETE FROM reading_list_items WHERE list_id = ?', (list_id,))
                # Delete list
                cursor.execute('DELETE FROM reading_lists WHERE list_id = ?', (list_id,))

                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), f"Deleted reading list {list_id}", "reading_lists")
                messagebox.showinfo(_("common.success"), "Reading list deleted")
                load_lists()

            except (sqlite3.Error, DatabaseError, tk.TclError) as e:
                messagebox.showerror(_("common.error"), f"Failed to delete list: {str(e)}")

    # Action buttons
    action_frame = ttk.Frame(lists_window)
    action_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(action_frame, text="View Details", command=view_list_details).pack(side=tk.LEFT, padx=5)
    ttk.Button(action_frame, text="Delete List", command=delete_list).pack(side=tk.LEFT, padx=5)
    ttk.Button(action_frame, text=_("common.refresh"), command=load_lists).pack(side=tk.LEFT, padx=5)
    ttk.Button(action_frame, text=_("common.close"), command=lists_window.destroy).pack(side=tk.RIGHT, padx=5)

    # Load initial data
    load_lists()

def create_reading_list_gui(self):
    """Create a new reading list"""
    create_window = tk.Toplevel(self.master)
    create_window.title("Create Reading List")
    create_window.geometry("500x350")

    ttk.Label(create_window, text="Create New Reading List",
             font=('Arial', 14, 'bold')).pack(pady=10)

    # Form frame
    form_frame = ttk.LabelFrame(create_window, text="List Information", padding=15)
    form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    name_var = tk.StringVar()
    desc_var = tk.StringVar()
    is_public_var = tk.BooleanVar(value=False)
    is_collaborative_var = tk.BooleanVar(value=False)

    ttk.Label(form_frame, text="List Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
    ttk.Entry(form_frame, textvariable=name_var, width=40).grid(row=0, column=1, padx=10, pady=5)

    ttk.Label(form_frame, text="Description:").grid(row=1, column=0, sticky=tk.W, pady=5)
    desc_entry = tk.Text(form_frame, height=4, width=40)
    desc_entry.grid(row=1, column=1, padx=10, pady=5)

    ttk.Checkbutton(form_frame, text="Public (visible to everyone)",
                   variable=is_public_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)

    ttk.Checkbutton(form_frame, text="Collaborative (others can add books)",
                   variable=is_collaborative_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)

    def create_list():
        name = name_var.get().strip()
        description = desc_entry.get('1.0', tk.END).strip()

        if not name:
            messagebox.showerror(_("common.error"), "Please enter a list name")
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            creator_id = get_current_user_id()
            created_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO reading_lists (
                name, description, creator_id, created_date, is_public, is_collaborative
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, description, creator_id, created_date,
                 1 if is_public_var.get() else 0,
                 1 if is_collaborative_var.get() else 0))

            conn.commit()
            conn.close()

            log_audit_event(creator_id, f"Created reading list: {name}", "reading_lists")

            messagebox.showinfo(_("common.success"), "Reading list created successfully!")
            create_window.destroy()

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to create list: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(create_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Create", command=create_list).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=create_window.destroy).pack(side=tk.LEFT, padx=5)

def view_reading_list_details_gui(self, list_id):
    """View details of a specific reading list"""
    details_window = tk.Toplevel(self.master)
    details_window.title("Reading List Details")
    details_window.geometry("800x600")

    ttk.Label(details_window, text="Reading List Details",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # List info frame
    info_frame = ttk.LabelFrame(details_window, text="List Information", padding=10)
    info_frame.pack(fill=tk.X, padx=10, pady=10)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT name, description, creator_id, created_date, is_public, is_collaborative
        FROM reading_lists WHERE list_id = ?
        ''', (list_id,))

        list_info = cursor.fetchone()

        if list_info:
            ttk.Label(info_frame, text=f"Name: {list_info[0]}", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"Description: {list_info[1] or 'No description'}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"Created by: {list_info[2]} on {list_info[3][:10]}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"Public: {'Yes' if list_info[4] else 'No'}").pack(anchor=tk.W, pady=2)

        conn.close()

    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Failed to load list info: {str(e)}")
        details_window.destroy()
        return

    # Books in list
    books_frame = ttk.LabelFrame(details_window, text="Books in List", padding=10)
    books_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('Book ID', 'Title', 'Author', 'Added Date', 'Added By')
    books_tree = ttk.Treeview(books_frame, columns=columns, show='headings', height=12)

    for col in columns:
        books_tree.heading(col, text=col)
        books_tree.column(col, width=150)

    books_tree.pack(fill=tk.BOTH, expand=True)

    def load_books():
        for item in books_tree.get_children():
            books_tree.delete(item)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT b.book_id, b.title, b.author, i.added_date, i.added_by
            FROM reading_list_items i
            JOIN books b ON i.book_id = b.book_id
            WHERE i.list_id = ?
            ORDER BY i.added_date DESC
            ''', (list_id,))

            for row in cursor.fetchall():
                books_tree.insert('', 'end', values=row)

            conn.close()

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to load books: {str(e)}")

    load_books()

    # Button frame
    button_frame = ttk.Frame(details_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text=_("common.close"), command=details_window.destroy).pack(side=tk.RIGHT, padx=5)

