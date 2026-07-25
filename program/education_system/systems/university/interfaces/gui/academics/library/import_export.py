"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n
init_i18n()
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import sys
from datetime import datetime, timedelta
import json
from education_system.systems.university.infrastructure.database.db import sqlite3
from typing import Dict, List, Optional, Any
import logging
import urllib.request
import urllib.parse
import urllib.error

# Import custom exceptions for better error handling
from education_system.systems.university.infrastructure.exceptions import (
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
    from education_system.systems.university.domain.academics.services.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from education_system.systems.university.domain.academics.services.library.menu import display_library_menu
    from education_system.systems.university.domain.academics.services.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from education_system.systems.university.domain.academics.services.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from education_system.systems.university.domain.academics.services.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from education_system.systems.university.domain.academics.services.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from education_system.systems.university.domain.academics.services.library.reading_lists import view_reading_list_details
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

# Import shared authentication system
try:
    from education_system.systems.university.infrastructure.auth import UserAuth
    from education_system.systems.university.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None

from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
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
    from education_system.systems.university.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_email_as_system(*args, **kwargs):
        return False
    print("Warning: Email service not available for library finance")

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None
_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

from education_system.systems.university.interfaces.gui.academics.library.base import LibraryGUI

def import_books_gui(self):
    """Import books from CSV or Excel file"""
    try:
        file_path = filedialog.askopenfilename(
            title="Select Book File to Import",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        # Ask user about column mapping
        dialog = tk.Toplevel(self.master)
        dialog.title("Import Books")
        dialog.geometry("600x400")
        dialog.transient(self.master)

        ttk.Label(dialog, text="Importing books from:", font=('Arial', 10, 'bold')).pack(pady=5)
        ttk.Label(dialog, text=os.path.basename(file_path)).pack(pady=5)

        # Read file preview
        import csv
        try:
            if file_path.endswith('.csv'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    headers = next(reader)
                    preview_rows = [next(reader) for _ in range(min(3, sum(1 for _ in reader)))]
            else:
                # For Excel, would need openpyxl - fallback to CSV-like approach
                messagebox.showwarning("Format", "Excel import requires openpyxl. Please convert to CSV.")
                dialog.destroy()
                return

            # Show column mapping
            frame = ttk.LabelFrame(dialog, text="Column Mapping")
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            mappings = {}
            required_fields = ['title', 'author', 'isbn', 'category', 'quantity']

            for i, field in enumerate(required_fields):
                ttk.Label(frame, text=f"{field.title()}:").grid(row=i, column=0, sticky='w', padx=5, pady=3)
                var = tk.StringVar(value=headers[i] if i < len(headers) else '')
                combo = ttk.Combobox(frame, textvariable=var, values=headers, width=30)
                combo.grid(row=i, column=1, padx=5, pady=3)
                mappings[field] = var

            # Import button
            def do_import():
                try:
                    imported_count = 0
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    with open(file_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            try:
                                book_data = {
                                    'title': row.get(mappings['title'].get(), ''),
                                    'author': row.get(mappings['author'].get(), ''),
                                    'isbn': row.get(mappings['isbn'].get(), ''),
                                    'category': row.get(mappings['category'].get(), ''),
                                    'quantity': int(row.get(mappings['quantity'].get(), 1))
                                }

                                # Generate book_id
                                cursor.execute('SELECT MAX(CAST(SUBSTR(book_id, 2) AS INTEGER)) FROM books')
                                result = cursor.fetchone()
                                next_num = (result[0] or 10000) + 1
                                book_id = f"B{next_num}"

                                cursor.execute('''
                                    INSERT INTO books (book_id, title, author, isbn, category,
                                                     quantity, available_quantity, status, location)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Available', 'Imported')
                                ''', (book_id, book_data['title'], book_data['author'],
                                     book_data['isbn'], book_data['category'],
                                     book_data['quantity'], book_data['quantity']))

                                imported_count += 1
                            except (sqlite3.Error, DatabaseError) as e:
                                print(f"Error importing row: {e}")
                                continue

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_("common.success"), f"Successfully imported {imported_count} books!")
                    dialog.destroy()
                    if hasattr(self, 'books_tree'):
                        self.load_books_data()

                except (tk.TclError, ValueError, TypeError) as e:
                    messagebox.showerror(_("common.error"), f"Import failed: {str(e)}")

            ttk.Button(dialog, text=_("common.import"), command=do_import).pack(pady=10)
            ttk.Button(dialog, text=_("common.cancel"), command=dialog.destroy).pack(pady=5)

        except (tk.TclError, ValueError, TypeError) as e:
            messagebox.showerror(_("common.error"), f"Could not read file: {str(e)}")
            dialog.destroy()

    except (OSError, IOError, tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Import failed: {str(e)}")

def export_books_gui(self):
    """Export books to CSV file"""
    try:
        file_path = filedialog.asksaveasfilename(
            title="Export Books",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        import csv
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT book_id, title, author, isbn, category, publisher,
                   publication_year, quantity, available_quantity, status, location
            FROM books
            ORDER BY title
        ''')

        books = cursor.fetchall()
        conn.close()

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Book ID', 'Title', 'Author', 'ISBN', 'Category',
                           'Publisher', 'Year', 'Quantity', 'Available', 'Status', 'Location'])
            writer.writerows(books)

        messagebox.showinfo(_("common.success"), f"Exported {len(books)} books to {os.path.basename(file_path)}")

    except (sqlite3.Error, DatabaseError, OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Export failed: {str(e)}")

def backup_system_gui(self):
    """Create database backup"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"library_backup_{timestamp}.db"

        file_path = filedialog.asksaveasfilename(
            title="Save Backup",
            defaultextension=".db",
            initialfile=default_name,
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )

        if not file_path:
            return

        import shutil
        shutil.copy2(DATABASE_FILE, file_path)

        # Log the backup
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            user_id = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'system'
            cursor.execute('''
                INSERT INTO audit_log (user_id, action, table_name, timestamp, success)
                VALUES (?, 'backup', 'system', ?, 1)
            ''', (user_id, datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except (sqlite3.Error, DatabaseError, OSError, IOError):
            pass

        messagebox.showinfo(_("common.success"), f"Backup created successfully!\n{os.path.basename(file_path)}")
        self.update_status("Backup created successfully", "success")

    except (sqlite3.Error, DatabaseError, OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Backup failed: {str(e)}")

def restore_system_gui(self):
    """Restore system via GUI"""
    if not self.check_permission('system_config'):
        return

    backup_dir = filedialog.askdirectory(title="Select Backup Directory")

    if backup_dir:
        # Confirm restore operation
        result = messagebox.askyesno("Confirm Restore",
                                   "This will overwrite current data. Are you sure you want to restore from backup?")

        if result:
            try:
                if ORIGINAL_LIBRARY_AVAILABLE:
                    success = self.restore_from_backup(backup_dir)
                    if success:
                        messagebox.showinfo(_("common.success"), "System restored successfully!")
                        # Restart application to reload data
                        restart = messagebox.askyesno("Restart Required",
                                                    "Application needs to restart to complete restore. Restart now?")
                        if restart:
                            self.exit_application(restart=True)
                    else:
                        messagebox.showerror(_("common.error"), "Restore failed")
                else:
                    messagebox.showinfo(_("common.demo"), f"Would restore from {backup_dir}")
            except tk.TclError as e:
                messagebox.showerror(_("common.error"), f"Restore error: {str(e)}")

def restore_from_backup(self, backup_dir):
    """Restore from backup directory"""
    try:
        import shutil

        # Check for manifest
        manifest_path = os.path.join(backup_dir, 'manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            print(f"Restoring backup from {manifest.get('backup_date', 'unknown date')}")

        # Create safety backup first
        safety_backup_dir = f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(safety_backup_dir, exist_ok=True)

        # Use DATABASE_FILE constant instead of self.DATABASE_FILE
        if os.path.exists(DATABASE_FILE):
            shutil.copy2(DATABASE_FILE, safety_backup_dir)

        # Restore database
        backup_db_path = os.path.join(backup_dir, 'library_database.db')
        if os.path.exists(backup_db_path):
            shutil.copy2(backup_db_path, DATABASE_FILE)

        # Restore additional directories
        restore_dirs = ['qr_codes', 'digital_library', 'cover_images']
        for dir_name in restore_dirs:
            backup_subdir = os.path.join(backup_dir, dir_name)
            if os.path.exists(backup_subdir):
                if os.path.exists(dir_name):
                    shutil.rmtree(dir_name)
                shutil.copytree(backup_subdir, dir_name)

        # Log the action
        if ORIGINAL_LIBRARY_AVAILABLE:
            log_audit_event(get_current_user_id(), f"GUI: Restored system from {backup_dir}", "system")

        return True

    except (OSError, IOError, sqlite3.Error) as e:
        print(f"Restore error: {e}")
        return False

def bulk_import_books_gui(self):
    """Bulk import books from CSV/Excel with GUI"""
    file_path = filedialog.askopenfilename(
        title="Select Books File",
        filetypes=[
            ("CSV files", "*.csv"),
            ("Excel files", "*.xlsx;*.xls"),
            ("All files", "*.*")
        ]
    )

    if not file_path:
        return

    try:
        import pandas as pd

        # Read file based on extension
        if file_path.lower().endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            messagebox.showerror(_("common.error"), "Unsupported file format. Use CSV or Excel files.")
            return

        # Validate required columns
        required_columns = ['title', 'author']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            messagebox.showerror(
                "Error",
                f"Missing required columns: {', '.join(missing_columns)}\n\n" +
                "Required: title, author\n" +
                "Optional: isbn, publisher, category, year_published, description, location, reading_level, tags"
            )
            return

        # Show preview dialog
        preview_dialog = tk.Toplevel(self.master)
        preview_dialog.title("Import Preview")
        preview_dialog.geometry("900x600")

        ttk.Label(preview_dialog, text=f"Found {len(df)} books to import",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Preview table
        frame = ttk.Frame(preview_dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tree = ttk.Treeview(frame, show='headings', height=15)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

        # Setup columns
        display_columns = ['title', 'author', 'isbn', 'category', 'year_published']
        tree['columns'] = [col for col in display_columns if col in df.columns]

        for col in tree['columns']:
            tree.heading(col, text=col.replace('_', ' ').title())
            tree.column(col, width=150)

        # Add preview data (first 20 rows)
        for idx, row in df.head(20).iterrows():
            values = [row.get(col, '') for col in tree['columns']]
            tree.insert('', 'end', values=values)

        # Button frame
        button_frame = ttk.Frame(preview_dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def do_import():
            preview_dialog.destroy()
            self._perform_import(df)

        ttk.Button(button_frame, text="Import All", command=do_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("common.cancel"), command=preview_dialog.destroy).pack(side=tk.LEFT, padx=5)

    except ImportError:
        messagebox.showerror(_("common.error"), "pandas library is required for bulk import.\nInstall it with: pip install pandas openpyxl")
    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to read file: {str(e)}")

def _perform_import(self, df):
    """Perform the actual import operation"""
    try:
        import pandas as pd
        import json
        from education_system.systems.university.domain.academics.services.library.barcode import generate_barcode, generate_qr_code

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get next book ID
        cursor.execute('SELECT MAX(CAST(SUBSTR(book_id, 2) AS INTEGER)) FROM books')
        result = cursor.fetchone()[0]
        next_id = 10001 if result is None else result + 1

        imported_count = 0
        error_count = 0
        errors = []

        # Progress dialog
        progress_dialog = tk.Toplevel(self.master)
        progress_dialog.title("Importing Books")
        progress_dialog.geometry("400x150")

        ttk.Label(progress_dialog, text="Importing books...").pack(pady=10)
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=len(df))
        progress_bar.pack(fill=tk.X, padx=20, pady=10)

        status_label = ttk.Label(progress_dialog, text="")
        status_label.pack(pady=5)

        for index, row in df.iterrows():
            try:
                book_id = f"B{next_id + imported_count}"

                # Extract data
                title = str(row['title']).strip()
                author = str(row['author']).strip()
                isbn = str(row.get('isbn', '')).strip() if pd.notna(row.get('isbn')) else None
                publisher = str(row.get('publisher', '')).strip() if pd.notna(row.get('publisher')) else None
                category = str(row.get('category', 'General')).strip()
                year_published = int(row['year_published']) if pd.notna(row.get('year_published')) else None
                description = str(row.get('description', '')).strip() if pd.notna(row.get('description')) else None
                location = str(row.get('location', '')).strip() if pd.notna(row.get('location')) else None
                reading_level = str(row.get('reading_level', 'Unknown')).strip()
                tags_str = str(row.get('tags', '')).strip() if pd.notna(row.get('tags')) else ''
                tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else []

                # Generate barcode and QR code
                barcode = generate_barcode(book_id)
                qr_code_path = generate_qr_code(book_id, title)
                qr_code_str = str(qr_code_path) if qr_code_path else None

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Insert book
                cursor.execute('''
                INSERT INTO books (
                    book_id, title, author, isbn, publisher, category, year_published,
                    description, location, status, added_date, last_updated,
                    reading_level, tags, cover_image_path, digital_copy_path, acquisition_cost,
                    barcode, qr_code_path, total_pages, language, edition, condition_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    book_id, title, author, isbn, publisher, category,
                    year_published, description, location, 'available', now, now,
                    reading_level, json.dumps(tags), None, None, 0.0,
                    barcode, qr_code_str, None, 'English', None, None
                ))

                imported_count += 1
                progress_var.set(index + 1)
                status_label.config(text=f"Imported: {imported_count} | Errors: {error_count}")
                progress_dialog.update()

            except (json.JSONDecodeError, tk.TclError) as e:
                error_count += 1
                errors.append(f"Row {index + 1} ({row.get('title', 'Unknown')}): {str(e)}")

        conn.commit()
        conn.close()
        progress_dialog.destroy()

        # Log the action
        log_audit_event(get_current_user_id(), f"Bulk imported {imported_count} books", "books")

        # Show results
        result_msg = f"Import Complete!\n\nSuccessfully imported: {imported_count} books"
        if error_count > 0:
            result_msg += f"\nErrors: {error_count}\n\nFirst few errors:\n"
            result_msg += "\n".join(errors[:5])

        messagebox.showinfo("Import Complete", result_msg)

        # Refresh the books display
        if hasattr(self, 'show_all_books'):
            self.show_all_books()

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Import failed: {str(e)}")

def bulk_export_books_gui(self):
    """Bulk export books to CSV/Excel with GUI"""
    # Export options dialog
    export_dialog = tk.Toplevel(self.master)
    export_dialog.title(_("library.dialogs.export_books"))
    export_dialog.geometry("400x350")

    ttk.Label(export_dialog, text="Export Books to CSV/Excel",
             font=('Arial', 14, 'bold')).pack(pady=15)

    export_type = tk.StringVar(value="all")

    ttk.Radiobutton(export_dialog, text="Export All Books",
                   variable=export_type, value="all").pack(anchor=tk.W, padx=30, pady=5)
    ttk.Radiobutton(export_dialog, text="Export by Category",
                   variable=export_type, value="category").pack(anchor=tk.W, padx=30, pady=5)
    ttk.Radiobutton(export_dialog, text="Export by Status",
                   variable=export_type, value="status").pack(anchor=tk.W, padx=30, pady=5)
    ttk.Radiobutton(export_dialog, text="Export by Date Range",
                   variable=export_type, value="date").pack(anchor=tk.W, padx=30, pady=5)

    # Additional options frame
    options_frame = ttk.LabelFrame(export_dialog, text="Options", padding=10)
    options_frame.pack(fill=tk.X, padx=20, pady=10)

    category_var = tk.StringVar()
    status_var = tk.StringVar(value="available")
    start_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
    end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))

    # Category selection
    ttk.Label(options_frame, text="Category:").grid(row=0, column=0, sticky=tk.W, pady=2)
    category_combo = ttk.Combobox(options_frame, textvariable=category_var, width=20)
    category_combo.grid(row=0, column=1, pady=2)

    # Status selection
    ttk.Label(options_frame, text="Status:").grid(row=1, column=0, sticky=tk.W, pady=2)
    status_combo = ttk.Combobox(options_frame, textvariable=status_var,
                                values=["available", "checked_out", "reserved", "lost", "damaged"], width=20)
    status_combo.grid(row=1, column=1, pady=2)

    # Date range
    ttk.Label(options_frame, text="Start Date:").grid(row=2, column=0, sticky=tk.W, pady=2)
    ttk.Entry(options_frame, textvariable=start_date_var, width=22).grid(row=2, column=1, pady=2)

    ttk.Label(options_frame, text="End Date:").grid(row=3, column=0, sticky=tk.W, pady=2)
    ttk.Entry(options_frame, textvariable=end_date_var, width=22).grid(row=3, column=1, pady=2)

    # Load categories
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT category FROM books ORDER BY category')
        categories = [row[0] for row in cursor.fetchall()]
        category_combo['values'] = categories
        if categories:
            category_var.set(categories[0])
        conn.close()
    except (sqlite3.Error, DatabaseError, tk.TclError):
        pass

    def do_export():
        export_dialog.destroy()
        self._perform_export(export_type.get(), category_var.get(),
                           status_var.get(), start_date_var.get(), end_date_var.get())

    ttk.Button(export_dialog, text=_("common.export"), command=do_export).pack(pady=10)

def _perform_export(self, export_type, category, status, start_date, end_date):
    """Perform the actual export operation"""
    try:
        import pandas as pd

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query based on export type
        base_query = '''
        SELECT book_id, title, author, isbn, publisher, category, year_published,
               description, location, status, reading_level, tags, barcode,
               acquisition_cost, total_pages, language, edition, added_date
        FROM books
        '''

        if export_type == "all":
            cursor.execute(base_query + " ORDER BY title")
        elif export_type == "category":
            cursor.execute(base_query + " WHERE category = ? ORDER BY title", (category,))
        elif export_type == "status":
            cursor.execute(base_query + " WHERE status = ? ORDER BY title", (status,))
        elif export_type == "date":
            cursor.execute(base_query + " WHERE added_date BETWEEN ? AND ? ORDER BY title",
                         (start_date, end_date))

        # Fetch data
        columns = [desc[0] for desc in cursor.description]
        data = cursor.fetchall()
        conn.close()

        if not data:
            messagebox.showinfo("No Data", "No books found matching the criteria.")
            return

        # Create DataFrame
        df = pd.DataFrame(data, columns=columns)

        # Ask for save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            # Save based on extension
            if file_path.lower().endswith('.csv'):
                df.to_csv(file_path, index=False)
            elif file_path.lower().endswith('.xlsx'):
                df.to_excel(file_path, index=False, engine='openpyxl')

            log_audit_event(get_current_user_id(), f"Exported {len(data)} books", "books")
            messagebox.showinfo(_("common.success"), f"Exported {len(data)} books to:\n{file_path}")

    except ImportError:
        messagebox.showerror(_("common.error"), "pandas and openpyxl libraries are required for export.\nInstall them with: pip install pandas openpyxl")
    except (OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Export failed: {str(e)}")

def system_backup_gui(self):
    """System backup and recovery interface"""
    backup_window = tk.Toplevel(self.master)
    backup_window.title("System Backup & Recovery")
    backup_window.geometry("700x600")

    ttk.Label(backup_window, text="System Backup & Recovery",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Notebook for backup options
    notebook = ttk.Notebook(backup_window)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Tab 1: Create Backup
    backup_tab = ttk.Frame(notebook)
    notebook.add(backup_tab, text="Create Backup")

    ttk.Label(backup_tab, text="Create a backup of the library system",
             font=('Arial', 12)).pack(pady=20)

    backup_type_var = tk.StringVar(value="full")
    ttk.Radiobutton(backup_tab, text="Full Backup (All data)",
                   variable=backup_type_var, value="full").pack(anchor=tk.W, padx=50, pady=5)
    ttk.Radiobutton(backup_tab, text="Database Only",
                   variable=backup_type_var, value="database").pack(anchor=tk.W, padx=50, pady=5)
    ttk.Radiobutton(backup_tab, text="Settings Only",
                   variable=backup_type_var, value="settings").pack(anchor=tk.W, padx=50, pady=5)

    def create_backup():
        try:
            import shutil
            from education_system.systems.university.infrastructure.paths import BACKUP_DIR

            BACKUP_DIR.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_type = backup_type_var.get()

            if backup_type == "full":
                backup_name = f"library_full_backup_{timestamp}.zip"
                backup_path = BACKUP_DIR / backup_name

                # Create zip of entire database directory
                from education_system.systems.university.infrastructure.paths import DATA_DIR
                shutil.make_archive(str(backup_path.with_suffix('')), 'zip', DATA_DIR)

            elif backup_type == "database":
                backup_name = f"library_db_backup_{timestamp}.db"
                backup_path = BACKUP_DIR / backup_name

                # Copy database file
                from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
                shutil.copy2(DEFAULT_DB_PATH, backup_path)

            else:  # settings
                backup_name = f"library_settings_backup_{timestamp}.sql"
                backup_path = BACKUP_DIR / backup_name

                # Export settings table
                conn = get_db_connection()
                with open(backup_path, 'w') as f:
                    for line in conn.iterdump():
                        if 'library_settings' in line:
                            f.write(f"{line}\n")
                conn.close()

            log_audit_event(get_current_user_id(), f"Created {backup_type} backup: {backup_name}", "system")

            messagebox.showinfo(_("common.success"),
                "Backup created successfully!\n\n" +
                f"Type: {backup_type}\n" +
                f"File: {backup_name}\n" +
                f"Location: {BACKUP_DIR}")

        except (sqlite3.Error, DatabaseError, OSError, IOError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Backup failed: {str(e)}")

    ttk.Button(backup_tab, text="Create Backup", command=create_backup).pack(pady=30)

    # Tab 2: Restore
    restore_tab = ttk.Frame(notebook)
    notebook.add(restore_tab, text="Restore from Backup")

    ttk.Label(restore_tab, text="Restore system from a backup file",
             font=('Arial', 12)).pack(pady=20)

    ttk.Label(restore_tab, text="⚠️ Warning: This will overwrite current data!",
             foreground='red').pack(pady=10)

    def restore_backup():
        file_path = filedialog.askopenfilename(
            title="Select Backup File",
            filetypes=[
                ("All backup files", "*.zip;*.db;*.sql"),
                ("ZIP files", "*.zip"),
                ("Database files", "*.db"),
                ("SQL files", "*.sql")
            ]
        )

        if not file_path:
            return

        confirm = messagebox.askyesnocancel("Confirm Restore",
            "This will overwrite current data. Continue?\n\n" +
            "A backup of current data will be created first.",
            icon='warning')

        if not confirm:
            return

        try:
            # Create safety backup first
            import shutil
            from education_system.systems.university.infrastructure.paths import BACKUP_DIR, DEFAULT_DB_PATH

            safety_backup = BACKUP_DIR / f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(DEFAULT_DB_PATH, safety_backup)

            # Restore based on file type
            if file_path.endswith('.zip'):
                # Extract zip
                shutil.unpack_archive(file_path, DEFAULT_DB_PATH.parent)
            elif file_path.endswith('.db'):
                # Copy database
                shutil.copy2(file_path, DEFAULT_DB_PATH)
            elif file_path.endswith('.sql'):
                # Execute SQL
                conn = get_db_connection()
                with open(file_path, 'r') as f:
                    conn.executescript(f.read())
                conn.commit()
                conn.close()

            log_audit_event(get_current_user_id(), f"Restored from backup: {os.path.basename(file_path)}", "system")

            messagebox.showinfo(_("common.success"),
                "System restored successfully!\n\n" +
                f"Safety backup created at:\n{safety_backup}")

        except (sqlite3.Error, DatabaseError, OSError, IOError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Restore failed: {str(e)}")

    ttk.Button(restore_tab, text="Select Backup File and Restore",
              command=restore_backup).pack(pady=30)

    # Tab 3: Scheduled Backups
    schedule_tab = ttk.Frame(notebook)
    notebook.add(schedule_tab, text="Backup Schedule")

    ttk.Label(schedule_tab, text="Configure automated backup schedule",
             font=('Arial', 12)).pack(pady=20)

    schedule_var = tk.StringVar(value="daily")
    ttk.Radiobutton(schedule_tab, text="Hourly", variable=schedule_var, value="hourly").pack(anchor=tk.W, padx=50, pady=5)
    ttk.Radiobutton(schedule_tab, text="Daily (recommended)", variable=schedule_var, value="daily").pack(anchor=tk.W, padx=50, pady=5)
    ttk.Radiobutton(schedule_tab, text="Weekly", variable=schedule_var, value="weekly").pack(anchor=tk.W, padx=50, pady=5)
    ttk.Radiobutton(schedule_tab, text="Disabled", variable=schedule_var, value="disabled").pack(anchor=tk.W, padx=50, pady=5)

    def save_schedule():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
            VALUES ('backup_schedule', ?)
            ''', (schedule_var.get(),))

            conn.commit()
            conn.close()

            messagebox.showinfo(_("common.success"), f"Backup schedule set to: {schedule_var.get()}")

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to save schedule: {str(e)}")

    ttk.Button(schedule_tab, text="Save Schedule", command=save_schedule).pack(pady=30)

    # Close button
    ttk.Button(backup_window, text=_("common.close"), command=backup_window.destroy).pack(pady=10)

def generate_library_statistics_export(self):
    """Generate comprehensive statistics export"""
    if not self.check_permission('generate_reports'):
        return

    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_filename = f"library_statistics_export_{timestamp}.json"

        # Generate comprehensive statistics
        stats = {
            'export_info': {
                'generated_at': datetime.now().isoformat(),
                'generated_by': get_current_user_id(),
                'system_version': '2.0.0'
            }
        }

        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Collection statistics
                cursor.execute('SELECT COUNT(*) FROM books')
                stats['collection_stats'] = {'total_books': cursor.fetchone()[0]}

                cursor.execute('SELECT COUNT(DISTINCT author) FROM books')
                stats['collection_stats']['unique_authors'] = cursor.fetchone()[0]

                cursor.execute('SELECT category, COUNT(*) FROM books GROUP BY category')
                stats['collection_stats']['books_by_category'] = dict(cursor.fetchall())

                conn.close()
        else:
            stats['collection_stats'] = {
                'total_books': 150,
                'unique_authors': 75,
                'books_by_category': {'Fiction': 60, 'Non-Fiction': 40, 'Science': 30, 'History': 20}
            }

        # Export to JSON file
        with open(export_filename, 'w') as f:
            json.dump(stats, f, indent=2, default=str)

        messagebox.showinfo(_("common.success"), f"Statistics exported to: {export_filename}")

        log_audit_event(get_current_user_id(),
                       f"Exported library statistics to {export_filename}",
                       "system")

    except (OSError, IOError, json.JSONDecodeError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Error exporting statistics: {str(e)}")

