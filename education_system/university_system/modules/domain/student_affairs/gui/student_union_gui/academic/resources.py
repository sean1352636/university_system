import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
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


class SharedResourcesDialog:
    """Shared academic resources platform"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Shared Academic Resources")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_resources()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📂 Shared Academic Resources",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Top button
        top_btn_frame = ttk.Frame(main_frame)
        top_btn_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(top_btn_frame, text="📤 Upload Resource",
                  command=self.upload_resource).pack(side='left')

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Course:").pack(side='left', padx=(0, 5))
        self.course_var = tk.StringVar()
        course_combo = ttk.Combobox(filter_frame, textvariable=self.course_var, width=25, state='readonly')
        course_combo['values'] = ('All Courses', 'CS101', 'MATH201', 'BIO150', 'CHEM101', 'PHYS200')
        course_combo.current(0)
        course_combo.pack(side='left', padx=(0, 15))

        ttk.Label(filter_frame, text="Type:").pack(side='left', padx=(0, 5))
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(filter_frame, textvariable=self.type_var, width=20, state='readonly')
        type_combo['values'] = ('All Types', 'Notes', 'Textbooks', 'Practice Problems',
                                'Study Guides', 'Past Exams')
        type_combo.current(0)
        type_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text="Filter", command=self.load_resources).pack(side='left')

        # Resources list
        list_frame = ttk.LabelFrame(main_frame, text="Available Resources")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Resource Name', 'Course', 'Type', 'Uploaded By', 'Date', 'Rating', 'Downloads')
        self.resources_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.resources_tree.heading(col, text=col)
            if col == 'Resource Name':
                self.resources_tree.column(col, width=250)
            elif col == 'Course':
                self.resources_tree.column(col, width=100)
            else:
                self.resources_tree.column(col, width=110)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.resources_tree.yview)
        self.resources_tree.configure(yscrollcommand=scrollbar.set)

        self.resources_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Download", command=self.download_resource).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Preview", command=self.preview_resource).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Rate Resource", command=self.rate_resource).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_resources(self):
        for item in self.resources_tree.get_children():
            self.resources_tree.delete(item)

        # Sample resources
        resources = [
            ("Python Basics - Comprehensive Notes", "CS101", "Notes", "Sarah J.", "Apr 1, 2025", "4.8/5", "142"),
            ("Calculus II Formula Sheet", "MATH201", "Study Guide", "Mike C.", "Mar 28, 2025", "4.9/5", "205"),
            ("Biology 150 - Chapter 5-8 Study Guide", "BIO150", "Study Guide", "Emily R.", "Apr 3, 2025", "5.0/5", "89"),
            ("Gen Chem Practice Problems with Solutions", "CHEM101", "Practice Problems", "David K.", "Mar 30, 2025", "4.7/5", "156"),
            ("Physics II - Past Exam Solutions", "PHYS200", "Past Exams", "Jessica L.", "Apr 5, 2025", "4.8/5", "178"),
            ("Data Structures Lecture Notes (Complete)", "CS102", "Notes", "Alex P.", "Apr 2, 2025", "4.9/5", "94"),
            ("Organic Chemistry Reaction Mechanisms", "CHEM201", "Study Guide", "Lisa M.", "Mar 29, 2025", "4.6/5", "67")
        ]

        for resource in resources:
            self.resources_tree.insert('', 'end', values=resource)

    def upload_resource(self):
        messagebox.showinfo("Upload Resource",
                           "Upload a new academic resource:\n\n"
                           "• Select file to upload\n"
                           "• Choose course\n"
                           "• Select resource type\n"
                           "• Add description\n\n"
                           "Help your peers succeed!")

    def download_resource(self):
        selection = self.resources_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a resource.")
            return

        item = self.resources_tree.item(selection[0])
        resource_name = item['values'][0]

        messagebox.showinfo("Download",
                           f"Downloading '{resource_name}'...\n\n"
                           "Resource will be saved to your downloads folder.")

    def preview_resource(self):
        selection = self.resources_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a resource to preview.")
            return

        item = self.resources_tree.item(selection[0])
        resource_name = item['values'][0]

        dialog = ResourcePreviewDialog(self.dialog, self.auth, resource_name)
        self.dialog.wait_window(dialog.dialog)

    def rate_resource(self):
        messagebox.showinfo("Rate Resource", "Rate this resource:\n\n⭐⭐⭐⭐⭐\n\nYour feedback helps others!")



class ResourcePreviewDialog:
    """Dialog for previewing academic resources"""

    def __init__(self, parent, auth_manager, resource_name):
        self.parent = parent
        self.auth = auth_manager
        self.resource_name = resource_name

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Preview: {resource_name}")
        self.dialog.geometry("800x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(header_frame, text="Resource Preview", font=('Arial', 14, 'bold')).pack(side='left')

        # Resource info
        info_frame = ttk.LabelFrame(main_frame, text="Resource Information")
        info_frame.pack(fill='x', pady=(0, 15))

        info_grid = ttk.Frame(info_frame)
        info_grid.pack(padx=15, pady=10, fill='x')

        ttk.Label(info_grid, text="Name:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        ttk.Label(info_grid, text=self.resource_name).grid(row=0, column=1, sticky='w', padx=10, pady=5)

        ttk.Label(info_grid, text="Type:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        ttk.Label(info_grid, text="Study Notes").grid(row=1, column=1, sticky='w', padx=10, pady=5)

        ttk.Label(info_grid, text="Course:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
        ttk.Label(info_grid, text="CS101").grid(row=2, column=1, sticky='w', padx=10, pady=5)

        ttk.Label(info_grid, text="Uploaded by:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=5)
        ttk.Label(info_grid, text="Sarah J.").grid(row=3, column=1, sticky='w', padx=10, pady=5)

        ttk.Label(info_grid, text="Rating:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='w', pady=5)
        ttk.Label(info_grid, text="⭐⭐⭐⭐⭐ 4.8/5 (142 downloads)").grid(row=4, column=1, sticky='w', padx=10, pady=5)

        # Preview content
        preview_frame = ttk.LabelFrame(main_frame, text="Content Preview")
        preview_frame.pack(fill='both', expand=True, pady=(0, 15))

        # Scrolled text for preview
        self.preview_text = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, font=('Courier', 10))
        self.preview_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Sample preview content
        preview_content = f"""PYTHON BASICS - COMPREHENSIVE NOTES
================================================================================

CHAPTER 1: INTRODUCTION TO PYTHON

What is Python?
- High-level, interpreted programming language
- Created by Guido van Rossum in 1991
- Emphasizes code readability and simplicity
- Used for web development, data science, AI, automation, and more

Key Features:
✓ Easy to learn and read
✓ Large standard library
✓ Cross-platform compatibility
✓ Dynamic typing
✓ Automatic memory management

CHAPTER 2: VARIABLES AND DATA TYPES

Variables:
- Containers for storing data values
- No declaration needed (dynamic typing)
- Names must start with letter or underscore

Example:
    name = "Alice"
    age = 25
    height = 5.6
    is_student = True

Data Types:
1. int - Integer numbers (e.g., 42, -10, 0)
2. float - Decimal numbers (e.g., 3.14, -0.5)
3. str - Text strings (e.g., "Hello", 'World')
4. bool - Boolean values (True or False)
5. list - Ordered, mutable collections [1, 2, 3]
6. tuple - Ordered, immutable collections (1, 2, 3)
7. dict - Key-value pairs {{"name": "Alice", "age": 25}}

CHAPTER 3: OPERATORS

Arithmetic Operators:
+ Addition        5 + 3 = 8
- Subtraction     5 - 3 = 2
* Multiplication  5 * 3 = 15
/ Division        5 / 2 = 2.5
// Floor Division 5 // 2 = 2
% Modulus         5 % 2 = 1
** Exponentiation 5 ** 2 = 25

Comparison Operators:
== Equal to
!= Not equal to
> Greater than
< Less than
>= Greater than or equal to
<= Less than or equal to

CHAPTER 4: CONTROL STRUCTURES

If Statements:
    if condition:
        # code block
    elif another_condition:
        # code block
    else:
        # code block

For Loops:
    for item in iterable:
        # process item

While Loops:
    while condition:
        # code block

CHAPTER 5: FUNCTIONS

Defining Functions:
    def function_name(parameters):
        # function body
        return value

Example:
    def greet(name):
        return f"Hello, {{name}}!"

    result = greet("Alice")  # Returns "Hello, Alice!"

TIPS FOR SUCCESS:
- Practice coding daily
- Start with simple programs
- Use Python documentation
- Join coding communities
- Work on projects you're passionate about

================================================================================
END OF PREVIEW - Full notes available after download
"""
        self.preview_text.insert(1.0, preview_content)
        self.preview_text.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Download Full Resource",
                  command=self.download_resource).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Rate Resource",
                  command=lambda: messagebox.showinfo("Rate", "⭐⭐⭐⭐⭐\n\nYour rating has been recorded!")).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def download_resource(self):
        messagebox.showinfo("Download", f"Downloading '{self.resource_name}'...\n\nFull resource will be saved to your downloads folder.")



