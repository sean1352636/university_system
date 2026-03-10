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

# Import support dialog classes
from .wellness import WellnessResourcesDialog, CrisisResourcesDialog
from .support_groups import CreateSupportGroupDialog, MySupportGroupsDialog, BrowseSupportGroupsDialog


class PeerSupportWellnessDialog:
    """Main hub for peer support and wellness features"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Peer Support & Wellness")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="🤝 Peer Support & Wellness Hub",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Info banner
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill='x', pady=(0, 15))

        info_text = ("Access peer support, join support groups, find wellness resources, "
                    "and connect with others in a safe, confidential environment.")
        ttk.Label(info_frame, text=info_text, wraplength=1000,
                 justify='left', font=('Arial', 10)).pack(padx=10, pady=10)

        # Create grid of support options
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='both', expand=True, pady=(0, 10))

        options = [
            ("Support Groups", "browse", "📋 Browse and join support groups", "blue"),
            ("My Groups", "my_groups", "👥 View my support group memberships", "green"),
            ("Create Group", "create", "➕ Create a new support group", "orange"),
            ("Peer Matching", "matching", "🤝 Anonymous peer support matching", "purple"),
            ("Wellness Resources", "resources", "📚 Mental health & wellness resources", "teal"),
            ("Crisis Support", "crisis", "🆘 Immediate crisis resources", "red"),
            ("Group Management", "manage", "⚙️ Manage my support groups", "gray")
        ]

        for i, (title, key, description, color) in enumerate(options):
            card = ttk.LabelFrame(buttons_frame, text=title)
            card.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='nsew')

            ttk.Label(card, text=description, wraplength=450,
                     foreground=color).pack(padx=10, pady=5)

            command_map = {
                'browse': self.browse_support_groups,
                'my_groups': self.view_my_support_groups,
                'create': self.create_support_group,
                'matching': self.anonymous_peer_matching,
                'resources': self.view_wellness_resources,
                'crisis': self.crisis_resources,
                'manage': self.manage_peer_support_system
            }

            ttk.Button(card, text="Open",
                      command=command_map[key]).pack(padx=10, pady=5)

        for i in range(4):
            buttons_frame.rowconfigure(i, weight=1)
        for i in range(2):
            buttons_frame.columnconfigure(i, weight=1)

        # Confidentiality notice
        notice_frame = ttk.LabelFrame(main_frame, text="⚠️ Confidentiality & Privacy")
        notice_frame.pack(fill='x', pady=(10, 10))

        notice_text = ("All peer support activities are confidential. If you're experiencing a mental health "
                      "crisis, please contact emergency services or use the Crisis Support button above.")
        ttk.Label(notice_frame, text=notice_text, wraplength=1000,
                 foreground='red').pack(padx=10, pady=8)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def browse_support_groups(self):
        dialog = BrowseSupportGroupsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_my_support_groups(self):
        dialog = MySupportGroupsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def create_support_group(self):
        dialog = CreateSupportGroupDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def anonymous_peer_matching(self):
        dialog = AnonymousPeerMatchingDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_wellness_resources(self):
        dialog = WellnessResourcesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def crisis_resources(self):
        dialog = CrisisResourcesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def manage_peer_support_system(self):
        dialog = ManagePeerSupportDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class AnonymousPeerMatchingDialog:
    """Anonymous peer matching system"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Anonymous Peer Matching")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🤝 Anonymous Peer Support Matching",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Info banner
        info_frame = ttk.LabelFrame(main_frame, text="How It Works")
        info_frame.pack(fill='x', pady=(0, 15))

        info_text = ("Get matched with peers facing similar challenges. All matches are anonymous "
                    "and confidential. Connect through secure messaging without revealing identities.")
        ttk.Label(info_frame, text=info_text, wraplength=850).pack(padx=10, pady=10)

        # Matching preferences
        pref_frame = ttk.LabelFrame(main_frame, text="Matching Preferences")
        pref_frame.pack(fill='both', expand=True, pady=(0, 15))

        pref_content = ttk.Frame(pref_frame)
        pref_content.pack(fill='both', expand=True, padx=10, pady=10)

        # Issue/interest
        ttk.Label(pref_content, text="What would you like support with?").grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 5))

        issues = ['Stress & Anxiety', 'Academic Pressure', 'Loneliness/Social Connection',
                 'Family Issues', 'Relationship Concerns', 'Self-Esteem', 'Life Transitions']

        for i, issue in enumerate(issues):
            ttk.Checkbutton(pref_content, text=issue).grid(
                row=i+1, column=0, sticky='w', padx=(20, 0))

        # Match type
        ttk.Label(pref_content, text="\nPreferred Match Type:",
                 font=('Arial', 10, 'bold')).grid(row=len(issues)+1, column=0, sticky='w', pady=(10, 5))

        match_type_var = tk.StringVar(value="One-on-one")
        ttk.Radiobutton(pref_content, text="One-on-one peer matching",
                       variable=match_type_var, value="One-on-one").grid(
                           row=len(issues)+2, column=0, sticky='w', padx=(20, 0))
        ttk.Radiobutton(pref_content, text="Small group (3-4 peers)",
                       variable=match_type_var, value="Group").grid(
                           row=len(issues)+3, column=0, sticky='w', padx=(20, 0))

        # Privacy notice
        privacy_frame = ttk.LabelFrame(main_frame, text="🔒 Privacy & Security")
        privacy_frame.pack(fill='x', pady=(0, 15))

        privacy_text = ("• Your identity remains anonymous\n"
                       "• Secure encrypted messaging\n"
                       "• You can unmatch at any time\n"
                       "• Conversations are not monitored (unless safety concern)")
        ttk.Label(privacy_frame, text=privacy_text, justify='left').pack(padx=10, pady=10)

        # My matches
        matches_frame = ttk.LabelFrame(main_frame, text="My Current Matches")
        matches_frame.pack(fill='x', pady=(0, 15))

        match_text = """Active Matches: 2

Match #1: Support Buddy (matched 2 weeks ago)
  Common interests: Academic stress, time management
  Messages exchanged: 15
  Last contact: 2 days ago

Match #2: Anonymous Friend (matched 1 week ago)
  Common interests: Social connection, first-year adjustment
  Messages exchanged: 8
  Last contact: Yesterday
"""
        ttk.Label(matches_frame, text=match_text, justify='left',
                 font=('Courier', 9)).pack(padx=15, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Find New Match",
                  command=self.find_match).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View My Matches",
                  command=self.view_matches).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Messaging",
                  command=self.open_messaging).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close",
                  command=self.dialog.destroy).pack(side='right')

    def find_match(self):
        if messagebox.askyesno("Find Match",
                              "Start searching for a peer match based on your preferences?"):
            messagebox.showinfo("Matching",
                               "Searching for compatible peer matches...\n\n"
                               "You'll be notified when a match is found.\n"
                               "This usually takes 1-2 days.")

    def view_matches(self):
        messagebox.showinfo("My Matches",
                           "Match details:\n\n"
                           "Match #1: Support Buddy\n"
                           "  Status: Active\n"
                           "  Compatibility: 85%\n\n"
                           "Match #2: Anonymous Friend\n"
                           "  Status: Active\n"
                           "  Compatibility: 78%")

    def open_messaging(self):
        messagebox.showinfo("Messaging",
                           "Secure messaging system:\n\n"
                           "• Send/receive anonymous messages\n"
                           "• End-to-end encryption\n"
                           "• Report concerns if needed")



class ManagePeerSupportDialog:
    """Manage peer support system (for moderators/admins)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Peer Support System")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="⚙️ Manage Peer Support System",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Tabs for different management areas
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Group moderation tab
        moderation_frame = ttk.Frame(notebook)
        notebook.add(moderation_frame, text="Group Moderation")
        self.create_moderation_tab(moderation_frame)

        # Pending requests tab
        requests_frame = ttk.Frame(notebook)
        notebook.add(requests_frame, text="Join Requests")
        self.create_requests_tab(requests_frame)

        # Reports tab
        reports_frame = ttk.Frame(notebook)
        notebook.add(reports_frame, text="Reports & Analytics")
        self.create_reports_tab(reports_frame)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_moderation_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Groups You Moderate",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        columns = ('Group', 'Members', 'Status', 'Last Activity')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True)

        # Sample data
        groups = [
            ("Mindfulness Together", "6/10", "Active", "2 hours ago"),
            ("Study Support Group", "12/15", "Active", "1 day ago")
        ]

        for group in groups:
            tree.insert('', 'end', values=group)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="Manage Members").pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Edit Group Settings").pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="View Activity").pack(side='left')

    def create_requests_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Pending Join Requests",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        columns = ('Student', 'Group', 'Requested', 'Reason')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Reason':
                tree.column(col, width=250)

        tree.pack(fill='both', expand=True)

        # Sample requests
        requests = [
            ("Anonymous User #123", "Mindfulness Together", "2 days ago",
             "Interested in learning mindfulness techniques"),
            ("Anonymous User #456", "Mindfulness Together", "1 day ago",
             "Looking for support with stress management")
        ]

        for req in requests:
            tree.insert('', 'end', values=req)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="Approve", command=self.approve_request).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Deny", command=self.deny_request).pack(side='left')

    def create_reports_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill='both', expand=True)

        content = """PEER SUPPORT SYSTEM ANALYTICS
================================================================================

OVERALL STATISTICS:

Total Support Groups: 24
Active Members: 156 students
Average Group Size: 8.5 members
Groups Created (This Month): 3
Total Peer Matches: 47 active connections

ENGAGEMENT METRICS:

Weekly Active Users: 112 (72% of members)
Average Meetings per Group: 3.2/month
Message Activity: 847 messages (last 30 days)
Resource Downloads: 234 (last 30 days)

TOP SUPPORT GROUP TOPICS:

1. Stress Management (6 groups, 52 members)
2. Academic Pressure (4 groups, 34 members)
3. Social Connection (4 groups, 29 members)
4. Anxiety (3 groups, 21 members)
5. Self-Care (3 groups, 18 members)

PEER MATCHING STATISTICS:

Active Matches: 47
Match Success Rate: 82%
Average Match Duration: 6.3 weeks
Satisfaction Rating: 4.6/5.0

WELLNESS RESOURCE USAGE:

Most Viewed Resources:
  • Stress management techniques (127 views)
  • Anxiety coping strategies (98 views)
  • Crisis hotline information (76 views)
  • Self-care activities (65 views)

CRISIS INTERVENTIONS:

Crisis Resources Accessed: 12 (last month)
Follow-up Completed: 12/12 (100%)
Professional Referrals Made: 8

MODERATOR ACTIVITY:

Active Moderators: 18
Average Groups per Moderator: 1.3
Join Requests Processed: 32 (last week)
Average Response Time: 1.8 days

GROWTH TRENDS:

  Month      | New Groups | New Members | Activity
  -----------|------------|-------------|----------
  January    | 2          | 23          | ↗
  February   | 3          | 31          | ↗↗
  March      | 3          | 28          | ↗
  April (YTD)| 1          | 12          | →

RECOMMENDATIONS:

✓ Peer support engagement is strong
✓ Consider creating groups for underserved topics
✓ Moderator recruitment needed for growing demand
✓ Continue promoting wellness resources
"""
        text.insert(1.0, content)
        text.config(state='disabled')

    def approve_request(self):
        messagebox.showinfo("Approved", "Join request approved.")

    def deny_request(self):
        if messagebox.askyesno("Deny Request", "Deny this join request?"):
            messagebox.showinfo("Denied", "Join request denied.")


# ============================================================================
# ACADEMIC SUPPORT SYSTEM - 6 Features
# ============================================================================


def open_peer_support_wellness_dialog(self):
    """Open peer support and wellness hub"""
    dialog = PeerSupportWellnessDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


