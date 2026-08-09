
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system import paths
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
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
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


class CreateCompetitionDialog:
    """Dialog for creating a new inter-club competition (Admin only)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.competitions.competition_admin.windows.create_new_competition', default="Create New Competition"))
        self.dialog.geometry("700x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.create_new_competition', default="Create New Competition"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Competition Name
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.competition_name', default="Competition Name:")).pack(anchor='w', pady=(0, 5))
        self.name_entry = ttk.Entry(main_frame, width=60)
        self.name_entry.pack(fill='x', pady=(0, 10))

        # Competition Type
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.competition_type', default="Competition Type:")).pack(anchor='w', pady=(0, 5))
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=57)
        type_combo['values'] = ('Sports', 'Academic', 'Creative', 'Community Service', 'Cultural', 'Technology', 'Other')
        type_combo.pack(fill='x', pady=(0, 10))
        type_combo.current(0)

        # Description
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.description', default="Description:")).pack(anchor='w', pady=(0, 5))
        self.description_text = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD)
        self.description_text.pack(fill='x', pady=(0, 10))

        # Dates Frame
        dates_frame = ttk.Frame(main_frame)
        dates_frame.pack(fill='x', pady=(0, 10))

        # Start Date
        ttk.Label(dates_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.start_date', default="Start Date:")).grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.start_date_entry = ttk.Entry(dates_frame, width=15)
        self.start_date_entry.grid(row=0, column=1, padx=(0, 20))
        self.start_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # End Date
        ttk.Label(dates_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.end_date', default="End Date:")).grid(row=0, column=2, sticky='w', padx=(0, 10))
        self.end_date_entry = ttk.Entry(dates_frame, width=15)
        self.end_date_entry.grid(row=0, column=3)
        self.end_date_entry.insert(0, (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'))

        # Registration Deadline
        ttk.Label(dates_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.registration_deadline', default="Registration Deadline:")).grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        self.reg_deadline_entry = ttk.Entry(dates_frame, width=15)
        self.reg_deadline_entry.grid(row=1, column=1, pady=(10, 0))
        self.reg_deadline_entry.insert(0, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))

        # Max Participants
        ttk.Label(dates_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.max_participants_per_club', default="Max Participants per Club:")).grid(row=1, column=2, sticky='w', padx=(0, 10), pady=(10, 0))
        self.max_participants_entry = ttk.Entry(dates_frame, width=15)
        self.max_participants_entry.grid(row=1, column=3, pady=(10, 0))
        self.max_participants_entry.insert(0, "10")

        # Prizes
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.prizes', default="Prizes:")).pack(anchor='w', pady=(10, 5))
        self.prizes_entry = ttk.Entry(main_frame, width=60)
        self.prizes_entry.pack(fill='x', pady=(0, 10))
        self.prizes_entry.insert(0, "1st: Trophy + £500, 2nd: £300, 3rd: £100")

        # Rules
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.rules_criteria', default="Rules & Criteria:")).pack(anchor='w', pady=(0, 5))
        self.rules_text = scrolledtext.ScrolledText(main_frame, height=5, wrap=tk.WORD)
        self.rules_text.pack(fill='x', pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.buttons.create_competition', default="Create Competition"), command=self.create_competition).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side='left')

    def create_competition(self):
        name = self.name_entry.get().strip()
        comp_type = self.type_var.get()
        description = self.description_text.get(1.0, tk.END).strip()
        start_date = self.start_date_entry.get().strip()
        end_date = self.end_date_entry.get().strip()
        reg_deadline = self.reg_deadline_entry.get().strip()
        max_participants = self.max_participants_entry.get().strip()
        prizes = self.prizes_entry.get().strip()
        rules = self.rules_text.get(1.0, tk.END).strip()

        if not all([name, comp_type, description, start_date, end_date, reg_deadline]):
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.please_fill_in_all_required_fields', default="Please fill in all required fields."))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO club_competitions (
                competition_name, competition_type, description, start_date, end_date,
                registration_deadline, max_participants_per_club, prizes, rules, status, created_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'upcoming', ?)
            ''', (name, comp_type, description, start_date, end_date, reg_deadline,
                  int(max_participants), prizes, rules, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.success', default="Success"), f"Competition '{name}' created successfully!")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.error', default="Error"), f"Failed to create competition: {str(e)}")



class UpdateCompetitionScoresDialog:
    """Dialog for updating competition scores (Admin only)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.competitions.competition_admin.windows.update_competition_scores', default="Update Competition Scores"))
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_competitions()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.update_competition_scores', default="Update Competition Scores"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Competition Selection
        comp_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.select_competition', default="Select Competition"))
        comp_frame.pack(fill='x', pady=(0, 10))

        self.comp_var = tk.StringVar()
        self.comp_combo = ttk.Combobox(comp_frame, textvariable=self.comp_var, state='readonly', width=70)
        self.comp_combo.pack(padx=10, pady=10, fill='x')
        self.comp_combo.bind('<<ComboboxSelected>>', self.on_competition_selected)

        # Participants List
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.participating_clubs', default="Participating Clubs"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Club ID', 'Club Name', 'Current Score', 'Rank')
        self.participants_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.participants_tree.heading(col, text=col)
            self.participants_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.participants_tree.yview)
        self.participants_tree.configure(yscrollcommand=scrollbar.set)

        self.participants_tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side='right', fill='y', pady=10)

        # Score Update Frame
        score_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.update_score', default="Update Score"))
        score_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(score_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.new_score', default="New Score:")).pack(side='left', padx=10)
        self.score_entry = ttk.Entry(score_frame, width=15)
        self.score_entry.pack(side='left', padx=10)

        ttk.Label(score_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.labels.rank', default="Rank:")).pack(side='left', padx=(20, 10))
        self.rank_entry = ttk.Entry(score_frame, width=10)
        self.rank_entry.pack(side='left', padx=10)

        ttk.Button(score_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.buttons.update_selected', default="Update Selected"), command=self.update_score).pack(side='left', padx=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.buttons.auto_calculate_ranks', default="Auto-Calculate Ranks"), command=self.auto_calculate_ranks).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.buttons.refresh', default="Refresh"), command=self.on_competition_selected).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.competitions.competition_admin.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def load_competitions(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT competition_id, competition_name, competition_type, status
            FROM club_competitions
            WHERE status IN ('active', 'upcoming')
            ORDER BY start_date DESC
            ''')

            competitions = cursor.fetchall()

            if competitions:
                comp_list = [f"{c[1]} ({c[2]}) - {c[3]}" for c in competitions]
                self.comp_combo['values'] = comp_list
                self.comp_data = competitions
                self.comp_combo.current(0)
                self.on_competition_selected()

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.error', default="Error"), f"Failed to load competitions: {str(e)}")

    def on_competition_selected(self, event=None):
        if not self.comp_combo.current() >= 0:
            return

        for item in self.participants_tree.get_children():
            self.participants_tree.delete(item)

        try:
            selected_index = self.comp_combo.current()
            comp_id = self.comp_data[selected_index][0]

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT DISTINCT c.club_id, c.club_name,
                       COALESCE(AVG(cp.score), 0) as avg_score,
                       MIN(cp.rank_position) as rank_pos
                FROM student_clubs c
                LEFT JOIN competition_participants cp ON c.club_id = cp.club_id AND cp.competition_id = ?
                WHERE c.club_id IN (SELECT DISTINCT club_id FROM competition_participants WHERE competition_id = ?)
                GROUP BY c.club_id, c.club_name
                ORDER BY rank_pos, avg_score DESC
                ''', (comp_id, comp_id))

                participants = cursor.fetchall()

                for p in participants:
                    self.participants_tree.insert('', 'end', values=(
                        p[0], p[1], f"{p[2]:.2f}", p[3] or "TBD"
                    ))

            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.error', default="Error"), f"Failed to load participants: {str(e)}")

    def update_score(self):
        selection = self.participants_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.please_select_a_club_first', default="Please select a club first."))
            return

        item = self.participants_tree.item(selection[0])
        club_id = item['values'][0]

        new_score = self.score_entry.get().strip()
        new_rank = self.rank_entry.get().strip()

        if not new_score:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.please_enter_a_score', default="Please enter a score."))
            return

        try:
            score = float(new_score)
            rank = int(new_rank) if new_rank else None

            selected_index = self.comp_combo.current()
            comp_id = self.comp_data[selected_index][0]

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Update all participants from this club in this competition
                cursor.execute('''
                UPDATE competition_participants
                SET score = ?, rank_position = ?
                WHERE competition_id = ? AND club_id = ?
                ''', (score, rank, comp_id, club_id))

                conn.commit()
            finally:
                conn.close()

            messagebox.showinfo(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.success', default="Success"), _t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.score_updated_successfully', default="Score updated successfully!"))
            self.on_competition_selected()
            self.score_entry.delete(0, tk.END)
            self.rank_entry.delete(0, tk.END)
        except ValueError:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.error', default="Error"), _t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.invalid_score_or_rank_value', default="Invalid score or rank value."))
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.error', default="Error"), f"Failed to update score: {str(e)}")

    def auto_calculate_ranks(self):
        if not self.comp_combo.current() >= 0:
            return

        try:
            selected_index = self.comp_combo.current()
            comp_id = self.comp_data[selected_index][0]

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Get all clubs with scores, ordered by score
                cursor.execute('''
                SELECT DISTINCT club_id, AVG(score) as avg_score
                FROM competition_participants
                WHERE competition_id = ? AND score IS NOT NULL
                GROUP BY club_id
                ORDER BY avg_score DESC
                ''')

                clubs = cursor.fetchall()

                # Assign ranks
                for rank, (club_id, score) in enumerate(clubs, 1):
                    cursor.execute('''
                    UPDATE competition_participants
                    SET rank_position = ?
                    WHERE competition_id = ? AND club_id = ?
                    ''', (rank, comp_id, club_id))

                conn.commit()
            finally:
                conn.close()

            messagebox.showinfo(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.success', default="Success"), f"Ranks calculated and assigned for {len(clubs)} clubs!")
            self.on_competition_selected()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.error', default="Error"), f"Failed to calculate ranks: {str(e)}")



def create_new_competition(self):
    """Create a new competition (Admin only)"""
    try:
        # Check admin permission
        if not self.auth_manager or not self.auth_manager.current_user:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.please_log_in_first', default="Please log in first."))
            return
        if not self.auth_manager.has_permission('manage_all_clubs'):
            messagebox.showerror(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.permission_denied', default="Permission Denied"), _t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.only_administrators_can_create_competitions', default="Only administrators can create competitions."))
            return
        dialog = CreateCompetitionDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.error', default="Error"), f"Failed to open dialog: {str(e)}")


def update_competition_scores(self):
    """Update competition scores (Admin only)"""
    try:
        # Check admin permission
        if not self.auth_manager or not self.auth_manager.current_user:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.please_log_in_first', default="Please log in first."))
            return
        if not self.auth_manager.has_permission('manage_all_clubs'):
            messagebox.showerror(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.permission_denied', default="Permission Denied"), _t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.only_administrators_can_update_scores', default="Only administrators can update scores."))
            return
        dialog = UpdateCompetitionScoresDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror(_t('gui.pastoral.student_union_gui.competitions.competition_admin.dialogs.error', default="Error"), f"Failed to open dialog: {str(e)}")


