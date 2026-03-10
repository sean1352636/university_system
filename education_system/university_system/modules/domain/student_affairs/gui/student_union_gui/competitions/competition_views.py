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
    

class CompetitionsDialog:
    """Dialog for viewing active competitions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Active Competitions")
        self.dialog.geometry("1000x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Active Competitions", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="Filter by Type:").pack(side='left', padx=(0, 10))
        self.type_var = tk.StringVar(value="All")
        type_combo = ttk.Combobox(filter_frame, textvariable=self.type_var, width=20)
        type_combo['values'] = ('All', 'Sports', 'Academic', 'Creative', 'Community Service', 'Other')
        type_combo.pack(side='left', padx=(0, 10))
        type_combo.bind('<<ComboboxSelected>>', lambda e: self.load_data())

        ttk.Button(filter_frame, text="Register for Competition", command=self.register_competition).pack(side='right')

        # Competitions list
        list_frame = ttk.LabelFrame(main_frame, text="Available Competitions")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Type', 'Start Date', 'End Date', 'Registration Deadline', 'Participants', 'Status')
        self.competitions_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.competitions_tree.heading(col, text=col)
            if col == 'Name':
                self.competitions_tree.column(col, width=200)
            else:
                self.competitions_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.competitions_tree.yview)
        self.competitions_tree.configure(yscrollcommand=scrollbar.set)

        self.competitions_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Competition Details")
        details_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=8, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        self.competitions_tree.bind('<<TreeviewSelect>>', self.show_details)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View Results", command=self.view_results).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load competitions"""
        for item in self.competitions_tree.get_children():
            self.competitions_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            type_filter = self.type_var.get()
            if type_filter == "All":
                cursor.execute('''
                SELECT competition_id, competition_name, competition_type, start_date, end_date,
                       registration_deadline, max_participants_per_club, status
                FROM club_competitions
                WHERE status IN ('upcoming', 'active')
                ORDER BY start_date
                ''')
            else:
                cursor.execute('''
                SELECT competition_id, competition_name, competition_type, start_date, end_date,
                       registration_deadline, max_participants_per_club, status
                FROM club_competitions
                WHERE status IN ('upcoming', 'active') AND competition_type = ?
                ORDER BY start_date
                ''', (type_filter,))

            competitions = cursor.fetchall()

            for comp in competitions:
                self.competitions_tree.insert('', 'end', values=comp)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load competitions: {str(e)}")

    def show_details(self, event):
        """Show competition details"""
        selection = self.competitions_tree.selection()
        if not selection:
            return

        item = self.competitions_tree.item(selection[0])
        comp_id = item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT description, prizes, max_participants_per_club,
                   (SELECT COUNT(*) FROM competition_participants WHERE competition_id = ?) as participant_count
            FROM club_competitions
            WHERE competition_id = ?
            ''', (comp_id, comp_id))

            details = cursor.fetchone()
            conn.close()

            if details:
                details_text = f"Description: {details[0]}\n\n"
                details_text += f"Prizes: {details[1]}\n\n"
                details_text += f"Max Participants per Club: {details[2]}\n"
                details_text += f"Current Participants: {details[3]}"

                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(1.0, details_text)
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load details: {str(e)}")

    def register_competition(self):
        """Register for a competition"""
        selection = self.competitions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a competition first.")
            return

        item = self.competitions_tree.item(selection[0])
        comp_id = item['values'][0]
        comp_name = item['values'][1]

        # Open registration dialog
        dialog = CompetitionRegistrationDialog(self.dialog, self.auth, comp_id, comp_name)
        self.dialog.wait_window(dialog.dialog)

    def view_results(self):
        """View competition results"""
        selection = self.competitions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a competition first.")
            return

        item = self.competitions_tree.item(selection[0])
        comp_id = item['values'][0]

        dialog = CompetitionResultsDialog(self.dialog, self.auth, comp_id)
        self.dialog.wait_window(dialog.dialog)



class CompetitionHistoryDialog:
    """Dialog for viewing competition history"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Competition History")
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
        title_label = ttk.Label(main_frame, text="My Competition History", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # History list
        list_frame = ttk.LabelFrame(main_frame, text="Past Competitions")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Competition', 'Type', 'Club', 'Date', 'Rank', 'Score', 'Status')
        self.history_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.history_tree.heading(col, text=col)
            if col == 'Competition':
                self.history_tree.column(col, width=200)
            else:
                self.history_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Stats frame
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics")
        stats_frame.pack(fill='x', pady=(0, 10))

        self.stats_label = ttk.Label(stats_frame, text="", justify='left')
        self.stats_label.pack(padx=10, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load competition history"""
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
            SELECT cc.competition_name, cc.competition_type, sc.club_name,
                   cc.end_date, COALESCE(cp.rank_position, 'N/A'), COALESCE(cp.score, 0), cc.status
            FROM competition_participants cp
            INNER JOIN club_competitions cc ON cp.competition_id = cc.competition_id
            INNER JOIN student_clubs sc ON cp.club_id = sc.club_id
            WHERE cp.student_id = ?
            ORDER BY cc.end_date DESC
            ''', (student_id,))

            history = cursor.fetchall()

            for item in history:
                self.history_tree.insert('', 'end', values=item)

            # Calculate stats
            total_comps = len(history)
            wins = sum(1 for h in history if str(h[4]) == '1')
            avg_score = sum(float(h[5]) for h in history) / total_comps if total_comps > 0 else 0

            stats_text = f"Total Competitions: {total_comps}\n"
            stats_text += f"First Place Finishes: {wins}\n"
            stats_text += f"Average Score: {avg_score:.2f}"

            self.stats_label.config(text=stats_text)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load history: {str(e)}")




def create_competitions_tab(self):
    """Create competitions tab"""
    competitions_frame = ttk.Frame(self.notebook)
    self.notebook.add(competitions_frame, text="Competitions")
    # Left panel
    left_panel = ttk.LabelFrame(competitions_frame, text="Competition Actions")
    left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
    ttk.Button(left_panel, text="View Competitions",
              command=self.view_active_competitions).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Register Club",
              command=self.register_club_for_competition_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="View Results",
              command=self.view_competition_results).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="My Competition History",
              command=self.view_my_competition_history).pack(fill='x', pady=2)
    # Admin actions separator
    ttk.Separator(left_panel, orient='horizontal').pack(fill='x', pady=10)
    # Admin buttons (will be visible if user has admin permissions)
    ttk.Button(left_panel, text="Create New Competition (Admin)",
              command=self.create_new_competition).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Update Competition Scores (Admin)",
              command=self.update_competition_scores).pack(fill='x', pady=2)
    # Right panel
    right_panel = ttk.LabelFrame(competitions_frame, text="Competition Information")
    right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
    self.competitions_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD,
                                                      height=30, width=80)
    self.competitions_text.pack(fill='both', expand=True, padx=5, pady=5)


def view_active_competitions(self):
    """View active competitions"""
    try:
        dialog = CompetitionsDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def view_my_competition_history(self):
    """View my competition history"""
    try:
        dialog = CompetitionHistoryDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


