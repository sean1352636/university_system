
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
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class ElectionsDialog:
    """Dialog for viewing elections with campaign information"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.elections.election_core.windows.elections_campaigns', default="Elections & Campaigns"))
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_elections()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.elections_campaigns', default="Elections & Campaigns"), font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Elections list
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.current_upcoming_elections', default="Current & Upcoming Elections"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Position', 'Department', 'Voting Period', 'Candidates', 'Status')
        self.elections_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            self.elections_tree.heading(col, text=col)
            if col == 'Voting Period':
                self.elections_tree.column(col, width=200)
            else:
                self.elections_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.elections_tree.yview)
        self.elections_tree.configure(yscrollcommand=scrollbar.set)

        self.elections_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.elections_tree.bind('<Double-1>', self.view_candidates)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.view_candidates', default="View Candidates"), command=self.view_candidates).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.vote', default="Vote"), command=self.vote_in_election).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.nominate_myself', default="Nominate Myself"), command=self.nominate_self).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.results', default="Results"), command=self.view_results).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def load_elections(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT e.id, e.title, e.department,
                   e.voting_start || ' to ' || e.voting_end,
                   COUNT(DISTINCT c.id), e.status
            FROM elections e
            LEFT JOIN election_candidates c ON e.id = c.election_id
            WHERE e.status IN ('upcoming', 'nomination', 'voting', 'completed')
            GROUP BY e.id
            ORDER BY e.voting_start
            ''')

            for row in cursor.fetchall():
                self.elections_tree.insert('', 'end', values=row)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.error', default="Error"), f"Failed to load elections: {str(e)}")

    def view_candidates(self, event=None):
        selection = self.elections_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.please_select_an_election', default="Please select an election."))
            return

        item = self.elections_tree.item(selection[0])
        election_id = item['values'][0]

        dialog = CandidatesDialog(self.dialog, self.auth, election_id)
        self.dialog.wait_window(dialog.dialog)

    def vote_in_election(self):
        selection = self.elections_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.please_select_an_election', default="Please select an election."))
            return

        item = self.elections_tree.item(selection[0])
        election_id = item['values'][0]
        status = item['values'][5]

        if status != 'voting':
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.voting_is_not_currently_open_for_this_election', default="Voting is not currently open for this election."))
            return

        dialog = VotingDialog(self.dialog, self.auth, election_id)
        self.dialog.wait_window(dialog.dialog)

    def nominate_self(self):
        dialog = NominationDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_elections()

    def view_results(self):
        selection = self.elections_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.please_select_an_election', default="Please select an election."))
            return

        item = self.elections_tree.item(selection[0])
        election_id = item['values'][0]

        dialog = ElectionResultsDialog(self.dialog, self.auth, election_id)
        self.dialog.wait_window(dialog.dialog)



class CandidatesDialog:
    """Dialog for viewing candidates and campaign materials"""

    def __init__(self, parent, auth_manager, election_id):
        self.parent = parent
        self.auth = auth_manager
        self.election_id = election_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.elections.election_core.windows.candidates_campaigns', default="Candidates & Campaigns"))
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.update_idletasks()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        self.create_widgets()
        self.load_candidates()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.candidates_campaigns', default="Candidates & Campaigns"), font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Candidates list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Candidate', 'Course', 'Materials', 'Expenses')
        self.candidates_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            self.candidates_tree.heading(col, text=col)
            if col == 'Candidate':
                self.candidates_tree.column(col, width=200)
            else:
                self.candidates_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.candidates_tree.yview)
        self.candidates_tree.configure(yscrollcommand=scrollbar.set)

        self.candidates_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.candidates_tree.bind('<<TreeviewSelect>>', self.on_candidate_selected)

        # Manifesto display
        manifesto_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.candidate_manifesto', default="Candidate Manifesto"))
        manifesto_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.manifesto_text = scrolledtext.ScrolledText(manifesto_frame, height=10, wrap=tk.WORD)
        self.manifesto_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.view_campaign_materials', default="View Campaign Materials"), command=self.view_materials).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def load_candidates(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT c.id, s.first_name || ' ' || s.last_name, s.course,
                   COUNT(DISTINCT cm.material_id), COALESCE(SUM(ce.amount), 0),
                   c.manifesto
            FROM election_candidates c
            JOIN students s ON c.student_id = s.student_id
            LEFT JOIN campaign_materials cm ON c.id = cm.candidate_id
            LEFT JOIN campaign_expenses ce ON c.id = ce.candidate_id
            WHERE c.election_id = ?
            GROUP BY c.id
            ''', (self.election_id,))

            candidates = cursor.fetchall()

            for row in candidates:
                values = (row[1], row[2], row[3], f"£{row[4]:.2f}")
                self.candidates_tree.insert('', 'end', values=values, tags=(row[0], row[5]))

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.error', default="Error"), f"Failed to load candidates: {str(e)}")

    def on_candidate_selected(self, event):
        selection = self.candidates_tree.selection()
        if not selection:
            return

        item = self.candidates_tree.item(selection[0])
        manifesto = item['tags'][1] if len(item['tags']) > 1 else "No manifesto submitted."

        self.manifesto_text.delete(1.0, tk.END)
        self.manifesto_text.insert(1.0, manifesto)

    def view_materials(self):
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.info', default="Info"), _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.campaign_materials_viewer_would_display_videos_photos_and_docume', default="Campaign materials viewer would display videos, photos, and documents here."))



class VotingDialog:
    """Dialog for casting votes in an election"""

    def __init__(self, parent, auth_manager, election_id):
        self.parent = parent
        self.auth = auth_manager
        self.election_id = election_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.elections.election_core.windows.cast_your_vote', default="Cast Your Vote"))
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.check_already_voted()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.cast_your_vote', default="Cast Your Vote"), font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        info_label = ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.your_vote_is_secret_and_anonymous_select_your_preferred_candidat', default="Your vote is secret and anonymous.\nSelect your preferred candidate below:"),
                              justify='center', foreground='blue')
        info_label.pack(pady=(0, 15))

        # Candidates frame
        candidates_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.select_candidate', default="Select Candidate"))
        candidates_frame.pack(fill='both', expand=True, pady=(0, 15))

        self.candidate_var = tk.StringVar()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT c.id, s.first_name || ' ' || s.last_name, s.course, c.manifesto
            FROM election_candidates c
            JOIN students s ON c.student_id = s.student_id
            WHERE c.election_id = ?
            ''', (self.election_id,))

            self.candidates = cursor.fetchall()
            conn.close()

            for candidate in self.candidates:
                frame = ttk.Frame(candidates_frame)
                frame.pack(fill='x', padx=10, pady=5)

                rb = ttk.Radiobutton(frame, text=f"{candidate[1]} ({candidate[2]})",
                                    variable=self.candidate_var, value=str(candidate[0]))
                rb.pack(anchor='w')

                if candidate[3]:
                    manifesto_label = ttk.Label(frame, text=f"Manifesto: {candidate[3][:100]}...",
                                               foreground='gray', wraplength=600)
                    manifesto_label.pack(anchor='w', padx=(30, 0))

        except sqlite3.Error as e:
            ttk.Label(candidates_frame, text=f"Error loading candidates: {str(e)}", foreground='red').pack()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.submit_vote', default="Submit Vote"), command=self.submit_vote, style='Accent.TButton').pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side='left')

    def check_already_voted(self):
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
            SELECT COUNT(*) FROM election_votes
            WHERE election_id = ? AND student_id = ?
            ''', (self.election_id, student_id))

            if cursor.fetchone()[0] > 0:
                messagebox.showinfo(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.already_voted', default="Already Voted"), _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.you_have_already_cast_your_vote_in_this_election', default="You have already cast your vote in this election."))
                self.dialog.destroy()

            conn.close()
        except sqlite3.Error:
            pass

    def submit_vote(self):
        if not self.candidate_var.get():
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.please_select_a_candidate', default="Please select a candidate."))
            return

        if messagebox.askyesno(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.confirm_vote', default="Confirm Vote"),
                              _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.are_you_sure_you_want_to_cast_your_vote_this_action_cannot_be_un', default="Are you sure you want to cast your vote?\nThis action cannot be undone.")):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                student_id = cursor.fetchone()[0]

                cursor.execute('''
                INSERT INTO election_votes (election_id, candidate_id, student_id, vote_date)
                VALUES (?, ?, ?, ?)
                ''', (self.election_id, int(self.candidate_var.get()), student_id, datetime.now().isoformat()))

                conn.commit()
                conn.close()

                messagebox.showinfo(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.success', default="Success"), _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.your_vote_has_been_recorded_thank_you_for_participating', default="Your vote has been recorded!\n\nThank you for participating."))
                self.dialog.destroy()
            except sqlite3.Error as e:
                messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.error', default="Error"), f"Failed to record vote: {str(e)}")



class NominationDialog:
    """Dialog for submitting election nomination"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.election_data = {}  # Initialize to prevent AttributeError

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.elections.election_core.windows.submit_nomination', default="Submit Nomination"))
        self.dialog.geometry("700x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.submit_election_nomination', default="Submit Election Nomination"), font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Election selection
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.select_election', default="Select Election:")).pack(anchor='w', pady=(0, 5))
        self.election_var = tk.StringVar()
        self.election_combo = ttk.Combobox(main_frame, textvariable=self.election_var, state='readonly', width=50)
        self.election_combo.pack(fill='x', pady=(0, 15))

        self.load_elections()

        # Manifesto
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.your_manifesto_why_should_students_vote_for_you', default="Your Manifesto (Why should students vote for you?):")).pack(anchor='w', pady=(0, 5))
        self.manifesto_text = scrolledtext.ScrolledText(main_frame, height=15, wrap=tk.WORD)
        self.manifesto_text.pack(fill='both', expand=True, pady=(0, 15))
        self.manifesto_text.insert(1.0, "Enter your campaign manifesto here...\n\nInclude:\n- Your vision\n- Key policies\n- Why you're the best candidate")

        # Endorsements
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.endorsements_optional', default="Endorsements (optional):")).pack(anchor='w', pady=(0, 5))
        self.endorsements_entry = ttk.Entry(main_frame, width=50)
        self.endorsements_entry.pack(fill='x', pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.submit_nomination', default="Submit Nomination"), command=self.submit_nomination).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side='left')

    def load_elections(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, title, department
            FROM elections
            WHERE status = 'nomination'
            AND nomination_end >= date('now')
            ORDER BY title
            ''')

            elections = cursor.fetchall()

            if elections:
                self.election_data = {f"{e[1]} ({e[2] if e[2] else 'All Departments'})": e[0] for e in elections}
                self.election_combo['values'] = list(self.election_data.keys())
            else:
                self.election_data = {}  # Ensure it's set even if no elections
                self.election_combo['values'] = ["No elections accepting nominations"]

            conn.close()
        except sqlite3.Error as e:
            self.election_data = {}  # Ensure it's set even on error
            self.election_combo['values'] = ["Error loading elections"]
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.error', default="Error"), f"Failed to load elections: {str(e)}")

    def submit_nomination(self):
        if not self.election_var.get() or self.election_var.get() not in self.election_data:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.please_select_an_election', default="Please select an election."))
            return

        manifesto = self.manifesto_text.get(1.0, tk.END).strip()
        if not manifesto or len(manifesto) < 100:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.please_provide_a_detailed_manifesto_at_least_100_characters', default="Please provide a detailed manifesto (at least 100 characters)."))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            student_id = cursor.fetchone()[0]

            election_id = self.election_data[self.election_var.get()]

            cursor.execute('''
            INSERT INTO election_candidates (election_id, student_id, manifesto, nomination_date)
            VALUES (?, ?, ?, ?)
            ''', (election_id, student_id, manifesto, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.success', default="Success"), _t('gui.pastoral.student_union_gui.elections.election_core.dialogs.your_nomination_has_been_submitted_good_luck_with_your_campaign', default="Your nomination has been submitted!\n\nGood luck with your campaign!"))
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_core.dialogs.error', default="Error"), f"Failed to submit nomination: {str(e)}")



class ElectionResultsDialog:
    """Dialog for viewing election results"""

    def __init__(self, parent, auth_manager, election_id):
        self.parent = parent
        self.auth = auth_manager
        self.election_id = election_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.elections.election_core.windows.election_results', default="Election Results"))
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_results()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.labels.election_results', default="Election Results"), font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Results display
        self.results_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=('Courier', 10))
        self.results_text.pack(fill='both', expand=True, pady=(0, 15))

        ttk.Button(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_core.buttons.close', default="Close"), command=self.dialog.destroy).pack()

    def load_results(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get election info
            cursor.execute('''
            SELECT title, department, voting_start, voting_end, status
            FROM elections WHERE id = ?
            ''', (self.election_id,))

            election = cursor.fetchone()

            if election[4] != 'completed':
                self.results_text.insert(1.0, "This election is still ongoing.\nResults will be available after voting closes.")
                conn.close()
                return

            results_text = "ELECTION RESULTS\n"
            results_text += f"{'='*60}\n\n"
            results_text += f"Position: {election[0]}\n"
            results_text += f"Department: {election[1] if election[1] else 'All'}\n"
            results_text += f"Voting Period: {election[2]} to {election[3]}\n\n"

            # Get vote counts
            cursor.execute('''
            SELECT s.first_name || ' ' || s.last_name, COUNT(v.id) as votes
            FROM election_candidates c
            JOIN students s ON c.student_id = s.student_id
            LEFT JOIN election_votes v ON c.id = v.candidate_id
            WHERE c.election_id = ?
            GROUP BY c.id, s.first_name, s.last_name
            ORDER BY votes DESC
            ''', (self.election_id,))

            candidates = cursor.fetchall()
            total_votes = sum(c[1] for c in candidates)

            results_text += f"Total Votes Cast: {total_votes}\n\n"
            results_text += f"{'Candidate':<30} {'Votes':<10} {'Percentage':<10}\n"
            results_text += f"{'-'*60}\n"

            for i, (name, votes) in enumerate(candidates):
                percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                winner = "  🏆 WINNER" if i == 0 and votes > 0 else ""
                results_text += f"{name:<30} {votes:<10} {percentage:>6.1f}%{winner}\n"

            self.results_text.insert(1.0, results_text)
            conn.close()
        except sqlite3.Error as e:
            self.results_text.insert(1.0, f"Error loading results: {str(e)}")



def open_elections_dialog(self):
    """Open elections and voting dialog"""
    dialog = ElectionsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


