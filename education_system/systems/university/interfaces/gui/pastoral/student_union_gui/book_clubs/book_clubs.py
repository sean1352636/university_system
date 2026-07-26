import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
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
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domain.pastoral.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class BookClubDialog:
    """Dialog for managing book club specific features"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Book Club Management")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_book_clubs()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Book Club Features", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Club selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(select_frame, text="Select Book Club:").pack(side='left', padx=(0, 10))
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(select_frame, textvariable=self.club_var, state='readonly', width=40)
        self.club_combo.pack(side='left', fill='x', expand=True)
        self.club_combo.bind('<<ComboboxSelected>>', self.on_club_selected)

        # Notebook for different sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 10))

        # Tab 1: Current Book
        current_book_frame = ttk.Frame(notebook)
        notebook.add(current_book_frame, text="Current Book")
        self.create_current_book_tab(current_book_frame)

        # Tab 2: Reading Schedule
        schedule_frame = ttk.Frame(notebook)
        notebook.add(schedule_frame, text="Reading Schedule")
        self.create_schedule_tab(schedule_frame)

        # Tab 3: Reviews
        reviews_frame = ttk.Frame(notebook)
        notebook.add(reviews_frame, text="Book Reviews")
        self.create_reviews_tab(reviews_frame)

        # Tab 4: Reading Challenge
        challenge_frame = ttk.Frame(notebook)
        notebook.add(challenge_frame, text="Reading Challenge")
        self.create_challenge_tab(challenge_frame)

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_current_book_tab(self, parent):
        # Current book display
        self.current_book_text = scrolledtext.ScrolledText(parent, height=15, wrap=tk.WORD)
        self.current_book_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Button to set new book
        ttk.Button(parent, text="Select New Book", command=self.select_new_book).pack(pady=5)

    def create_schedule_tab(self, parent):
        # Reading schedule
        self.schedule_text = scrolledtext.ScrolledText(parent, height=15, wrap=tk.WORD)
        self.schedule_text.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Button(parent, text="Update Schedule", command=self.update_schedule).pack(pady=5)

    def create_reviews_tab(self, parent):
        # Reviews list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('Book', 'Reviewer', 'Rating', 'Date')
        self.reviews_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            self.reviews_tree.heading(col, text=col)
            if col == 'Book':
                self.reviews_tree.column(col, width=200)
            else:
                self.reviews_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.reviews_tree.yview)
        self.reviews_tree.configure(yscrollcommand=scrollbar.set)

        self.reviews_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        ttk.Button(parent, text="Add Review", command=self.add_review).pack(pady=5)

    def create_challenge_tab(self, parent):
        # Challenge display
        self.challenge_text = scrolledtext.ScrolledText(parent, height=15, wrap=tk.WORD)
        self.challenge_text.pack(fill='both', expand=True, padx=10, pady=10)

        challenge_info = """READING CHALLENGE 2025

Goal: Read 12 books this year
Current Progress: 0 books

Monthly Targets:
- January: 1 book
- February: 1 book
...

Join the challenge by clicking 'Join Challenge' below!
"""
        self.challenge_text.insert(1.0, challenge_info)

        ttk.Button(parent, text="Join Challenge", command=self.join_challenge).pack(pady=5)

    def load_book_clubs(self):
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

            # Get book clubs
            cursor.execute('''
            SELECT c.club_id, c.club_name
            FROM student_clubs c
            JOIN club_members m ON c.club_id = m.club_id
            WHERE m.student_id = ? AND c.category LIKE '%book%' AND c.status = 'active'
            ORDER BY c.club_name
            ''', (student_id,))

            clubs = cursor.fetchall()

            if clubs:
                club_list = [c[1] for c in clubs]
                self.club_combo['values'] = club_list
                self.club_data = clubs
                if club_list:
                    self.club_combo.current(0)
                    self.on_club_selected()
            else:
                self.club_combo['values'] = ["No book clubs found"]

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load book clubs: {str(e)}")

    def on_club_selected(self, event=None):
        if not self.club_combo.current() >= 0 or not hasattr(self, 'club_data'):
            return

        # Load current book info
        self.current_book_text.delete(1.0, tk.END)
        self.current_book_text.insert(1.0, "CURRENT BOOK:\n\nTitle: The Great Gatsby\nAuthor: F. Scott Fitzgerald\nPages: 180\n\nDescription: A classic American novel about the American Dream...\n\nDiscussion Date: Next meeting on [Date]")

        # Load schedule
        self.schedule_text.delete(1.0, tk.END)
        self.schedule_text.insert(1.0, "READING SCHEDULE:\n\nWeek 1: Chapters 1-3\nWeek 2: Chapters 4-6\nWeek 3: Chapters 7-9\nWeek 4: Discussion & Wrap-up")

    def select_new_book(self):
        if not self.club_combo.current() >= 0 or not hasattr(self, 'club_data'):
            messagebox.showwarning("Warning", "Please select a book club first.")
            return

        selected_index = self.club_combo.current()
        club_id = self.club_data[selected_index][0]

        dialog = BookSelectionDialog(self.dialog, self.auth, club_id)
        self.dialog.wait_window(dialog.dialog)

    def update_schedule(self):
        if not self.club_combo.current() >= 0 or not hasattr(self, 'club_data'):
            messagebox.showwarning("Warning", "Please select a book club first.")
            return

        selected_index = self.club_combo.current()
        club_id = self.club_data[selected_index][0]

        dialog = ScheduleUpdateDialog(self.dialog, self.auth, club_id)
        self.dialog.wait_window(dialog.dialog)
        self.on_club_selected()  # Refresh display

    def add_review(self):
        if not self.club_combo.current() >= 0 or not hasattr(self, 'club_data'):
            messagebox.showwarning("Warning", "Please select a book club first.")
            return

        selected_index = self.club_combo.current()
        club_id = self.club_data[selected_index][0]

        dialog = BookReviewDialog(self.dialog, self.auth, club_id)
        self.dialog.wait_window(dialog.dialog)

    def join_challenge(self):
        messagebox.showinfo("Success", "You've joined the reading challenge!\n\nGood luck reaching your reading goals!")



class BookSelectionDialog:
    """Dialog for book clubs to select and vote on next book"""

    def __init__(self, parent, auth_manager, club_id):
        self.parent = parent
        self.auth = auth_manager
        self.club_id = club_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Next Book")
        self.dialog.geometry("700x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Select Next Book to Read", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Book Title
        ttk.Label(main_frame, text="Book Title:").pack(anchor='w', pady=(0, 5))
        self.title_entry = ttk.Entry(main_frame, width=60)
        self.title_entry.pack(fill='x', pady=(0, 10))

        # Author
        ttk.Label(main_frame, text="Author:").pack(anchor='w', pady=(0, 5))
        self.author_entry = ttk.Entry(main_frame, width=60)
        self.author_entry.pack(fill='x', pady=(0, 10))

        # ISBN (optional)
        ttk.Label(main_frame, text="ISBN (optional):").pack(anchor='w', pady=(0, 5))
        self.isbn_entry = ttk.Entry(main_frame, width=60)
        self.isbn_entry.pack(fill='x', pady=(0, 10))

        # Genre
        ttk.Label(main_frame, text="Genre:").pack(anchor='w', pady=(0, 5))
        self.genre_var = tk.StringVar()
        genre_combo = ttk.Combobox(main_frame, textvariable=self.genre_var, width=57)
        genre_combo['values'] = ('Fiction', 'Non-Fiction', 'Mystery', 'Science Fiction', 'Fantasy',
                                 'Biography', 'History', 'Self-Help', 'Other')
        genre_combo.pack(fill='x', pady=(0, 10))
        genre_combo.current(0)

        # Page Count
        ttk.Label(main_frame, text="Page Count:").pack(anchor='w', pady=(0, 5))
        self.pages_entry = ttk.Entry(main_frame, width=60)
        self.pages_entry.pack(fill='x', pady=(0, 10))

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(0, 5))
        self.description_text = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD)
        self.description_text.pack(fill='both', expand=True, pady=(0, 10))
        self.description_text.insert(1.0, "Brief description of the book...")

        # Proposed Discussion Date
        ttk.Label(main_frame, text="Proposed Discussion Date (YYYY-MM-DD):").pack(anchor='w', pady=(0, 5))
        self.date_entry = ttk.Entry(main_frame, width=60)
        self.date_entry.pack(fill='x', pady=(0, 15))
        default_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        self.date_entry.insert(0, default_date)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Propose Book", command=self.propose_book).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def propose_book(self):
        title = self.title_entry.get().strip()
        author = self.author_entry.get().strip()
        isbn = self.isbn_entry.get().strip()
        genre = self.genre_var.get()
        pages = self.pages_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()
        discussion_date = self.date_entry.get().strip()

        if not all([title, author, pages, discussion_date]):
            messagebox.showwarning("Warning", "Please fill in all required fields (Title, Author, Pages, Discussion Date).")
            return

        try:
            pages_int = int(pages)
            if pages_int <= 0:
                raise ValueError("Page count must be positive")
        except ValueError:
            messagebox.showwarning("Warning", "Please enter a valid page count.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS book_club_books (
                book_id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                isbn TEXT,
                genre TEXT,
                page_count INTEGER,
                description TEXT,
                discussion_date TEXT,
                proposed_by TEXT,
                proposed_date TEXT,
                status TEXT DEFAULT 'proposed',
                votes INTEGER DEFAULT 0,
                FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
            )
            ''')

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            student_id = result[0] if result else 'unknown'

            cursor.execute('''
            INSERT INTO book_club_books (
                club_id, title, author, isbn, genre, page_count, description,
                discussion_date, proposed_by, proposed_date, status, votes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', 0)
            ''', (self.club_id, title, author, isbn, genre, pages_int, description,
                  discussion_date, student_id, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Book '{title}' has been proposed!\n\nMembers can now vote on reading this book.")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to propose book: {str(e)}")



class ScheduleUpdateDialog:
    """Dialog for updating book club reading schedule"""

    def __init__(self, parent, auth_manager, club_id):
        self.parent = parent
        self.auth = auth_manager
        self.club_id = club_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Update Reading Schedule")
        self.dialog.geometry("650x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Update Reading Schedule", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Label(main_frame, text="Enter the reading schedule for your book club:",
                 font=('Arial', 10)).pack(anchor='w', pady=(0, 10))

        # Book Title Reference
        ttk.Label(main_frame, text="Book Title (reference):").pack(anchor='w', pady=(0, 5))
        self.book_entry = ttk.Entry(main_frame, width=60)
        self.book_entry.pack(fill='x', pady=(0, 10))

        # Schedule Details
        ttk.Label(main_frame, text="Reading Schedule:").pack(anchor='w', pady=(0, 5))
        self.schedule_text = scrolledtext.ScrolledText(main_frame, height=15, wrap=tk.WORD)
        self.schedule_text.pack(fill='both', expand=True, pady=(0, 10))

        # Pre-fill with template
        template = """Week 1 (Date Range): Chapters 1-3
Week 2 (Date Range): Chapters 4-6
Week 3 (Date Range): Chapters 7-9
Week 4 (Date Range): Chapters 10-12
Week 5 (Date Range): Discussion & Wrap-up

Meeting Location: [Location]
Meeting Time: [Time]

Notes:
- Please read assigned chapters before each meeting
- Come prepared with discussion questions
- Feel free to read ahead at your own pace
"""
        self.schedule_text.insert(1.0, template)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Save Schedule", command=self.save_schedule).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def save_schedule(self):
        book_title = self.book_entry.get().strip()
        schedule_content = self.schedule_text.get(1.0, tk.END).strip()

        if not all([book_title, schedule_content]):
            messagebox.showwarning("Warning", "Please fill in all fields.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS book_club_schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER,
                book_title TEXT,
                schedule_content TEXT,
                created_by TEXT,
                created_date TEXT,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
            )
            ''')

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            student_id = result[0] if result else 'unknown'

            cursor.execute('''
            INSERT INTO book_club_schedules (
                club_id, book_title, schedule_content, created_by, created_date, status
            ) VALUES (?, ?, ?, ?, ?, 'active')
            ''', (self.club_id, book_title, schedule_content, student_id, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Reading schedule has been updated!")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to save schedule: {str(e)}")



class BookReviewDialog:
    """Dialog for submitting book reviews"""

    def __init__(self, parent, auth_manager, club_id):
        self.parent = parent
        self.auth = auth_manager
        self.club_id = club_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Submit Book Review")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Submit Book Review", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Book Title
        ttk.Label(main_frame, text="Book Title:").pack(anchor='w', pady=(0, 5))
        self.title_entry = ttk.Entry(main_frame, width=60)
        self.title_entry.pack(fill='x', pady=(0, 10))

        # Author
        ttk.Label(main_frame, text="Author:").pack(anchor='w', pady=(0, 5))
        self.author_entry = ttk.Entry(main_frame, width=60)
        self.author_entry.pack(fill='x', pady=(0, 10))

        # Rating
        rating_frame = ttk.LabelFrame(main_frame, text="Your Rating")
        rating_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(rating_frame, text="Overall Rating:", font=('Arial', 10, 'bold')).pack(pady=(10, 5))

        # Star rating
        stars_frame = ttk.Frame(rating_frame)
        stars_frame.pack(pady=(0, 10))

        self.rating_var = tk.IntVar(value=5)
        for i in range(1, 6):
            ttk.Radiobutton(stars_frame, text=f"{'⭐' * i}", variable=self.rating_var, value=i).pack(side='left', padx=5)

        # Review Text
        ttk.Label(main_frame, text="Your Review:").pack(anchor='w', pady=(0, 5))
        self.review_text = scrolledtext.ScrolledText(main_frame, height=12, wrap=tk.WORD)
        self.review_text.pack(fill='both', expand=True, pady=(0, 10))
        self.review_text.insert(1.0, "Share your thoughts about the book...\n\nWhat did you like? What didn't you like? Would you recommend it to others?")

        # Would Recommend
        self.recommend_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="I would recommend this book to others",
                       variable=self.recommend_var).pack(anchor='w', pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Submit Review", command=self.submit_review).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def submit_review(self):
        title = self.title_entry.get().strip()
        author = self.author_entry.get().strip()
        rating = self.rating_var.get()
        review_content = self.review_text.get(1.0, tk.END).strip()
        recommend = self.recommend_var.get()

        if not all([title, author, review_content]):
            messagebox.showwarning("Warning", "Please fill in all fields.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS book_reviews (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER,
                book_title TEXT NOT NULL,
                author TEXT NOT NULL,
                rating INTEGER,
                review_content TEXT,
                recommend BOOLEAN,
                reviewer_id TEXT,
                review_date TEXT,
                FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
            )
            ''')

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            student_id = result[0] if result else 'unknown'

            cursor.execute('''
            INSERT INTO book_reviews (
                club_id, book_title, author, rating, review_content, recommend,
                reviewer_id, review_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (self.club_id, title, author, rating, review_content, recommend,
                  student_id, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Thank you for your review!\n\nYour review has been submitted successfully.")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to submit review: {str(e)}")


# ============================================================================
# ELECTIONS & VOTING SYSTEM DIALOGS
# ============================================================================


def manage_book_clubs(self):
    """Manage book club specific features"""
    try:
        dialog = BookClubDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


