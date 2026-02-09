import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print(_t("student_union.finance_integration_unavailable"))

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print(_t("student_union.cli_system_unavailable"))
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

class CompetitionResultsDialog:
    """Dialog for viewing competition results"""

    def __init__(self, parent, auth_manager, competition_id):
        self.parent = parent
        self.auth = auth_manager
        self.competition_id = competition_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.competitions.results_title"))
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text=_t("student_union.competitions.results_title"), font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Results list
        list_frame = ttk.LabelFrame(main_frame, text=_t("student_union.competitions.standings"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = (_t("student_union.competitions.rank"), _t("student_union.competitions.club"), _t("student_union.competitions.participant"), _t("student_union.competitions.score"))
        self.results_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.results_tree.heading(col, text=col)
            if col in ('Club', 'Participant'):
                self.results_tree.column(col, width=200)
            else:
                self.results_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        self.results_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t("student_union.competitions.export_results"), command=self.export_results).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.close"), command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load results"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT cp.rank_position, sc.club_name,
                   s.first_name || ' ' || s.last_name, cp.score
            FROM competition_participants cp
            INNER JOIN student_clubs sc ON cp.club_id = sc.club_id
            INNER JOIN students s ON cp.student_id = s.student_id
            WHERE cp.competition_id = ?
            ORDER BY cp.rank_position, cp.score DESC
            ''', (self.competition_id,))

            results = cursor.fetchall()

            for result in results:
                self.results_tree.insert('', 'end', values=result)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("student_union.competitions.load_results_failed", error=str(e)))

    def export_results(self):
        """Export results to file"""
        messagebox.showinfo(_t("student_union.competitions.export_title"), _t("student_union.competitions.export_message"))



def view_competition_results(self):
    """View competition results"""
    try:
        dialog = CompetitionsDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


