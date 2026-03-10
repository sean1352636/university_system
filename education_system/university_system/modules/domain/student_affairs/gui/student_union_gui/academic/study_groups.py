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
    

class StudyGroupsDialog:
    """Study group management platform"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Study Groups")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_groups()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📚 Study Groups",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Course:").pack(side='left', padx=(0, 5))
        self.course_var = tk.StringVar()
        course_combo = ttk.Combobox(filter_frame, textvariable=self.course_var, width=25, state='readonly')
        course_combo['values'] = ('All Courses', 'CS101 - Intro to Programming',
                                  'MATH201 - Calculus II', 'BIO150 - Biology',
                                  'CHEM101 - General Chemistry', 'PHYS200 - Physics II')
        course_combo.current(0)
        course_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text="Filter", command=self.load_groups).pack(side='left', padx=(0, 20))
        ttk.Button(filter_frame, text="➕ Create Study Group",
                  command=self.create_group).pack(side='left')

        # Groups list
        list_frame = ttk.LabelFrame(main_frame, text="Available Study Groups")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Course', 'Group Name', 'Members', 'Next Session', 'Location', 'Status')
        self.groups_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.groups_tree.heading(col, text=col)
            if col == 'Course':
                self.groups_tree.column(col, width=150)
            elif col == 'Group Name':
                self.groups_tree.column(col, width=180)
            else:
                self.groups_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=scrollbar.set)

        self.groups_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.groups_tree.bind('<<TreeviewSelect>>', self.on_select)

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Group Details")
        details_frame.pack(fill='x', pady=(0, 15))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=5, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Join Group", command=self.join_group).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Schedule Session", command=self.schedule_session).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Share Materials", command=self.share_materials).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_groups(self):
        for item in self.groups_tree.get_children():
            self.groups_tree.delete(item)

        # Sample study groups
        groups = [
            ("CS101", "Python Basics Study Group", "5/8", "Mon, Apr 14, 7PM", "Library Room 203", "Open",
             "Weekly study sessions covering Python fundamentals, homework help, and project collaboration."),
            ("MATH201", "Calculus II Mastery", "6/10", "Wed, Apr 16, 6PM", "Math Building 105", "Open",
             "Working through problem sets together, reviewing lecture material, and preparing for exams."),
            ("BIO150", "Biology Study Squad", "4/6", "Thu, Apr 17, 5PM", "Science Center 201", "Open",
             "Chapter reviews, lab report help, and exam preparation for Biology 150."),
            ("CHEM101", "Chem Study Crew", "7/12", "Tue, Apr 15, 7:30PM", "Chemistry Lab 3", "Open",
             "Problem-solving sessions, lab review, and test preparation strategies."),
            ("PHYS200", "Physics II Workshop", "3/8", "Fri, Apr 18, 4PM", "Physics Building 110", "Open",
             "Collaborative problem solving and concept clarification for Physics II topics.")
        ]

        for group in groups:
            self.groups_tree.insert('', 'end', values=group[:6], tags=(group[6],))

    def on_select(self, event):
        selection = self.groups_tree.selection()
        if not selection:
            return

        item = self.groups_tree.item(selection[0])
        details = item['tags'][0] if item['tags'] else "No details available."

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)

    def join_group(self):
        selection = self.groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a study group.")
            return

        item = self.groups_tree.item(selection[0])
        group_name = item['values'][1]

        if messagebox.askyesno("Confirm", f"Join '{group_name}'?"):
            messagebox.showinfo("Success",
                               f"You've joined '{group_name}'!\n\n"
                               "You'll receive notifications about upcoming sessions.")

    def schedule_session(self):
        messagebox.showinfo("Schedule Session",
                           "Schedule a new study session:\n\n"
                           "• Select date and time\n"
                           "• Choose location\n"
                           "• Set agenda/topics\n"
                           "• Notify group members")

    def share_materials(self):
        messagebox.showinfo("Share Materials",
                           "Share study materials with your group:\n\n"
                           "• Upload notes\n"
                           "• Share practice problems\n"
                           "• Post helpful resources")

    def create_group(self):
        dialog = CreateStudyGroupDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class CreateStudyGroupDialog:
    """Create a new study group"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Study Group")
        self.dialog.geometry("700x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="➕ Create New Study Group",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True, pady=(0, 15))

        ttk.Label(form_frame, text="Course:").grid(row=0, column=0, sticky='w', pady=5)
        self.course_combo = ttk.Combobox(form_frame, width=47, state='readonly')
        self.course_combo['values'] = ('CS101 - Intro to Programming', 'MATH201 - Calculus II',
                                        'BIO150 - Biology', 'CHEM101 - General Chemistry')
        self.course_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Group Name:").grid(row=1, column=0, sticky='w', pady=5)
        self.name_entry = ttk.Entry(form_frame, width=50)
        self.name_entry.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        self.desc_text = scrolledtext.ScrolledText(form_frame, width=50, height=3)
        self.desc_text.grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Member Limit:").grid(row=3, column=0, sticky='w', pady=5)
        self.limit_spin = ttk.Spinbox(form_frame, from_=3, to=20, width=10)
        self.limit_spin.grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))
        self.limit_spin.set(8)

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Create", command=self.create).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='right')

    def create(self):
        if not self.name_entry.get():
            messagebox.showwarning("Warning", "Please enter a group name.")
            return

        messagebox.showinfo("Success", "Study group created successfully!")
        self.dialog.destroy()



class ExamPrepGroupsDialog:
    """Exam preparation groups"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Exam Preparation Groups")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_groups()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📝 Exam Preparation Groups",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Info banner
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill='x', pady=(0, 15))

        info_text = ("Join exam-specific study groups to prepare together. Share practice materials, "
                    "quiz each other, and support your peers!")
        ttk.Label(info_frame, text=info_text, wraplength=1000).pack()

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Course:").pack(side='left', padx=(0, 5))
        self.course_var = tk.StringVar()
        course_combo = ttk.Combobox(filter_frame, textvariable=self.course_var, width=25, state='readonly')
        course_combo['values'] = ('All Courses', 'CS101', 'MATH201', 'BIO150', 'CHEM101', 'PHYS200')
        course_combo.current(0)
        course_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text="Filter", command=self.load_groups).pack(side='left', padx=(0, 20))
        ttk.Button(filter_frame, text="➕ Create Exam Prep Group",
                  command=self.create_group).pack(side='left')

        # Groups list
        list_frame = ttk.LabelFrame(main_frame, text="Upcoming Exam Prep Groups")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Course', 'Exam Date', 'Group Name', 'Members', 'Next Session', 'Focus')
        self.groups_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.groups_tree.heading(col, text=col)
            if col == 'Group Name':
                self.groups_tree.column(col, width=180)
            elif col == 'Focus':
                self.groups_tree.column(col, width=200)
            else:
                self.groups_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=scrollbar.set)

        self.groups_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Join Group", command=self.join_group).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Study Schedule", command=self.view_schedule).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Practice Tests", command=self.practice_tests).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_groups(self):
        for item in self.groups_tree.get_children():
            self.groups_tree.delete(item)

        # Sample exam prep groups
        groups = [
            ("CS101", "Apr 22, 2025", "Midterm Crashers", "8/15", "Mon, Apr 14, 8PM", "Chapters 1-5, Algorithms"),
            ("MATH201", "Apr 25, 2025", "Calc II Conquerors", "6/12", "Tue, Apr 15, 7PM", "Integration techniques"),
            ("BIO150", "Apr 20, 2025", "Bio Exam Warriors", "10/15", "Wed, Apr 16, 6PM", "Cell biology, genetics"),
            ("CHEM101", "Apr 23, 2025", "Chem Final Prep", "5/10", "Thu, Apr 17, 7:30PM", "Stoichiometry, bonding"),
            ("PHYS200", "Apr 24, 2025", "Physics Study Marathon", "7/12", "Fri, Apr 18, 5PM", "Electromagnetism")
        ]

        for group in groups:
            self.groups_tree.insert('', 'end', values=group)

    def join_group(self):
        selection = self.groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an exam prep group.")
            return

        item = self.groups_tree.item(selection[0])
        group_name = item['values'][2]

        if messagebox.askyesno("Confirm", f"Join '{group_name}'?"):
            messagebox.showinfo("Success",
                               f"You've joined '{group_name}'!\n\n"
                               "Check your email for session details and study materials.")

    def create_group(self):
        messagebox.showinfo("Create Group",
                           "Create an exam prep group:\n\n"
                           "• Select course and exam date\n"
                           "• Name your group\n"
                           "• Define study schedule\n"
                           "• Invite classmates")

    def view_schedule(self):
        messagebox.showinfo("Study Schedule",
                           "Exam Prep Study Schedule:\n\n"
                           "Week 1: Review chapters 1-3\n"
                           "Week 2: Practice problems, chapters 4-5\n"
                           "Week 3: Past exams, mock tests\n"
                           "Final Week: Last-minute review")

    def practice_tests(self):
        messagebox.showinfo("Practice Tests",
                           "Available Practice Resources:\n\n"
                           "• Past exam papers\n"
                           "• Practice quiz bank\n"
                           "• Timed mock exams\n"
                           "• Solution explanations")



