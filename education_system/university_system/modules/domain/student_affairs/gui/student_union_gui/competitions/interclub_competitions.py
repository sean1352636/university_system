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


class InterClubCompetitionsDialog:
    """Main dialog for inter-club competitions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.competitions.dialog_title"))
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="🏆 " + _t("student_union.competitions.interclub_header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(button_frame, text=_t("student_union.competitions.view_active"),
                  command=self.view_active).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("student_union.competitions.view_results"),
                  command=self.view_results).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("student_union.competitions.create_competition_admin"),
                  command=self.create_competition).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t("student_union.competitions.update_scores_admin"),
                  command=self.update_scores).pack(side='left', padx=5)

        # Competitions display
        display_frame = ttk.LabelFrame(main_frame, text=_t("student_union.competitions.overview_label"))
        display_frame.pack(fill='both', expand=True, pady=(0, 15))

        self.comp_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD, height=25)
        self.comp_text.pack(fill='both', expand=True, padx=5, pady=5)

        self.load_overview()

        ttk.Button(main_frame, text=_t("student_union.competitions.close"), command=self.dialog.destroy).pack()

    def load_overview(self):
        self.comp_text.delete(1.0, tk.END)
        overview = f"""{_t("student_union.competitions.overview.header")}

🏅 {_t("student_union.competitions.overview.active_header")}
{_t("student_union.competitions.overview.active_1")}
{_t("student_union.competitions.overview.active_2")}
{_t("student_union.competitions.overview.active_3")}
{_t("student_union.competitions.overview.active_4")}

📊 {_t("student_union.competitions.overview.standings_header")}
1. 🥇 {_t("student_union.competitions.overview.standing_1").lstrip("1. ")}
2. 🥈 {_t("student_union.competitions.overview.standing_2").lstrip("2. ")}
3. 🥉 {_t("student_union.competitions.overview.standing_3").lstrip("3. ")}

📅 {_t("student_union.competitions.overview.upcoming_header")}
{_t("student_union.competitions.overview.upcoming_1")}
{_t("student_union.competitions.overview.upcoming_2")}
{_t("student_union.competitions.overview.upcoming_3")}

🎯 {_t("student_union.competitions.overview.benefits_header")}
✓ {_t("student_union.competitions.overview.benefit_1")}
✓ {_t("student_union.competitions.overview.benefit_2")}
✓ {_t("student_union.competitions.overview.benefit_3")}
✓ {_t("student_union.competitions.overview.benefit_4")}
✓ {_t("student_union.competitions.overview.benefit_5")}

{_t("student_union.competitions.overview.footer")}
"""
        self.comp_text.insert(1.0, overview)

    def view_active(self):
        dialog = ActiveCompetitionsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_results(self):
        dialog = CompetitionResultsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def create_competition(self):
        dialog = CreateCompetitionDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def update_scores(self):
        dialog = UpdateCompetitionScoresDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class ActiveCompetitionsDialog:
    """Dialog for viewing active competitions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.competitions.active_title"))
        self.dialog.geometry("1000x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t("student_union.competitions.active_title"), font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Competitions list
        list_frame = ttk.LabelFrame(main_frame, text=_t("student_union.competitions.available_competitions"))
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = (
            _t("student_union.competitions.columns.id"),
            _t("student_union.competitions.columns.name"),
            _t("student_union.competitions.columns.type"),
            _t("student_union.competitions.columns.start_date"),
            _t("student_union.competitions.columns.end_date"),
            _t("student_union.competitions.columns.registered"),
            _t("student_union.competitions.columns.status")
        )
        self.comp_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        name_col = _t("student_union.competitions.columns.name")
        for col in columns:
            self.comp_tree.heading(col, text=col)
            if col == name_col:
                self.comp_tree.column(col, width=200)
            else:
                self.comp_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.comp_tree.yview)
        self.comp_tree.configure(yscrollcommand=scrollbar.set)

        self.comp_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.comp_tree.bind('<<TreeviewSelect>>', self.on_select)

        # Sample data
        competitions = [
            (1, "Sports Tournament", "Sports", "2025-04-01", "2025-04-30", "12/20", "Active"),
            (2, "Academic Challenge", "Academic", "2025-04-10", "2025-04-25", "15/25", "Registration Open"),
            (3, "Cultural Festival", "Arts", "2025-05-01", "2025-05-03", "8/15", "Upcoming"),
            (4, "Hackathon 2025", "Technology", "2025-04-20", "2025-04-21", "20/30", "Active")
        ]

        for comp in competitions:
            self.comp_tree.insert('', 'end', values=comp)

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text=_t("student_union.competitions.competition_details"))
        details_frame.pack(fill='x', pady=(0, 15))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=8, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t("student_union.competitions.register_club"), command=self.register_club).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("student_union.competitions.view_standings"), command=self.view_standings).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("student_union.competitions.close"), command=self.dialog.destroy).pack(side='right')

    def on_select(self, event):
        selection = self.comp_tree.selection()
        if not selection:
            return

        item = self.comp_tree.item(selection[0])
        comp_name = item['values'][1]
        comp_type = item['values'][2]

        details = f"""{_t("student_union.competitions.details.competition").format(name=comp_name)}

{_t("student_union.competitions.details.type").format(type=comp_type)}
{_t("student_union.competitions.details.period").format(start=item['values'][3], end=item['values'][4])}
{_t("student_union.competitions.details.registered_clubs").format(count=item['values'][5])}
{_t("student_union.competitions.details.status").format(status=item['values'][6])}

{_t("student_union.competitions.details.description_header")}
{_t("student_union.competitions.details.description")}

{_t("student_union.competitions.details.rules_header")}
{_t("student_union.competitions.details.rule_1")}
{_t("student_union.competitions.details.rule_2")}
{_t("student_union.competitions.details.rule_3")}

{_t("student_union.competitions.details.prizes_header")}
🥇 {_t("student_union.competitions.details.prize_1st")}
🥈 {_t("student_union.competitions.details.prize_2nd")}
🥉 {_t("student_union.competitions.details.prize_3rd")}

{_t("student_union.competitions.details.registration_header")}
{_t("student_union.competitions.details.registration_hint")}
"""
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)

    def register_club(self):
        dialog = RegisterClubCompetitionDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_standings(self):
        messagebox.showinfo(_t("student_union.competitions.standings"), _t("student_union.competitions.standings_info"))



class RegisterClubCompetitionDialog:
    """Dialog for registering a club for competition"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.competitions.register_club_title"))
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=_t("student_union.competitions.register_dialog.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Club selection
        ttk.Label(main_frame, text=_t("student_union.competitions.register_dialog.select_club")).pack(anchor='w', pady=(0, 5))
        self.club_combo = ttk.Combobox(main_frame, width=50, state='readonly')
        self.club_combo['values'] = ('Computer Science Society', 'Engineering Club', 'Business Society')
        self.club_combo.pack(fill='x', pady=(0, 15))

        # Participant selection
        ttk.Label(main_frame, text=_t("student_union.competitions.register_dialog.select_team_members")).pack(anchor='w', pady=(0, 5))

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.members_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, yscrollcommand=scrollbar.set, height=10)
        self.members_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.members_listbox.yview)

        # Sample members
        members = ['John Doe', 'Jane Smith', 'Bob Johnson', 'Alice Williams', 'Charlie Brown', 'David Lee']
        for member in members:
            self.members_listbox.insert(tk.END, member)

        # Team name
        ttk.Label(main_frame, text=_t("student_union.competitions.register_dialog.team_name")).pack(anchor='w', pady=(0, 5))
        self.team_entry = ttk.Entry(main_frame, width=50)
        self.team_entry.pack(fill='x', pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t("student_union.competitions.register_dialog.register"), command=self.register).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("student_union.competitions.register_dialog.cancel"), command=self.dialog.destroy).pack(side='left')

    def register(self):
        selected = self.members_listbox.curselection()
        if len(selected) == 0:
            messagebox.showwarning(_t("student_union.competitions.warning"), _t("student_union.competitions.register_dialog.warning_no_members"))
            return

        if len(selected) > 5:
            messagebox.showwarning(_t("student_union.competitions.warning"), _t("student_union.competitions.register_dialog.warning_max_members"))
            return

        messagebox.showinfo(_t("student_union.competitions.success"), _t("student_union.competitions.register_dialog.success").format(count=len(selected)))
        self.dialog.destroy()


# ============================================================================
# COMMUNITY ENGAGEMENT DIALOGS
# ============================================================================


def open_interclub_competitions_dialog(self):
    """Open inter-club competitions dialog"""
    dialog = InterClubCompetitionsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


