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

from education_system.university_system.modules.domain.academics.gui.library.base import LibraryGUI

def show_all_books(self):
    """Show all books in a table"""
    if not self.check_permission('view_books'):
        return

    self.clear_content_area()

    books_frame = ttk.Frame(self.notebook)
    self.notebook.add(books_frame, text=_("library.tabs.all_books"))

    # Search and filter frame
    search_frame = ttk.Frame(books_frame)
    search_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Label(search_frame, text=_("library.labels.search")).pack(side=tk.LEFT)
    self.book_search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=self.book_search_var, width=30)
    search_entry.pack(side=tk.LEFT, padx=5)

    search_btn = ttk.Button(search_frame, text=_("common.search"), command=self.search_books_table)
    search_btn.pack(side=tk.LEFT, padx=5)

    refresh_btn = ttk.Button(search_frame, text=_("common.refresh"), command=self.refresh_books_table)
    refresh_btn.pack(side=tk.LEFT, padx=5)

    # Books table
    table_frame = ttk.Frame(books_frame)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # Create treeview for books
    columns = ('ID', 'Title', 'Author', 'Category', 'Status', 'Location')
    column_headers = {
        'ID': _("library.columns.id"),
        'Title': _("library.columns.title"),
        'Author': _("library.columns.author"),
        'Category': _("library.columns.category"),
        'Status': _("library.columns.status"),
        'Location': _("library.columns.location")
    }
    self.books_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)

    # Define column headings and widths
    column_widths = {'ID': 80, 'Title': 300, 'Author': 200, 'Category': 150, 'Status': 100, 'Location': 150}
    for col in columns:
        self.books_tree.heading(col, text=column_headers.get(col, col))
        self.books_tree.column(col, width=column_widths.get(col, 100))

    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.books_tree.yview)
    h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.books_tree.xview)
    self.books_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Pack treeview and scrollbars
    self.books_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    # Context menu for books
    self.create_books_context_menu()

    # Load books data
    self.load_books_data()

    # Bind double-click to view details
    self.books_tree.bind('<Double-1>', self.on_book_double_click)

def create_books_context_menu(self):
    """Create context menu for books table"""
    self.books_context_menu = tk.Menu(self.master, tearoff=0)
    self.books_context_menu.add_command(label=_("library.context.view_details"), command=self.view_selected_book)
    self.books_context_menu.add_command(label=_("library.context.edit_book"), command=self.edit_selected_book)
    self.books_context_menu.add_separator()
    self.books_context_menu.add_command(label=_("library.context.checkout"), command=self.checkout_selected_book)
    self.books_context_menu.add_command(label=_("library.context.reserve"), command=self.reserve_selected_book)
    self.books_context_menu.add_separator()
    self.books_context_menu.add_command(label=_("common.delete"), command=self.delete_selected_book)
    self.books_context_menu.add_separator()
    self.books_context_menu.add_command(label=_("library.context.generate_barcode"), command=self.generate_book_barcode)
    self.books_context_menu.add_command(label=_("library.context.view_loan_history"), command=self.view_book_loan_history)
    self.books_tree.bind('<Button-3>', self.show_books_context_menu)

def show_books_context_menu(self, event):
    """Show context menu for books"""
    item = self.books_tree.selection()[0] if self.books_tree.selection() else None
    if item:
        # Rebuild cross-link items each click for the selected row.
        try:
            from education_system.university_system.modules.domain.academics.gui.library import _cross_links
            menu = self.books_context_menu
            # Drop previously appended cross-link items (the original
            # menu has 7 entries up to and including the trailing
            # "View Loan History"; anything beyond that came from us).
            try:
                # Original menu ends at index 9 (View Loan History);
                # delete anything beyond that — it must be ours from a
                # previous right-click.
                while (menu.index("end") is not None
                       and menu.index("end") > 9):
                    menu.delete("end")
            except Exception:
                pass
            values = self.books_tree.item(item).get("values") or []
            _cross_links.append_cross_links(
                menu,
                _cross_links.books_menu_items(values, parent=self.master),
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Could not append cross-link items")
        self.books_context_menu.post(event.x_root, event.y_root)

def load_books_data(self, search_term=""):
    """Load books data into the table"""
    # Clear existing data
    for item in self.books_tree.get_children():
        self.books_tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            if search_term:
                cursor.execute('''
                SELECT book_id, title, author, category, status, location
                FROM books
                WHERE title LIKE ? OR author LIKE ? OR category LIKE ?
                ORDER BY title
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute('''
                SELECT book_id, title, author, category, status, location
                FROM books
                ORDER BY title
                ''')

            books = cursor.fetchall()
            conn.close()

            # Insert books into table
            for book in books:
                self.books_tree.insert('', 'end', values=book)

            self.update_status(_("library.status.loaded_books").format(count=len(books)), "success")
        else:
            # Demo data
            demo_books = [
                ("B10001", "The Great Gatsby", "F. Scott Fitzgerald", "Fiction", _("library.status_values.available"), "Floor 1, A1"),
                ("B10002", "To Kill a Mockingbird", "Harper Lee", "Fiction", _("library.status_values.checked_out"), "Floor 1, A2"),
                ("B10003", "1984", "George Orwell", "Fiction", _("library.status_values.available"), "Floor 1, A3"),
            ]

            for book in demo_books:
                self.books_tree.insert('', 'end', values=book)

    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), _("library.messages.error_loading_books").format(error=str(e)))

def search_books_table(self):
    """Search books in the table"""
    search_term = self.book_search_var.get()
    self.load_books_data(search_term)

def refresh_books_table(self):
    """Refresh the books table"""
    self.book_search_var.set("")
    self.load_books_data()

def on_book_double_click(self, event):
    """Handle double-click on book"""
    self.view_selected_book()

def view_selected_book(self):
    """View details of selected book"""
    selection = self.books_tree.selection()
    if not selection:
        messagebox.showwarning(_("common.warning"), _("library.messages.please_select_book"))
        return

    item = self.books_tree.item(selection[0])
    book_id = item['values'][0]

    self.show_book_details(book_id)

def show_book_details(self, book_id):
    """Show detailed book information"""
    # Create new tab for book details
    details_frame = ttk.Frame(self.notebook)
    self.notebook.add(details_frame, text=_("library.tabs.book_details").format(book_id=book_id))
    self.notebook.select(details_frame)

    # Create scrollable frame
    canvas = tk.Canvas(details_frame)
    scrollbar = ttk.Scrollbar(details_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Get book details
    book_details = self.get_book_details(book_id)

    if book_details:
        # Book information
        info_frame = ttk.LabelFrame(scrollable_frame, text=_("library.details.book_information"))
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        # Display book information
        info_fields = [
            (_("library.fields.title"), book_details.get('title', _("common.na"))),
            (_("library.fields.author"), book_details.get('author', _("common.na"))),
            (_("library.fields.isbn"), book_details.get('isbn', _("common.na"))),
            (_("library.fields.category"), book_details.get('category', _("common.na"))),
            (_("library.fields.status"), book_details.get('status', _("common.na"))),
            (_("library.fields.location"), book_details.get('location', _("common.na"))),
            (_("library.fields.reading_level"), book_details.get('reading_level', _("common.na"))),
            (_("library.fields.year_published"), book_details.get('year_published', _("common.na"))),
            (_("library.fields.publisher"), book_details.get('publisher', _("common.na"))),
        ]

        for i, (label, value) in enumerate(info_fields):
            ttk.Label(info_frame, text=label, style='Heading.TLabel').grid(row=i, column=0, sticky='w', padx=5, pady=2)
            ttk.Label(info_frame, text=str(value)).grid(row=i, column=1, sticky='w', padx=5, pady=2)

        # Description
        if book_details.get('description'):
            desc_frame = ttk.LabelFrame(scrollable_frame, text=_("library.details.description"))
            desc_frame.pack(fill=tk.X, padx=10, pady=5)

            desc_text = tk.Text(desc_frame, height=4, wrap=tk.WORD)
            desc_text.pack(fill=tk.X, padx=5, pady=5)
            desc_text.insert(tk.END, book_details['description'])
            desc_text.config(state=tk.DISABLED)

        # Actions frame
        actions_frame = ttk.LabelFrame(scrollable_frame, text=_("library.details.actions"))
        actions_frame.pack(fill=tk.X, padx=10, pady=5)

        action_buttons = [
            (_("library.buttons.checkout"), lambda: self.checkout_book_dialog(book_id)),
            (_("library.buttons.reserve"), lambda: self.reserve_book_dialog(book_id)),
            (_("common.edit"), lambda: self.edit_book_dialog(book_id)),
            (_("library.buttons.reviews"), lambda: self.show_book_reviews(book_id)),
        ]

        for i, (text, command) in enumerate(action_buttons):
            btn = ttk.Button(actions_frame, text=text, command=command)
            btn.grid(row=0, column=i, padx=5, pady=5)

        # Loan history
        history_frame = ttk.LabelFrame(scrollable_frame, text=_("library.details.loan_history"))
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.create_loan_history_table(history_frame, book_id)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

def get_book_details(self, book_id):
    """Get detailed book information"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return None

            cursor = conn.cursor()
            cursor.execute('''
            SELECT book_id, title, author, isbn, publisher, category, year_published,
                   description, location, status, reading_level, tags
            FROM books WHERE book_id = ?
            ''', (book_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                columns = ['book_id', 'title', 'author', 'isbn', 'publisher', 'category',
                          'year_published', 'description', 'location', 'status', 'reading_level', 'tags']
                return dict(zip(columns, result))
        else:
            # Demo data
            return {
                'book_id': book_id,
                'title': 'Sample Book',
                'author': 'Sample Author',
                'isbn': '123-456-789',
                'publisher': 'Sample Publisher',
                'category': 'Fiction',
                'year_published': 2023,
                'description': 'This is a sample book description for demonstration purposes.',
                'location': 'Floor 1, A1',
                'status': 'Available',
                'reading_level': 'High School',
                'tags': 'fiction, sample'
            }
    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), _("library.messages.error_getting_book_details").format(error=str(e)))
        return None

def generate_book_barcode(self):
    """Generate barcode for selected book"""
    selection = self.books_tree.selection()
    if not selection:
        messagebox.showwarning(_("common.warning"), _("library.messages.please_select_book"))
        return

    item = self.books_tree.item(selection[0])
    book_id = item['values'][0]
    book_title = item['values'][1] if len(item['values']) > 1 else "Unknown Title"

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            # Try to generate using original library functions
            try:
                barcode = generate_barcode(book_id)
                qr_code_path = generate_qr_code(book_id, book_title)
                # Convert PosixPath to string for database compatibility
                qr_code_path = str(qr_code_path) if qr_code_path else None

                # Update database with generated barcode
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE books SET barcode = ?, qr_code_path = ? WHERE book_id = ?',
                                 (barcode, qr_code_path, book_id))
                    conn.commit()
                    conn.close()

                messagebox.showinfo(_("common.success"),
                                  f"Barcode generated successfully!\n\n"
                                  f"Book ID: {book_id}\n"
                                  f"Title: {book_title}\n"
                                  f"Barcode: {barcode}")

                # Refresh the books table to show updated barcode
                self.refresh_books_table()

            except (sqlite3.Error, DatabaseError, tk.TclError) as e:
                # Fallback to simple barcode generation
                barcode = f"LIB{book_id}"
                messagebox.showinfo("Barcode Generated",
                                  f"Simple barcode generated:\n\n"
                                  f"Book ID: {book_id}\n"
                                  f"Title: {book_title}\n"
                                  f"Barcode: {barcode}")
        else:
            # Demo mode - simple barcode
            barcode = f"LIB{book_id}"
            messagebox.showinfo("Demo Barcode",
                              f"Demo barcode generated:\n\n"
                              f"Book ID: {book_id}\n"
                              f"Title: {book_title}\n"
                              f"Barcode: {barcode}")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to generate barcode: {str(e)}")

def create_loan_history_table(self, parent, book_id):
    """Create loan history table for a book"""
    columns = ('User ID', 'Checkout Date', 'Due Date', 'Return Date', 'Status')
    history_tree = ttk.Treeview(parent, columns=columns, show='headings', height=6)

    for col in columns:
        history_tree.heading(col, text=col)
        history_tree.column(col, width=120)

    # Add scrollbar
    scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=history_tree.yview)
    history_tree.configure(yscrollcommand=scrollbar.set)

    history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Load loan history
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT user_id, checkout_date, due_date, return_date, status
                FROM book_loans
                WHERE book_id = ?
                ORDER BY checkout_date DESC
                LIMIT 10
                ''', (book_id,))

                loans = cursor.fetchall()
                conn.close()

                for loan in loans:
                    # Format dates
                    formatted_loan = list(loan)
                    for i in [1, 2, 3]:  # Date fields
                        if formatted_loan[i]:
                            formatted_loan[i] = formatted_loan[i][:10]
                    history_tree.insert('', 'end', values=formatted_loan)
    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        print(f"Error loading loan history: {e}")

def show_add_book(self):
    """Show add book dialog"""
    if not self.check_permission('manage_books'):
        return

    self.add_book_dialog()

def add_book_dialog(self):
    """Create add book dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.add_new_book"))
    dialog.geometry("600x700")
    dialog.transient(self.master)
    dialog.grab_set()

    # Center the dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")

    # Create form
    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Form fields
    fields = [
        ("Title*:", "title"),
        ("Author*:", "author"),
        ("ISBN:", "isbn"),
        ("Publisher:", "publisher"),
        ("Category:", "category"),
        ("Year Published:", "year_published"),
        ("Location:", "location"),
        ("Reading Level:", "reading_level"),
    ]

    self.add_book_vars = {}

    for i, (label, field) in enumerate(fields):
        ttk.Label(main_frame, text=label).grid(row=i, column=0, sticky='w', pady=5)

        if field == "category":
            # Category dropdown
            var = tk.StringVar()
            combo = ttk.Combobox(main_frame, textvariable=var, width=40)
            combo['values'] = ('Fiction', 'Non-Fiction', 'Science', 'History', 'Computer Science',
                              'Mathematics', 'Philosophy', 'Psychology', 'Business', 'Biography')
            combo.grid(row=i, column=1, sticky='w', pady=5)
            self.add_book_vars[field] = var
        elif field == "reading_level":
            # Reading level dropdown
            var = tk.StringVar()
            combo = ttk.Combobox(main_frame, textvariable=var, width=40)
            combo['values'] = ('Elementary', 'Middle School', 'High School', 'College', 'Unknown')
            combo.grid(row=i, column=1, sticky='w', pady=5)
            self.add_book_vars[field] = var
        elif field == "isbn":
            # ISBN field with lookup button
            isbn_frame = ttk.Frame(main_frame)
            isbn_frame.grid(row=i, column=1, sticky='w', pady=5)

            var = tk.StringVar()
            entry = ttk.Entry(isbn_frame, textvariable=var, width=32)
            entry.pack(side=tk.LEFT)
            self.add_book_vars[field] = var

            # Add lookup button
            lookup_btn = ttk.Button(isbn_frame, text="🔍 Lookup",
                                   command=lambda: self.lookup_isbn_data(dialog),
                                   width=10)
            lookup_btn.pack(side=tk.LEFT, padx=5)
        else:
            # Regular entry
            var = tk.StringVar()
            entry = ttk.Entry(main_frame, textvariable=var, width=40)
            entry.grid(row=i, column=1, sticky='w', pady=5)
            self.add_book_vars[field] = var

    # Description field
    ttk.Label(main_frame, text="Description:").grid(row=len(fields), column=0, sticky='nw', pady=5)
    self.add_book_description = tk.Text(main_frame, height=4, width=40)
    self.add_book_description.grid(row=len(fields), column=1, sticky='w', pady=5)

    # Tags field
    ttk.Label(main_frame, text="Tags:").grid(row=len(fields)+1, column=0, sticky='w', pady=5)
    self.add_book_tags = tk.StringVar()
    ttk.Entry(main_frame, textvariable=self.add_book_tags, width=40).grid(row=len(fields)+1, column=1, sticky='w', pady=5)
    ttk.Label(main_frame, text="(comma-separated)", font=('Arial', 8)).grid(row=len(fields)+2, column=1, sticky='w')

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=len(fields)+3, column=0, columnspan=2, pady=20)

    ttk.Button(button_frame, text="Add Book", command=lambda: self.save_new_book(dialog)).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # Focus on title field
    list(self.add_book_vars.values())[0].get()  # Get title entry and focus

def lookup_isbn_data(self, dialog):
    """Lookup book data by ISBN and auto-fill the form"""
    isbn = self.add_book_vars['isbn'].get().strip()

    if not isbn:
        messagebox.showwarning("ISBN Required", "Please enter an ISBN number first")
        return

    # Clean ISBN (remove dashes and spaces)
    isbn_clean = isbn.replace('-', '').replace(' ', '')

    # Show loading status
    original_text = dialog.title()
    dialog.title("Looking up ISBN...")

    def lookup_thread():
        """Run lookup in background thread to avoid freezing GUI"""
        try:
            # Try Open Library API first
            book_data = self._fetch_from_openlibrary(isbn_clean)

            if not book_data:
                # Try Google Books API as fallback
                book_data = self._fetch_from_google_books(isbn_clean)

            # Update GUI in main thread
            dialog.after(0, lambda: self._populate_book_data(book_data, dialog, original_text))

        except (urllib.error.URLError, json.JSONDecodeError, tk.TclError, ValueError) as e:
            dialog.after(0, lambda _e=e: self._handle_lookup_error(str(_e), dialog, original_text))

    # Start lookup in background thread
    thread = threading.Thread(target=lookup_thread, daemon=True)
    thread.start()

def _fetch_from_openlibrary(self, isbn):
    """Fetch book data from Open Library API"""
    try:
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"

        with urllib.request.urlopen(url, timeout=10) as response:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            data = json.loads(response.read().decode())

        key = f"ISBN:{isbn}"
        if key not in data:
            return None

        book = data[key]

        # Extract data
        book_data = {
            'title': book.get('title', ''),
            'author': ', '.join([author.get('name', '') for author in book.get('authors', [])]),
            'publisher': ', '.join([pub.get('name', '') for pub in book.get('publishers', [])]),
            'year': book.get('publish_date', ''),
            'description': book.get('notes', '') or book.get('subtitle', ''),
            'subjects': book.get('subjects', [])
        }

        return book_data

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError):
        return None

def _fetch_from_google_books(self, isbn):
    """Fetch book data from Google Books API (fallback)"""
    try:
        query = urllib.parse.quote(f"isbn:{isbn}")
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}"

        with urllib.request.urlopen(url, timeout=10) as response:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            data = json.loads(response.read().decode())

        if 'items' not in data or len(data['items']) == 0:
            return None

        volume_info = data['items'][0]['volumeInfo']

        # Extract data
        book_data = {
            'title': volume_info.get('title', ''),
            'author': ', '.join(volume_info.get('authors', [])),
            'publisher': volume_info.get('publisher', ''),
            'year': volume_info.get('publishedDate', '')[:4] if volume_info.get('publishedDate') else '',
            'description': volume_info.get('description', ''),
            'subjects': volume_info.get('categories', [])
        }

        return book_data

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError):
        return None

def _populate_book_data(self, book_data, dialog, original_title):
    """Populate form fields with book data"""
    dialog.title(original_title)

    if not book_data:
        messagebox.showinfo("Not Found",
                          "Book data not found for this ISBN.\n\n" +
                          "Please enter the details manually.")
        return

    # Auto-fill fields
    if book_data.get('title'):
        self.add_book_vars['title'].set(book_data['title'])

    if book_data.get('author'):
        self.add_book_vars['author'].set(book_data['author'])

    if book_data.get('publisher'):
        self.add_book_vars['publisher'].set(book_data['publisher'])

    if book_data.get('year'):
        year_str = str(book_data['year'])
        # Extract just the year if it's a full date
        if len(year_str) >= 4:
            self.add_book_vars['year_published'].set(year_str[:4])

    # Set description
    if book_data.get('description'):
        self.add_book_description.delete("1.0", tk.END)
        self.add_book_description.insert("1.0", book_data['description'])

    # Set category based on subjects
    if book_data.get('subjects'):
        # Try to match subject to our categories
        # Handle subjects that may be strings or dicts
        subjects_lower = []
        for s in book_data['subjects']:
            if isinstance(s, str):
                subjects_lower.append(s.lower())
            elif isinstance(s, dict):
                # Extract name/value from dict
                subject_str = s.get('name') or s.get('value') or s.get('subject') or str(s)
                subjects_lower.append(subject_str.lower())

        category_mapping = {
            'fiction': 'Fiction',
            'science': 'Science',
            'history': 'History',
            'computer': 'Computer Science',
            'mathematics': 'Mathematics',
            'math': 'Mathematics',
            'philosophy': 'Philosophy',
            'psychology': 'Psychology',
            'business': 'Business',
            'biography': 'Biography'
        }

        for subject in subjects_lower:
            for key, value in category_mapping.items():
                if key in subject:
                    self.add_book_vars['category'].set(value)
                    break

    # Show success message
    messagebox.showinfo(_("common.success"),
                      f"Book information found!\n\n" +
                      f"Title: {book_data.get('title', 'N/A')}\n" +
                      f"Author: {book_data.get('author', 'N/A')}\n\n" +
                      f"Please review and adjust the details as needed.")

def _handle_lookup_error(self, error_msg, dialog, original_title):
    """Handle lookup errors"""
    dialog.title(original_title)
    messagebox.showerror("Lookup Error",
                       f"Failed to lookup ISBN:\n{error_msg}\n\n" +
                       "Please check your internet connection and try again,\n" +
                       "or enter the book details manually.")

def save_new_book(self, dialog):
    """Save new book to database"""
    # Validate required fields
    title = self.add_book_vars['title'].get().strip()
    author = self.add_book_vars['author'].get().strip()

    if not title or not author:
        messagebox.showerror(_("common.error"), "Title and Author are required fields")
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            # Use original add book function
            book_data = {}
            for field, var in self.add_book_vars.items():
                book_data[field] = var.get().strip()

            book_data['description'] = self.add_book_description.get("1.0", tk.END).strip()
            book_data['tags'] = self.add_book_tags.get().strip()

            # Call original function (you'd need to modify enhanced_add_book to accept parameters)
            success = self.add_book_to_database(book_data)

            if success:
                messagebox.showinfo(_("common.success"), "Book added successfully!")
                dialog.destroy()
                self.refresh_books_table() if hasattr(self, 'books_tree') else None
            else:
                messagebox.showerror(_("common.error"), "Failed to add book")
        else:
            # Demo mode
            messagebox.showinfo(_("common.demo"), f"Book '{title}' by {author} would be added to the database")
            dialog.destroy()

    except (sqlite3.Error, DatabaseError, ValidationError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Error adding book: {str(e)}")

def add_book_to_database(self, book_data):
    """Add book to database using original functions"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Generate book ID
        cursor.execute('SELECT MAX(CAST(SUBSTR(book_id, 2) AS INTEGER)) FROM books')
        result = cursor.fetchone()[0]
        next_id = 10001 if result is None else result + 1
        book_id = f"B{next_id}"

        # Prepare data
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        year_published = int(book_data['year_published']) if book_data['year_published'].isdigit() else None
        tags = [tag.strip() for tag in book_data['tags'].split(',') if tag.strip()]

        # Generate barcode
        if ORIGINAL_LIBRARY_AVAILABLE:
            barcode = generate_barcode(book_id)
            qr_code_path = generate_qr_code(book_id, book_data['title'])
            # Convert PosixPath to string for database compatibility
            qr_code_path = str(qr_code_path) if qr_code_path else None
        else:
            barcode = f"LIB{book_id}"
            qr_code_path = None

        # Insert book
        cursor.execute('''
        INSERT INTO books (
            book_id, title, author, isbn, publisher, category, year_published,
            description, location, status, added_date, last_updated,
            reading_level, tags, cover_image_path, digital_copy_path, acquisition_cost,
            barcode, qr_code_path, total_pages, language, edition, condition_notes,
            purchase_price, purchase_date, supplier, quantity
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            book_id, book_data['title'], book_data['author'], book_data.get('isbn'),
            book_data.get('publisher'), book_data.get('category', 'General'), year_published,
            book_data.get('description'), book_data.get('location'), 'available', now, now,
            book_data.get('reading_level', 'Unknown'), json.dumps(tags), None, None, 0.0,
            barcode, qr_code_path, None, 'English', None, None,
            0.0, None, None, 1
        ))

        conn.commit()

        # Log the action
        if ORIGINAL_LIBRARY_AVAILABLE:
            log_audit_event(get_current_user_id(), f"Added book: {book_id}", "books", book_id)

        conn.close()
        return True

    except (sqlite3.Error, DatabaseError, ValueError, json.JSONDecodeError) as e:
        print(f"Error adding book to database: {e}")
        return False

def edit_selected_book(self):
    """Edit details of selected book"""
    selection = self.books_tree.selection()
    if not selection:
        messagebox.showwarning(_("common.warning"), "Please select a book to edit")
        return

    item = self.books_tree.item(selection[0])
    book_id = item['values'][0]

    try:
        # Get current book details
        book_details = self.get_book_details(book_id)
        if not book_details:
            messagebox.showerror(_("common.error"), "Book not found")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.master)
        dialog.title(f"Edit Book - {book_id}")
        dialog.geometry("600x700")
        dialog.transient(self.master)

        # Create form
        form_frame = ttk.Frame(dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        fields = {}
        field_names = [
            ('title', 'Title'),
            ('author', 'Author'),
            ('isbn', 'ISBN'),
            ('category', 'Category'),
            ('publisher', 'Publisher'),
            ('publication_year', 'Publication Year'),
            ('quantity', 'Quantity'),
            ('available_quantity', 'Available Quantity'),
            ('location', 'Location'),
            ('status', 'Status')
        ]

        for i, (field_key, field_label) in enumerate(field_names):
            ttk.Label(form_frame, text=f"{field_label}:").grid(row=i, column=0, sticky='w', pady=5, padx=5)

            if field_key == 'status':
                fields[field_key] = tk.StringVar(value=book_details.get(field_key, ''))
                ttk.Combobox(form_frame, textvariable=fields[field_key],
                           values=['Available', 'Checked Out', 'Reserved', 'Maintenance'],
                           width=37).grid(row=i, column=1, pady=5, padx=5)
            else:
                fields[field_key] = tk.StringVar(value=book_details.get(field_key, ''))
                ttk.Entry(form_frame, textvariable=fields[field_key], width=40).grid(row=i, column=1, pady=5, padx=5)

        def save_changes():
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE books
                    SET title = ?, author = ?, isbn = ?, category = ?,
                        publisher = ?, publication_year = ?, quantity = ?,
                        available_quantity = ?, location = ?, status = ?
                    WHERE book_id = ?
                ''', (
                    fields['title'].get(),
                    fields['author'].get(),
                    fields['isbn'].get(),
                    fields['category'].get(),
                    fields['publisher'].get(),
                    fields['publication_year'].get(),
                    fields['quantity'].get(),
                    fields['available_quantity'].get(),
                    fields['location'].get(),
                    fields['status'].get(),
                    book_id
                ))

                conn.commit()
                conn.close()

                # Log the edit
                try:
                    user_id = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'system'
                    log_audit_event(user_id, 'update', 'books', book_id, True)
                except tk.TclError:
                    pass

                messagebox.showinfo(_("common.success"), "Book updated successfully!")
                dialog.destroy()
                self.load_books_data()

            except tk.TclError as e:
                messagebox.showerror(_("common.error"), f"Update failed: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Edit failed: {str(e)}")

def delete_selected_book(self):
    """Delete book with confirmation"""
    selection = self.books_tree.selection()
    if not selection:
        messagebox.showwarning(_("common.warning"), "Please select a book to delete")
        return

    item = self.books_tree.item(selection[0])
    book_id = item['values'][0]
    title = item['values'][1]

    # Confirm deletion
    result = messagebox.askyesno(
        "Confirm Deletion",
        f"Are you sure you want to delete this book?\n\n"
        f"Book ID: {book_id}\n"
        f"Title: {title}\n\n"
        f"This action cannot be undone!"
    )

    if not result:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if book has active loans
        cursor.execute('''
            SELECT COUNT(*) FROM loans
            WHERE book_id = ? AND status = 'active'
        ''', (book_id,))

        active_loans = cursor.fetchone()[0]
        if active_loans > 0:
            messagebox.showerror(
                "Cannot Delete",
                f"This book has {active_loans} active loan(s).\n"
                "Please return all copies before deleting."
            )
            conn.close()
            return

        # Delete the book
        cursor.execute('DELETE FROM books WHERE book_id = ?', (book_id,))
        conn.commit()
        conn.close()

        # Log the deletion
        try:
            user_id = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'system'
            log_audit_event(user_id, 'delete', 'books', book_id, True)
        except (sqlite3.Error, DatabaseError):
            pass

        messagebox.showinfo(_("common.success"), "Book deleted successfully!")
        self.load_books_data()
        self.update_status(f"Deleted book: {book_id}", "success")

    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Deletion failed: {str(e)}")

def view_book_loan_history(self):
    """View loan history for selected book"""
    selection = self.books_tree.selection()
    if not selection:
        messagebox.showwarning(_("common.warning"), _("library.messages.please_select_book"))
        return

    item = self.books_tree.item(selection[0])
    book_id = item['values'][0]
    title = item['values'][1]

    # Create loan history dialog
    dialog = tk.Toplevel(self.master)
    dialog.title(f"Loan History - {title}")
    dialog.geometry("900x600")
    dialog.transient(self.master)

    ttk.Label(dialog, text=f"Loan History for: {title}", font=('Arial', 12, 'bold')).pack(pady=10)
    ttk.Label(dialog, text=f"Book ID: {book_id}").pack(pady=5)

    # Create treeview for loan history
    frame = ttk.Frame(dialog)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('Loan ID', 'User ID', 'Loan Date', 'Due Date', 'Return Date', 'Status', 'Fine')
    history_tree = ttk.Treeview(frame, columns=columns, show='headings', height=20)

    for col in columns:
        history_tree.heading(col, text=col)
        history_tree.column(col, width=120)

    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=history_tree.yview)
    h_scrollbar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=history_tree.xview)
    history_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    history_tree.grid(row=0, column=0, sticky='nsew')
    v_scrollbar.grid(row=0, column=1, sticky='ns')
    h_scrollbar.grid(row=1, column=0, sticky='ew')

    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    try:
        # Load loan history
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT loan_id, user_id, loan_date, due_date, return_date, status,
                   COALESCE(fine_amount, 0) as fine
            FROM loans
            WHERE book_id = ?
            ORDER BY loan_date DESC
        ''', (book_id,))

        loans = cursor.fetchall()
        conn.close()

        for loan in loans:
            history_tree.insert('', 'end', values=loan)

        # Add summary
        summary_frame = ttk.Frame(dialog)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)

        total_loans = len(loans)
        active_loans = sum(1 for loan in loans if loan[5] == 'active')
        returned_loans = sum(1 for loan in loans if loan[5] == 'returned')
        total_fines = sum(float(loan[6] or 0) for loan in loans)

        ttk.Label(summary_frame, text=f"Total Loans: {total_loans}").pack(side=tk.LEFT, padx=10)
        ttk.Label(summary_frame, text=f"Active: {active_loans}").pack(side=tk.LEFT, padx=10)
        ttk.Label(summary_frame, text=f"Returned: {returned_loans}").pack(side=tk.LEFT, padx=10)
        ttk.Label(summary_frame, text=f"Total Fines: £{total_fines:.2f}").pack(side=tk.LEFT, padx=10)

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to load loan history: {str(e)}")

    # Close button
    ttk.Button(dialog, text=_("common.close"), command=dialog.destroy).pack(pady=10)

def checkout_book_dialog(self, book_id):
    """Checkout dialog opened from book details view"""
    try:
        # Get current user
        current_user = get_current_user() if SHARED_AUTH_AVAILABLE else None
        if not current_user:
            messagebox.showerror(_("common.error"), "No user logged in. Please log in to checkout books.")
            return

        current_user_id = current_user.get('username') or current_user.get('user_id') or current_user.get('id')
        current_role = current_user.get('role', '').lower()

        # Get book details
        book_details = self.get_book_details(book_id)
        if not book_details:
            messagebox.showerror(_("common.error"), "Book not found")
            return

        if book_details.get('status', '').lower() not in ('available',):
            messagebox.showwarning(_("common.warning"),
                                   f"This book is currently '{book_details.get('status')}' and cannot be checked out.")
            return

        dialog = tk.Toplevel(self.master)
        dialog.title(f"Checkout - {book_details.get('title', book_id)}")
        dialog.geometry("500x450")
        dialog.transient(self.master)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Book info
        book_frame = ttk.LabelFrame(main_frame, text="Book Information")
        book_frame.pack(fill=tk.X, pady=(0, 10))

        book_info = (
            f"Title: {book_details.get('title', 'N/A')}\n"
            f"Author: {book_details.get('author', 'N/A')}\n"
            f"Book ID: {book_id}\n"
            f"Status: {book_details.get('status', 'N/A')}"
        )
        ttk.Label(book_frame, text=book_info, justify=tk.LEFT).pack(anchor='w', padx=10, pady=10)

        # Borrower frame
        borrower_frame = ttk.LabelFrame(main_frame, text="Borrower")
        borrower_frame.pack(fill=tk.X, pady=(0, 10))

        if current_role in ('admin', 'staff', 'instructor', 'librarian'):
            ttk.Label(borrower_frame, text="User ID / Student ID:").pack(anchor='w', padx=10, pady=(10, 0))
            borrower_var = tk.StringVar()
            ttk.Entry(borrower_frame, textvariable=borrower_var, width=30).pack(anchor='w', padx=10, pady=(5, 10))
        else:
            borrower_var = tk.StringVar(value=current_user_id)
            user_info = f"User: {current_user_id}\nRole: {current_role}"
            if current_user.get('first_name'):
                user_info = f"Name: {current_user.get('first_name', '')} {current_user.get('last_name', '')}\n" + user_info
            ttk.Label(borrower_frame, text=user_info, justify=tk.LEFT).pack(anchor='w', padx=10, pady=10)

        # Eligibility info
        eligibility_frame = ttk.LabelFrame(main_frame, text="Loan Details")
        eligibility_frame.pack(fill=tk.X, pady=(0, 10))

        eligibility_text = tk.Text(eligibility_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        eligibility_text.pack(fill=tk.X, padx=10, pady=10)

        def check_eligibility():
            uid = borrower_var.get().strip()
            if not uid:
                messagebox.showwarning(_("common.warning"), "Please enter a user ID")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Count active loans
                cursor.execute('''
                    SELECT COUNT(*) FROM book_loans
                    WHERE user_id = ? AND status IN ('active', 'overdue')
                ''', (uid,))
                active_loans = cursor.fetchone()[0]

                # Get max loans setting
                cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "max_loans"')
                max_result = cursor.fetchone()
                max_loans = int(max_result[0]) if max_result else 5

                # Get loan period
                cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "loan_period_days"')
                period_result = cursor.fetchone()
                loan_period = int(period_result[0]) if period_result else 14

                conn.close()

                due_date = (datetime.now() + timedelta(days=loan_period)).strftime('%Y-%m-%d')
                eligible = active_loans < max_loans

                info = (
                    f"Active loans: {active_loans} / {max_loans}\n"
                    f"Loan period: {loan_period} days\n"
                    f"Due date: {due_date}\n"
                    f"Eligible: {'Yes' if eligible else 'No - max loans reached'}"
                )

                eligibility_text.config(state=tk.NORMAL)
                eligibility_text.delete("1.0", tk.END)
                eligibility_text.insert(tk.END, info)
                eligibility_text.config(state=tk.DISABLED)

                if eligible:
                    checkout_btn.config(state=tk.NORMAL)
                else:
                    checkout_btn.config(state=tk.DISABLED)

            except (sqlite3.Error, DatabaseError, ValueError) as e:
                messagebox.showerror(_("common.error"), f"Eligibility check failed: {str(e)}")

        ttk.Button(eligibility_frame, text="Check Eligibility", command=check_eligibility).pack(anchor='w', padx=10, pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        def process():
            uid = borrower_var.get().strip()
            if not uid:
                messagebox.showwarning(_("common.warning"), "Please enter a user ID")
                return

            try:
                success = self.checkout_book_database(book_id, uid)
                if success:
                    messagebox.showinfo(_("common.success"),
                                        f"Book checked out successfully!\n\n"
                                        f"Title: {book_details.get('title')}\n"
                                        f"Borrower: {uid}")
                    dialog.destroy()
                    # Refresh book details
                    self.show_book_details(book_id)
                else:
                    messagebox.showerror(_("common.error"), "Checkout failed")
            except (sqlite3.Error, DatabaseError, tk.TclError) as e:
                messagebox.showerror(_("common.error"), f"Checkout error: {str(e)}")

        checkout_btn = ttk.Button(button_frame, text="Checkout", command=process, state=tk.DISABLED)
        checkout_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Auto-check eligibility for non-staff users
        if current_role not in ('admin', 'staff', 'instructor', 'librarian'):
            check_eligibility()

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to open checkout dialog: {str(e)}")

def reserve_book_dialog(self, book_id):
    """Reserve book dialog opened from book details view"""
    try:
        # Get current user
        current_user = get_current_user() if SHARED_AUTH_AVAILABLE else None
        if not current_user:
            messagebox.showerror(_("common.error"), "No user logged in. Please log in to reserve books.")
            return

        current_user_id = current_user.get('username') or current_user.get('user_id') or current_user.get('id')
        current_role = current_user.get('role', '').lower()

        # Get book details
        book_details = self.get_book_details(book_id)
        if not book_details:
            messagebox.showerror(_("common.error"), "Book not found")
            return

        dialog = tk.Toplevel(self.master)
        dialog.title(f"Reserve - {book_details.get('title', book_id)}")
        dialog.geometry("500x400")
        dialog.transient(self.master)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Book info
        book_frame = ttk.LabelFrame(main_frame, text="Book Information")
        book_frame.pack(fill=tk.X, pady=(0, 10))

        book_info = (
            f"Title: {book_details.get('title', 'N/A')}\n"
            f"Author: {book_details.get('author', 'N/A')}\n"
            f"Book ID: {book_id}\n"
            f"Current Status: {book_details.get('status', 'N/A')}"
        )
        ttk.Label(book_frame, text=book_info, justify=tk.LEFT).pack(anchor='w', padx=10, pady=10)

        # Reservation info
        info_frame = ttk.LabelFrame(main_frame, text="Reservation Queue")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        queue_info = "Loading..."
        queue_label = ttk.Label(info_frame, text=queue_info, justify=tk.LEFT)
        queue_label.pack(anchor='w', padx=10, pady=10)

        # Load queue info
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get active reservations count
            cursor.execute('''
                SELECT COUNT(*) FROM book_reservations
                WHERE book_id = ? AND status = 'active'
            ''', (book_id,))
            queue_count = cursor.fetchone()[0]

            # Check if user already has a reservation
            cursor.execute('''
                SELECT reservation_id FROM book_reservations
                WHERE book_id = ? AND user_id = ? AND status = 'active'
            ''', (book_id, current_user_id))
            existing = cursor.fetchone()

            # Get reservation period
            cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "reservation_period_days"')
            period_result = cursor.fetchone()
            reservation_days = int(period_result[0]) if period_result else 3

            conn.close()

            expiry_date = (datetime.now() + timedelta(days=reservation_days)).strftime('%Y-%m-%d')

            if existing:
                queue_label.config(text=f"You already have an active reservation for this book.\n"
                                        f"People in queue: {queue_count}")
                has_existing = True
            else:
                queue_label.config(text=f"People in queue: {queue_count}\n"
                                        f"Your position will be: {queue_count + 1}\n"
                                        f"Reservation period: {reservation_days} days\n"
                                        f"Expires: {expiry_date}")
                has_existing = False

        except (sqlite3.Error, DatabaseError, ValueError) as e:
            queue_label.config(text=f"Could not load queue info: {str(e)}")
            has_existing = False

        # Borrower field for staff
        if current_role in ('admin', 'staff', 'instructor', 'librarian'):
            borrower_frame = ttk.LabelFrame(main_frame, text="Reserve For")
            borrower_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Label(borrower_frame, text="User ID / Student ID:").pack(anchor='w', padx=10, pady=(10, 0))
            reserve_user_var = tk.StringVar(value=current_user_id)
            ttk.Entry(borrower_frame, textvariable=reserve_user_var, width=30).pack(anchor='w', padx=10, pady=(5, 10))
        else:
            reserve_user_var = tk.StringVar(value=current_user_id)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        def create_reservation():
            uid = reserve_user_var.get().strip()
            if not uid:
                messagebox.showwarning(_("common.warning"), "Please enter a user ID")
                return

            try:
                success = self.create_reservation_database(book_id, uid)
                if success:
                    messagebox.showinfo(_("common.success"),
                                        f"Reservation created successfully!\n\n"
                                        f"Title: {book_details.get('title')}\n"
                                        f"User: {uid}")
                    dialog.destroy()
                    # Refresh book details
                    self.show_book_details(book_id)
                else:
                    pass  # Error already shown by create_reservation_database
            except (sqlite3.Error, DatabaseError, tk.TclError) as e:
                messagebox.showerror(_("common.error"), f"Reservation error: {str(e)}")

        reserve_btn = ttk.Button(button_frame, text="Reserve", command=create_reservation)
        if has_existing:
            reserve_btn.config(state=tk.DISABLED)
        reserve_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to open reserve dialog: {str(e)}")

def edit_book_dialog(self, book_id):
    """Edit book dialog opened from book details view"""
    try:
        if not self.check_permission('manage_books'):
            return

        # Get current book details
        book_details = self.get_book_details(book_id)
        if not book_details:
            messagebox.showerror(_("common.error"), "Book not found")
            return

        dialog = tk.Toplevel(self.master)
        dialog.title(f"Edit Book - {book_id}")
        dialog.geometry("600x700")
        dialog.transient(self.master)
        dialog.grab_set()

        # Create scrollable form
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        form_outer = ttk.Frame(canvas)

        form_outer.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=form_outer, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        form_frame = ttk.Frame(form_outer)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(form_frame, text=f"Edit Book: {book_id}", style='Title.TLabel').grid(
            row=0, column=0, columnspan=2, pady=(0, 15), sticky='w')

        fields = {}
        field_defs = [
            ('title', 'Title'),
            ('author', 'Author'),
            ('isbn', 'ISBN'),
            ('publisher', 'Publisher'),
            ('category', 'Category'),
            ('year_published', 'Year Published'),
            ('location', 'Location'),
            ('reading_level', 'Reading Level'),
            ('status', 'Status'),
        ]

        for i, (field_key, field_label) in enumerate(field_defs, start=1):
            ttk.Label(form_frame, text=f"{field_label}:").grid(row=i, column=0, sticky='w', pady=5, padx=5)

            if field_key == 'status':
                fields[field_key] = tk.StringVar(value=book_details.get(field_key, ''))
                ttk.Combobox(form_frame, textvariable=fields[field_key],
                             values=['available', 'checked_out', 'reserved', 'maintenance', 'damaged'],
                             width=37).grid(row=i, column=1, pady=5, padx=5)
            elif field_key == 'category':
                fields[field_key] = tk.StringVar(value=book_details.get(field_key, ''))
                ttk.Combobox(form_frame, textvariable=fields[field_key],
                             values=['Fiction', 'Non-Fiction', 'Science', 'History', 'Computer Science',
                                     'Mathematics', 'Philosophy', 'Psychology', 'Business', 'Biography', 'General'],
                             width=37).grid(row=i, column=1, pady=5, padx=5)
            elif field_key == 'reading_level':
                fields[field_key] = tk.StringVar(value=book_details.get(field_key, ''))
                ttk.Combobox(form_frame, textvariable=fields[field_key],
                             values=['Elementary', 'Middle School', 'High School', 'College', 'Unknown'],
                             width=37).grid(row=i, column=1, pady=5, padx=5)
            else:
                fields[field_key] = tk.StringVar(value=str(book_details.get(field_key, '') or ''))
                ttk.Entry(form_frame, textvariable=fields[field_key], width=40).grid(row=i, column=1, pady=5, padx=5)

        # Description
        desc_row = len(field_defs) + 1
        ttk.Label(form_frame, text="Description:").grid(row=desc_row, column=0, sticky='nw', pady=5, padx=5)
        desc_text = tk.Text(form_frame, height=4, width=40)
        desc_text.grid(row=desc_row, column=1, pady=5, padx=5)
        if book_details.get('description'):
            desc_text.insert(tk.END, book_details['description'])

        # Tags
        tags_row = desc_row + 1
        ttk.Label(form_frame, text="Tags:").grid(row=tags_row, column=0, sticky='w', pady=5, padx=5)
        tags_var = tk.StringVar(value=str(book_details.get('tags', '') or ''))
        ttk.Entry(form_frame, textvariable=tags_var, width=40).grid(row=tags_row, column=1, pady=5, padx=5)

        # Buttons
        btn_row = tags_row + 1
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=btn_row, column=0, columnspan=2, pady=20)

        def save_changes():
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                description = desc_text.get("1.0", tk.END).strip()
                tags = tags_var.get().strip()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    UPDATE books
                    SET title = ?, author = ?, isbn = ?, publisher = ?,
                        category = ?, year_published = ?, location = ?,
                        reading_level = ?, status = ?, description = ?,
                        tags = ?, last_updated = ?
                    WHERE book_id = ?
                ''', (
                    fields['title'].get(),
                    fields['author'].get(),
                    fields['isbn'].get(),
                    fields['publisher'].get(),
                    fields['category'].get(),
                    fields['year_published'].get() or None,
                    fields['location'].get(),
                    fields['reading_level'].get(),
                    fields['status'].get(),
                    description,
                    tags,
                    now,
                    book_id
                ))

                conn.commit()
                conn.close()

                # Log the edit
                if ORIGINAL_LIBRARY_AVAILABLE:
                    try:
                        log_audit_event(get_current_user_id(), f"GUI: Updated book {book_id}", "books", book_id)
                    except (sqlite3.Error, DatabaseError):
                        pass

                messagebox.showinfo(_("common.success"), "Book updated successfully!")
                dialog.destroy()
                # Refresh book details view
                self.show_book_details(book_id)
                # Refresh books table if visible
                if hasattr(self, 'books_tree'):
                    try:
                        self.load_books_data()
                    except tk.TclError:
                        pass

            except (sqlite3.Error, DatabaseError, tk.TclError) as e:
                messagebox.showerror(_("common.error"), f"Update failed: {str(e)}")

        ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to open edit dialog: {str(e)}")

def show_book_reviews(self, book_id):
    """Show reviews for a specific book and allow adding new reviews"""
    try:
        # Get book details
        book_details = self.get_book_details(book_id)
        if not book_details:
            messagebox.showerror(_("common.error"), "Book not found")
            return

        dialog = tk.Toplevel(self.master)
        dialog.title(f"Reviews - {book_details.get('title', book_id)}")
        dialog.geometry("700x600")
        dialog.transient(self.master)

        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Book header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=book_details.get('title', 'Unknown'),
                  style='Title.TLabel').pack(anchor='w')
        ttk.Label(header_frame, text=f"by {book_details.get('author', 'Unknown')}").pack(anchor='w')

        # Average rating display
        avg_label = ttk.Label(header_frame, text="Loading ratings...")
        avg_label.pack(anchor='w', pady=(5, 0))

        # Reviews list
        reviews_frame = ttk.LabelFrame(main_frame, text="Reviews")
        reviews_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('Reviewer', 'Rating', 'Date', 'Status')
        reviews_tree = ttk.Treeview(reviews_frame, columns=columns, show='headings', height=8)

        reviews_tree.heading('Reviewer', text='Reviewer')
        reviews_tree.heading('Rating', text='Rating')
        reviews_tree.heading('Date', text='Date')
        reviews_tree.heading('Status', text='Status')
        reviews_tree.column('Reviewer', width=150)
        reviews_tree.column('Rating', width=120)
        reviews_tree.column('Date', width=100)
        reviews_tree.column('Status', width=80)

        reviews_scrollbar = ttk.Scrollbar(reviews_frame, orient=tk.VERTICAL, command=reviews_tree.yview)
        reviews_tree.configure(yscrollcommand=reviews_scrollbar.set)

        reviews_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        reviews_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Review text display
        review_detail_frame = ttk.LabelFrame(main_frame, text="Review Text")
        review_detail_frame.pack(fill=tk.X, pady=(0, 10))

        review_detail_text = tk.Text(review_detail_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        review_detail_text.pack(fill=tk.X, padx=5, pady=5)

        review_data = []

        def on_review_select(event=None):
            selection = reviews_tree.selection()
            if not selection:
                return
            idx = reviews_tree.index(selection[0])
            if idx < len(review_data) and review_data[idx].get('review_text'):
                review_detail_text.config(state=tk.NORMAL)
                review_detail_text.delete("1.0", tk.END)
                review_detail_text.insert(tk.END, review_data[idx]['review_text'])
                review_detail_text.config(state=tk.DISABLED)

        reviews_tree.bind('<<TreeviewSelect>>', on_review_select)

        # Load reviews
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT user_id, rating, review_text, review_date, status
                    FROM book_reviews
                    WHERE book_id = ?
                    ORDER BY review_date DESC
                ''', (book_id,))

                reviews = cursor.fetchall()

                # Calculate average
                cursor.execute('''
                    SELECT AVG(rating), COUNT(*) FROM book_reviews
                    WHERE book_id = ?
                ''', (book_id,))
                avg_result = cursor.fetchone()
                conn.close()

                avg_rating = avg_result[0] if avg_result and avg_result[0] else 0
                total_reviews = avg_result[1] if avg_result else 0

                if total_reviews > 0:
                    stars = int(round(avg_rating))
                    star_display = "\u2605" * stars + "\u2606" * (5 - stars)
                    avg_label.config(text=f"Average Rating: {star_display} ({avg_rating:.1f}/5) - {total_reviews} review(s)")
                else:
                    avg_label.config(text="No reviews yet")

                for rev in reviews:
                    user_id, rating, review_text_val, review_date, status = rev
                    stars = "\u2605" * rating + "\u2606" * (5 - rating)
                    reviews_tree.insert('', 'end', values=(
                        user_id, stars, review_date[:10] if review_date else 'N/A', status
                    ))
                    review_data.append({
                        'user_id': user_id,
                        'rating': rating,
                        'review_text': review_text_val,
                        'review_date': review_date,
                        'status': status
                    })
            else:
                avg_label.config(text="Reviews not available in demo mode")

        except (sqlite3.Error, DatabaseError) as e:
            avg_label.config(text=f"Error loading reviews: {str(e)}")

        # Add review section
        add_frame = ttk.LabelFrame(main_frame, text="Write a Review")
        add_frame.pack(fill=tk.X, pady=(0, 10))

        rating_row = ttk.Frame(add_frame)
        rating_row.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(rating_row, text="Your Rating:").pack(side=tk.LEFT)
        new_rating_var = tk.StringVar(value="5")
        for i in range(1, 6):
            ttk.Radiobutton(rating_row, text=f"{i}", variable=new_rating_var, value=str(i)).pack(side=tk.LEFT, padx=3)

        ttk.Label(add_frame, text="Your Review:").pack(anchor='w', padx=10)
        new_review_text = tk.Text(add_frame, height=3, width=60)
        new_review_text.pack(fill=tk.X, padx=10, pady=(0, 5))

        def submit_new_review():
            review_content = new_review_text.get("1.0", tk.END).strip()
            rating = int(new_rating_var.get())

            if not review_content:
                messagebox.showwarning(_("common.warning"), "Please write a review")
                return

            try:
                if ORIGINAL_LIBRARY_AVAILABLE:
                    success = self.submit_review_database(book_id, rating, review_content)
                    if success:
                        messagebox.showinfo(_("common.success"), "Review submitted successfully!")
                        dialog.destroy()
                        # Reopen to show updated reviews
                        self.show_book_reviews(book_id)
                else:
                    messagebox.showinfo(_("common.demo"), "Review submitted (demo mode)")
                    dialog.destroy()

            except (sqlite3.Error, DatabaseError, tk.TclError) as e:
                messagebox.showerror(_("common.error"), f"Error submitting review: {str(e)}")

        review_btn_frame = ttk.Frame(add_frame)
        review_btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(review_btn_frame, text="Submit Review", command=submit_new_review).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=dialog.destroy).pack(pady=5)

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to open reviews: {str(e)}")

