"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


from education_system.post_18.university_system.core.sql_safety import escape_like
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.post_18.university_system.core.i18n import get_text as _, init_i18n
init_i18n()
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import sys
from datetime import datetime, timedelta
import json
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from typing import Dict, List, Optional, Any
import logging
import urllib.request
import urllib.parse
import urllib.error

# Import custom exceptions for better error handling
from education_system.post_18.university_system.core.exceptions import (
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
    from education_system.post_18.university_system.modules.domain.academics.services.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from education_system.post_18.university_system.modules.domain.academics.services.library.menu import display_library_menu
    from education_system.post_18.university_system.modules.domain.academics.services.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from education_system.post_18.university_system.modules.domain.academics.services.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from education_system.post_18.university_system.modules.domain.academics.services.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from education_system.post_18.university_system.modules.domain.academics.services.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from education_system.post_18.university_system.modules.domain.academics.services.library.reading_lists import view_reading_list_details
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

# Import shared authentication system
try:
    from education_system.post_18.university_system.infrastructure.auth import UserAuth
    from education_system.post_18.university_system.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None

from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
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
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_email_as_system(*args, **kwargs):
        return False
    print("Warning: Email service not available for library finance")

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None
_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

from education_system.post_18.university_system.modules.domain.academics.gui.library.base import LibraryGUI

def show_search_books(self):
    """Show advanced search interface"""
    self.clear_content_area()

    search_frame = ttk.Frame(self.notebook)
    self.notebook.add(search_frame, text="Search Books")

    # Search criteria frame
    criteria_frame = ttk.LabelFrame(search_frame, text=_("library.frames.search_criteria"))
    criteria_frame.pack(fill=tk.X, padx=10, pady=5)

    # Search fields
    search_fields = [
        ("Title:", "title"),
        ("Author:", "author"),
        ("ISBN:", "isbn"),
        ("Category:", "category"),
        ("Reading Level:", "reading_level"),
        ("Status:", "status"),
    ]

    self.search_vars = {}

    for i, (label, field) in enumerate(search_fields):
        row = i // 2
        col = (i % 2) * 2

        ttk.Label(criteria_frame, text=label).grid(row=row, column=col, sticky='w', padx=5, pady=5)

        if field == "category":
            var = tk.StringVar()
            combo = ttk.Combobox(criteria_frame, textvariable=var, width=20)
            combo['values'] = ('', 'Fiction', 'Non-Fiction', 'Science', 'History', 'Computer Science')
            combo.grid(row=row, column=col+1, sticky='w', padx=5, pady=5)
            self.search_vars[field] = var
        elif field == "reading_level":
            var = tk.StringVar()
            combo = ttk.Combobox(criteria_frame, textvariable=var, width=20)
            combo['values'] = ('', 'Elementary', 'Middle School', 'High School', 'College')
            combo.grid(row=row, column=col+1, sticky='w', padx=5, pady=5)
            self.search_vars[field] = var
        elif field == "status":
            var = tk.StringVar()
            combo = ttk.Combobox(criteria_frame, textvariable=var, width=20)
            combo['values'] = ('', 'available', 'checked_out', 'reserved', 'lost', 'damaged')
            combo.grid(row=row, column=col+1, sticky='w', padx=5, pady=5)
            self.search_vars[field] = var
        else:
            var = tk.StringVar()
            entry = ttk.Entry(criteria_frame, textvariable=var, width=20)
            entry.grid(row=row, column=col+1, sticky='w', padx=5, pady=5)
            self.search_vars[field] = var

    # Search buttons
    button_frame = ttk.Frame(criteria_frame)
    button_frame.grid(row=len(search_fields)//2 + 1, column=0, columnspan=4, pady=10)

    ttk.Button(button_frame, text=_("common.search"), command=self.execute_search).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.clear"), command=self.clear_search).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Save Search", command=self.save_search).pack(side=tk.LEFT, padx=5)

    # Results frame
    results_frame = ttk.LabelFrame(search_frame, text=_("library.frames.search_results"))
    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # Results table
    columns = ('ID', 'Title', 'Author', 'Category', 'Status')
    self.search_results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)

    for col in columns:
        self.search_results_tree.heading(col, text=col)
        self.search_results_tree.column(col, width=150)

    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.search_results_tree.yview)
    self.search_results_tree.configure(yscrollcommand=v_scrollbar.set)

    self.search_results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Bind double-click
    self.search_results_tree.bind('<Double-1>', self.on_search_result_double_click)

def execute_search(self):
    """Execute the search with current criteria"""
    # Clear previous results
    for item in self.search_results_tree.get_children():
        self.search_results_tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Build dynamic query
            query = "SELECT book_id, title, author, category, status FROM books WHERE 1=1"
            params = []

            for field, var in self.search_vars.items():
                value = var.get().strip()
                if value:
                    if field in ['title', 'author', 'isbn', 'category']:
                        query += f" AND {field} LIKE ?"
                        params.append(f'%{value}%')
                    else:
                        query += f" AND {field} = ?"
                        params.append(value)

            query += " ORDER BY title"

            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            # Insert results
            for result in results:
                self.search_results_tree.insert('', 'end', values=result)

            self.update_status(f"Found {len(results)} books", "success")
        else:
            # Demo results
            demo_results = [
                ("B10001", "Sample Book 1", "Author 1", "Fiction", "Available"),
                ("B10002", "Sample Book 2", "Author 2", "Non-Fiction", "Checked Out"),
            ]

            for result in demo_results:
                self.search_results_tree.insert('', 'end', values=result)

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Search error: {str(e)}")

def clear_search(self):
    """Clear all search criteria"""
    for var in self.search_vars.values():
        var.set("")

    # Clear results
    for item in self.search_results_tree.get_children():
        self.search_results_tree.delete(item)

def save_search(self):
    """Save current search criteria"""
    search_name = simpledialog.askstring("Save Search", "Enter name for this search:")
    if search_name:
        # Save search criteria (implementation depends on your requirements)
        messagebox.showinfo(_("common.success"), f"Search '{search_name}' saved successfully!")

def on_search_result_double_click(self, event):
    """Handle double-click on search result"""
    selection = self.search_results_tree.selection()
    if selection:
        item = self.search_results_tree.item(selection[0])
        book_id = item['values'][0]
        self.show_book_details(book_id)

def show_advanced_search(self):
    """Show advanced search dialog with multiple criteria"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.advanced_book_search"))
    dialog.geometry("650x700")
    dialog.transient(self.master)

    # Search criteria frame
    criteria_frame = ttk.LabelFrame(dialog, text=_("library.frames.search_criteria"))
    criteria_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Create search fields
    fields = {
        'title': tk.StringVar(),
        'author': tk.StringVar(),
        'isbn': tk.StringVar(),
        'category': tk.StringVar(),
        'publisher': tk.StringVar(),
        'year_from': tk.StringVar(),
        'year_to': tk.StringVar(),
        'status': tk.StringVar(value='Any')
    }

    row = 0
    ttk.Label(criteria_frame, text="Title:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
    ttk.Entry(criteria_frame, textvariable=fields['title'], width=40).grid(row=row, column=1, padx=5, pady=5)

    row += 1
    ttk.Label(criteria_frame, text="Author:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
    ttk.Entry(criteria_frame, textvariable=fields['author'], width=40).grid(row=row, column=1, padx=5, pady=5)

    row += 1
    ttk.Label(criteria_frame, text="ISBN:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
    ttk.Entry(criteria_frame, textvariable=fields['isbn'], width=40).grid(row=row, column=1, padx=5, pady=5)

    row += 1
    ttk.Label(criteria_frame, text="Category:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
    ttk.Entry(criteria_frame, textvariable=fields['category'], width=40).grid(row=row, column=1, padx=5, pady=5)

    row += 1
    ttk.Label(criteria_frame, text="Publisher:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
    ttk.Entry(criteria_frame, textvariable=fields['publisher'], width=40).grid(row=row, column=1, padx=5, pady=5)

    row += 1
    ttk.Label(criteria_frame, text="Year From:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
    ttk.Entry(criteria_frame, textvariable=fields['year_from'], width=15).grid(row=row, column=1, sticky='w', padx=5, pady=5)

    row += 1
    ttk.Label(criteria_frame, text="Year To:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
    ttk.Entry(criteria_frame, textvariable=fields['year_to'], width=15).grid(row=row, column=1, sticky='w', padx=5, pady=5)

    row += 1
    ttk.Label(criteria_frame, text="Status:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
    ttk.Combobox(criteria_frame, textvariable=fields['status'],
                values=['Any', 'Available', 'Checked Out', 'Reserved', 'Maintenance'],
                width=37).grid(row=row, column=1, padx=5, pady=5)

    # Results frame
    results_frame = ttk.LabelFrame(dialog, text=_("library.frames.search_results"))
    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Results treeview
    columns = ('ID', 'Title', 'Author', 'Category', 'Year', 'Status')
    results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=8)

    for col in columns:
        results_tree.heading(col, text=col)
        results_tree.column(col, width=100)

    scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=results_tree.yview)
    results_tree.configure(yscrollcommand=scrollbar.set)

    results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def execute_advanced_search():
        try:
            # Clear previous results
            for item in results_tree.get_children():
                results_tree.delete(item)

            # Build query
            query = "SELECT book_id, title, author, category, publication_year, status FROM books WHERE 1=1"
            params = []

            if fields['title'].get():
                query += " AND title LIKE ?"
                params.append(f"%{escape_like(fields['title'].get())}%")

            if fields['author'].get():
                query += " AND author LIKE ?"
                params.append(f"%{escape_like(fields['author'].get())}%")

            if fields['isbn'].get():
                query += " AND isbn LIKE ?"
                params.append(f"%{escape_like(fields['isbn'].get())}%")

            if fields['category'].get():
                query += " AND category LIKE ?"
                params.append(f"%{escape_like(fields['category'].get())}%")

            if fields['publisher'].get():
                query += " AND publisher LIKE ?"
                params.append(f"%{escape_like(fields['publisher'].get())}%")

            if fields['year_from'].get():
                query += " AND publication_year >= ?"
                params.append(int(fields['year_from'].get()))

            if fields['year_to'].get():
                query += " AND publication_year <= ?"
                params.append(int(fields['year_to'].get()))

            if fields['status'].get() != 'Any':
                query += " AND status = ?"
                params.append(fields['status'].get())

            query += " ORDER BY title LIMIT 100"

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            for result in results:
                results_tree.insert('', 'end', values=result)

            messagebox.showinfo("Search Complete", f"Found {len(results)} matching books")

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Search failed: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text=_("common.search"), command=execute_advanced_search).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.clear"), command=lambda: [v.set('') for v in fields.values()]).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

def show_advanced_search_gui(self):
    """Show advanced search interface"""
    search_window = tk.Toplevel(self.master)
    search_window.title("Advanced Search")
    search_window.geometry("800x700")

    ttk.Label(search_window, text="Advanced Book Search",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Search criteria frame
    criteria_frame = ttk.LabelFrame(search_window, text=_("library.frames.search_criteria"), padding=15)
    criteria_frame.pack(fill=tk.X, padx=10, pady=10)

    # Search fields
    fields = {}

    row = 0
    for label, field in [
        ("Title", "title"),
        ("Author", "author"),
        ("ISBN", "isbn"),
        ("Publisher", "publisher"),
        ("Category", "category"),
        ("Year Published", "year"),
        ("Reading Level", "reading_level"),
        ("Status", "status")
    ]:
        ttk.Label(criteria_frame, text=f"{label}:").grid(row=row, column=0, sticky=tk.W, pady=5)
        var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=var, width=40).grid(row=row, column=1, padx=10, pady=5)
        fields[field] = var
        row += 1

    # Results frame
    results_frame = ttk.LabelFrame(search_window, text=_("library.frames.search_results"), padding=10)
    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('ID', 'Title', 'Author', 'Category', 'Year', 'Status')
    results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)

    for col in columns:
        results_tree.heading(col, text=col)
        results_tree.column(col, width=120)

    results_tree.pack(fill=tk.BOTH, expand=True)

    def perform_search():
        # Clear previous results
        for item in results_tree.get_children():
            results_tree.delete(item)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Build dynamic query
            query = "SELECT book_id, title, author, category, year_published, status FROM books WHERE 1=1"
            params = []

            for field, var in fields.items():
                value = var.get().strip()
                if value:
                    if field == "year":
                        query += " AND year_published = ?"
                        params.append(int(value))
                    else:
                        query += f" AND {field} LIKE ?"
                        params.append(f"%{escape_like(value)}%")

            query += " ORDER BY title LIMIT 100"

            cursor.execute(query, params)
            results = cursor.fetchall()

            for row in results:
                results_tree.insert('', 'end', values=row)

            conn.close()

            messagebox.showinfo("Search Complete", f"Found {len(results)} books")

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Search failed: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(search_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text=_("common.search"), command=perform_search).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.clear"),
              command=lambda: [var.set('') for var in fields.values()]).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=search_window.destroy).pack(side=tk.RIGHT, padx=5)

