
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog
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

# Import email service
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available")

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


def _vm():
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.elections import (
        voting_methods,
    )
    return voting_methods


def _vm_conn():
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    _vm().ensure_schema(conn)
    conn.commit()
    return conn


def _election_label(e):
    dept = f" ({e['department']})" if e.get('department') else ""
    return f"{e['election_id']}: {e['position']}{dept}"


class ManageEnhancedVotingDialog:
    """Dialog for managing enhanced voting systems"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.windows.enhanced_voting_systems', default="Enhanced Voting Systems"))
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.enhanced_voting_systems', default="🗳️ Enhanced Voting Systems"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Voting methods overview
        overview_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.available_voting_methods', default="Available Voting Methods"))
        overview_frame.pack(fill='x', pady=(0, 15))
        self.methods_label = ttk.Label(overview_frame, text="", justify='left', font=('Courier', 9))
        self.methods_label.pack(padx=15, pady=10, anchor='w')

        # Buttons (packed before the expanding table so they stay visible)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side='bottom', fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.configure_ranked_choice', default="Configure Ranked Choice"), command=self.config_ranked).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.configure_approval', default="Configure Approval"), command=self.config_approval).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.configure_score', default="Configure Score"), command=self.config_score).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.view_method_comparison', default="View Method Comparison"), command=self.view_comparison).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

        # Statistics
        stats_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.voting_statistics', default="Voting Statistics"))
        stats_frame.pack(side='bottom', fill='x', pady=(0, 15))
        self.stats_label = ttk.Label(stats_frame, text="", justify='left', font=('Courier', 10))
        self.stats_label.pack(padx=15, pady=10, anchor='w')

        # Elections using enhanced voting
        elections_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.elections_configuration', default="Elections Configuration"))
        elections_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Election', 'Position', 'Voting Method', 'Status', 'Start Date', 'End Date')
        self.tree = ttk.Treeview(elections_frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            self.tree.heading(col, text=col)
            if col == 'Election':
                self.tree.column(col, width=180)
            elif col == 'Voting Method':
                self.tree.column(col, width=140)
            else:
                self.tree.column(col, width=100)

        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

    def load_data(self):
        vm = _vm()
        try:
            conn = _vm_conn()
            try:
                rows = vm.elections(conn)
                default = vm.union_default(conn)
                stats = vm.method_statistics(conn)
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"), f"Failed to load elections: {e}", parent=self.dialog)
            return

        lines = ["VOTING METHODS THE ELECTION SERVICE SUPPORTS:", ""]
        for method, label in vm.METHOD_LABELS.items():
            support = vm.METHOD_SUPPORT[method]
            if method == vm.RANKED and not default['allow_ranked_choice']:
                status = "SWITCHED OFF in union voting configuration"
            elif support['cast']:
                status = "AVAILABLE" + (" (union default)" if default['default_method'] == method else "")
            else:
                status = "NOT AVAILABLE"
            lines.append(f"{'✓' if support['cast'] else '✗'} {label}: {status}")
            lines.append(f"    {support['note']}")
        self.methods_label.config(text="\n".join(lines))

        for item in self.tree.get_children():
            self.tree.delete(item)
        for e in rows:
            self.tree.insert('', 'end', values=(
                _election_label(e), e['position'] or '', e['method_label'],
                (e['status'] or '').title(), (e['voting_start'] or '')[:10], (e['voting_end'] or '')[:10]))
        if not rows:
            self.tree.insert('', 'end', values=("No elections have been set up yet.", '', '', '', '', ''))

        if not stats['total']:
            self.stats_label.config(text=f"No elections recorded for {stats['year']}.")
        else:
            out = [f"Total Elections This Year: {stats['total']}"]
            for method, label in vm.METHOD_LABELS.items():
                m = stats['by_method'][method]
                out.append(f"{label}: {m['elections']} ({m['share']:.0f}%)")
            out.append("")
            if stats['eligible_voters']:
                out.append(f"Average Voter Turnout (of {stats['eligible_voters']} eligible students):")
                for method, label in vm.METHOD_LABELS.items():
                    t = stats['by_method'][method]['turnout']
                    if t is not None:
                        out.append(f"- {label}: {t:.0f}%")
            else:
                out.append("Turnout not available: no eligible student records.")
            self.stats_label.config(text="\n".join(out))

    def _open_config(self, tab_index):
        dialog = ConfigureVotingMethodsDialog(self.dialog, self.auth, initial_tab=tab_index)
        self.dialog.wait_window(dialog.dialog)
        self.load_data()

    def config_ranked(self):
        self._open_config(1)

    def config_approval(self):
        self._open_config(2)

    def config_score(self):
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.score_voting', default="Score Voting"),
                            "Score voting is not implemented by the Student Union election service, "
                            "so it cannot be configured for an election.\n\n"
                            "Supported methods: Standard Voting and Ranked Choice.", parent=self.dialog)

    def view_comparison(self):
        vm = _vm()
        text = "Voting Method Comparison (as implemented here):\n\n" + "\n\n".join(
            f"{label}: {vm.METHOD_SUPPORT[m]['note']}" for m, label in vm.METHOD_LABELS.items())
        text += ("\n\nStandard voting can split the vote between similar candidates; ranked choice "
                 "transfers ballots until one candidate holds a majority of live ballots.")
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.method_comparison', default="Method Comparison"),
                            text, parent=self.dialog)



class RankedChoiceVotingDialog:
    """Dialog for ranked choice voting system"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.rank_combos = {}  # candidate_id -> ranking dropdown
        self.candidates = []  # candidate dicts for the selected election
        self.elections = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.windows.ranked_choice_voting', default="Ranked Choice Voting"))
        self.dialog.geometry("1000x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_elections()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.ranked_choice_voting', default="📊 Ranked Choice Voting"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side='bottom', fill='x')
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.view_tutorial_video', default="View Tutorial Video"), command=self.view_tutorial).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.download_ballot_template', default="Download Ballot Template"), command=self.download_template).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

        # Create notebook for sections
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True, pady=(0, 15))

        # How It Works tab
        how_frame = ttk.Frame(self.notebook)
        self.notebook.add(how_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.tabs.how_it_works', default="How It Works"))

        how_scroll = scrolledtext.ScrolledText(how_frame, height=15, wrap=tk.WORD)
        how_scroll.pack(fill='both', expand=True, padx=10, pady=10)
        how_scroll.insert('1.0', (
            "RANKED CHOICE VOTING (RCV)\n\n"
            "HOW TO VOTE:\n"
            "1. Rank candidates in order of preference (1st, 2nd, 3rd, ...)\n"
            "2. You do not have to rank every candidate (unless the election requires it)\n"
            "3. Each candidate can be given only one rank\n\n"
            "HOW VOTES ARE COUNTED (instant runoff):\n"
            "- Each ballot counts for its highest-ranked candidate still in the race\n"
            "- If a candidate holds more than half of the live ballots, they win\n"
            "- Otherwise the candidate with the fewest votes is eliminated and their\n"
            "  ballots move to each voter's next choice\n"
            "- Ties for elimination go to the candidate with fewer first preferences\n"
            "- A ballot whose ranked candidates are all eliminated is 'exhausted'\n\n"
            "The RCV Results tab shows the real round-by-round count for the\n"
            "election selected on the Cast RCV Vote tab."))
        how_scroll.config(state='disabled')

        # Cast Vote tab
        vote_frame = ttk.Frame(self.notebook)
        self.notebook.add(vote_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.tabs.cast_rcv_vote', default="Cast RCV Vote"))

        picker = ttk.Frame(vote_frame)
        picker.pack(fill='x', padx=15, pady=(15, 0))
        ttk.Label(picker, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.election', default="Election:")).pack(side='left', padx=(0, 10))
        self.election_combo = ttk.Combobox(picker, width=50, state='readonly')
        self.election_combo.pack(side='left', fill='x', expand=True)
        self.election_combo.bind('<<ComboboxSelected>>', lambda e: self.show_ballot())

        self.vote_content = ttk.Frame(vote_frame)
        self.vote_content.pack(fill='both', expand=True, padx=15, pady=15)

        # Results tab
        results_frame = ttk.Frame(self.notebook)
        self.notebook.add(results_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.tabs.rcv_results', default="RCV Results"))

        self.results_scroll = scrolledtext.ScrolledText(results_frame, height=15, wrap=tk.WORD, font=('Courier', 9))
        self.results_scroll.pack(fill='both', expand=True, padx=10, pady=10)

    def _voter_id(self, conn):
        from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import current_student_id
        return current_student_id(conn.cursor(), self.auth)

    def load_elections(self):
        vm = _vm()
        try:
            conn = _vm_conn()
            try:
                # Every ranked-choice election (for results), marking those this voter can vote in.
                ranked = [e for e in vm.elections(conn) if e['method'] == vm.RANKED]
                open_ids = {e['election_id'] for e in vm.ranked_elections_open_to(conn, self._voter_id(conn))}
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"), f"Failed to load elections: {e}", parent=self.dialog)
            return
        self.open_ids = open_ids
        self.elections = {}
        for e in ranked:
            suffix = " - voting open" if e['election_id'] in open_ids else f" - {(e['status'] or '').lower()}"
            self.elections[_election_label(e) + suffix] = e
        self.election_combo['values'] = list(self.elections)
        if self.elections:
            preferred = next((k for k, e in self.elections.items() if e['election_id'] in open_ids), next(iter(self.elections)))
            self.election_combo.set(preferred)
        self.show_ballot()

    def _selected_election(self):
        return self.elections.get(self.election_combo.get())

    def show_ballot(self):
        for w in self.vote_content.winfo_children():
            w.destroy()
        self.rank_combos = {}
        self.candidates = []
        election = self._selected_election()
        if not election:
            ttk.Label(self.vote_content, text="No elections are set to use ranked choice voting.\n\n"
                      "An administrator can switch an election to ranked choice under Configure Voting Methods.",
                      justify='center', foreground='gray').pack(pady=40)
            self._show_results(None)
            return

        vm = _vm()
        try:
            conn = _vm_conn()
            try:
                self.candidates = vm.candidates(conn, election['election_id'])
                self.config = vm.election_config(conn, election['election_id'])
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"), f"Failed to load candidates: {e}", parent=self.dialog)
            return

        ttk.Label(self.vote_content, text=election['position'] or f"Election {election['election_id']}",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        if not self.candidates:
            ttk.Label(self.vote_content, text="No candidates are standing in this election yet, so there is no ballot to cast.",
                      foreground='gray').pack(pady=20)
            self._show_results(election)
            return

        can_vote = election['election_id'] in getattr(self, 'open_ids', set())
        ttk.Label(self.vote_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.rank_candidates_in_order_of_preference_1_most_preferred', default="Rank candidates in order of preference (1 = most preferred)"),
                 font=('Arial', 10)).pack(pady=(0, 15))

        max_rank = len(self.candidates)
        if self.config.get('max_choices'):
            max_rank = min(max_rank, self.config['max_choices'])
        ordinals = {1: '1st', 2: '2nd', 3: '3rd'}
        rank_values = ['Not Ranked'] + [f"{ordinals.get(i, f'{i}th')} Choice" for i in range(1, max_rank + 1)]

        for cand in self.candidates:
            candidate_frame = ttk.Frame(self.vote_content)
            candidate_frame.pack(fill='x', pady=5)

            info_frame = ttk.Frame(candidate_frame)
            info_frame.pack(side='left', fill='x', expand=True)
            ttk.Label(info_frame, text=cand['name'], font=('Arial', 10, 'bold')).pack(anchor='w')
            detail = [p for p in (cand.get('course'),
                                  f"{cand['endorsements']} endorsements" if cand.get('endorsements') else None) if p]
            if detail:
                ttk.Label(info_frame, text=" • ".join(detail), font=('Arial', 9)).pack(anchor='w')
            if cand.get('manifesto'):
                ttk.Label(info_frame, text=cand['manifesto'][:140], font=('Arial', 9), foreground='gray',
                          wraplength=600).pack(anchor='w')

            rank_combo = ttk.Combobox(candidate_frame, width=15, state='readonly' if can_vote else 'disabled')
            rank_combo['values'] = rank_values
            rank_combo.current(0)
            rank_combo.pack(side='right', padx=(10, 0))
            self.rank_combos[cand['candidate_id']] = rank_combo

        if can_vote:
            ttk.Button(self.vote_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.submit_ranked_ballot', default="Submit Ranked Ballot"),
                      command=self.submit_ballot).pack(pady=20)
        else:
            ttk.Label(self.vote_content, text="Voting is not open to you for this election "
                      "(not in its voting window, or you have already voted).",
                      foreground='gray').pack(pady=20)
        self._show_results(election)

    def _show_results(self, election):
        vm = _vm()
        self.results_scroll.config(state='normal')
        self.results_scroll.delete('1.0', tk.END)
        if election is None:
            self.results_scroll.insert('1.0', "No ranked choice elections to count.")
        else:
            try:
                conn = _vm_conn()
                try:
                    result = vm.tally_ranked(conn, election['election_id'])
                finally:
                    conn.close()
                text = vm.tally_text(election['position'] or '', result)
                if (election['status'] or '').lower() == 'voting' and result.get('total'):
                    text = "PROVISIONAL - voting is still open\n\n" + text
                self.results_scroll.insert('1.0', text)
            except sqlite3.Error as e:
                self.results_scroll.insert('1.0', f"Could not count ballots: {e}")
        self.results_scroll.config(state='disabled')

    def submit_ballot(self):
        """Submit the ranked choice ballot to ranked_votes."""
        election = self._selected_election()
        if not election:
            return
        ranked = {}
        for cand_id, combo in self.rank_combos.items():
            value = combo.get()
            if value != 'Not Ranked':
                rank = int(''.join(ch for ch in value.split()[0] if ch.isdigit()))
                if rank in ranked:
                    messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"),
                                         "Each rank can only be given to one candidate.", parent=self.dialog)
                    return
                ranked[rank] = cand_id
        if not ranked:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.no_rankings', default="No Rankings"),
                                   "Please rank at least one candidate.", parent=self.dialog)
            return
        order = [ranked[r] for r in sorted(ranked)]
        if sorted(ranked) != list(range(1, len(ranked) + 1)):
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.no_rankings', default="No Rankings"),
                                   "Please use consecutive ranks starting from 1st (no gaps).", parent=self.dialog)
            return
        names = {c['candidate_id']: c['name'] for c in self.candidates}
        rankings_display = "".join(f"{i}. {names[c]}\n" for i, c in enumerate(order, 1))
        if not messagebox.askyesno(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.vote_submitted', default="Vote Submitted"),
                                   f"Submit this ranked ballot for {election['position']}?\n\n{rankings_display}\n"
                                   "Once submitted it cannot be changed.", parent=self.dialog):
            return

        vm = _vm()
        try:
            conn = _vm_conn()
            try:
                voter = self._voter_id(conn)
                vote_id = vm.cast_ranked(conn, election_id=election['election_id'], voter_id=voter,
                                         ranked_candidate_ids=order)
                from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import contact_email
                email = contact_email(conn.cursor(), voter)
            finally:
                conn.close()
        except ValueError as e:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"), str(e), parent=self.dialog)
            return
        except sqlite3.IntegrityError:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"),
                                 "Your ballot could not be recorded: ranked ballots must belong to a student record, "
                                 "and this account has none.", parent=self.dialog)
            return
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"), f"Failed to record ballot: {e}", parent=self.dialog)
            return

        messagebox.showinfo(
            _t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.vote_submitted', default="Vote Submitted"),
            f"Your ranked choice ballot has been recorded (receipt #{vote_id}).\n\nYour rankings:\n{rankings_display}\nThank you for voting!",
            parent=self.dialog)

        if EMAIL_SERVICE_AVAILABLE and email:
            try:
                username = (self.auth.current_user or {}).get('username', 'Voter')
                subject, email_body = render_template('student_union/ranked_choice_ballot_receipt', {
                    'username': username,
                    'rankings': rankings_display,
                    'position': election['position'],
                    'submission_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                send_email(to_email=email, subject=subject, body=email_body)
            except Exception:
                logger.debug("ballot receipt email failed", exc_info=True)
        self.load_elections()

    def view_tutorial(self):
        """Show the voting guidance (the How It Works tab)."""
        self.notebook.select(0)

    def download_template(self):
        """Download a ranked choice voting ballot template"""
        # Ask user where to save the file
        file_path = filedialog.asksaveasfilename(
            parent=self.dialog,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="rcv_ballot_template.txt"
        )

        if not file_path:
            return  # User cancelled

        try:
            election = self._selected_election()
            position = election['position'] if election else "[Insert Position Name]"
            dates = (f"{(election['voting_start'] or '')[:10]} to {(election['voting_end'] or '')[:10]}"
                     if election else "[Insert Date]")
            names = [c['name'] for c in self.candidates] if election else []
            if not names:
                names = [f"Candidate {i}" for i in range(1, 6)]
            candidate_lines = "\n".join(f"[ ]     {n}" for n in names)
            template_content = (
                "RANKED CHOICE VOTING BALLOT TEMPLATE\n"
                "========================================\n\n"
                "INSTRUCTIONS FOR VOTERS:\n"
                "------------------------\n"
                "1. Rank candidates in order of preference (1 = first choice, 2 = second choice, etc.)\n"
                "2. You may rank as many or as few candidates as you wish\n"
                "3. Do not rank the same candidate more than once\n"
                "4. Leave boxes blank for candidates you do not wish to rank\n\n"
                f"POSITION: {position}\n"
                f"VOTING PERIOD: {dates}\n\n"
                "CANDIDATES:\n"
                "-----------\n"
                "Rank    Candidate Name\n"
                f"{candidate_lines}\n\n"
                "HOW RANKED CHOICE VOTING WORKS:\n"
                "-------------------------------\n"
                "- If a candidate holds more than half of the live ballots, they win\n"
                "- Otherwise the candidate with the fewest votes is eliminated\n"
                "- Ballots for the eliminated candidate move to each voter's next choice\n"
                "- This repeats until a candidate has a majority\n\n"
                "For questions or assistance, contact the Elections Committee.\n"
            )

            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(template_content)

            messagebox.showinfo(
                _t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.download_complete', default="Download Complete"),
                f"Ballot template saved successfully to:\n{file_path}\n\n" +
                ("It lists the candidates standing for " + position + "." if election and self.candidates
                 else "No election with candidates is selected, so the candidate rows are blank placeholders."),
                parent=self.dialog
            )
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"), f"Failed to save ballot template: {e}", parent=self.dialog)



class ConfigureVotingMethodsDialog:
    """Dialog for configuring voting methods"""

    # Options that election_voting_config has no column for; kept per election
    # in union_voting_settings under 'election_options:<id>'.
    _OPTION_VARS = (
        'allow_writein_var', 'show_live_results_var', 'require_confirm_var', 'winning_criterion_var',
        'show_runoff_viz_var', 'elimination_var', 'tiebreak_var', 'show_approval_count_var',
        'approval_limit_var', 'results_display_var', 'require_2fa_var', 'unique_code_var',
        'vote_verify_var', 'allow_change_var', 'screen_reader_var', 'audio_ballot_var',
        'extended_time_var', 'enable_standard_var',
    )

    def __init__(self, parent, auth_manager, initial_tab=None):
        self.parent = parent
        self.auth = auth_manager
        self.election_data = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.windows.configure_voting_methods', default="Configure Voting Methods"))
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_elections()
        if initial_tab is not None:
            self.notebook.select(initial_tab)

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.configure_voting_methods', default="⚙️ Configure Voting Methods"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Election selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(select_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.election', default="Election:")).pack(side='left', padx=(0, 10))
        self.election_combo = ttk.Combobox(select_frame, width=40, state='readonly')
        self.election_combo.pack(side='left', fill='x', expand=True)
        self.election_combo.bind('<<ComboboxSelected>>', lambda e: self.load_election_config())

        # Create notebook for method configuration
        notebook = self.notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Standard Voting tab
        standard_frame = ttk.Frame(notebook)
        notebook.add(standard_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.tabs.standard_voting', default="Standard Voting"))

        standard_content = ttk.Frame(standard_frame)
        standard_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(standard_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.standard_voting_configuration', default="Standard Voting Configuration"),
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        self.enable_standard_var = tk.BooleanVar(value=True)
        self.allow_writein_var = tk.BooleanVar()
        self.show_live_results_var = tk.BooleanVar()
        self.require_confirm_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(standard_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.enable_standard_voting_for_this_election', default="Enable standard voting for this election"), variable=self.enable_standard_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(standard_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.allow_write_in_candidates', default="Allow write-in candidates"), variable=self.allow_writein_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(standard_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.show_live_results_during_voting', default="Show live results during voting"), variable=self.show_live_results_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(standard_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.require_confirmation_before_submitting', default="Require confirmation before submitting"), variable=self.require_confirm_var).pack(anchor='w', pady=3)

        ttk.Label(standard_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.winning_criterion', default="\nWinning Criterion:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.winning_criterion_var = tk.IntVar(value=1)
        ttk.Radiobutton(standard_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.simple_plurality_most_votes_wins', default="Simple Plurality (most votes wins)"), variable=self.winning_criterion_var, value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(standard_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.absolute_majority_50_required_runoff_if_needed', default="Absolute Majority (>50% required, runoff if needed)"), variable=self.winning_criterion_var, value=2).pack(anchor='w', pady=2)

        # Ranked Choice tab
        rcv_frame = ttk.Frame(notebook)
        notebook.add(rcv_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.tabs.ranked_choice', default="Ranked Choice"))

        rcv_content = ttk.Frame(rcv_frame)
        rcv_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.ranked_choice_voting_configuration', default="Ranked Choice Voting Configuration"),
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        self.enable_rcv_var = tk.BooleanVar()
        self.allow_partial_var = tk.BooleanVar(value=True)
        self.show_runoff_viz_var = tk.BooleanVar()

        ttk.Checkbutton(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.enable_ranked_choice_voting_for_this_election', default="Enable ranked choice voting for this election"), variable=self.enable_rcv_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.allow_partial_rankings_don_t_require_ranking_all', default="Allow partial rankings (don't require ranking all)"), variable=self.allow_partial_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.show_instant_runoff_visualization', default="Show instant runoff visualization"), variable=self.show_runoff_viz_var).pack(anchor='w', pady=3)

        ttk.Label(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.maximum_rankings_allowed', default="\nMaximum Rankings Allowed:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.rank_spin = ttk.Spinbox(rcv_content, from_=3, to=10, width=10)
        self.rank_spin.pack(anchor='w')
        self.rank_spin.set(5)

        ttk.Label(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.elimination_method', default="\nElimination Method:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.elimination_var = tk.IntVar(value=1)
        ttk.Radiobutton(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.eliminate_one_candidate_per_round', default="Eliminate one candidate per round"), variable=self.elimination_var, value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.batch_elimination_all_below_threshold', default="Batch elimination (all below threshold)"), variable=self.elimination_var, value=2).pack(anchor='w', pady=2)

        ttk.Label(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.tie_breaking', default="\nTie Breaking:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.tiebreak_var = tk.IntVar(value=2)
        ttk.Radiobutton(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.random_selection', default="Random selection"), variable=self.tiebreak_var, value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.most_1st_place_votes', default="Most 1st place votes"), variable=self.tiebreak_var, value=2).pack(anchor='w', pady=2)
        ttk.Radiobutton(rcv_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.manual_review', default="Manual review"), variable=self.tiebreak_var, value=3).pack(anchor='w', pady=2)

        # Approval Voting tab
        approval_frame = ttk.Frame(notebook)
        notebook.add(approval_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.tabs.approval_voting', default="Approval Voting"))

        approval_content = ttk.Frame(approval_frame)
        approval_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(approval_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.approval_voting_configuration', default="Approval Voting Configuration"),
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))
        ttk.Label(approval_content, text=_vm().METHOD_SUPPORT[_vm().APPROVAL]['note'],
                  foreground='#a15c00', wraplength=780).pack(anchor='w', pady=(0, 10))

        self.enable_approval_var = tk.BooleanVar()
        self.show_approval_count_var = tk.BooleanVar(value=True)
        self.allow_abstain_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(approval_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.enable_approval_voting_for_this_election', default="Enable approval voting for this election"), variable=self.enable_approval_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(approval_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.show_number_of_approvals_for_each_candidate', default="Show number of approvals for each candidate"), variable=self.show_approval_count_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(approval_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.allow_abstaining_approve_none', default="Allow abstaining (approve none)"), variable=self.allow_abstain_var).pack(anchor='w', pady=3)

        ttk.Label(approval_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.approval_limit', default="\nApproval Limit:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.approval_limit_var = tk.IntVar(value=1)
        ttk.Radiobutton(approval_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.unlimited_approve_as_many_as_you_want', default="Unlimited (approve as many as you want)"), variable=self.approval_limit_var, value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(approval_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.limited_to_specific_number', default="Limited to specific number:"), variable=self.approval_limit_var, value=2).pack(anchor='w', pady=2)

        self.limit_spin = ttk.Spinbox(approval_content, from_=1, to=10, width=10)
        self.limit_spin.pack(anchor='w', padx=30)
        self.limit_spin.set(3)

        ttk.Label(approval_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.results_display', default="\nResults Display:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.results_display_var = tk.IntVar(value=3)
        ttk.Radiobutton(approval_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.show_approval_count', default="Show approval count"), variable=self.results_display_var, value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(approval_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.show_approval_percentage', default="Show approval percentage"), variable=self.results_display_var, value=2).pack(anchor='w', pady=2)
        ttk.Radiobutton(approval_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.show_both', default="Show both"), variable=self.results_display_var, value=3).pack(anchor='w', pady=2)

        # Advanced tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.tabs.advanced_settings', default="Advanced Settings"))

        advanced_content = ttk.Frame(advanced_frame)
        advanced_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(advanced_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.advanced_configuration', default="Advanced Configuration"),
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        ttk.Label(advanced_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.voting_period', default="Voting Period:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))

        period_frame = ttk.Frame(advanced_content)
        period_frame.pack(anchor='w', pady=5)
        ttk.Label(period_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.start', default="Start:")).pack(side='left', padx=(0, 5))
        self.start_date_entry = ttk.Entry(period_frame, width=15)
        self.start_date_entry.pack(side='left', padx=(0, 15))
        ttk.Label(period_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.end', default="End:")).pack(side='left', padx=(0, 5))
        self.end_date_entry = ttk.Entry(period_frame, width=15)
        self.end_date_entry.pack(side='left')

        ttk.Label(advanced_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.security_options', default="\nSecurity Options:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.require_2fa_var = tk.BooleanVar()
        self.unique_code_var = tk.BooleanVar()
        self.vote_verify_var = tk.BooleanVar()
        self.allow_change_var = tk.BooleanVar()
        ttk.Checkbutton(advanced_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.require_two_factor_authentication_for_voting', default="Require two-factor authentication for voting"), variable=self.require_2fa_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.generate_unique_verification_code_for_each_voter', default="Generate unique verification code for each voter"), variable=self.unique_code_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.enable_vote_verification_voters_can_check_their_vote_was_counted', default="Enable vote verification (voters can check their vote was counted)"), variable=self.vote_verify_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.allow_vote_change_before_deadline', default="Allow vote change before deadline"), variable=self.allow_change_var).pack(anchor='w', pady=2)

        ttk.Label(advanced_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.accessibility', default="\nAccessibility:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.screen_reader_var = tk.BooleanVar()
        self.audio_ballot_var = tk.BooleanVar()
        self.extended_time_var = tk.BooleanVar()
        ttk.Checkbutton(advanced_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.enable_screen_reader_support', default="Enable screen reader support"), variable=self.screen_reader_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.provide_audio_ballot_option', default="Provide audio ballot option"), variable=self.audio_ballot_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.allow_extended_time_for_voting', default="Allow extended time for voting"), variable=self.extended_time_var).pack(anchor='w', pady=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.save_configuration', default="Save Configuration"), command=self.save_config).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.load_template', default="Load Template"), command=self.load_template).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.preview_ballot', default="Preview Ballot"), command=self.preview_ballot).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def _determine_voting_method(self):
        """Determine which voting method is currently configured."""
        if self.enable_rcv_var.get():
            return "Ranked Choice"
        elif self.enable_approval_var.get():
            return "Approval Voting"
        else:
            return "Simple Majority"

    def load_elections(self):
        try:
            conn = _vm_conn()
            try:
                rows = _vm().elections(conn)
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"), f"Failed to load elections: {e}", parent=self.dialog)
            return
        self.election_data = {_election_label(e): e for e in rows}
        self.election_combo['values'] = list(self.election_data)
        if rows:
            self.election_combo.current(0)
            self.load_election_config()
        else:
            self.election_combo.set("No elections have been set up yet")

    def _selected_election(self):
        return self.election_data.get(self.election_combo.get())

    def load_election_config(self):
        """Show the stored configuration for the selected election."""
        election = self._selected_election()
        if not election:
            return
        vm = _vm()
        try:
            conn = _vm_conn()
            try:
                cfg = vm.election_config(conn, election['election_id'])
                row = conn.execute("SELECT value FROM union_voting_settings WHERE key = ?",
                                   (f"election_options:{election['election_id']}",)).fetchone() \
                    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='union_voting_settings'").fetchone() else None
            finally:
                conn.close()
        except sqlite3.Error:
            return
        self.enable_rcv_var.set(cfg['method'] == vm.RANKED)
        self.enable_approval_var.set(cfg['method'] == vm.APPROVAL)
        self.enable_standard_var.set(cfg['method'] == vm.SIMPLE)
        self.allow_abstain_var.set(cfg['allow_abstain'])
        self.allow_partial_var.set(not cfg['require_full_ranking'])
        if cfg['method'] == vm.RANKED and cfg['max_choices']:
            self.rank_spin.set(cfg['max_choices'])
        try:
            options = json.loads(row[0]) if row and row[0] else {}
        except ValueError:
            options = {}
        for name in self._OPTION_VARS:
            if name in options and hasattr(self, name):
                try:
                    getattr(self, name).set(options[name])
                except (tk.TclError, ValueError):
                    pass
        for entry, value in ((self.start_date_entry, election.get('voting_start')),
                             (self.end_date_entry, election.get('voting_end'))):
            entry.delete(0, tk.END)
            entry.insert(0, (value or '')[:10])

    def save_config(self):
        """Save the current voting method configuration to the database."""
        election = self._selected_election()
        if not election:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.no_election', default="No Election"), _t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.please_select_an_election_first', default="Please select an election first."), parent=self.dialog)
            return
        if self.enable_rcv_var.get() and self.enable_approval_var.get():
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"),
                                   "Choose one voting method: ranked choice and approval are both ticked.", parent=self.dialog)
            return

        vm = _vm()
        voting_method = self._determine_voting_method()
        method = vm.method_from_label(voting_method)
        allow_abstain = self.allow_abstain_var.get()
        require_ranked = self.enable_rcv_var.get() and not self.allow_partial_var.get()
        max_choices = int(self.rank_spin.get()) if self.enable_rcv_var.get() else 0

        start = self.start_date_entry.get().strip()
        end = self.end_date_entry.get().strip()
        for value in (start, end):
            if value:
                try:
                    datetime.strptime(value, '%Y-%m-%d')
                except ValueError:
                    messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"),
                                           "Voting period dates must be YYYY-MM-DD.", parent=self.dialog)
                    return
        if start and end and end < start:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"),
                                   "The voting period ends before it starts.", parent=self.dialog)
            return

        created_by = (self.auth.current_user or {}).get("username", "") if self.auth else ""
        options = {}
        for name in self._OPTION_VARS:
            if hasattr(self, name):
                options[name] = getattr(self, name).get()
        try:
            conn = _vm_conn()
            try:
                vm.save_election_config(conn, election_id=election['election_id'], method=method,
                                        allow_abstain=allow_abstain, require_full_ranking=require_ranked,
                                        max_choices=max_choices, updated_by=created_by)
                conn.execute("CREATE TABLE IF NOT EXISTS union_voting_settings (key TEXT PRIMARY KEY, value TEXT)")
                conn.execute("INSERT OR REPLACE INTO union_voting_settings (key, value) VALUES (?, ?)",
                             (f"election_options:{election['election_id']}", json.dumps(options)))
                if start or end:
                    # start_date/end_date mirror the voting window on `elections`.
                    conn.execute("UPDATE elections SET voting_start = COALESCE(?, voting_start), "
                                 "voting_end = COALESCE(?, voting_end), "
                                 "start_date = COALESCE(?, voting_start, start_date), "
                                 "end_date = COALESCE(?, voting_end, end_date) WHERE id = ?",
                                 (start or None, end or None, start or None, end or None,
                                  election['election_id']))
                conn.commit()
            finally:
                conn.close()
        except ValueError as e:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"), str(e), parent=self.dialog)
            return
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"), f"Failed to save configuration: {e}", parent=self.dialog)
            return

        messagebox.showinfo(
            _t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.configuration_saved', default="Configuration Saved"),
            f"Voting method configuration saved.\n\n"
            f"Election: {election['position']}\n"
            f"Method: {vm.METHOD_LABELS[method]}\n"
            f"Allow Abstain: {'Yes' if allow_abstain else 'No'}\n"
            f"Require Full Ranking: {'Yes' if require_ranked else 'No'}\n"
            f"Max Rankings: {max_choices if max_choices else 'All candidates'}\n\n"
            "Ballots enforce the method, full-ranking and maximum-rank rules. The other "
            "options are recorded with the election for the returning officer.",
            parent=self.dialog)
        self.load_elections()

    def load_template(self):
        """Show a dialog with predefined voting configuration templates."""
        template_win = tk.Toplevel(self.dialog)
        template_win.title(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.windows.load_voting_template', default="Load Voting Template"))
        template_win.geometry("500x420")
        template_win.transient(self.dialog)
        template_win.grab_set()

        ttk.Label(template_win, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.select_a_voting_template', default="Select a Voting Template"),
                  font=('Arial', 12, 'bold')).pack(pady=(15, 10))

        templates = {
            "Simple Majority": {
                "description": "Traditional single-choice voting. Candidate with the most votes wins.",
                "enable_standard": True, "enable_rcv": False, "enable_approval": False,
                "allow_abstain": False, "allow_partial": False, "max_rankings": 3,
                "approval_limit": 1, "approval_limit_mode": 1, "winning_criterion": 1,
            },
            "Ranked Choice": {
                "description": "Voters rank candidates in order of preference. Eliminates lowest and redistributes until majority.",
                "enable_standard": False, "enable_rcv": True, "enable_approval": False,
                "allow_abstain": True, "allow_partial": True, "max_rankings": 5,
                "approval_limit": 3, "approval_limit_mode": 1, "winning_criterion": 2,
            },
            "Approval Voting": {
                "description": "Voters approve as many candidates as they like. Most approvals wins.",
                "enable_standard": False, "enable_rcv": False, "enable_approval": True,
                "allow_abstain": True, "allow_partial": False, "max_rankings": 3,
                "approval_limit": 3, "approval_limit_mode": 1, "winning_criterion": 1,
            },
            "Two-Round System": {
                "description": "Standard voting requiring absolute majority (>50%). If no majority, top two go to runoff.",
                "enable_standard": True, "enable_rcv": False, "enable_approval": False,
                "allow_abstain": True, "allow_partial": False, "max_rankings": 3,
                "approval_limit": 3, "approval_limit_mode": 1, "winning_criterion": 2,
            },
        }

        selected_var = tk.StringVar(value="")

        list_frame = ttk.Frame(template_win)
        list_frame.pack(fill='both', expand=True, padx=15, pady=5)

        desc_label = ttk.Label(list_frame, text="", wraplength=440, justify='left',
                               font=('Arial', 9))
        desc_label.pack(side='bottom', fill='x', pady=(10, 0))

        for name, info in templates.items():
            ttk.Radiobutton(
                list_frame, text=name, variable=selected_var, value=name,
                command=lambda n=name: desc_label.config(text=templates[n]["description"])
            ).pack(anchor='w', pady=4)

        def apply_template():
            chosen = selected_var.get()
            if not chosen:
                messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.no_selection', default="No Selection"), _t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.please_select_a_template', default="Please select a template."), parent=template_win)
                return
            t = templates[chosen]
            self.enable_standard_var.set(t["enable_standard"])
            self.enable_rcv_var.set(t["enable_rcv"])
            self.enable_approval_var.set(t["enable_approval"])
            self.allow_abstain_var.set(t["allow_abstain"])
            self.allow_partial_var.set(t["allow_partial"])
            self.rank_spin.set(t["max_rankings"])
            self.limit_spin.set(t["approval_limit"])
            self.approval_limit_var.set(t["approval_limit_mode"])
            self.winning_criterion_var.set(t["winning_criterion"])
            template_win.destroy()
            messagebox.showinfo(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.template_loaded', default="Template Loaded"),
                                f"'{chosen}' template has been applied.\n\n"
                                "Review the settings and click Save Configuration when ready.")

        btn_frame = ttk.Frame(template_win)
        btn_frame.pack(fill='x', padx=15, pady=(5, 15))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.apply_template', default="Apply Template"), command=apply_template).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.cancel', default="Cancel"), command=template_win.destroy).pack(side='right')

    def preview_ballot(self):
        """Show a Toplevel window that simulates the ballot appearance."""
        election = self._selected_election()
        if not election:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.no_election', default="No Election"), _t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.please_select_an_election_first', default="Please select an election first."), parent=self.dialog)
            return
        election_name = election['position'] or f"Election {election['election_id']}"
        voting_method = self._determine_voting_method()

        try:
            conn = _vm_conn()
            try:
                candidates = [{"id": c['candidate_id'], "name": c['name'], "manifesto": c['manifesto'] or ""}
                              for c in _vm().candidates(conn, election['election_id'])]
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.dialogs.error', default="Error"), f"Failed to load candidates: {e}", parent=self.dialog)
            return

        if not candidates:
            messagebox.showinfo(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.windows.ballot_preview', default="Ballot Preview"),
                                f"No candidates are standing for {election_name} yet, so the ballot would be empty.",
                                parent=self.dialog)
            return

        preview_win = tk.Toplevel(self.dialog)
        preview_win.title(_t('gui.pastoral.student_union_gui.elections.election_voting_methods.windows.ballot_preview', default="Ballot Preview"))
        preview_win.geometry("550x600")
        preview_win.transient(self.dialog)
        preview_win.grab_set()

        # Outer ballot container
        outer = ttk.Frame(preview_win)
        outer.pack(fill='both', expand=True, padx=20, pady=15)

        # Preview warning banner
        warn_frame = tk.Frame(outer, bg="#fff3cd")
        warn_frame.pack(fill='x', pady=(0, 10))
        tk.Label(warn_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.this_is_a_preview_only_no_votes_will_be_recorded', default="THIS IS A PREVIEW ONLY - No votes will be recorded"),
                 bg="#fff3cd", fg="#856404", font=('Arial', 10, 'bold'),
                 pady=6).pack()

        # Ballot header
        header_frame = ttk.LabelFrame(outer, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.official_ballot', default="Official Ballot"))
        header_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(header_frame, text=election_name,
                  font=('Arial', 13, 'bold')).pack(pady=(10, 2))
        ttk.Label(header_frame, text=f"Voting Method: {voting_method}",
                  font=('Arial', 10)).pack(pady=(0, 5))

        # Instructions based on method
        if voting_method == "Ranked Choice":
            max_ranks = int(self.rank_spin.get())
            instructions = (f"Rank up to {max_ranks} candidates in order of preference.\n"
                            "1 = most preferred.")
        elif voting_method == "Approval Voting":
            if self.approval_limit_var.get() == 2:
                limit = int(self.limit_spin.get())
                instructions = f"Select up to {limit} candidates you approve of."
            else:
                instructions = "Select all candidates you approve of."
        else:
            instructions = "Select ONE candidate for this position."

        ttk.Label(header_frame, text=instructions, wraplength=460,
                  font=('Arial', 9, 'italic'), justify='center').pack(pady=(0, 10))

        ttk.Separator(outer, orient='horizontal').pack(fill='x', pady=5)

        # Candidate list
        canvas = tk.Canvas(outer)
        scrollbar = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        cand_frame = ttk.Frame(canvas)

        cand_frame.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=cand_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        if voting_method == "Ranked Choice":
            max_ranks = int(self.rank_spin.get())
            rank_options = ["--"] + [str(i) for i in range(1, max_ranks + 1)]
            for cand in candidates:
                row_frame = ttk.Frame(cand_frame)
                row_frame.pack(fill='x', padx=10, pady=6)

                info_f = ttk.Frame(row_frame)
                info_f.pack(side='left', fill='x', expand=True)
                ttk.Label(info_f, text=cand["name"],
                          font=('Arial', 10, 'bold')).pack(anchor='w')
                if cand["manifesto"]:
                    ttk.Label(info_f, text=cand["manifesto"],
                              font=('Arial', 9)).pack(anchor='w')

                combo = ttk.Combobox(row_frame, values=rank_options, width=5, state='readonly')
                combo.current(0)
                combo.pack(side='right', padx=5)
                ttk.Label(row_frame, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.rank', default="Rank:")).pack(side='right')

        elif voting_method == "Approval Voting":
            for cand in candidates:
                row_frame = ttk.Frame(cand_frame)
                row_frame.pack(fill='x', padx=10, pady=6)

                cb = ttk.Checkbutton(row_frame, text="")
                cb.pack(side='left', padx=(0, 5))

                info_f = ttk.Frame(row_frame)
                info_f.pack(side='left', fill='x', expand=True)
                ttk.Label(info_f, text=cand["name"],
                          font=('Arial', 10, 'bold')).pack(anchor='w')
                if cand["manifesto"]:
                    ttk.Label(info_f, text=cand["manifesto"],
                              font=('Arial', 9)).pack(anchor='w')

        else:
            # Simple Majority — radio buttons
            preview_choice = tk.IntVar(value=0)
            for cand in candidates:
                row_frame = ttk.Frame(cand_frame)
                row_frame.pack(fill='x', padx=10, pady=6)

                rb = ttk.Radiobutton(row_frame, variable=preview_choice,
                                     value=cand["id"], text="")
                rb.pack(side='left', padx=(0, 5))

                info_f = ttk.Frame(row_frame)
                info_f.pack(side='left', fill='x', expand=True)
                ttk.Label(info_f, text=cand["name"],
                          font=('Arial', 10, 'bold')).pack(anchor='w')
                if cand["manifesto"]:
                    ttk.Label(info_f, text=cand["manifesto"],
                              font=('Arial', 9)).pack(anchor='w')

            if self.allow_abstain_var.get():
                sep = ttk.Separator(cand_frame, orient='horizontal')
                sep.pack(fill='x', padx=10, pady=6)
                ttk.Radiobutton(cand_frame, variable=preview_choice,
                                value=0, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.abstain', default="Abstain")).pack(anchor='w', padx=10)

        ttk.Separator(outer, orient='horizontal').pack(fill='x', pady=8)

        # Disabled submit button (preview only)
        ttk.Button(outer, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.submit_ballot_disabled_in_preview', default="Submit Ballot (disabled in preview)"),
                   state='disabled').pack(pady=(0, 5))

        # Footer
        ttk.Label(outer, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.labels.this_is_a_preview_only_no_votes_are_cast', default="This is a preview only. No votes are cast."),
                  font=('Arial', 9, 'italic'), foreground='gray').pack(pady=(0, 5))

        ttk.Button(outer, text=_t('gui.pastoral.student_union_gui.elections.election_voting_methods.buttons.close_preview', default="Close Preview"),
                   command=preview_win.destroy).pack(pady=(0, 5))



def open_manage_enhanced_voting_dialog(self):
    """Open enhanced voting systems management"""
    dialog = ManageEnhancedVotingDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_ranked_choice_voting_dialog(self):
    """Open ranked choice voting"""
    dialog = RankedChoiceVotingDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_configure_voting_methods_dialog(self):
    """Open voting methods configuration"""
    dialog = ConfigureVotingMethodsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)
# FIFTH ROUND (PART 3C FINAL) - Facilities Approval

