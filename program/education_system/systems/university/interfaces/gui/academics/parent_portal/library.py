from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.systems.university.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.systems.university.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from education_system.systems.university.interfaces.gui.academics.parent_portal.base import ParentPortalGUI

def show_library_interface(self):
    """Show library account interface"""
    self.clear_content()
    self.update_status("Library Account")

    title = ttk.Label(self.content_frame, text="Library Account", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if not self.children:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
        return

    # Child selection
    child_frame = ttk.Frame(self.content_frame)
    child_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(child_frame, text="Select Student:").pack(side=tk.LEFT, padx=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
    child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
    if child_combo['values']:
        child_combo.set(child_combo['values'][0])
    child_combo.pack(side=tk.LEFT, padx=5)

    # Library display frame
    library_frame = ttk.LabelFrame(self.content_frame, text="Library Information", padding=15)
    library_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_library_info():
        for widget in library_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(library_frame, text="Please select a child").pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check for library_accounts or book_loans tables
            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('library_accounts', 'book_loans')
            """)

            table_result = cursor.fetchone()
            if table_result:
                # Use library_accounts first (has more info)
                cursor.execute("""
                SELECT book_title, author, checkout_date, due_date, status
                FROM library_accounts
                WHERE student_id = ? AND status = 'checked_out'
                ORDER BY due_date
                """, (student_id,))

                checkouts = cursor.fetchall()

                # Summary
                summary_frame = ttk.LabelFrame(library_frame, text="Account Summary", padding=10)
                summary_frame.pack(fill=tk.X, pady=(0, 10))

                ttk.Label(summary_frame, text=f"Books Checked Out: {len(checkouts)}",
                         font=('Arial', 10, 'bold')).pack(anchor='w', pady=3)

                overdue_count = sum(1 for book in checkouts if book[3] < datetime.datetime.now().strftime('%Y-%m-%d'))
                if overdue_count > 0:
                    ttk.Label(summary_frame, text=f"Overdue Books: {overdue_count}",
                             font=('Arial', 10, 'bold'), foreground='red').pack(anchor='w', pady=3)

                if checkouts:
                    # Display checked out books
                    columns = ("Title", "Author", "Checked Out", "Due Date", "Status")
                    tree = ttk.Treeview(library_frame, columns=columns, show="headings", height=10)

                    for col in columns:
                        tree.heading(col, text=col)
                        tree.column(col, width=120)

                    for book in checkouts:
                        tree.insert('', tk.END, values=book)

                    scrollbar = ttk.Scrollbar(library_frame, orient=tk.VERTICAL, command=tree.yview)
                    tree.configure(yscrollcommand=scrollbar.set)

                    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                else:
                    ttk.Label(library_frame, text="No books currently checked out",
                             font=('Arial', 11)).pack(pady=50)

                ttk.Button(library_frame, text="View Reading History",
                          command=lambda: self.view_reading_history(student_id)).pack(pady=10)
            else:
                ttk.Label(library_frame, text="Library system not configured",
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(library_frame, text=f"Error loading library info: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    ttk.Button(child_frame, text="Load Library Info", command=load_library_info).pack(side=tk.LEFT, padx=5)
    load_library_info()
ParentPortalGUI.show_library_interface = show_library_interface

def view_reading_history(self, student_id):
    """View reading history"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Reading History")
    dialog.geometry("800x600")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Reading History",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Check for library_accounts table (correct table name)
        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='library_accounts'
        """)

        if not cursor.fetchone():
            ttk.Label(main_frame, text="Library system not configured.",
                     font=('Arial', 11)).pack(pady=50)
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()
            conn.close()
            return

        # Get all checkouts (current and historical) from library_accounts
        cursor.execute("""
        SELECT book_title, author, checkout_date, due_date, return_date, status
        FROM library_accounts
        WHERE student_id = ?
        ORDER BY checkout_date DESC
        """, (student_id,))

        checkouts = cursor.fetchall()
        conn.close()

        if not checkouts:
            ttk.Label(main_frame, text="No reading history found.",
                     font=('Arial', 11)).pack(pady=50)
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()
            return

        # Display reading history
        columns = ("Title", "Author", "Checked Out", "Due Date", "Returned", "Status")
        tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=15)

        tree.heading("Title", text="Title")
        tree.heading("Author", text="Author")
        tree.heading("Checked Out", text="Checked Out")
        tree.heading("Due Date", text="Due Date")
        tree.heading("Returned", text="Returned")
        tree.heading("Status", text="Status")

        tree.column("Title", width=200)
        tree.column("Author", width=150)
        tree.column("Checked Out", width=100)
        tree.column("Due Date", width=100)
        tree.column("Returned", width=100)
        tree.column("Status", width=100)

        for checkout in checkouts:
            tree.insert('', tk.END, values=checkout)

        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Summary
        summary_frame = ttk.Frame(dialog, padding=20)
        summary_frame.pack(fill=tk.X)

        total_books = len(checkouts)
        returned_books = sum(1 for c in checkouts if c[5] == 'Returned')

        ttk.Label(summary_frame, text=f"Total Books: {total_books} | Returned: {returned_books}",
                 font=('Arial', 11)).pack(side=tk.LEFT)

        ttk.Button(summary_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load reading history: {str(e)}")
        dialog.destroy()
ParentPortalGUI.view_reading_history = view_reading_history
