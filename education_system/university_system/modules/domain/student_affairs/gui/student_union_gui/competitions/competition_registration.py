import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
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
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class CompetitionRegistrationDialog:
    """Dialog for registering for a competition"""

    def __init__(self, parent, auth_manager, competition_id, competition_name):
        self.parent = parent
        self.auth = auth_manager
        self.competition_id = competition_id
        self.competition_name = competition_name

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.competitions.register_title"))
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text=_t("student_union.competitions.register_for", name=self.competition_name),
                               font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 10))

        # Club selection
        ttk.Label(main_frame, text=_t("student_union.competitions.select_club")).pack(anchor='w', pady=(0, 5))
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(main_frame, textvariable=self.club_var, width=50)
        self.club_combo.pack(fill='x', pady=(0, 10))

        # Team members
        ttk.Label(main_frame, text=_t("student_union.competitions.team_members_label")).pack(anchor='w', pady=(0, 5))
        self.members_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
        self.members_text.pack(fill='both', expand=True, pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t("common.register"), command=self.register).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side='left')

    def load_data(self):
        """Load user's clubs"""
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
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("student_union.competitions.failed_load_clubs", error=str(e)))

    def register(self):
        """Register for competition"""
        selected_club = self.club_var.get()
        if not selected_club or selected_club not in self.club_data:
            messagebox.showwarning(_t("common.warning"), _t("student_union.competitions.please_select_club"))
            return

        club_id = self.club_data[selected_club]
        members = self.members_text.get(1.0, tk.END).strip().split('\n')
        members = [m.strip() for m in members if m.strip()]

        if not members:
            messagebox.showwarning(_t("common.warning"), _t("student_union.competitions.please_add_member"))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Register each team member
            for member_id in members:
                cursor.execute('''
                INSERT INTO competition_participants (competition_id, club_id, student_id, registration_date)
                VALUES (?, ?, ?, ?)
                ''', (self.competition_id, club_id, member_id, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t("common.success"), _t("student_union.competitions.registration_success", count=len(members)))
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("student_union.competitions.failed_register", error=str(e)))



def register_club_for_competition_gui(self):
    """Register club for competition"""
    try:
        dialog = CompetitionsDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror(_t("common.error"), _t("student_union.competitions.failed_open_dialog", error=str(e)))


