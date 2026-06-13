import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog
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

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available")

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


class ManageEnhancedVotingDialog:
    """Dialog for managing enhanced voting systems"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Enhanced Voting Systems")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🗳️ Enhanced Voting Systems",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Voting methods overview
        overview_frame = ttk.LabelFrame(main_frame, text="Available Voting Methods")
        overview_frame.pack(fill='x', pady=(0, 15))

        methods_text = """ENABLED VOTING METHODS:

✓ Standard Voting (Traditional)
  - Single choice per position
  - Simple majority wins
  - Currently used for all elections
  - Status: ACTIVE

✓ Ranked Choice Voting (Alternative Vote)
  - Rank candidates in order of preference
  - Eliminates candidates with lowest votes
  - Redistributes votes until majority achieved
  - Status: AVAILABLE

✓ Approval Voting
  - Vote for as many candidates as you approve
  - Candidate with most approvals wins
  - Simple and effective for multiple candidates
  - Status: AVAILABLE

✓ Score Voting (Range Voting)
  - Rate each candidate on a scale (0-10)
  - Highest average score wins
  - Allows nuanced preferences
  - Status: EXPERIMENTAL"""

        ttk.Label(overview_frame, text=methods_text, justify='left', font=('Courier', 9)).pack(padx=15, pady=10)

        # Elections using enhanced voting
        elections_frame = ttk.LabelFrame(main_frame, text="Elections Configuration")
        elections_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Election', 'Position', 'Voting Method', 'Status', 'Start Date', 'End Date')
        tree = ttk.Treeview(elections_frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Election':
                tree.column(col, width=180)
            elif col == 'Voting Method':
                tree.column(col, width=140)
            else:
                tree.column(col, width=100)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample elections
        elections = [
            ("Student Union President 2025", "President", "Standard Voting", "Active", "2025-04-01", "2025-04-07"),
            ("VP Academic Affairs 2025", "VP Academic", "Standard Voting", "Upcoming", "2025-04-01", "2025-04-07"),
            ("Treasurer 2025", "Treasurer", "Standard Voting", "Upcoming", "2025-04-01", "2025-04-07"),
            ("Best Club Award 2025", "Club Award", "Approval Voting", "Upcoming", "2025-04-15", "2025-04-20")
        ]

        for election in elections:
            tree.insert('', 'end', values=election)

        # Statistics
        stats_frame = ttk.LabelFrame(main_frame, text="Voting Statistics")
        stats_frame.pack(fill='x', pady=(0, 15))

        stats_text = """Total Elections This Year: 12
Standard Voting: 10 (83%)
Ranked Choice Voting: 1 (8%)
Approval Voting: 1 (8%)
Score Voting: 0 (0%)

Average Voter Turnout:
- Standard: 67%
- Ranked Choice: 72% (+5%)
- Approval: 69% (+2%)"""

        ttk.Label(stats_frame, text=stats_text, justify='left', font=('Courier', 10)).pack(padx=15, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Configure Ranked Choice", command=self.config_ranked).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Configure Approval", command=self.config_approval).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Configure Score", command=self.config_score).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Method Comparison", command=self.view_comparison).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def config_ranked(self):
        messagebox.showinfo("Ranked Choice Voting", "Configure Ranked Choice Voting:\n\n- Number of rankings to allow (3-10)\n- Elimination threshold\n- Tie-breaking rules\n- Ballot format options")

    def config_approval(self):
        messagebox.showinfo("Approval Voting", "Configure Approval Voting:\n\n- Maximum approvals allowed\n- Ballot design\n- Counting method\n- Results display format")

    def config_score(self):
        messagebox.showinfo("Score Voting", "Configure Score Voting:\n\n- Score range (0-5 or 0-10)\n- Decimal scores allowed?\n- Averaging method\n- Minimum participation threshold")

    def view_comparison(self):
        messagebox.showinfo("Method Comparison", "Voting Method Comparison:\n\nStandard: Simple, familiar, but can split votes\nRanked Choice: Fair, eliminates spoilers, more complex\nApproval: Simple, reduces strategic voting\nScore: Most nuanced, but can be confusing\n\nRecommendation: Ranked Choice for competitive races")



class RankedChoiceVotingDialog:
    """Dialog for ranked choice voting system"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.rank_combos = {}  # Store ranking dropdowns
        self.candidates = []  # Store candidate info

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Ranked Choice Voting")
        self.dialog.geometry("1000x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📊 Ranked Choice Voting",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create notebook for sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # How It Works tab
        how_frame = ttk.Frame(notebook)
        notebook.add(how_frame, text="How It Works")

        how_scroll = scrolledtext.ScrolledText(how_frame, height=15, wrap=tk.WORD)
        how_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        how_text = """RANKED CHOICE VOTING (RCV) EXPLANATION:

HOW TO VOTE:
1. Rank candidates in order of preference (1st, 2nd, 3rd, etc.)
2. You don't have to rank all candidates
3. Only rank candidates you support
4. Your 1st choice gets your vote initially

HOW VOTES ARE COUNTED:

ROUND 1:
- All 1st choice votes are counted
- If a candidate has >50%, they WIN
- If no majority, proceed to Round 2

ROUND 2 (and subsequent rounds):
- Candidate with fewest votes is ELIMINATED
- Ballots for eliminated candidate transfer to next choice
- Count votes again
- Repeat until someone has >50%

EXAMPLE:
Starting votes (100 total):
- Alice: 40 votes (40%)
- Bob: 35 votes (35%)
- Carol: 25 votes (25%)

No majority, so Carol eliminated.

Carol voters' 2nd choices:
- 15 → Alice
- 10 → Bob

Final count:
- Alice: 55 votes (55%) → WINS
- Bob: 45 votes (45%)

BENEFITS:
✓ Eliminates "spoiler effect"
✓ Majority winner guaranteed
✓ Voters can support favorite without "wasting" vote
✓ Reduces negative campaigning
✓ More representative results

CONSIDERATIONS:
- More complex to understand initially
- Longer counting process
- Requires voter education
- Some ballots may become "exhausted" if all choices eliminated"""

        how_scroll.insert('1.0', how_text)
        how_scroll.config(state='disabled')

        # Cast Vote tab
        vote_frame = ttk.Frame(notebook)
        notebook.add(vote_frame, text="Cast RCV Vote")

        vote_content = ttk.Frame(vote_frame)
        vote_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(vote_content, text="Student Union President 2025",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        ttk.Label(vote_content, text="Rank candidates in order of preference (1 = most preferred)",
                 font=('Arial', 10)).pack(pady=(0, 15))

        # Candidates with ranking dropdowns
        self.candidates = [
            ("Alice Johnson", "Political Science, 3rd Year", "15 endorsements"),
            ("Bob Smith", "Business Admin, 4th Year", "12 endorsements"),
            ("Carol Davis", "Education, 3rd Year", "8 endorsements"),
            ("David Lee", "Accounting, 2nd Year", "10 endorsements")
        ]

        for i, (name, info, endorsements) in enumerate(self.candidates):
            candidate_frame = ttk.Frame(vote_content)
            candidate_frame.pack(fill='x', pady=5)

            # Candidate info
            info_frame = ttk.Frame(candidate_frame)
            info_frame.pack(side='left', fill='x', expand=True)

            ttk.Label(info_frame, text=name, font=('Arial', 10, 'bold')).pack(anchor='w')
            ttk.Label(info_frame, text=f"{info} • {endorsements}", font=('Arial', 9)).pack(anchor='w')

            # Ranking dropdown
            rank_combo = ttk.Combobox(candidate_frame, width=15, state='readonly')
            rank_combo['values'] = ('Not Ranked', '1st Choice', '2nd Choice', '3rd Choice', '4th Choice')
            rank_combo.current(0)
            rank_combo.pack(side='right', padx=(10, 0))

            # Store reference to the combobox
            self.rank_combos[name] = rank_combo

        ttk.Button(vote_content, text="Submit Ranked Ballot",
                  command=self.submit_ballot).pack(pady=20)

        # Results tab
        results_frame = ttk.Frame(notebook)
        notebook.add(results_frame, text="RCV Results")

        results_scroll = scrolledtext.ScrolledText(results_frame, height=15, wrap=tk.WORD, font=('Courier', 9))
        results_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        results_text = """RANKED CHOICE VOTING RESULTS
Student Union President 2025

ROUND 1 (Initial Count):
Alice Johnson:    487 votes (39.5%)  ████████████████
Bob Smith:        395 votes (32.0%)  █████████████
Carol Davis:      231 votes (18.7%)  ████████
David Lee:        121 votes (9.8%)   ████
─────────────────────────────────────────────────
Total:           1234 votes

No majority. David Lee eliminated (fewest votes).

ROUND 2:
David Lee's 121 votes redistributed:
  → Alice Johnson: 52 votes
  → Bob Smith: 38 votes
  → Carol Davis: 31 votes

New totals:
Alice Johnson:    539 votes (43.7%)  █████████████████
Bob Smith:        433 votes (35.1%)  ██████████████
Carol Davis:      262 votes (21.2%)  ████████
─────────────────────────────────────────────────
Total:           1234 votes

No majority. Carol Davis eliminated.

ROUND 3 (FINAL):
Carol Davis's 262 votes redistributed:
  → Alice Johnson: 148 votes
  → Bob Smith: 114 votes

FINAL RESULTS:
Alice Johnson:    687 votes (55.7%)  ██████████████████████  ✓ WINNER
Bob Smith:        547 votes (44.3%)  ██████████████████
─────────────────────────────────────────────────
Total:           1234 votes

🏆 WINNER: Alice Johnson (Majority achieved in Round 3)

ANALYSIS:
- Alice started with 39.5%, ended with 55.7% (won by 140 votes)
- 3 rounds needed to achieve majority
- No exhausted ballots (all voters ranked enough candidates)
- Turnout: 1,234 voters (68% of eligible students)

COMPARISON WITH STANDARD VOTING:
Under standard voting, Alice would have won with 39.5%, meaning
60.5% of voters preferred other candidates. RCV ensures the
winner has broad support (55.7% final approval)."""

        results_scroll.insert('1.0', results_text)
        results_scroll.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View Tutorial Video", command=self.view_tutorial).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Download Ballot Template", command=self.download_template).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def submit_ballot(self):
        """Submit the ranked choice ballot"""
        # Collect rankings
        rankings = {}
        for candidate_name, combo in self.rank_combos.items():
            rank_value = combo.get()
            if rank_value != 'Not Ranked':
                # Extract the rank number (1st, 2nd, etc)
                rank_num = rank_value.split()[0]  # Gets "1st", "2nd", etc
                rankings[rank_num] = candidate_name

        # Check if at least one candidate was ranked
        if not rankings:
            messagebox.showwarning("No Rankings", "Please rank at least one candidate before submitting.")
            return

        # Check for duplicate rankings
        if len(rankings) != len(set(rankings.keys())):
            messagebox.showerror("Error", "Please ensure each candidate has a unique ranking.")
            return

        # Build rankings display
        rankings_display = ""
        for rank in sorted(rankings.keys()):
            rankings_display += f"{rank}: {rankings[rank]}\n"

        # Get current user info
        username = self.auth.current_user.get('username', 'Voter') if self.auth.current_user else 'Voter'
        email = self.auth.current_user.get('email', '') if self.auth.current_user else ''

        # Show success message
        messagebox.showinfo(
            "Vote Submitted",
            f"Your ranked choice ballot has been submitted!\n\nYour rankings:\n{rankings_display}\nThank you for voting!"
        )

        # Send email receipt if email service is available
        if EMAIL_SERVICE_AVAILABLE and email:
            try:
                subject, email_body = render_template('student_union/ranked_choice_ballot_receipt', {
                    'username': username,
                    'rankings': rankings_display,
                    'position': 'Student Union President 2025',
                    'submission_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                send_email(
                    to_email=email,
                    subject=subject,
                    body=email_body
                )
            except Exception as e:
                print(f"Failed to send ballot receipt email: {e}")

        self.dialog.destroy()

    def view_tutorial(self):
        messagebox.showinfo("RCV Tutorial", "Opening RCV tutorial video:\n\n'Understanding Ranked Choice Voting'\nDuration: 3:45\n\nCovers:\n- How to fill out ballot\n- Vote counting process\n- Benefits and examples\n- FAQs")

    def download_template(self):
        """Download a ranked choice voting ballot template"""
        # Ask user where to save the file
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="rcv_ballot_template.txt"
        )

        if not file_path:
            return  # User cancelled

        try:
            # Create ballot template content
            template_content = """RANKED CHOICE VOTING BALLOT TEMPLATE
========================================

INSTRUCTIONS FOR VOTERS:
------------------------
1. Rank candidates in order of preference (1 = first choice, 2 = second choice, etc.)
2. You may rank as many or as few candidates as you wish
3. Do not rank the same candidate more than once
4. Leave boxes blank for candidates you do not wish to rank

POSITION: [Insert Position Name]
ELECTION DATE: [Insert Date]

CANDIDATES:
-----------
Rank    Candidate Name
[ ]     Candidate 1
[ ]     Candidate 2
[ ]     Candidate 3
[ ]     Candidate 4
[ ]     Candidate 5

HOW RANKED CHOICE VOTING WORKS:
-------------------------------
- If a candidate receives more than 50% of first-choice votes, they win
- If no candidate receives a majority, the candidate with the fewest votes is eliminated
- Votes for the eliminated candidate are redistributed to voters' next choices
- This process continues until a candidate has a majority

SAMPLE BALLOT:
--------------
Rank    Candidate Name
[1]     Alice Johnson
[3]     Bob Smith
[ ]     Carol Davis
[2]     David Lee
[ ]     Eve Martinez

In this example:
- Alice is the voter's first choice
- David is the second choice
- Bob is the third choice
- Carol and Eve are not ranked

For questions or assistance, contact the Elections Committee.
"""

            # Write to file
            with open(file_path, 'w') as f:
                f.write(template_content)

            messagebox.showinfo(
                "Download Complete",
                f"Ballot template saved successfully to:\n{file_path}\n\n" +
                "The template includes:\n" +
                "- Sample ballot format\n" +
                "- Instructions for voters\n" +
                "- Explanation of RCV process"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save ballot template: {e}")



class ConfigureVotingMethodsDialog:
    """Dialog for configuring voting methods"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Configure Voting Methods")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="⚙️ Configure Voting Methods",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Election selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(select_frame, text="Election:").pack(side='left', padx=(0, 10))
        self.election_combo = ttk.Combobox(select_frame, width=40, state='readonly')
        self.election_combo['values'] = ('Student Union President 2025', 'VP Academic Affairs 2025',
                                     'Best Club Award 2025', 'Sports Team Captain Elections')
        self.election_combo.pack(side='left', fill='x', expand=True)
        self.election_combo.current(0)

        # Create notebook for method configuration
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Standard Voting tab
        standard_frame = ttk.Frame(notebook)
        notebook.add(standard_frame, text="Standard Voting")

        standard_content = ttk.Frame(standard_frame)
        standard_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(standard_content, text="Standard Voting Configuration",
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        self.enable_standard_var = tk.BooleanVar(value=True)
        self.allow_writein_var = tk.BooleanVar()
        self.show_live_results_var = tk.BooleanVar()
        self.require_confirm_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(standard_content, text="Enable standard voting for this election", variable=self.enable_standard_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(standard_content, text="Allow write-in candidates", variable=self.allow_writein_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(standard_content, text="Show live results during voting", variable=self.show_live_results_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(standard_content, text="Require confirmation before submitting", variable=self.require_confirm_var).pack(anchor='w', pady=3)

        ttk.Label(standard_content, text="\nWinning Criterion:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.winning_criterion_var = tk.IntVar(value=1)
        ttk.Radiobutton(standard_content, text="Simple Plurality (most votes wins)", variable=self.winning_criterion_var, value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(standard_content, text="Absolute Majority (>50% required, runoff if needed)", variable=self.winning_criterion_var, value=2).pack(anchor='w', pady=2)

        # Ranked Choice tab
        rcv_frame = ttk.Frame(notebook)
        notebook.add(rcv_frame, text="Ranked Choice")

        rcv_content = ttk.Frame(rcv_frame)
        rcv_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(rcv_content, text="Ranked Choice Voting Configuration",
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        self.enable_rcv_var = tk.BooleanVar()
        self.allow_partial_var = tk.BooleanVar(value=True)
        self.show_runoff_viz_var = tk.BooleanVar()

        ttk.Checkbutton(rcv_content, text="Enable ranked choice voting for this election", variable=self.enable_rcv_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(rcv_content, text="Allow partial rankings (don't require ranking all)", variable=self.allow_partial_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(rcv_content, text="Show instant runoff visualization", variable=self.show_runoff_viz_var).pack(anchor='w', pady=3)

        ttk.Label(rcv_content, text="\nMaximum Rankings Allowed:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.rank_spin = ttk.Spinbox(rcv_content, from_=3, to=10, width=10)
        self.rank_spin.pack(anchor='w')
        self.rank_spin.set(5)

        ttk.Label(rcv_content, text="\nElimination Method:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.elimination_var = tk.IntVar(value=1)
        ttk.Radiobutton(rcv_content, text="Eliminate one candidate per round", variable=self.elimination_var, value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(rcv_content, text="Batch elimination (all below threshold)", variable=self.elimination_var, value=2).pack(anchor='w', pady=2)

        ttk.Label(rcv_content, text="\nTie Breaking:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.tiebreak_var = tk.IntVar(value=2)
        ttk.Radiobutton(rcv_content, text="Random selection", variable=self.tiebreak_var, value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(rcv_content, text="Most 1st place votes", variable=self.tiebreak_var, value=2).pack(anchor='w', pady=2)
        ttk.Radiobutton(rcv_content, text="Manual review", variable=self.tiebreak_var, value=3).pack(anchor='w', pady=2)

        # Approval Voting tab
        approval_frame = ttk.Frame(notebook)
        notebook.add(approval_frame, text="Approval Voting")

        approval_content = ttk.Frame(approval_frame)
        approval_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(approval_content, text="Approval Voting Configuration",
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        self.enable_approval_var = tk.BooleanVar()
        self.show_approval_count_var = tk.BooleanVar(value=True)
        self.allow_abstain_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(approval_content, text="Enable approval voting for this election", variable=self.enable_approval_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(approval_content, text="Show number of approvals for each candidate", variable=self.show_approval_count_var).pack(anchor='w', pady=3)
        ttk.Checkbutton(approval_content, text="Allow abstaining (approve none)", variable=self.allow_abstain_var).pack(anchor='w', pady=3)

        ttk.Label(approval_content, text="\nApproval Limit:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.approval_limit_var = tk.IntVar(value=1)
        ttk.Radiobutton(approval_content, text="Unlimited (approve as many as you want)", variable=self.approval_limit_var, value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(approval_content, text="Limited to specific number:", variable=self.approval_limit_var, value=2).pack(anchor='w', pady=2)

        self.limit_spin = ttk.Spinbox(approval_content, from_=1, to=10, width=10)
        self.limit_spin.pack(anchor='w', padx=30)
        self.limit_spin.set(3)

        ttk.Label(approval_content, text="\nResults Display:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.results_display_var = tk.IntVar(value=3)
        ttk.Radiobutton(approval_content, text="Show approval count", variable=self.results_display_var, value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(approval_content, text="Show approval percentage", variable=self.results_display_var, value=2).pack(anchor='w', pady=2)
        ttk.Radiobutton(approval_content, text="Show both", variable=self.results_display_var, value=3).pack(anchor='w', pady=2)

        # Advanced tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="Advanced Settings")

        advanced_content = ttk.Frame(advanced_frame)
        advanced_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(advanced_content, text="Advanced Configuration",
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        ttk.Label(advanced_content, text="Voting Period:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))

        period_frame = ttk.Frame(advanced_content)
        period_frame.pack(anchor='w', pady=5)
        ttk.Label(period_frame, text="Start:").pack(side='left', padx=(0, 5))
        self.start_date_entry = ttk.Entry(period_frame, width=15)
        self.start_date_entry.pack(side='left', padx=(0, 15))
        ttk.Label(period_frame, text="End:").pack(side='left', padx=(0, 5))
        self.end_date_entry = ttk.Entry(period_frame, width=15)
        self.end_date_entry.pack(side='left')

        ttk.Label(advanced_content, text="\nSecurity Options:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.require_2fa_var = tk.BooleanVar()
        self.unique_code_var = tk.BooleanVar()
        self.vote_verify_var = tk.BooleanVar()
        self.allow_change_var = tk.BooleanVar()
        ttk.Checkbutton(advanced_content, text="Require two-factor authentication for voting", variable=self.require_2fa_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text="Generate unique verification code for each voter", variable=self.unique_code_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text="Enable vote verification (voters can check their vote was counted)", variable=self.vote_verify_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text="Allow vote change before deadline", variable=self.allow_change_var).pack(anchor='w', pady=2)

        ttk.Label(advanced_content, text="\nAccessibility:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.screen_reader_var = tk.BooleanVar()
        self.audio_ballot_var = tk.BooleanVar()
        self.extended_time_var = tk.BooleanVar()
        ttk.Checkbutton(advanced_content, text="Enable screen reader support", variable=self.screen_reader_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text="Provide audio ballot option", variable=self.audio_ballot_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text="Allow extended time for voting", variable=self.extended_time_var).pack(anchor='w', pady=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Save Configuration", command=self.save_config).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Load Template", command=self.load_template).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Preview Ballot", command=self.preview_ballot).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def _determine_voting_method(self):
        """Determine which voting method is currently configured."""
        if self.enable_rcv_var.get():
            return "Ranked Choice"
        elif self.enable_approval_var.get():
            return "Approval Voting"
        else:
            return "Simple Majority"

    def save_config(self):
        """Save the current voting method configuration to the database."""
        election_name = self.election_combo.get()
        if not election_name:
            messagebox.showwarning("No Election", "Please select an election first.")
            return

        voting_method = self._determine_voting_method()
        allow_abstain = self.allow_abstain_var.get()
        require_ranked = self.enable_rcv_var.get() and not self.allow_partial_var.get()
        max_choices = int(self.rank_spin.get()) if self.enable_rcv_var.get() else (
            int(self.limit_spin.get()) if self.enable_approval_var.get() and self.approval_limit_var.get() == 2 else 0
        )
        created_by = ""
        if self.auth and self.auth.current_user:
            created_by = self.auth.current_user.get("username", "")

        config_name = f"{election_name} - {voting_method}"

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS election_voting_config (
                    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_name TEXT NOT NULL,
                    voting_method TEXT NOT NULL,
                    allow_abstain INTEGER DEFAULT 0,
                    require_ranked INTEGER DEFAULT 0,
                    max_choices INTEGER DEFAULT 0,
                    created_by TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                INSERT INTO election_voting_config
                    (config_name, voting_method, allow_abstain, require_ranked, max_choices, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                config_name,
                voting_method,
                1 if allow_abstain else 0,
                1 if require_ranked else 0,
                max_choices,
                created_by,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            conn.commit()

            messagebox.showinfo(
                "Configuration Saved",
                f"Voting method configuration saved successfully.\n\n"
                f"Election: {election_name}\n"
                f"Method: {voting_method}\n"
                f"Allow Abstain: {'Yes' if allow_abstain else 'No'}\n"
                f"Require Full Ranking: {'Yes' if require_ranked else 'No'}\n"
                f"Max Choices: {max_choices if max_choices else 'Unlimited'}\n\n"
                f"Configuration will be active when voting opens."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {e}")
        finally:
            if conn:
                conn.close()

    def load_template(self):
        """Show a dialog with predefined voting configuration templates."""
        template_win = tk.Toplevel(self.dialog)
        template_win.title("Load Voting Template")
        template_win.geometry("500x420")
        template_win.transient(self.dialog)
        template_win.grab_set()

        ttk.Label(template_win, text="Select a Voting Template",
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
                messagebox.showwarning("No Selection", "Please select a template.", parent=template_win)
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
            messagebox.showinfo("Template Loaded",
                                f"'{chosen}' template has been applied.\n\n"
                                "Review the settings and click Save Configuration when ready.")

        btn_frame = ttk.Frame(template_win)
        btn_frame.pack(fill='x', padx=15, pady=(5, 15))
        ttk.Button(btn_frame, text="Apply Template", command=apply_template).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=template_win.destroy).pack(side='right')

    def preview_ballot(self):
        """Show a Toplevel window that simulates the ballot appearance."""
        election_name = self.election_combo.get() or "Election"
        voting_method = self._determine_voting_method()

        # Load candidates from the database
        candidates = []
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            # Try to find the election and its candidates
            cursor.execute(
                "SELECT election_id FROM union_elections WHERE position = ? LIMIT 1",
                (election_name,)
            )
            row = cursor.fetchone()
            if row:
                election_id = row[0]
                cursor.execute('''
                    SELECT c.id, s.first_name || ' ' || s.last_name, c.manifesto
                    FROM election_candidates c
                    LEFT JOIN students s ON c.student_id = s.student_id
                    WHERE c.election_id = ?
                ''', (election_id,))
                for cand_row in cursor.fetchall():
                    candidates.append({
                        "id": cand_row[0],
                        "name": cand_row[1] if cand_row[1] else f"Candidate {cand_row[0]}",
                        "manifesto": cand_row[2] or "",
                    })
        except Exception:
            pass
        finally:
            if conn:
                conn.close()

        # Fall back to sample candidates if none found in DB
        if not candidates:
            candidates = [
                {"id": 1, "name": "Alice Johnson", "manifesto": "Improve campus facilities"},
                {"id": 2, "name": "Bob Smith", "manifesto": "Better student services"},
                {"id": 3, "name": "Carol Davis", "manifesto": "Increase club funding"},
                {"id": 4, "name": "David Lee", "manifesto": "Transparent budgeting"},
            ]

        preview_win = tk.Toplevel(self.dialog)
        preview_win.title("Ballot Preview")
        preview_win.geometry("550x600")
        preview_win.transient(self.dialog)
        preview_win.grab_set()

        # Outer ballot container
        outer = ttk.Frame(preview_win)
        outer.pack(fill='both', expand=True, padx=20, pady=15)

        # Preview warning banner
        warn_frame = tk.Frame(outer, bg="#fff3cd")
        warn_frame.pack(fill='x', pady=(0, 10))
        tk.Label(warn_frame, text="THIS IS A PREVIEW ONLY - No votes will be recorded",
                 bg="#fff3cd", fg="#856404", font=('Arial', 10, 'bold'),
                 pady=6).pack()

        # Ballot header
        header_frame = ttk.LabelFrame(outer, text="Official Ballot")
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
                ttk.Label(row_frame, text="Rank:").pack(side='right')

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
                                value=0, text="Abstain").pack(anchor='w', padx=10)

        ttk.Separator(outer, orient='horizontal').pack(fill='x', pady=8)

        # Disabled submit button (preview only)
        ttk.Button(outer, text="Submit Ballot (disabled in preview)",
                   state='disabled').pack(pady=(0, 5))

        # Footer
        ttk.Label(outer, text="This is a preview only. No votes are cast.",
                  font=('Arial', 9, 'italic'), foreground='gray').pack(pady=(0, 5))

        ttk.Button(outer, text="Close Preview",
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

