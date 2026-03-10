import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog
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

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available")

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
        election_combo = ttk.Combobox(select_frame, width=40, state='readonly')
        election_combo['values'] = ('Student Union President 2025', 'VP Academic Affairs 2025',
                                     'Best Club Award 2025', 'Sports Team Captain Elections')
        election_combo.pack(side='left', fill='x', expand=True)
        election_combo.current(0)

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

        ttk.Checkbutton(standard_content, text="Enable standard voting for this election").pack(anchor='w', pady=3)
        ttk.Checkbutton(standard_content, text="Allow write-in candidates").pack(anchor='w', pady=3)
        ttk.Checkbutton(standard_content, text="Show live results during voting").pack(anchor='w', pady=3)
        ttk.Checkbutton(standard_content, text="Require confirmation before submitting").pack(anchor='w', pady=3)

        ttk.Label(standard_content, text="\nWinning Criterion:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        ttk.Radiobutton(standard_content, text="Simple Plurality (most votes wins)", value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(standard_content, text="Absolute Majority (>50% required, runoff if needed)", value=2).pack(anchor='w', pady=2)

        # Ranked Choice tab
        rcv_frame = ttk.Frame(notebook)
        notebook.add(rcv_frame, text="Ranked Choice")

        rcv_content = ttk.Frame(rcv_frame)
        rcv_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(rcv_content, text="Ranked Choice Voting Configuration",
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        ttk.Checkbutton(rcv_content, text="Enable ranked choice voting for this election").pack(anchor='w', pady=3)
        ttk.Checkbutton(rcv_content, text="Allow partial rankings (don't require ranking all)").pack(anchor='w', pady=3)
        ttk.Checkbutton(rcv_content, text="Show instant runoff visualization").pack(anchor='w', pady=3)

        ttk.Label(rcv_content, text="\nMaximum Rankings Allowed:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        rank_spin = ttk.Spinbox(rcv_content, from_=3, to=10, width=10)
        rank_spin.pack(anchor='w')
        rank_spin.set(5)

        ttk.Label(rcv_content, text="\nElimination Method:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        ttk.Radiobutton(rcv_content, text="Eliminate one candidate per round", value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(rcv_content, text="Batch elimination (all below threshold)", value=2).pack(anchor='w', pady=2)

        ttk.Label(rcv_content, text="\nTie Breaking:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        ttk.Radiobutton(rcv_content, text="Random selection", value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(rcv_content, text="Most 1st place votes", value=2).pack(anchor='w', pady=2)
        ttk.Radiobutton(rcv_content, text="Manual review", value=3).pack(anchor='w', pady=2)

        # Approval Voting tab
        approval_frame = ttk.Frame(notebook)
        notebook.add(approval_frame, text="Approval Voting")

        approval_content = ttk.Frame(approval_frame)
        approval_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(approval_content, text="Approval Voting Configuration",
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        ttk.Checkbutton(approval_content, text="Enable approval voting for this election").pack(anchor='w', pady=3)
        ttk.Checkbutton(approval_content, text="Show number of approvals for each candidate").pack(anchor='w', pady=3)
        ttk.Checkbutton(approval_content, text="Allow abstaining (approve none)").pack(anchor='w', pady=3)

        ttk.Label(approval_content, text="\nApproval Limit:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        ttk.Radiobutton(approval_content, text="Unlimited (approve as many as you want)", value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(approval_content, text="Limited to specific number:", value=2).pack(anchor='w', pady=2)

        limit_spin = ttk.Spinbox(approval_content, from_=1, to=10, width=10)
        limit_spin.pack(anchor='w', padx=30)
        limit_spin.set(3)

        ttk.Label(approval_content, text="\nResults Display:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        ttk.Radiobutton(approval_content, text="Show approval count", value=1).pack(anchor='w', pady=2)
        ttk.Radiobutton(approval_content, text="Show approval percentage", value=2).pack(anchor='w', pady=2)
        ttk.Radiobutton(approval_content, text="Show both", value=3).pack(anchor='w', pady=2)

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
        ttk.Entry(period_frame, width=15).pack(side='left', padx=(0, 15))
        ttk.Label(period_frame, text="End:").pack(side='left', padx=(0, 5))
        ttk.Entry(period_frame, width=15).pack(side='left')

        ttk.Label(advanced_content, text="\nSecurity Options:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        ttk.Checkbutton(advanced_content, text="Require two-factor authentication for voting").pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text="Generate unique verification code for each voter").pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text="Enable vote verification (voters can check their vote was counted)").pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text="Allow vote change before deadline").pack(anchor='w', pady=2)

        ttk.Label(advanced_content, text="\nAccessibility:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        ttk.Checkbutton(advanced_content, text="Enable screen reader support").pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text="Provide audio ballot option").pack(anchor='w', pady=2)
        ttk.Checkbutton(advanced_content, text="Allow extended time for voting").pack(anchor='w', pady=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Save Configuration", command=self.save_config).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Load Template", command=self.load_template).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Preview Ballot", command=self.preview_ballot).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def save_config(self):
        messagebox.showinfo("Configuration Saved",
                          "Voting method configuration saved!\n\n" +
                          "Election: Student Union President 2025\n" +
                          "Method: Ranked Choice Voting\n" +
                          "Max Rankings: 5\n" +
                          "Elimination: One per round\n" +
                          "Tie Breaking: Most 1st place votes\n\n" +
                          "Configuration active when voting opens.")

    def load_template(self):
        messagebox.showinfo("Load Template",
                          "Available templates:\n\n" +
                          "1. Standard SU Election (Standard voting)\n" +
                          "2. Competitive Race (RCV, 5 rankings)\n" +
                          "3. Awards Voting (Approval voting)\n" +
                          "4. Custom\n\n" +
                          "Select template to load configuration.")

    def preview_ballot(self):
        messagebox.showinfo("Ballot Preview",
                          "Ballot preview:\n\n" +
                          "┌─────────────────────────────┐\n" +
                          "│ Student Union President 2025 │\n" +
                          "│ Rank Choice Voting          │\n" +
                          "├─────────────────────────────┤\n" +
                          "│ □ Alice Johnson  [Rank: __] │\n" +
                          "│ □ Bob Smith      [Rank: __] │\n" +
                          "│ □ Carol Davis    [Rank: __] │\n" +
                          "│ □ David Lee      [Rank: __] │\n" +
                          "└─────────────────────────────┘\n\n" +
                          "Preview in full ballot viewer")



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

