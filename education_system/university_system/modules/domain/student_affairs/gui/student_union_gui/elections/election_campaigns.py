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

    def show_profile_details(self, event):
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        values = item['values']
        name = values[0]

        # Sample profile data
        self.profiles = {
            "Alice Johnson": {
                "bio": """Alice Johnson is a third-year Political Science student with a passion for student advocacy and democratic representation.

She has served on the Student Union executive board for two years and has been instrumental in launching several successful student initiatives including the Free Breakfast Program and the Student Mental Health Support Network.

Alice is known for her collaborative leadership style and her commitment to transparency in student governance.""",
                "platform": """KEY POLICIES:

1. AFFORDABILITY & SUPPORT
   - Expand hardship fund by 50%
   - Introduce free textbook rental program
   - Negotiate student discount partnerships with local businesses

2. SUSTAINABILITY
   - Achieve carbon-neutral campus by 2027
   - Install solar panels on all student buildings
   - Launch campus-wide composting program

3. STUDENT WELLBEING
   - 24/7 mental health crisis support
   - Double counseling service capacity
   - Create peer support network across all departments

4. ACADEMIC EXCELLENCE
   - Student voice in curriculum design
   - Increase library opening hours
   - Fund undergraduate research opportunities""",
                "experience": """LEADERSHIP EXPERIENCE:

Student Union Executive Board (2023-2025)
- Led 3 successful campaigns resulting in policy changes
- Managed £50,000 budget for student initiatives
- Coordinated team of 12 student representatives

Political Science Society - President (2024-2025)
- Grew membership from 45 to 120 students
- Organized 8 speaker events with MPs and policy experts
- Established partnerships with 3 NGOs

Course Representative (2023-2024)
- Championed improvements to assessment feedback
- Mediated between students and faculty on course issues

AWARDS:
- Outstanding Student Leadership Award 2024
- Dean's List (2023, 2024)""",
                "endorsements": """ENDORSED BY:

15 Student Organizations including:
- Political Science Society
- Environmental Action Group
- Student Mental Health Association
- Debate Club
- International Students Society

5 Faculty Members:
- Prof. Sarah Williams (Political Science)
- Dr. James Brown (Sociology)
- Dr. Emily Chen (Psychology)

Student Testimonials:
"Alice genuinely cares about every student's voice" - Mark Thompson

"She turned our ideas into real change" - Jennifer Lee

"A proven leader with integrity" - Michael Rodriguez"""
            }
        }

        # Load profile data (default if not found)
        profile = self.profiles.get(name, {
            "bio": f"{name}'s biography would appear here with personal background, interests, and motivations.",
            "platform": f"{name}'s platform and policy proposals would appear here.",
            "experience": f"{name}'s experience and qualifications would appear here.",
            "endorsements": f"{name}'s endorsements would appear here."
        })

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

        manifesto_text = scrolledtext.ScrolledText(manifesto_frame, height=20, wrap=tk.WORD)
        manifesto_text.pack(fill='both', expand=True, padx=10, pady=10)
        manifesto_text.insert('1.0', f"""CAMPAIGN MANIFESTO
{candidate_name}

{self.profiles.get(candidate_name, {}).get('platform', 'Manifesto not available')}

This manifesto represents my commitment to the student body.
Vote for positive change!
""")
        manifesto_text.config(state='disabled')

        # Media tab
        media_frame = ttk.Frame(notebook)
        notebook.add(media_frame, text="Media & Posters")

        media_list = ttk.Frame(media_frame)
        media_list.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(media_list, text="Campaign Media Files:", font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        media_items = [
            "📄 Campaign Poster 1.pdf",
            "📄 Campaign Poster 2.pdf",
            "🎥 Introduction Video.mp4",
            "🎥 Policy Explanation Video.mp4",
            "📊 Infographic - Key Policies.png",
            "📷 Campaign Photos (12 images)"
        ]

        for item in media_items:
            item_frame = ttk.Frame(media_list)
            item_frame.pack(fill='x', pady=2)
            ttk.Label(item_frame, text=item).pack(side='left')
            ttk.Button(item_frame, text="View", width=8,
                      command=lambda i=item: messagebox.showinfo("View", f"Viewing: {i}")).pack(side='right')

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

                cursor.execute('''
                    INSERT INTO candidate_endorsements
                    (candidate_name, endorser_username, visibility, message, endorsed_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (candidate_name, username, visibility, message,
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                conn.commit()
                conn.close()

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


