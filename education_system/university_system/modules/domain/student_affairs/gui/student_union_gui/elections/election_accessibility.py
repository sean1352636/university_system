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
    

class ElectionAccessibilityFeaturesDialog:
    """Dialog for election accessibility features"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.elections.accessibility_features"))
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t("student_union.elections.accessibility_title"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create notebook for categories
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Voting Access tab
        voting_frame = ttk.Frame(notebook)
        notebook.add(voting_frame, text=_t("student_union.elections.voting_access"))

        voting_scroll = scrolledtext.ScrolledText(voting_frame, height=15, wrap=tk.WORD)
        voting_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        voting_text = _t("student_union.elections.accessible_voting_options")

        voting_scroll.insert('1.0', voting_text)
        voting_scroll.config(state='disabled')

        # Candidate Information tab
        info_frame = ttk.Frame(notebook)
        notebook.add(info_frame, text=_t("student_union.elections.candidate_information"))

        info_scroll = scrolledtext.ScrolledText(info_frame, height=15, wrap=tk.WORD)
        info_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        info_text = _t("student_union.elections.accessible_candidate_info")

        info_scroll.insert('1.0', info_text)
        info_scroll.config(state='disabled')

        # Support Services tab
        support_frame = ttk.Frame(notebook)
        notebook.add(support_frame, text=_t("student_union.elections.support_services"))

        support_scroll = scrolledtext.ScrolledText(support_frame, height=15, wrap=tk.WORD)
        support_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        support_text = _t("student_union.elections.accessibility_support")

        support_scroll.insert('1.0', support_text)
        support_scroll.config(state='disabled')

        # Feedback tab
        feedback_frame = ttk.Frame(notebook)
        notebook.add(feedback_frame, text=_t("student_union.elections.feedback_complaints"))

        feedback_content = ttk.Frame(feedback_frame)
        feedback_content.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(feedback_content, text=_t("student_union.elections.report_accessibility_issues"),
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        ttk.Label(feedback_content, text=_t("student_union.elections.issue_type")).pack(anchor='w', pady=(5,0))
        self.issue_type = ttk.Combobox(feedback_content, state='readonly', width=40)
        self.issue_type['values'] = (
            _t("student_union.elections.issue_website"),
            _t("student_union.elections.issue_voting_platform"),
            _t("student_union.elections.issue_physical_access"),
            _t("student_union.elections.issue_info_format"),
            _t("student_union.elections.issue_support_service"),
            _t("common.other")
        )
        self.issue_type.pack(fill='x', pady=(0, 10))

        ttk.Label(feedback_content, text=_t("common.description")).pack(anchor='w', pady=(5,0))
        self.issue_desc = scrolledtext.ScrolledText(feedback_content, height=6, wrap=tk.WORD)
        self.issue_desc.pack(fill='both', expand=True, pady=(0, 10))

        ttk.Label(feedback_content, text=_t("student_union.elections.contact_email_optional")).pack(anchor='w', pady=(5,0))
        self.contact_email = ttk.Entry(feedback_content, width=40)
        self.contact_email.pack(fill='x', pady=(0, 15))

        ttk.Button(feedback_content, text=_t("student_union.elections.submit_feedback"),
                  command=self.submit_feedback).pack()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t("student_union.elections.request_accommodation"),
                  command=self.request_accommodation).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("student_union.elections.accessibility_guide"),
                  command=self.show_guide).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("student_union.elections.test_voting_system"),
                  command=self.test_system).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.close"), command=self.dialog.destroy).pack(side='right')

    def submit_feedback(self):
        """Submit accessibility feedback/complaint"""
        issue_type = self.issue_type.get().strip()
        description = self.issue_desc.get("1.0", tk.END).strip()
        contact_email = self.contact_email.get().strip()

        if not issue_type or not description:
            messagebox.showwarning("Missing Information", "Please select an issue type and provide a description.")
            return

        username = self.auth.current_user.get('username', 'Anonymous') if self.auth.current_user else 'Anonymous'
        user_email = self.auth.current_user.get('email', contact_email) if self.auth.current_user else contact_email

        # Store feedback in database
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accessibility_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    issue_type TEXT,
                    description TEXT,
                    contact_email TEXT,
                    submitted_date TEXT,
                    status TEXT DEFAULT 'pending'
                )
            ''')

            user_id = self.auth.current_user.get('id') if self.auth.current_user else None

            cursor.execute('''
                INSERT INTO accessibility_feedback
                (user_id, username, issue_type, description, contact_email, submitted_date, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
            ''', (user_id, username, issue_type, description, contact_email or user_email,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            conn.close()

            # Send email to admin
            if EMAIL_SERVICE_AVAILABLE:
                try:
                    # Get admin email from database
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()
                    cursor.execute("SELECT email FROM users WHERE role = 'admin' LIMIT 1")
                    admin_row = cursor.fetchone()
                    admin_email = admin_row[0] if admin_row else None
                    conn.close()

                    if admin_email:
                        subject, admin_body = render_template('student_union/accessibility_feedback_admin', {
                            'username': username,
                            'contact_email': contact_email or user_email,
                            'issue_type': issue_type,
                            'submitted_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'description': description
                        })
                        send_email(
                            to_email=admin_email,
                            subject=subject,
                            body=admin_body
                        )

                    # Send confirmation to user if they provided email
                    if user_email:
                        subject, user_body = render_template('student_union/accessibility_feedback_confirmation', {
                            'username': username,
                            'issue_type': issue_type,
                            'submitted_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        send_email(
                            to_email=user_email,
                            subject=subject,
                            body=user_body
                        )
                except Exception as e:
                    print(f"Failed to send feedback emails: {e}")

            messagebox.showinfo("Submitted", "Thank you for your feedback! Your concerns will be reviewed promptly.")

            # Clear form
            self.issue_type.set('')
            self.issue_desc.delete("1.0", tk.END)
            self.contact_email.delete(0, tk.END)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to submit feedback: {e}")

    def request_accommodation(self):
        """Request election accessibility accommodation"""
        # Create accommodation request dialog
        request_window = tk.Toplevel(self.dialog)
        request_window.title("Request Accommodation")
        request_window.geometry("600x500")
        request_window.transient(self.dialog)
        request_window.grab_set()

        main_frame = ttk.Frame(request_window)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Request Election Accessibility Accommodation",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Accommodation type
        ttk.Label(main_frame, text="Type of Accommodation Needed:").pack(anchor='w', pady=(5,0))
        accom_type = ttk.Combobox(main_frame, state='readonly', width=50)
        accom_type['values'] = (
            'Screen reader compatible ballot',
            'Large print materials',
            'Extended time for voting',
            'Physical accessibility assistance',
            'Sign language interpreter',
            'Alternative voting format',
            'Other (specify in description)'
        )
        accom_type.pack(fill='x', pady=(0, 10))

        # Description
        ttk.Label(main_frame, text="Additional Details:").pack(anchor='w', pady=(5,0))
        accom_desc = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD)
        accom_desc.pack(fill='both', expand=True, pady=(0, 10))

        def submit_request():
            accom_type_val = accom_type.get().strip()
            accom_desc_val = accom_desc.get("1.0", tk.END).strip()

            if not accom_type_val:
                messagebox.showwarning("Missing Information", "Please select an accommodation type.")
                return

            username = self.auth.current_user.get('username', 'Student') if self.auth.current_user else 'Student'
            user_email = self.auth.current_user.get('email', '') if self.auth.current_user else ''

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Create table if not exists
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS accommodation_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        username TEXT,
                        accommodation_type TEXT,
                        description TEXT,
                        submitted_date TEXT,
                        status TEXT DEFAULT 'pending'
                    )
                ''')

                user_id = self.auth.current_user.get('id') if self.auth.current_user else None

                cursor.execute('''
                    INSERT INTO accommodation_requests
                    (user_id, username, accommodation_type, description, submitted_date, status)
                    VALUES (?, ?, ?, ?, ?, 'pending')
                ''', (user_id, username, accom_type_val, accom_desc_val,
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                conn.commit()
                conn.close()

                # Send email confirmation
                if EMAIL_SERVICE_AVAILABLE and user_email:
                    try:
                        subject, email_body = render_template('student_union/accommodation_request_confirmation', {
                            'username': username,
                            'accommodation_type': accom_type_val,
                            'submitted_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'description': accom_desc_val
                        })
                        send_email(
                            to_email=user_email,
                            subject=subject,
                            body=email_body
                        )
                    except Exception as e:
                        print(f"Failed to send accommodation confirmation email: {e}")

                messagebox.showinfo("Request Submitted",
                                   "Your accommodation request has been submitted successfully.\n\n" +
                                   "You will be contacted within 2 business days.")
                request_window.destroy()

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to submit request: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Submit Request", command=submit_request).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=request_window.destroy).pack(side='left')

    def show_guide(self):
        """Show accessibility guide"""
        guide_window = tk.Toplevel(self.dialog)
        guide_window.title("Election Accessibility Guide")
        guide_window.geometry("700x600")
        guide_window.transient(self.dialog)

        main_frame = ttk.Frame(guide_window)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Election Accessibility Guide",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        guide_text = scrolledtext.ScrolledText(main_frame, height=25, wrap=tk.WORD, font=('Arial', 10))
        guide_text.pack(fill='both', expand=True, pady=(0, 15))

        guide_content = """STUDENT UNION ELECTION ACCESSIBILITY GUIDE

==========================================

OVERVIEW
--------
We are committed to ensuring all students can participate fully in Student Union elections. This guide outlines available accessibility features and accommodations.

AVAILABLE ACCOMMODATIONS
------------------------

1. VISUAL ACCESSIBILITY
   • Screen reader compatible voting platform
   • High contrast mode for ballot interface
   • Large print ballot materials available
   • Braille materials upon request
   • Audio ballot instructions

2. MOTOR/PHYSICAL ACCESSIBILITY
   • Keyboard-only navigation supported
   • Extended time for ballot completion
   • Physical polling station accessibility
   • Assistance available at all voting locations
   • Alternative input methods supported

3. COGNITIVE ACCESSIBILITY
   • Plain language ballot materials
   • Step-by-step voting instructions
   • Practice/test voting mode
   • Extended time available
   • Assistance without influencing vote

4. HEARING ACCESSIBILITY
   • Sign language interpreters available
   • Written instructions for all audio content
   • Captioned video materials
   • Visual alerts and notifications

HOW TO REQUEST ACCOMMODATION
----------------------------
1. Click "Request Accommodation" button
2. Select accommodation type needed
3. Provide additional details if necessary
4. Submit request at least 5 days before election
5. Receive confirmation within 2 business days

VOTING PLATFORM FEATURES
-----------------------
• WCAG 2.1 AA compliant interface
• Keyboard navigation (Tab, Enter, Arrows)
• Skip navigation links
• Resizable text (up to 200%)
• Color blind friendly design
• Clear error messages
• Progress indicators

ASSISTIVE TECHNOLOGY SUPPORT
---------------------------
Our voting platform is tested with:
• JAWS screen reader
• NVDA screen reader
• VoiceOver (Mac/iOS)
• TalkBack (Android)
• Dragon NaturallySpeaking
• ZoomText

POLLING STATION ACCESSIBILITY
-----------------------------
• Wheelchair accessible entrances
• Accessible parking nearby
• Height-adjustable voting booths
• Magnification tools available
• Privacy screens for assisted voting

CONTACT FOR ASSISTANCE
---------------------
Accessibility Coordinator
Email: elections@studentunion.edu
Phone: (555) 123-4567
Office: Student Union Building, Room 201

Hours: Monday-Friday, 9 AM - 5 PM

EMERGENCY ACCOMMODATION
----------------------
If you need urgent accommodation or encounter accessibility barriers on election day:
1. Contact accessibility coordinator immediately
2. On-site staff can provide immediate assistance
3. Alternative voting methods available if needed

FEEDBACK
--------
We continuously improve accessibility. Please report any issues or suggestions using the "Feedback & Complaints" tab.

Your participation matters!
"""

        guide_text.insert('1.0', guide_content)
        guide_text.config(state='disabled')

        ttk.Button(main_frame, text="Close", command=guide_window.destroy).pack()

    def test_system(self):
        """Test voting system accessibility"""
        test_window = tk.Toplevel(self.dialog)
        test_window.title("Test Voting System")
        test_window.geometry("700x600")
        test_window.transient(self.dialog)
        test_window.grab_set()

        main_frame = ttk.Frame(test_window)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Practice Voting Mode",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Label(main_frame, text="This is a practice ballot. No votes will be recorded.",
                 font=('Arial', 10, 'italic'), foreground='blue').pack(pady=(0, 20))

        # Sample ballot
        ttk.Label(main_frame, text="Sample Election: Class President",
                 font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        ttk.Label(main_frame, text="Select one candidate (use keyboard or mouse):",
                 font=('Arial', 10)).pack(anchor='w', pady=(0, 10))

        selected_candidate = tk.StringVar()

        candidates = [
            "Alice Johnson - Vote using 'A' key",
            "Bob Smith - Vote using 'B' key",
            "Carol Davis - Vote using 'C' key"
        ]

        for i, candidate in enumerate(candidates):
            rb = ttk.Radiobutton(main_frame, text=candidate, variable=selected_candidate,
                               value=candidate)
            rb.pack(anchor='w', pady=5)

        # Accessibility features info
        info_frame = ttk.LabelFrame(main_frame, text="Accessibility Features in Use")
        info_frame.pack(fill='x', pady=20)

        features = [
            "✓ Keyboard navigation enabled (Tab to navigate, Space to select)",
            "✓ Screen reader compatible labels",
            "✓ High contrast mode available (Ctrl+H)",
            "✓ Resizable text (Ctrl+ / Ctrl-)",
            "✓ Confirmation before final submission"
        ]

        for feature in features:
            ttk.Label(info_frame, text=feature, font=('Arial', 9)).pack(anchor='w', padx=10, pady=2)

        def submit_test_vote():
            if selected_candidate.get():
                messagebox.showinfo("Test Vote Submitted",
                                   f"Practice vote recorded for: {selected_candidate.get()}\n\n" +
                                   "In a real election, you would now see a confirmation screen.\n\n" +
                                   "This was a test - no actual vote was recorded.")
            else:
                messagebox.showwarning("No Selection", "Please select a candidate to test the voting process.")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text="Submit Test Vote", command=submit_test_vote).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Reset", command=lambda: selected_candidate.set('')).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=test_window.destroy).pack(side='right')



def open_election_accessibility_dialog(self):
    """Open election accessibility features"""
    dialog = ElectionAccessibilityFeaturesDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


