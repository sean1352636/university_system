"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.university_system.core.i18n import get_text as _, init_i18n
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
from education_system.university_system.core.exceptions import (
    DatabaseError,
    QueryError,
    ValidationError,
    InvalidInputError,
    FileError,
    UniversityFileNotFoundError
)

# Import secure file upload handler
try:
    from education_system.university_system.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None
    def secure_filename(x):
        return x

# Import activity logger
try:
    from education_system.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

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

from education_system.university_system.core.paths import DEFAULT_DB_PATH
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

from education_system.university_system.modules.domain.academics.gui.library.base import LibraryGUI

def show_digital_library(self):
    """Show digital library interface"""
    if not self.check_permission('manage_books'):
        return

    self.clear_content_area()

    digital_frame = ttk.Frame(self.notebook)
    self.notebook.add(digital_frame, text="Digital Library")

    title_label = ttk.Label(digital_frame, text="Digital Library Management", style='Title.TLabel')
    title_label.pack(pady=10)

    # Control buttons
    control_frame = ttk.Frame(digital_frame)
    control_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(control_frame, text="Add Digital Resource", command=self.add_digital_resource_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text="Manage Access", command=self.manage_digital_access_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text="Download Stats", command=self.show_download_stats).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text=_("common.refresh"), command=self.refresh_digital_library).pack(side=tk.LEFT, padx=5)

    # Digital resources table
    table_frame = ttk.Frame(digital_frame)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    columns = ('ID', 'Title', 'Author', 'Type', 'Access Level', 'Downloads', 'Added Date')
    self.digital_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

    for col in columns:
        self.digital_tree.heading(col, text=col)
        self.digital_tree.column(col, width=100)

    # Add scrollbar
    digital_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.digital_tree.yview)
    self.digital_tree.configure(yscrollcommand=digital_scrollbar.set)

    self.digital_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    digital_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Load digital resources
    self.load_digital_resources()

    # Bind double-click
    self.digital_tree.bind('<Double-1>', self.view_digital_resource)

def load_digital_resources(self):
    """Load digital resources data"""
    # Clear existing data
    for item in self.digital_tree.get_children():
        self.digital_tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
            SELECT digital_id, title, author, file_type, access_level,
                   download_count, added_date
            FROM digital_library
            ORDER BY title
            ''')

            resources = cursor.fetchall()
            conn.close()

            for resource in resources:
                digital_id, title, author, file_type, access_level, downloads, added_date = resource
                self.digital_tree.insert('', 'end', values=(
                    digital_id, title[:30], author[:20], file_type,
                    access_level, downloads, added_date[:10]
                ))
        else:
            # Demo data
            demo_resources = [
                (1, "Digital Guide to Python", "Author Name", "PDF", "public", 45, "2024-01-15"),
                (2, "Library Science eBook", "Jane Smith", "EPUB", "students", 23, "2024-01-10"),
            ]

            for resource in demo_resources:
                self.digital_tree.insert('', 'end', values=resource)

    except (OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Error loading digital resources: {str(e)}")

def refresh_digital_library(self):
    """Refresh digital library"""
    self.load_digital_resources()

def add_digital_resource_dialog(self):
    """Add digital resource dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.add_digital_resource"))
    dialog.geometry("500x400")
    dialog.transient(self.master)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # File selection
    file_frame = ttk.LabelFrame(main_frame, text="File Selection")
    file_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(file_frame, text="Select File:").pack(anchor='w', padx=5, pady=5)
    self.digital_file_path = tk.StringVar()
    file_path_frame = ttk.Frame(file_frame)
    file_path_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Entry(file_path_frame, textvariable=self.digital_file_path, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
    ttk.Button(file_path_frame, text="Browse", command=self.browse_digital_file).pack(side=tk.RIGHT, padx=(5, 0))

    # Metadata
    metadata_frame = ttk.LabelFrame(main_frame, text="Metadata")
    metadata_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Form fields
    fields = [
        ("Title:", "title"),
        ("Author:", "author"),
        ("Category:", "category"),
        ("Description:", "description"),
    ]

    self.digital_metadata_vars = {}

    for i, (label, field) in enumerate(fields):
        ttk.Label(metadata_frame, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=5)

        if field == "description":
            var = None  # Text widget
            self.digital_description = tk.Text(metadata_frame, height=3, width=40)
            self.digital_description.grid(row=i, column=1, sticky='w', padx=5, pady=5)
        else:
            var = tk.StringVar()
            entry = ttk.Entry(metadata_frame, textvariable=var, width=40)
            entry.grid(row=i, column=1, sticky='w', padx=5, pady=5)
            self.digital_metadata_vars[field] = var

    # Access level
    ttk.Label(metadata_frame, text="Access Level:").grid(row=len(fields), column=0, sticky='w', padx=5, pady=5)
    self.digital_access_var = tk.StringVar(value="public")
    access_combo = ttk.Combobox(metadata_frame, textvariable=self.digital_access_var, width=37)
    access_combo['values'] = ('public', 'students', 'staff', 'restricted')
    access_combo.grid(row=len(fields), column=1, sticky='w', padx=5, pady=5)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)

    ttk.Button(button_frame, text="Add Resource", command=lambda: self.save_digital_resource(dialog)).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

def browse_digital_file(self):
    """Browse for digital file"""
    file_path = filedialog.askopenfilename(
        title="Select Digital Resource",
        filetypes=[
            ("PDF files", "*.pdf"),
            ("eBook files", "*.epub *.mobi"),
            ("Document files", "*.doc *.docx"),
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ]
    )

    if file_path:
        self.digital_file_path.set(file_path)

        # Auto-fill title from filename
        filename = os.path.basename(file_path)
        title = os.path.splitext(filename)[0]
        if 'title' in self.digital_metadata_vars:
            self.digital_metadata_vars['title'].set(title)

def save_digital_resource(self, dialog):
    """Save digital resource"""
    file_path = self.digital_file_path.get().strip()

    if not file_path or not os.path.exists(file_path):
        messagebox.showerror(_("common.error"), "Please select a valid file")
        return

    # Get metadata
    title = self.digital_metadata_vars['title'].get().strip()
    author = self.digital_metadata_vars['author'].get().strip()
    category = self.digital_metadata_vars['category'].get().strip()
    description = self.digital_description.get("1.0", tk.END).strip()
    access_level = self.digital_access_var.get()

    if not title or not author:
        messagebox.showerror(_("common.error"), "Title and Author are required")
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            success = self.add_digital_resource_database(file_path, title, author, category, description, access_level)
            if success:
                messagebox.showinfo(_("common.success"), "Digital resource added successfully!")
                dialog.destroy()
                self.refresh_digital_library()
            else:
                messagebox.showerror(_("common.error"), "Failed to add digital resource")
        else:
            messagebox.showinfo(_("common.demo"), f"Digital resource '{title}' would be added")
            dialog.destroy()

    except (OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Error adding digital resource: {str(e)}")

def add_digital_resource_database(self, file_path, title, author, category, description, access_level):
    """Add digital resource to database"""
    try:
        import shutil

        original_filename = os.path.basename(file_path)

        # Security: Validate file before upload
        if SECURE_UPLOAD_AVAILABLE and validate_upload:
            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                validation = validate_upload(original_filename, file_content, category='documents')
                if not validation['valid']:
                    messagebox.showerror(
                        _("common.error"),
                        f"File validation failed: {validation['error']}"
                    )
                    if ACTIVITY_LOGGER_AVAILABLE:
                        log_activity(
                            'security_blocked',
                            'digital_library_upload',
                            filename=original_filename,
                            reason=validation['error']
                        )
                    return False
                safe_filename = validation.get('sanitized_filename', secure_filename(original_filename))
            except Exception as e:
                logging.error(f"File validation error: {e}")
                return False
        else:
            safe_filename = secure_filename(original_filename)

        # Copy file to digital library directory
        digital_dir = "digital_library"
        os.makedirs(digital_dir, exist_ok=True)
        # Set restrictive permissions on directory
        os.chmod(digital_dir, 0o700)

        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_filename}"
        new_path = os.path.join(digital_dir, filename)
        shutil.copy2(file_path, new_path)
        # Set restrictive permissions on file
        os.chmod(new_path, 0o600)

        # Get file info
        file_type = os.path.splitext(file_path)[1][1:].upper()
        file_size = os.path.getsize(file_path)

        # Insert into database
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO digital_library
        (title, author, file_path, file_type, file_size, category,
         description, access_level, added_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            title, author, new_path, file_type, file_size, category,
            description, access_level, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        conn.commit()
        conn.close()

        # Log the action
        log_audit_event(get_current_user_id(), f"GUI: Added digital resource '{title}'", "digital_library")

        return True

    except (OSError, IOError) as e:
        print(f"Error adding digital resource: {e}")
        return False

def show_digital_library_gui(self):
    """Show digital library management interface"""
    digital_window = tk.Toplevel(self.master)
    digital_window.title("Digital Library")
    digital_window.geometry("1000x700")

    ttk.Label(digital_window, text="Digital Library Management",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Button frame
    button_frame = ttk.Frame(digital_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Upload Digital Resource",
              command=self.upload_digital_resource).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.refresh"),
              command=lambda: self.load_digital_library(tree)).pack(side=tk.LEFT, padx=5)

    # Digital library table
    frame = ttk.Frame(digital_window)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('ID', 'Title', 'Author', 'Type', 'Category', 'Downloads', 'Date Added')
    tree = ttk.Treeview(frame, columns=columns, show='headings', height=20)

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120)

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
    h_scrollbar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    tree.grid(row=0, column=0, sticky='nsew')
    v_scrollbar.grid(row=0, column=1, sticky='ns')
    h_scrollbar.grid(row=1, column=0, sticky='ew')

    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    # Double-click to download
    tree.bind('<Double-Button-1>', lambda e: self.download_digital_resource_gui(tree))

    # Load digital library
    self.load_digital_library(tree)

def load_digital_library(self, tree):
    """Load digital library items into tree"""
    try:
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT digital_id, title, author, file_type, category, download_count, added_date
        FROM digital_library
        ORDER BY added_date DESC
        ''')

        for row in cursor.fetchall():
            tree.insert('', 'end', values=row)

        conn.close()

    except (sqlite3.Error, DatabaseError, OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Failed to load digital library: {str(e)}")

def upload_digital_resource(self):
    """Upload a digital resource"""
    file_path = filedialog.askopenfilename(
        title="Select Digital Resource",
        filetypes=[
            ("PDF files", "*.pdf"),
            ("EPUB files", "*.epub"),
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ]
    )

    if not file_path:
        return

    # Get metadata dialog
    metadata_dialog = tk.Toplevel(self.master)
    metadata_dialog.title("Resource Metadata")
    metadata_dialog.geometry("400x300")

    ttk.Label(metadata_dialog, text="Enter Resource Details",
             font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)

    ttk.Label(metadata_dialog, text="Title:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
    title_var = tk.StringVar(value=os.path.basename(file_path))
    ttk.Entry(metadata_dialog, textvariable=title_var, width=30).grid(row=1, column=1, padx=10, pady=5)

    ttk.Label(metadata_dialog, text="Author:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
    author_var = tk.StringVar()
    ttk.Entry(metadata_dialog, textvariable=author_var, width=30).grid(row=2, column=1, padx=10, pady=5)

    ttk.Label(metadata_dialog, text="Category:").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
    category_var = tk.StringVar(value="General")
    ttk.Entry(metadata_dialog, textvariable=category_var, width=30).grid(row=3, column=1, padx=10, pady=5)

    ttk.Label(metadata_dialog, text="Description:").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
    desc_text = tk.Text(metadata_dialog, width=30, height=4)
    desc_text.grid(row=4, column=1, padx=10, pady=5)

    def save_resource():
        try:
            import shutil

            title = title_var.get().strip()
            author = author_var.get().strip()
            category = category_var.get().strip()
            description = desc_text.get('1.0', tk.END).strip()

            if not title or not author:
                messagebox.showerror(_("common.error"), "Title and Author are required")
                return

            original_filename = os.path.basename(file_path)

            # Security: Validate file before upload
            if SECURE_UPLOAD_AVAILABLE and validate_upload:
                try:
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    validation = validate_upload(original_filename, file_content, category='documents')
                    if not validation['valid']:
                        messagebox.showerror(
                            _("common.error"),
                            f"File validation failed: {validation['error']}"
                        )
                        if ACTIVITY_LOGGER_AVAILABLE:
                            log_activity(
                                'security_blocked',
                                'digital_resource_upload',
                                filename=original_filename,
                                reason=validation['error']
                            )
                        return
                    safe_filename = validation.get('sanitized_filename', secure_filename(original_filename))
                except Exception as e:
                    messagebox.showerror(_("common.error"), f"Validation error: {str(e)}")
                    return
            else:
                safe_filename = secure_filename(original_filename)

            # Copy file to digital library folder
            from education_system.university_system.core.paths import UPLOAD_DIR
            digital_dir = UPLOAD_DIR / "digital_library"
            digital_dir.mkdir(parents=True, exist_ok=True)
            # Set restrictive permissions on directory
            os.chmod(digital_dir, 0o700)

            dest_path = digital_dir / safe_filename
            shutil.copy2(file_path, dest_path)
            # Set restrictive permissions on file
            os.chmod(dest_path, 0o600)

            # Get file info
            file_type = os.path.splitext(safe_filename)[1].lstrip('.')
            file_size = os.path.getsize(dest_path)

            # Save to database
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO digital_library (
                title, author, file_path, file_type, file_size, category,
                description, access_level, download_count, added_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title, author, str(dest_path), file_type, file_size, category,
                description, 'public', 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

            conn.commit()
            conn.close()

            log_audit_event(get_current_user_id(), f"Uploaded digital resource: {title}", "digital_library")

            metadata_dialog.destroy()
            messagebox.showinfo(_("common.success"), "Digital resource uploaded successfully!")

        except (OSError, IOError, tk.TclError, ValueError, TypeError) as e:
            messagebox.showerror(_("common.error"), f"Upload failed: {str(e)}")

    ttk.Button(metadata_dialog, text=_("common.save"), command=save_resource).grid(row=5, column=0, columnspan=2, pady=20)

def download_digital_resource_gui(self, tree):
    """Download selected digital resource"""
    selection = tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a resource to download")
        return

    item = tree.item(selection[0])
    digital_id = item['values'][0]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT file_path, title FROM digital_library WHERE digital_id = ?', (digital_id,))
        result = cursor.fetchone()

        if not result:
            messagebox.showerror(_("common.error"), "Resource not found")
            return

        file_path, title = result

        # Ask where to save
        save_path = filedialog.asksaveasfilename(
            initialfile=os.path.basename(file_path),
            defaultextension=os.path.splitext(file_path)[1]
        )

        if save_path:
            import shutil
            shutil.copy2(file_path, save_path)

            # Update download count
            cursor.execute('''
            UPDATE digital_library
            SET download_count = download_count + 1
            WHERE digital_id = ?
            ''', (digital_id,))
            conn.commit()

            messagebox.showinfo(_("common.success"), f"Downloaded to:\n{save_path}")

        conn.close()

    except (sqlite3.Error, DatabaseError, OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Download failed: {str(e)}")

def manage_digital_access_permissions_gui(self):
    """Manage digital resource access permissions"""
    perms_window = tk.Toplevel(self.master)
    perms_window.title("Digital Access Permissions")
    perms_window.geometry("900x600")

    ttk.Label(perms_window, text="Digital Resource Access Permissions",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Filter frame
    filter_frame = ttk.LabelFrame(perms_window, text="Filter", padding=10)
    filter_frame.pack(fill=tk.X, padx=10, pady=10)

    resource_filter = tk.StringVar()
    ttk.Label(filter_frame, text="Resource ID:").pack(side=tk.LEFT, padx=5)
    ttk.Entry(filter_frame, textvariable=resource_filter, width=20).pack(side=tk.LEFT, padx=5)

    # Permissions table
    table_frame = ttk.Frame(perms_window)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('Permission ID', 'Resource', 'User/Role', 'Access Level', 'Granted', 'Expires')
    perms_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

    for col in columns:
        perms_tree.heading(col, text=col)
        perms_tree.column(col, width=140)

    scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=perms_tree.yview)
    perms_tree.configure(yscrollcommand=scrollbar.set)

    perms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def load_permissions():
        for item in perms_tree.get_children():
            perms_tree.delete(item)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            res_filter = resource_filter.get().strip()
            if res_filter:
                query = '''
                SELECT p.permission_id, d.title, p.user_id, p.access_level,
                       p.granted_date, p.expiry_date
                FROM digital_access_permissions p
                JOIN digital_library d ON p.digital_id = d.digital_id
                WHERE d.digital_id = ? OR d.title LIKE ?
                ORDER BY p.granted_date DESC
                '''
                cursor.execute(query, (res_filter, f'%{res_filter}%'))
            else:
                query = '''
                SELECT p.permission_id, d.title, p.user_id, p.access_level,
                       p.granted_date, p.expiry_date
                FROM digital_access_permissions p
                JOIN digital_library d ON p.digital_id = d.digital_id
                ORDER BY p.granted_date DESC
                LIMIT 100
                '''
                cursor.execute(query)

            for row in cursor.fetchall():
                perms_tree.insert('', 'end', values=(
                    row[0], row[1][:30], row[2], row[3], row[4][:10], row[5][:10] if row[5] else 'Never'
                ))

            conn.close()

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to load permissions: {str(e)}")

    ttk.Button(filter_frame, text=_("common.search"), command=load_permissions).pack(side=tk.LEFT, padx=5)
    ttk.Button(filter_frame, text=_("common.clear"), command=lambda: resource_filter.set('')).pack(side=tk.LEFT, padx=5)

    def grant_permission():
        # Permission dialog
        grant_dialog = tk.Toplevel(perms_window)
        grant_dialog.title("Grant Permission")
        grant_dialog.geometry("400x300")

        ttk.Label(grant_dialog, text="Grant Digital Access",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(grant_dialog, padding=15)
        form_frame.pack(fill=tk.BOTH, expand=True)

        digital_id_var = tk.StringVar()
        user_id_var = tk.StringVar()
        access_level_var = tk.StringVar(value="read")
        days_valid_var = tk.IntVar(value=30)

        ttk.Label(form_frame, text="Digital Resource ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=digital_id_var, width=25).grid(row=0, column=1, pady=5)

        ttk.Label(form_frame, text="User ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=user_id_var, width=25).grid(row=1, column=1, pady=5)

        ttk.Label(form_frame, text="Access Level:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Combobox(form_frame, textvariable=access_level_var,
                    values=["read", "download", "full"], width=22).grid(row=2, column=1, pady=5)

        ttk.Label(form_frame, text="Valid for (days):").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=days_valid_var, width=25).grid(row=3, column=1, pady=5)

        def save_permission():
            digital_id = digital_id_var.get().strip()
            user_id = user_id_var.get().strip()

            if not digital_id or not user_id:
                messagebox.showerror(_("common.error"), "Please provide both Resource ID and User ID")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                granted_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                expiry_date = (datetime.now() + timedelta(days=days_valid_var.get())).strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO digital_access_permissions (
                    digital_id, user_id, access_level, granted_date, expiry_date, granted_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (digital_id, user_id, access_level_var.get(), granted_date, expiry_date, get_current_user_id()))

                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(),
                              f"Granted {access_level_var.get()} access to digital resource {digital_id} for {user_id}",
                              "digital_access_permissions")

                messagebox.showinfo(_("common.success"), "Permission granted successfully!")
                grant_dialog.destroy()
                load_permissions()

            except tk.TclError as e:
                messagebox.showerror(_("common.error"), f"Failed to grant permission: {str(e)}")

        ttk.Button(form_frame, text="Grant", command=save_permission).grid(row=4, column=0, columnspan=2, pady=20)

    def revoke_permission():
        selection = perms_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), "Please select a permission to revoke")
            return

        item = perms_tree.item(selection[0])
        perm_id = item['values'][0]

        if messagebox.askyesno("Confirm", "Revoke this permission?"):
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM digital_access_permissions WHERE permission_id = ?', (perm_id,))
                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), f"Revoked permission {perm_id}", "digital_access_permissions")
                messagebox.showinfo(_("common.success"), "Permission revoked")
                load_permissions()

            except (sqlite3.Error, DatabaseError, tk.TclError) as e:
                messagebox.showerror(_("common.error"), f"Failed to revoke: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(perms_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Grant Permission", command=grant_permission).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Revoke Selected", command=revoke_permission).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.refresh"), command=load_permissions).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=perms_window.destroy).pack(side=tk.RIGHT, padx=5)

    # Load initial data
    load_permissions()

