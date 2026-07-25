import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure import paths
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
from education_system.systems.university.interfaces.gui.pastoral.student_union_gui.analytics.analytics import (
    EngagementTrendAnalysisDialog, MemberRetentionInsightsDialog
)

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
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
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


class VolunteerOpportunitiesDialog:
    """Dialog for browsing volunteer opportunities"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Volunteer Opportunities")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_opportunities()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="🌟 Volunteer Opportunities",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="Category:").pack(side='left', padx=(0, 5))
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, width=20, state='readonly')
        category_combo['values'] = ('All', 'Community Service', 'Education', 'Environment', 'Health', 'Animals')
        category_combo.current(0)
        category_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text="Filter", command=self.load_opportunities).pack(side='left')

        # Opportunities list
        list_frame = ttk.LabelFrame(main_frame, text="Available Opportunities")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Organization', 'Description', 'Date', 'Hours', 'Spots', 'Status')
        self.opp_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.opp_tree.heading(col, text=col)
            if col == 'Description':
                self.opp_tree.column(col, width=250)
            elif col == 'Organization':
                self.opp_tree.column(col, width=150)
            else:
                self.opp_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.opp_tree.yview)
        self.opp_tree.configure(yscrollcommand=scrollbar.set)

        self.opp_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.opp_tree.bind('<<TreeviewSelect>>', self.on_select)

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Opportunity Details")
        details_frame.pack(fill='x', pady=(0, 10))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=6, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Sign Up", command=self.sign_up).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="My Activities", command=self.view_my_activities).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_opportunities(self):
        # Clear existing
        for item in self.opp_tree.get_children():
            self.opp_tree.delete(item)

        # Sample data
        opportunities = [
            ("Local Food Bank", "Sort and pack food donations", "2025-04-15", "4", "5/10", "Open",
             "Help organize food donations for families in need. No experience required."),
            ("Animal Shelter", "Walk dogs and socialize cats", "2025-04-20", "3", "2/8", "Open",
             "Spend time with shelter animals. Must love animals!"),
            ("Community Garden", "Plant vegetables and maintain garden", "2025-04-25", "5", "8/15", "Open",
             "Help grow fresh produce for the local community. Great outdoor activity!"),
            ("Hospital", "Visit with elderly patients", "2025-05-01", "2", "0/6", "Open",
             "Provide companionship to hospital patients. Training provided."),
            ("Beach Cleanup", "Environmental cleanup event", "2025-05-10", "3", "15/30", "Open",
             "Join us for a beach cleanup! Help protect marine life.")
        ]

        for opp in opportunities:
            self.opp_tree.insert('', 'end', values=opp[:6], tags=(opp[6],))

    def on_select(self, event):
        selection = self.opp_tree.selection()
        if not selection:
            return

        item = self.opp_tree.item(selection[0])
        details = item['tags'][0] if item['tags'] else "No details available."

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)

    def sign_up(self):
        selection = self.opp_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an opportunity.")
            return

        item = self.opp_tree.item(selection[0])
        org = item['values'][0]

        if messagebox.askyesno("Confirm", f"Sign up for volunteer opportunity with {org}?"):
            messagebox.showinfo("Success", "You've been signed up!\n\nYou will receive further details via email.\n\n+20 Community Service Points earned!")

    def view_my_activities(self):
        dialog = MyVolunteerActivitiesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class MyVolunteerActivitiesDialog:
    """Dialog for viewing student's volunteer activities"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Volunteer Activities")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🤝 My Volunteer Activities",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Stats frame
        stats_frame = ttk.LabelFrame(main_frame, text="Volunteer Statistics")
        stats_frame.pack(fill='x', pady=(0, 15))

        stats_text = """Total Hours: 45 hours
Activities Completed: 8
Organizations Helped: 5
Community Service Points: 450 points

🏆 Achievements:
- Rising Star Volunteer (25+ hours)
- Community Champion Badge
- Service Leader Status
"""
        ttk.Label(stats_frame, text=stats_text, justify='left', font=('Arial', 10)).pack(padx=15, pady=10)

        # Activities list
        list_frame = ttk.LabelFrame(main_frame, text="Activity History")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Organization', 'Activity', 'Date', 'Hours', 'Status')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col in ('Organization', 'Activity'):
                tree.column(col, width=180)
            else:
                tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Sample data
        activities = [
            ("Food Bank", "Food sorting", "2025-03-28", "4", "Completed ✓"),
            ("Animal Shelter", "Dog walking", "2025-03-22", "3", "Completed ✓"),
            ("Community Garden", "Garden maintenance", "2025-03-15", "5", "Completed ✓"),
            ("Hospital", "Patient visits", "2025-04-05", "2", "Upcoming"),
            ("Beach Cleanup", "Beach cleanup", "2025-05-10", "3", "Registered")
        ]

        for activity in activities:
            tree.insert('', 'end', values=activity)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Download Certificate", command=self.download_cert).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def download_cert(self):
        messagebox.showinfo("Success", "Volunteer hours certificate downloaded!\n\nFile: volunteer_certificate_2025.pdf\n\nTotal Hours: 45")



class CommunityServiceHoursDialog:
    """Dialog for tracking community service hours"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Community Service Hours")
        self.dialog.geometry("800x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📋 Track Community Service Hours",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Log hours form
        form_frame = ttk.LabelFrame(main_frame, text="Log Service Hours")
        form_frame.pack(fill='x', pady=(0, 15))

        form = ttk.Frame(form_frame)
        form.pack(padx=15, pady=15, fill='x')

        # Organization
        ttk.Label(form, text="Organization:").grid(row=0, column=0, sticky='w', pady=5)
        self.org_entry = ttk.Entry(form, width=40)
        self.org_entry.grid(row=0, column=1, pady=5, sticky='ew')

        # Activity
        ttk.Label(form, text="Activity:").grid(row=1, column=0, sticky='w', pady=5)
        self.activity_entry = ttk.Entry(form, width=40)
        self.activity_entry.grid(row=1, column=1, pady=5, sticky='ew')

        # Date
        ttk.Label(form, text="Date:").grid(row=2, column=0, sticky='w', pady=5)
        self.date_entry = ttk.Entry(form, width=40)
        self.date_entry.grid(row=2, column=1, pady=5, sticky='ew')
        self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Hours
        ttk.Label(form, text="Hours:").grid(row=3, column=0, sticky='w', pady=5)
        self.hours_entry = ttk.Entry(form, width=40)
        self.hours_entry.grid(row=3, column=1, pady=5, sticky='ew')

        # Supervisor
        ttk.Label(form, text="Supervisor Name:").grid(row=4, column=0, sticky='w', pady=5)
        self.supervisor_entry = ttk.Entry(form, width=40)
        self.supervisor_entry.grid(row=4, column=1, pady=5, sticky='ew')

        # Supervisor Email
        ttk.Label(form, text="Supervisor Email:").grid(row=5, column=0, sticky='w', pady=5)
        self.supervisor_email_entry = ttk.Entry(form, width=40)
        self.supervisor_email_entry.grid(row=5, column=1, pady=5, sticky='ew')

        form.columnconfigure(1, weight=1)

        ttk.Button(form_frame, text="Submit for Verification", command=self.submit_hours).pack(pady=(0, 10))

        # Pending verification
        pending_frame = ttk.LabelFrame(main_frame, text="Pending Verification")
        pending_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Organization', 'Hours', 'Date', 'Status')
        tree = ttk.Treeview(pending_frame, columns=columns, show='tree headings', height=6)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample pending
        tree.insert('', 'end', values=("Food Bank", "4", "2025-03-28", "Pending"))
        tree.insert('', 'end', values=("Hospital", "2", "2025-03-25", "Verified ✓"))

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def submit_hours(self):
        org = self.org_entry.get().strip()
        hours = self.hours_entry.get().strip()
        supervisor = self.supervisor_entry.get().strip()

        if not all([org, hours, supervisor]):
            messagebox.showwarning("Warning", "Please fill in all required fields.")
            return

        messagebox.showinfo("Success", f"Hours submitted for verification!\n\nAn email has been sent to your supervisor for verification.\n\nHours: {hours}\nOrganization: {org}")

        # Clear form
        self.org_entry.delete(0, tk.END)
        self.activity_entry.delete(0, tk.END)
        self.hours_entry.delete(0, tk.END)
        self.supervisor_entry.delete(0, tk.END)
        self.supervisor_email_entry.delete(0, tk.END)


# ============================================================================
# ANALYTICS DIALOGS
# ============================================================================


class CommunityEngagementDialog:
    """Main dialog for community engagement"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Community Engagement")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="🤝 Community Engagement & Outreach",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Tabs for different features
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 10))

        # Tab 1: Community Projects
        projects_frame = ttk.Frame(notebook)
        notebook.add(projects_frame, text="Community Projects")
        self.create_projects_tab(projects_frame)

        # Tab 2: Engagement Analytics
        analytics_frame = ttk.Frame(notebook)
        notebook.add(analytics_frame, text="Engagement Analytics")
        self.create_analytics_tab(analytics_frame)

        # Tab 3: Retention Insights
        retention_frame = ttk.Frame(notebook)
        notebook.add(retention_frame, text="Retention Insights")
        self.create_retention_tab(retention_frame)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_projects_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Active Community Projects", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        columns = ('Project', 'Partners', 'Students', 'Impact', 'Status')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True)

        # Sample data
        projects = [
            ("Food Bank Support", "Local Food Bank", "45", "500 families helped", "Active"),
            ("Tutoring Program", "Primary School", "30", "150 students tutored", "Active"),
            ("Park Cleanup", "City Council", "60", "5 parks cleaned", "Completed"),
            ("Senior Center Visits", "Elderly Care Home", "25", "100 seniors visited", "Active")
        ]

        for project in projects:
            tree.insert('', 'end', values=project)

    def create_analytics_tab(self, parent):
        dialog = EngagementTrendAnalysisDialog(parent, self.auth, embedded=True)

    def create_retention_tab(self, parent):
        dialog = MemberRetentionInsightsDialog(parent, self.auth, embedded=True)



def open_volunteer_opportunities_dialog(self):
    """Open volunteer opportunities dialog"""
    dialog = VolunteerOpportunitiesDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_community_service_hours_dialog(self):
    """Open community service hours tracking dialog"""
    dialog = CommunityServiceHoursDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_community_engagement_dialog(self):
    """Open community engagement dialog"""
    dialog = CommunityEngagementDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


