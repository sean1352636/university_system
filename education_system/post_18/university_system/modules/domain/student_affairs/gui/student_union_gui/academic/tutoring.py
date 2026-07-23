import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
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
    from education_system.post_18.university_system.infrastructure.database.db import get_connection
    from education_system.post_18.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class PeerTutoringDialog:
    """Peer tutoring system"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Peer Tutoring")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_tutors()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="👨‍🏫 Peer Tutoring",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Top buttons
        top_btn_frame = ttk.Frame(main_frame)
        top_btn_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(top_btn_frame, text="🎓 Become a Tutor",
                  command=self.become_tutor).pack(side='left', padx=(0, 10))
        ttk.Button(top_btn_frame, text="📅 My Tutoring Schedule",
                  command=self.view_schedule).pack(side='left', padx=(0, 10))
        ttk.Button(top_btn_frame, text="📊 My Tutoring Hours",
                  command=self.view_hours).pack(side='left')

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Subject:").pack(side='left', padx=(0, 5))
        self.subject_var = tk.StringVar()
        subject_combo = ttk.Combobox(filter_frame, textvariable=self.subject_var, width=25, state='readonly')
        subject_combo['values'] = ('All Subjects', 'Computer Science', 'Mathematics',
                                   'Biology', 'Chemistry', 'Physics', 'English', 'History')
        subject_combo.current(0)
        subject_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text="Filter", command=self.load_tutors).pack(side='left')

        # Tutors list
        list_frame = ttk.LabelFrame(main_frame, text="Available Tutors")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Tutor', 'Subject', 'Rating', 'Sessions', 'Availability', 'Rate')
        self.tutors_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.tutors_tree.heading(col, text=col)
            if col == 'Tutor':
                self.tutors_tree.column(col, width=150)
            elif col == 'Subject':
                self.tutors_tree.column(col, width=180)
            else:
                self.tutors_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tutors_tree.yview)
        self.tutors_tree.configure(yscrollcommand=scrollbar.set)

        self.tutors_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.tutors_tree.bind('<<TreeviewSelect>>', self.on_select)

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Tutor Details")
        details_frame.pack(fill='x', pady=(0, 15))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=5, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Request Session", command=self.request_session).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Reviews", command=self.view_reviews).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_tutors(self):
        for item in self.tutors_tree.get_children():
            self.tutors_tree.delete(item)

        # Sample tutors
        tutors = [
            ("Sarah Johnson", "Computer Science (Python, Java)", "4.9/5", "45", "Mon/Wed 4-7PM", "Free",
             "CS senior, experienced with intro programming and data structures. Patient and encouraging!"),
            ("Michael Chen", "Mathematics (Calculus I-III)", "4.8/5", "38", "Tue/Thu 5-8PM", "Free",
             "Math major, tutoring calculus for 2 years. Specializes in breaking down complex concepts."),
            ("Emily Rodriguez", "Biology (General Bio, Anatomy)", "5.0/5", "52", "Wed/Fri 3-6PM", "Free",
             "Biology grad student. Can help with lecture review, lab reports, and exam prep."),
            ("David Kim", "Chemistry (Gen Chem, Organic)", "4.7/5", "29", "Mon/Thu 6-9PM", "Free",
             "Chemistry tutor for 1 year. Good at problem-solving strategies and lab techniques."),
            ("Jessica Lee", "Physics (Mechanics, E&M)", "4.9/5", "41", "Tue/Fri 4-7PM", "Free",
             "Physics major, loves helping students understand difficult concepts through examples.")
        ]

        for tutor in tutors:
            self.tutors_tree.insert('', 'end', values=tutor[:6], tags=(tutor[6],))

    def on_select(self, event):
        selection = self.tutors_tree.selection()
        if not selection:
            return

        item = self.tutors_tree.item(selection[0])
        details = item['tags'][0] if item['tags'] else "No details available."

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)

    def request_session(self):
        selection = self.tutors_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a tutor.")
            return

        item = self.tutors_tree.item(selection[0])
        tutor_name = item['values'][0]

        if messagebox.askyesno("Request Session",
                              f"Request a tutoring session with {tutor_name}?\n\n"
                              "You'll be able to select a time from their available slots."):
            messagebox.showinfo("Success",
                               "Tutoring session request sent!\n\n"
                               f"{tutor_name} will confirm your session request shortly.")

    def view_reviews(self):
        messagebox.showinfo("Tutor Reviews",
                           "Student Reviews:\n\n"
                           "⭐⭐⭐⭐⭐ 'Excellent tutor, very patient!'\n"
                           "⭐⭐⭐⭐⭐ 'Helped me improve my grade significantly'\n"
                           "⭐⭐⭐⭐ 'Clear explanations, very helpful'")

    def become_tutor(self):
        if messagebox.askyesno("Become a Tutor",
                              "Interested in becoming a peer tutor?\n\n"
                              "Requirements:\n"
                              "• GPA 3.5+ in subject area\n"
                              "• Professor recommendation\n"
                              "• Complete tutor training\n\n"
                              "Would you like to apply?"):
            messagebox.showinfo("Application",
                               "Tutor application process:\n\n"
                               "1. Fill out application form\n"
                               "2. Get professor recommendation\n"
                               "3. Attend training session\n"
                               "4. Start tutoring!\n\n"
                               "Applications reviewed weekly.")

    def view_schedule(self):
        messagebox.showinfo("My Schedule",
                           "Upcoming Tutoring Sessions:\n\n"
                           "Mon, Apr 14, 5PM - John Doe (CS101)\n"
                           "Wed, Apr 16, 6PM - Jane Smith (CS101)\n"
                           "Fri, Apr 18, 5PM - Bob Johnson (CS102)")

    def view_hours(self):
        messagebox.showinfo("Tutoring Hours",
                           "My Tutoring Statistics:\n\n"
                           "Total Hours: 24.5\n"
                           "Sessions Completed: 18\n"
                           "Average Rating: 4.8/5\n"
                           "Students Helped: 12")



class AcademicWorkshopsDialog:
    """Academic workshops and skill-building sessions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Academic Workshops")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_workshops()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🎯 Academic Workshops",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Category:").pack(side='left', padx=(0, 5))
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, width=25, state='readonly')
        category_combo['values'] = ('All Categories', 'Study Skills', 'Time Management',
                                    'Writing Skills', 'Research Skills', 'Test Strategies',
                                    'Note-Taking', 'Critical Thinking')
        category_combo.current(0)
        category_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text="Filter", command=self.load_workshops).pack(side='left')

        # Workshops list
        list_frame = ttk.LabelFrame(main_frame, text="Upcoming Workshops")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Workshop Title', 'Category', 'Date/Time', 'Location', 'Seats', 'Duration')
        self.workshops_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.workshops_tree.heading(col, text=col)
            if col == 'Workshop Title':
                self.workshops_tree.column(col, width=280)
            elif col == 'Category':
                self.workshops_tree.column(col, width=140)
            else:
                self.workshops_tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.workshops_tree.yview)
        self.workshops_tree.configure(yscrollcommand=scrollbar.set)

        self.workshops_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.workshops_tree.bind('<<TreeviewSelect>>', self.on_select)

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Workshop Description")
        details_frame.pack(fill='x', pady=(0, 15))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=5, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Register", command=self.register).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Materials", command=self.view_materials).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="My Workshops", command=self.my_workshops).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_workshops(self):
        for item in self.workshops_tree.get_children():
            self.workshops_tree.delete(item)

        # Sample workshops
        workshops = [
            ("Effective Note-Taking Strategies", "Study Skills", "Mon, Apr 14, 2PM", "Library 301", "12/20", "90 min",
             "Learn Cornell, mapping, and outline methods. Discover digital note-taking tools and organization strategies."),
            ("Time Management for Students", "Time Management", "Wed, Apr 16, 3PM", "Student Center 205", "8/25", "2 hours",
             "Master scheduling, prioritization, and avoiding procrastination. Create a personalized time management system."),
            ("Academic Writing Workshop", "Writing Skills", "Thu, Apr 17, 4PM", "Writing Center", "15/20", "2 hours",
             "Improve essay structure, argumentation, and citation. Get feedback on your writing from peers and experts."),
            ("Research Skills 101", "Research Skills", "Fri, Apr 18, 1PM", "Library 205", "10/15", "90 min",
             "Navigate academic databases, evaluate sources, and organize research. Perfect for research papers and projects."),
            ("Test-Taking Strategies", "Test Strategies", "Tue, Apr 15, 5PM", "Academic Building 110", "6/30", "75 min",
             "Learn strategies for multiple choice, essay, and short answer exams. Manage test anxiety effectively."),
            ("Speed Reading Techniques", "Study Skills", "Mon, Apr 21, 3PM", "Library 302", "14/25", "90 min",
             "Double your reading speed while maintaining comprehension. Learn skimming and scanning techniques."),
            ("Critical Thinking Skills", "Critical Thinking", "Wed, Apr 23, 2PM", "Philosophy Hall 101", "11/20", "2 hours",
             "Develop analytical and evaluative thinking skills. Apply logic and reasoning to academic challenges.")
        ]

        for workshop in workshops:
            self.workshops_tree.insert('', 'end', values=workshop[:6], tags=(workshop[6],))

    def on_select(self, event):
        selection = self.workshops_tree.selection()
        if not selection:
            return

        item = self.workshops_tree.item(selection[0])
        details = item['tags'][0] if item['tags'] else "No description available."

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)

    def register(self):
        selection = self.workshops_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a workshop.")
            return

        item = self.workshops_tree.item(selection[0])
        workshop_title = item['values'][0]

        if messagebox.askyesno("Register", f"Register for '{workshop_title}'?"):
            messagebox.showinfo("Success",
                               "Registration successful!\n\n"
                               "You'll receive a confirmation email with workshop details.")

    def view_materials(self):
        messagebox.showinfo("Workshop Materials",
                           "Workshop materials:\n\n"
                           "• Presentation slides\n"
                           "• Handouts and worksheets\n"
                           "• Recommended reading\n"
                           "• Practice exercises\n\n"
                           "Available after attendance")

    def my_workshops(self):
        messagebox.showinfo("My Workshops",
                           "Registered Workshops:\n\n"
                           "Upcoming:\n"
                           "• Note-Taking Strategies (Apr 14)\n"
                           "• Time Management (Apr 16)\n\n"
                           "Completed:\n"
                           "• Academic Writing (Mar 20)\n"
                           "• Research Skills (Feb 15)")



