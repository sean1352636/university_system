"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t


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
    from education_system.systems.university.domains.library.domain.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from education_system.systems.university.domains.library.domain.library.menu import display_library_menu
    from education_system.systems.university.domains.library.domain.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from education_system.systems.university.domains.library.domain.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from education_system.systems.university.domains.library.domain.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from education_system.systems.university.domains.library.domain.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from education_system.systems.university.domains.library.domain.library.reading_lists import view_reading_list_details
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

from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
DATABASE_FILE = str(UNIVERSITY_DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
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

# Matplotlib is imported lazily by finance_shared, the one module in this
# package whose names are actually read (by the two chart dialogs under
# finance_parts/). This module carried an identical eager copy of that import
# and never used any of it — importing matplotlib.pyplot costs ~1.3s and was
# paid by anything that touched the library package at all.

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

from education_system.systems.university.domains.library.interfaces.gui.library.base import LibraryGUI

from education_system.systems.university.domains.library.interfaces.gui.library._pickers import attach_picker


def show_reviews(self):
    """Show reviews and ratings interface"""
    # Check permission instead of user directly
    if not self.check_permission('manage_reviews'):
        return

    self.clear_content_area()

    reviews_frame = ttk.Frame(self.notebook)
    self.notebook.add(reviews_frame, text=_t('gui.academics.library.reviews.tabs.reviews_ratings', default="Reviews & Ratings"))

    title_label = ttk.Label(reviews_frame, text=_t('gui.academics.library.reviews.labels.book_reviews_ratings', default="Book Reviews & Ratings"), style='Title.TLabel')
    title_label.pack(pady=10)

    # Control frame
    control_frame = ttk.Frame(reviews_frame)
    control_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(control_frame, text=_t('gui.academics.library.reviews.buttons.write_review', default="Write Review"), command=self.write_review_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text=_t('gui.academics.library.reviews.buttons.my_reviews', default="My Reviews"), command=self.show_my_reviews).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text=_t('gui.academics.library.reviews.buttons.publish_all_reviews', default="Publish All Reviews"), command=self.publish_all_reviews).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text=_t('gui.academics.library.reviews.buttons.all_reviews', default="All Reviews"), command=self.show_all_reviews).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text=_("common.refresh"), command=self.refresh_reviews).pack(side=tk.LEFT, padx=5)

    # Reviews display
    reviews_display_frame = ttk.LabelFrame(reviews_frame, text=_t('gui.academics.library.reviews.labels.recent_reviews', default="Recent Reviews"))
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
    ttk.Label(main_frame, text=_t('gui.academics.library.reviews.labels.book', default="Book:")).pack(anchor='w', pady=(0, 5))
    book_picker = attach_picker(main_frame, "book", width=48)
    book_picker.pack(anchor='w', pady=(0, 10))

    # Rating selection
    ttk.Label(main_frame, text=_t('gui.academics.library.reviews.labels.rating', default="Rating:")).pack(anchor='w', pady=(0, 5))
    rating_var = tk.StringVar(value="5")
    rating_frame = ttk.Frame(main_frame)
    rating_frame.pack(anchor='w', pady=(0, 10))

    for i in range(1, 6):
        ttk.Radiobutton(rating_frame, text=f"{i} Star{'s' if i > 1 else ''}",
                       variable=rating_var, value=str(i)).pack(side=tk.LEFT, padx=5)

    # Review text
    ttk.Label(main_frame, text=_t('gui.academics.library.reviews.labels.review_variant_2', default="Review:")).pack(anchor='w', pady=(0, 5))
    review_text = ScrolledText(main_frame, height=8, width=50)
    review_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)

    def submit_review():
        book_id = book_picker.get()
        rating = int(rating_var.get())
        review_content = review_text.get("1.0", tk.END).strip()

        if not book_id:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.library.reviews.dialogs.please_enter_a_book_id', default="Please enter a book ID"))
            return

        if not review_content:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.library.reviews.dialogs.please_write_a_review', default="Please write a review"))
            return

        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                success = self.submit_review_database(book_id, rating, review_content)
                if success:
                    messagebox.showinfo(_("common.success"), _t('gui.academics.library.reviews.dialogs.review_submitted_successfully', default="Review submitted successfully!"))
                    dialog.destroy()
                    self.refresh_reviews()
                else:
                    messagebox.showerror(_("common.error"), _t('gui.academics.library.reviews.dialogs.failed_to_submit_review', default="Failed to submit review"))
            else:
                messagebox.showinfo(_("common.demo"), f"Review for book {book_id} submitted!")
                dialog.destroy()

        except tk.TclError as e:
            messagebox.showerror(_("common.error"), f"Error submitting review: {str(e)}")

    ttk.Button(button_frame, text=_t('gui.academics.library.reviews.buttons.submit', default="Submit"), command=submit_review).pack(side=tk.LEFT, padx=5)
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
            messagebox.showerror(_("common.error"), _t('gui.academics.library.reviews.dialogs.book_not_found', default="Book not found"))
            return False

        # Check if user already reviewed this book
        user_id = get_current_user_id()
        cursor.execute('SELECT review_id FROM book_reviews WHERE book_id = ? AND user_id = ?',
                      (book_id, user_id))

        if cursor.fetchone():
            messagebox.showwarning(_("common.warning"), _t('gui.academics.library.reviews.dialogs.you_have_already_reviewed_this_book', default="You have already reviewed this book"))
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
    """View full review details in a dialog"""
    selection = self.reviews_tree.selection()
    if not selection:
        if event:
            return
        messagebox.showwarning(_("common.warning"), _t('gui.academics.library.reviews.dialogs.please_select_a_review_first', default="Please select a review first"))
        return

    item = self.reviews_tree.item(selection[0])
    book_id = item['values'][0]
    user_id = item['values'][2]

    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()
        cursor.execute('''
            SELECT br.review_id, b.title, b.author, br.user_id, br.rating,
                   br.review_text, br.review_date, br.status,
                   br.helpful_votes, br.moderated_by, br.moderation_date
            FROM book_reviews br
            JOIN books b ON br.book_id = b.book_id
            WHERE br.book_id = ? AND br.user_id = ?
            ORDER BY br.review_date DESC LIMIT 1
        ''', (book_id, user_id))
        review = cursor.fetchone()
        conn.close()

        if not review:
            messagebox.showinfo(_t('gui.academics.library.reviews.dialogs.review', default="Review"), _t('gui.academics.library.reviews.dialogs.review_details_not_found', default="Review details not found."))
            return

        review_id, title, author, uid, rating, text, date, status, votes, mod_by, mod_date = review

        dialog = tk.Toplevel(self.master)
        dialog.title(f"Review - {title}")
        dialog.geometry("550x500")
        dialog.transient(self.master)

        # Book info
        info_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.library.reviews.labels.book_information', default="Book Information"), padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(info_frame, text=f"Title: {title}").pack(anchor='w')
        ttk.Label(info_frame, text=f"Author: {author}").pack(anchor='w')
        ttk.Label(info_frame, text=f"Book ID: {book_id}").pack(anchor='w')

        # Review info
        review_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.library.reviews.labels.review', default="Review"), padding=10)
        review_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        stars = "★" * rating + "☆" * (5 - rating)
        ttk.Label(review_frame, text=f"Rating: {stars} ({rating}/5)",
                 font=('Arial', 12)).pack(anchor='w')
        ttk.Label(review_frame, text=f"Reviewer: {uid}").pack(anchor='w')
        ttk.Label(review_frame, text=f"Date: {date}").pack(anchor='w')
        ttk.Label(review_frame, text=f"Status: {status}").pack(anchor='w')
        ttk.Label(review_frame, text=f"Helpful votes: {votes or 0}").pack(anchor='w')

        ttk.Label(review_frame, text=_t('gui.academics.library.reviews.labels.review_text', default="Review Text:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))

        import tkinter.scrolledtext as st
        review_text_widget = st.ScrolledText(review_frame, height=8, wrap=tk.WORD)
        review_text_widget.pack(fill=tk.BOTH, expand=True)
        review_text_widget.insert('1.0', text or '(No review text)')
        review_text_widget.config(state='disabled')

        if mod_by:
            ttk.Label(review_frame, text=f"Moderated by: {mod_by} ({mod_date or ''})").pack(anchor='w', pady=(5, 0))

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def publish_review():
            try:
                c = get_db_connection()
                cur = c.cursor()
                cur.execute("UPDATE book_reviews SET status = 'published' WHERE review_id = ?", (review_id,))
                c.commit()
                c.close()
                messagebox.showinfo(_t('gui.academics.library.reviews.dialogs.success', default="Success"), _t('gui.academics.library.reviews.dialogs.review_published', default="Review published!"))
                dialog.destroy()
                self.load_reviews()
            except Exception as e:
                messagebox.showerror(_t('gui.academics.library.reviews.dialogs.error', default="Error"), f"Failed to publish: {e}")

        if status != 'published':
            ttk.Button(btn_frame, text=_t('gui.academics.library.reviews.buttons.publish_review', default="Publish Review"), command=publish_review).pack(side='left', padx=5)

        ttk.Button(btn_frame, text=_t('gui.academics.library.reviews.buttons.close', default="Close"), command=dialog.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror(_t('gui.academics.library.reviews.dialogs.error', default="Error"), f"Failed to load review: {e}")


def publish_all_reviews(self):
    """Set all pending reviews to published"""
    try:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        cursor.execute("UPDATE book_reviews SET status = 'published' WHERE status != 'published'")
        count = cursor.rowcount
        conn.commit()
        conn.close()
        messagebox.showinfo(_t('gui.academics.library.reviews.dialogs.reviews_published', default="Reviews Published"), f"Published {count} review(s).")
        self.load_reviews()
    except Exception as e:
        messagebox.showerror(_t('gui.academics.library.reviews.dialogs.error', default="Error"), f"Failed to publish reviews: {e}")

def rate_and_review_book_gui(self, book_id=None):
    """Rate and review a book"""
    review_window = tk.Toplevel(self.master)
    review_window.title(_t('gui.academics.library.reviews.windows.rate_and_review_book', default="Rate and Review Book"))
    review_window.geometry("600x500")

    ttk.Label(review_window, text=_t('gui.academics.library.reviews.labels.rate_and_review_book', default="Rate and Review Book"),
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Book selection
    book_frame = ttk.LabelFrame(review_window, text=_t('gui.academics.library.reviews.labels.book', default="Book"), padding=15)
    book_frame.pack(fill=tk.X, padx=10, pady=10)

    book_id_var = tk.StringVar(value=book_id or "")
    book_info_var = tk.StringVar(value=_t('gui.academics.library.reviews.values.no_book_selected', default="No book selected"))

    ttk.Label(book_frame, text=_t('gui.academics.library.reviews.labels.book', default="Book:")).grid(row=0, column=0, sticky=tk.W, pady=5)

    # Pick the book from the catalogue rather than typing its ID: the IDs
    # are opaque codes, and a typo here just produced "Book not found".
    book_picker = attach_picker(book_frame, "book", width=44)
    book_picker.grid(row=0, column=1, padx=10, pady=5)
    if book_id:
        book_picker.set(book_id)

    def lookup_book():
        bid = book_picker.get()
        book_id_var.set(bid)
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

    book_picker.combo.bind("<<ComboboxSelected>>", lambda _e: lookup_book(), add="+")
    ttk.Button(book_frame, text=_t('gui.academics.library.reviews.buttons.lookup', default="Lookup"), command=lookup_book).grid(row=0, column=2, padx=5)
    ttk.Label(book_frame, textvariable=book_info_var, foreground='blue').grid(
        row=1, column=0, columnspan=3, pady=10, sticky=tk.W)

    # Rating frame
    rating_frame = ttk.LabelFrame(review_window, text=_t('gui.academics.library.reviews.labels.your_rating', default="Your Rating"), padding=15)
    rating_frame.pack(fill=tk.X, padx=10, pady=10)

    rating_var = tk.IntVar(value=5)

    ttk.Label(rating_frame, text=_t('gui.academics.library.reviews.labels.rating_1_5_stars', default="Rating (1-5 stars):")).pack(anchor=tk.W, pady=5)
    rating_scale = ttk.Scale(rating_frame, from_=1, to=5, variable=rating_var, orient=tk.HORIZONTAL)
    rating_scale.pack(fill=tk.X, pady=5)

    rating_label = ttk.Label(rating_frame, text="★★★★★")
    rating_label.pack(anchor=tk.W, pady=5)

    def update_rating_display(val):
        stars = int(float(val))
        rating_label.config(text="★" * stars + "☆" * (5 - stars))

    rating_scale.config(command=update_rating_display)

    # Review frame
    review_frame = ttk.LabelFrame(review_window, text=_t('gui.academics.library.reviews.labels.your_review_optional', default="Your Review (Optional)"), padding=15)
    review_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    review_text = tk.Text(review_frame, height=8, width=60)
    review_text.pack(fill=tk.BOTH, expand=True)

    def submit_review():
        bid = book_picker.get()
        book_id_var.set(bid)
        if not bid:
            messagebox.showerror(_("common.error"), _t('gui.academics.library.reviews.dialogs.please_select_a_book', default="Please select a book"))
            return

        rating = rating_var.get()
        review = review_text.get('1.0', tk.END).strip()

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if book exists
            cursor.execute('SELECT title FROM books WHERE book_id = ?', (bid,))
            if not cursor.fetchone():
                messagebox.showerror(_("common.error"), _t('gui.academics.library.reviews.dialogs.book_not_found', default="Book not found"))
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

    ttk.Button(button_frame, text=_t('gui.academics.library.reviews.buttons.submit_review', default="Submit Review"), command=submit_review).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=review_window.destroy).pack(side=tk.LEFT, padx=5)

