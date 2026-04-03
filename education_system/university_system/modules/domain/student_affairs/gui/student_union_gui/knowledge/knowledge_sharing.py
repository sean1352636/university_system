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


class KnowledgeSharingDialog:
    """Dialog for knowledge sharing sessions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.knowledge.title"))
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t("student_union.knowledge.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Sessions list
        list_frame = ttk.LabelFrame(main_frame, text=_t("student_union.knowledge.upcoming_sessions"))
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = (_t("student_union.knowledge.columns.topic"), _t("student_union.knowledge.columns.presenter"), _t("student_union.knowledge.columns.date"), _t("student_union.knowledge.columns.duration"), _t("student_union.knowledge.columns.skill_level"), _t("student_union.knowledge.columns.spots"))
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Topic':
                tree.column(col, width=200)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample sessions
        sessions = [
            ("Python for Data Science", "Dr. Sarah Johnson", "2025-04-15", "2 hours", "Intermediate", "15/20"),
            ("Web Development Basics", "Mike Chen", "2025-04-18", "1.5 hours", "Beginner", "8/15"),
            ("Machine Learning 101", "Prof. David Lee", "2025-04-22", "3 hours", "Advanced", "10/12"),
            ("Git & GitHub Workshop", "Emma Wilson", "2025-04-25", "1 hour", "Beginner", "20/25")
        ]

        for session in sessions:
            tree.insert('', 'end', values=session)

        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t("student_union.knowledge.join_session"), command=self.join_session).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("student_union.knowledge.propose_session"), command=self.propose_session).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("student_union.knowledge.view_recordings"), command=self.view_recordings).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.close"), command=self.dialog.destroy).pack(side='right')

    def join_session(self):
        messagebox.showinfo(_t("common.success"), _t("student_union.knowledge.registered_for_session"))

    def propose_session(self):
        dialog = ProposeSessionDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_recordings(self):
        messagebox.showinfo(_t("student_union.knowledge.recordings"), _t("student_union.knowledge.recordings_list"))



class ProposeSessionDialog:
    """Dialog for proposing a workshop/skill-sharing session"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.knowledge.propose_workshop"))
        self.dialog.geometry("700x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=_t("student_union.knowledge.propose_workshop"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Label(main_frame, text=_t("student_union.knowledge.share_expertise"),
                 font=('Arial', 10, 'italic')).pack(pady=(0, 15))

        # Session title
        ttk.Label(main_frame, text=_t("student_union.knowledge.session_title")).pack(anchor='w', pady=(0, 5))
        self.title_entry = ttk.Entry(main_frame, width=60)
        self.title_entry.pack(fill='x', pady=(0, 10))
        self.title_entry.insert(0, "Introduction to Python Programming")

        # Category
        ttk.Label(main_frame, text=_t("student_union.knowledge.category")).pack(anchor='w', pady=(0, 5))
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(main_frame, textvariable=self.category_var, width=57)
        category_combo['values'] = ('Programming', 'Design', 'Business', 'Languages',
                                    'Music', 'Art', 'Wellness', 'Academic Skills', 'Other')
        category_combo.pack(fill='x', pady=(0, 10))
        category_combo.current(0)

        # Duration & Level
        details_frame = ttk.Frame(main_frame)
        details_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(details_frame, text=_t("student_union.knowledge.duration_hours")).grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.duration_entry = ttk.Entry(details_frame, width=10)
        self.duration_entry.grid(row=0, column=1, sticky='w', padx=(0, 30))
        self.duration_entry.insert(0, "2")

        ttk.Label(details_frame, text=_t("student_union.knowledge.level")).grid(row=0, column=2, sticky='w', padx=(0, 10))
        self.level_var = tk.StringVar(value="Beginner")
        level_combo = ttk.Combobox(details_frame, textvariable=self.level_var, width=15, state='readonly')
        level_combo['values'] = ('Beginner', 'Intermediate', 'Advanced', 'All Levels')
        level_combo.grid(row=0, column=3, sticky='w')

        # Max participants
        ttk.Label(main_frame, text=_t("student_union.knowledge.max_participants")).pack(anchor='w', pady=(0, 5))
        self.max_participants_entry = ttk.Entry(main_frame, width=60)
        self.max_participants_entry.pack(fill='x', pady=(0, 10))
        self.max_participants_entry.insert(0, "20")

        # Description
        ttk.Label(main_frame, text=_t("student_union.knowledge.session_description")).pack(anchor='w', pady=(0, 5))
        self.description_text = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD)
        self.description_text.pack(fill='both', expand=True, pady=(0, 10))
        self.description_text.insert(1.0, "Describe what participants will learn, prerequisites, and what they should bring...")

        # Prerequisites
        ttk.Label(main_frame, text=_t("student_union.knowledge.prerequisites")).pack(anchor='w', pady=(0, 5))
        self.prerequisites_entry = ttk.Entry(main_frame, width=60)
        self.prerequisites_entry.pack(fill='x', pady=(0, 15))
        self.prerequisites_entry.insert(0, "None - beginners welcome!")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t("student_union.knowledge.submit_proposal"), command=self.submit_proposal).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side='left')

    def submit_proposal(self):
        title = self.title_entry.get().strip()
        category = self.category_var.get()
        duration = self.duration_entry.get().strip()
        level = self.level_var.get()
        max_participants = self.max_participants_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()
        prerequisites = self.prerequisites_entry.get().strip()

        if not all([title, category, duration, max_participants, description]):
            messagebox.showwarning(_t("common.warning"), _t("student_union.knowledge.fill_required_fields"))
            return

        try:
            duration_float = float(duration)
            max_part_int = int(max_participants)
            if duration_float <= 0 or max_part_int <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning(_t("common.warning"), _t("student_union.knowledge.invalid_values"))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS workshop_proposals (
                proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT,
                duration_hours REAL,
                level TEXT,
                max_participants INTEGER,
                description TEXT,
                prerequisites TEXT,
                proposed_by TEXT,
                proposed_date TEXT,
                status TEXT DEFAULT 'pending'
            )
            ''')

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            proposed_by = result[0] if result else 'unknown'

            cursor.execute('''
            INSERT INTO workshop_proposals (
                title, category, duration_hours, level, max_participants,
                description, prerequisites, proposed_by, proposed_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            ''', (title, category, duration_float, level, max_part_int,
                  description, prerequisites, proposed_by, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t("common.success"), _t("student_union.knowledge.proposal_submitted", title=title))
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("student_union.knowledge.proposal_failed", error=str(e)))



def open_knowledge_sharing_dialog(self):
    """Open knowledge sharing sessions"""
    dialog = KnowledgeSharingDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)
# FOURTH ROUND - Additional Elections Features

