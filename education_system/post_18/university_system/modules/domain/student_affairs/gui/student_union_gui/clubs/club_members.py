import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
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
    from education_system.post_18.university_system.infrastructure.database.db import get_connection
    from education_system.post_18.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class ClubMemberDirectoryDialog:
    """Dialog for viewing club member directory"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.clubs.member_directory.title"))
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text=_t("student_union.clubs.member_directory.title"), font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Club selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(select_frame, text=_t("student_union.clubs.member_directory.select_club")).pack(side='left', padx=(0, 10))
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(select_frame, textvariable=self.club_var, width=40)
        self.club_combo.pack(side='left', fill='x', expand=True)
        self.club_combo.bind('<<ComboboxSelected>>', self.on_club_selected)

        # Members list
        list_frame = ttk.LabelFrame(main_frame, text=_t("student_union.clubs.member_directory.members_list"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = (_t("student_union.clubs.member_directory.col_student_id"), _t("student_union.clubs.member_directory.col_name"),
                   _t("student_union.clubs.member_directory.col_role"), _t("student_union.clubs.member_directory.col_join_date"),
                   _t("student_union.clubs.member_directory.col_email"), _t("student_union.clubs.member_directory.col_phone"))
        self.members_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.members_tree.heading(col, text=col)
            self.members_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.members_tree.yview)
        self.members_tree.configure(yscrollcommand=scrollbar.set)

        self.members_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t("student_union.clubs.member_directory.export_csv"), command=self.export_members).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("student_union.clubs.member_directory.send_group_email"), command=self.send_group_email).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.close"), command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load clubs that the user belongs to"""
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get student ID
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            # Get clubs the user is a member of
            cursor.execute('''
            SELECT DISTINCT sc.club_id, sc.club_name
            FROM student_clubs sc
            INNER JOIN club_members cm ON sc.club_id = cm.club_id
            WHERE cm.student_id = ? AND sc.status = 'active'
            ORDER BY sc.club_name
            ''', (student_id,))

            clubs = cursor.fetchall()
            self.club_data = {f"{club[1]} (ID: {club[0]})": club[0] for club in clubs}
            self.club_combo['values'] = list(self.club_data.keys())

            conn.close()

            if clubs:
                self.club_combo.current(0)
                self.on_club_selected(None)
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("student_union.clubs.member_directory.load_clubs_failed", error=str(e)))

    def on_club_selected(self, event):
        """Load members when club is selected"""
        # Clear current items
        for item in self.members_tree.get_children():
            self.members_tree.delete(item)

        selected = self.club_var.get()
        if not selected or selected not in self.club_data:
            return

        club_id = self.club_data[selected]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get members with their details
            cursor.execute('''
            SELECT cm.student_id, s.first_name || ' ' || s.last_name, cm.role, cm.join_date,
                   s.email, s.phone
            FROM club_members cm
            INNER JOIN students s ON cm.student_id = s.student_id
            WHERE cm.club_id = ?
            ORDER BY cm.role, s.last_name
            ''', (club_id,))

            members = cursor.fetchall()

            for member in members:
                self.members_tree.insert('', 'end', values=member)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("student_union.clubs.member_directory.load_members_failed", error=str(e)))

    def export_members(self):
        """Export members to CSV"""
        messagebox.showinfo(_t("common.export"), _t("student_union.clubs.member_directory.export_message"))

    def send_group_email(self):
        """Send email to all club members"""
        messagebox.showinfo(_t("student_union.clubs.member_directory.group_email"), _t("student_union.clubs.member_directory.group_email_message"))



def club_member_directory(self):
    """View club member directory"""
    try:
        dialog = ClubMemberDirectoryDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror(_t("common.error"), _t("student_union.clubs.member_directory.open_dialog_failed", error=str(e)))


