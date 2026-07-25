"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


from education_system.systems.university.infrastructure.sql_safety import escape_like
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

def show_barcode_generator(self):
    """Show barcode generator interface"""
    if not self.check_permission('manage_books'):
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.barcode_generator"))
    dialog.geometry("500x400")
    dialog.transient(self.master)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    title_label = ttk.Label(main_frame, text="Generate Barcodes", style='Title.TLabel')
    title_label.pack(pady=(0, 20))

    # Options frame
    options_frame = ttk.LabelFrame(main_frame, text="Generation Options")
    options_frame.pack(fill=tk.X, pady=(0, 10))

    self.barcode_type = tk.StringVar(value="single")
    ttk.Radiobutton(options_frame, text="Single Book", variable=self.barcode_type, value="single").pack(anchor='w', padx=5, pady=2)
    ttk.Radiobutton(options_frame, text="Multiple Books", variable=self.barcode_type, value="multiple").pack(anchor='w', padx=5, pady=2)
    ttk.Radiobutton(options_frame, text="All Books", variable=self.barcode_type, value="all").pack(anchor='w', padx=5, pady=2)

    # Input frame
    input_frame = ttk.Frame(main_frame)
    input_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(input_frame, text="Book ID(s) (comma-separated):").pack(anchor='w')
    self.barcode_input = tk.Text(input_frame, height=3)
    self.barcode_input.pack(fill=tk.X, pady=5)

    # Generate button
    ttk.Button(main_frame, text="Generate Barcodes", command=self.generate_barcodes).pack(pady=10)

    # Results area
    results_frame = ttk.LabelFrame(main_frame, text="Results")
    results_frame.pack(fill=tk.BOTH, expand=True)

    self.barcode_results = ScrolledText(results_frame, height=8)
    self.barcode_results.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    ttk.Button(main_frame, text=_("common.close"), command=dialog.destroy).pack(pady=10)

def generate_barcodes(self):
    """Generate barcodes based on selected options"""
    try:
        barcode_type = self.barcode_type.get()
        book_ids = []

        if barcode_type == "single" or barcode_type == "multiple":
            input_text = self.barcode_input.get("1.0", tk.END).strip()
            if input_text:
                book_ids = [bid.strip() for bid in input_text.split(',') if bid.strip()]
        elif barcode_type == "all":
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT book_id FROM books ORDER BY book_id')
                    book_ids = [row[0] for row in cursor.fetchall()]
                    conn.close()
            else:
                book_ids = ["B10001", "B10002", "B10003"]  # Demo data

        if not book_ids:
            messagebox.showwarning(_("common.warning"), "Please enter book IDs or select 'All Books'")
            return

        # Generate barcode labels
        self.barcode_results.delete("1.0", tk.END)
        self.barcode_results.insert(tk.END, f"Generating barcodes for {len(book_ids)} books...\n\n")

        generated_count = 0

        for book_id in book_ids:
            # Get book info
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT title, author, barcode FROM books WHERE book_id = ?', (book_id,))
                    book_info = cursor.fetchone()
                    conn.close()

                    if book_info:
                        title, author, barcode = book_info
                        self.barcode_results.insert(tk.END, f"Book ID: {book_id}\n")
                        self.barcode_results.insert(tk.END, f"Title: {title}\n")
                        self.barcode_results.insert(tk.END, f"Author: {author}\n")
                        self.barcode_results.insert(tk.END, f"Barcode: {barcode or 'Not generated'}\n")
                        self.barcode_results.insert(tk.END, "-" * 30 + "\n\n")
                        generated_count += 1
            else:
                # Demo mode
                self.barcode_results.insert(tk.END, f"Book ID: {book_id}\n")
                self.barcode_results.insert(tk.END, "Title: Demo Book\n")
                self.barcode_results.insert(tk.END, "Author: Demo Author\n")
                self.barcode_results.insert(tk.END, f"Barcode: LIB{book_id}\n")
                self.barcode_results.insert(tk.END, "-" * 30 + "\n\n")
                generated_count += 1

        self.barcode_results.insert(tk.END, f"✅ Generated {generated_count} barcode labels\n")

        # Log the action
        log_audit_event(get_current_user_id(),
                       f"Generated {generated_count} barcode labels",
                       "books")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Error generating barcodes: {str(e)}")

def show_barcode_scanner(self):
    """Show barcode scanner interface"""
    scanner_dialog = tk.Toplevel(self.master)
    scanner_dialog.title(_("library.dialogs.barcode_scanner"))
    scanner_dialog.geometry("400x300")
    scanner_dialog.transient(self.master)

    main_frame = ttk.Frame(scanner_dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    title_label = ttk.Label(main_frame, text="Barcode Scanner", style='Title.TLabel')
    title_label.pack(pady=(0, 20))

    # Scanner input
    ttk.Label(main_frame, text="Scan or Enter Barcode:").pack(anchor='w', pady=(0, 5))
    self.barcode_var = tk.StringVar()
    barcode_entry = ttk.Entry(main_frame, textvariable=self.barcode_var, width=40, font=('Courier', 12))
    barcode_entry.pack(pady=(0, 10))

    # Result display
    result_frame = ttk.LabelFrame(main_frame, text="Scan Result")
    result_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    self.barcode_result = tk.Text(result_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
    self.barcode_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Action buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)

    ttk.Button(button_frame, text="Process Scan", command=self.process_barcode_scan).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.clear"), command=self.clear_barcode_scan).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=scanner_dialog.destroy).pack(side=tk.LEFT, padx=5)

    # Focus on barcode entry
    barcode_entry.focus()
    barcode_entry.bind('<Return>', lambda e: self.process_barcode_scan())

def process_barcode_scan(self):
    """Process barcode scan"""
    barcode = self.barcode_var.get().strip()

    if not barcode:
        messagebox.showwarning(_("common.warning"), "Please enter a barcode")
        return

    self.barcode_result.config(state=tk.NORMAL)
    self.barcode_result.delete("1.0", tk.END)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            # Use original barcode processing function
            result = process_scanned_barcode(barcode)

            if result:
                if result['type'] == 'book':
                    result_text = "📚 BOOK FOUND\n\n"
                    result_text += f"Book ID: {result['id']}\n"
                    result_text += f"Title: {result['title']}\n"
                    result_text += f"Author: {result['author']}\n"
                    result_text += f"Status: {result['status']}\n"
                    result_text += f"Barcode: {result['barcode']}\n\n"
                    result_text += "Actions available:\n"
                    result_text += "• View Details\n"
                    if result['status'] == 'available':
                        result_text += "• Checkout Book\n"
                    result_text += "• Reserve Book\n"

                elif result['type'] == 'user':
                    result_text = "👤 USER FOUND\n\n"
                    result_text += f"User ID: {result['id']}\n"
                    result_text += f"Name: {result['name']}\n"
                    result_text += f"Barcode: {result['barcode']}\n\n"
                    result_text += "Actions available:\n"
                    result_text += "• View User History\n"
                    result_text += "• Checkout Book to User\n"
                    result_text += "• View Active Loans\n"

                self.barcode_result.insert(tk.END, result_text)
            else:
                self.barcode_result.insert(tk.END, f"❌ NO MATCH FOUND\n\nBarcode: {barcode}\n\nThis barcode was not found in the system.")
        else:
            # Demo mode
            self.barcode_result.insert(tk.END, f"📚 DEMO SCAN RESULT\n\nBarcode: {barcode}\nDemo Book: Sample Title\nStatus: Available\n\nThis is a demonstration of barcode scanning.")

    except tk.TclError as e:
        self.barcode_result.insert(tk.END, f"❌ SCAN ERROR\n\nError processing barcode: {str(e)}")

    self.barcode_result.config(state=tk.DISABLED)

def clear_barcode_scan(self):
    """Clear barcode scan"""
    self.barcode_var.set("")
    self.barcode_result.config(state=tk.NORMAL)
    self.barcode_result.delete("1.0", tk.END)
    self.barcode_result.config(state=tk.DISABLED)

def show_library_cards_generator(self):
    """Generate library cards with barcodes for users"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.library_card_generator"))
    dialog.geometry("700x600")
    dialog.transient(self.master)

    ttk.Label(dialog, text="Library Card Generator", font=('Arial', 14, 'bold')).pack(pady=10)

    # User selection frame
    selection_frame = ttk.LabelFrame(dialog, text="Select User")
    selection_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(selection_frame, text="User ID or Username:").pack(side=tk.LEFT, padx=5)
    user_var = tk.StringVar()
    user_entry = ttk.Entry(selection_frame, textvariable=user_var, width=30)
    user_entry.pack(side=tk.LEFT, padx=5)

    # Card preview frame
    preview_frame = ttk.LabelFrame(dialog, text="Card Preview")
    preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    preview_canvas = tk.Canvas(preview_frame, bg='white', height=300)
    preview_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def generate_card():
        try:
            user_id = user_var.get().strip()
            if not user_id:
                messagebox.showwarning(_("common.warning"), "Please enter a user ID or username")
                return

            # Get user info
            conn = get_db_connection()
            cursor = conn.cursor()

            # Try to find user
            cursor.execute('''
                SELECT student_id, first_name, last_name, email_address, course
                FROM students WHERE student_id = ? OR email_address LIKE ?
            ''', (user_id, f"%{escape_like(user_id)}%"))

            user = cursor.fetchone()
            conn.close()

            if not user:
                messagebox.showerror(_("common.error"), "User not found")
                return

            # Clear canvas
            preview_canvas.delete('all')

            # Draw card (simplified version)
            card_width = 400
            card_height = 250
            x_offset = 50
            y_offset = 25

            # Card background
            preview_canvas.create_rectangle(x_offset, y_offset, x_offset + card_width, y_offset + card_height,
                                          fill='lightblue', outline='darkblue', width=2)

            # University name
            preview_canvas.create_text(x_offset + card_width//2, y_offset + 30,
                                     text="UNIVERSITY LIBRARY", font=('Arial', 16, 'bold'))

            # User info
            y = y_offset + 70
            preview_canvas.create_text(x_offset + 20, y, text=f"Name: {user[1]} {user[2]}",
                                     anchor='w', font=('Arial', 12))
            y += 30
            preview_canvas.create_text(x_offset + 20, y, text=f"ID: {user[0]}",
                                     anchor='w', font=('Arial', 12))
            y += 30
            preview_canvas.create_text(x_offset + 20, y, text=f"Department: {user[4] or 'N/A'}",
                                     anchor='w', font=('Arial', 12))
            y += 30

            # Barcode placeholder (simple representation)
            barcode_text = f"*{user[0]}*"
            preview_canvas.create_text(x_offset + card_width//2, y + 20,
                                     text=barcode_text, font=('Courier', 20, 'bold'))

            messagebox.showinfo(_("common.success"), "Library card generated successfully!")

        except tk.TclError as e:
            messagebox.showerror(_("common.error"), f"Card generation failed: {str(e)}")

    def save_card():
        try:
            file_path = filedialog.asksaveasfilename(
                title="Save Library Card",
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )

            if file_path:
                messagebox.showinfo("Info", "Card save functionality requires PIL/Pillow library")

        except (OSError, IOError, tk.TclError, ValueError, TypeError) as e:
            messagebox.showerror(_("common.error"), f"Save failed: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Generate Card", command=generate_card).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Save Card", command=save_card).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

def generate_library_card_gui(self):
    """Generate library card for a student"""
    card_window = tk.Toplevel(self.master)
    card_window.title("Generate Library Card")
    card_window.geometry("700x600")

    ttk.Label(card_window, text="Generate Library Card",
             font=('Arial', 14, 'bold')).pack(pady=10)

    # Student search
    search_frame = ttk.LabelFrame(card_window, text="Find Student", padding=10)
    search_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(search_frame, text="Student ID:").pack(side=tk.LEFT, padx=5)
    student_id_entry = ttk.Entry(search_frame, width=30)
    student_id_entry.pack(side=tk.LEFT, padx=5)

    # Card preview
    preview_frame = ttk.LabelFrame(card_window, text="Card Preview", padding=10)
    preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    preview_text = ScrolledText(preview_frame, height=20, width=70, font=('Courier', 10))
    preview_text.pack(fill=tk.BOTH, expand=True)

    def generate_card():
        student_id = student_id_entry.get().strip()
        if not student_id:
            messagebox.showwarning(_("common.warning"), "Please enter a student ID")
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT student_id, first_name, last_name, email_address, course
            FROM students
            WHERE student_id = ?
            ''', (student_id,))

            result = cursor.fetchone()
            if not result:
                messagebox.showwarning(_("common.warning"), f"Student ID {student_id} not found")
                conn.close()
                return

            student_id, first_name, last_name, email, program = result

            # Generate card number
            import random
            card_number = f"LC{student_id[:4]}{random.randint(1000, 9999)}"
            issue_date = datetime.now().strftime('%Y-%m-%d')
            expiry_date = (datetime.now().replace(year=datetime.now().year + 1)).strftime('%Y-%m-%d')

            card_design = f"""
╔══════════════════════════════════════════════════════════════╗
║                    UNIVERSITY LIBRARY CARD                   ║
╚══════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Name: {first_name} {last_name:<48} │
│  Student ID: {student_id:<47} │
│  Program: {program if program else 'N/A':<50} │
│                                                              │
│  Card Number: {card_number:<46} │
│  Issue Date: {issue_date:<47} │
│  Expiry Date: {expiry_date:<46} │
│                                                              │
│  This card is the property of University Library.           │
│  If found, please return to library circulation desk.       │
│                                                              │
│  [Barcode: *{card_number}*]                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Cardholder Benefits:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Borrow up to 5 books simultaneously
✓ Access to digital resources
✓ Reserve books online
✓ Participate in library events
✓ Study room booking privileges

For assistance, contact: library@university.edu
"""

            preview_text.delete('1.0', tk.END)
            preview_text.insert('1.0', card_design)

            # Store card info in database
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS library_cards (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                card_number TEXT UNIQUE,
                issue_date TEXT,
                expiry_date TEXT,
                status TEXT DEFAULT 'active'
            )
            ''')

            cursor.execute('''
            INSERT OR REPLACE INTO library_cards (student_id, card_number, issue_date, expiry_date, status)
            VALUES (?, ?, ?, ?, 'active')
            ''', (student_id, card_number, issue_date, expiry_date))

            conn.commit()
            conn.close()

            log_audit_event(get_current_user_id(), f"Generated library card for {student_id}", "library_cards")

        except (sqlite3.Error, DatabaseError) as e:
            messagebox.showerror(_("common.error"), f"Failed to generate card: {str(e)}")

    def save_card():
        content = preview_text.get('1.0', tk.END)
        if not content.strip():
            messagebox.showwarning(_("common.warning"), "No card to save. Generate a card first.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"library_card_{student_id_entry.get()}.txt"
        )

        if file_path:
            with open(file_path, 'w') as f:
                f.write(content)
            messagebox.showinfo(_("common.success"), f"Card saved to:\n{file_path}")

    # Button frame
    button_frame = ttk.Frame(card_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Generate Card", command=generate_card).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Save to File", command=save_card).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=card_window.destroy).pack(side=tk.RIGHT, padx=5)

def bulk_generate_library_cards_gui(self):
    """Bulk generate library cards for multiple students"""
    bulk_window = tk.Toplevel(self.master)
    bulk_window.title("Bulk Generate Library Cards")
    bulk_window.geometry("600x500")

    ttk.Label(bulk_window, text="Bulk Generate Library Cards",
             font=('Arial', 14, 'bold')).pack(pady=10)

    # Selection criteria
    criteria_frame = ttk.LabelFrame(bulk_window, text="Selection Criteria", padding=10)
    criteria_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(criteria_frame, text="Generate cards for:").pack(anchor=tk.W)

    selection_var = tk.StringVar(value="all")
    ttk.Radiobutton(criteria_frame, text="All students without cards", variable=selection_var, value="all").pack(anchor=tk.W)
    ttk.Radiobutton(criteria_frame, text="Specific program", variable=selection_var, value="program").pack(anchor=tk.W)

    program_frame = ttk.Frame(criteria_frame)
    program_frame.pack(fill=tk.X, pady=5)
    ttk.Label(program_frame, text="Program:").pack(side=tk.LEFT, padx=5)
    program_entry = ttk.Entry(program_frame, width=30)
    program_entry.pack(side=tk.LEFT, padx=5)

    # Results display
    results_frame = ttk.LabelFrame(bulk_window, text="Generation Results", padding=10)
    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    results_text = ScrolledText(results_frame, height=15, width=70, font=('Courier', 9))
    results_text.pack(fill=tk.BOTH, expand=True)

    def generate_bulk():
        results_text.delete('1.0', tk.END)
        results_text.insert('1.0', "Starting bulk card generation...\n\n")

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Create table if not exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS library_cards (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                card_number TEXT UNIQUE,
                issue_date TEXT,
                expiry_date TEXT,
                status TEXT DEFAULT 'active'
            )
            ''')

            # Get students without cards
            if selection_var.get() == "all":
                cursor.execute('''
                SELECT s.student_id, s.first_name, s.last_name
                FROM students s
                LEFT JOIN library_cards lc ON s.student_id = lc.student_id
                WHERE lc.card_id IS NULL
                ''')
            else:
                program = program_entry.get().strip()
                cursor.execute('''
                SELECT s.student_id, s.first_name, s.last_name
                FROM students s
                LEFT JOIN library_cards lc ON s.student_id = lc.student_id
                WHERE lc.card_id IS NULL AND s.course = ?
                ''', (program,))

            students = cursor.fetchall()

            if not students:
                results_text.insert(tk.END, "No students found without library cards.\n")
                conn.close()
                return

            results_text.insert(tk.END, f"Found {len(students)} students without cards\n\n")

            import random
            generated = 0

            for student_id, first_name, last_name in students:
                card_number = f"LC{student_id[:4]}{random.randint(1000, 9999)}"
                issue_date = datetime.now().strftime('%Y-%m-%d')
                expiry_date = (datetime.now().replace(year=datetime.now().year + 1)).strftime('%Y-%m-%d')

                cursor.execute('''
                INSERT INTO library_cards (student_id, card_number, issue_date, expiry_date, status)
                VALUES (?, ?, ?, ?, 'active')
                ''', (student_id, card_number, issue_date, expiry_date))

                results_text.insert(tk.END, f"✓ {student_id}: {first_name} {last_name} - {card_number}\n")
                generated += 1

            conn.commit()
            conn.close()

            results_text.insert(tk.END, f"\n{'='*60}\n")
            results_text.insert(tk.END, f"Successfully generated {generated} library cards!\n")

            log_audit_event(get_current_user_id(), f"Bulk generated {generated} library cards", "library_cards")

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            results_text.insert(tk.END, f"\n❌ Error: {str(e)}\n")

    # Button frame
    button_frame = ttk.Frame(bulk_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Generate Cards", command=generate_bulk).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=bulk_window.destroy).pack(side=tk.RIGHT, padx=5)

def print_library_card_gui(self):
    """Print/export library card design"""
    print_window = tk.Toplevel(self.master)
    print_window.title("Print Library Card")
    print_window.geometry("600x400")

    ttk.Label(print_window, text="Print Library Card",
             font=('Arial', 14, 'bold')).pack(pady=10)

    # Card number input
    input_frame = ttk.LabelFrame(print_window, text="Card Information", padding=10)
    input_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(input_frame, text="Card Number or Student ID:").pack(side=tk.LEFT, padx=5)
    card_input = ttk.Entry(input_frame, width=30)
    card_input.pack(side=tk.LEFT, padx=5)

    info_frame = ttk.LabelFrame(print_window, text="Export Options", padding=10)
    info_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(info_frame, text="Select export format and click Export").pack()

    def export_card():
        card_id = card_input.get().strip()
        if not card_id:
            messagebox.showwarning(_("common.warning"), "Please enter card number or student ID")
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Try to find card
            cursor.execute('''
            SELECT lc.card_number, lc.issue_date, lc.expiry_date, lc.status,
                   s.student_id, s.first_name, s.last_name, s.course
            FROM library_cards lc
            JOIN students s ON lc.student_id = s.student_id
            WHERE lc.card_number = ? OR lc.student_id = ?
            ''', (card_id, card_id))

            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showwarning(_("common.warning"), "Card not found")
                return

            card_number, issue_date, expiry_date, status, student_id, first_name, last_name, program = result

            card_text = f"""
╔══════════════════════════════════════════════════════════════╗
║                    UNIVERSITY LIBRARY CARD                   ║
╚══════════════════════════════════════════════════════════════╝

  Name: {first_name} {last_name}
  Student ID: {student_id}
  Program: {program if program else 'N/A'}

  Card Number: {card_number}
  Issue Date: {issue_date}
  Expiry Date: {expiry_date}
  Status: {status.upper()}

  [Barcode: *{card_number}*]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This card is the property of University Library.
Contact: library@university.edu
"""

            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=f"library_card_{card_number}.txt"
            )

            if file_path:
                with open(file_path, 'w') as f:
                    f.write(card_text)

                log_audit_event(get_current_user_id(), f"Exported library card {card_number}", "library_cards")
                messagebox.showinfo(_("common.success"), f"Card exported to:\n{file_path}")

        except (OSError, IOError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to export card: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(print_window)
    button_frame.pack(fill=tk.X, padx=10, pady=20)

    ttk.Button(button_frame, text="Export Card", command=export_card).pack(side=tk.LEFT, padx=5)

    def open_access_card_in_bm():
        """Cross-jump: open Building Management → Access Cards filtered
        to this card's user. Resolves the user_id for the entered card
        number / student id then writes an IPC request that the parent
        GUI's poller picks up."""
        from tkinter import messagebox
        ident = card_input.get().strip()
        if not ident:
            messagebox.showwarning(_("common.warning"),
                                   "Enter a card number or student ID first.",
                                   parent=print_window)
            return
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT student_id FROM library_cards "
                "WHERE card_number = ? OR student_id = ?",
                (ident, ident))
            row = cur.fetchone()
            conn.close()
        except Exception:
            row = None
        user_id = row[0] if row else ident
        try:
            from education_system.systems.university.interfaces.gui.academics.library._cross_links import (
                _jump,
            )
            _jump("building_mgmt", {"user_id": str(user_id)})
            messagebox.showinfo(
                "Opening…",
                "Building Management is opening — switch to it and check "
                "the Access Cards tab for this user.",
                parent=print_window)
        except Exception as exc:
            messagebox.showerror(
                _("common.error"),
                f"Could not open Building Management:\n{exc}",
                parent=print_window)

    ttk.Button(button_frame, text="🏢 View Building Access Card",
               command=open_access_card_in_bm).pack(side=tk.LEFT, padx=5)

    ttk.Button(button_frame, text=_("common.close"), command=print_window.destroy).pack(side=tk.RIGHT, padx=5)

