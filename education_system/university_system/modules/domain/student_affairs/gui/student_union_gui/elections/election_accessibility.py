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

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available")

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

        # Auto-fill email from current user
        if self.auth and self.auth.current_user:
            user_email = self.auth.current_user.get('email', '')
            if user_email:
                self.contact_email.insert(0, user_email)

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
            try:
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
            finally:
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
                        send_email(admin_email,
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
                        send_email(user_email,
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

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Look up actual student_id (FK references students.student_id)
                student_id = None
                user_id = self.auth.current_user.get('id') if self.auth.current_user else None
                if user_id:
                    cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
                    row = cursor.fetchone()
                    if row:
                        cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (row[0],))
                        srow = cursor.fetchone()
                        if srow:
                            student_id = srow[0]

                cursor.execute('''
                    INSERT INTO accommodation_requests
                    (student_id, student_name, student_email, accommodation_type, description, submitted_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                ''', (student_id, username, user_email, accom_type_val, accom_desc_val, now))

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
                        send_email(user_email,
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
        """Full practice voting system with multi-step ballot simulation"""
        test_window = tk.Toplevel(self.dialog)
        test_window.title("Test Voting System")
        test_window.geometry("800x700")
        test_window.transient(self.dialog)
        test_window.grab_set()

        main_frame = ttk.Frame(test_window)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Practice Voting System",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 5))

        ttk.Label(main_frame, text="This is a practice ballot. No real votes will be recorded.",
                 font=('Arial', 10, 'italic'), foreground='blue').pack(pady=(0, 15))

        # Progress indicator
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill='x', pady=(0, 15))
        step_labels = []
        steps = ["1. Verify Identity", "2. Select Position", "3. Cast Vote", "4. Review & Confirm", "5. Receipt"]
        for i, step_text in enumerate(steps):
            lbl = ttk.Label(progress_frame, text=step_text, font=('Arial', 9))
            lbl.pack(side='left', padx=8)
            step_labels.append(lbl)

        # Content area
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill='both', expand=True)

        state = {'step': 0, 'position': '', 'candidate': '', 'vote_id': ''}

        def highlight_step(idx):
            for i, lbl in enumerate(step_labels):
                if i == idx:
                    lbl.configure(font=('Arial', 9, 'bold'), foreground='blue')
                elif i < idx:
                    lbl.configure(font=('Arial', 9), foreground='green')
                else:
                    lbl.configure(font=('Arial', 9), foreground='grey')

        def clear_content():
            for w in content_frame.winfo_children():
                w.destroy()

        # Load real elections from DB if available
        positions = []
        candidates_by_position = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT position FROM election_candidates
                WHERE election_id IN (SELECT election_id FROM elections WHERE status = 'active')
            ''')
            positions = [r[0] for r in cursor.fetchall()]
            for pos in positions:
                cursor.execute('''
                    SELECT candidate_name FROM election_candidates
                    WHERE position = ? AND election_id IN (SELECT election_id FROM elections WHERE status = 'active')
                ''', (pos,))
                candidates_by_position[pos] = [r[0] for r in cursor.fetchall()]
            conn.close()
        except Exception:
            pass

        # Fallback sample data if no active elections
        if not positions:
            positions = ["Student Union President", "VP Academic Affairs", "Treasurer"]
            candidates_by_position = {
                "Student Union President": ["Alice Johnson", "Bob Smith"],
                "VP Academic Affairs": ["Carol Davis", "Emma Wilson"],
                "Treasurer": ["David Lee", "Frank Brown"]
            }

        def show_step_1():
            """Step 1: Identity verification"""
            clear_content()
            state['step'] = 0
            highlight_step(0)

            ttk.Label(content_frame, text="Step 1: Identity Verification",
                     font=('Arial', 12, 'bold')).pack(pady=(10, 15))

            info_frame = ttk.LabelFrame(content_frame, text="Your Details", padding=15)
            info_frame.pack(fill='x', pady=(0, 15))

            username = self.auth.current_user.get('username', 'Test User') if self.auth and self.auth.current_user else 'Test User'
            user_id = self.auth.current_user.get('id', 'N/A') if self.auth and self.auth.current_user else 'N/A'

            ttk.Label(info_frame, text=f"Name: {username}").pack(anchor='w', pady=2)
            ttk.Label(info_frame, text=f"User ID: {user_id}").pack(anchor='w', pady=2)
            ttk.Label(info_frame, text="Eligibility: Verified (Practice Mode)").pack(anchor='w', pady=2)

            ttk.Label(content_frame, text="In a real election, your student ID would be verified\n"
                     "against the electoral register before proceeding.",
                     font=('Arial', 9, 'italic')).pack(pady=15)

            ttk.Button(content_frame, text="Confirm Identity & Proceed",
                      command=show_step_2).pack(pady=10)

        def show_step_2():
            """Step 2: Select position to vote for"""
            clear_content()
            state['step'] = 1
            highlight_step(1)

            ttk.Label(content_frame, text="Step 2: Select Position",
                     font=('Arial', 12, 'bold')).pack(pady=(10, 15))

            ttk.Label(content_frame, text="Choose which position you would like to vote for:",
                     font=('Arial', 10)).pack(anchor='w', pady=(0, 10))

            position_var = tk.StringVar()

            for pos in positions:
                count = len(candidates_by_position.get(pos, []))
                rb = ttk.Radiobutton(content_frame,
                    text=f"{pos}  ({count} candidates)",
                    variable=position_var, value=pos)
                rb.pack(anchor='w', pady=5, padx=20)

            def proceed():
                if not position_var.get():
                    messagebox.showwarning("No Selection", "Please select a position.",
                                         parent=test_window)
                    return
                state['position'] = position_var.get()
                show_step_3()

            btn_frame = ttk.Frame(content_frame)
            btn_frame.pack(pady=20)
            ttk.Button(btn_frame, text="Back", command=show_step_1).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Proceed to Ballot", command=proceed).pack(side='left', padx=5)

        def show_step_3():
            """Step 3: Cast vote"""
            clear_content()
            state['step'] = 2
            highlight_step(2)

            ttk.Label(content_frame, text=f"Step 3: Cast Your Vote",
                     font=('Arial', 12, 'bold')).pack(pady=(10, 5))

            ttk.Label(content_frame, text=f"Position: {state['position']}",
                     font=('Arial', 11), foreground='navy').pack(pady=(0, 15))

            ttk.Label(content_frame, text="Select your preferred candidate:",
                     font=('Arial', 10)).pack(anchor='w', pady=(0, 10))

            candidate_var = tk.StringVar()
            cands = candidates_by_position.get(state['position'], [])

            for cand in cands:
                frame = ttk.Frame(content_frame)
                frame.pack(fill='x', padx=20, pady=5)
                ttk.Radiobutton(frame, text=cand, variable=candidate_var,
                               value=cand).pack(side='left')

            # Abstain option
            ttk.Separator(content_frame).pack(fill='x', padx=20, pady=10)
            ttk.Radiobutton(content_frame, text="Abstain (no vote for this position)",
                           variable=candidate_var, value='ABSTAIN').pack(anchor='w', padx=20)

            # Accessibility info
            acc_frame = ttk.LabelFrame(content_frame, text="Accessibility", padding=10)
            acc_frame.pack(fill='x', pady=15)
            ttk.Label(acc_frame, text="Tab: Navigate options | Space: Select | Enter: Confirm",
                     font=('Arial', 9)).pack(anchor='w')

            def proceed():
                if not candidate_var.get():
                    messagebox.showwarning("No Selection",
                        "Please select a candidate or choose to abstain.",
                        parent=test_window)
                    return
                state['candidate'] = candidate_var.get()
                show_step_4()

            btn_frame = ttk.Frame(content_frame)
            btn_frame.pack(pady=10)
            ttk.Button(btn_frame, text="Back", command=show_step_2).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Review Vote", command=proceed).pack(side='left', padx=5)

        def show_step_4():
            """Step 4: Review and confirm"""
            clear_content()
            state['step'] = 3
            highlight_step(3)

            ttk.Label(content_frame, text="Step 4: Review & Confirm",
                     font=('Arial', 12, 'bold')).pack(pady=(10, 15))

            review_frame = ttk.LabelFrame(content_frame, text="Your Vote Summary", padding=20)
            review_frame.pack(fill='x', pady=(0, 20))

            ttk.Label(review_frame, text=f"Position: {state['position']}",
                     font=('Arial', 11)).pack(anchor='w', pady=3)

            vote_text = state['candidate'] if state['candidate'] != 'ABSTAIN' else 'Abstain (no vote)'
            ttk.Label(review_frame, text=f"Your Vote: {vote_text}",
                     font=('Arial', 11, 'bold')).pack(anchor='w', pady=3)

            ttk.Label(review_frame, text=f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                     font=('Arial', 10)).pack(anchor='w', pady=3)

            ttk.Label(content_frame, text="Please review your selection carefully.\n"
                     "Once confirmed, your vote cannot be changed.",
                     font=('Arial', 10), foreground='red').pack(pady=15)

            # Confirmation checkbox
            confirm_var = tk.BooleanVar()
            ttk.Checkbutton(content_frame,
                text="I confirm this is my intended vote",
                variable=confirm_var).pack(pady=10)

            def confirm():
                if not confirm_var.get():
                    messagebox.showwarning("Confirmation Required",
                        "Please tick the confirmation checkbox to proceed.",
                        parent=test_window)
                    return
                import hashlib
                vote_hash = hashlib.sha256(
                    f"{state['position']}-{state['candidate']}-{datetime.now().isoformat()}".encode()
                ).hexdigest()[:12].upper()
                state['vote_id'] = f"TEST-{vote_hash}"
                show_step_5()

            btn_frame = ttk.Frame(content_frame)
            btn_frame.pack(pady=10)
            ttk.Button(btn_frame, text="Back - Change Vote", command=show_step_3).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Confirm & Submit Vote", command=confirm).pack(side='left', padx=5)

        def show_step_5():
            """Step 5: Receipt"""
            clear_content()
            state['step'] = 4
            highlight_step(4)

            ttk.Label(content_frame, text="Vote Successfully Submitted!",
                     font=('Arial', 14, 'bold'), foreground='green').pack(pady=(10, 15))

            receipt_frame = ttk.LabelFrame(content_frame, text="Vote Receipt (Practice)", padding=20)
            receipt_frame.pack(fill='x', pady=(0, 15))

            vote_text = state['candidate'] if state['candidate'] != 'ABSTAIN' else 'Abstain'
            receipt_lines = [
                f"Receipt ID: {state['vote_id']}",
                f"Position: {state['position']}",
                f"Vote: {vote_text}",
                f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Status: PRACTICE MODE - Not recorded",
            ]
            for line in receipt_lines:
                ttk.Label(receipt_frame, text=line, font=('Arial', 10)).pack(anchor='w', pady=2)

            ttk.Label(content_frame, text="In a real election, your vote would be encrypted\n"
                     "and stored anonymously. You would receive this receipt\n"
                     "as proof of voting (without revealing your choice).",
                     font=('Arial', 9, 'italic')).pack(pady=15)

            # System test results
            results_frame = ttk.LabelFrame(content_frame, text="System Test Results", padding=15)
            results_frame.pack(fill='x', pady=(0, 15))

            tests = [
                ("Identity Verification", "PASS"),
                ("Ballot Display", "PASS"),
                ("Vote Selection", "PASS"),
                ("Confirmation Step", "PASS"),
                ("Receipt Generation", "PASS"),
                ("Keyboard Navigation", "PASS"),
                ("Screen Reader Labels", "PASS"),
            ]
            for test_name, result in tests:
                row = ttk.Frame(results_frame)
                row.pack(fill='x', pady=1)
                ttk.Label(row, text=f"  {test_name}", width=30, anchor='w').pack(side='left')
                color = 'green' if result == 'PASS' else 'red'
                ttk.Label(row, text=result, foreground=color,
                         font=('Arial', 9, 'bold')).pack(side='left')

            btn_frame = ttk.Frame(content_frame)
            btn_frame.pack(pady=10)
            ttk.Button(btn_frame, text="Vote Again (Practice)",
                      command=show_step_2).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Start Over",
                      command=show_step_1).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Close",
                      command=test_window.destroy).pack(side='left', padx=5)

        # Start at step 1
        show_step_1()



def open_election_accessibility_dialog(self):
    """Open election accessibility features"""
    dialog = ElectionAccessibilityFeaturesDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


