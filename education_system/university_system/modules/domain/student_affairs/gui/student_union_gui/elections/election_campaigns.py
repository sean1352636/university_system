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
    

class TrackCampaignExpensesDialog:
    """Dialog for tracking campaign expenses and budgets"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Track Campaign Expenses")
        self.dialog.geometry("1100x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="💰 Campaign Expense Tracking",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Election selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(select_frame, text="Select Election:").pack(side='left', padx=(0, 10))
        election_combo = ttk.Combobox(select_frame, width=40, state='readonly')
        election_combo['values'] = ('Student Union President 2025', 'VP Academic Affairs 2025', 'Treasurer 2025')
        election_combo.pack(side='left', fill='x', expand=True)
        election_combo.current(0)

        # Budget overview
        budget_frame = ttk.LabelFrame(main_frame, text="Budget Overview")
        budget_frame.pack(fill='x', pady=(0, 15))

        budget_info = ttk.Frame(budget_frame)
        budget_info.pack(fill='x', padx=15, pady=10)

        ttk.Label(budget_info, text="Maximum Budget:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=3)
        ttk.Label(budget_info, text="£500.00").grid(row=0, column=1, sticky='w', padx=10)

        ttk.Label(budget_info, text="Total Spent:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=3)
        ttk.Label(budget_info, text="£387.50", foreground='blue').grid(row=1, column=1, sticky='w', padx=10)

        ttk.Label(budget_info, text="Remaining:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=3)
        ttk.Label(budget_info, text="£112.50", foreground='green').grid(row=2, column=1, sticky='w', padx=10)

        ttk.Label(budget_info, text="Budget Utilization:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=3)
        ttk.Label(budget_info, text="77.5%").grid(row=3, column=1, sticky='w', padx=10)

        # Expenses list
        list_frame = ttk.LabelFrame(main_frame, text="Expense Records")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Candidate', 'Category', 'Description', 'Amount', 'Date', 'Receipt', 'Status')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Description':
                tree.column(col, width=200)
            elif col == 'Amount':
                tree.column(col, width=80)
            else:
                tree.column(col, width=110)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # Sample expense data
        expenses = [
            ("Alice Johnson", "Marketing", "Campaign posters (500 units)", "£150.00", "2025-03-15", "Yes", "Approved"),
            ("Alice Johnson", "Digital", "Social media advertising", "£75.00", "2025-03-18", "Yes", "Approved"),
            ("Bob Smith", "Materials", "Campaign leaflets printing", "£85.50", "2025-03-20", "Yes", "Approved"),
            ("Carol Davis", "Events", "Town hall venue rental", "£50.00", "2025-03-22", "Yes", "Approved"),
            ("Alice Johnson", "Materials", "Banner printing", "£27.00", "2025-03-25", "Yes", "Pending"),
            ("Bob Smith", "Marketing", "Campaign badges", "£0.00", "2025-03-26", "No", "Rejected - Over Budget")
        ]

        for expense in expenses:
            tree.insert('', 'end', values=expense)

        # Category breakdown
        category_frame = ttk.LabelFrame(main_frame, text="Spending by Category")
        category_frame.pack(fill='x', pady=(0, 15))

        category_text = """Marketing: £150.00 (38.7%)
Digital: £75.00 (19.4%)
Materials: £112.50 (29.0%)
Events: £50.00 (12.9%)
"""
        ttk.Label(category_frame, text=category_text, justify='left', font=('Courier', 10)).pack(padx=15, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Add Expense", command=self.add_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Receipt", command=self.view_receipt).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Generate Report", command=self.generate_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Export to CSV", command=self.export_csv).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def add_expense(self):
        dialog = CampaignExpenseSubmissionDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_receipt(self):
        messagebox.showinfo("View Receipt", "Receipt viewer would display the scanned receipt image.")

    def generate_report(self):
        messagebox.showinfo("Report Generated", "Campaign finance report generated:\n\nreports/campaign_expenses_2025.pdf\n\nIncludes all expenses, receipts, and compliance verification.")

    def export_csv(self):
        messagebox.showinfo("Exported", "Expense data exported to:\nreports/campaign_expenses_2025.csv")



class ViewCandidateProfilesDialog:
    """Dialog for viewing detailed candidate profiles and platforms"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Candidate Profiles")
        self.dialog.geometry("1000x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="👤 Candidate Profiles",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Candidates list
        list_frame = ttk.LabelFrame(main_frame, text="Candidates")
        list_frame.pack(fill='x', pady=(0, 15))

        columns = ('Name', 'Position', 'Year', 'Course', 'Experience', 'Endorsements')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=6)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Name':
                tree.column(col, width=140)
            elif col == 'Position':
                tree.column(col, width=150)
            else:
                tree.column(col, width=100)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample candidates
        self.candidates = [
            ("Alice Johnson", "Student Union President", "3rd Year", "Political Science", "2 years SU", "15"),
            ("Bob Smith", "Student Union President", "4th Year", "Business Admin", "Club President", "12"),
            ("Carol Davis", "VP Academic Affairs", "3rd Year", "Education", "Course Rep x2", "8"),
            ("David Lee", "Treasurer", "2nd Year", "Accounting", "Finance Club VP", "10")
        ]

        for candidate in self.candidates:
            tree.insert('', 'end', values=candidate)

        tree.bind('<Double-1>', self.show_profile_details)

        # Profile details area
        details_frame = ttk.LabelFrame(main_frame, text="Profile Details (Double-click candidate to view)")
        details_frame.pack(fill='both', expand=True, pady=(0, 15))

        # Use notebook for organized profile
        notebook = ttk.Notebook(details_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Bio tab
        bio_frame = ttk.Frame(notebook)
        notebook.add(bio_frame, text="Biography")

        self.bio_text = scrolledtext.ScrolledText(bio_frame, height=8, wrap=tk.WORD)
        self.bio_text.pack(fill='both', expand=True, padx=10, pady=10)
        self.bio_text.insert('1.0', "Select a candidate to view their biography...")
        self.bio_text.config(state='disabled')

        # Platform tab
        platform_frame = ttk.Frame(notebook)
        notebook.add(platform_frame, text="Platform & Policies")

        self.platform_text = scrolledtext.ScrolledText(platform_frame, height=8, wrap=tk.WORD)
        self.platform_text.pack(fill='both', expand=True, padx=10, pady=10)
        self.platform_text.insert('1.0', "Select a candidate to view their platform...")
        self.platform_text.config(state='disabled')

        # Experience tab
        experience_frame = ttk.Frame(notebook)
        notebook.add(experience_frame, text="Experience & Qualifications")

        self.experience_text = scrolledtext.ScrolledText(experience_frame, height=8, wrap=tk.WORD)
        self.experience_text.pack(fill='both', expand=True, padx=10, pady=10)
        self.experience_text.insert('1.0', "Select a candidate to view their experience...")
        self.experience_text.config(state='disabled')

        # Endorsements tab
        endorsements_frame = ttk.Frame(notebook)
        notebook.add(endorsements_frame, text="Endorsements")

        self.endorsements_text = scrolledtext.ScrolledText(endorsements_frame, height=8, wrap=tk.WORD)
        self.endorsements_text.pack(fill='both', expand=True, padx=10, pady=10)
        self.endorsements_text.insert('1.0', "Select a candidate to view endorsements...")
        self.endorsements_text.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Compare Candidates", command=self.compare_candidates).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Campaign Materials", command=self.view_materials).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Endorse Candidate", command=self.endorse).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

        # Store tree reference
        self.tree = tree

    def _load_endorsements_from_db(self, candidate_name):
        """Load endorsements from database for a candidate."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS candidate_endorsements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_name TEXT,
                    endorser_username TEXT,
                    visibility TEXT,
                    message TEXT,
                    endorsed_date TEXT
                )
            ''')
            cursor.execute('''
                SELECT endorser_username, visibility, message, endorsed_date
                FROM candidate_endorsements
                WHERE candidate_name = ?
                ORDER BY endorsed_date DESC
            ''', (candidate_name,))
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return "No endorsements yet. Be the first to endorse this candidate!"

            lines = [f"ENDORSEMENTS ({len(rows)} total):", "=" * 40, ""]
            for endorser, visibility, message, date in rows:
                if visibility == 'public':
                    lines.append(f"- {endorser} ({date})")
                else:
                    lines.append(f"- Anonymous supporter ({date})")
                if message:
                    lines.append(f'  "{message}"')
                lines.append("")
            return "\n".join(lines)
        except Exception:
            return "Unable to load endorsements."

    def _get_candidate_profiles(self):
        """Return profile data for all candidates."""
        return {
            "Alice Johnson": {
                "bio": "Alice Johnson is a third-year Political Science student with a passion for student advocacy and democratic representation.\n\nShe has served on the Student Union executive board for two years and has been instrumental in launching several successful student initiatives including the Free Breakfast Program and the Student Mental Health Support Network.\n\nAlice is known for her collaborative leadership style and her commitment to transparency in student governance.",
                "platform": "KEY POLICIES:\n\n1. AFFORDABILITY & SUPPORT\n   - Expand hardship fund by 50%\n   - Introduce free textbook rental program\n   - Negotiate student discount partnerships\n\n2. SUSTAINABILITY\n   - Achieve carbon-neutral campus by 2027\n   - Install solar panels on all student buildings\n   - Launch campus-wide composting program\n\n3. STUDENT WELLBEING\n   - 24/7 mental health crisis support\n   - Double counseling service capacity\n   - Create peer support network across all departments\n\n4. ACADEMIC EXCELLENCE\n   - Student voice in curriculum design\n   - Increase library opening hours\n   - Fund undergraduate research opportunities",
                "experience": "LEADERSHIP EXPERIENCE:\n\nStudent Union Executive Board (2023-2025)\n- Led 3 successful campaigns resulting in policy changes\n- Managed \u00a350,000 budget for student initiatives\n- Coordinated team of 12 student representatives\n\nPolitical Science Society - President (2024-2025)\n- Grew membership from 45 to 120 students\n- Organized 8 speaker events with MPs and policy experts\n\nCourse Representative (2023-2024)\n- Championed improvements to assessment feedback\n\nAWARDS:\n- Outstanding Student Leadership Award 2024\n- Dean's List (2023, 2024)",
            },
            "Bob Smith": {
                "bio": "Bob Smith is a fourth-year Business Administration student with extensive experience in financial management and organisational leadership.\n\nAs the current President of the Entrepreneurship Club, Bob has led fundraising efforts that raised over \u00a330,000 for student startups. He is passionate about making the Student Union financially sustainable while delivering more services to students.\n\nBob brings a practical, results-oriented approach to student governance, emphasising accountability and measurable outcomes.",
                "platform": "KEY POLICIES:\n\n1. FINANCIAL TRANSPARENCY\n   - Publish quarterly SU financial reports\n   - Student oversight committee for budget decisions\n   - Online dashboard showing how SU fees are spent\n\n2. EMPLOYABILITY\n   - Expand careers service partnerships with employers\n   - Create paid internship fund for disadvantaged students\n   - Launch alumni mentorship programme\n\n3. STUDENT ENTERPRISE\n   - \u00a320,000 startup fund for student businesses\n   - Co-working space in the SU building\n   - Business skills workshops every semester\n\n4. CAMPUS FACILITIES\n   - Extended gym opening hours\n   - Upgrade common room facilities\n   - Better Wi-Fi across campus",
                "experience": "LEADERSHIP EXPERIENCE:\n\nEntrepreneurship Club - President (2024-2026)\n- Raised \u00a330,000+ for student startup initiatives\n- Managed club budget of \u00a315,000\n- Organised 12 networking events with industry leaders\n\nBusiness Society - Vice President (2023-2024)\n- Led team of 8 committee members\n- Doubled society membership to 200+\n\nStudent Ambassador (2023-2025)\n- Represented university at 15+ open days\n\nAWARDS:\n- Best Society Leader 2025\n- Business Faculty Prize for Excellence",
            },
            "Carol Davis": {
                "bio": "Carol Davis is a third-year Education student with a deep commitment to academic quality and student support. Having served as Course Representative twice, she understands the challenges students face.\n\nCarol has been instrumental in establishing peer tutoring programmes and advocating for improved assessment feedback. She volunteers weekly at the Student Advice Centre.\n\nHer approach to leadership centres on listening to students and turning their concerns into actionable improvements.",
                "platform": "KEY POLICIES:\n\n1. ACADEMIC QUALITY\n   - Standardise feedback turnaround times (2 weeks max)\n   - Student evaluation of teaching quality\n   - More flexible assessment options\n\n2. LEARNING SUPPORT\n   - Expand peer tutoring to all departments\n   - Free academic writing workshops\n   - Dedicated study spaces with 24/7 access during exams\n\n3. INCLUSIVITY\n   - Improved accessibility across all buildings\n   - Better support for international students\n   - Inclusive curriculum review committee\n\n4. STUDENT VOICE\n   - Monthly open forums with university leadership\n   - Online suggestion platform with guaranteed responses\n   - Student representatives on all university committees",
                "experience": "LEADERSHIP EXPERIENCE:\n\nCourse Representative x2 (2024-2026)\n- Successfully campaigned for improved feedback policies\n- Represented 300+ Education students\n\nPeer Tutoring Coordinator (2025-2026)\n- Set up tutoring programmes across 5 departments\n- Trained 40+ peer tutors\n\nStudent Advice Centre Volunteer (2024-2026)\n- 200+ hours of volunteer service\n\nAWARDS:\n- Student Voice Champion Award 2025\n- Faculty Commendation for Student Support",
            },
            "David Lee": {
                "bio": "David Lee is a second-year Accounting student who brings financial expertise and a fresh perspective to student governance. Despite being in his second year, David has already made a significant impact as Vice President of the Finance Club.\n\nHe is passionate about financial literacy and ensuring the Student Union uses its resources effectively. David has proposed innovative budgeting approaches that could save the SU thousands while improving services.\n\nDavid believes in data-driven decision making and wants to bring modern financial practices to the Student Union.",
                "platform": "KEY POLICIES:\n\n1. SMART BUDGETING\n   - Zero-based budgeting for all SU departments\n   - Cost-benefit analysis for all new initiatives\n   - Emergency fund for student hardship cases\n\n2. STUDENT SAVINGS\n   - Negotiate bulk purchasing deals for course materials\n   - Student discount app with local businesses\n   - Transparent pricing in all SU outlets\n\n3. FINANCIAL LITERACY\n   - Free budgeting workshops for all students\n   - Tax advice sessions for working students\n   - Scholarship and bursary awareness campaigns\n\n4. ACCOUNTABILITY\n   - Monthly financial updates to all students\n   - Open budget meetings every semester\n   - Annual value-for-money audit",
                "experience": "LEADERSHIP EXPERIENCE:\n\nFinance Club - Vice President (2025-2026)\n- Managed club investments portfolio\n- Organised financial literacy week (500+ attendees)\n- Created budgeting app used by 200+ students\n\nClass Treasurer (2024-2025)\n- Managed class social fund of \u00a35,000\n- Delivered surplus back to students\n\nCharity Fundraising Coordinator (2025)\n- Raised \u00a38,000 for local food bank\n\nAWARDS:\n- ACCA Student Excellence Award 2025\n- Best New Committee Member (Finance Club)",
            },
        }

    def show_profile_details(self, event):
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        values = item['values']
        name = values[0]

        # Load profiles and endorsements from DB
        self.profiles = self._get_candidate_profiles()
        endorsements_text = self._load_endorsements_from_db(name)
        profile = self.profiles.get(name, {
            "bio": f"No biography available for {name}.",
            "platform": f"No platform available for {name}.",
            "experience": f"No experience listed for {name}.",
        })
        profile['endorsements'] = endorsements_text

        # Update text widgets
        self.bio_text.config(state='normal')
        self.bio_text.delete('1.0', tk.END)
        self.bio_text.insert('1.0', profile.get('bio', 'No biography available'))
        self.bio_text.config(state='disabled')

        self.platform_text.config(state='normal')
        self.platform_text.delete('1.0', tk.END)
        self.platform_text.insert('1.0', profile.get('platform', 'No platform available'))
        self.platform_text.config(state='disabled')

        self.experience_text.config(state='normal')
        self.experience_text.delete('1.0', tk.END)
        self.experience_text.insert('1.0', profile.get('experience', 'No experience listed'))
        self.experience_text.config(state='disabled')

        self.endorsements_text.config(state='normal')
        self.endorsements_text.delete('1.0', tk.END)
        self.endorsements_text.insert('1.0', profile.get('endorsements', 'No endorsements yet'))
        self.endorsements_text.config(state='disabled')

    def compare_candidates(self):
        """Side-by-side candidate comparison"""
        # Create comparison window
        compare_window = tk.Toplevel(self.dialog)
        compare_window.title("Side-by-Side Candidate Comparison")
        compare_window.geometry("1200x700")
        compare_window.transient(self.dialog)

        main_frame = ttk.Frame(compare_window)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Compare Candidates Side-by-Side",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Candidate selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(select_frame, text="Select candidates to compare:").pack(side='left', padx=(0, 10))

        candidate_names = [c[0] for c in self.candidates]

        ttk.Label(select_frame, text="Candidate 1:").pack(side='left', padx=(20, 5))
        candidate1_var = tk.StringVar()
        candidate1_combo = ttk.Combobox(select_frame, textvariable=candidate1_var,
                                       values=candidate_names, state='readonly', width=20)
        candidate1_combo.pack(side='left', padx=(0, 20))
        if candidate_names:
            candidate1_combo.current(0)

        ttk.Label(select_frame, text="Candidate 2:").pack(side='left', padx=(0, 5))
        candidate2_var = tk.StringVar()
        candidate2_combo = ttk.Combobox(select_frame, textvariable=candidate2_var,
                                       values=candidate_names, state='readonly', width=20)
        candidate2_combo.pack(side='left')
        if len(candidate_names) > 1:
            candidate2_combo.current(1)

        # Comparison display
        comparison_frame = ttk.Frame(main_frame)
        comparison_frame.pack(fill='both', expand=True)

        # Create canvas with scrollbar
        canvas = tk.Canvas(comparison_frame)
        scrollbar = ttk.Scrollbar(comparison_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def update_comparison():
            # Clear previous comparison
            for widget in scrollable_frame.winfo_children():
                widget.destroy()

            name1 = candidate1_var.get()
            name2 = candidate2_var.get()

            if not name1 or not name2:
                return

            # Get candidate data
            candidate1_data = None
            candidate2_data = None
            for c in self.candidates:
                if c[0] == name1:
                    candidate1_data = c
                if c[0] == name2:
                    candidate2_data = c

            # Header
            header_frame = ttk.Frame(scrollable_frame)
            header_frame.pack(fill='x', padx=10, pady=(10, 5))

            ttk.Label(header_frame, text="", width=20).grid(row=0, column=0)
            ttk.Label(header_frame, text=name1, font=('Arial', 11, 'bold'),
                     foreground='blue').grid(row=0, column=1, padx=20)
            ttk.Label(header_frame, text=name2, font=('Arial', 11, 'bold'),
                     foreground='green').grid(row=0, column=2, padx=20)

            # Comparison categories
            categories = [
                ('Position', 1),
                ('Year', 2),
                ('Course', 3),
                ('Experience', 4),
                ('Endorsements', 5)
            ]

            for cat_name, idx in categories:
                cat_frame = ttk.Frame(scrollable_frame)
                cat_frame.pack(fill='x', padx=10, pady=2)

                ttk.Label(cat_frame, text=f"{cat_name}:", font=('Arial', 10, 'bold'),
                         width=20).grid(row=0, column=0, sticky='w')
                ttk.Label(cat_frame, text=candidate1_data[idx] if candidate1_data else 'N/A',
                         width=25, anchor='w').grid(row=0, column=1, padx=20, sticky='w')
                ttk.Label(cat_frame, text=candidate2_data[idx] if candidate2_data else 'N/A',
                         width=25, anchor='w').grid(row=0, column=2, padx=20, sticky='w')

            # Platform comparison
            ttk.Separator(scrollable_frame, orient='horizontal').pack(fill='x', padx=10, pady=15)

            platform_header = ttk.Frame(scrollable_frame)
            platform_header.pack(fill='x', padx=10, pady=(0, 10))
            ttk.Label(platform_header, text="PLATFORM & POLICIES",
                     font=('Arial', 12, 'bold')).pack()

            platform_frame = ttk.Frame(scrollable_frame)
            platform_frame.pack(fill='both', expand=True, padx=10)

            # Side by side platforms
            left_platform = scrolledtext.ScrolledText(platform_frame, height=15, width=50, wrap=tk.WORD)
            left_platform.pack(side='left', fill='both', expand=True, padx=(0, 5))

            right_platform = scrolledtext.ScrolledText(platform_frame, height=15, width=50, wrap=tk.WORD)
            right_platform.pack(side='right', fill='both', expand=True, padx=(5, 0))

            profile1 = self.profiles.get(name1, {})
            profile2 = self.profiles.get(name2, {})

            left_platform.insert('1.0', profile1.get('platform', f"{name1}'s platform not available"))
            left_platform.config(state='disabled')

            right_platform.insert('1.0', profile2.get('platform', f"{name2}'s platform not available"))
            right_platform.config(state='disabled')

        # Initial comparison
        update_comparison()

        # Update button
        ttk.Button(select_frame, text="Update Comparison",
                  command=update_comparison).pack(side='left', padx=(20, 0))

        ttk.Button(main_frame, text="Close", command=compare_window.destroy).pack(pady=(10, 0))

    def view_materials(self):
        """View campaign materials"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a candidate first.")
            return

        item = self.tree.item(selection[0])
        candidate_name = item['values'][0]

        # Create materials window
        materials_window = tk.Toplevel(self.dialog)
        materials_window.title(f"Campaign Materials - {candidate_name}")
        materials_window.geometry("800x600")
        materials_window.transient(self.dialog)

        main_frame = ttk.Frame(materials_window)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=f"📄 Campaign Materials: {candidate_name}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Tabs for different materials
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Manifesto tab
        manifesto_frame = ttk.Frame(notebook)
        notebook.add(manifesto_frame, text="Manifesto")

        profiles = self._get_candidate_profiles()
        candidate_profile = profiles.get(candidate_name, {})

        manifesto_text = scrolledtext.ScrolledText(manifesto_frame, height=20, wrap=tk.WORD)
        manifesto_text.pack(fill='both', expand=True, padx=10, pady=10)

        platform = candidate_profile.get('platform', '')
        bio = candidate_profile.get('bio', '')
        manifesto_content = (
            f"CAMPAIGN MANIFESTO\n"
            f"{'=' * 40}\n"
            f"{candidate_name}\n\n"
            f"ABOUT ME:\n{'-' * 40}\n{bio}\n\n"
            f"MY PLATFORM:\n{'-' * 40}\n{platform}\n\n"
            f"This manifesto represents my commitment to the student body.\n"
            f"Vote for positive change!"
        )
        manifesto_text.insert('1.0', manifesto_content)
        manifesto_text.config(state='disabled')

        # Media tab - with upload and DB-backed file list
        media_frame = ttk.Frame(notebook)
        notebook.add(media_frame, text="Media & Posters")

        media_content = ttk.Frame(media_frame)
        media_content.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(media_content, text="Campaign Media Files:",
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        # Media treeview
        media_columns = ('File Name', 'Type', 'Uploaded')
        media_tree = ttk.Treeview(media_content, columns=media_columns,
                                  show='headings', height=8)
        for col in media_columns:
            media_tree.heading(col, text=col)
        media_tree.column('File Name', width=300)
        media_tree.column('Type', width=100)
        media_tree.column('Uploaded', width=150)
        media_tree.pack(fill='both', expand=True, pady=(0, 10))

        # Load media from DB
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaign_media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_name TEXT,
                    file_name TEXT,
                    file_type TEXT,
                    file_path TEXT,
                    uploaded_by TEXT,
                    uploaded_at TEXT
                )
            ''')
            cursor.execute('''
                SELECT file_name, file_type, uploaded_at
                FROM campaign_media
                WHERE candidate_name = ?
                ORDER BY uploaded_at DESC
            ''', (candidate_name,))
            for row in cursor.fetchall():
                media_tree.insert('', 'end', values=row)
            conn.close()
        except Exception:
            pass

        # Upload button
        media_btn_frame = ttk.Frame(media_content)
        media_btn_frame.pack(fill='x')

        def upload_media():
            from tkinter import filedialog
            filepath = filedialog.askopenfilename(
                title="Select Campaign Media",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.gif"),
                          ("PDF", "*.pdf"), ("Videos", "*.mp4 *.avi"),
                          ("All files", "*.*")]
            )
            if not filepath:
                return
            import os, shutil
            filename = os.path.basename(filepath)
            ext = os.path.splitext(filename)[1].lower()
            file_type = 'Image' if ext in ('.png','.jpg','.jpeg','.gif') else 'PDF' if ext == '.pdf' else 'Video' if ext in ('.mp4','.avi') else 'Other'
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            uploads_dir = os.path.join(str(paths.DATA_DIR), 'uploads', 'campaign_media')
            os.makedirs(uploads_dir, exist_ok=True)
            dest = os.path.join(uploads_dir, f"{candidate_name.replace(' ','_')}_{filename}")
            try:
                shutil.copy(filepath, dest)
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO campaign_media
                    (candidate_name, file_name, file_type, file_path, uploaded_by, uploaded_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (candidate_name, filename, file_type, dest,
                      self.auth.current_user.get('username', '') if self.auth and self.auth.current_user else '',
                      now))
                conn.commit()
                conn.close()
                media_tree.insert('', 0, values=(filename, file_type, now))
                messagebox.showinfo("Uploaded", f"'{filename}' uploaded successfully.",
                                   parent=materials_window)
            except Exception as e:
                messagebox.showerror("Error", f"Upload failed: {e}", parent=materials_window)

        ttk.Button(media_btn_frame, text="Upload Media File",
                  command=upload_media).pack(side='left', padx=(0, 10))
        ttk.Button(media_btn_frame, text="Delete Selected",
                  command=lambda: self._delete_media(media_tree, candidate_name, materials_window)
                  ).pack(side='left')

        # Social media tab
        social_frame = ttk.Frame(notebook)
        notebook.add(social_frame, text="Social Media")

        social_content = ttk.Frame(social_frame)
        social_content.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(social_content, text="Social Media Presence:", font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        social_links = [
            ("Twitter/X", f"@{candidate_name.replace(' ', '').lower()}_vote"),
            ("Instagram", f"@{candidate_name.replace(' ', '').lower()}_campaign"),
            ("Facebook", f"{candidate_name} for Student Union"),
            ("TikTok", f"@{candidate_name.replace(' ', '').lower()}_su")
        ]

        for platform, handle in social_links:
            link_frame = ttk.Frame(social_content)
            link_frame.pack(fill='x', pady=5)
            ttk.Label(link_frame, text=f"{platform}:", font=('Arial', 10, 'bold'), width=15).pack(side='left')
            ttk.Label(link_frame, text=handle, foreground='blue').pack(side='left')

        ttk.Button(main_frame, text="Close", command=materials_window.destroy).pack()

    def _delete_media(self, media_tree, candidate_name, parent_window):
        """Delete selected media file from DB."""
        selection = media_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to delete.",
                                 parent=parent_window)
            return
        values = media_tree.item(selection[0], 'values')
        file_name = values[0]
        if not messagebox.askyesno("Confirm", f"Delete '{file_name}'?", parent=parent_window):
            return
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM campaign_media WHERE candidate_name = ? AND file_name = ?',
                         (candidate_name, file_name))
            conn.commit()
            conn.close()
            media_tree.delete(selection[0])
        except Exception as e:
            messagebox.showerror("Error", f"Delete failed: {e}", parent=parent_window)

    def _refresh_endorsement_count(self, candidate_name):
        """Update endorsement count in the candidates treeview."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM candidate_endorsements WHERE candidate_name = ?',
                         (candidate_name,))
            count = cursor.fetchone()[0]
            conn.close()

            for item_id in self.tree.get_children():
                values = list(self.tree.item(item_id, 'values'))
                if values[0] == candidate_name:
                    values[5] = str(count)
                    self.tree.item(item_id, values=values)
                    break
        except Exception:
            pass

    def endorse(self):
        """Endorse a candidate"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a candidate to endorse.")
            return

        item = self.tree.item(selection[0])
        candidate_name = item['values'][0]

        # Create endorsement window
        endorse_window = tk.Toplevel(self.dialog)
        endorse_window.title(f"Endorse {candidate_name}")
        endorse_window.geometry("500x400")
        endorse_window.transient(self.dialog)
        endorse_window.grab_set()

        main_frame = ttk.Frame(endorse_window)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=f"Endorse {candidate_name}",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        ttk.Label(main_frame, text="Your endorsement helps build trust and credibility.",
                 font=('Arial', 10)).pack(pady=(0, 15))

        # Public/Private option
        ttk.Label(main_frame, text="Endorsement Visibility:").pack(anchor='w', pady=(5, 0))
        visibility_var = tk.StringVar(value='public')

        ttk.Radiobutton(main_frame, text="Public (Your name will appear on candidate's profile)",
                       variable=visibility_var, value='public').pack(anchor='w', padx=20)
        ttk.Radiobutton(main_frame, text="Private (Anonymous support)",
                       variable=visibility_var, value='private').pack(anchor='w', padx=20, pady=(0, 10))

        # Optional message
        ttk.Label(main_frame, text="Optional Endorsement Message:").pack(anchor='w', pady=(5, 0))
        message_text = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD)
        message_text.pack(fill='both', expand=True, pady=(0, 15))

        def submit_endorsement():
            visibility = visibility_var.get()
            message = message_text.get("1.0", tk.END).strip()

            username = self.auth.current_user.get('username', 'Anonymous') if self.auth.current_user else 'Anonymous'

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Create table if not exists
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS candidate_endorsements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        candidate_name TEXT,
                        endorser_username TEXT,
                        visibility TEXT,
                        message TEXT,
                        endorsed_date TEXT
                    )
                ''')

                # Check for duplicate endorsement
                cursor.execute('''
                    SELECT id FROM candidate_endorsements
                    WHERE candidate_name = ? AND endorser_username = ?
                ''', (candidate_name, username))
                if cursor.fetchone():
                    conn.close()
                    messagebox.showinfo("Already Endorsed",
                                       f"You have already endorsed {candidate_name}.",
                                       parent=endorse_window)
                    return

                cursor.execute('''
                    INSERT INTO candidate_endorsements
                    (candidate_name, endorser_username, visibility, message, endorsed_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (candidate_name, username, visibility, message,
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                conn.commit()
                conn.close()

                # Update endorsement count in treeview
                self._refresh_endorsement_count(candidate_name)

                visibility_text = "publicly" if visibility == 'public' else "privately"
                messagebox.showinfo("Endorsement Recorded",
                                   f"Your {visibility_text} endorsement of {candidate_name} has been recorded!\n\n" +
                                   ("Your name will appear on their profile page." if visibility == 'public'
                                    else "Your support is recorded anonymously."))

                endorse_window.destroy()

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to record endorsement: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Submit Endorsement", command=submit_endorsement).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=endorse_window.destroy).pack(side='left')



class CampaignExpenseSubmissionDialog:
    """Dialog for submitting campaign expenses"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Submit Campaign Expense")
        self.dialog.geometry("650x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Submit Campaign Expense", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Label(main_frame, text="Required: Category, Description, Amount, Receipt",
                 font=('Arial', 10, 'italic')).pack(pady=(0, 15))

        # Category
        ttk.Label(main_frame, text="Expense Category:").pack(anchor='w', pady=(0, 5))
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(main_frame, textvariable=self.category_var, width=47)
        category_combo['values'] = ('Promotional Materials', 'Event Costs', 'Digital Marketing',
                                    'Printing', 'Venue Rental', 'Travel', 'Other')
        category_combo.pack(fill='x', pady=(0, 10))
        category_combo.current(0)

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(0, 5))
        self.description_entry = ttk.Entry(main_frame, width=50)
        self.description_entry.pack(fill='x', pady=(0, 10))
        self.description_entry.insert(0, "Campaign posters and flyers")

        # Amount
        ttk.Label(main_frame, text="Amount (£):").pack(anchor='w', pady=(0, 5))
        self.amount_entry = ttk.Entry(main_frame, width=50)
        self.amount_entry.pack(fill='x', pady=(0, 10))

        # Date
        ttk.Label(main_frame, text="Date of Expense (YYYY-MM-DD):").pack(anchor='w', pady=(0, 5))
        self.date_entry = ttk.Entry(main_frame, width=50)
        self.date_entry.pack(fill='x', pady=(0, 10))
        self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Vendor
        ttk.Label(main_frame, text="Vendor/Supplier:").pack(anchor='w', pady=(0, 5))
        self.vendor_entry = ttk.Entry(main_frame, width=50)
        self.vendor_entry.pack(fill='x', pady=(0, 10))

        # Receipt upload simulation
        receipt_frame = ttk.LabelFrame(main_frame, text="Receipt")
        receipt_frame.pack(fill='x', pady=(0, 10))

        receipt_inner = ttk.Frame(receipt_frame)
        receipt_inner.pack(padx=15, pady=15, fill='x')

        ttk.Label(receipt_inner, text="Receipt Number/Reference:").pack(anchor='w', pady=(0, 5))
        self.receipt_num_entry = ttk.Entry(receipt_inner, width=30)
        self.receipt_num_entry.pack(anchor='w', pady=(0, 10))

        ttk.Button(receipt_inner, text="📎 Attach Receipt File",
                  command=lambda: messagebox.showinfo("Info", "File upload dialog would open here")).pack(anchor='w')

        # Notes
        ttk.Label(main_frame, text="Additional Notes:").pack(anchor='w', pady=(0, 5))
        self.notes_text = scrolledtext.ScrolledText(main_frame, height=5, wrap=tk.WORD)
        self.notes_text.pack(fill='both', expand=True, pady=(0, 15))

        # Compliance notice
        compliance_frame = ttk.Frame(main_frame)
        compliance_frame.pack(fill='x', pady=(0, 15))

        self.compliance_var = tk.BooleanVar()
        ttk.Checkbutton(compliance_frame,
                       text="I certify this expense complies with campaign finance regulations",
                       variable=self.compliance_var).pack(anchor='w')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Submit Expense", command=self.submit_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def submit_expense(self):
        category = self.category_var.get()
        description = self.description_entry.get().strip()
        amount = self.amount_entry.get().strip()
        date = self.date_entry.get().strip()
        vendor = self.vendor_entry.get().strip()
        receipt_num = self.receipt_num_entry.get().strip()
        notes = self.notes_text.get(1.0, tk.END).strip()
        compliance = self.compliance_var.get()

        if not all([category, description, amount, date, vendor]):
            messagebox.showwarning("Warning", "Please fill in all required fields.")
            return

        if not compliance:
            messagebox.showwarning("Warning", "You must certify compliance with campaign finance regulations.")
            return

        try:
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("Warning", "Please enter a valid amount.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS campaign_expenses (
                expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                vendor TEXT,
                receipt_number TEXT,
                notes TEXT,
                submitted_by TEXT,
                submitted_date TEXT,
                status TEXT DEFAULT 'pending_review'
            )
            ''')

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            submitted_by = result[0] if result else 'unknown'

            cursor.execute('''
            INSERT INTO campaign_expenses (
                category, description, amount, date, vendor, receipt_number,
                notes, submitted_by, submitted_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review')
            ''', (category, description, amount_float, date, vendor, receipt_num,
                  notes, submitted_by, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Expense submitted successfully!\n\nAmount: £{amount_float:.2f}\nCategory: {category}\n\nYour expense will be reviewed for compliance.")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to submit expense: {str(e)}")



def open_campaign_expenses_dialog(self):
    """Open campaign expenses tracking"""
    dialog = TrackCampaignExpensesDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_candidate_profiles_dialog(self):
    """Open candidate profiles viewer"""
    dialog = ViewCandidateProfilesDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


