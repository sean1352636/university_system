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

def load_loan_history(self):
    """Load loan history data based on current selection"""
    # Clear existing data
    for item in self.loan_history_tree.get_children():
        self.loan_history_tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            history_type = self.loan_history_type.get()
            # The search value comes from whichever picker the mode shows;
            # loan_search_var remains the fallback for callers that set it
            # directly (the cross-link menu jumps in that way).
            picker = {"user": getattr(self, "_loan_user_picker", None),
                      "book": getattr(self, "_loan_book_picker", None)
                      }.get(history_type)
            search_term = picker.get() if picker is not None \
                else self.loan_search_var.get().strip()
            self.loan_search_var.set(search_term)

            if history_type == "all":
                cursor.execute('''
                SELECT bl.loan_id, bl.user_id, bl.book_id, b.title,
                       bl.checkout_date, bl.due_date, bl.return_date, bl.status
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                ORDER BY bl.checkout_date DESC
                LIMIT 100
                ''')
            elif history_type == "user" and search_term:
                cursor.execute('''
                SELECT bl.loan_id, bl.user_id, bl.book_id, b.title,
                       bl.checkout_date, bl.due_date, bl.return_date, bl.status
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                WHERE bl.user_id = ?
                ORDER BY bl.checkout_date DESC
                ''', (search_term,))
            elif history_type == "book" and search_term:
                cursor.execute('''
                SELECT bl.loan_id, bl.user_id, bl.book_id, b.title,
                       bl.checkout_date, bl.due_date, bl.return_date, bl.status
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                WHERE bl.book_id = ?
                ORDER BY bl.checkout_date DESC
                ''', (search_term,))
            else:
                return

            loans = cursor.fetchall()
            conn.close()

            for loan in loans:
                loan_id, user_id, book_id, title, checkout, due, returned, status = loan
                # Format dates
                checkout_date = checkout[:10] if checkout else ""
                due_date = due[:10] if due else ""
                return_date = returned[:10] if returned else ""

                self.loan_history_tree.insert('', 'end', values=(
                    loan_id, user_id, book_id, title[:30], checkout_date, due_date, return_date, status
                ))
        else:
            # Demo data
            demo_loans = [
                (1, "USER001", "B10001", "Demo Book 1", "2024-01-15", "2024-01-29", "2024-01-25", "returned"),
                (2, "USER002", "B10002", "Demo Book 2", "2024-01-20", "2024-02-03", "", "active"),
            ]

            for loan in demo_loans:
                self.loan_history_tree.insert('', 'end', values=loan)

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), _("library.error_loading_loan_history", error=str(e)))

