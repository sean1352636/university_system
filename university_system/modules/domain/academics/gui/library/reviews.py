"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import sys
from datetime import datetime, timedelta
import json
from university_system.infrastructure.database.db import sqlite3
from typing import Dict, List, Optional, Any
import logging
import urllib.request
import urllib.parse
import urllib.error

# Import custom exceptions for better error handling
from university_system.infrastructure.exceptions import (
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
    from university_system.modules.domain.academics.services.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from university_system.modules.domain.academics.services.library.menu import display_library_menu
    from university_system.modules.domain.academics.services.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from university_system.modules.domain.academics.services.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from university_system.modules.domain.academics.services.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from university_system.modules.domain.academics.services.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from university_system.modules.domain.academics.services.library.reading_lists import view_reading_list_details
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

# Import shared authentication system
try:
    from university_system.infrastructure.auth import UserAuth
    from university_system.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None

from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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
    from university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_email_as_system(*args, **kwargs):
        return False
    print("Warning: Email service not available for library finance")

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None
_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

from .base import LibraryGUI

def show_reviews(self):
    """Show reviews and ratings interface"""
    # Check permission instead of user directly
    if not self.check_permission('manage_reviews'):
        return

    self.clear_content_area()

    reviews_frame = ttk.Frame(self.notebook)
    self.notebook.add(reviews_frame, text="Reviews & Ratings")

    title_label = ttk.Label(reviews_frame, text="Book Reviews & Ratings", style='Title.TLabel')
    title_label.pack(pady=10)

    # Control frame
    control_frame = ttk.Frame(reviews_frame)
    control_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(control_frame, text="Write Review", command=self.write_review_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text="My Reviews", command=self.show_my_reviews).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text="All Reviews", command=self.show_all_reviews).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text=_("common.refresh"), command=self.refresh_reviews).pack(side=tk.LEFT, padx=5)

    # Reviews display
    reviews_display_frame = ttk.LabelFrame(reviews_frame, text="Recent Reviews")
    reviews_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # Reviews table
    columns = ('Book', 'Title', 'Reviewer', 'Rating', 'Date', 'Status')
    self.reviews_tree = ttk.Treeview(reviews_display_frame, columns=columns, show='headings', height=15)

    for col in columns:
        self.reviews_tree.heading(col, text=col)
        self.reviews_tree.column(col, width=120)

    # Scrollbar
    reviews_scrollbar = ttk.Scrollbar(reviews_display_frame, orient=tk.VERTICAL, command=self.reviews_tree.yview)
    self.reviews_tree.configure(yscrollcommand=reviews_scrollbar.set)

    self.reviews_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    reviews_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Load reviews
    self.load_reviews()

    # Bind double-click to view review
    self.reviews_tree.bind('<Double-1>', self.view_review_details)

def load_reviews(self, filter_user=None):
    """Load reviews data"""
    # Clear existing data
    for item in self.reviews_tree.get_children():
        self.reviews_tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            if filter_user:
                cursor.execute('''
                SELECT br.book_id, b.title, br.user_id, br.rating, br.review_date, br.status
                FROM book_reviews br
                JOIN books b ON br.book_id = b.book_id
                WHERE br.user_id = ?
                ORDER BY br.review_date DESC
                ''', (filter_user,))
            else:
                cursor.execute('''
                SELECT br.book_id, b.title, br.user_id, br.rating, br.review_date, br.status
                FROM book_reviews br
                JOIN books b ON br.book_id = b.book_id
                ORDER BY br.review_date DESC
                LIMIT 50
                ''')

            reviews = cursor.fetchall()
            conn.close()

            for review in reviews:
                book_id, title, user_id, rating, review_date, status = review
                stars = "★" * rating + "☆" * (5 - rating)

                self.reviews_tree.insert('', 'end', values=(
                    book_id, title[:30], user_id, stars, review_date[:10], status
                ))
        else:
            # Demo data
            demo_reviews = [
                ("B10001", "Sample Book 1", "user1", "★★★★☆", "2024-01-15", "approved"),
                ("B10002", "Sample Book 2", "user2", "★★★★★", "2024-01-14", "pending"),
            ]

            for review in demo_reviews:
                self.reviews_tree.insert('', 'end', values=review)

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Error loading reviews: {str(e)}")

def show_my_reviews(self):
    """Show only current user's reviews"""
    if ORIGINAL_LIBRARY_AVAILABLE:
        user_id = get_current_user_id()
        self.load_reviews(filter_user=user_id)
    else:
        self.load_reviews()

def show_all_reviews(self):
    """Show all reviews"""
    self.load_reviews()

def refresh_reviews(self):
    """Refresh reviews display"""
    self.load_reviews()

def write_review_dialog(self):
    """Create write review dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.write_book_review"))
    dialog.geometry("500x400")
    dialog.transient(self.master)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Book selection
    ttk.Label(main_frame, text="Book ID:").pack(anchor='w', pady=(0, 5))
    book_id_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=book_id_var, width=30).pack(anchor='w', pady=(0, 10))

    # Rating selection
    ttk.Label(main_frame, text="Rating:").pack(anchor='w', pady=(0, 5))
    rating_var = tk.StringVar(value="5")
    rating_frame = ttk.Frame(main_frame)
    rating_frame.pack(anchor='w', pady=(0, 10))

    for i in range(1, 6):
        ttk.Radiobutton(rating_frame, text=f"{i} Star{'s' if i > 1 else ''}", 
                       variable=rating_var, value=str(i)).pack(side=tk.LEFT, padx=5)

    # Review text
    ttk.Label(main_frame, text="Review:").pack(anchor='w', pady=(0, 5))
    review_text = ScrolledText(main_frame, height=8, width=50)
    review_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)

    def submit_review():
        book_id = book_id_var.get().strip()
        rating = int(rating_var.get())
        review_content = review_text.get("1.0", tk.END).strip()

        if not book_id:
            messagebox.showwarning(_("common.warning"), "Please enter a book ID")
            return

        if not review_content:
            messagebox.showwarning(_("common.warning"), "Please write a review")
            return

        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                success = self.submit_review_database(book_id, rating, review_content)
                if success:
                    messagebox.showinfo(_("common.success"), "Review submitted successfully!")
                    dialog.destroy()
                    self.refresh_reviews()
                else:
                    messagebox.showerror(_("common.error"), "Failed to submit review")
            else:
                messagebox.showinfo(_("common.demo"), f"Review for book {book_id} submitted!")
                dialog.destroy()

        except tk.TclError as e:
            messagebox.showerror(_("common.error"), f"Error submitting review: {str(e)}")

    ttk.Button(button_frame, text="Submit", command=submit_review).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

def submit_review_database(self, book_id, rating, review_text):
    """Submit review to database"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Check if book exists
        cursor.execute('SELECT title FROM books WHERE book_id = ?', (book_id,))
        if not cursor.fetchone():
            messagebox.showerror(_("common.error"), "Book not found")
            return False

        # Check if user already reviewed this book
        user_id = get_current_user_id()
        cursor.execute('SELECT review_id FROM book_reviews WHERE book_id = ? AND user_id = ?', 
                      (book_id, user_id))

        if cursor.fetchone():
            messagebox.showwarning(_("common.warning"), "You have already reviewed this book")
            return False

        # Insert review
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO book_reviews (book_id, user_id, rating, review_text, review_date, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (book_id, user_id, rating, review_text, now))

        conn.commit()
        conn.close()

        # Log the action
        log_audit_event(user_id, f"GUI: Submitted review for book {book_id}", "book_reviews")

        return True

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error submitting review: {e}")
        return False

def view_review_details(self, event=None):
    """View review details"""
    selection = self.reviews_tree.selection()
    if not selection:
        if event:  # Called from double-click
            return
        messagebox.showwarning(_("common.warning"), "Please select a review first")
        return

    # This would show detailed review information in a dialog
    messagebox.showinfo("Review Details", "Review details would be displayed here")

def rate_and_review_book_gui(self, book_id=None):
    """Rate and review a book"""
    review_window = tk.Toplevel(self.master)
    review_window.title("Rate and Review Book")
    review_window.geometry("600x500")

    ttk.Label(review_window, text="Rate and Review Book",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Book selection
    book_frame = ttk.LabelFrame(review_window, text="Book", padding=15)
    book_frame.pack(fill=tk.X, padx=10, pady=10)

    book_id_var = tk.StringVar(value=book_id or "")
    book_info_var = tk.StringVar(value="No book selected")

    ttk.Label(book_frame, text="Book ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
    ttk.Entry(book_frame, textvariable=book_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

    def lookup_book():
        bid = book_id_var.get().strip()
        if not bid:
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT title, author FROM books WHERE book_id = ?', (bid,))
            book = cursor.fetchone()

            if book:
                book_info_var.set(f"{book[0]} by {book[1]}")
            else:
                book_info_var.set("Book not found")

            conn.close()
        except (sqlite3.Error, DatabaseError) as e:
            messagebox.showerror(_("common.error"), f"Failed to lookup book: {str(e)}")

    ttk.Button(book_frame, text="Lookup", command=lookup_book).grid(row=0, column=2, padx=5)
    ttk.Label(book_frame, textvariable=book_info_var, foreground='blue').grid(
        row=1, column=0, columnspan=3, pady=10, sticky=tk.W)

    # Rating frame
    rating_frame = ttk.LabelFrame(review_window, text="Your Rating", padding=15)
    rating_frame.pack(fill=tk.X, padx=10, pady=10)

    rating_var = tk.IntVar(value=5)

    ttk.Label(rating_frame, text="Rating (1-5 stars):").pack(anchor=tk.W, pady=5)
    rating_scale = ttk.Scale(rating_frame, from_=1, to=5, variable=rating_var, orient=tk.HORIZONTAL)
    rating_scale.pack(fill=tk.X, pady=5)

    rating_label = ttk.Label(rating_frame, text="★★★★★")
    rating_label.pack(anchor=tk.W, pady=5)

    def update_rating_display(val):
        stars = int(float(val))
        rating_label.config(text="★" * stars + "☆" * (5 - stars))

    rating_scale.config(command=update_rating_display)

    # Review frame
    review_frame = ttk.LabelFrame(review_window, text="Your Review (Optional)", padding=15)
    review_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    review_text = tk.Text(review_frame, height=8, width=60)
    review_text.pack(fill=tk.BOTH, expand=True)

    def submit_review():
        bid = book_id_var.get().strip()
        if not bid:
            messagebox.showerror(_("common.error"), "Please select a book")
            return

        rating = rating_var.get()
        review = review_text.get('1.0', tk.END).strip()

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if book exists
            cursor.execute('SELECT title FROM books WHERE book_id = ?', (bid,))
            if not cursor.fetchone():
                messagebox.showerror(_("common.error"), "Book not found")
                conn.close()
                return

            user_id = get_current_user_id()

            # Check if user already reviewed
            cursor.execute('''
            SELECT review_id FROM book_reviews
            WHERE book_id = ? AND user_id = ?
            ''', (bid, user_id))

            existing = cursor.fetchone()

            review_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if existing:
                # Update existing review
                cursor.execute('''
                UPDATE book_reviews
                SET rating = ?, review_text = ?, review_date = ?, status = 'pending'
                WHERE review_id = ?
                ''', (rating, review, review_date, existing[0]))
                message = "Review updated successfully!"
            else:
                # Create new review
                cursor.execute('''
                INSERT INTO book_reviews (
                    book_id, user_id, rating, review_text, review_date, status
                ) VALUES (?, ?, ?, ?, ?, 'pending')
                ''', (bid, user_id, rating, review, review_date))
                message = "Review submitted successfully! It will be visible after moderation."

            conn.commit()
            conn.close()

            log_audit_event(user_id, f"Reviewed book {bid} ({rating} stars)", "book_reviews")

            messagebox.showinfo(_("common.success"), message)
            review_window.destroy()

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to submit review: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(review_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Submit Review", command=submit_review).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=review_window.destroy).pack(side=tk.LEFT, padx=5)

