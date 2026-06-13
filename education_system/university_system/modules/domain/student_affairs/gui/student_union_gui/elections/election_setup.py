import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core import paths
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
from education_system.university_system.core.i18n import (
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


class CampaignMaterialsDialog:
    """Dialog for submitting campaign materials"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.elections.submit_campaign_materials"))
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=_t("student_union.elections.submit_campaign_materials"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Material type
        ttk.Label(main_frame, text=_t("student_union.elections.material_type")).pack(anchor='w', pady=(0, 5))
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, state='readonly', width=30)
        type_combo['values'] = (_t("student_union.elections.mat_poster"), _t("student_union.elections.mat_video"), _t("student_union.elections.mat_manifesto"), _t("student_union.elections.mat_social_media"), _t("student_union.elections.mat_other"))
        type_combo.pack(fill='x', pady=(0, 15))
        type_combo.current(0)

        # Title
        ttk.Label(main_frame, text=_t("student_union.elections.title_label")).pack(anchor='w', pady=(0, 5))
        self.title_entry = ttk.Entry(main_frame, width=50)
        self.title_entry.pack(fill='x', pady=(0, 15))

        # Description
        ttk.Label(main_frame, text=_t("student_union.elections.description_label")).pack(anchor='w', pady=(0, 5))
        self.description_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
        self.description_text.pack(fill='both', expand=True, pady=(0, 15))

        # File upload (simulated)
        ttk.Label(main_frame, text=_t("student_union.elections.file_path_or_url")).pack(anchor='w', pady=(0, 5))
        self.file_entry = ttk.Entry(main_frame, width=50)
        self.file_entry.pack(fill='x', pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t("common.submit"), command=self.submit_material).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side='left')

    def submit_material(self):
        title = self.title_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()
        file_path = self.file_entry.get().strip()

        if not all([self.type_var.get(), title, description]):
            messagebox.showwarning(_t("common.warning"), _t("student_union.elections.fill_required_fields"))
            return

        messagebox.showinfo(_t("common.success"), _t("student_union.elections.material_submitted_for_approval"))
        self.dialog.destroy()



class SetupElectionDialog:
    """Dialog for setting up a new election (Admin only)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.elections.setup_new_election"))
        self.dialog.geometry("800x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=_t("student_union.elections.setup_new_election"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Scrollable form
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        # Position
        ttk.Label(scrollable_frame, text=_t("student_union.elections.position_title")).grid(row=0, column=0, sticky='w', pady=5)
        self.position_entry = ttk.Entry(scrollable_frame, width=40)
        self.position_entry.grid(row=0, column=1, pady=5, sticky='ew')

        # Department
        ttk.Label(scrollable_frame, text=_t("student_union.elections.department_optional")).grid(row=1, column=0, sticky='w', pady=5)
        self.department_entry = ttk.Entry(scrollable_frame, width=40)
        self.department_entry.grid(row=1, column=1, pady=5, sticky='ew')

        # Nomination period
        ttk.Label(scrollable_frame, text=_t("student_union.elections.nomination_start")).grid(row=2, column=0, sticky='w', pady=5)
        self.nom_start_entry = ttk.Entry(scrollable_frame, width=40)
        self.nom_start_entry.grid(row=2, column=1, pady=5, sticky='ew')
        self.nom_start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Label(scrollable_frame, text=_t("student_union.elections.nomination_end")).grid(row=3, column=0, sticky='w', pady=5)
        self.nom_end_entry = ttk.Entry(scrollable_frame, width=40)
        self.nom_end_entry.grid(row=3, column=1, pady=5, sticky='ew')

        # Voting period
        ttk.Label(scrollable_frame, text=_t("student_union.elections.voting_start")).grid(row=4, column=0, sticky='w', pady=5)
        self.vote_start_entry = ttk.Entry(scrollable_frame, width=40)
        self.vote_start_entry.grid(row=4, column=1, pady=5, sticky='ew')

        ttk.Label(scrollable_frame, text=_t("student_union.elections.voting_end")).grid(row=5, column=0, sticky='w', pady=5)
        self.vote_end_entry = ttk.Entry(scrollable_frame, width=40)
        self.vote_end_entry.grid(row=5, column=1, pady=5, sticky='ew')

        # Eligibility
        ttk.Label(scrollable_frame, text=_t("student_union.elections.voter_eligibility_rules")).grid(row=6, column=0, sticky='w', pady=5)
        self.eligibility_text = scrolledtext.ScrolledText(scrollable_frame, height=5, width=40, wrap=tk.WORD)
        self.eligibility_text.grid(row=6, column=1, pady=5, sticky='ew')

        # Campaign guidelines
        ttk.Label(scrollable_frame, text=_t("student_union.elections.campaign_guidelines")).grid(row=7, column=0, sticky='w', pady=5)
        self.guidelines_text = scrolledtext.ScrolledText(scrollable_frame, height=5, width=40, wrap=tk.WORD)
        self.guidelines_text.grid(row=7, column=1, pady=5, sticky='ew')

        scrollable_frame.columnconfigure(1, weight=1)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text=_t("student_union.elections.create_election"), command=self.create_election).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side='left')

    def create_election(self):
        position = self.position_entry.get().strip()
        if not position:
            messagebox.showwarning(_t("common.warning"), _t("student_union.elections.enter_position_title"))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO union_elections (
                position, department, nomination_start, nomination_end,
                voting_start, voting_end, status
            ) VALUES (?, ?, ?, ?, ?, ?, 'upcoming')
            ''', (
                position,
                self.department_entry.get().strip() or None,
                self.nom_start_entry.get().strip(),
                self.nom_end_entry.get().strip(),
                self.vote_start_entry.get().strip(),
                self.vote_end_entry.get().strip()
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t("common.success"), _t("student_union.elections.election_created_success", position=position))
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("student_union.elections.election_create_failed", error=str(e)))


# ============================================================================
# GREEN INITIATIVES / SUSTAINABILITY DIALOGS
# ============================================================================


def open_setup_election_dialog(self):
    """Open setup election dialog (Admin only)"""
    dialog = SetupElectionDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)
# SECOND ROUND - Additional Features

