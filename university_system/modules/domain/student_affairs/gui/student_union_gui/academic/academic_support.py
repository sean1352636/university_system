import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False

# Import academic dialog classes
from .resources import SharedResourcesDialog
from .tutoring import PeerTutoringDialog, AcademicWorkshopsDialog
from .study_groups import StudyGroupsDialog, ExamPrepGroupsDialog


class AcademicSupportDialog:
    """Main hub for academic support features"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Academic Support Hub")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="🎓 Academic Support Hub",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Info banner
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill='x', pady=(0, 15))

        info_text = ("Access peer tutoring, study groups, shared academic resources, "
                    "exam preparation support, and academic workshops.")
        ttk.Label(info_frame, text=info_text, wraplength=1000,
                 justify='left', font=('Arial', 10)).pack(padx=10, pady=10)

        # Create grid of support options
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='both', expand=True, pady=(0, 10))

        options = [
            ("Study Groups", "study_groups", "📚 Join or create study groups", "blue"),
            ("Peer Tutoring", "tutoring", "👨‍🏫 Find tutors or become one", "green"),
            ("Shared Resources", "resources", "📂 Notes, textbooks, study guides", "orange"),
            ("Exam Prep Groups", "exam_prep", "📝 Prepare for exams together", "purple"),
            ("Academic Workshops", "workshops", "🎯 Skill-building workshops", "teal"),
            ("My Academic Activity", "my_activity", "📊 Track my participation", "gray")
        ]

        for i, (title, key, description, color) in enumerate(options):
            card = ttk.LabelFrame(buttons_frame, text=title)
            card.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='nsew')

            ttk.Label(card, text=description, wraplength=450,
                     foreground=color).pack(padx=10, pady=5)

            command_map = {
                'study_groups': self.manage_study_groups,
                'tutoring': self.manage_peer_tutoring,
                'resources': self.manage_shared_resources,
                'exam_prep': self.exam_preparation_groups,
                'workshops': self.view_academic_workshops,
                'my_activity': self.view_my_activity
            }

            ttk.Button(card, text="Open",
                      command=command_map[key]).pack(padx=10, pady=5)

        for i in range(3):
            buttons_frame.rowconfigure(i, weight=1)
        for i in range(2):
            buttons_frame.columnconfigure(i, weight=1)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def manage_study_groups(self):
        dialog = StudyGroupsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def manage_peer_tutoring(self):
        dialog = PeerTutoringDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def manage_shared_resources(self):
        dialog = SharedResourcesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def exam_preparation_groups(self):
        dialog = ExamPrepGroupsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_academic_workshops(self):
        dialog = AcademicWorkshopsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_my_activity(self):
        dialog = MyAcademicActivityDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class MyAcademicActivityDialog:
    """View student's academic support activity"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Academic Activity")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📊 My Academic Support Activity",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create notebook for different activity areas
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Study groups tab
        study_groups_frame = ttk.Frame(notebook)
        notebook.add(study_groups_frame, text="Study Groups")
        self.create_study_groups_tab(study_groups_frame)

        # Tutoring tab
        tutoring_frame = ttk.Frame(notebook)
        notebook.add(tutoring_frame, text="Tutoring")
        self.create_tutoring_tab(tutoring_frame)

        # Resources tab
        resources_frame = ttk.Frame(notebook)
        notebook.add(resources_frame, text="My Resources")
        self.create_resources_tab(resources_frame)

        # Workshops tab
        workshops_frame = ttk.Frame(notebook)
        notebook.add(workshops_frame, text="Workshops")
        self.create_workshops_tab(workshops_frame)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_study_groups_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="My Study Groups",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        columns = ('Group', 'Course', 'Members', 'Sessions Attended', 'Next Meeting')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True)

        # Sample data
        groups = [
            ("Python Basics", "CS101", "5/8", "6", "Mon, Apr 14, 7PM"),
            ("Calculus II Mastery", "MATH201", "6/10", "4", "Wed, Apr 16, 6PM")
        ]

        for group in groups:
            tree.insert('', 'end', values=group)

        stats_label = ttk.Label(frame, text="\nTotal study hours: 15\nGroups joined: 2",
                               font=('Arial', 10))
        stats_label.pack(pady=(10, 0))

    def create_tutoring_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill='both', expand=True)

        content = """TUTORING ACTIVITY
================================================================================

AS A TUTEE (Receiving Tutoring):

Subjects: Computer Science, Mathematics
Total Sessions: 8
Total Hours: 12
Tutors: Sarah Johnson (CS), Michael Chen (Math)
Average Rating Given: 4.9/5

Upcoming Sessions:
  • Apr 14, 5PM - Sarah Johnson (Python debugging)
  • Apr 16, 6PM - Michael Chen (Integration techniques)

Progress Notes:
  • Improved Python programming skills significantly
  • Better understanding of calculus concepts
  • More confident with problem-solving


AS A TUTOR (Providing Tutoring):

Subject: Biology
Students Helped: 3
Total Sessions: 5
Total Hours: 7.5
Average Rating Received: 5.0/5

Recent Sessions:
  • Apr 10 - Helped with cell biology concepts
  • Apr 8 - Reviewed genetics problems
  • Apr 5 - Lab report assistance

Student Feedback:
  ⭐⭐⭐⭐⭐ "Very patient and helpful!"
  ⭐⭐⭐⭐⭐ "Excellent explanations"
  ⭐⭐⭐⭐⭐ "Made difficult concepts easy to understand"
"""
        text.insert(1.0, content)
        text.config(state='disabled')

    def create_resources_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Resources I've Shared",
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        columns = ('Resource', 'Course', 'Type', 'Downloads', 'Rating')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=6)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Resource':
                tree.column(col, width=300)

        tree.pack(fill='both', expand=True)

        # Sample uploaded resources
        resources = [
            ("Biology Chapter 5 Notes", "BIO150", "Notes", "42", "4.9/5"),
            ("CS101 Midterm Study Guide", "CS101", "Study Guide", "38", "5.0/5")
        ]

        for resource in resources:
            tree.insert('', 'end', values=resource)

        ttk.Label(frame, text="\nTotal uploads: 2 | Total downloads: 80 | Avg rating: 4.95/5",
                 font=('Arial', 10)).pack(pady=(10, 0))

    def create_workshops_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill='both', expand=True)

        content = """WORKSHOP ATTENDANCE
================================================================================

COMPLETED WORKSHOPS:

1. Academic Writing Workshop
   Date: Mar 20, 2025
   Duration: 2 hours
   Certificate: ✓ Earned
   Rating Given: ⭐⭐⭐⭐⭐
   Notes: Learned essay structure, improved citation skills

2. Research Skills 101
   Date: Feb 15, 2025
   Duration: 90 minutes
   Certificate: ✓ Earned
   Rating Given: ⭐⭐⭐⭐
   Notes: Database navigation, source evaluation

3. Test-Taking Strategies
   Date: Jan 28, 2025
   Duration: 75 minutes
   Certificate: ✓ Earned
   Rating Given: ⭐⭐⭐⭐⭐
   Notes: Reduced test anxiety, learned time management


UPCOMING REGISTRATIONS:

1. Note-Taking Strategies
   Date: Apr 14, 2025, 2PM
   Location: Library 301

2. Time Management for Students
   Date: Apr 16, 2025, 3PM
   Location: Student Center 205


STATISTICS:

Workshops Completed: 3
Total Hours: 5.25
Certificates Earned: 3
Average Rating Given: 4.7/5

Skills Developed:
  ✓ Academic writing
  ✓ Research methodology
  ✓ Test preparation
  ✓ Time management (in progress)
  ✓ Note-taking (registered)
"""
        text.insert(1.0, content)
        text.config(state='disabled')


# ============================================================================
# LEARNING INTEGRATION SYSTEM - 4 Features
# ============================================================================


class LearningIntegrationDialog:
    """Main hub for learning integration and academic event features"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Learning Integration")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="🎓 Learning Integration Hub",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Info banner
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill='x', pady=(0, 15))

        info_text = ("Integrate academic learning with student union activities. Organize conferences, "
                    "showcase research, earn course credit, and track learning outcomes.")
        ttk.Label(info_frame, text=info_text, wraplength=950,
                 justify='left', font=('Arial', 10)).pack(padx=10, pady=10)

        # Create grid of learning options
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='both', expand=True, pady=(0, 10))

        options = [
            ("Academic Conferences", "conferences", "📚 Organize and attend academic conferences", "blue"),
            ("Research Presentations", "research", "🔬 Showcase research and poster sessions", "green"),
            ("Learning Analytics", "analytics", "📊 Track learning outcomes and skills", "purple"),
            ("Course Credit Events", "credit", "🎯 Events eligible for course credit", "orange")
        ]

        for i, (title, key, description, color) in enumerate(options):
            card = ttk.LabelFrame(buttons_frame, text=title)
            card.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='nsew')

            ttk.Label(card, text=description, wraplength=420,
                     foreground=color).pack(padx=10, pady=5)

            command_map = {
                'conferences': self.organize_academic_conferences,
                'research': self.research_presentation_platform,
                'analytics': self.learning_analytics_dashboard,
                'credit': self.course_credit_events
            }

            ttk.Button(card, text="Open",
                      command=command_map[key]).pack(padx=10, pady=5)

        for i in range(2):
            buttons_frame.rowconfigure(i, weight=1)
            buttons_frame.columnconfigure(i, weight=1)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def organize_academic_conferences(self):
        dialog = AcademicConferencesOrganizerDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def research_presentation_platform(self):
        dialog = ResearchPresentationDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def learning_analytics_dashboard(self):
        dialog = LearningAnalyticsDashboardDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def course_credit_events(self):
        messagebox.showinfo("Course Credit Events",
                           "Events eligible for academic course credit:\n\n"
                           "• Student Union Leadership Seminar (1 credit)\n"
                           "• Event Management Workshop Series (2 credits)\n"
                           "• Community Engagement Project (3 credits)\n"
                           "• Research Conference Participation (1 credit)\n\n"
                           "Contact your academic advisor to register.")



def open_academic_support_dialog(self):
    """Open academic support hub"""
    dialog = AcademicSupportDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


